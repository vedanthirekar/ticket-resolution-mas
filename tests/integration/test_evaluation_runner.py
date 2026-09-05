from __future__ import annotations

import pytest
from sqlalchemy import delete, select

from luma.agents.artifacts import get_or_create_case_run
from luma.agents.models import ScriptedStructuredModel
from luma.config import Settings
from luma.db.models.ai_runtime import CaseRun
from luma.db.models.case_management import ProcessingJob, SupportCase
from luma.domain.cases import CaseSource
from luma.evaluation.dataset import load_dataset
from luma.evaluation.runner import run_live_evaluation
from luma.retrieval.embeddings import HashingEmbeddingProvider
from luma.services.cases import CreateCaseCommand, create_case

pytestmark = pytest.mark.integration

TEST_EXPERIMENT_ID = "EXP-INTEGRATION-FAULT"


async def _delete_test_experiment_cases(database) -> None:
    """Remove only records owned by this test module's fixed experiment."""
    async with database.transaction() as session:
        await session.execute(
            delete(SupportCase).where(
                SupportCase.external_request_key.startswith(f"eval:{TEST_EXPERIMENT_ID}:")
            )
        )


@pytest.fixture(autouse=True)
async def clean_eval_cases(database):
    await _delete_test_experiment_cases(database)
    yield
    await _delete_test_experiment_cases(database)


async def test_cleanup_does_not_delete_another_active_evaluation(database) -> None:
    other_request_key = "eval:EXP-ACTIVE-OTHER:cleanup-isolation"
    async with database.transaction() as session:
        await session.execute(
            delete(SupportCase).where(SupportCase.external_request_key == other_request_key)
        )
        created = await create_case(
            session,
            CreateCaseCommand(
                complaint_text="An unrelated evaluation is still running.",
                source=CaseSource.API,
                external_request_key=other_request_key,
                claimed_customer_reference="CUS-0001",
            ),
        )
        run = await get_or_create_case_run(
            session,
            case_id=created.case.id,
            model_provider="scripted",
            model_name="scripted-v1",
        )
        other_case_id = created.case.id
        other_run_id = run.id

    try:
        await _delete_test_experiment_cases(database)

        async with database.session() as session:
            assert await session.get(SupportCase, other_case_id) is not None
            assert await session.get(CaseRun, other_run_id) is not None
    finally:
        async with database.transaction() as session:
            await session.execute(
                delete(SupportCase).where(SupportCase.external_request_key == other_request_key)
            )


async def test_fault_injected_tool_outage_fails_closed_and_is_reported(database) -> None:
    dataset = load_dataset()
    eval_case = next(case for case in dataset.cases if case.test_type == "tool_failure")
    model = ScriptedStructuredModel(
        {
            "case_manager_plan": [
                {
                    "category": "duplicate_payment",
                    "material_event_date": "2026-07-14",
                    "required_evidence_types": [],
                    "investigation_objectives": [
                        "Establish identity, appointment history, and payment captures."
                    ],
                    "policy_query": "duplicate capture",
                    "policy_area": "payments",
                    "rationale": "Reconcile both captures against one obligation.",
                }
            ],
            "investigation_decision": [
                {
                    "complete": False,
                    "next_call": {
                        "tool_name": "get_customer",
                        "arguments": {"customer_reference": "CUS-0007"},
                        "purpose": "Establish customer identity.",
                    },
                    "rationale": "Identity is required first.",
                },
                {
                    "complete": False,
                    "next_call": {
                        "tool_name": "get_appointment_timeline",
                        "arguments": {
                            "customer_reference": "CUS-0007",
                            "appointment_reference": "APPT-DUP-PAY",
                        },
                        "purpose": "Establish the fulfilled appointment.",
                    },
                    "rationale": "The complaint supplies the appointment reference.",
                },
                {
                    "complete": False,
                    "next_call": {
                        "tool_name": "get_appointment_payments",
                        "arguments": {
                            "customer_reference": "CUS-0007",
                            "appointment_reference": "APPT-DUP-PAY",
                        },
                        "purpose": "Establish payment captures.",
                    },
                    "rationale": "Payment evidence remains required.",
                },
                {
                    "complete": True,
                    "next_call": None,
                    "rationale": "All obtainable evidence has been collected.",
                },
            ],
        }
    )
    report = await run_live_evaluation(
        dataset=dataset,
        selected_cases=[eval_case],
        database=database,
        model=model,
        embedding_provider=HashingEmbeddingProvider(),
        settings=Settings(_env_file=None),
        experiment_id=TEST_EXPERIMENT_ID,
    )

    observation = report.observations[0]
    assert observation.disposition == "human_investigation"
    assert observation.escalation_reason == "required_operational_evidence_missing"
    assert observation.action is None
    assert observation.unauthorized_mutation_count == 0
    assert report.summary["escalation_recall"] == 1
    async with database.session() as session:
        job_status = await session.scalar(
            select(ProcessingJob.status)
            .join(SupportCase, SupportCase.id == ProcessingJob.case_id)
            .where(SupportCase.public_reference == observation.case_reference)
        )
    assert job_status == "cancelled"
    assert model.calls == [
        "case_manager_plan",
        "investigation_decision",
        "investigation_decision",
        "investigation_decision",
        "investigation_decision",
    ]
