from __future__ import annotations

import argparse

from sqlalchemy import select

from luma.agents.checkpoints import postgres_checkpointer
from luma.agents.graph import CaseResolutionWorkflow
from luma.agents.models import build_model
from luma.agents.runner import run_case
from luma.config import get_settings
from luma.db.models.case_management import SupportCase
from luma.db.session import Database
from luma.retrieval.embeddings import HashingEmbeddingProvider
from luma.runtime import run_async


async def _run(case_reference: str, *, setup_checkpoints: bool) -> None:
    settings = get_settings()
    database = Database(settings.database_url, echo=settings.database_echo)
    try:
        async with postgres_checkpointer(
            settings.database_url, setup=setup_checkpoints
        ) as checkpointer:
            if setup_checkpoints and not case_reference:
                print("LangGraph checkpoint tables are ready.")
                return
            async with database.session() as session:
                case_id = await session.scalar(
                    select(SupportCase.id).where(SupportCase.public_reference == case_reference)
                )
            if case_id is None:
                raise SystemExit(f"case not found: {case_reference}")
            workflow = CaseResolutionWorkflow(
                database=database,
                model=build_model(settings),
                embedding_provider=HashingEmbeddingProvider(),
                settings=settings,
            )
            result = await run_case(database, workflow, case_id=case_id, checkpointer=checkpointer)
            print(result)
    finally:
        await database.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run or initialize the Luma agent graph")
    parser.add_argument("case_reference", nargs="?", default="")
    parser.add_argument(
        "--setup-checkpoints", action="store_true", help="create/update checkpoint tables"
    )
    args = parser.parse_args()
    if not args.case_reference and not args.setup_checkpoints:
        parser.error("case_reference is required unless --setup-checkpoints is used")
    run_async(_run(args.case_reference, setup_checkpoints=args.setup_checkpoints))


if __name__ == "__main__":
    main()
