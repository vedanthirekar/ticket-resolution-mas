from __future__ import annotations

from uuid import uuid4

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from sqlalchemy import delete, select

from luma.agents.artifacts import complete_stage
from luma.agents.checkpoints import postgres_checkpointer
from luma.agents.graph import CaseResolutionWorkflow
from luma.agents.models import ScriptedStructuredModel
from luma.agents.runner import prepare_run_state, run_case
from luma.config import Settings
from luma.db.models.ai_runtime import (
    EvidenceItem,
    InvestigationPlan,
    ResolutionProposal,
    WorkflowStage,
)
from luma.db.models.case_management import ActionIntent, Escalation, SupportCase
from luma.domain.cases import CaseSource
from luma.retrieval.embeddings import HashingEmbeddingProvider
from luma.services.cases import CreateCaseCommand, create_case

pytestmark = pytest.mark.integration

TEST_REQUEST_KEYS = (
    "agent-happy-path",
    "agent-missing-identity",
    "agent-idempotent-plan",
    "agent-postgres-resume",
    "agent-discovery-without-reference",
    "agent-regression-auth-hold",
    "agent-regression-no-show",
    "agent-regression-booking-failure",
)


async def test_stage_commit_reports_a_deleted_parent_run_clearly(database) -> None:
    missing_run_id = uuid4()

    with pytest.raises(RuntimeError, match="was deleted while the workflow was active"):
        async with database.transaction() as session:
            await complete_stage(
                session,
                case_run_id=missing_run_id,
                stage_name="policy",
                output={},
            )


def _verification_response() -> dict[str, object]:
    return {
        "supported": True,
        "missing_evidence": [],
        "contradictions": [],
        "unsupported_claims": [],
        "recommended_outcome": "refund_cancellation_fee",
        "recommended_disposition": "human_approval",
        "requires_human": True,
        "rationale": "The source records and effective policy support the exact refund.",
    }


@pytest.fixture(autouse=True)
async def clean_agent_cases(database):
    async with database.transaction() as session:
        await session.execute(
            delete(SupportCase).where(SupportCase.external_request_key.in_(TEST_REQUEST_KEYS))
        )
    yield
    async with database.transaction() as session:
        await session.execute(
            delete(SupportCase).where(SupportCase.external_request_key.in_(TEST_REQUEST_KEYS))
        )


def _proposal_response() -> dict[str, object]:
    return {
        "outcome": "refund_cancellation_fee",
        "disposition": "human_approval",
        "rationale": "The provider initiated cancellation and the fee was captured.",
        "action_payload": {
            "action_type": "refund_payment",
            "payment_reference": "PAY-001491-provider-fee",
            "amount_cents": 8000,
            "reason_code": "provider_cancelled_fee",
        },
        "evidence_references": ["APPT-CAN-PROVIDER"],
        "policy_references": ["POL-CAN-v2#4.1"],
    }


def _happy_model() -> ScriptedStructuredModel:
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
                    "policy_query": "provider cancelled and customer was charged a fee refund",
                    "policy_area": None,
                    "rationale": "Check authoritative cancellation and payment records.",
                }
            ],
            "investigation_decision": [
                {
                    "complete": False,
                    "next_call": {
                        "tool_name": "get_customer",
                        "arguments": {"customer_reference": "CUS-0001"},
                        "purpose": "Establish customer identity.",
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
                    "rationale": "The complaint supplies a grounded appointment reference.",
                },
                {
                    "complete": False,
                    "next_call": {
                        "tool_name": "get_appointment_payments",
                        "arguments": {
                            "customer_reference": "CUS-0001",
                            "appointment_reference": "APPT-CAN-PROVIDER",
                        },
                        "purpose": "Establish captured cancellation fee.",
                    },
                    "rationale": "Payment evidence remains required.",
                },
                {
                    "complete": True,
                    "next_call": None,
                    "rationale": "All required operational evidence is present.",
                },
            ],
            "policy_assessment": [
                {
                    "applicable": True,
                    "selected_section_ids": ["POL-CAN-v2#4.1"],
                    "rule_summary": "A provider cancellation must not produce a customer fee.",
                    "missing_evidence_types": [],
                    "supplemental_call": None,
                }
            ],
            "resolution_proposal": [_proposal_response()],
            "verification": [_verification_response()],
        }
    )


async def test_happy_path_persists_provenance_and_proposal(database) -> None:
    async with database.transaction() as session:
        created = await create_case(
            session,
            CreateCaseCommand(
                complaint_text=(
                    "I was charged $80 even though the provider cancelled APPT-CAN-PROVIDER."
                ),
                source=CaseSource.API,
                external_request_key="agent-happy-path",
                claimed_customer_reference="CUS-0001",
            ),
        )

    model = _happy_model()
    workflow = CaseResolutionWorkflow(
        database=database,
        model=model,
        embedding_provider=HashingEmbeddingProvider(),
        settings=Settings(_env_file=None),
    )
    result = await run_case(
        database,
        workflow,
        case_id=created.case.id,
        checkpointer=InMemorySaver(),
    )

    assert result["proposal"]["disposition"] == "human_approval"
    assert model.calls == [
        "case_manager_plan",
        "investigation_decision",
        "investigation_decision",
        "investigation_decision",
        "investigation_decision",
        "policy_assessment",
        "resolution_proposal",
        "verification",
    ]
    async with database.session() as session:
        assert await session.scalar(
            select(InvestigationPlan).where(InvestigationPlan.case_run_id == result["case_run_id"])
        )
        evidence = (
            (
                await session.execute(
                    select(EvidenceItem).where(EvidenceItem.case_run_id == result["case_run_id"])
                )
            )
            .scalars()
            .all()
        )
        proposal = await session.scalar(
            select(ResolutionProposal).where(
                ResolutionProposal.case_run_id == result["case_run_id"]
            )
        )
        action = await session.scalar(
            select(ActionIntent).where(ActionIntent.case_run_id == result["case_run_id"])
        )
    assert len(evidence) == 3
    assert any(
        item.source_reference and "APPT-CAN-PROVIDER" in item.source_reference for item in evidence
    )
    assert proposal is not None
    assert action is not None and action.status == "pending_approval"


async def test_missing_identity_escalates_without_model_call(database) -> None:
    async with database.transaction() as session:
        created = await create_case(
            session,
            CreateCaseCommand(
                complaint_text="Something is wrong with my appointment.",
                source=CaseSource.API,
                external_request_key="agent-missing-identity",
            ),
        )
    model = ScriptedStructuredModel({})
    workflow = CaseResolutionWorkflow(
        database=database,
        model=model,
        embedding_provider=HashingEmbeddingProvider(),
        settings=Settings(_env_file=None),
    )
    result = await run_case(
        database,
        workflow,
        case_id=created.case.id,
        checkpointer=InMemorySaver(),
    )

    assert result["escalation_reason"] == "customer_identity_not_established"
    assert model.calls == []
    async with database.session() as session:
        support_case = await session.get(SupportCase, created.case.id)
        escalation = await session.scalar(
            select(Escalation).where(Escalation.case_id == created.case.id)
        )
    assert support_case is not None and support_case.status == "human_investigation"
    assert escalation is not None


async def test_investigator_discovers_appointment_before_exact_detail_calls(database) -> None:
    async with database.transaction() as session:
        created = await create_case(
            session,
            CreateCaseCommand(
                complaint_text=(
                    "My provider cancelled my August 20 appointment, but I still see an $80 fee."
                ),
                source=CaseSource.API,
                external_request_key="agent-discovery-without-reference",
                claimed_customer_reference="CUS-0001",
            ),
        )
    model = ScriptedStructuredModel(
        {
            "case_manager_plan": [
                {
                    "category": "cancellation_fee_dispute",
                    "material_event_date": "2026-08-20",
                    "required_evidence_types": [],
                    "investigation_objectives": [
                        "Find the appointment, cancellation initiator, and related payment."
                    ],
                    "policy_query": "provider cancellation fee",
                    "policy_area": "cancellation",
                    "rationale": "Discover the record before requesting exact details.",
                }
            ],
            "investigation_decision": [
                {
                    "complete": False,
                    "next_call": {
                        "tool_name": "get_customer",
                        "arguments": {},
                        "purpose": "Establish identity.",
                    },
                    "rationale": "Identity comes first.",
                },
                {
                    "complete": False,
                    "next_call": {
                        "tool_name": "get_customer_appointments",
                        "arguments": {
                            "starts_on_or_after": "2026-08-20T00:00:00Z",
                            "starts_before": "2026-08-21T00:00:00Z",
                            "limit": 20,
                        },
                        "purpose": "Find the appointment described by date.",
                    },
                    "rationale": "No appointment reference was supplied.",
                },
                {
                    "complete": False,
                    "next_call": {
                        "tool_name": "get_appointment_timeline",
                        "arguments": {"appointment_reference": "APPT-CAN-PROVIDER"},
                        "purpose": "Establish cancellation initiator.",
                    },
                    "rationale": "The discovery result supplied the appointment reference.",
                },
                {
                    "complete": False,
                    "next_call": {
                        "tool_name": "get_appointment_payments",
                        "arguments": {"appointment_reference": "APPT-CAN-PROVIDER"},
                        "purpose": "Establish the charge.",
                    },
                    "rationale": "The same discovered appointment scopes payment evidence.",
                },
                {
                    "complete": True,
                    "next_call": None,
                    "rationale": "Required evidence is now present.",
                },
            ],
        }
    )
    workflow = CaseResolutionWorkflow(
        database=database,
        model=model,
        embedding_provider=HashingEmbeddingProvider(),
        settings=Settings(_env_file=None),
    )
    state = await prepare_run_state(database, workflow, case_id=created.case.id)
    planned = await workflow.plan_node(state)
    investigated = await workflow.investigation_node({**state, **planned})

    assert investigated.get("escalation_reason") is None
    references = {
        reference for item in investigated["evidence"] for reference in item["source_references"]
    }
    assert "APPT-CAN-PROVIDER" in references
    assert "PAY-001491-provider-fee" in references
    assert model.calls == ["case_manager_plan", *("investigation_decision" for _ in range(5))]


@pytest.mark.parametrize(
    (
        "request_key",
        "complaint",
        "customer_reference",
        "category",
        "material_event_date",
        "decision_calls",
        "expected_references",
    ),
    [
        pytest.param(
            "agent-regression-auth-hold",
            "My bank shows a pending $60 Luma charge. Was it collected or only a hold?",
            "CUS-0006",
            "duplicate_payment",
            "2026-07-13",
            [
                ("get_customer", {}),
                ("get_customer_appointments", {}),
                (
                    "get_appointment_timeline",
                    {"appointment_reference": "APPT-AUTH-HOLD"},
                ),
                (
                    "get_appointment_payments",
                    {"appointment_reference": "APPT-AUTH-HOLD"},
                ),
            ],
            {"APPT-AUTH-HOLD", "PAY-001494-auth-hold"},
            id="authorization-hold",
        ),
        pytest.param(
            "agent-regression-no-show",
            "I was charged after missing my July 12, 2026 appointment. Is the fee valid?",
            "CUS-0005",
            "cancellation_fee_dispute",
            "2026-07-12",
            [
                ("get_customer", {}),
                ("get_customer_appointments", {}),
                (
                    "get_appointment_timeline",
                    {"appointment_reference": "APPT-NO-SHOW"},
                ),
                (
                    "get_appointment_payments",
                    {"appointment_reference": "APPT-NO-SHOW"},
                ),
            ],
            {"APPT-NO-SHOW", "PAY-001493-no-show"},
            id="valid-no-show",
        ),
        pytest.param(
            "agent-regression-booking-failure",
            "The booking site showed a technical error for September 15, 2026.",
            "CUS-0024",
            "online_booking_unavailable",
            "2026-09-15",
            [
                ("get_customer", {}),
                ("get_customer_booking_attempts", {}),
                (
                    "get_booking_attempt_evidence",
                    {"booking_attempt_reference": "BATT-TECHNICAL-FAILURE"},
                ),
            ],
            {"BATT-TECHNICAL-FAILURE"},
            id="booking-technical-failure",
        ),
    ],
)
async def test_natural_language_cases_reach_exact_detail_tools(
    database,
    request_key: str,
    complaint: str,
    customer_reference: str,
    category: str,
    material_event_date: str,
    decision_calls: list[tuple[str, dict[str, object]]],
    expected_references: set[str],
) -> None:
    async with database.transaction() as session:
        created = await create_case(
            session,
            CreateCaseCommand(
                complaint_text=complaint,
                source=CaseSource.API,
                external_request_key=request_key,
                claimed_customer_reference=customer_reference,
            ),
        )

    decisions = [
        {
            "complete": False,
            "next_call": {
                "tool_name": tool_name,
                "arguments": arguments,
                "purpose": f"Collect authoritative evidence with {tool_name}.",
            },
            "rationale": "This is the next required evidence lookup.",
        }
        for tool_name, arguments in decision_calls
    ]
    decisions.append(
        {
            "complete": True,
            "next_call": None,
            "rationale": "All required operational evidence is present.",
        }
    )
    model = ScriptedStructuredModel(
        {
            "case_manager_plan": [
                {
                    "category": category,
                    "material_event_date": material_event_date,
                    "required_evidence_types": [],
                    "investigation_objectives": ["Collect the exact authoritative records."],
                    "policy_query": "Find the policy governing the established facts.",
                    "policy_area": None,
                    "rationale": "The complaint maps to a supported case category.",
                }
            ],
            "investigation_decision": decisions,
        }
    )
    workflow = CaseResolutionWorkflow(
        database=database,
        model=model,
        embedding_provider=HashingEmbeddingProvider(),
        settings=Settings(_env_file=None),
    )
    state = await prepare_run_state(database, workflow, case_id=created.case.id)
    planned = await workflow.plan_node(state)
    investigated = await workflow.investigation_node({**state, **planned})

    assert investigated.get("escalation_reason") is None
    references = {
        reference for item in investigated["evidence"] for reference in item["source_references"]
    }
    assert expected_references <= references
    assert investigated["evidence_coverage"]["complete"] is True


async def test_completed_plan_stage_is_not_repeated(database) -> None:
    async with database.transaction() as session:
        created = await create_case(
            session,
            CreateCaseCommand(
                complaint_text="I was charged for APPT-CAN-PROVIDER.",
                source=CaseSource.API,
                external_request_key="agent-idempotent-plan",
                claimed_customer_reference="CUS-0001",
            ),
        )
    model = _happy_model()
    workflow = CaseResolutionWorkflow(
        database=database,
        model=model,
        embedding_provider=HashingEmbeddingProvider(),
        settings=Settings(_env_file=None),
    )
    from luma.agents.runner import prepare_run_state

    state = await prepare_run_state(database, workflow, case_id=created.case.id)
    first = await workflow.plan_node(state)
    second = await workflow.plan_node(state)

    assert first == second
    assert model.calls == ["case_manager_plan"]
    async with database.session() as session:
        stages = (
            (
                await session.execute(
                    select(WorkflowStage).where(WorkflowStage.case_run_id == state["case_run_id"])
                )
            )
            .scalars()
            .all()
        )
    assert len(stages) == 1


async def test_postgres_checkpoint_resumes_after_process_boundary(database) -> None:
    async with database.transaction() as session:
        created = await create_case(
            session,
            CreateCaseCommand(
                complaint_text=(
                    "I was charged $80 even though the provider cancelled APPT-CAN-PROVIDER."
                ),
                source=CaseSource.API,
                external_request_key="agent-postgres-resume",
                claimed_customer_reference="CUS-0001",
            ),
        )
    settings = Settings(_env_file=".env")
    first_model = _happy_model()
    first_model._responses["resolution_proposal"].clear()
    first_workflow = CaseResolutionWorkflow(
        database=database,
        model=first_model,
        embedding_provider=HashingEmbeddingProvider(),
        settings=settings,
    )
    prepared = await prepare_run_state(database, first_workflow, case_id=created.case.id)
    run_id = prepared["case_run_id"]
    async with postgres_checkpointer(settings.database_url, setup=True) as checkpointer:
        with pytest.raises(RuntimeError, match="no scripted response"):
            await run_case(
                database,
                first_workflow,
                case_id=created.case.id,
                checkpointer=checkpointer,
            )
        async with database.session() as session:
            stage = await session.scalar(
                select(WorkflowStage).where(
                    WorkflowStage.stage_name == "policy",
                    WorkflowStage.case_run_id == run_id,
                )
            )
        assert stage is not None

    second_model = ScriptedStructuredModel(
        {
            "resolution_proposal": [_proposal_response()],
            "verification": [_verification_response()],
        }
    )
    second_workflow = CaseResolutionWorkflow(
        database=database,
        model=second_model,
        embedding_provider=HashingEmbeddingProvider(),
        settings=settings,
    )
    async with postgres_checkpointer(settings.database_url) as checkpointer:
        result = await run_case(
            database,
            second_workflow,
            case_id=created.case.id,
            checkpointer=checkpointer,
        )
        await checkpointer.adelete_thread(run_id)

    assert result["proposal"]["outcome"] == "refund_cancellation_fee"
    assert second_model.calls == ["resolution_proposal", "verification"]
