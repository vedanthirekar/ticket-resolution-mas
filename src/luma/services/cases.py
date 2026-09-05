from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from luma.db.models.case_management import CaseEvent, ProcessingJob, SupportCase
from luma.db.models.organization import Customer
from luma.domain.cases import (
    ALLOWED_CASE_TRANSITIONS,
    CaseSource,
    CaseStatus,
    ClaimedCaseCategory,
)


class CaseIntakeError(ValueError):
    """Base class for an invalid case intake operation."""


class IdempotencyConflictError(CaseIntakeError):
    """The source reused an idempotency key for different content."""


class CaseTransitionError(ValueError):
    """The requested case transition violates the lifecycle contract."""


@dataclass(frozen=True, slots=True)
class CreateCaseCommand:
    complaint_text: str
    source: CaseSource
    external_request_key: str
    claimed_customer_reference: str | None = None
    claimed_category: ClaimedCaseCategory | None = None


@dataclass(frozen=True, slots=True)
class CreateCaseResult:
    case: SupportCase
    created: bool


def _fingerprint(command: CreateCaseCommand, complaint_text: str) -> str:
    canonical = json.dumps(
        {
            "claimed_customer_reference": command.claimed_customer_reference,
            "claimed_category": (
                command.claimed_category.value if command.claimed_category is not None else None
            ),
            "complaint_text": complaint_text,
            "source": command.source.value,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


async def create_case(session: AsyncSession, command: CreateCaseCommand) -> CreateCaseResult:
    """Create a case, immutable intake events, and its first job atomically.

    The caller owns the transaction. A source-scoped idempotency key safely handles
    concurrent request retries.
    """
    complaint_text = command.complaint_text.strip()
    if not complaint_text:
        raise CaseIntakeError("complaint_text must not be blank")
    if len(complaint_text) > 10_000:
        raise CaseIntakeError("complaint_text exceeds 10000 characters")
    if not command.external_request_key.strip():
        raise CaseIntakeError("external_request_key must not be blank")
    if len(command.external_request_key) > 128:
        raise CaseIntakeError("external_request_key exceeds 128 characters")

    customer_id: UUID | None = None
    if command.claimed_customer_reference:
        customer_id = await session.scalar(
            select(Customer.id).where(
                Customer.public_reference == command.claimed_customer_reference
            )
        )

    case_id = uuid4()
    public_reference = f"CASE-{case_id.hex[:12].upper()}"
    request_fingerprint = _fingerprint(command, complaint_text)
    values = {
        "id": case_id,
        "public_reference": public_reference,
        "source": command.source.value,
        "external_request_key": command.external_request_key,
        "request_fingerprint": request_fingerprint,
        "customer_id": customer_id,
        "claimed_customer_reference": command.claimed_customer_reference,
        "claimed_category": (
            command.claimed_category.value if command.claimed_category is not None else None
        ),
        "complaint_text": complaint_text,
        "status": CaseStatus.QUEUED.value,
        "version": 1,
    }
    statement = (
        insert(SupportCase)
        .values(**values)
        .on_conflict_do_nothing(
            index_elements=[SupportCase.source, SupportCase.external_request_key]
        )
        .returning(SupportCase.id)
    )
    inserted_id = await session.scalar(statement)

    if inserted_id is None:
        existing = (
            await session.execute(
                select(SupportCase).where(
                    SupportCase.source == command.source.value,
                    SupportCase.external_request_key == command.external_request_key,
                )
            )
        ).scalar_one()
        if existing.request_fingerprint != request_fingerprint:
            raise IdempotencyConflictError(
                "external_request_key was already used for a different request"
            )
        return CreateCaseResult(case=existing, created=False)

    support_case = (
        await session.execute(select(SupportCase).where(SupportCase.id == inserted_id))
    ).scalar_one()
    now = datetime.now(UTC)
    session.add_all(
        [
            CaseEvent(
                case_id=support_case.id,
                sequence=1,
                event_type="case_received",
                actor_type="customer" if command.source is CaseSource.MANUAL else "system",
                actor_reference=command.source.value,
                occurred_at=now,
                payload={"source": command.source.value},
            ),
            CaseEvent(
                case_id=support_case.id,
                sequence=2,
                event_type="case_queued",
                actor_type="system",
                actor_reference="intake_service",
                occurred_at=now,
                payload={},
            ),
            ProcessingJob(
                case_id=support_case.id,
                job_type="case_resolution",
                status="queued",
                available_at=now,
                max_attempts=3,
            ),
        ]
    )
    await session.flush()
    return CreateCaseResult(case=support_case, created=True)


async def transition_case(
    session: AsyncSession,
    *,
    case_id: UUID,
    to_status: CaseStatus,
    event_type: str,
    actor_type: str,
    actor_reference: str,
    payload: dict[str, object] | None = None,
    occurred_at: datetime | None = None,
) -> SupportCase:
    """Lock a case, validate its state change, and append the next event."""
    support_case = (
        await session.execute(
            select(SupportCase).where(SupportCase.id == case_id).with_for_update()
        )
    ).scalar_one()
    current = CaseStatus(support_case.status)
    if to_status not in ALLOWED_CASE_TRANSITIONS[current]:
        raise CaseTransitionError(f"cannot transition case from {current} to {to_status}")

    next_sequence = await session.scalar(
        select(func.coalesce(func.max(CaseEvent.sequence), 0) + 1).where(
            CaseEvent.case_id == case_id
        )
    )
    support_case.status = to_status.value
    support_case.version += 1
    event_time = occurred_at or datetime.now(UTC)
    if to_status is CaseStatus.RESOLVED:
        support_case.resolved_at = event_time
    session.add(
        CaseEvent(
            case_id=case_id,
            sequence=next_sequence,
            event_type=event_type,
            actor_type=actor_type,
            actor_reference=actor_reference,
            occurred_at=event_time,
            payload=payload or {},
        )
    )
    await session.flush()
    return support_case
