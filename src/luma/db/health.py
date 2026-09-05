from __future__ import annotations

from typing import cast

from sqlalchemy import text

from luma.config import get_settings
from luma.db.session import Database
from luma.runtime import run_async


async def database_healthcheck(database: Database) -> bool:
    async with database.session() as session:
        result = await session.execute(text("SELECT 1"))
        value = cast(int, result.scalar_one())
        return value == 1


async def _main() -> None:
    settings = get_settings()
    database = Database(settings.database_url, echo=settings.database_echo)
    try:
        healthy = await database_healthcheck(database)
        print("database healthy" if healthy else "database unhealthy")
    finally:
        await database.dispose()


if __name__ == "__main__":
    run_async(_main())
