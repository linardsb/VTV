"""Feature-specific exceptions for driver management.

Inherits from core exceptions for automatic HTTP status code mapping:
- DriverNotFoundError -> 404
- DriverAlreadyExistsError -> 422
- DriverError -> 500
"""

from app.core.exceptions import AppError, DomainValidationError, NotFoundError


class DriverError(AppError):
    """Base exception for driver-related errors."""


class DriverNotFoundError(NotFoundError):
    """Raised when a driver is not found by ID."""


class DriverAlreadyExistsError(DomainValidationError):
    """Raised when creating a driver with a duplicate employee_number."""
