from __future__ import annotations

from uuid import UUID

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from sqlalchemy import delete, select, update

from luma.agents.graph import CaseResolutionWorkflow
from luma.agents.models import ScriptedStructuredModel
from luma.agents.runner import resume_after_approval, run_case
from luma.config import Settings
from luma.db.models.ai_runtime import CaseRun, VerificationResult
from luma.db.models.billing import Payment, PaymentEvent, Refund
from luma.db.models.case_management import (
    ActionIntent,
    CustomerCommunication,
    ExecutionAttempt,
    OperationsAccount,
    ProcessingJob,
    SupportCase,
)
from luma.db.models.membership import MembershipLedgerEntry
from luma.domain.cases import CaseSource, CaseStatus
from luma.retrieval.embeddings import HashingEmbeddingProvider
from luma.services.actions import create_action_intent, decide_action, execute_approved_action
from luma.services.cases import CreateCaseCommand, create_case, transition_case
from luma.worker import process_next_job

pytestmark = pytest.mark.integration

REQUEST_KEYS = (
    "m7-approved-refund",
    "m7-verifier-reject",
    "m7-rejected-action",
    "m7-membership-adjustment",
    "m7-stale-action",
    "m9-worker-resume",
)
PAYMENT_REFERENCE = "PAY-001491-provider-fee"
ACCOUNT_USERNAME = "m7-test-operator"


async def _clean(database) -> None:
    async with database.transaction() as session:
        actions = (
            (
                await session.execute(
                    select(ActionIntent)
                    .join(SupportCase, SupportCase.id == ActionIntent.case_id)
                    .where(SupportCase.external_request_key.in_(REQUEST_KEYS))
                )
            )
            .scalars()
            .all()
        )
        if actions:
            await session.execute(
                delete(PaymentEvent).where(
                    PaymentEvent.correlation_reference.in_(
                        [action.public_reference for action in actions]
                    )
                )
            )
            await session.execute(
                delete(Refund).where(
                    Refund.idempotency_key.in_([action.idempotency_key for action in actions])
                )
            )
            await session.execute(
                delete(MembershipLedgerEntry).where(
                    MembershipLedgerEntry.idempotency_key.in_(
                        [action.idempotency_key for action in actions]
                    )
                )
            )
        await session.execute(
            update(Payment)
            .where(Payment.public_reference == PAYMENT_REFERENCE)
            .values(refunded_amount_cents=0, status="captured")
        )
        await session.execute(
            delete(SupportCase).where(SupportCase.external_request_key.in_(REQUEST_KEYS))
        )
        await session.execute(
            delete(OperationsAccount).where(OperationsAccount.username == ACCOUNT_USERNAME)
        )


@pytest.fixture(autouse=True)
async def clean_m7_cases(database):
    await _clean(database)
    async with database.transaction() as session:
        session.add(
            OperationsAccount(
                username=ACCOUNT_USERNAME,
                password_hash="not-used-by-service-test",
                display_name="M7 Test Operator",
                active=True,
            )
        )
    yield
    await _clean(database)


def _model(*, verifier_supported: bool = True) -> ScriptedStructuredModel:
    return ScriptedStructuredModel(
        {
            "case_manager_plan": [
                {
                    "category": "cancellation_fee_dispute",
                    "material_event_date": "2026-08-20",
                    "required_evidence_types": [],
                    "investigation_objectives": [
                        "Establish identity, cancellation initiator, and captured fee."
                    ],
                    "policy_query": "provider cancelled customer fee refund",
                    "policy_area": None,
                    "rationale": "Use operational truth and effective policy.",
                }
            ],
            "investigation_decision": [
                {
                    "complete": False,
                    "next_call": {
                        "tool_name": "get_customer",
                        "arguments": {"customer_reference": "CUS-0001"},
                        "purpose": "Establish identity.",
                    },
                    "rationale": "Identity is required first.",
                },
                {
                    "complete": False,
                    "next_call": {
                        "tool_name": "get_appointment_timeline",
                        "arguments": {
                            "customer_reference": "CUS-0001",
                            "appointment_reference": "APPT-CAN-PROVIDER",
                        },
                        "purpose": "Establish cancellation initiator.",
                    },
                    "rationale": "The reference is supplied by the complaint.",
                },
                {
                    "complete": False,
                    "next_call": {
                        "tool_name": "get_appointment_payments",
                        "arguments": {
                            "customer_reference": "CUS-0001",
                            "appointment_reference": "APPT-CAN-PROVIDER",
                        },
                        "purpose": "Establish captured fee and target payment.",
                    },
                    "rationale": "Payment evidence remains required.",
                },
                {
                    "complete": True,
                    "next_call": None,
                    "rationale": "The required operational evidence is present.",
                },
            ],
            "policy_assessment": [
                {
                    "applicable": True,
                    "selected_section_ids": ["POL-CAN-v2#4.1"],
                    "rule_summary": "Provider cancellations must not create a customer fee.",
                    "missing_evidence_types": [],
                    "supplemental_call": None,
                }
            ],
            "resolution_proposal": [
                {
                    "outcome": "refund_cancellation_fee",
                    "disposition": "human_approval",
                    "rationale": "The provider cancelled and the customer fee was captured.",
                    "action_payload": {
                        "action_type": "refund_payment",
                        "payment_reference": PAYMENT_REFERENCE,
                        "amount_cents": 8000,
                        "reason_code": "m7_test_provider_cancelled",
                    },
                    "evidence_references": ["APPT-CAN-PROVIDER", PAYMENT_REFERENCE],
                    "policy_references": ["POL-CAN-v2#4.1"],
                }
            ],
            "verification": [
                {
                    "supported": verifier_supported,
                    "missing_evidence": [],
                    "contradictions": [],
                    "unsupported_claims": [] if verifier_supported else ["refund amount"],
                    "recommended_outcome": (
                        "refund_cancellation_fee"
                        if verifier_supported
                        else "insufficient_grounding"
                    ),
                    "recommended_disposition": (
                        "human_approval" if verifier_supported else "human_investigation"
                    ),
                    "requires_human": True,
                    "rationale": (
                        "The exact action is supported."
                        if verifier_supported
                        else "The exact amount is not supported."
                    ),
                }
            ],
        }
    )


def _workflow(database, model: ScriptedStructuredModel) -> CaseResolutionWorkflow:
    return CaseResolutionWorkflow(
        database=database,
        model=model,
        embedding_provider=HashingEmbeddingProvider(),
        settings=Settings(_env_file=None),
    )


async def _new_case(database, request_key: str):
    async with database.transaction() as session:
        return (
            await create_case(
                session,
                CreateCaseCommand(
                    complaint_text=(
                        "I was charged $80 even though the provider cancelled APPT-CAN-PROVIDER."
                    ),
                    source=CaseSource.API,
                    external_request_key=request_key,
                    claimed_customer_reference="CUS-0001",
                    contact_email="workflow-customer@example.com",
                ),
            )
        ).case


async def test_approved_refund_resumes_revalidates_and_executes_once(database) -> None:
    case = await _new_case(database, "m7-approved-refund")
    saver = InMemorySaver()
    workflow = _workflow(database, _model())
    interrupted = await run_case(database, workflow, case_id=case.id, checkpointer=saver)
    action_reference = interrupted["action_intent_reference"]

    async with database.transaction() as session:
        account = (
            await session.execute(
                select(OperationsAccount).where(OperationsAccount.username == ACCOUNT_USERNAME)
            )
        ).scalar_one()
        await decide_action(
            session,
            action_reference=action_reference,
            account=account,
            decision="approved",
            rationale="Operational evidence and policy reviewed.",
        )
        resume_job = await session.scalar(
            select(ProcessingJob).where(
                ProcessingJob.case_id == case.id,
                ProcessingJob.job_type == f"approval_resume:{action_reference}",
            )
        )
        assert resume_job is not None
        assert resume_job.status == "queued"
    completed = await resume_after_approval(
        workflow, case_run_id=UUID(interrupted["case_run_id"]), checkpointer=saver
    )

    assert completed["execution_receipt"]["status"] == "succeeded"
    async with database.transaction() as session:
        repeated = await execute_approved_action(session, action_reference=action_reference)
    assert repeated.receipt == completed["execution_receipt"]
    async with database.session() as session:
        payment = await session.scalar(
            select(Payment).where(Payment.public_reference == PAYMENT_REFERENCE)
        )
        refunds = (
            (await session.execute(select(Refund).where(Refund.payment_id == payment.id)))
            .scalars()
            .all()
        )
        attempts = (
            (
                await session.execute(
                    select(ExecutionAttempt)
                    .join(ActionIntent, ActionIntent.id == ExecutionAttempt.action_intent_id)
                    .where(ActionIntent.public_reference == action_reference)
                )
            )
            .scalars()
            .all()
        )
        resolved_case = await session.get(SupportCase, case.id)
        communication = await session.scalar(
            select(CustomerCommunication).where(CustomerCommunication.case_id == case.id)
        )
    assert payment is not None and payment.refunded_amount_cents == 8000
    assert len([refund for refund in refunds if refund.status == "succeeded"]) == 1
    assert len(attempts) == 1
    assert resolved_case is not None and resolved_case.status == "resolved"
    assert communication is not None and communication.status == "prepared"
    assert "Refund completed: $80.00" in communication.body
    assert "REF-" in communication.body


async def test_verifier_rejection_escalates_without_action(database) -> None:
    case = await _new_case(database, "m7-verifier-reject")
    result = await run_case(
        database,
        _workflow(database, _model(verifier_supported=False)),
        case_id=case.id,
        checkpointer=InMemorySaver(),
    )
    async with database.session() as session:
        verification = await session.scalar(
            select(VerificationResult).where(
                VerificationResult.case_run_id == result["case_run_id"]
            )
        )
        action = await session.scalar(select(ActionIntent).where(ActionIntent.case_id == case.id))
        communication = await session.scalar(
            select(CustomerCommunication).where(CustomerCommunication.case_id == case.id)
        )
        escalated_case = await session.get(SupportCase, case.id)
    assert verification is not None and not verification.supported
    assert action is None
    assert communication is None
    assert escalated_case is not None and escalated_case.status == "human_investigation"


async def test_rejected_action_never_executes(database) -> None:
    case = await _new_case(database, "m7-rejected-action")
    saver = InMemorySaver()
    workflow = _workflow(database, _model())
    interrupted = await run_case(database, workflow, case_id=case.id, checkpointer=saver)
    async with database.transaction() as session:
        account = (
            await session.execute(
                select(OperationsAccount).where(OperationsAccount.username == ACCOUNT_USERNAME)
            )
        ).scalar_one()
        await decide_action(
            session,
            action_reference=interrupted["action_intent_reference"],
            account=account,
            decision="rejected",
            rationale="Operator rejected the proposed correction.",
        )
    result = await resume_after_approval(
        workflow, case_run_id=UUID(interrupted["case_run_id"]), checkpointer=saver
    )
    async with database.session() as session:
        attempt = await session.scalar(
            select(ExecutionAttempt)
            .join(ActionIntent, ActionIntent.id == ExecutionAttempt.action_intent_id)
            .where(ActionIntent.public_reference == interrupted["action_intent_reference"])
        )
    assert result["escalation_reason"] == "action_rejected_by_operations"
    assert attempt is None


async def test_membership_adjustment_is_append_only_and_idempotent(database) -> None:
    case = await _new_case(database, "m7-membership-adjustment")
    async with database.transaction() as session:
        await transition_case(
            session,
            case_id=case.id,
            to_status=CaseStatus.PROCESSING,
            event_type="service_test_started",
            actor_type="system",
            actor_reference="m7_test",
        )
        run = CaseRun(
            case_id=case.id,
            run_number=1,
            architecture_version="multi-agent-v1",
            model_provider="scripted",
            model_name="scripted",
            configuration={},
            status="running",
        )
        session.add(run)
        await session.flush()
        intent = await create_action_intent(
            session,
            case_id=case.id,
            case_run_id=run.id,
            action_payload={
                "action_type": "adjust_membership_credit",
                "membership_reference": "MEM-0001",
                "credit_delta": 1,
                "reason_code": "m7_test_credit_correction",
            },
        )
        account = (
            await session.execute(
                select(OperationsAccount).where(OperationsAccount.username == ACCOUNT_USERNAME)
            )
        ).scalar_one()
        await decide_action(
            session,
            action_reference=intent.public_reference,
            account=account,
            decision="approved",
            rationale="Ledger evidence reviewed.",
        )
        first = await execute_approved_action(session, action_reference=intent.public_reference)
    async with database.transaction() as session:
        second = await execute_approved_action(session, action_reference=intent.public_reference)
    async with database.session() as session:
        entries = (
            (
                await session.execute(
                    select(MembershipLedgerEntry).where(
                        MembershipLedgerEntry.idempotency_key == intent.idempotency_key
                    )
                )
            )
            .scalars()
            .all()
        )
    assert first.receipt == second.receipt
    assert len(entries) == 1 and entries[0].credit_delta == 1


async def test_state_change_after_approval_fails_closed(database) -> None:
    case = await _new_case(database, "m7-stale-action")
    saver = InMemorySaver()
    workflow = _workflow(database, _model())
    interrupted = await run_case(database, workflow, case_id=case.id, checkpointer=saver)
    action_reference = interrupted["action_intent_reference"]
    async with database.transaction() as session:
        account = (
            await session.execute(
                select(OperationsAccount).where(OperationsAccount.username == ACCOUNT_USERNAME)
            )
        ).scalar_one()
        await decide_action(
            session,
            action_reference=action_reference,
            account=account,
            decision="approved",
            rationale="Evidence reviewed before the concurrent state change.",
        )
        await session.execute(
            update(Payment)
            .where(Payment.public_reference == PAYMENT_REFERENCE)
            .values(refunded_amount_cents=1, status="partially_refunded")
        )
    result = await resume_after_approval(
        workflow, case_run_id=UUID(interrupted["case_run_id"]), checkpointer=saver
    )
    async with database.session() as session:
        intent = await session.scalar(
            select(ActionIntent).where(ActionIntent.public_reference == action_reference)
        )
        refund = await session.scalar(
            select(Refund).where(Refund.idempotency_key == intent.idempotency_key)
        )
        escalated_case = await session.get(SupportCase, case.id)
    assert result["escalation_reason"] == "stale_or_invalid_action"
    assert intent is not None and intent.status == "failed"
    assert refund is None
    assert escalated_case is not None and escalated_case.status == "human_investigation"


async def test_worker_runs_intake_then_durable_approval_continuation(database) -> None:
    case = await _new_case(database, "m9-worker-resume")
    saver = InMemorySaver()
    settings = Settings(_env_file=None)
    workflow = _workflow(database, _model())

    assert await process_next_job(
        database,
        workflow,
        saver,
        worker_id="m9-worker-test",
        settings=settings,
    )
    async with database.session() as session:
        waiting_case = await session.get(SupportCase, case.id)
        intent = await session.scalar(select(ActionIntent).where(ActionIntent.case_id == case.id))
    assert waiting_case is not None and waiting_case.status == "pending_approval"
    assert intent is not None and intent.status == "pending_approval"

    async with database.transaction() as session:
        account = await session.scalar(
            select(OperationsAccount).where(OperationsAccount.username == ACCOUNT_USERNAME)
        )
        assert account is not None
        await decide_action(
            session,
            action_reference=intent.public_reference,
            account=account,
            decision="approved",
            rationale="Worker continuation test reviewed the persisted evidence.",
        )

    assert await process_next_job(
        database,
        workflow,
        saver,
        worker_id="m9-worker-test",
        settings=settings,
    )
    async with database.session() as session:
        completed_case = await session.get(SupportCase, case.id)
        completed_intent = await session.get(ActionIntent, intent.id)
    assert completed_case is not None and completed_case.status == "resolved"
    assert completed_intent is not None and completed_intent.status == "succeeded"
