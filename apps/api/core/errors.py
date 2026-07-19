from __future__ import annotations

from typing import Any

import structlog
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = structlog.get_logger("gridkeep.errors")


class AppError(Exception):
    """Base of GRIDKEEP's structured error model. Every deliberately-raised
    error carries a stable machine-readable `code`, a user-safe `message`
    (never a stack trace or internal detail), and an HTTP status."""

    code: str = "internal_error"
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        self.message = message
        self.details = details or {}
        super().__init__(message)


class NotFoundError(AppError):
    code = "not_found"
    status_code = status.HTTP_404_NOT_FOUND


class ValidationAppError(AppError):
    code = "validation_error"
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY


class AuthenticationError(AppError):
    code = "authentication_required"
    status_code = status.HTTP_401_UNAUTHORIZED


class InvalidCredentialsError(AuthenticationError):
    code = "invalid_credentials"


class AuthorizationError(AppError):
    code = "forbidden"
    status_code = status.HTTP_403_FORBIDDEN


class TenantStatusError(AppError):
    code = "tenant_status_blocked"
    status_code = status.HTTP_403_FORBIDDEN


class MfaEnrollmentRequiredError(AppError):
    code = "mfa_enrollment_required"
    status_code = status.HTTP_403_FORBIDDEN


class EntitlementError(AppError):
    code = "entitlement_required"
    status_code = status.HTTP_402_PAYMENT_REQUIRED


class ApprovalRequiredError(AppError):
    code = "approval_required"
    status_code = status.HTTP_202_ACCEPTED


class RateLimitError(AppError):
    code = "rate_limited"
    status_code = status.HTTP_429_TOO_MANY_REQUESTS


class ConflictError(AppError):
    code = "conflict"
    status_code = status.HTTP_409_CONFLICT


class VaultUnavailableError(AppError):
    """Hardening-programme Milestone 5 (finding C-02): the production
    credential-vault adapter talks to an external service (HashiCorp
    Vault's Transit engine) over the network — unlike the local adapter's
    in-process key derivation, that call can fail for reasons entirely
    outside the request itself (Vault sealed, unreachable, misconfigured
    token). 503 signals "retry later," not "this request was invalid."""

    code = "vault_unavailable"
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE


def _envelope(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details or {}}}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        if exc.status_code >= 500:
            logger.error("app_error", code=exc.code, path=request.url.path)
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_envelope(
                "validation_error",
                "The request was invalid.",
                {"fields": exc.errors()},
            ),
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        # Never leak internal stack traces or exception messages to clients.
        logger.error("unhandled_exception", path=request.url.path, exc_info=exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_envelope("internal_error", "An unexpected error occurred."),
        )
