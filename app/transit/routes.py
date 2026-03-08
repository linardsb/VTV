# pyright: reportUnknownMemberType=false, reportUntypedFunctionDecorator=false
"""Transit REST API routes for real-time and historical vehicle positions.

Endpoints:
- GET /api/v1/transit/vehicles - Real-time vehicle positions from GTFS-RT
- GET /api/v1/transit/feeds - Configured transit feeds
- GET /api/v1/transit/vehicles/{vehicle_id}/history - Historical positions
- GET /api/v1/transit/routes/{route_id}/delay-trend - Route delay trends
"""

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, require_role
from app.auth.models import User
from app.core.config import get_settings
from app.core.database import get_db
from app.core.logging import get_logger
from app.core.rate_limit import limiter
from app.transit.schemas import (
    RouteDelayTrendResponse,
    TransitFeedsResponse,
    TransitFeedStatus,
    VehicleHistoryResponse,
    VehiclePositionsResponse,
)
from app.transit.service import get_transit_service

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/transit", tags=["transit"])


def _parse_iso_time(value: str) -> dt.datetime:
    """Parse ISO 8601 string to timezone-aware datetime, or raise 422."""
    try:
        return dt.datetime.fromisoformat(value).replace(tzinfo=dt.UTC)
    except ValueError as err:
        raise HTTPException(status_code=422, detail=f"Invalid ISO 8601 time: {value}") from err


@router.get("/vehicles", response_model=VehiclePositionsResponse)
@limiter.limit("30/minute")
async def get_vehicles(
    request: Request,
    route_id: str | None = Query(None, max_length=100, pattern=r"^[\w\-.:]+$"),
    feed_id: str | None = Query(None, max_length=50, pattern=r"^[\w\-]+$"),
    _current_user: User = Depends(get_current_user),  # noqa: B008
) -> VehiclePositionsResponse:
    """Get real-time vehicle positions, optionally filtered by feed and/or route.

    Args:
        request: The incoming HTTP request (used for rate limiting).
        route_id: Optional GTFS route ID to filter results.
        feed_id: Optional feed source to filter results (e.g., "riga").

    Returns:
        VehiclePositionsResponse with vehicle positions.

    Raises:
        TransitDataError: Mapped to HTTP 503 by global exception handler.
    """
    logger.info("transit.api.vehicles_requested", route_id=route_id, feed_id=feed_id)

    service = get_transit_service()
    return await service.get_vehicle_positions(route_id=route_id, feed_id=feed_id)


@router.get("/feeds", response_model=TransitFeedsResponse)
@limiter.limit("30/minute")
async def get_feeds(
    request: Request,
    _current_user: User = Depends(get_current_user),  # noqa: B008
) -> TransitFeedsResponse:
    """List configured transit feeds and their status."""
    _ = request
    settings = get_settings()
    feeds = [
        TransitFeedStatus(
            feed_id=f.feed_id,
            operator_name=f.operator_name,
            enabled=f.enabled,
            poll_interval_seconds=f.poll_interval_seconds,
        )
        for f in settings.transit_feeds
    ]
    return TransitFeedsResponse(feeds=feeds)


@router.get("/vehicles/{vehicle_id}/history", response_model=VehicleHistoryResponse)
@limiter.limit("10/minute")
async def get_vehicle_history(
    request: Request,
    vehicle_id: str = Path(max_length=100, pattern=r"^[\w\-.:]+$"),
    from_time: str = Query(
        ...,
        max_length=30,
        pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}",
        description="ISO 8601 start time (UTC)",
    ),
    to_time: str = Query(
        ...,
        max_length=30,
        pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}",
        description="ISO 8601 end time (UTC)",
    ),
    limit: int = Query(1000, ge=1, le=10000),
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _current_user: User = Depends(  # noqa: B008
        require_role("admin", "dispatcher", "editor")  # noqa: B008
    ),
) -> VehicleHistoryResponse:
    """Get historical positions for a specific vehicle within a time range.

    Requires admin, dispatcher, or editor role. Rate limited to 10/minute.

    Args:
        request: HTTP request (rate limiting).
        vehicle_id: Fleet vehicle identifier.
        from_time: ISO 8601 start time (UTC).
        to_time: ISO 8601 end time (UTC).
        limit: Maximum positions to return (1-10000, default 1000).
        db: Async database session.

    Returns:
        VehicleHistoryResponse with ordered position history.
    """
    _ = request
    logger.info(
        "transit.api.vehicle_history_requested",
        vehicle_id=vehicle_id,
        from_time=from_time,
        to_time=to_time,
    )
    from_dt = _parse_iso_time(from_time)
    to_dt = _parse_iso_time(to_time)

    service = get_transit_service()
    return await service.get_history(db, vehicle_id, from_dt, to_dt, limit)


@router.get("/routes/{route_id}/delay-trend", response_model=RouteDelayTrendResponse)
@limiter.limit("10/minute")
async def get_route_delay_trend(
    request: Request,
    route_id: str = Path(max_length=100, pattern=r"^[\w\-.:]+$"),
    from_time: str = Query(
        ...,
        max_length=30,
        pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}",
        description="ISO 8601 start time (UTC)",
    ),
    to_time: str = Query(
        ...,
        max_length=30,
        pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}",
        description="ISO 8601 end time (UTC)",
    ),
    interval_minutes: int = Query(60, ge=5, le=1440),
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _current_user: User = Depends(  # noqa: B008
        require_role("admin", "dispatcher", "editor")  # noqa: B008
    ),
) -> RouteDelayTrendResponse:
    """Get aggregated delay trend for a route over a time range.

    Uses TimescaleDB time_bucket for efficient time-series aggregation.
    Rate limited to 10/minute.

    Args:
        request: HTTP request (rate limiting).
        route_id: GTFS route identifier.
        from_time: ISO 8601 start time (UTC).
        to_time: ISO 8601 end time (UTC).
        interval_minutes: Time bucket size (5-1440 minutes, default 60).
        db: Async database session.

    Returns:
        RouteDelayTrendResponse with time-bucketed delay data.
    """
    _ = request
    logger.info(
        "transit.api.route_delay_trend_requested",
        route_id=route_id,
        from_time=from_time,
        to_time=to_time,
        interval_minutes=interval_minutes,
    )
    from_dt = _parse_iso_time(from_time)
    to_dt = _parse_iso_time(to_time)

    service = get_transit_service()
    return await service.get_delay_trend(db, route_id, from_dt, to_dt, interval_minutes)
