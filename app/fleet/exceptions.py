"""Fleet-specific exceptions.

Exception -> HTTP mapping:
- DeviceNotFoundError -> 404
- DeviceAlreadyExistsError -> 422
- DeviceValidationError -> 422
- FleetError -> 500
- WebhookAuthError -> 401
"""

from app.core.exceptions import AppError, DomainValidationError, NotFoundError


class FleetError(AppError):
    """Base exception for fleet operations."""


class DeviceNotFoundError(NotFoundError):
    """Raised when tracked device not found by ID or IMEI."""

    def __init__(self, identifier: int | str) -> None:
        super().__init__(f"Tracked device '{identifier}' not found")


class DeviceAlreadyExistsError(DomainValidationError):
    """Raised when IMEI already registered."""

    def __init__(self, imei: str) -> None:
        super().__init__(f"Device with IMEI '{imei}' already exists")


class DeviceValidationError(DomainValidationError):
    """Raised on business logic validation failure."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class WebhookAuthError(AppError):
    """Raised when webhook token is invalid."""

    def __init__(self) -> None:
        super().__init__("Invalid webhook authentication token")
