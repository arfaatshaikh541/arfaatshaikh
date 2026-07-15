from fastapi import Request, Response

from app.core.config import get_settings
from app.core.errors import ForbiddenError, RateLimitedError
from app.core.rate_limit import global_rate_limit_key, is_rate_limited
from app.core.security import constant_time_equals, generate_opaque_token

settings = get_settings()

_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
_SESSION_COOKIE_NAMES = (settings.session_cookie_name, settings.portal_session_cookie_name)


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def set_csrf_cookie(response: Response) -> None:
    """Issued alongside every staff/portal session cookie (login and
    accept-invitation, both domains). Deliberately NOT `httponly` —
    frontend JS must be able to read it and mirror it into the
    `X-CSRF-Token` header on every mutating request, which is exactly
    what makes the double-submit check meaningful: a cross-site
    attacker's script cannot read this cookie's value (blocked by the
    browser's same-origin policy), so it cannot forge a matching header
    even for a request the browser does attach the cookie to."""
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=generate_opaque_token(),
        httponly=False,
        secure=settings.session_cookie_secure,
        samesite="lax",
        max_age=settings.session_absolute_ttl_hours * 3600,
        path="/",
    )


def clear_csrf_cookie(response: Response) -> None:
    response.delete_cookie(key=settings.csrf_cookie_name, path="/")


def enforce_global_rate_limit(request: Request) -> None:
    """A generous, IP-keyed backstop applied to every `/api/*` request
    (Milestone 10) — distinct from, and on top of, the tighter,
    action-specific throttles already in place for login and portal
    login. Defense in depth against basic request flooding from a
    single client, not a substitute for those endpoint-specific limits.
    """
    if not settings.global_rate_limit_enabled:
        return
    key = global_rate_limit_key(_client_ip(request))
    limited, retry_after = is_rate_limited(
        key, max_attempts=settings.global_rate_limit_max_attempts, window_seconds=settings.global_rate_limit_window_seconds
    )
    if limited:
        raise RateLimitedError(f"Too many requests. Try again in {retry_after} seconds.", code="rate_limited")


def enforce_csrf_protection(request: Request) -> None:
    """Double-submit CSRF protection for cookie-authenticated,
    state-changing requests (Milestone 10). `SameSite=Lax` on the
    session cookies already blocks the common cross-site form/fetch
    forgery case; this is an independent, defense-in-depth layer.

    Skipped entirely for safe (read-only) methods, and for any request
    that carries no staff/portal session cookie at all — which
    naturally exempts login, forgot-password, reset-password, and
    accept-invitation (no session exists yet when those are called)
    without needing to special-case them, while still protecting every
    mutation that does ride on an existing session, including logout.
    """
    if request.method in _SAFE_METHODS:
        return
    if not any(request.cookies.get(name) for name in _SESSION_COOKIE_NAMES):
        return

    cookie_token = request.cookies.get(settings.csrf_cookie_name)
    header_token = request.headers.get("x-csrf-token")
    if not cookie_token or not header_token or not constant_time_equals(cookie_token, header_token):
        raise ForbiddenError("Missing or invalid CSRF token.", code="csrf_token_invalid")
