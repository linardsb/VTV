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

from app.analytics.daily_adherence import get_daily_reports
from app.analytics.schemas import (
    AnalyticsOverviewResponse,
    DailyAdherenceReportResponse,
    DriverSummaryResponse,
    FleetSummaryResponse,
    OnTimePerformanceResponse,
    PerHourAdherence,
    PerRouteAdherence,
    RouteAnomalyResponse,
    RouteDelayByStopResponse,
    RouteLoadTrendResponse,
    RoutePerformanceTrendResponse,
    WindowLiteral,
)
from app.analytics.service import AnalyticsService
from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.core.database import get_db
from app.core.logging import get_logger
from app.core.rate_limit import _analytics_subbucket_key, limiter

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
@limiter.limit("5/hour", key_func=_analytics_subbucket_key)
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


@router.get("/adherence/daily", response_model=list[DailyAdherenceReportResponse])
@limiter.limit("30/minute")
async def get_daily_adherence_reports(
    request: Request,
    date_from: str = Query(..., max_length=10, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    date_to: str = Query(..., max_length=10, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _current_user: User = Depends(get_current_user),  # noqa: B008
) -> list[DailyAdherenceReportResponse]:
    """Get daily schedule adherence reports for a date range.

    Args:
        request: The incoming HTTP request (used for rate limiting).
        date_from: Start date as YYYY-MM-DD.
        date_to: End date as YYYY-MM-DD.
        db: Async database session.

    Returns:
        List of daily adherence reports.
    """
    _ = request
    try:
        parsed_from = datetime.date.fromisoformat(date_from)
        parsed_to = datetime.date.fromisoformat(date_to)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid date format") from e

    if parsed_from > parsed_to:
        raise HTTPException(status_code=400, detail="date_from must be <= date_to")

    if (parsed_to - parsed_from).days > 90:
        raise HTTPException(status_code=400, detail="Date range must not exceed 90 days")

    logger.info(
        "analytics.api.adherence_daily_requested",
        date_from=date_from,
        date_to=date_to,
    )

    reports = await get_daily_reports(db, parsed_from, parsed_to)

    result: list[DailyAdherenceReportResponse] = []
    for r in reports:
        result.append(
            DailyAdherenceReportResponse(
                id=r.id,
                report_date=r.report_date,
                overall_pct=r.overall_pct,
                total_trips=r.total_trips,
                on_time_trips=r.on_time_trips,
                late_trips=r.late_trips,
                early_trips=r.early_trips,
                per_route=[PerRouteAdherence.model_validate(item) for item in r.per_route_json],
                per_hour=[PerHourAdherence.model_validate(item) for item in r.per_hour_json],
                anomaly_count=r.anomaly_count,
                alert_triggered=r.alert_triggered,
                created_at=r.created_at,  # pyright: ignore[reportArgumentType]
            )
        )
    return result


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


@router.get("/route-performance", response_model=RoutePerformanceTrendResponse)
@limiter.limit("30/minute")
async def get_route_performance(
    request: Request,
    route_id: str = Query(..., max_length=50, pattern=r"^[A-Za-z0-9_\-.:]+$"),
    window: WindowLiteral = Query("7"),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _user: User = Depends(get_current_user),  # noqa: B008
) -> RoutePerformanceTrendResponse:
    """Get daily on-time performance trend for a single route."""
    _ = request
    logger.info("analytics.api.route_performance_requested", route_id=route_id, window=window)
    service = AnalyticsService(db)
    return await service.get_route_performance(route_id, int(window))


@router.get("/route-delay-by-stop", response_model=RouteDelayByStopResponse)
@limiter.limit("30/minute")
async def get_route_delay_by_stop(
    request: Request,
    route_id: str = Query(..., max_length=50, pattern=r"^[A-Za-z0-9_\-.:]+$"),
    window: WindowLiteral = Query("7"),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _user: User = Depends(get_current_user),  # noqa: B008
) -> RouteDelayByStopResponse:
    """Get average delay per stop for a route."""
    _ = request
    logger.info("analytics.api.route_delay_by_stop_requested", route_id=route_id, window=window)
    service = AnalyticsService(db)
    return await service.get_route_delay_by_stop(route_id, int(window))


@router.get("/route-load-trend", response_model=RouteLoadTrendResponse)
@limiter.limit("30/minute")
async def get_route_load_trend(
    request: Request,
    route_id: str = Query(..., max_length=50, pattern=r"^[A-Za-z0-9_\-.:]+$"),
    window: WindowLiteral = Query("7"),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _user: User = Depends(get_current_user),  # noqa: B008
) -> RouteLoadTrendResponse:
    """Get daily load factor trend for a route."""
    _ = request
    logger.info("analytics.api.route_load_trend_requested", route_id=route_id, window=window)
    service = AnalyticsService(db)
    return await service.get_route_load_trend(route_id, int(window))


@router.get("/route-anomalies", response_model=RouteAnomalyResponse)
@limiter.limit("30/minute")
async def get_route_anomalies(
    request: Request,
    route_id: str = Query(..., max_length=50, pattern=r"^[A-Za-z0-9_\-.:]+$"),
    window: WindowLiteral = Query("7"),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _user: User = Depends(get_current_user),  # noqa: B008
) -> RouteAnomalyResponse:
    """Get daily anomaly counts by type for a route."""
    _ = request
    logger.info("analytics.api.route_anomalies_requested", route_id=route_id, window=window)
    service = AnalyticsService(db)
    return await service.get_route_anomalies(route_id, int(window))
