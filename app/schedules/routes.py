# pyright: reportUnknownMemberType=false, reportUntypedFunctionDecorator=false
"""REST API routes for schedule management."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from fastapi.requests import Request
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, require_role
from app.auth.models import User
from app.core.database import get_db
from app.core.rate_limit import limiter
from app.schedules.schemas import (
    AgencyCreate,
    AgencyResponse,
    CalendarCreate,
    CalendarDateCreate,
    CalendarDateResponse,
    CalendarResponse,
    CalendarUpdate,
    GTFSImportResponse,
    RouteCreate,
    RouteResponse,
    RouteUpdate,
    StopTimeResponse,
    StopTimesBulkUpdate,
    TripCreate,
    TripDetailResponse,
    TripResponse,
    TripUpdate,
    ValidationResult,
)
from app.schedules.service import ScheduleService
from app.shared.schemas import PaginatedResponse, PaginationParams

# Maximum GTFS ZIP upload size (matches nginx client_max_body_size for /api/v1/schedules/import)
MAX_GTFS_UPLOAD_BYTES = 10 * 1024 * 1024  # 10MB

router = APIRouter(prefix="/api/v1/schedules", tags=["schedules"])


def get_service(db: AsyncSession = Depends(get_db)) -> ScheduleService:  # noqa: B008
    """Dependency to create ScheduleService with request-scoped session."""
    return ScheduleService(db)


# --- Agency endpoints ---


@router.get("/agencies", response_model=list[AgencyResponse])
@limiter.limit("30/minute")
async def list_agencies(
    request: Request,
    feed_id: str | None = Query(None, max_length=50),
    service: ScheduleService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(get_current_user),  # noqa: B008
) -> list[AgencyResponse]:
    """List all transit agencies."""
    _ = request
    return await service.list_agencies(feed_id=feed_id)


@router.post("/agencies", response_model=AgencyResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def create_agency(
    request: Request,
    data: AgencyCreate,
    service: ScheduleService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(require_role("admin", "editor")),  # noqa: B008
) -> AgencyResponse:
    """Create a new transit agency."""
    _ = request
    return await service.create_agency(data)


# --- Route endpoints ---


@router.get("/routes", response_model=PaginatedResponse[RouteResponse])
@limiter.limit("30/minute")
async def list_routes(
    request: Request,
    pagination: PaginationParams = Depends(),  # noqa: B008
    search: str | None = Query(None, max_length=200),
    route_type: int | None = Query(None, ge=0),
    agency_id: int | None = Query(None),
    is_active: bool | None = Query(None),
    feed_id: str | None = Query(None, max_length=50),
    service: ScheduleService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(get_current_user),  # noqa: B008
) -> PaginatedResponse[RouteResponse]:
    """List routes with pagination and filtering."""
    _ = request
    return await service.list_routes(
        pagination,
        search=search,
        route_type=route_type,
        agency_id=agency_id,
        is_active=is_active,
        feed_id=feed_id,
    )


@router.post("/routes", response_model=RouteResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def create_route(
    request: Request,
    data: RouteCreate,
    service: ScheduleService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(require_role("admin", "editor")),  # noqa: B008
) -> RouteResponse:
    """Create a new route."""
    _ = request
    return await service.create_route(data)


@router.get("/routes/{route_id}", response_model=RouteResponse)
@limiter.limit("30/minute")
async def get_route(
    request: Request,
    route_id: int,
    service: ScheduleService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(get_current_user),  # noqa: B008
) -> RouteResponse:
    """Get a route by its database ID."""
    _ = request
    return await service.get_route(route_id)


@router.patch("/routes/{route_id}", response_model=RouteResponse)
@limiter.limit("10/minute")
async def update_route(
    request: Request,
    route_id: int,
    data: RouteUpdate,
    service: ScheduleService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(require_role("admin", "editor")),  # noqa: B008
) -> RouteResponse:
    """Update an existing route."""
    _ = request
    return await service.update_route(route_id, data)


@router.delete("/routes/{route_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
async def delete_route(
    request: Request,
    route_id: int,
    service: ScheduleService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(require_role("admin", "editor")),  # noqa: B008
) -> None:
    """Delete a route by its database ID."""
    _ = request
    await service.delete_route(route_id)


# --- Calendar endpoints ---


@router.get("/calendars", response_model=PaginatedResponse[CalendarResponse])
@limiter.limit("30/minute")
async def list_calendars(
    request: Request,
    pagination: PaginationParams = Depends(),  # noqa: B008
    active_on: date | None = Query(None),  # noqa: B008
    service: ScheduleService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(get_current_user),  # noqa: B008
) -> PaginatedResponse[CalendarResponse]:
    """List service calendars with pagination."""
    _ = request
    return await service.list_calendars(pagination, active_on=active_on)


@router.post("/calendars", response_model=CalendarResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def create_calendar(
    request: Request,
    data: CalendarCreate,
    service: ScheduleService = Depends(get_service),  # noqa: B008
    current_user: User = Depends(require_role("admin", "editor")),  # noqa: B008
) -> CalendarResponse:
    """Create a new service calendar."""
    _ = request
    return await service.create_calendar(data, user_id=current_user.id)


@router.get("/calendars/{calendar_id}", response_model=CalendarResponse)
@limiter.limit("30/minute")
async def get_calendar(
    request: Request,
    calendar_id: int,
    service: ScheduleService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(get_current_user),  # noqa: B008
) -> CalendarResponse:
    """Get a service calendar by ID."""
    _ = request
    return await service.get_calendar(calendar_id)


@router.patch("/calendars/{calendar_id}", response_model=CalendarResponse)
@limiter.limit("10/minute")
async def update_calendar(
    request: Request,
    calendar_id: int,
    data: CalendarUpdate,
    service: ScheduleService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(require_role("admin", "editor")),  # noqa: B008
) -> CalendarResponse:
    """Update an existing service calendar."""
    _ = request
    return await service.update_calendar(calendar_id, data)


@router.delete("/calendars/{calendar_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
async def delete_calendar(
    request: Request,
    calendar_id: int,
    service: ScheduleService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(require_role("admin", "editor")),  # noqa: B008
) -> None:
    """Delete a service calendar."""
    _ = request
    await service.delete_calendar(calendar_id)


@router.post(
    "/calendars/{calendar_id}/exceptions",
    response_model=CalendarDateResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("10/minute")
async def add_calendar_exception(
    request: Request,
    calendar_id: int,
    data: CalendarDateCreate,
    service: ScheduleService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(require_role("admin", "editor")),  # noqa: B008
) -> CalendarDateResponse:
    """Add a date exception to a service calendar."""
    _ = request
    return await service.add_calendar_exception(calendar_id, data)


@router.delete("/calendar-exceptions/{exception_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
async def remove_calendar_exception(
    request: Request,
    exception_id: int,
    service: ScheduleService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(require_role("admin", "editor")),  # noqa: B008
) -> None:
    """Remove a calendar date exception."""
    _ = request
    await service.remove_calendar_exception(exception_id)


# --- Trip endpoints ---


@router.get("/trips", response_model=PaginatedResponse[TripResponse])
@limiter.limit("30/minute")
async def list_trips(
    request: Request,
    pagination: PaginationParams = Depends(),  # noqa: B008
    route_id: int | None = Query(None),
    calendar_id: int | None = Query(None),
    direction_id: int | None = Query(None, ge=0, le=1),
    service: ScheduleService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(get_current_user),  # noqa: B008
) -> PaginatedResponse[TripResponse]:
    """List trips with pagination and filtering."""
    _ = request
    return await service.list_trips(
        pagination, route_id=route_id, calendar_id=calendar_id, direction_id=direction_id
    )


@router.post("/trips", response_model=TripResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def create_trip(
    request: Request,
    data: TripCreate,
    service: ScheduleService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(require_role("admin", "editor")),  # noqa: B008
) -> TripResponse:
    """Create a new trip."""
    _ = request
    return await service.create_trip(data)


@router.get("/trips/{trip_id}", response_model=TripDetailResponse)
@limiter.limit("30/minute")
async def get_trip(
    request: Request,
    trip_id: int,
    service: ScheduleService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(get_current_user),  # noqa: B008
) -> TripDetailResponse:
    """Get a trip by ID with its stop times."""
    _ = request
    return await service.get_trip(trip_id)


@router.patch("/trips/{trip_id}", response_model=TripResponse)
@limiter.limit("10/minute")
async def update_trip(
    request: Request,
    trip_id: int,
    data: TripUpdate,
    service: ScheduleService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(require_role("admin", "editor")),  # noqa: B008
) -> TripResponse:
    """Update an existing trip."""
    _ = request
    return await service.update_trip(trip_id, data)


@router.delete("/trips/{trip_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
async def delete_trip(
    request: Request,
    trip_id: int,
    service: ScheduleService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(require_role("admin", "editor")),  # noqa: B008
) -> None:
    """Delete a trip."""
    _ = request
    await service.delete_trip(trip_id)


@router.put("/trips/{trip_id}/stop-times", response_model=list[StopTimeResponse])
@limiter.limit("10/minute")
async def replace_stop_times(
    request: Request,
    trip_id: int,
    data: StopTimesBulkUpdate,
    service: ScheduleService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(require_role("admin", "editor")),  # noqa: B008
) -> list[StopTimeResponse]:
    """Replace all stop times for a trip."""
    _ = request
    return await service.replace_stop_times(trip_id, data)


# --- Import & Validation ---


@router.get("/export")
@limiter.limit("5/minute")
async def export_gtfs(
    request: Request,
    agency_id: int | None = Query(None),
    feed_id: str | None = Query(None, max_length=50),
    service: ScheduleService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(get_current_user),  # noqa: B008
) -> Response:
    """Export schedule data as a GTFS-compliant ZIP file."""
    _ = request
    zip_bytes = await service.export_gtfs(agency_id=agency_id, feed_id=feed_id)
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=gtfs.zip"},
    )


@router.post("/import", response_model=GTFSImportResponse)
@limiter.limit("5/minute")
async def import_gtfs(
    request: Request,
    file: UploadFile,
    feed_id: str = Query("riga", max_length=50),
    service: ScheduleService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(require_role("admin", "editor")),  # noqa: B008
) -> GTFSImportResponse:
    """Import schedule data from a GTFS ZIP file."""
    _ = request
    # Stream upload with size enforcement (defense-in-depth beyond nginx limit)
    chunks: list[bytes] = []
    total_size = 0
    while chunk := await file.read(8192):
        total_size += len(chunk)
        if total_size > MAX_GTFS_UPLOAD_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File exceeds {MAX_GTFS_UPLOAD_BYTES // (1024 * 1024)}MB upload limit",
            )
        chunks.append(chunk)
    zip_data = b"".join(chunks)
    return await service.import_gtfs(zip_data, feed_id=feed_id)


@router.post("/validate", response_model=ValidationResult)
@limiter.limit("5/minute")
async def validate_schedule(
    request: Request,
    service: ScheduleService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(get_current_user),  # noqa: B008
) -> ValidationResult:
    """Validate referential integrity of schedule data."""
    _ = request
    return await service.validate_schedule()
