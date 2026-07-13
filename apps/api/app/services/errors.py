class ServiceError(Exception):
    """Base class for service-layer errors that routes translate to HTTP responses."""

    status_code = 400

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFoundError(ServiceError):
    status_code = 404


class ForbiddenError(ServiceError):
    status_code = 403


class ConflictError(ServiceError):
    status_code = 409


class ValidationError(ServiceError):
    status_code = 422


class RateLimitedError(ServiceError):
    status_code = 429


class UnauthorizedError(ServiceError):
    status_code = 401
