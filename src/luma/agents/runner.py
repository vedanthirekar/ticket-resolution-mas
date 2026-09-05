from __future__ import annotations

import logging
from time import perf_counter
from typing import Any, cast
from uuid import UUID

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.types import Command
from sqlalchemy import exists, select

from luma.agents.artifacts import ARCHITECTURE_VERSION, get_or_create_case_run
from luma.agents.contracts import CaseResolutionState
from luma.agents.graph import CaseResolutionWorkflow
from luma.db.models.case_management import ActionIntent, Approval, SupportCase
from luma.db.session import Database
from luma.domain.cases import CaseStatus
from luma.observability.logging import log_event
from luma.services.cases import transition_case


async def prepare_run_state(
    database: Database,
    workflow: CaseResolutionWorkflow,
    *,
    case_id: UUID,
) -> CaseResolutionState:
    async with database.transaction() as session:
        support_case = (
            await session.execute(select(SupportCase).where(SupportCase.id == case_id))
        ).scalar_one()
        run = await get_or_create_case_run(
            session,
            case_id=case_id,
            model_provider=workflow.model.provider,
            model_name=workflow.model.model_name,
        )
        if support_case.status == CaseStatus.QUEUED.value:
            support_case = await transition_case(
                session,
                case_id=support_case.id,
                to_status=CaseStatus.PROCESSING,
                event_type="case_processing_started",
                actor_type="system",
                actor_reference="case_resolution_worker",
                payload={"case_run_id": str(run.id)},
            )
        return CaseResolutionState(
            case_id=str(support_case.id),
            case_reference=support_case.public_reference,
            case_run_id=str(run.id),
            case_received_at=support_case.received_at.isoformat(),
            complaint_text=support_case.complaint_text,
            customer_reference=support_case.claimed_customer_reference,
            claimed_category=support_case.claimed_category,
            evidence=[],
            supplemental_count=0,
            escalation_reason=None,
            input_tokens=0,
            output_tokens=0,
        )


async def run_case(
    database: Database,
    workflow: CaseResolutionWorkflow,
    *,
    case_id: UUID,
    checkpointer: BaseCheckpointSaver[Any],
) -> CaseResolutionState:
    state = await prepare_run_state(database, workflow, case_id=case_id)
    config: RunnableConfig = {
        "configurable": {"thread_id": state["case_run_id"]},
        "run_name": "luma_case_resolution",
        "tags": ["luma", ARCHITECTURE_VERSION],
        "metadata": {
            "case_reference": state["case_reference"],
            "case_run_id": state["case_run_id"],
            "architecture_version": ARCHITECTURE_VERSION,
        },
    }
    checkpoint = await checkpointer.aget(config)
    graph = workflow.compile(checkpointer=checkpointer)
    logger = logging.getLogger("luma.agent")
    started = perf_counter()
    log_event(
        logger,
        "case_run_started",
        case_reference=state["case_reference"],
        case_run_id=state["case_run_id"],
        resumed=checkpoint is not None,
    )
    graph_input: CaseResolutionState | Command[Any] | None
    if checkpoint is None:
        graph_input = state
    else:
        async with database.session() as session:
            has_decision = bool(
                await session.scalar(
                    select(
                        exists().where(
                            ActionIntent.case_run_id == UUID(state["case_run_id"]),
                            Approval.action_intent_id == ActionIntent.id,
                        )
                    )
                )
            )
        graph_input = (
            Command(resume={"durable_approval_decision_recorded": True}) if has_decision else None
        )
    try:
        result = await graph.ainvoke(graph_input, config=config, durability="sync")
    except Exception as exc:
        log_event(
            logger,
            "case_run_failed",
            case_reference=state["case_reference"],
            case_run_id=state["case_run_id"],
            latency_ms=(perf_counter() - started) * 1000,
            error_type=type(exc).__name__,
        )
        raise
    log_event(
        logger,
        "case_run_yielded",
        case_reference=state["case_reference"],
        case_run_id=state["case_run_id"],
        latency_ms=(perf_counter() - started) * 1000,
        disposition=result.get("final_disposition"),
        interrupted="action_intent_reference" in result and "approval_decision" not in result,
    )
    return cast(CaseResolutionState, result)


async def resume_after_approval(
    workflow: CaseResolutionWorkflow,
    *,
    case_run_id: UUID,
    checkpointer: BaseCheckpointSaver[Any],
) -> CaseResolutionState:
    """Resume an interrupted graph only after the approval service persisted a decision."""
    config: RunnableConfig = {
        "configurable": {"thread_id": str(case_run_id)},
        "run_name": "luma_case_resolution_resume",
        "tags": ["luma", ARCHITECTURE_VERSION, "approval-resume"],
        "metadata": {
            "case_run_id": str(case_run_id),
            "architecture_version": ARCHITECTURE_VERSION,
        },
    }
    graph = workflow.compile(checkpointer=checkpointer)
    result = await graph.ainvoke(
        Command(resume={"durable_approval_decision_recorded": True}),
        config=config,
        durability="sync",
    )
    return cast(CaseResolutionState, result)
