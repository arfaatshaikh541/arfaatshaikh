"""Conservative, cluster-wide rate limiting (state in PostgreSQL)."""
from __future__ import annotations

import datetime as dt
import random

from sqlalchemy import select

from .db import session_scope
from .lifecycle import sleep
from .models import RateLimitBucket, utcnow


class RateLimited(Exception):
    """The next permitted request is too far away to wait for inline; reschedule the work."""

    def __init__(self, key: str, wait_s: float):
        super().__init__(f"rate limit for {key}: next slot in {wait_s:.0f}s")
        self.wait_s = wait_s


def reserve_slot(key: str, min_interval_s: float, max_wait_s: float | None = None) -> float:
    """Reserve the next request slot for ``key``; returns seconds the caller must wait.

    If ``max_wait_s`` is given and the slot is further away, nothing is reserved and
    RateLimited is raised so the caller can defer instead of holding a worker.
    """
    with session_scope() as s:
        b = s.scalar(select(RateLimitBucket).where(RateLimitBucket.key == key).with_for_update())
        now = utcnow()
        if b is None:
            b = RateLimitBucket(key=key, next_allowed_at=now, backoff_seconds=0.0)
            s.add(b)
            s.flush()
        start = max(now, b.next_allowed_at)
        wait = max(0.0, (start - now).total_seconds())
        if max_wait_s is not None and wait > max_wait_s:
            raise RateLimited(key, wait)
        b.next_allowed_at = start + dt.timedelta(seconds=min_interval_s + b.backoff_seconds)
        return wait


def wait_for_slot(key: str, min_interval_s: float, max_inline_wait_s: float = 30) -> None:
    sleep(reserve_slot(key, min_interval_s, max_inline_wait_s))


def penalize(key: str, retry_after_s: float | None = None) -> None:
    """Called on 429/5xx: grow per-host backoff (capped) and push the next slot out."""
    with session_scope() as s:
        b = s.scalar(select(RateLimitBucket).where(RateLimitBucket.key == key).with_for_update())
        if b is None:
            return
        b.backoff_seconds = min(max(b.backoff_seconds * 2, 5.0), 900.0)
        delay = max(retry_after_s or 0, b.backoff_seconds)
        b.next_allowed_at = max(b.next_allowed_at, utcnow() + dt.timedelta(seconds=delay))


def relax(key: str) -> None:
    with session_scope() as s:
        b = s.scalar(select(RateLimitBucket).where(RateLimitBucket.key == key).with_for_update())
        if b is not None and b.backoff_seconds:
            b.backoff_seconds = max(0.0, b.backoff_seconds / 2 - 1)


def backoff_delay(attempt: int, base: float, cap: float = 3600) -> float:
    """Exponential backoff with full jitter."""
    return random.uniform(0, min(cap, base * (2 ** max(0, attempt - 1))))
