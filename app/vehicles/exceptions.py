"""Feature-specific exceptions for vehicle management.

Inherits from core exceptions for automatic HTTP status code mapping:
- VehicleNotFoundError -> 404
- VehicleAlreadyExistsError -> 422
- DriverAssignmentError -> 422
- VehicleError -> 500
"""

from app.core.exceptions import AppError, DomainValidationError, NotFoundError


class VehicleError(AppError):
    """Base exception for vehicle-related errors."""


class VehicleNotFoundError(NotFoundError):
    """Raised when a vehicle is not found by ID."""

    def __init__(self, vehicle_id: int) -> None:
        super().__init__(f"Vehicle with id {vehicle_id} not found")


class VehicleAlreadyExistsError(DomainValidationError):
    """Raised when creating a vehicle with a duplicate fleet_number."""

    def __init__(self, fleet_number: str) -> None:
        super().__init__(f"Vehicle with fleet number '{fleet_number}' already exists")


class MaintenanceRecordNotFoundError(NotFoundError):
    """Raised when a maintenance record is not found by ID."""

    def __init__(self, record_id: int) -> None:
        super().__init__(f"Maintenance record with id {record_id} not found")


class DriverAssignmentError(DomainValidationError):
    """Raised when driver assignment validation fails."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
