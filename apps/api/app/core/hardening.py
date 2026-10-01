"""Defence-in-depth HTTP hardening that does not depend on the reverse proxy being configured correctly."""
from __future__ import annotations

import structlog
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

MAX_BODY_BYTES = 12 * 1024 * 1024  # largest accepted request body (dataset uploads are capped at 5,000 records)
NO_STORE_PREFIXES = ("/api/v1/auth", "/api/v1/admin", "/api/v1/directory/admin", "/api/v1/assistant", "/api/v1/quran/me", "/api/v1/hadith/me", "/api/v1/tafsir/me")

logger = structlog.get_logger()


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        length = request.headers.get("content-length")
        if length and length.isdigit() and int(length) > MAX_BODY_BYTES:
            return JSONResponse({"error": {"code": "payload_too_large", "message": "The request body is too large.", "details": {}}}, status_code=413)
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Cross-Origin-Resource-Policy", "same-site")
        if request.url.path.startswith(NO_STORE_PREFIXES):
            response.headers["Cache-Control"] = "no-store"
        return response


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Never leak a stack trace or internal message; the request id lets an operator find the log entry."""
    request_id = getattr(request.state, "request_id", None)
    logger.error("unhandled_exception", path=request.url.path, error_type=type(exc).__name__, request_id=request_id)
    return JSONResponse({"error": {"code": "internal_error", "message": "Something went wrong. Please try again.", "details": {"request_id": request_id}}}, status_code=500)
