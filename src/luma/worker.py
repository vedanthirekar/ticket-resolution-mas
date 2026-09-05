from __future__ import annotations

import argparse
import asyncio
import logging
import socket
from datetime import timedelta
from typing import Any
from uuid import uuid4

from langgraph.checkpoint.base import BaseCheckpointSaver
from sqlalchemy import select

from luma.agents.checkpoints import postgres_checkpointer
from luma.agents.graph import CaseResolutionWorkflow
from luma.agents.models import build_model
from luma.agents.runner import run_case
from luma.config import Settings, get_settings
from luma.db.models.case_management import SupportCase
from luma.db.session import Database
from luma.domain.cases import CaseStatus, FailureKind
from luma.observability.logging import log_event
from luma.retrieval.embeddings import HashingEmbeddingProvider
from luma.runtime import run_async
from luma.services.jobs import claim_next_job, complete_job, fail_job


def _failure_kind(error: Exception) -> FailureKind:
    if isinstance(error, (TimeoutError, ConnectionError)):
        return FailureKind.TRANSIENT
    message = str(error).lower()
    transient_markers = ("429", "503", "quota", "rate limit", "timeout", "temporarily unavailable")
    if any(marker in message for marker in transient_markers):
        return FailureKind.TRANSIENT
    return FailureKind.PERMANENT


async def process_next_job(
    database: Database,
    workflow: CaseResolutionWorkflow,
    checkpointer: BaseCheckpointSaver[Any],
    *,
    worker_id: str,
    settings: Settings,
) -> bool:
    async with database.transaction() as session:
        claimed = await claim_next_job(
            session,
            worker_id=worker_id,
            lease_duration=timedelta(seconds=settings.worker_lease_seconds),
        )
    if claimed is None:
        return False

    logger = logging.getLogger("luma.worker")
    log_event(
        logger,
        "job_claimed",
        job_id=claimed.id,
        job_type=claimed.job_type,
        attempt=claimed.attempt_count,
        worker_id=worker_id,
    )
    try:
        async with database.session() as session:
            case_status = await session.scalar(
                select(SupportCase.status).where(SupportCase.id == claimed.case_id)
            )
        already_yielded = (
            claimed.job_type == "case_resolution"
            and case_status == CaseStatus.PENDING_APPROVAL.value
        )
        terminal = case_status in {
            CaseStatus.RESOLVED.value,
            CaseStatus.HUMAN_INVESTIGATION.value,
            CaseStatus.FAILED.value,
        }
        if not already_yielded and not terminal:
            await run_case(
                database,
                workflow,
                case_id=claimed.case_id,
                checkpointer=checkpointer,
            )
        async with database.transaction() as session:
            await complete_job(session, job_id=claimed.id, worker_id=worker_id)
        log_event(logger, "job_completed", job_id=claimed.id, worker_id=worker_id)
    except Exception as error:
        failure_kind = _failure_kind(error)
        async with database.transaction() as session:
            result = await fail_job(
                session,
                job_id=claimed.id,
                worker_id=worker_id,
                failure_kind=failure_kind,
                error_code=type(error).__name__.lower(),
                error_detail=str(error),
            )
        log_event(
            logger,
            "job_failed",
            job_id=claimed.id,
            worker_id=worker_id,
            failure_kind=failure_kind.value,
            resulting_status=result.value,
            error_type=type(error).__name__,
        )
    return True


async def run_worker(*, once: bool = False) -> None:
    settings = get_settings()
    database = Database(settings.database_url, echo=settings.database_echo)
    worker_id = f"{socket.gethostname()}-{uuid4().hex[:8]}"
    workflow = CaseResolutionWorkflow(
        database=database,
        model=build_model(settings),
        embedding_provider=HashingEmbeddingProvider(),
        settings=settings,
    )
    try:
        async with postgres_checkpointer(settings.database_url) as checkpointer:
            while True:
                processed = await process_next_job(
                    database,
                    workflow,
                    checkpointer,
                    worker_id=worker_id,
                    settings=settings,
                )
                if once:
                    return
                if not processed:
                    await asyncio.sleep(settings.worker_poll_seconds)
    finally:
        await database.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the durable Luma case worker")
    parser.add_argument("--once", action="store_true", help="claim at most one job and exit")
    args = parser.parse_args()
    logging.basicConfig(level=get_settings().log_level)
    run_async(run_worker(once=args.once))


if __name__ == "__main__":
    main()
