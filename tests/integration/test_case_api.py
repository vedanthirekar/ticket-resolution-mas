from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from luma.api.app import create_app
from luma.config import Settings
from luma.db.models.case_management import Escalation, OperationsAccount, SupportCase
from luma.domain.cases import CaseSource, CaseStatus, ClaimedCaseCategory
from luma.services.auth import hash_password
from luma.services.cases import CreateCaseCommand, create_case, transition_case

pytestmark = pytest.mark.integration


async def test_api_intake_retry_and_authenticated_case_queue(database) -> None:
    username = "api-runtime-test"
    password = "api-runtime-test-password"
    request_key = "api-runtime-case-001"
    eval_request_key = "eval:api-runtime-hidden-001"
    async with database.transaction() as session:
        await session.execute(
            delete(SupportCase).where(
                SupportCase.external_request_key.in_([request_key, eval_request_key])
            )
        )
        await session.execute(
            delete(OperationsAccount).where(OperationsAccount.username == username)
        )
        session.add(
            OperationsAccount(
                username=username,
                password_hash=hash_password(password),
                display_name="API Test Operator",
                active=True,
            )
        )

    settings = Settings(_env_file=None)
    app = create_app(settings)
    try:
        async with app.router.lifespan_context(app):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                payload = {
                    "complaint_text": "The provider cancelled but I paid a fee.",
                    "source": "manual",
                    "external_request_key": request_key,
                    "claimed_category": "cancellation_fee_dispute",
                }
                created = await client.post("/api/cases", json=payload)
                retried = await client.post("/api/cases", json=payload)
                eval_case = await client.post(
                    "/api/cases",
                    json={
                        **payload,
                        "source": "api",
                        "external_request_key": eval_request_key,
                    },
                )
                assert created.status_code == 201
                assert retried.status_code == 200
                assert eval_case.status_code == 201
                assert created.json()["public_reference"] == retried.json()["public_reference"]
                assert created.json()["claimed_category"] == "cancellation_fee_dispute"

                unauthorized = await client.get("/api/cases")
                assert unauthorized.status_code == 401
                login = await client.post(
                    "/api/auth/login", json={"username": username, "password": password}
                )
                assert login.status_code == 200
                token = login.json()["access_token"]
                queue = await client.get("/api/cases", headers={"Authorization": f"Bearer {token}"})
                assert queue.status_code == 200
                assert any(
                    item["public_reference"] == created.json()["public_reference"]
                    for item in queue.json()
                )
                operations_queue = await client.get(
                    "/api/operations/cases",
                    headers={"Authorization": f"Bearer {token}"},
                )
                assert operations_queue.status_code == 200
                operation_references = {
                    item["public_reference"] for item in operations_queue.json()
                }
                assert created.json()["public_reference"] in operation_references
                assert eval_case.json()["public_reference"] not in operation_references

                overview = await client.get(
                    "/api/operations/overview",
                    headers={"Authorization": f"Bearer {token}"},
                )
                assert overview.status_code == 200
                assert overview.json()["total_cases"] >= 1

                research_payload = {
                    "tool_name": "get_customer",
                    "arguments": {"customer_reference": "CUS-0001"},
                }
                unauthorized_research = await client.post(
                    "/api/operations/research", json=research_payload
                )
                assert unauthorized_research.status_code == 401
                research = await client.post(
                    "/api/operations/research",
                    json=research_payload,
                    headers={"Authorization": f"Bearer {token}"},
                )
                assert research.status_code == 200
                assert research.json()["tool_name"] == "get_customer"
                assert research.json()["evidence_type"] == "customer_identity"
                assert research.json()["data"]["customer_reference"] == "CUS-0001"
                assert research.json()["metadata"]["source_system"] == "luma_postgresql"

                invoice_research = await client.post(
                    "/api/operations/research",
                    json={
                        "tool_name": "get_appointment_payments",
                        "arguments": {
                            "customer_reference": "CUS-0007",
                            "appointment_reference": "APPT-DUP-PAY",
                        },
                    },
                    headers={"Authorization": f"Bearer {token}"},
                )
                assert invoice_research.status_code == 200
                assert invoice_research.json()["data"]["appointment_reference"] == "APPT-DUP-PAY"
                assert len(invoice_research.json()["data"]["payments"]) == 2
                assert all(
                    payment["invoice_reference"]
                    for payment in invoice_research.json()["data"]["payments"]
                )

                wrong_customer = await client.post(
                    "/api/operations/research",
                    json={
                        "tool_name": "get_appointment_payments",
                        "arguments": {
                            "customer_reference": "CUS-0001",
                            "appointment_reference": "APPT-DUP-PAY",
                        },
                    },
                    headers={"Authorization": f"Bearer {token}"},
                )
                assert wrong_customer.status_code == 404

                invalid_research = await client.post(
                    "/api/operations/research",
                    json={"tool_name": "get_customer", "arguments": {}},
                    headers={"Authorization": f"Bearer {token}"},
                )
                assert invalid_research.status_code == 422

                policy_search = await client.get(
                    "/api/operations/policies/search",
                    params={
                        "query": "provider cancelled cancellation fee",
                        "effective_on": "2026-08-20",
                        "policy_area": "cancellation",
                    },
                    headers={"Authorization": f"Bearer {token}"},
                )
                assert policy_search.status_code == 200
                assert any(item["section_id"] == "POL-CAN-v2#4.1" for item in policy_search.json())

                workspace = await client.get(
                    f"/api/operations/cases/{created.json()['public_reference']}",
                    headers={"Authorization": f"Bearer {token}"},
                )
                assert workspace.status_code == 200
                assert workspace.json()["status"] in {
                    "queued",
                    "processing",
                    "human_investigation",
                }
                assert [event["event_type"] for event in workspace.json()["events"]][:2] == [
                    "case_received",
                    "case_queued",
                ]

                hidden_workspace = await client.get(
                    f"/api/operations/cases/{eval_case.json()['public_reference']}",
                    headers={"Authorization": f"Bearer {token}"},
                )
                assert hidden_workspace.status_code == 404
    finally:
        async with database.transaction() as session:
            await session.execute(
                delete(SupportCase).where(
                    SupportCase.external_request_key.in_([request_key, eval_request_key])
                )
            )
            await session.execute(
                delete(OperationsAccount).where(OperationsAccount.username == username)
            )


async def test_employee_can_document_and_close_human_investigation(database) -> None:
    username = "investigation-api-test"
    password = "investigation-api-test-password"
    request_key = "investigation-api-case-001"
    async with database.transaction() as session:
        await session.execute(
            delete(SupportCase).where(SupportCase.external_request_key == request_key)
        )
        await session.execute(
            delete(OperationsAccount).where(OperationsAccount.username == username)
        )
        account = OperationsAccount(
            username=username,
            password_hash=hash_password(password),
            display_name="Investigation Test Operator",
            active=True,
        )
        session.add(account)
        created = await create_case(
            session,
            CreateCaseCommand(
                complaint_text="I cannot identify the appointment that disappeared.",
                source=CaseSource.MANUAL,
                external_request_key=request_key,
                claimed_customer_reference="CUS-0001",
                contact_email="Customer.One@Example.com",
                claimed_category=ClaimedCaseCategory.MISSING_APPOINTMENT,
            ),
        )
        await transition_case(
            session,
            case_id=created.case.id,
            to_status=CaseStatus.HUMAN_INVESTIGATION,
            event_type="agent_escalated",
            actor_type="agent",
            actor_reference="case_manager",
            payload={"reason_code": "required_operational_evidence_missing"},
        )
        session.add(
            Escalation(
                case_id=created.case.id,
                reason_code="required_operational_evidence_missing",
                details={"missing_evidence": ["booking_history"]},
                status="open",
            )
        )
        case_reference = created.case.public_reference

    settings = Settings(_env_file=None)
    app = create_app(settings)
    try:
        async with app.router.lifespan_context(app):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                unauthenticated = await client.post(
                    f"/api/operations/cases/{case_reference}/investigation/acknowledge"
                )
                assert unauthenticated.status_code == 401

                login = await client.post(
                    "/api/auth/login", json={"username": username, "password": password}
                )
                token = login.json()["access_token"]
                headers = {"Authorization": f"Bearer {token}"}

                premature_send = await client.post(
                    f"/api/operations/cases/{case_reference}/customer-communication/send",
                    headers=headers,
                    json={"subject": "Too early", "body": "This must not be sent."},
                )
                assert premature_send.status_code == 409

                acknowledged = await client.post(
                    f"/api/operations/cases/{case_reference}/investigation/acknowledge",
                    headers=headers,
                )
                repeated_acknowledgement = await client.post(
                    f"/api/operations/cases/{case_reference}/investigation/acknowledge",
                    headers=headers,
                )
                assert acknowledged.status_code == 200
                assert repeated_acknowledgement.status_code == 200
                assert acknowledged.json()["escalation_status"] == "acknowledged"

                note = await client.post(
                    f"/api/operations/cases/{case_reference}/investigation/notes",
                    headers=headers,
                    json={"note": "Checked the booking history and confirmed no reservation."},
                )
                assert note.status_code == 200

                resolved = await client.post(
                    f"/api/operations/cases/{case_reference}/investigation/resolve",
                    headers=headers,
                    json={
                        "resolution_code": "customer_guidance_provided",
                        "resolution_summary": (
                            "No appointment was committed; guidance was provided."
                        ),
                        "customer_response": (
                            "We found no completed reservation and can help you rebook."
                        ),
                    },
                )
                assert resolved.status_code == 200
                assert resolved.json() == {
                    "case_status": "resolved",
                    "escalation_status": "resolved",
                }

                repeated_resolution = await client.post(
                    f"/api/operations/cases/{case_reference}/investigation/resolve",
                    headers=headers,
                    json={
                        "resolution_code": "customer_guidance_provided",
                        "resolution_summary": "Attempted duplicate closure.",
                        "customer_response": "This must not replace the original closure.",
                    },
                )
                assert repeated_resolution.status_code == 409

                workspace = await client.get(
                    f"/api/operations/cases/{case_reference}", headers=headers
                )
                assert workspace.status_code == 200
                workspace_payload = workspace.json()
                assert workspace_payload["status"] == "resolved"
                assert workspace_payload["contact_email"] == "customer.one@example.com"
                assert workspace_payload["escalations"][0]["status"] == "resolved"
                draft = workspace_payload["final_communication"]
                assert draft["status"] == "prepared"
                assert draft["recipient_email"] == "customer.one@example.com"
                assert "We found no completed reservation" in draft["body"]

                edited = {
                    "subject": f"Your case {case_reference} is complete",
                    "body": "Hello,\n\nWe found no completed reservation.\n\nLuma Wellness Support",
                }
                saved = await client.put(
                    f"/api/operations/cases/{case_reference}/customer-communication/draft",
                    headers=headers,
                    json=edited,
                )
                assert saved.status_code == 200
                assert saved.json()["subject"] == edited["subject"]

                sent = await client.post(
                    f"/api/operations/cases/{case_reference}/customer-communication/send",
                    headers=headers,
                    json=edited,
                )
                repeated_send = await client.post(
                    f"/api/operations/cases/{case_reference}/customer-communication/send",
                    headers=headers,
                    json=edited,
                )
                assert sent.status_code == 200
                assert repeated_send.status_code == 200
                assert sent.json()["status"] == "sent"
                assert sent.json()["delivery_reference"].startswith("MOCK-EMAIL-")

                edit_after_send = await client.put(
                    f"/api/operations/cases/{case_reference}/customer-communication/draft",
                    headers=headers,
                    json=edited,
                )
                assert edit_after_send.status_code == 409

                completed_workspace = await client.get(
                    f"/api/operations/cases/{case_reference}", headers=headers
                )
                completed_payload = completed_workspace.json()
                assert completed_payload["final_communication"]["sent_by"] == (
                    "Investigation Test Operator"
                )
                event_types = [event["event_type"] for event in completed_payload["events"]]
                assert event_types.count("human_investigation_started") == 1
                assert event_types.count("customer_email_mock_sent") == 1
                assert event_types[-4:] == [
                    "human_investigation_resolved",
                    "customer_email_draft_prepared",
                    "customer_email_draft_updated",
                    "customer_email_mock_sent",
                ]
    finally:
        async with database.transaction() as session:
            await session.execute(
                delete(SupportCase).where(SupportCase.external_request_key == request_key)
            )
            await session.execute(
                delete(OperationsAccount).where(OperationsAccount.username == username)
            )
