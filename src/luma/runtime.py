from __future__ import annotations

import asyncio
import sys
from collections.abc import Coroutine
from typing import Any


def configure_asyncio_policy() -> None:
    """Use the event loop required by async Psycopg on Windows.

    API, worker, CLI, and test entrypoints must call this before creating an event
    loop. Other platforms retain their default policy.
    """
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def run_async[ResultT](coroutine: Coroutine[Any, Any, ResultT]) -> ResultT:
    """Run async entrypoints on a Psycopg-compatible loop, including on Windows."""
    configure_asyncio_policy()
    if sys.platform == "win32":
        with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
            return runner.run(coroutine)
    return asyncio.run(coroutine)
