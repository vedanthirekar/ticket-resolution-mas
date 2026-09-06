from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from luma.agents.contracts import EvidenceRecord, ResolutionProposalOutput, VerificationOutput
from luma.db.models.ai_runtime import (
    CaseRun,
    EvidenceItem,
    InvestigationPlan,
    PolicyRetrieval,
    ResolutionProposal,
    VerificationResult,
    WorkflowStage,
)
from luma.db.models.case_management import SupportCase

ARCHITECTURE_VERSION = "multi-agent-v3"


async def get_or_create_case_run(
    session: AsyncSession,
    *,
    case_id: UUID,
    model_provider: str,
    model_name: str,
) -> CaseRun:
    existing = (
        await session.execute(
            select(CaseRun)
            .where(CaseRun.case_id == case_id, CaseRun.status.in_(["queued", "running"]))
            .order_by(CaseRun.run_number.desc())
            .limit(1)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    support_case = await session.get(SupportCase, case_id)
    if support_case is None:
        raise ValueError("case does not exist")
    run_number = await session.scalar(
        select(func.coalesce(func.max(CaseRun.run_number), 0) + 1).where(CaseRun.case_id == case_id)
    )
    run = CaseRun(
        case_id=case_id,
        run_number=run_number,
        architecture_version=ARCHITECTURE_VERSION,
        model_provider=model_provider,
        model_name=model_name,
        configuration={"model_routing": False, "supplemental_rounds": 1},
        status="running",
        started_at=datetime.now(UTC),
    )
    session.add(run)
    await session.flush()
    return run


async def completed_stage_output(
    session: AsyncSession, case_run_id: UUID, stage_name: str
) -> dict[str, Any] | None:
    stage = await session.scalar(
        select(WorkflowStage).where(
            WorkflowStage.case_run_id == case_run_id,
            WorkflowStage.stage_name == stage_name,
            WorkflowStage.status == "completed",
        )
    )
    return None if stage is None else stage.output


async def complete_stage(
    session: AsyncSession,
    *,
    case_run_id: UUID,
    stage_name: str,
    output: dict[str, Any],
) -> dict[str, Any]:
    # Artifact rows may already be pending in this session. Suppress autoflush
    # until the parent is verified and locked, otherwise a concurrently deleted
    # run surfaces as an opaque child-table foreign-key violation.
    with session.no_autoflush:
        parent_run_id = await session.scalar(
            select(CaseRun.id).where(CaseRun.id == case_run_id).with_for_update()
        )
    if parent_run_id is None:
        raise RuntimeError(f"case run {case_run_id} was deleted while the workflow was active")

    stage = (
        await session.execute(
            select(WorkflowStage)
            .where(
                WorkflowStage.case_run_id == case_run_id,
                WorkflowStage.stage_name == stage_name,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if stage is not None and stage.status == "completed":
        return stage.output
    now = datetime.now(UTC)
    if stage is None:
        stage = WorkflowStage(
            case_run_id=case_run_id,
            stage_name=stage_name,
            status="completed",
            attempt_count=1,
            output=output,
            completed_at=now,
        )
        session.add(stage)
    else:
        stage.status = "completed"
        stage.attempt_count += 1
        stage.output = output
        stage.completed_at = now
        stage.error_code = None
        stage.error_detail = None
    await session.flush()
    return output


async def persist_plan(session: AsyncSession, *, case_run_id: UUID, plan: dict[str, Any]) -> None:
    existing = await session.scalar(
        select(InvestigationPlan.id).where(
            InvestigationPlan.case_run_id == case_run_id,
            InvestigationPlan.revision == 1,
        )
    )
    if existing is None:
        session.add(InvestigationPlan(case_run_id=case_run_id, revision=1, plan=plan))


async def persist_evidence(
    session: AsyncSession, *, case_run_id: UUID, records: list[EvidenceRecord]
) -> None:
    for record in records:
        session.add(
            EvidenceItem(
                case_run_id=case_run_id,
                evidence_type=record.evidence_type,
                condition=record.condition,
                source_system="luma_postgresql",
                source_reference=(",".join(record.source_references) or None),
                tool_call_reference=record.tool_call_id,
                observed_as_of=datetime.now(UTC),
                content=record.model_dump(mode="json"),
            )
        )


async def persist_policy_retrieval(
    session: AsyncSession,
    *,
    case_run_id: UUID,
    query: str,
    effective_on: datetime,
    filters: dict[str, Any],
    results: list[dict[str, Any]],
    selected_ids: list[str],
) -> None:
    session.add(
        PolicyRetrieval(
            case_run_id=case_run_id,
            query_text=query,
            effective_on=effective_on.date(),
            filters=filters,
            retrieval_config={"algorithm": "weighted_rrf", "limit": 5},
            ranked_results=results,
            selected_section_ids=selected_ids,
        )
    )


async def persist_proposal(
    session: AsyncSession, *, case_run_id: UUID, proposal: ResolutionProposalOutput
) -> None:
    existing = await session.scalar(
        select(ResolutionProposal.id).where(ResolutionProposal.case_run_id == case_run_id)
    )
    if existing is None:
        session.add(
            ResolutionProposal(
                case_run_id=case_run_id,
                outcome=proposal.outcome,
                disposition=proposal.disposition,
                rationale=proposal.rationale,
                action_payload=(
                    proposal.action_payload.model_dump(mode="json")
                    if proposal.action_payload is not None
                    else None
                ),
                evidence_references=proposal.evidence_references,
                policy_references=proposal.policy_references,
            )
        )


async def persist_verification(
    session: AsyncSession, *, case_run_id: UUID, result: VerificationOutput
) -> None:
    existing = await session.scalar(
        select(VerificationResult.id).where(VerificationResult.case_run_id == case_run_id)
    )
    if existing is None:
        session.add(
            VerificationResult(
                case_run_id=case_run_id,
                supported=result.supported,
                missing_evidence=result.missing_evidence,
                contradictions=result.contradictions,
                unsupported_claims=result.unsupported_claims,
                recommended_outcome=result.recommended_outcome,
                recommended_disposition=result.recommended_disposition,
                requires_human=result.requires_human,
                rationale=result.rationale,
            )
        )


async def complete_run(
    session: AsyncSession,
    case_run_id: UUID,
    *,
    input_tokens: int = 0,
    output_tokens: int = 0,
) -> None:
    run = await session.get(CaseRun, case_run_id)
    if run is not None and run.status != "completed":
        run.status = "completed"
        run.completed_at = datetime.now(UTC)
        run.input_tokens = input_tokens
        run.output_tokens = output_tokens
