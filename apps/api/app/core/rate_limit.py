from __future__ import annotations

from fastapi import Request
from redis.asyncio import Redis

from app.core.config import get_settings
from app.core.errors import ApplicationError


class RateLimiter:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.redis = Redis.from_url(self.settings.redis_url, decode_responses=True)

    async def check(self, request: Request, scope: str, limit: int, window_seconds: int) -> None:
        client_ip = request.client.host if request.client else "unknown"
        key = f"rate:{scope}:{client_ip}"
        try:
            current = await self.redis.incr(key)
            if current == 1:
                await self.redis.expire(key, window_seconds)
        except Exception as exc:
            if self.settings.environment == "production":
                raise ApplicationError("rate_limit_unavailable", "Request cannot be processed safely.", 503) from exc
            return
        if current > limit:
            raise ApplicationError("rate_limit_exceeded", "Too many requests. Try again later.", 429)

    async def close(self) -> None:
        await self.redis.aclose()


rate_limiter = RateLimiter()
