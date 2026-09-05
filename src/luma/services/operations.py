from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from luma.db.models.ai_runtime import (
    CaseRun,
    EvidenceItem,
    InvestigationPlan,
    PolicyRetrieval,
    ResolutionProposal,
    VerificationResult,
    WorkflowStage,
)
from luma.db.models.case_management import (
    ActionIntent,
    Approval,
    CaseEvent,
    Escalation,
    ExecutionAttempt,
    OperationsAccount,
    SupportCase,
)


def _product_cases() -> Any:
    """Builder eval traffic must never appear in the employee product surface."""
    return ~SupportCase.external_request_key.startswith("eval:")


@dataclass(frozen=True, slots=True)
class OperationsCaseRow:
    case: SupportCase
    category: str | None
    outcome: str | None
    disposition: str | None
    escalation_reason: str | None


@dataclass(frozen=True, slots=True)
class OperationsCaseWorkspace:
    """Auditable product read model; deliberately excludes model chain-of-thought."""

    case: SupportCase
    run: CaseRun | None
    plan: InvestigationPlan | None
    stages: list[WorkflowStage]
    evidence: list[EvidenceItem]
    policy_retrievals: list[PolicyRetrieval]
    proposal: ResolutionProposal | None
    verification: VerificationResult | None
    actions: list[tuple[ActionIntent, Approval | None, str | None]]
    execution_attempts: list[ExecutionAttempt]
    escalations: list[Escalation]
    events: list[CaseEvent]


async def operations_overview(session: AsyncSession) -> dict[str, Any]:
    status_rows = await session.execute(
        select(SupportCase.status, func.count(SupportCase.id))
        .where(_product_cases())
        .group_by(SupportCase.status)
    )
    counts = {status: int(count) for status, count in status_rows}
    total = sum(counts.values())
    terminal = counts.get("resolved", 0) + counts.get("human_investigation", 0)
    average_resolution_seconds = await session.scalar(
        select(
            func.avg(func.extract("epoch", SupportCase.resolved_at - SupportCase.received_at))
        ).where(_product_cases(), SupportCase.resolved_at.is_not(None))
    )
    return {
        "total_cases": total,
        "status_counts": counts,
        "active_cases": sum(
            counts.get(status, 0)
            for status in ("received", "queued", "processing", "pending_approval")
        ),
        "resolved_cases": counts.get("resolved", 0),
        "pending_approval_cases": counts.get("pending_approval", 0),
        "human_investigation_cases": counts.get("human_investigation", 0),
        "resolution_rate": counts.get("resolved", 0) / terminal if terminal else None,
        "average_resolution_seconds": (
            float(average_resolution_seconds) if average_resolution_seconds is not None else None
        ),
    }


def _latest_runs() -> Any:
    return (
        select(CaseRun.id.label("run_id"), CaseRun.case_id.label("case_id"))
        .distinct(CaseRun.case_id)
        .order_by(CaseRun.case_id, CaseRun.run_number.desc())
        .subquery()
    )


async def list_operations_cases(
    session: AsyncSession,
    *,
    status: str | None = None,
    source: str | None = None,
    category: str | None = None,
    query: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[OperationsCaseRow]:
    latest_runs = _latest_runs()
    statement = (
        select(
            SupportCase,
            InvestigationPlan.plan["category"].as_string().label("category"),
            ResolutionProposal.outcome,
            ResolutionProposal.disposition,
            Escalation.reason_code.label("escalation_reason"),
        )
        .outerjoin(latest_runs, latest_runs.c.case_id == SupportCase.id)
        .outerjoin(InvestigationPlan, InvestigationPlan.case_run_id == latest_runs.c.run_id)
        .outerjoin(ResolutionProposal, ResolutionProposal.case_run_id == latest_runs.c.run_id)
        .outerjoin(Escalation, Escalation.case_run_id == latest_runs.c.run_id)
        .where(_product_cases())
        .order_by(SupportCase.received_at.desc())
        .limit(max(1, min(limit, 200)))
        .offset(max(0, offset))
    )
    if status is not None:
        statement = statement.where(SupportCase.status == status)
    if source is not None:
        statement = statement.where(SupportCase.source == source)
    if category is not None:
        statement = statement.where(InvestigationPlan.plan["category"].as_string() == category)
    if query:
        pattern = f"%{query.strip()}%"
        statement = statement.where(
            or_(
                SupportCase.public_reference.ilike(pattern),
                SupportCase.complaint_text.ilike(pattern),
                SupportCase.claimed_customer_reference.ilike(pattern),
            )
        )
    rows = await session.execute(statement)
    return [
        OperationsCaseRow(
            case=row[0],
            category=row[1],
            outcome=row[2],
            disposition=row[3],
            escalation_reason=row[4],
        )
        for row in rows
    ]


async def get_operations_case_workspace(
    session: AsyncSession, *, case_reference: str
) -> OperationsCaseWorkspace | None:
    case_record = await session.scalar(
        select(SupportCase).where(
            SupportCase.public_reference == case_reference,
            _product_cases(),
        )
    )
    if case_record is None:
        return None

    run = await session.scalar(
        select(CaseRun)
        .where(CaseRun.case_id == case_record.id)
        .order_by(CaseRun.run_number.desc())
        .limit(1)
    )
    run_id = None if run is None else run.id

    plan: InvestigationPlan | None = None
    stages: list[WorkflowStage] = []
    evidence: list[EvidenceItem] = []
    policy_retrievals: list[PolicyRetrieval] = []
    proposal: ResolutionProposal | None = None
    verification: VerificationResult | None = None
    if run_id is not None:
        plan = await session.scalar(
            select(InvestigationPlan)
            .where(InvestigationPlan.case_run_id == run_id)
            .order_by(InvestigationPlan.revision.desc())
            .limit(1)
        )
        stages = list(
            (
                await session.scalars(
                    select(WorkflowStage)
                    .where(WorkflowStage.case_run_id == run_id)
                    .order_by(WorkflowStage.created_at)
                )
            ).all()
        )
        evidence = list(
            (
                await session.scalars(
                    select(EvidenceItem)
                    .where(EvidenceItem.case_run_id == run_id)
                    .order_by(EvidenceItem.created_at)
                )
            ).all()
        )
        policy_retrievals = list(
            (
                await session.scalars(
                    select(PolicyRetrieval)
                    .where(PolicyRetrieval.case_run_id == run_id)
                    .order_by(PolicyRetrieval.created_at)
                )
            ).all()
        )
        proposal = await session.scalar(
            select(ResolutionProposal).where(ResolutionProposal.case_run_id == run_id)
        )
        verification = await session.scalar(
            select(VerificationResult).where(VerificationResult.case_run_id == run_id)
        )

    action_rows = await session.execute(
        select(ActionIntent, Approval, OperationsAccount.display_name)
        .outerjoin(Approval, Approval.action_intent_id == ActionIntent.id)
        .outerjoin(OperationsAccount, OperationsAccount.id == Approval.decided_by_account_id)
        .where(ActionIntent.case_id == case_record.id)
        .order_by(ActionIntent.created_at)
    )
    actions = [(row[0], row[1], row[2]) for row in action_rows]
    action_ids = [item.id for item, _, _ in actions]
    execution_attempts = (
        list(
            (
                await session.scalars(
                    select(ExecutionAttempt)
                    .where(ExecutionAttempt.action_intent_id.in_(action_ids))
                    .order_by(ExecutionAttempt.started_at)
                )
            ).all()
        )
        if action_ids
        else []
    )
    escalations = list(
        (
            await session.scalars(
                select(Escalation)
                .where(Escalation.case_id == case_record.id)
                .order_by(Escalation.created_at)
            )
        ).all()
    )
    events = list(
        (
            await session.scalars(
                select(CaseEvent)
                .where(CaseEvent.case_id == case_record.id)
                .order_by(CaseEvent.sequence)
            )
        ).all()
    )
    return OperationsCaseWorkspace(
        case=case_record,
        run=run,
        plan=plan,
        stages=stages,
        evidence=evidence,
        policy_retrievals=policy_retrievals,
        proposal=proposal,
        verification=verification,
        actions=actions,
        execution_attempts=execution_attempts,
        escalations=escalations,
        events=events,
    )
