"""Feature-specific exceptions for operational events.

Inherits from core exceptions for automatic HTTP status code mapping:
- EventNotFoundError -> 404
- EventError -> 500
"""

from app.core.exceptions import AppError, NotFoundError


class EventError(AppError):
    """Base exception for event-related errors."""


class EventNotFoundError(NotFoundError):
    """Raised when an operational event is not found by ID."""
