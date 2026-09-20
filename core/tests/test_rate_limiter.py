from __future__ import annotations

from aura_core.governance.rate_limiter import RateLimiter


def test_allows_up_to_the_limit_then_blocks():
    limiter = RateLimiter(default_max_count=3, default_window_seconds=60)
    assert limiter.allow("email.send") is True
    assert limiter.allow("email.send") is True
    assert limiter.allow("email.send") is True
    assert limiter.allow("email.send") is False


def test_per_key_limits_are_independent():
    limiter = RateLimiter(default_max_count=1, default_window_seconds=60)
    assert limiter.allow("a") is True
    assert limiter.allow("b") is True  # different key, own budget
    assert limiter.allow("a") is False
    assert limiter.allow("b") is False


def test_explicit_limit_overrides_default():
    limiter = RateLimiter(default_max_count=1, default_window_seconds=60)
    limiter.set_limit("bulk.action", max_count=10, window_seconds=60)
    for _ in range(10):
        assert limiter.allow("bulk.action") is True
    assert limiter.allow("bulk.action") is False


def test_old_events_outside_the_window_are_forgotten():
    limiter = RateLimiter(default_max_count=1, default_window_seconds=0)
    assert limiter.allow("x") is True
    # window_seconds=0 means every prior event is immediately "outside the window"
    assert limiter.allow("x") is True
