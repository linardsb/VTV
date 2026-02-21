# pyright: reportUnknownMemberType=false, reportUntypedFunctionDecorator=false
"""Transit REST API routes for real-time vehicle positions.

Endpoints:
- GET /api/v1/transit/vehicles - Real-time vehicle positions from GTFS-RT
"""

from fastapi import APIRouter, Request

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.rate_limit import limiter
from app.transit.schemas import VehiclePositionsResponse
from app.transit.service import get_transit_service

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/transit", tags=["transit"])


@router.get("/vehicles", response_model=VehiclePositionsResponse)
@limiter.limit("30/minute")
async def get_vehicles(
    request: Request,
    route_id: str | None = None,
    feed_id: str | None = None,
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


@router.get("/feeds")
async def get_feeds() -> list[dict[str, object]]:
    """List configured transit feeds and their status."""
    settings = get_settings()
    return [
        {
            "feed_id": f.feed_id,
            "operator_name": f.operator_name,
            "enabled": f.enabled,
            "poll_interval_seconds": f.poll_interval_seconds,
        }
        for f in settings.transit_feeds
    ]
