"""Redis-backed fixed-window rate limiting for sensitive endpoints
(login, password reset, invitation acceptance)."""

from redis.asyncio import Redis

from app.core.config import get_settings
from app.core.exceptions import RateLimitedError

_redis: Redis | None = None


def get_redis() -> Redis:
    global _redis
    if _redis is None:
        settings = get_settings()
        _redis = Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis


async def reset_redis_connection() -> None:
    """Closes and forgets the cached client so the next `get_redis()` call
    opens a fresh connection bound to the caller's current event loop.

    redis-py's asyncio connections are bound to the event loop that opened
    them, just like asyncpg's are (see `app.core.db`). The API serves every
    request on one long-lived loop, so this is never called there. The
    worker starts a brand new loop per Celery task invocation (see
    `worker.async_utils.run_db_task`), so it must call this after every task
    or the next task's loop inherits a connection tied to a closed one.
    """
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None


async def enforce_rate_limit(key: str, max_attempts: int, window_seconds: int) -> None:
    """Raises RateLimitedError if `key` has been hit more than `max_attempts`
    times within `window_seconds`. Uses a simple INCR + EXPIRE fixed window,
    which is sufficient for abuse throttling on auth endpoints."""
    redis = get_redis()
    current = await redis.incr(key)
    if current == 1:
        await redis.expire(key, window_seconds)
    if current > max_attempts:
        raise RateLimitedError("Too many attempts. Please try again later.")
