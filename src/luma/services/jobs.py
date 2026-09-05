from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import case, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from luma.db.models.case_management import Escalation, ProcessingJob, SupportCase
from luma.domain.cases import CaseStatus, FailureKind, JobStatus
from luma.services.cases import transition_case


class JobLeaseError(RuntimeError):
    """A worker attempted to modify a job it does not currently lease."""


@dataclass(frozen=True, slots=True)
class ClaimedJob:
    id: UUID
    case_id: UUID
    job_type: str
    attempt_count: int
    lease_expires_at: datetime


def _assert_owned_lease(job: ProcessingJob, worker_id: str, now: datetime) -> None:
    if job.status != JobStatus.LEASED.value or job.lease_owner != worker_id:
        raise JobLeaseError("worker does not own the active lease")
    if job.lease_expires_at is None or job.lease_expires_at <= now:
        raise JobLeaseError("job lease has expired")


async def claim_next_job(
    session: AsyncSession,
    *,
    worker_id: str,
    lease_duration: timedelta = timedelta(minutes=2),
    now: datetime | None = None,
) -> ClaimedJob | None:
    """Claim one eligible job under a PostgreSQL skip-locked row lease."""
    claim_time = now or datetime.now(UTC)
    eligible = or_(
        (
            ProcessingJob.status.in_([JobStatus.QUEUED.value, JobStatus.RETRY_WAIT.value])
            & (ProcessingJob.available_at <= claim_time)
        ),
        (
            (ProcessingJob.status == JobStatus.LEASED.value)
            & (ProcessingJob.lease_expires_at <= claim_time)
        ),
    )
    priority_order = case(
        (SupportCase.priority == "urgent", 0),
        (SupportCase.priority == "high", 1),
        else_=2,
    )
    job = (
        await session.execute(
            select(ProcessingJob)
            .join(SupportCase, SupportCase.id == ProcessingJob.case_id)
            .where(eligible)
            .order_by(priority_order, ProcessingJob.available_at, ProcessingJob.created_at)
            .limit(1)
            .with_for_update(of=ProcessingJob, skip_locked=True)
        )
    ).scalar_one_or_none()
    if job is None:
        return None

    job.status = JobStatus.LEASED.value
    job.lease_owner = worker_id
    job.lease_expires_at = claim_time + lease_duration
    job.attempt_count += 1
    job.last_error_code = None
    job.last_error_detail = None

    support_case = await session.get(SupportCase, job.case_id)
    if support_case is not None and support_case.status == CaseStatus.QUEUED.value:
        await transition_case(
            session,
            case_id=job.case_id,
            to_status=CaseStatus.PROCESSING,
            event_type="processing_started",
            actor_type="system",
            actor_reference=worker_id,
            payload={"job_id": str(job.id), "attempt": job.attempt_count},
            occurred_at=claim_time,
        )
    await session.flush()
    return ClaimedJob(
        id=job.id,
        case_id=job.case_id,
        job_type=job.job_type,
        attempt_count=job.attempt_count,
        lease_expires_at=job.lease_expires_at,
    )


async def enqueue_approval_resume(
    session: AsyncSession,
    *,
    case_id: UUID,
    action_reference: str,
    now: datetime | None = None,
) -> None:
    """Idempotently enqueue graph continuation in the approval transaction."""
    await session.execute(
        insert(ProcessingJob)
        .values(
            case_id=case_id,
            job_type=f"approval_resume:{action_reference}",
            status=JobStatus.QUEUED.value,
            available_at=now or datetime.now(UTC),
            attempt_count=0,
            max_attempts=3,
        )
        .on_conflict_do_nothing(index_elements=[ProcessingJob.case_id, ProcessingJob.job_type])
    )
    await session.flush()


async def complete_job(
    session: AsyncSession, *, job_id: UUID, worker_id: str, now: datetime | None = None
) -> None:
    completion_time = now or datetime.now(UTC)
    job = (
        await session.execute(
            select(ProcessingJob).where(ProcessingJob.id == job_id).with_for_update()
        )
    ).scalar_one()
    _assert_owned_lease(job, worker_id, completion_time)
    job.status = JobStatus.SUCCEEDED.value
    job.lease_owner = None
    job.lease_expires_at = None
    await session.flush()


async def fail_job(
    session: AsyncSession,
    *,
    job_id: UUID,
    worker_id: str,
    failure_kind: FailureKind,
    error_code: str,
    error_detail: str,
    now: datetime | None = None,
) -> JobStatus:
    failure_time = now or datetime.now(UTC)
    job = (
        await session.execute(
            select(ProcessingJob).where(ProcessingJob.id == job_id).with_for_update()
        )
    ).scalar_one()
    _assert_owned_lease(job, worker_id, failure_time)
    job.last_error_code = error_code[:64]
    job.last_error_detail = error_detail[:4000]
    job.lease_owner = None
    job.lease_expires_at = None

    retryable = failure_kind is FailureKind.TRANSIENT and job.attempt_count < job.max_attempts
    if retryable:
        delay_seconds = min(300, 2 ** (job.attempt_count - 1) * 10)
        job.status = JobStatus.RETRY_WAIT.value
        job.available_at = failure_time + timedelta(seconds=delay_seconds)
        await session.flush()
        return JobStatus.RETRY_WAIT

    job.status = JobStatus.DEAD_LETTER.value
    session.add(
        Escalation(
            case_id=job.case_id,
            reason_code="processing_exhausted",
            details={
                "job_id": str(job.id),
                "attempt_count": job.attempt_count,
                "error_code": job.last_error_code,
            },
            status="open",
        )
    )
    support_case = await session.get(SupportCase, job.case_id)
    if support_case is not None and support_case.status in {
        CaseStatus.QUEUED.value,
        CaseStatus.PROCESSING.value,
    }:
        await transition_case(
            session,
            case_id=job.case_id,
            to_status=CaseStatus.HUMAN_INVESTIGATION,
            event_type="processing_escalated",
            actor_type="system",
            actor_reference="job_service",
            payload={"job_id": str(job.id), "error_code": job.last_error_code},
            occurred_at=failure_time,
        )
    await session.flush()
    return JobStatus.DEAD_LETTER
