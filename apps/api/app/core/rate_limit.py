import time

import redis

from app.core.config import get_settings

settings = get_settings()
_redis_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.Redis.from_url(settings.rate_limit_redis_url, decode_responses=True)
    return _redis_client


def is_rate_limited(key: str, *, max_attempts: int, window_seconds: int) -> tuple[bool, int]:
    """Fixed-window counter with per-key TTL.

    Returns (is_limited, seconds_until_reset). Uses a Lua-free
    INCR + EXPIRE pair; the small race between INCR and EXPIRE on first
    write only risks a slightly longer window, never a bypass, which is
    an acceptable trade-off for login throttling.
    """
    client = get_redis()
    current = client.incr(key)
    if current == 1:
        client.expire(key, window_seconds)
    ttl = client.ttl(key)
    ttl = ttl if ttl and ttl > 0 else window_seconds
    return current > max_attempts, ttl


def reset_rate_limit(key: str) -> None:
    get_redis().delete(key)


def login_throttle_key(email: str, ip_address: str) -> str:
    return f"throttle:login:{email.lower()}:{ip_address}"


def global_rate_limit_key(ip_address: str) -> str:
    return f"throttle:global:{ip_address}"


def record_attempt_timestamp(key: str) -> None:
    get_redis().set(f"{key}:last", int(time.time()), ex=3600)
