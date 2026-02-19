# pyright: reportUnknownMemberType=false, reportUntypedFunctionDecorator=false
"""REST API routes for stop management."""

from fastapi import APIRouter, Depends, Query, status
from fastapi.requests import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.rate_limit import limiter
from app.shared.schemas import PaginatedResponse, PaginationParams
from app.stops.schemas import (
    StopCreate,
    StopNearbyParams,
    StopResponse,
    StopUpdate,
)
from app.stops.service import StopService

router = APIRouter(prefix="/api/v1/stops", tags=["stops"])


def get_service(db: AsyncSession = Depends(get_db)) -> StopService:  # noqa: B008
    """Dependency to create StopService with request-scoped session."""
    return StopService(db)


@router.get("/", response_model=PaginatedResponse[StopResponse])
@limiter.limit("30/minute")
async def list_stops(
    request: Request,
    pagination: PaginationParams = Depends(),  # noqa: B008
    search: str | None = Query(None, max_length=200),
    active_only: bool = Query(default=True),
    service: StopService = Depends(get_service),  # noqa: B008
) -> PaginatedResponse[StopResponse]:
    """List stops with pagination and optional search filter."""
    _ = request
    return await service.list_stops(pagination, search=search, active_only=active_only)


@router.get("/nearby", response_model=list[StopResponse])
@limiter.limit("30/minute")
async def nearby_stops(
    request: Request,
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    radius_meters: int = Query(500, ge=1, le=5000),
    limit: int = Query(20, ge=1, le=100),
    service: StopService = Depends(get_service),  # noqa: B008
) -> list[StopResponse]:
    """Find stops within a radius of a geographic point."""
    _ = request
    params = StopNearbyParams(latitude=latitude, longitude=longitude, radius_meters=radius_meters)
    return await service.search_nearby(params, limit=limit)


@router.get("/{stop_id}", response_model=StopResponse)
@limiter.limit("30/minute")
async def get_stop(
    request: Request,
    stop_id: int,
    service: StopService = Depends(get_service),  # noqa: B008
) -> StopResponse:
    """Get a stop by its database ID."""
    _ = request
    return await service.get_stop(stop_id)


@router.post("/", response_model=StopResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def create_stop(
    request: Request,
    data: StopCreate,
    service: StopService = Depends(get_service),  # noqa: B008
) -> StopResponse:
    """Create a new stop."""
    _ = request
    return await service.create_stop(data)


@router.patch("/{stop_id}", response_model=StopResponse)
@limiter.limit("10/minute")
async def update_stop(
    request: Request,
    stop_id: int,
    data: StopUpdate,
    service: StopService = Depends(get_service),  # noqa: B008
) -> StopResponse:
    """Update an existing stop."""
    _ = request
    return await service.update_stop(stop_id, data)


@router.delete("/{stop_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
async def delete_stop(
    request: Request,
    stop_id: int,
    service: StopService = Depends(get_service),  # noqa: B008
) -> None:
    """Delete a stop by its database ID."""
    _ = request
    await service.delete_stop(stop_id)
