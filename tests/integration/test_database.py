from __future__ import annotations

import pytest
from sqlalchemy import text

from luma.db.health import database_healthcheck
from luma.db.session import Database

pytestmark = pytest.mark.integration


async def test_database_healthcheck(database: Database) -> None:
    assert await database_healthcheck(database)


async def test_vector_extension_is_installed(database: Database) -> None:
    async with database.session() as session:
        result = await session.execute(
            text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')")
        )

    assert result.scalar_one() is True
