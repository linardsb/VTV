"""Feature-specific exceptions for schedule management.

Inherits from core exceptions for automatic HTTP status code mapping:
- *NotFoundError -> 404
- *AlreadyExistsError / ScheduleValidationError -> 422
- ScheduleError / GTFSImportError -> 500
"""

from app.core.exceptions import AppError, NotFoundError, ValidationError


class ScheduleError(AppError):
    """Base exception for schedule-related errors."""


class AgencyNotFoundError(NotFoundError):
    """Raised when an agency is not found by ID."""


class AgencyAlreadyExistsError(ValidationError):
    """Raised when creating an agency with a duplicate gtfs_agency_id."""


class RouteNotFoundError(NotFoundError):
    """Raised when a route is not found by ID."""


class CalendarNotFoundError(NotFoundError):
    """Raised when a calendar is not found by ID."""


class TripNotFoundError(NotFoundError):
    """Raised when a trip is not found by ID."""


class StopTimeNotFoundError(NotFoundError):
    """Raised when a stop time is not found by ID."""


class CalendarDateNotFoundError(NotFoundError):
    """Raised when a calendar date exception is not found by ID."""


class RouteAlreadyExistsError(ValidationError):
    """Raised when creating a route with a duplicate gtfs_route_id."""


class CalendarAlreadyExistsError(ValidationError):
    """Raised when creating a calendar with a duplicate gtfs_service_id."""


class TripAlreadyExistsError(ValidationError):
    """Raised when creating a trip with a duplicate gtfs_trip_id."""


class ScheduleValidationError(ValidationError):
    """Raised when schedule data fails validation checks."""


class GTFSImportError(AppError):
    """Raised when GTFS import encounters a critical error."""
