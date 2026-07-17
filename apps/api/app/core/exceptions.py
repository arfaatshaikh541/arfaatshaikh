"""Structured application errors and their FastAPI exception handlers.

Every error returned to a client has the shape:
    {"error": {"code": "...", "message": "...", "request_id": "..."}}

In production, unexpected exceptions never leak a stack trace or internal
message to the client - only a generic message plus the request_id a
support engineer can use to look up the real error in structured logs.
"""

import logging
import uuid

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import get_settings

logger = logging.getLogger("gridkeep.errors")


class AppError(Exception):
    """Base class for all application-raised, client-facing errors."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "app_error"

    def __init__(
        self, message: str, code: str | None = None, status_code: int | None = None
    ) -> None:
        self.message = message
        if code:
            self.code = code
        if status_code:
            self.status_code = status_code
        super().__init__(message)


class AuthenticationError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "authentication_required"


class InvalidCredentialsError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "invalid_credentials"


class SessionExpiredError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "session_expired"


class CSRFValidationError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "csrf_validation_failed"


class PermissionDeniedError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "permission_denied"


class TenantAccessDeniedError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "tenant_access_denied"


class TenantStatusError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "tenant_status_restricted"


class EntitlementDeniedError(AppError):
    status_code = status.HTTP_402_PAYMENT_REQUIRED
    code = "entitlement_denied"


class InsufficientCreditsError(AppError):
    status_code = status.HTTP_402_PAYMENT_REQUIRED
    code = "insufficient_credits"


class ResourceNotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "resource_not_found"


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"


class RateLimitedError(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "rate_limited"


class ValidationAppError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    code = "validation_error"


def _error_body(code: str, message: str, request_id: str) -> dict:
    return {"error": {"code": code, "message": message, "request_id": request_id}}


def register_exception_handlers(app: FastAPI) -> None:
    settings = get_settings()

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(exc.code, exc.message, request_id),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=_error_body("validation_error", "The request payload is invalid.", request_id),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body("http_error", str(exc.detail), request_id),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        logger.exception("Unhandled exception", extra={"request_id": request_id})
        message = str(exc) if not settings.is_production else "An unexpected error occurred."
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_body("internal_error", message, request_id),
        )
