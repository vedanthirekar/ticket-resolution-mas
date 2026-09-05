from __future__ import annotations

from luma.config import get_settings
from luma.db.session import Database
from luma.retrieval.embeddings import HashingEmbeddingProvider
from luma.retrieval.indexing import index_policy_sections
from luma.runtime import run_async


async def _index() -> int:
    settings = get_settings()
    database = Database(settings.database_url, echo=settings.database_echo)
    try:
        async with database.transaction() as session:
            return await index_policy_sections(session, HashingEmbeddingProvider())
    finally:
        await database.dispose()


def main() -> None:
    count = run_async(_index())
    print(f"indexed {count} policy sections")


if __name__ == "__main__":
    main()
