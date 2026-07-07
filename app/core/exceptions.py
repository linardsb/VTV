"""Custom exception classes and global exception handlers.

AppError hierarchy and HTTP status mapping (handled in `app_exception_handler`):

- ``AppError`` — base, maps to 500
- ``NotFoundError`` — 404
- ``ConflictError`` — 409
- ``GoneError`` — 410
- ``DomainValidationError`` — 422
- ``BadRequestError`` — 400 (semantic input error: invalid combination of
  values that parsed cleanly, e.g., ``date_from > date_to``)
- ``PayloadTooLargeError`` — 413 (per-route body size limits)
- ``UnsupportedMediaTypeError`` — 415 (rejected file type / content mismatch)
- ``ServiceUnavailableError`` — 503 (transient upstream dependency failure)
- ``RBACConfigurationError`` — 500 (programmer error: missing scope)

Auth-flow specific (separate handlers, not in the polymorphic chain):

- ``InvalidCredentialsError`` — 401 (login)
- ``AccountLockedError`` — 423
- ``InvalidAPIKeyError`` / ``APIKeyRevokedError`` — 401 (Public API)
- ``APIKeyRateLimitError`` — 429 (Public API)
"""

from typing import Any, cast

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.core.logging import get_logger

logger = get_logger(__name__)


# Custom exception classes
class AppError(Exception):
    """Base exception for all application errors."""

    pass


class NotFoundError(AppError):
    """Exception raised when a resource is not found."""

    pass


class DomainValidationError(AppError):
    """Exception raised when validation fails."""

    pass


class RBACConfigurationError(AppError):
    """Raised when a repository query is executed without required RBAC scope.

    This indicates a programming error - a route handler forgot to inject and
    pass RequestScope to a scoped repository method. Maps to HTTP 500.
    """

    pass


class ConflictError(AppError):
    """Raised when a request conflicts with current resource state.

    Examples: creating a resource whose unique key collides with an existing
    active row, attempting a state transition that contradicts the current
    state. Maps to HTTP 409 Conflict.
    """

    pass


class GoneError(AppError):
    """Raised when a resource exists historically but is no longer available.

    Distinct from ``NotFoundError`` (which means "never existed or unknown").
    Examples: an expired share link, a finalised job that has been purged.
    Maps to HTTP 410 Gone.
    """

    pass


class BadRequestError(AppError):
    """Raised for semantic input errors that parsed cleanly but are invalid.

    Distinct from ``DomainValidationError`` (which is for shape-level /
    Pydantic-level issues): use ``BadRequestError`` when the request body or
    query parameters parse successfully but the *combination* of values is
    rejected (e.g., ``date_from > date_to``, range > 90 days). Maps to HTTP
    400 Bad Request.
    """

    pass


class PayloadTooLargeError(AppError):
    """Raised when a request body exceeds a per-route size limit.

    The global ``BodySizeLimitMiddleware`` returns 413 directly for the
    100KB middleware ceiling; this exception is for per-route enforcement
    above that ceiling (e.g., 50MB knowledge upload, GTFS ZIP upload).
    Maps to HTTP 413 Request Entity Too Large.
    """

    pass


class UnsupportedMediaTypeError(AppError):
    """Raised when an upload's declared or detected media type is rejected.

    Used for unsupported file extensions and for magic-byte mismatches
    against the declared ``Content-Type``. Maps to HTTP 415 Unsupported
    Media Type.
    """

    pass


class ServiceUnavailableError(AppError):
    """Raised when a transient upstream dependency failure prevents serving.

    Examples: GTFS-RT poller has stale data, OpenTripPlanner timed out,
    LLM provider unreachable through the fallback chain. Maps to HTTP 503
    Service Unavailable.
    """

    pass


# Global exception handlers
async def app_exception_handler(request: Request, exc: AppError) -> JSONResponse:
    """Handle application exceptions globally.

    Args:
        request: The incoming request.
        exc: The application exception that was raised.

    Returns:
        JSONResponse with error details.
    """
    logger.error(
        "app.error",
        extra={
            "error_type": type(exc).__name__,
            "error_message": str(exc),
            "path": request.url.path,
            "method": request.method,
        },
        exc_info=True,
    )

    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    if isinstance(exc, NotFoundError):
        status_code = status.HTTP_404_NOT_FOUND
    elif isinstance(exc, ConflictError):
        status_code = status.HTTP_409_CONFLICT
    elif isinstance(exc, GoneError):
        status_code = status.HTTP_410_GONE
    elif isinstance(exc, DomainValidationError):
        status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    elif isinstance(exc, BadRequestError):
        status_code = status.HTTP_400_BAD_REQUEST
    elif isinstance(exc, PayloadTooLargeError):
        status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    elif isinstance(exc, UnsupportedMediaTypeError):
        status_code = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    elif isinstance(exc, ServiceUnavailableError):
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return JSONResponse(
        status_code=status_code,
        content={
            "error": str(exc),
            "type": type(exc).__name__,
        },
    )


async def invalid_credentials_handler(request: Request, exc: AppError) -> JSONResponse:
    """Handle invalid credentials with 401 Unauthorized.

    Args:
        request: The incoming request.
        exc: The credentials exception that was raised.

    Returns:
        JSONResponse with 401 status.
    """
    logger.warning(
        "auth.invalid_credentials",
        extra={"path": request.url.path, "method": request.method},
    )
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={
            "error": str(exc) or "Invalid email or password",
            "type": "InvalidCredentialsError",
        },
    )


async def account_locked_handler(request: Request, exc: AppError) -> JSONResponse:
    """Handle locked accounts with 423 Locked.

    Args:
        request: The incoming request.
        exc: The account locked exception that was raised.

    Returns:
        JSONResponse with 423 status.
    """
    logger.warning(
        "auth.account_locked",
        extra={"path": request.url.path, "method": request.method},
    )
    return JSONResponse(
        status_code=status.HTTP_423_LOCKED,
        content={
            "error": str(exc) or "Account is temporarily locked",
            "type": "AccountLockedError",
        },
    )


async def api_key_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Handle invalid/revoked API key with 401 Unauthorized.

    Args:
        request: The incoming request.
        exc: The API key exception that was raised.

    Returns:
        JSONResponse with 401 status and WWW-Authenticate header.
    """
    logger.warning(
        "public_api.auth_failed",
        extra={"path": request.url.path, "method": request.method},
    )
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={
            "error": str(exc) or "Invalid or missing API key",
            "type": type(exc).__name__,
        },
        headers={"WWW-Authenticate": "ApiKey"},
    )


async def rate_limit_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Handle per-key rate limit exceeded with 429 Too Many Requests.

    Args:
        request: The incoming request.
        exc: The rate limit exception that was raised.

    Returns:
        JSONResponse with 429 status and Retry-After header.
    """
    from app.public_api.exceptions import APIKeyRateLimitError

    retry_after = exc.retry_after if isinstance(exc, APIKeyRateLimitError) else 60
    logger.warning(
        "public_api.rate_limit_exceeded",
        extra={"path": request.url.path, "method": request.method, "retry_after": retry_after},
    )
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={
            "error": str(exc) or "Rate limit exceeded",
            "type": "APIKeyRateLimitError",
        },
        headers={"Retry-After": str(retry_after)},
    )


def setup_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers with the FastAPI application.

    Args:
        app: The FastAPI application instance.
    """
    # Lazy import to avoid circular dependency (auth.exceptions imports from core.exceptions)
    from app.auth.exceptions import AccountLockedError, InvalidCredentialsError

    # FastAPI's type system expects exception handlers with exact type signatures
    # matching each exception class. However, our app_exception_handler uses
    # polymorphism to handle AppError and all its subtypes (NotFoundError,
    # DomainValidationError) with a single implementation. This is a valid design pattern
    # that reduces code duplication. We use cast(Any, ...) to inform the type checker
    # that we're intentionally using polymorphic exception handling.
    handler: Any = cast(Any, app_exception_handler)

    app.add_exception_handler(AppError, handler)
    app.add_exception_handler(NotFoundError, handler)
    app.add_exception_handler(ConflictError, handler)
    app.add_exception_handler(GoneError, handler)
    app.add_exception_handler(DomainValidationError, handler)
    app.add_exception_handler(BadRequestError, handler)
    app.add_exception_handler(PayloadTooLargeError, handler)
    app.add_exception_handler(UnsupportedMediaTypeError, handler)
    app.add_exception_handler(ServiceUnavailableError, handler)

    # Auth-specific handlers (401, 423)
    app.add_exception_handler(InvalidCredentialsError, cast(Any, invalid_credentials_handler))
    app.add_exception_handler(AccountLockedError, cast(Any, account_locked_handler))

    # Public API handlers (401, 429)
    from app.public_api.exceptions import (
        APIKeyRateLimitError,
        APIKeyRevokedError,
        InvalidAPIKeyError,
    )

    app.add_exception_handler(InvalidAPIKeyError, cast(Any, api_key_error_handler))
    app.add_exception_handler(APIKeyRevokedError, cast(Any, api_key_error_handler))
    app.add_exception_handler(APIKeyRateLimitError, cast(Any, rate_limit_error_handler))
