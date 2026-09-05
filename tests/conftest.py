from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest

from luma.config import Settings
from luma.db.session import Database
from luma.runtime import configure_asyncio_policy

configure_asyncio_policy()


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    if os.getenv("RUN_DB_TESTS") == "1":
        return

    skip_database = pytest.mark.skip(reason="set RUN_DB_TESTS=1 with PostgreSQL running")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_database)


@pytest.fixture
async def database() -> AsyncIterator[Database]:
    settings = Settings(_env_file=".env")
    instance = Database(settings.database_url, echo=settings.database_echo)
    try:
        yield instance
    finally:
        await instance.dispose()
