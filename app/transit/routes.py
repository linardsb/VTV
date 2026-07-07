# pyright: reportUnknownMemberType=false, reportUntypedFunctionDecorator=false
"""Transit REST API routes for real-time and historical vehicle positions.

Endpoints:
- GET /api/v1/transit/vehicles - Real-time vehicle positions from GTFS-RT
- GET /api/v1/transit/feeds - Configured transit feeds
- GET /api/v1/transit/vehicles/{vehicle_id}/history - Historical positions
- GET /api/v1/transit/routes/{route_id}/delay-trend - Route delay trends
"""

import datetime as dt

from fastapi import APIRouter, Depends, Path, Query, Request
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, require_role
from app.auth.models import User
from app.core.agents.exceptions import TransitDataError
from app.core.config import get_settings
from app.core.database import get_db
from app.core.exceptions import (
    ConflictError,
    DomainValidationError,
    GoneError,
    NotFoundError,
    ServiceUnavailableError,
)
from app.core.logging import get_logger
from app.core.rate_limit import limiter
from app.transit.journey_planner import get_journey_planner
from app.transit.locshare import (
    create_share_token,
    decode_share_token,
    generate_qr_code_base64,
    hash_token,
)
from app.transit.models import ShareLink, VehiclePhoneAssignment
from app.transit.schemas import (
    JourneyPlanResponse,
    PhoneAssignmentCreate,
    PhoneAssignmentResponse,
    RouteDelayTrendResponse,
    ShareLinkCreate,
    ShareLinkResponse,
    ShareResolveResponse,
    TransitFeedsResponse,
    TransitFeedStatus,
    VehicleHistoryResponse,
    VehiclePositionsResponse,
)
from app.transit.schemas_eta import ETAResponse
from app.transit.service import get_transit_service

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/transit", tags=["transit"])


def _parse_iso_time(value: str) -> dt.datetime:
    """Parse ISO 8601 string to timezone-aware datetime, or raise 422."""
    try:
        return dt.datetime.fromisoformat(value).replace(tzinfo=dt.UTC)
    except ValueError as err:
        raise DomainValidationError(f"Invalid ISO 8601 time: {value}") from err


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


@router.get("/vehicles/{vehicle_id}/eta", response_model=ETAResponse)
@limiter.limit("30/minute")
async def get_vehicle_eta(
    request: Request,
    vehicle_id: str = Path(max_length=100, pattern=r"^[\w\-.:]+$"),
    stop_id: str = Query(
        ...,
        max_length=100,
        pattern=r"^[\w\-.:]+$",
        description="GTFS stop ID to predict arrival at",
    ),
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _current_user: User = Depends(get_current_user),  # noqa: B008
) -> ETAResponse:
    """Get ML-predicted ETA for a vehicle arriving at a specific stop.

    Returns predicted arrival time with confidence interval. Falls back to
    scheduled arrival time when the ML model is unavailable.

    Args:
        request: HTTP request (rate limiting).
        vehicle_id: Fleet vehicle identifier.
        stop_id: GTFS stop identifier.
        db: Async database session.

    Returns:
        ETAResponse with predicted arrival and confidence bounds.
    """
    _ = request
    logger.info(
        "transit.api.vehicle_eta_requested",
        vehicle_id=vehicle_id,
        stop_id=stop_id,
    )
    service = get_transit_service()
    result = await service.get_eta(db, vehicle_id, stop_id)
    return ETAResponse(**result)


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


@router.get("/gtfs-rt/vehicle_positions.pb")
@limiter.limit("60/minute")
async def get_gtfs_rt_vehicle_positions(
    request: Request,
    feed_id: str | None = Query(None, max_length=50, pattern=r"^[\w\-]+$"),
) -> Response:
    """Serve combined GTFS-RT VehiclePositions feed as protobuf.

    Public endpoint — no authentication required. Rate limited to 60 requests/minute.
    Returns binary protobuf (application/x-protobuf).
    """
    _ = request
    from app.transit.gtfs_rt_publisher import build_combined_feed

    pb_bytes = await build_combined_feed(feed_id=feed_id)
    return Response(
        content=pb_bytes,
        media_type="application/x-protobuf",
    )


# ── Phone Assignment endpoints (LV-3.1) ─────────────────────────────


@router.post(
    "/phone-assignments",
    response_model=PhoneAssignmentResponse,
    status_code=201,
)
@limiter.limit("30/minute")
async def create_phone_assignment(
    request: Request,
    body: PhoneAssignmentCreate,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    current_user: User = Depends(  # noqa: B008
        require_role("admin", "dispatcher")  # noqa: B008
    ),
) -> PhoneAssignmentResponse:
    """Create a phone-to-vehicle assignment for OwnTracks tracking."""
    _ = request
    logger.info(
        "transit.phone_assignment.create_started",
        phone_identifier=body.phone_identifier,
        vehicle_id=body.vehicle_id,
    )

    # Check for duplicate phone_identifier
    existing = await db.execute(
        select(VehiclePhoneAssignment).where(
            VehiclePhoneAssignment.phone_identifier == body.phone_identifier,
            VehiclePhoneAssignment.active.is_(True),
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise ConflictError("Phone identifier already assigned")

    assignment = VehiclePhoneAssignment(
        phone_identifier=body.phone_identifier,
        vehicle_id=body.vehicle_id,
        route_id=body.route_id,
        driver_id=body.driver_id,
        assigned_by=current_user.email,
        active=True,
    )
    db.add(assignment)
    await db.commit()
    await db.refresh(assignment)

    logger.info(
        "transit.phone_assignment.create_completed",
        assignment_id=assignment.id,
        phone_identifier=body.phone_identifier,
    )
    return PhoneAssignmentResponse.model_validate(assignment)


@router.get("/phone-assignments", response_model=list[PhoneAssignmentResponse])
@limiter.limit("30/minute")
async def list_phone_assignments(
    request: Request,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _current_user: User = Depends(  # noqa: B008
        require_role("admin", "dispatcher")  # noqa: B008
    ),
) -> list[PhoneAssignmentResponse]:
    """List all active phone-to-vehicle assignments."""
    _ = request
    result = await db.execute(
        select(VehiclePhoneAssignment).where(VehiclePhoneAssignment.active.is_(True))
    )
    rows = result.scalars().all()
    return [PhoneAssignmentResponse.model_validate(r) for r in rows]


@router.delete("/phone-assignments/{assignment_id}", status_code=200)
@limiter.limit("30/minute")
async def delete_phone_assignment(
    request: Request,
    assignment_id: int = Path(ge=1),
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _current_user: User = Depends(require_role("admin")),  # noqa: B008
) -> PhoneAssignmentResponse:
    """Deactivate a phone-to-vehicle assignment (admin only)."""
    _ = request
    result = await db.execute(
        select(VehiclePhoneAssignment).where(VehiclePhoneAssignment.id == assignment_id)
    )
    assignment = result.scalar_one_or_none()
    if assignment is None:
        raise NotFoundError("Assignment not found")

    assignment.active = False
    await db.commit()
    await db.refresh(assignment)

    logger.info(
        "transit.phone_assignment.delete_completed",
        assignment_id=assignment_id,
    )
    return PhoneAssignmentResponse.model_validate(assignment)


# ── LV-3.3 OTP journey planner ──────────────────────────────────────


@router.get("/plan", response_model=JourneyPlanResponse)
@limiter.limit("10/minute")
async def plan_journey(
    request: Request,
    from_lat: float = Query(..., ge=55.5, le=58.1),
    from_lon: float = Query(..., ge=20.5, le=28.3),
    to_lat: float = Query(..., ge=55.5, le=58.1),
    to_lon: float = Query(..., ge=20.5, le=28.3),
    depart_at: str | None = Query(None, max_length=30),
    arrive_by: str | None = Query(None, max_length=30),
    modes: str = Query("TRANSIT,WALK", max_length=100, pattern=r"^[A-Z,]+$"),
    _current_user: User = Depends(get_current_user),  # noqa: B008
) -> JourneyPlanResponse:
    """Plan a multi-modal journey via OpenTripPlanner with GTFS-RT delay enrichment."""
    _ = request
    if depart_at is not None and arrive_by is not None:
        raise DomainValidationError("depart_at and arrive_by are mutually exclusive")
    depart_dt = _parse_iso_time(depart_at) if depart_at else None
    arrive_dt = _parse_iso_time(arrive_by) if arrive_by else None
    planner = get_journey_planner()
    try:
        return await planner.plan_journey(
            from_lat=from_lat,
            from_lon=from_lon,
            to_lat=to_lat,
            to_lon=to_lon,
            depart_at=depart_dt,
            arrive_by=arrive_dt,
            modes=modes,
        )
    except TransitDataError as exc:
        raise ServiceUnavailableError(str(exc)) from exc


# ── LV-3.4 Trip share links ─────────────────────────────────────────


@router.post(
    "/share",
    response_model=ShareLinkResponse,
    status_code=201,
)
@limiter.limit("30/minute")
async def create_share_link(
    request: Request,
    body: ShareLinkCreate,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    current_user: User = Depends(  # noqa: B008
        require_role("admin", "dispatcher")  # noqa: B008
    ),
) -> ShareLinkResponse:
    """Mint a signed share-link JWT for a specific vehicle/route (LV-3.4)."""
    _ = request
    token, token_hash_val = create_share_token(
        body.vehicle_id,
        body.route_id,
        body.feed_id,
        body.expiry_hours,
    )
    expires_at = dt.datetime.now(dt.UTC) + dt.timedelta(hours=body.expiry_hours)
    link = ShareLink(
        token_hash=token_hash_val,
        vehicle_id=body.vehicle_id,
        route_id=body.route_id,
        feed_id=body.feed_id,
        created_by=current_user.id,
        expires_at=expires_at,
        view_count=0,
        is_active=True,
    )
    db.add(link)
    await db.commit()
    await db.refresh(link)
    share_url = f"/share/{token}"
    qr = generate_qr_code_base64(share_url)
    logger.info(
        "transit.share_link.created",
        share_link_id=link.id,
        vehicle_id=body.vehicle_id,
        user_id=current_user.id,
    )
    return ShareLinkResponse(
        id=link.id,
        vehicle_id=link.vehicle_id,
        route_id=link.route_id,
        feed_id=link.feed_id,
        token=token,
        share_url=share_url,
        qr_code_base64=qr,
        expires_at=link.expires_at,
    )


@router.get("/share/{token}", response_model=ShareResolveResponse)
@limiter.limit("60/minute")
async def resolve_share_link(
    request: Request,
    token: str = Path(..., min_length=8, max_length=2048),
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> ShareResolveResponse:
    """Public resolver for a share link — returns live vehicle position (LV-3.4)."""
    _ = request
    payload = decode_share_token(token)
    if payload is None:
        raise NotFoundError("Share link not found")
    token_hash_val = hash_token(token)
    result = await db.execute(
        select(ShareLink).where(
            ShareLink.token_hash == token_hash_val,
            ShareLink.is_active.is_(True),
        )
    )
    link = result.scalar_one_or_none()
    if link is None:
        raise NotFoundError("Share link not found")
    if link.expires_at < dt.datetime.now(dt.UTC):
        raise GoneError("Share link expired")

    service = get_transit_service()
    positions = await service.get_vehicle_positions(
        route_id=link.route_id,
        feed_id=link.feed_id,
    )
    position = next(
        (v for v in positions.vehicles if v.vehicle_id == link.vehicle_id),
        None,
    )
    link.view_count += 1
    await db.commit()
    return ShareResolveResponse(
        vehicle_id=link.vehicle_id,
        route_id=link.route_id,
        feed_id=link.feed_id,
        expires_at=link.expires_at,
        position=position,
    )
