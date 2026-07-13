from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.routes import (
    appointments,
    assignment,
    auth,
    catalog,
    communication,
    health,
    invitations,
    leads,
    members,
    platform,
    public_enquiry,
    qualification,
    roles,
    scoring,
    tasks,
    tenants,
    workflows,
)
from app.core.config import get_settings
from app.core.cookies import CSRF_COOKIE, CSRF_HEADER, REFRESH_TOKEN_COOKIE, UNSAFE_METHODS
from app.core.logging import configure_logging
from app.core.security import constant_time_compare
from app.services.errors import ServiceError

# Endpoints exempt from the double-submit CSRF check because the cookie
# they read is itself the credential being presented for that specific
# action (login submits fresh credentials; refresh/logout act on the
# refresh_token cookie directly) rather than ambient authority being used
# to perform an unrelated state change on the user's behalf. Every other
# mutating, cookie-authenticated endpoint (settings, roles, members, etc.)
# stays protected.
_CSRF_EXEMPT_PATHS = frozenset(
    {
        "/api/auth/login",
        "/api/auth/refresh",
        "/api/auth/logout",
        "/api/auth/forgot-password",
        "/api/auth/reset-password",
        "/api/auth/verify-email",
        "/api/invitations/accept",
    }
)

# The public enquiry form is designed to be embedded on arbitrary external
# websites (Module 15) and never relies on ambient tenant-app cookies for
# authorization - it's unauthenticated by design and protected instead by
# honeypot/rate-limiting/idempotency (see public_enquiry_service.py), so
# CSRF's double-submit check would only break legitimate cross-site embeds.
_CSRF_EXEMPT_PREFIXES = ("/api/public/",)


class CSRFMiddleware(BaseHTTPMiddleware):
    """Double-submit-cookie CSRF protection for cookie-authenticated mutating
    requests. See docs/architecture/authentication-strategy.md."""

    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        if (
            request.method in UNSAFE_METHODS
            and REFRESH_TOKEN_COOKIE in request.cookies
            and request.url.path not in _CSRF_EXEMPT_PATHS
            and not request.url.path.startswith(_CSRF_EXEMPT_PREFIXES)
        ):
            cookie_token = request.cookies.get(CSRF_COOKIE)
            header_token = request.headers.get(CSRF_HEADER)
            if (
                not cookie_token
                or not header_token
                or not constant_time_compare(cookie_token, header_token)
            ):
                return JSONResponse(status_code=403, content={"detail": "CSRF validation failed."})
        return await call_next(request)


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging()

    docs_enabled = settings.environment in ("local", "test")
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url="/api/docs" if docs_enabled else None,
        redoc_url="/api/redoc" if docs_enabled else None,
        openapi_url="/api/openapi.json" if docs_enabled else None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Content-Type",
            "Authorization",
            CSRF_HEADER,
            "X-Tenant-Id",
            "Idempotency-Key",
        ],
    )
    app.add_middleware(CSRFMiddleware)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):  # type: ignore[no-untyped-def]
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if settings.environment not in ("local", "test"):
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        return response

    @app.exception_handler(ServiceError)
    async def handle_service_error(request: Request, exc: ServiceError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})

    api = settings.api_prefix
    app.include_router(health.router, prefix=api)
    app.include_router(auth.router, prefix=api)
    app.include_router(tenants.router, prefix=api)
    app.include_router(roles.router, prefix=api)
    app.include_router(members.router, prefix=api)
    app.include_router(invitations.tenant_router, prefix=api)
    app.include_router(invitations.public_router, prefix=api)
    app.include_router(platform.router, prefix=api)
    app.include_router(catalog.router, prefix=api)
    app.include_router(qualification.router, prefix=api)
    app.include_router(leads.router, prefix=api)
    app.include_router(public_enquiry.router, prefix=api)
    app.include_router(scoring.router, prefix=api)
    app.include_router(assignment.router, prefix=api)
    app.include_router(tasks.router, prefix=api)
    app.include_router(tasks.task_types_router, prefix=api)
    app.include_router(communication.templates_router, prefix=api)
    app.include_router(communication.notifications_router, prefix=api)
    app.include_router(appointments.router, prefix=api)
    app.include_router(workflows.router, prefix=api)

    return app


app = create_app()
