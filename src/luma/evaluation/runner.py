from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from langgraph.checkpoint.memory import InMemorySaver
from sqlalchemy import select

from luma.agents.artifacts import ARCHITECTURE_VERSION
from luma.agents.graph import CaseResolutionWorkflow
from luma.agents.models import StructuredModel
from luma.agents.runner import run_case
from luma.config import Settings
from luma.db.models.case_management import ProcessingJob
from luma.db.session import Database
from luma.domain.cases import CaseSource
from luma.evaluation.contracts import EvalCase, EvalDataset, EvalObservation, EvalReport
from luma.evaluation.graders import grade_case, summarize_results
from luma.evaluation.observations import observe_case_run
from luma.observability.logging import log_event
from luma.retrieval.embeddings import EmbeddingProvider
from luma.services.cases import CreateCaseCommand, create_case

PROMPT_VERSION = "prompts-v2"
TOOL_VERSION = "operational-tools-v1"
GRAPH_VERSION = "langgraph-v2"
EVAL_CASE_MAX_ATTEMPTS = 3


def _retry_delay_seconds(exc: Exception, attempt: int) -> int:
    message = str(exc)
    if "429" in message or "RESOURCE_EXHAUSTED" in message:
        return 60
    return int(2**attempt)


def _is_daily_quota_exhaustion(exc: Exception) -> bool:
    message = str(exc)
    return "PerDay" in message or "requests per day" in message.lower()


def _estimated_cost(settings: Settings, observation: EvalObservation) -> float | None:
    if (
        settings.model_input_cost_per_million_usd is None
        or settings.model_output_cost_per_million_usd is None
    ):
        return None
    return (
        (observation.input_tokens or 0) * settings.model_input_cost_per_million_usd
        + (observation.output_tokens or 0) * settings.model_output_cost_per_million_usd
    ) / 1_000_000


async def run_live_evaluation(
    *,
    dataset: EvalDataset,
    selected_cases: list[EvalCase],
    database: Database,
    model: StructuredModel,
    embedding_provider: EmbeddingProvider,
    settings: Settings,
    experiment_id: str | None = None,
) -> EvalReport:
    experiment_id = experiment_id or f"EXP-{datetime.now(UTC):%Y%m%dT%H%M%S}-{uuid4().hex[:8]}"
    logger = logging.getLogger("luma.evaluation")
    observations: list[EvalObservation] = []
    attempted_cases: list[EvalCase] = []
    incomplete_reason: str | None = None

    for eval_case in selected_cases:
        attempted_cases.append(eval_case)
        started = perf_counter()
        case_id = None
        error: str | None = None
        daily_quota_exhausted = False
        log_event(
            logger,
            "eval_case_started",
            experiment_id=experiment_id,
            eval_case_id=eval_case.case_id,
            split=eval_case.split,
            test_type=eval_case.test_type,
        )
        try:
            async with database.transaction() as session:
                created = await create_case(
                    session,
                    CreateCaseCommand(
                        complaint_text=eval_case.complaint,
                        source=CaseSource.API,
                        external_request_key=f"eval:{experiment_id}:{eval_case.case_id}",
                        claimed_customer_reference=eval_case.customer_reference,
                    ),
                )
                case_id = created.case.id
                # Eval execution is synchronous and isolated; its intake-created job
                # must never be visible to the production worker queue.
                job = await session.scalar(
                    select(ProcessingJob).where(ProcessingJob.case_id == case_id)
                )
                if job is not None:
                    job.status = "cancelled"
            unavailable = frozenset(
                [eval_case.fault_injection["tool_name"]]
                if eval_case.fault_injection is not None
                else []
            )
            workflow = CaseResolutionWorkflow(
                database=database,
                model=model,
                embedding_provider=embedding_provider,
                settings=settings,
                unavailable_tools=unavailable,
            )
            checkpointer = InMemorySaver()
            for attempt in range(1, EVAL_CASE_MAX_ATTEMPTS + 1):
                try:
                    await run_case(
                        database,
                        workflow,
                        case_id=case_id,
                        checkpointer=checkpointer,
                    )
                    error = None
                    break
                except Exception as exc:
                    error = f"{type(exc).__name__}: {exc}"
                    if _is_daily_quota_exhaustion(exc):
                        daily_quota_exhausted = True
                        raise
                    if attempt == EVAL_CASE_MAX_ATTEMPTS:
                        raise
                    log_event(
                        logger,
                        "eval_case_retrying",
                        experiment_id=experiment_id,
                        eval_case_id=eval_case.case_id,
                        attempt=attempt,
                        max_attempts=EVAL_CASE_MAX_ATTEMPTS,
                        error_type=type(exc).__name__,
                    )
                    await asyncio.sleep(_retry_delay_seconds(exc, attempt))
        except Exception as exc:  # an eval records per-case failures and continues
            error = f"{type(exc).__name__}: {exc}"

        if case_id is None:
            observation = EvalObservation(case_id=eval_case.case_id, error=error)
        else:
            async with database.session() as session:
                observation = await observe_case_run(
                    session, eval_case_id=eval_case.case_id, case_id=case_id
                )
            observation.latency_ms = (perf_counter() - started) * 1000
            observation.estimated_cost_usd = _estimated_cost(settings, observation)
            if error is not None:
                observation.error = error
                # Preserve intermediate artifacts for debugging, but never grade an
                # unverified proposal as the system's final decision.
                observation.outcome = None
                observation.disposition = None
                observation.action = None
        observations.append(observation)
        log_event(
            logger,
            "eval_case_completed",
            experiment_id=experiment_id,
            eval_case_id=eval_case.case_id,
            case_reference=observation.case_reference,
            case_run_id=observation.case_run_id,
            disposition=observation.disposition,
            latency_ms=observation.latency_ms,
            error=observation.error,
        )
        if daily_quota_exhausted:
            incomplete_reason = "provider_daily_quota_exhausted"
            log_event(
                logger,
                "eval_run_stopped",
                experiment_id=experiment_id,
                reason=incomplete_reason,
                attempted_case_count=len(attempted_cases),
                requested_case_count=len(selected_cases),
            )
            break

    grades = [
        grade_case(eval_case, observation)
        for eval_case, observation in zip(attempted_cases, observations, strict=True)
    ]
    return EvalReport(
        experiment_id=experiment_id,
        created_at=datetime.now(UTC),
        dataset_name=dataset.dataset_name,
        dataset_version=dataset.dataset_version,
        business_dataset_version=dataset.business_dataset_version,
        architecture_version=ARCHITECTURE_VERSION,
        prompt_version=PROMPT_VERSION,
        tool_version=TOOL_VERSION,
        graph_version=GRAPH_VERSION,
        model_provider=model.provider,
        model_name=model.model_name,
        configuration={
            "temperature": 0,
            "fault_injection_enabled": any(case.fault_injection for case in selected_cases),
            "mutations_executed": False,
            "case_max_attempts": EVAL_CASE_MAX_ATTEMPTS,
            "requested_case_count": len(selected_cases),
            "completed_case_count": len(observations),
            "incomplete_reason": incomplete_reason,
            "langsmith_tracing": "controlled by LANGSMITH_TRACING environment setting",
        },
        summary=summarize_results(attempted_cases, observations, grades),
        observations=observations,
        cases=grades,
    )


def write_report(report: EvalReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
