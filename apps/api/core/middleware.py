from __future__ import annotations

import redis.asyncio as redis_asyncio
from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware

from core.config import Settings, settings
from core.errors import RateLimitError


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
        # Milestone 29 (finding H-02): sent unconditionally, in every
        # environment. Browsers only ever honour Strict-Transport-Security
        # when it arrives over an actual HTTPS connection, so this is inert
        # (not misleading) over the plain-HTTP connections local dev and the
        # test suite use — the previous state was that no HSTS header
        # existed at all, leaving a real TLS deployment with zero downgrade
        # protection unless a reverse proxy happened to add one.
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'none'; frame-ancestors 'none'",
        )
        return response


class RedisRateLimiter:
    """Multi-instance-safe rate limiter for auth endpoints, backed by
    Redis's INCR + EXPIRE per window — the exact swap this class's
    single-process predecessor (`InMemorySlidingWindowLimiter`, replaced
    in Milestone 23) named as its own intended replacement, down to the
    technique. This is a fixed-window counter, not a true sliding window
    like the predecessor: a client could in principle get up to `2 *
    limit` requests through across a window boundary. That tradeoff is
    deliberate — INCR + EXPIRE needs no Lua scripting or sorted-set
    bookkeeping to reason about, and is the standard, well-understood
    building block for this in Redis. Documented explicitly in
    docs/project-status.md rather than left implicit."""

    def __init__(self, redis_client: redis_asyncio.Redis) -> None:
        self._redis = redis_client

    async def check(self, key: str, *, limit: int, window_seconds: int) -> None:
        redis_key = f"ratelimit:{key}"
        count = await self._redis.incr(redis_key)
        if count == 1:
            await self._redis.expire(redis_key, window_seconds)
        if count > limit:
            raise RateLimitError("Too many attempts. Please wait before trying again.")

    async def reset_all(self) -> None:
        """Test-only: clears every rate-limiter key without touching any
        other Redis-backed state — Celery's broker/backend share this same
        Redis instance in dev/test, so this scans by the `ratelimit:`
        prefix rather than issuing a blanket `FLUSHDB`."""
        cursor = 0
        while True:
            cursor, keys = await self._redis.scan(cursor=cursor, match="ratelimit:*", count=200)
            if keys:
                await self._redis.delete(*keys)
            if cursor == 0:
                break


login_rate_limiter = RedisRateLimiter(redis_asyncio.Redis.from_url(settings.redis_url, decode_responses=True))


def install_middleware(app: FastAPI, settings: Settings) -> None:
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
        allow_headers=["Content-Type", "X-CSRF-Token"],
    )
