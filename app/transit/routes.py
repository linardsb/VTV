"""Transit REST API routes for real-time vehicle positions.

Endpoints:
- GET /api/v1/transit/vehicles - Real-time vehicle positions from GTFS-RT
"""

from fastapi import APIRouter

from app.core.logging import get_logger
from app.transit.schemas import VehiclePositionsResponse
from app.transit.service import get_transit_service

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/transit", tags=["transit"])


@router.get("/vehicles", response_model=VehiclePositionsResponse)
async def get_vehicles(
    route_id: str | None = None,
) -> VehiclePositionsResponse:
    """Get real-time vehicle positions from GTFS-RT feeds.

    Returns enriched vehicle positions with route names, delay data,
    and stop name resolution. Data is cached for 20 seconds.

    Args:
        route_id: Optional GTFS route ID to filter results.

    Returns:
        VehiclePositionsResponse with vehicle positions.

    Raises:
        TransitDataError: Mapped to HTTP 503 by global exception handler.
    """
    logger.info("transit.api.vehicles_requested", route_id=route_id)

    service = get_transit_service()
    return await service.get_vehicle_positions(route_id=route_id)
