# pyright: reportUnknownMemberType=false, reportUntypedFunctionDecorator=false
"""Analytics REST API routes for dashboard summary data.

Endpoints:
- GET /api/v1/analytics/fleet-summary - Fleet status breakdown
- GET /api/v1/analytics/driver-summary - Driver coverage breakdown
- GET /api/v1/analytics/on-time-performance - Route adherence metrics
- GET /api/v1/analytics/overview - Combined dashboard summary
"""

import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.schemas import (
    AnalyticsOverviewResponse,
    DriverSummaryResponse,
    FleetSummaryResponse,
    OnTimePerformanceResponse,
)
from app.analytics.service import AnalyticsService
from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.core.database import get_db
from app.core.logging import get_logger
from app.core.rate_limit import limiter

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


@router.get("/fleet-summary", response_model=FleetSummaryResponse)
@limiter.limit("30/minute")
async def get_fleet_summary(
    request: Request,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _current_user: User = Depends(get_current_user),  # noqa: B008
) -> FleetSummaryResponse:
    """Get fleet status breakdown with operational alerts.

    Args:
        request: The incoming HTTP request (used for rate limiting).
        db: Async database session.

    Returns:
        FleetSummaryResponse with counts by type/status and alerts.
    """
    _ = request
    logger.info("analytics.api.fleet_summary_requested")
    service = AnalyticsService(db)
    return await service.get_fleet_summary()


@router.get("/driver-summary", response_model=DriverSummaryResponse)
@limiter.limit("30/minute")
async def get_driver_summary(
    request: Request,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _current_user: User = Depends(get_current_user),  # noqa: B008
) -> DriverSummaryResponse:
    """Get driver coverage breakdown with expiry alerts.

    Args:
        request: The incoming HTTP request (used for rate limiting).
        db: Async database session.

    Returns:
        DriverSummaryResponse with counts by shift/status and alerts.
    """
    _ = request
    logger.info("analytics.api.driver_summary_requested")
    service = AnalyticsService(db)
    return await service.get_driver_summary()


@router.get("/on-time-performance", response_model=OnTimePerformanceResponse)
@limiter.limit("10/minute")
async def get_on_time_performance(
    request: Request,
    route_id: str | None = Query(None, max_length=100, pattern=r"^[\w\-.:]+$"),
    date: str | None = Query(None, max_length=10, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    time_from: str | None = Query(None, max_length=5, pattern=r"^\d{2}:\d{2}$"),
    time_until: str | None = Query(None, max_length=5, pattern=r"^\d{2}:\d{2}$"),
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _current_user: User = Depends(get_current_user),  # noqa: B008
) -> OnTimePerformanceResponse:
    """Get on-time adherence metrics from live GTFS-RT data.

    Args:
        request: The incoming HTTP request (used for rate limiting).
        route_id: Optional GTFS route ID for single-route analysis.
        date: Service date as YYYY-MM-DD. Defaults to today (Riga timezone).
        time_from: Start of analysis window (HH:MM).
        time_until: End of analysis window (HH:MM).
        db: Async database session.

    Returns:
        OnTimePerformanceResponse with per-route and network metrics.
    """
    _ = request
    logger.info(
        "analytics.api.on_time_requested",
        route_id=route_id,
        date=date,
        time_from=time_from,
        time_until=time_until,
    )
    service = AnalyticsService(db)
    try:
        return await service.get_on_time_performance(
            route_id=route_id,
            date=date,
            time_from=time_from,
            time_until=time_until,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(
            "analytics.api.on_time_failed",
            exc_info=True,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise HTTPException(
            status_code=503,
            detail="Transit data temporarily unavailable",
        ) from e


@router.get("/overview", response_model=AnalyticsOverviewResponse)
@limiter.limit("10/minute")
async def get_overview(
    request: Request,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _current_user: User = Depends(get_current_user),  # noqa: B008
) -> AnalyticsOverviewResponse:
    """Get combined dashboard summary with fleet, driver, and on-time data.

    On-time performance degrades gracefully — if transit data is unavailable,
    the overview still returns fleet and driver summaries with an empty on-time
    section.

    Args:
        request: The incoming HTTP request (used for rate limiting).
        db: Async database session.

    Returns:
        AnalyticsOverviewResponse with all three summaries.
    """
    _ = request
    logger.info("analytics.api.overview_requested")
    service = AnalyticsService(db)

    fleet = await service.get_fleet_summary()
    drivers = await service.get_driver_summary()

    try:
        on_time = await service.get_on_time_performance()
    except Exception as e:
        logger.warning(
            "analytics.api.overview_on_time_degraded",
            error=str(e),
            error_type=type(e).__name__,
        )
        on_time = OnTimePerformanceResponse(
            service_date=datetime.datetime.now(tz=datetime.UTC).date().isoformat(),
            service_type="unknown",
            total_routes=0,
            network_on_time_percentage=0.0,
            network_average_delay_seconds=0.0,
            routes=[],
            generated_at=datetime.datetime.now(tz=datetime.UTC),
        )

    return AnalyticsOverviewResponse(
        fleet=fleet,
        drivers=drivers,
        on_time=on_time,
    )
