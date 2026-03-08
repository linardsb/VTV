"""Transit service for fetching and enriching real-time vehicle positions.

Bridges the existing GTFSRealtimeClient and GTFSStaticCache into
REST-friendly response schemas for the CMS frontend.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import cast

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.agents.tools.transit.client import (
    GTFSRealtimeClient,
    TripUpdateData,
    VehiclePositionData,
)
from app.core.agents.tools.transit.static_cache import GTFSStaticCache
from app.core.agents.tools.transit.static_store import get_static_store
from app.core.config import Settings, get_settings
from app.core.database import get_db_context
from app.core.logging import get_logger
from app.transit.repository import (
    get_route_delay_trend,
    get_vehicle_history,
)
from app.transit.schemas import (
    HistoricalPosition,
    RouteDelayTrendPoint,
    RouteDelayTrendResponse,
    VehicleHistoryResponse,
    VehiclePosition,
    VehiclePositionsResponse,
    VehicleStopStatus,
)

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
        self._rt_client = GTFSRealtimeClient(http_client, settings)

    async def get_vehicle_positions(
        self,
        route_id: str | None = None,
        feed_id: str | None = None,
    ) -> VehiclePositionsResponse:
        """Get vehicle positions, from Redis (if poller active) or direct fetch.

        Args:
            route_id: Optional GTFS route ID to filter results.
            feed_id: Optional feed source to filter results.

        Returns:
            VehiclePositionsResponse with enriched vehicle data.

        Raises:
            TransitDataError: If GTFS-RT feeds are unavailable (direct mode).
        """
        start_time = time.monotonic()

        logger.info(
            "transit.vehicles.fetch_started",
            route_filter=route_id,
            feed_filter=feed_id,
            source="redis" if self._settings.poller_enabled else "direct",
        )

        if self._settings.poller_enabled:
            from app.transit.redis_reader import get_vehicles_from_redis

            result = await get_vehicles_from_redis(feed_id=feed_id, route_id=route_id)
        else:
            result = await self._fetch_direct(route_id=route_id)

        duration_ms = int((time.monotonic() - start_time) * 1000)
        logger.info(
            "transit.vehicles.fetch_completed",
            count=result.count,
            duration_ms=duration_ms,
        )
        return result

    async def get_history(
        self,
        db: AsyncSession,
        vehicle_id: str,
        from_time: datetime,
        to_time: datetime,
        limit: int = 1000,
    ) -> VehicleHistoryResponse:
        """Get historical positions for a vehicle.

        Args:
            db: Async database session.
            vehicle_id: Fleet vehicle identifier.
            from_time: Start of time range (UTC).
            to_time: End of time range (UTC).
            limit: Maximum number of positions to return.

        Returns:
            VehicleHistoryResponse with ordered position history.
        """
        records = await get_vehicle_history(db, vehicle_id, from_time, to_time, limit)
        positions = [
            HistoricalPosition(
                recorded_at=r.recorded_at.isoformat(),
                vehicle_id=r.vehicle_id,
                route_id=r.route_id,
                route_short_name=r.route_short_name,
                latitude=r.latitude,
                longitude=r.longitude,
                bearing=r.bearing,
                speed_kmh=r.speed_kmh,
                delay_seconds=r.delay_seconds,
                current_status=cast(VehicleStopStatus, r.current_status),
                feed_id=r.feed_id,
            )
            for r in records
        ]
        return VehicleHistoryResponse(
            vehicle_id=vehicle_id,
            count=len(positions),
            positions=positions,
            from_time=from_time.isoformat(),
            to_time=to_time.isoformat(),
        )

    async def get_delay_trend(
        self,
        db: AsyncSession,
        route_id: str,
        from_time: datetime,
        to_time: datetime,
        interval_minutes: int = 60,
    ) -> RouteDelayTrendResponse:
        """Get aggregated delay trend for a route.

        Args:
            db: Async database session.
            route_id: GTFS route identifier.
            from_time: Start of time range (UTC).
            to_time: End of time range (UTC).
            interval_minutes: Time bucket size in minutes.

        Returns:
            RouteDelayTrendResponse with time-bucketed delay data.
        """
        raw_points = await get_route_delay_trend(db, route_id, from_time, to_time, interval_minutes)
        static = await get_static_store(get_db_context, self._settings)
        route_short_name = static.get_route_name(route_id)

        data_points = [
            RouteDelayTrendPoint(
                time_bucket=str(p["time_bucket"]),
                avg_delay_seconds=p["avg_delay"],
                min_delay_seconds=p["min_delay"],
                max_delay_seconds=p["max_delay"],
                sample_count=p["sample_count"],
            )
            for p in raw_points
        ]
        return RouteDelayTrendResponse(
            route_id=route_id,
            route_short_name=route_short_name,
            interval_minutes=interval_minutes,
            count=len(data_points),
            data_points=data_points,
            from_time=from_time.isoformat(),
            to_time=to_time.isoformat(),
        )

    async def _fetch_direct(
        self,
        route_id: str | None = None,
    ) -> VehiclePositionsResponse:
        """Direct GTFS-RT fetch (legacy mode, used when poller is disabled)."""
        raw_vehicles = await self._rt_client.fetch_vehicle_positions()
        trip_updates = await self._rt_client.fetch_trip_updates()
        static = await get_static_store(get_db_context, self._settings)

        # Build trip update lookup by trip_id
        trip_update_map: dict[str, TripUpdateData] = {tu.trip_id: tu for tu in trip_updates}

        vehicles = _enrich_vehicles(raw_vehicles, trip_update_map, static)

        # Apply route filter
        if route_id is not None:
            vehicles = [v for v in vehicles if v.route_id == route_id]

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
        route_info = static.routes.get(resolved_route_id)
        route_type = route_info.route_type if route_info else 3

        # Fallback: extract route number from vehicle label (e.g. "Trolejbuss 15" → "15")
        if not route_short_name and v.vehicle_label:
            parts = v.vehicle_label.rsplit(" ", 1)
            if len(parts) == 2:
                route_short_name = parts[1]
                prefix = parts[0].lower()
                if "tram" in prefix:
                    route_type = 0
                elif "trol" in prefix:
                    route_type = 800
                elif "auto" in prefix or "bus" in prefix:
                    route_type = 3

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
        speed_kmh = round(v.speed * 3.6, 1) if v.speed is not None else None

        # Convert timestamp
        timestamp = datetime.fromtimestamp(v.timestamp, tz=UTC).isoformat() if v.timestamp else ""

        vehicles.append(
            VehiclePosition(
                vehicle_id=v.vehicle_id,
                route_id=resolved_route_id,
                route_short_name=route_short_name,
                route_type=route_type,
                latitude=v.latitude,
                longitude=v.longitude,
                bearing=v.bearing,
                speed_kmh=speed_kmh,
                delay_seconds=delay_seconds,
                current_status=cast(VehicleStopStatus, v.current_status),
                next_stop_name=next_stop_name,
                current_stop_name=current_stop_name,
                timestamp=timestamp,
            )
        )

    return vehicles


# --- Module-level singleton ---

_transit_service: TransitService | None = None


def get_transit_service(settings: Settings | None = None) -> TransitService:
    """Get or create the transit service singleton.

    Reuses the same httpx.AsyncClient and GTFSRealtimeClient across requests
    so the GTFS-RT cache (10s TTL) actually works.

    Args:
        settings: Optional settings override. Uses get_settings() if None.

    Returns:
        Singleton TransitService instance.
    """
    global _transit_service
    if _transit_service is None:
        if settings is None:
            settings = get_settings()
        client = httpx.AsyncClient(
            timeout=httpx.Timeout(10.0, connect=5.0),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )
        _transit_service = TransitService(http_client=client, settings=settings)
    return _transit_service


async def close_transit_service() -> None:
    """Close the singleton transit service and its HTTP client.

    Called during application shutdown.
    """
    global _transit_service
    if _transit_service is not None:
        try:
            await _transit_service._http_client.aclose()
        except RuntimeError:
            pass  # Event loop already closed during shutdown
        _transit_service = None
