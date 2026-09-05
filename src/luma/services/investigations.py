from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from luma.db.models.case_management import (
    CaseEvent,
    Escalation,
    OperationsAccount,
    SupportCase,
)
from luma.domain.cases import CaseStatus
from luma.services.cases import transition_case


class InvestigationWorkflowError(ValueError):
    """The requested employee investigation update is not valid for the case."""


RESOLUTION_CODES = frozenset(
    {
        "no_action_required",
        "customer_guidance_provided",
        "corrected_externally",
        "other_manual_resolution",
    }
)


@dataclass(frozen=True, slots=True)
class InvestigationUpdate:
    case_status: str
    escalation_status: str


async def _locked_case(session: AsyncSession, case_reference: str) -> SupportCase:
    support_case = await session.scalar(
        select(SupportCase)
        .where(
            SupportCase.public_reference == case_reference,
            ~SupportCase.external_request_key.startswith("eval:"),
        )
        .with_for_update()
    )
    if support_case is None:
        raise InvestigationWorkflowError("case does not exist")
    if support_case.status != CaseStatus.HUMAN_INVESTIGATION.value:
        raise InvestigationWorkflowError("case is not awaiting human investigation")
    return support_case


async def _active_escalations(session: AsyncSession, case_id: UUID) -> list[Escalation]:
    return list(
        (
            await session.scalars(
                select(Escalation)
                .where(
                    Escalation.case_id == case_id,
                    Escalation.status.in_(("open", "acknowledged")),
                )
                .order_by(Escalation.created_at)
                .with_for_update()
            )
        ).all()
    )


async def _append_event(
    session: AsyncSession,
    *,
    support_case: SupportCase,
    account: OperationsAccount,
    event_type: str,
    payload: dict[str, object],
    occurred_at: datetime,
) -> None:
    sequence = await session.scalar(
        select(func.coalesce(func.max(CaseEvent.sequence), 0) + 1).where(
            CaseEvent.case_id == support_case.id
        )
    )
    support_case.version += 1
    session.add(
        CaseEvent(
            case_id=support_case.id,
            sequence=sequence,
            event_type=event_type,
            actor_type="employee",
            actor_reference=account.username,
            occurred_at=occurred_at,
            payload=payload,
        )
    )


async def acknowledge_investigation(
    session: AsyncSession,
    *,
    case_reference: str,
    account: OperationsAccount,
) -> InvestigationUpdate:
    support_case = await _locked_case(session, case_reference)
    escalations = await _active_escalations(session, support_case.id)
    if not escalations:
        raise InvestigationWorkflowError("case has no active escalation")
    if all(item.status == "acknowledged" for item in escalations):
        return InvestigationUpdate(
            case_status=support_case.status,
            escalation_status="acknowledged",
        )

    now = datetime.now(UTC)
    for escalation in escalations:
        escalation.status = "acknowledged"
    await _append_event(
        session,
        support_case=support_case,
        account=account,
        event_type="human_investigation_started",
        payload={"escalation_count": len(escalations)},
        occurred_at=now,
    )
    await session.flush()
    return InvestigationUpdate(
        case_status=support_case.status,
        escalation_status="acknowledged",
    )


async def add_investigation_note(
    session: AsyncSession,
    *,
    case_reference: str,
    account: OperationsAccount,
    note: str,
) -> InvestigationUpdate:
    support_case = await _locked_case(session, case_reference)
    escalations = await _active_escalations(session, support_case.id)
    if not escalations:
        raise InvestigationWorkflowError("case has no active escalation")
    cleaned_note = note.strip()
    if not cleaned_note:
        raise InvestigationWorkflowError("investigation note must not be blank")

    now = datetime.now(UTC)
    for escalation in escalations:
        if escalation.status == "open":
            escalation.status = "acknowledged"
    await _append_event(
        session,
        support_case=support_case,
        account=account,
        event_type="human_investigation_note_added",
        payload={"note": cleaned_note},
        occurred_at=now,
    )
    await session.flush()
    return InvestigationUpdate(
        case_status=support_case.status,
        escalation_status="acknowledged",
    )


async def resolve_investigation(
    session: AsyncSession,
    *,
    case_reference: str,
    account: OperationsAccount,
    resolution_code: str,
    resolution_summary: str,
    customer_response: str,
) -> InvestigationUpdate:
    support_case = await _locked_case(session, case_reference)
    escalations = await _active_escalations(session, support_case.id)
    if not escalations:
        raise InvestigationWorkflowError("case has no active escalation")
    cleaned_summary = resolution_summary.strip()
    cleaned_response = customer_response.strip()
    if resolution_code not in RESOLUTION_CODES:
        raise InvestigationWorkflowError("unsupported investigation resolution type")
    if not cleaned_summary:
        raise InvestigationWorkflowError("resolution summary must not be blank")
    if not cleaned_response:
        raise InvestigationWorkflowError("customer response must not be blank")

    now = datetime.now(UTC)
    for escalation in escalations:
        escalation.status = "resolved"
        escalation.resolved_by_account_id = account.id
        escalation.resolved_at = now
    await transition_case(
        session,
        case_id=support_case.id,
        to_status=CaseStatus.RESOLVED,
        event_type="human_investigation_resolved",
        actor_type="employee",
        actor_reference=account.username,
        payload={
            "resolution_code": resolution_code,
            "resolution_summary": cleaned_summary,
            "customer_response": cleaned_response,
            "resolved_escalation_count": len(escalations),
        },
        occurred_at=now,
    )
    await session.flush()
    return InvestigationUpdate(case_status="resolved", escalation_status="resolved")
