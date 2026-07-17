"""Session and CSRF cookie helpers.

Session cookie: HttpOnly (never readable by JS), Secure in production,
SameSite=Lax (sent on same-site cross-origin requests such as
localhost:3000 -> localhost:8000, withheld on genuine cross-site
requests, which is what makes it a CSRF mitigation in its own right - the
double-submit token below is the second, independent layer).

CSRF cookie: deliberately NOT HttpOnly - the frontend reads it and echoes
it back in the `X-CSRF-Token` header on mutating requests, and
`app.dependencies.verify_csrf` checks the two match.
"""

from fastapi import Response

from app.core.config import get_settings
from app.core.security import generate_opaque_token


def set_session_cookie(response: Response, raw_token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.session_cookie_name,
        value=raw_token,
        max_age=settings.session_ttl_hours * 3600,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )
    # Issue (or re-issue) the CSRF token alongside the session.
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=generate_opaque_token(16),
        max_age=settings.session_ttl_hours * 3600,
        httponly=False,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(settings.session_cookie_name, path="/")
    response.delete_cookie(settings.csrf_cookie_name, path="/")
