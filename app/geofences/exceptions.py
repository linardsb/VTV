"""Geofence-specific exceptions.

Exception -> HTTP mapping:
- GeofenceNotFoundError -> 404
- GeofenceEventNotFoundError -> 404
- GeofenceValidationError -> 422
- GeofenceError -> 500
"""

from app.core.exceptions import AppError, DomainValidationError, NotFoundError


class GeofenceError(AppError):
    """Base exception for geofence operations."""


class GeofenceNotFoundError(NotFoundError):
    """Raised when geofence not found by ID."""

    def __init__(self, geofence_id: int) -> None:
        super().__init__(f"Geofence '{geofence_id}' not found")


class GeofenceEventNotFoundError(NotFoundError):
    """Raised when geofence event not found by ID."""

    def __init__(self, event_id: int) -> None:
        super().__init__(f"Geofence event '{event_id}' not found")


class GeofenceValidationError(DomainValidationError):
    """Raised on geofence business logic validation failure."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
