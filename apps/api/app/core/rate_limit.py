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
