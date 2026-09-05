from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
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
    Escalation,
    ExecutionAttempt,
    SupportCase,
)
from luma.evaluation.contracts import EvalObservation


def _disposition(case_status: str, proposal: ResolutionProposal | None) -> str | None:
    if case_status == "human_investigation":
        return "human_investigation"
    if case_status == "pending_approval":
        return "human_approval"
    if case_status == "resolved":
        return proposal.disposition if proposal is not None else "auto_resolve"
    return proposal.disposition if proposal is not None else None


async def observe_case_run(
    session: AsyncSession, *, eval_case_id: str, case_id: UUID
) -> EvalObservation:
    support_case = await session.get(SupportCase, case_id)
    if support_case is None:
        raise ValueError("support case does not exist")
    run = await session.scalar(
        select(CaseRun)
        .where(CaseRun.case_id == case_id)
        .order_by(CaseRun.run_number.desc())
        .limit(1)
    )
    if run is None:
        return EvalObservation(case_id=eval_case_id, case_reference=support_case.public_reference)
    plan = await session.scalar(
        select(InvestigationPlan).where(InvestigationPlan.case_run_id == run.id)
    )
    evidence = list(
        (
            await session.scalars(select(EvidenceItem).where(EvidenceItem.case_run_id == run.id))
        ).all()
    )
    retrievals = list(
        (
            await session.scalars(
                select(PolicyRetrieval).where(PolicyRetrieval.case_run_id == run.id)
            )
        ).all()
    )
    stages = list(
        (
            await session.scalars(select(WorkflowStage).where(WorkflowStage.case_run_id == run.id))
        ).all()
    )
    proposal = await session.scalar(
        select(ResolutionProposal).where(ResolutionProposal.case_run_id == run.id)
    )
    verification = await session.scalar(
        select(VerificationResult).where(VerificationResult.case_run_id == run.id)
    )
    action_intent = await session.scalar(
        select(ActionIntent).where(ActionIntent.case_run_id == run.id)
    )
    escalation = await session.scalar(select(Escalation).where(Escalation.case_run_id == run.id))

    action: dict[str, object] | None = None
    unauthorized_mutation_count = 0
    duplicate_execution_count = 0
    if action_intent is not None:
        command = action_intent.action_payload.get("command", action_intent.action_payload)
        action = {
            "action_type": action_intent.action_type,
            "target_reference": action_intent.target_reference,
            **{key: command[key] for key in ("amount_cents", "credit_delta") if key in command},
        }
        execution_count = int(
            await session.scalar(
                select(func.count(ExecutionAttempt.id)).where(
                    ExecutionAttempt.action_intent_id == action_intent.id,
                    ExecutionAttempt.status == "succeeded",
                )
            )
            or 0
        )
        has_approval = await session.scalar(
            select(Approval.id).where(
                Approval.action_intent_id == action_intent.id,
                Approval.decision == "approved",
            )
        )
        unauthorized_mutation_count = (
            execution_count if execution_count and has_approval is None else 0
        )
        duplicate_execution_count = max(0, execution_count - 1)

    source_references: set[str] = set()
    tools_called: set[str] = set()
    for item in evidence:
        if item.source_reference:
            source_references.update(value for value in item.source_reference.split(",") if value)
        tool_name = item.content.get("tool_name")
        if isinstance(tool_name, str):
            tools_called.add(tool_name)
    policy_references = {
        reference for retrieval in retrievals for reference in retrieval.selected_section_ids
    }
    latency_ms = None
    if run.started_at is not None and run.completed_at is not None:
        latency_ms = (run.completed_at - run.started_at).total_seconds() * 1000
    stage_input_tokens = max(
        (int(stage.output.get("input_tokens", 0)) for stage in stages), default=0
    )
    stage_output_tokens = max(
        (int(stage.output.get("output_tokens", 0)) for stage in stages), default=0
    )
    return EvalObservation(
        case_id=eval_case_id,
        case_reference=support_case.public_reference,
        case_run_id=str(run.id),
        category=plan.plan.get("category") if plan is not None else None,
        outcome=proposal.outcome if proposal is not None else None,
        disposition=_disposition(support_case.status, proposal),
        evidence_types=sorted(
            {item.evidence_type for item in evidence if item.condition == "present"}
        ),
        source_references=sorted(source_references),
        policy_references=sorted(policy_references),
        tools_called=sorted(tools_called),
        action=action,
        escalation_reason=escalation.reason_code if escalation is not None else None,
        verifier_supported=verification.supported if verification is not None else None,
        unauthorized_mutation_count=unauthorized_mutation_count,
        duplicate_execution_count=duplicate_execution_count,
        latency_ms=latency_ms,
        input_tokens=run.input_tokens if run.input_tokens is not None else stage_input_tokens,
        output_tokens=run.output_tokens if run.output_tokens is not None else stage_output_tokens,
        estimated_cost_usd=float(run.estimated_cost_usd)
        if run.estimated_cost_usd is not None
        else None,
        error=run.error_code,
    )
