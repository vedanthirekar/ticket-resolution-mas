from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer


def psycopg_connection_url(sqlalchemy_url: str) -> str:
    return sqlalchemy_url.replace("postgresql+psycopg://", "postgresql://", 1)


@asynccontextmanager
async def postgres_checkpointer(
    database_url: str, *, setup: bool = False
) -> AsyncIterator[AsyncPostgresSaver]:
    serializer = JsonPlusSerializer(pickle_fallback=False, allowed_msgpack_modules=())
    async with AsyncPostgresSaver.from_conn_string(
        psycopg_connection_url(database_url), serde=serializer
    ) as saver:
        if setup:
            await saver.setup()
        yield saver
