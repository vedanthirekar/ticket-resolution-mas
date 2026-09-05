from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from luma.api.app import create_app
from luma.config import Settings
from luma.db.models.case_management import OperationsAccount, SupportCase
from luma.services.auth import hash_password

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
                    "/api/operations/cases?status=queued",
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
                assert workspace.json()["status"] in {"queued", "processing"}
                assert workspace.json()["run"] is None
                assert workspace.json()["evidence"] == []
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
