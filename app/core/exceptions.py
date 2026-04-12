"""Custom exception classes and global exception handlers."""

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
    elif isinstance(exc, DomainValidationError):
        status_code = status.HTTP_422_UNPROCESSABLE_CONTENT

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
    app.add_exception_handler(DomainValidationError, handler)

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
