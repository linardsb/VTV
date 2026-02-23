"""Unit tests for custom exceptions and exception handlers."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import Request, status
from fastapi.responses import JSONResponse

from app.auth.exceptions import AccountLockedError, InvalidCredentialsError
from app.core.exceptions import (
    AppError,
    DomainValidationError,
    NotFoundError,
    account_locked_handler,
    app_exception_handler,
    invalid_credentials_handler,
    setup_exception_handlers,
)


def test_database_error_is_exception():
    """Test that AppError is properly defined and can be raised."""
    with pytest.raises(AppError):
        raise AppError("Test error")


def test_not_found_error_inherits_from_database_error():
    """Test that NotFoundError inherits from AppError."""
    assert issubclass(NotFoundError, AppError)

    with pytest.raises(NotFoundError):
        raise NotFoundError("Resource not found")

    # Verify it can also be caught as AppError
    with pytest.raises(AppError):
        raise NotFoundError("Resource not found")


def test_validation_error_inherits_from_database_error():
    """Test that DomainValidationError inherits from AppError."""
    assert issubclass(DomainValidationError, AppError)

    with pytest.raises(DomainValidationError):
        raise DomainValidationError("Validation failed")

    # Verify it can also be caught as AppError
    with pytest.raises(AppError):
        raise DomainValidationError("Validation failed")


@pytest.mark.asyncio
async def test_app_exception_handler_logs_and_returns_json():
    """Test that the exception handler logs errors and returns proper JSON."""
    # Create a mock request
    mock_request = MagicMock(spec=Request)
    mock_request.url.path = "/test/path"
    mock_request.method = "GET"

    # Create an exception
    exc = AppError("Test database error")

    # Patch the logger to verify it's called
    with patch("app.core.exceptions.logger.error") as mock_logger:
        # Call the handler
        response = await app_exception_handler(mock_request, exc)

        # Verify logger was called with exc_info=True
        mock_logger.assert_called_once()
        call_kwargs = mock_logger.call_args[1]
        assert call_kwargs["exc_info"] is True
        assert "error_type" in call_kwargs["extra"]
        assert "error_message" in call_kwargs["extra"]

    # Verify response
    assert isinstance(response, JSONResponse)
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert response.body is not None


@pytest.mark.asyncio
async def test_app_exception_handler_returns_404_for_not_found():
    """Test that NotFoundError returns 404 status code."""
    mock_request = MagicMock(spec=Request)
    mock_request.url.path = "/test/path"
    mock_request.method = "GET"

    exc = NotFoundError("Resource not found")

    with patch("app.core.exceptions.logger.error"):
        response = await app_exception_handler(mock_request, exc)

    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_app_exception_handler_returns_422_for_validation():
    """Test that DomainValidationError returns 422 status code."""
    mock_request = MagicMock(spec=Request)
    mock_request.url.path = "/test/path"
    mock_request.method = "GET"

    exc = DomainValidationError("Validation failed")

    with patch("app.core.exceptions.logger.error"):
        response = await app_exception_handler(mock_request, exc)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


@pytest.mark.asyncio
async def test_invalid_credentials_handler_returns_401():
    """Test that invalid_credentials_handler returns 401 with correct body."""
    mock_request = MagicMock(spec=Request)
    mock_request.url.path = "/api/v1/auth/login"
    mock_request.method = "POST"

    exc = InvalidCredentialsError("Invalid email or password")

    with patch("app.core.exceptions.logger.warning") as mock_logger:
        response = await invalid_credentials_handler(mock_request, exc)

        mock_logger.assert_called_once_with(
            "auth.invalid_credentials",
            extra={"path": "/api/v1/auth/login", "method": "POST"},
        )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert isinstance(response, JSONResponse)


@pytest.mark.asyncio
async def test_account_locked_handler_returns_423():
    """Test that account_locked_handler returns 423 with correct body."""
    mock_request = MagicMock(spec=Request)
    mock_request.url.path = "/api/v1/auth/login"
    mock_request.method = "POST"

    exc = AccountLockedError("Account is temporarily locked")

    with patch("app.core.exceptions.logger.warning") as mock_logger:
        response = await account_locked_handler(mock_request, exc)

        mock_logger.assert_called_once_with(
            "auth.account_locked",
            extra={"path": "/api/v1/auth/login", "method": "POST"},
        )

    assert response.status_code == status.HTTP_423_LOCKED
    assert isinstance(response, JSONResponse)


def test_setup_exception_handlers_registers_handlers():
    """Test that setup_exception_handlers registers all exception handlers."""
    # Create a mock FastAPI app
    mock_app = MagicMock()

    # Call setup function
    setup_exception_handlers(mock_app)

    # Verify add_exception_handler was called for each exception type
    assert mock_app.add_exception_handler.call_count == 5

    # Verify the exception types that were registered
    call_args_list = [call[0][0] for call in mock_app.add_exception_handler.call_args_list]
    assert AppError in call_args_list
    assert NotFoundError in call_args_list
    assert DomainValidationError in call_args_list
    assert InvalidCredentialsError in call_args_list
    assert AccountLockedError in call_args_list
