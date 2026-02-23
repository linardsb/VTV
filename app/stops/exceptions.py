"""Feature-specific exceptions for stop management.

Inherits from core exceptions for automatic HTTP status code mapping:
- StopNotFoundError -> 404
- StopAlreadyExistsError -> 422
- StopError -> 500
"""

from app.core.exceptions import AppError, DomainValidationError, NotFoundError


class StopError(AppError):
    """Base exception for stop-related errors."""


class StopNotFoundError(NotFoundError):
    """Raised when a stop is not found by ID."""


class StopAlreadyExistsError(DomainValidationError):
    """Raised when creating a stop with a duplicate gtfs_stop_id."""
