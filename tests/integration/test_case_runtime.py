from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, func, select

from luma.db.models.case_management import CaseEvent, ProcessingJob, SupportCase
from luma.domain.cases import CaseSource, FailureKind, JobStatus
from luma.services.cases import (
    CreateCaseCommand,
    IdempotencyConflictError,
    create_case,
)
from luma.services.jobs import claim_next_job, fail_job

pytestmark = pytest.mark.integration


async def _delete_test_cases(database, prefix: str) -> None:
    async with database.transaction() as session:
        await session.execute(
            delete(SupportCase).where(SupportCase.external_request_key.startswith(prefix))
        )


async def test_case_intake_is_atomic_and_idempotent(database) -> None:
    key = "runtime-idempotency-001"
    await _delete_test_cases(database, key)
    command = CreateCaseCommand(
        complaint_text="I was charged twice for one appointment.",
        source=CaseSource.API,
        external_request_key=key,
        claimed_customer_reference="CUS-DOES-NOT-EXIST",
    )
    try:
        async with database.transaction() as session:
            first = await create_case(session, command)
        async with database.transaction() as session:
            second = await create_case(session, command)

        assert first.created is True
        assert second.created is False
        assert second.case.id == first.case.id
        assert first.case.customer_id is None

        async with database.session() as session:
            event_count = await session.scalar(
                select(func.count())
                .select_from(CaseEvent)
                .where(CaseEvent.case_id == first.case.id)
            )
            job_count = await session.scalar(
                select(func.count())
                .select_from(ProcessingJob)
                .where(ProcessingJob.case_id == first.case.id)
            )
        assert event_count == 2
        assert job_count == 1

        conflicting = CreateCaseCommand(
            complaint_text="Different complaint with the same request key.",
            source=CaseSource.API,
            external_request_key=key,
        )
        with pytest.raises(IdempotencyConflictError):
            async with database.transaction() as session:
                await create_case(session, conflicting)
    finally:
        await _delete_test_cases(database, key)


async def test_job_lease_prevents_double_claim_and_recovers_after_expiry(database) -> None:
    key = "runtime-lease-001"
    await _delete_test_cases(database, key)
    start = datetime.now(UTC) + timedelta(seconds=1)
    try:
        async with database.transaction() as session:
            created = await create_case(
                session,
                CreateCaseCommand(
                    complaint_text="My cancellation fee looks wrong.",
                    source=CaseSource.API,
                    external_request_key=key,
                ),
            )

        async with database.session() as first_session:
            async with first_session.begin():
                first_claim = await claim_next_job(
                    first_session,
                    worker_id="worker-a",
                    lease_duration=timedelta(seconds=30),
                    now=start,
                )
                assert first_claim is not None

                async with database.transaction() as second_session:
                    competing_claim = await claim_next_job(
                        second_session,
                        worker_id="worker-b",
                        lease_duration=timedelta(seconds=30),
                        now=start,
                    )
                assert competing_claim is None

        async with database.transaction() as session:
            recovered = await claim_next_job(
                session,
                worker_id="worker-b",
                lease_duration=timedelta(seconds=30),
                now=start + timedelta(seconds=31),
            )
        assert recovered is not None
        assert recovered.id == first_claim.id
        assert recovered.case_id == created.case.id
        assert recovered.attempt_count == 2
    finally:
        await _delete_test_cases(database, key)


async def test_permanent_job_failure_dead_letters_and_escalates(database) -> None:
    key = "runtime-dead-letter-001"
    await _delete_test_cases(database, key)
    now = datetime.now(UTC) + timedelta(seconds=1)
    try:
        async with database.transaction() as session:
            created = await create_case(
                session,
                CreateCaseCommand(
                    complaint_text="There is not enough evidence in the records.",
                    source=CaseSource.API,
                    external_request_key=key,
                ),
            )
        async with database.transaction() as session:
            claimed = await claim_next_job(session, worker_id="worker-a", now=now)
        assert claimed is not None

        async with database.transaction() as session:
            result = await fail_job(
                session,
                job_id=claimed.id,
                worker_id="worker-a",
                failure_kind=FailureKind.PERMANENT,
                error_code="unsupported_input",
                error_detail="test permanent failure",
                now=now + timedelta(seconds=1),
            )
        assert result is JobStatus.DEAD_LETTER

        async with database.session() as session:
            case_record = await session.get(SupportCase, created.case.id)
            job = await session.get(ProcessingJob, claimed.id)
        assert case_record is not None and case_record.status == "human_investigation"
        assert job is not None and job.status == "dead_letter"
    finally:
        await _delete_test_cases(database, key)
