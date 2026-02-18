"""Transit service for fetching and enriching real-time vehicle positions.

Bridges the existing GTFSRealtimeClient and GTFSStaticCache into
REST-friendly response schemas for the CMS frontend.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime

import httpx

from app.core.agents.tools.transit.client import (
    GTFSRealtimeClient,
    TripUpdateData,
    VehiclePositionData,
)
from app.core.agents.tools.transit.static_cache import (
    GTFSStaticCache,
    get_static_cache,
)
from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.transit.schemas import VehiclePosition, VehiclePositionsResponse

logger = get_logger(__name__)


class TransitService:
    """Service for fetching enriched vehicle positions from GTFS-RT feeds.

    Combines real-time vehicle positions with trip delay data and static
    route/stop name resolution.

    Args:
        http_client: Async HTTP client for GTFS feed requests.
        settings: Application settings with feed URLs and cache TTL.
    """

    def __init__(self, http_client: httpx.AsyncClient, settings: Settings) -> None:
        self._http_client = http_client
        self._settings = settings

    async def get_vehicle_positions(
        self,
        route_id: str | None = None,
    ) -> VehiclePositionsResponse:
        """Fetch and enrich real-time vehicle positions.

        Args:
            route_id: Optional GTFS route ID to filter results.

        Returns:
            VehiclePositionsResponse with enriched vehicle data.

        Raises:
            TransitDataError: If GTFS-RT feeds are unavailable.
        """
        start_time = time.monotonic()

        logger.info("transit.vehicles.fetch_started", route_filter=route_id)

        client = GTFSRealtimeClient(self._http_client, self._settings)
        raw_vehicles = await client.fetch_vehicle_positions()
        trip_updates = await client.fetch_trip_updates()
        static = await get_static_cache(self._http_client, self._settings)

        # Build trip update lookup by trip_id
        trip_update_map: dict[str, TripUpdateData] = {tu.trip_id: tu for tu in trip_updates}

        vehicles = _enrich_vehicles(raw_vehicles, trip_update_map, static)

        # Apply route filter
        if route_id is not None:
            vehicles = [v for v in vehicles if v.route_id == route_id]

        duration_ms = int((time.monotonic() - start_time) * 1000)
        logger.info(
            "transit.vehicles.fetch_completed",
            count=len(vehicles),
            duration_ms=duration_ms,
        )

        return VehiclePositionsResponse(
            count=len(vehicles),
            vehicles=vehicles,
            fetched_at=datetime.now(tz=UTC).isoformat(),
        )


def _enrich_vehicles(
    raw_vehicles: list[VehiclePositionData],
    trip_update_map: dict[str, TripUpdateData],
    static: GTFSStaticCache,
) -> list[VehiclePosition]:
    """Convert raw GTFS-RT vehicle positions into enriched REST models.

    Args:
        raw_vehicles: Parsed vehicle positions from GTFS-RT feed.
        trip_update_map: Trip updates keyed by trip_id for delay lookup.
        static: Static GTFS cache for name resolution.

    Returns:
        List of enriched VehiclePosition models.
    """
    vehicles: list[VehiclePosition] = []

    for v in raw_vehicles:
        # Resolve route
        resolved_route_id = (
            v.route_id or (static.get_trip_route_id(v.trip_id) if v.trip_id else None) or ""
        )
        route_short_name = static.get_route_name(resolved_route_id)

        # Get delay and next stop from trip updates
        delay_seconds = 0
        next_stop_name: str | None = None
        if v.trip_id and v.trip_id in trip_update_map:
            tu = trip_update_map[v.trip_id]
            if tu.stop_time_updates:
                relevant = tu.stop_time_updates
                if v.current_stop_sequence is not None:
                    filtered = [
                        s
                        for s in tu.stop_time_updates
                        if s.stop_sequence >= v.current_stop_sequence
                    ]
                    relevant = filtered or tu.stop_time_updates
                next_stu = relevant[0]
                delay_seconds = next_stu.arrival_delay or next_stu.departure_delay or 0
                if next_stu.stop_id:
                    next_stop_name = static.get_stop_name(next_stu.stop_id)

        # Resolve current stop name
        current_stop_name = static.get_stop_name(v.stop_id) if v.stop_id else None

        # Convert speed m/s -> km/h
        speed_kmh = round(v.speed * 3.6, 1) if v.speed else None

        # Convert timestamp
        timestamp = datetime.fromtimestamp(v.timestamp, tz=UTC).isoformat() if v.timestamp else ""

        vehicles.append(
            VehiclePosition(
                vehicle_id=v.vehicle_id,
                route_id=resolved_route_id,
                route_short_name=route_short_name,
                latitude=v.latitude,
                longitude=v.longitude,
                bearing=v.bearing,
                speed_kmh=speed_kmh,
                delay_seconds=delay_seconds,
                current_status=v.current_status,
                next_stop_name=next_stop_name,
                current_stop_name=current_stop_name,
                timestamp=timestamp,
            )
        )

    return vehicles


def get_transit_service(settings: Settings | None = None) -> TransitService:
    """Create a TransitService with a configured HTTP client.

    Args:
        settings: Optional settings override. Uses get_settings() if None.

    Returns:
        Configured TransitService instance.
    """
    if settings is None:
        settings = get_settings()
    client = httpx.AsyncClient(
        timeout=httpx.Timeout(10.0, connect=5.0),
        limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
    )
    return TransitService(http_client=client, settings=settings)
