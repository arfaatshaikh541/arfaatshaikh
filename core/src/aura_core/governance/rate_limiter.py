"""In-process sliding-window rate limiter. Resets on restart — a known,
documented limitation (see docs/project-status.md) rather than a silent
gap; acceptable for single-process, single-owner scale today. Guards
against a runaway/compromised caller submitting unboundedly many actions
of one type, per docs/security/README.md#network-security.
"""
from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone


class RateLimiter:
    def __init__(self, default_max_count: int = 100, default_window_seconds: int = 60) -> None:
        self._default_max = default_max_count
        self._default_window = default_window_seconds
        self._limits: dict[str, tuple[int, int]] = {}
        self._events: dict[str, deque] = defaultdict(deque)

    def set_limit(self, key: str, max_count: int, window_seconds: int) -> None:
        self._limits[key] = (max_count, window_seconds)

    def allow(self, key: str) -> bool:
        max_count, window_seconds = self._limits.get(key, (self._default_max, self._default_window))
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(seconds=window_seconds)
        events = self._events[key]
        while events and events[0] < window_start:
            events.popleft()
        if len(events) >= max_count:
            return False
        events.append(now)
        return True
