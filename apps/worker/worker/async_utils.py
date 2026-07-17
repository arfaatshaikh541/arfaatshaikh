"""Helper for running async DB/Redis-backed coroutines from synchronous
Celery tasks.

Celery's prefork workers call `asyncio.run(...)` once per task invocation,
each time creating a brand new event loop. Both asyncpg (SQLAlchemy's async
engine) and redis-py's asyncio client bind their connections to the loop
that created them, but both clients are cached at module scope (an engine's
pool, `app.core.rate_limit`'s `_redis` singleton) across every task the
worker process runs. When a later task is handed a connection opened on an
earlier (now closed) loop, it raises "Future attached to a different loop"
or "Event loop is closed" and the task fails outright.

Prefork children process one task to completion before starting the next,
so tearing down both caches right after a task finishes is safe: the next
`asyncio.run()` call is guaranteed to open fresh connections on its own loop
instead of reusing ones tied to a dead loop.
"""

import asyncio
from collections.abc import Coroutine

from app.core.db import engine
from app.core.rate_limit import reset_redis_connection


def run_db_task[T](coro: Coroutine[object, object, T]) -> T:
    async def _wrapper() -> T:
        try:
            return await coro
        finally:
            await engine.dispose()
            await reset_redis_connection()

    return asyncio.run(_wrapper())
