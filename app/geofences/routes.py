# pyright: reportUnknownMemberType=false, reportUntypedFunctionDecorator=false
"""REST API routes for geofence zone management and event queries."""

import datetime

from fastapi import APIRouter, Depends, Query, status
from fastapi.requests import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, require_role
from app.auth.models import User
from app.core.database import get_db
from app.core.rate_limit import limiter
from app.geofences.schemas import (
    DwellTimeReport,
    GeofenceCreate,
    GeofenceEventResponse,
    GeofenceResponse,
    GeofenceUpdate,
)
from app.geofences.service import GeofenceService
from app.shared.schemas import PaginatedResponse, PaginationParams

router = APIRouter(prefix="/api/v1/geofences", tags=["geofences"])


def get_service(db: AsyncSession = Depends(get_db)) -> GeofenceService:  # noqa: B008
    """Dependency to create GeofenceService with request-scoped session."""
    return GeofenceService(db)


# --- Geofence CRUD ---


@router.get("/", response_model=PaginatedResponse[GeofenceResponse])
@limiter.limit("30/minute")
async def list_geofences(
    request: Request,
    pagination: PaginationParams = Depends(),  # noqa: B008
    search: str | None = Query(None, max_length=200),
    zone_type: str | None = Query(None),
    is_active: bool | None = Query(None),
    service: GeofenceService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(get_current_user),  # noqa: B008
) -> PaginatedResponse[GeofenceResponse]:
    """List geofences with pagination and optional filters."""
    _ = request
    return await service.list_geofences(
        pagination,
        search=search,
        zone_type=zone_type,
        is_active=is_active,
    )


@router.post(
    "/",
    response_model=GeofenceResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("10/minute")
async def create_geofence(
    request: Request,
    data: GeofenceCreate,
    service: GeofenceService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(require_role("admin", "editor")),  # noqa: B008
) -> GeofenceResponse:
    """Create a new geofence zone."""
    _ = request
    return await service.create_geofence(data)


# NOTE: /events must be defined BEFORE /{geofence_id} to avoid FastAPI
# treating "events" as a geofence_id path parameter.
@router.get("/events", response_model=PaginatedResponse[GeofenceEventResponse])
@limiter.limit("30/minute")
async def list_all_events(
    request: Request,
    pagination: PaginationParams = Depends(),  # noqa: B008
    vehicle_id: str | None = Query(None, max_length=100),
    event_type: str | None = Query(None),
    geofence_id: int | None = Query(None),
    start_time: datetime.datetime | None = Query(None),  # noqa: B008
    end_time: datetime.datetime | None = Query(None),  # noqa: B008
    service: GeofenceService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(get_current_user),  # noqa: B008
) -> PaginatedResponse[GeofenceEventResponse]:
    """List all geofence events with filters."""
    _ = request
    return await service.list_all_events(
        pagination,
        vehicle_id=vehicle_id,
        event_type=event_type,
        geofence_id=geofence_id,
        start_time=start_time,
        end_time=end_time,
    )


@router.get("/{geofence_id}", response_model=GeofenceResponse)
@limiter.limit("30/minute")
async def get_geofence(
    request: Request,
    geofence_id: int,
    service: GeofenceService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(get_current_user),  # noqa: B008
) -> GeofenceResponse:
    """Get a geofence by database ID."""
    _ = request
    return await service.get_geofence(geofence_id)


@router.patch("/{geofence_id}", response_model=GeofenceResponse)
@limiter.limit("10/minute")
async def update_geofence(
    request: Request,
    geofence_id: int,
    data: GeofenceUpdate,
    service: GeofenceService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(require_role("admin", "editor")),  # noqa: B008
) -> GeofenceResponse:
    """Update an existing geofence zone."""
    _ = request
    return await service.update_geofence(geofence_id, data)


@router.delete("/{geofence_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
async def delete_geofence(
    request: Request,
    geofence_id: int,
    service: GeofenceService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(require_role("admin")),  # noqa: B008
) -> None:
    """Delete a geofence zone by database ID."""
    _ = request
    await service.delete_geofence(geofence_id)


@router.get("/{geofence_id}/events", response_model=PaginatedResponse[GeofenceEventResponse])
@limiter.limit("30/minute")
async def list_geofence_events(
    request: Request,
    geofence_id: int,
    pagination: PaginationParams = Depends(),  # noqa: B008
    event_type: str | None = Query(None),
    start_time: datetime.datetime | None = Query(None),  # noqa: B008
    end_time: datetime.datetime | None = Query(None),  # noqa: B008
    service: GeofenceService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(get_current_user),  # noqa: B008
) -> PaginatedResponse[GeofenceEventResponse]:
    """List events for a specific geofence."""
    _ = request
    return await service.list_events_by_geofence(
        geofence_id,
        pagination,
        event_type=event_type,
        start_time=start_time,
        end_time=end_time,
    )


@router.get("/{geofence_id}/dwell-report", response_model=DwellTimeReport)
@limiter.limit("30/minute")
async def get_dwell_report(
    request: Request,
    geofence_id: int,
    start_time: datetime.datetime | None = Query(None),  # noqa: B008
    end_time: datetime.datetime | None = Query(None),  # noqa: B008
    service: GeofenceService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(get_current_user),  # noqa: B008
) -> DwellTimeReport:
    """Get dwell time statistics for a geofence."""
    _ = request
    return await service.get_dwell_report(geofence_id, start_time, end_time)
