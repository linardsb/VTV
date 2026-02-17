# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false
# pyright: reportUnknownParameterType=false, reportUnknownArgumentType=false
# pyright: reportAttributeAccessIssue=false
"""GTFS-Realtime client for fetching and parsing protobuf feeds.

Fetches vehicle positions, trip updates, and alerts from Rigas Satiksme
public endpoints with in-memory caching.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import httpx
from google.transit import gtfs_realtime_pb2

from app.core.agents.exceptions import TransitDataError
from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)


# --- Internal data classes (typed wrappers around protobuf) ---


@dataclass
class VehiclePositionData:
    """Parsed vehicle position from GTFS-RT feed."""

    vehicle_id: str
    trip_id: str | None
    route_id: str | None
    latitude: float
    longitude: float
    bearing: float | None
    speed: float | None  # m/s from feed
    current_stop_sequence: int | None
    current_status: str  # "IN_TRANSIT_TO", "STOPPED_AT", "INCOMING_AT"
    stop_id: str | None
    timestamp: int  # POSIX


@dataclass
class StopTimeUpdateData:
    """Parsed stop time update from a trip update."""

    stop_sequence: int
    stop_id: str | None
    arrival_delay: int | None  # seconds
    departure_delay: int | None  # seconds
    arrival_time: int | None  # POSIX timestamp
    departure_time: int | None  # POSIX timestamp


@dataclass
class TripUpdateData:
    """Parsed trip update from GTFS-RT feed."""

    trip_id: str
    route_id: str | None
    vehicle_id: str | None
    stop_time_updates: list[StopTimeUpdateData]
    timestamp: int


@dataclass
class AlertData:
    """Parsed service alert from GTFS-RT feed."""

    header_text: str
    description_text: str | None
    cause: str | None
    effect: str | None
    route_ids: list[str]
    stop_ids: list[str]


# --- Cache entry ---


@dataclass
class _CacheEntry:
    """In-memory cache entry with timestamp."""

    data: list[VehiclePositionData] | list[TripUpdateData] | list[AlertData]
    fetched_at: float = field(default_factory=time.monotonic)


# --- Status enum mapping ---

_VEHICLE_STOP_STATUS: dict[int, str] = {
    0: "INCOMING_AT",
    1: "STOPPED_AT",
    2: "IN_TRANSIT_TO",
}

_ALERT_CAUSE: dict[int, str] = {
    1: "UNKNOWN_CAUSE",
    2: "OTHER_CAUSE",
    3: "TECHNICAL_PROBLEM",
    4: "STRIKE",
    5: "DEMONSTRATION",
    6: "ACCIDENT",
    7: "HOLIDAY",
    8: "WEATHER",
    9: "MAINTENANCE",
    10: "CONSTRUCTION",
    11: "POLICE_ACTIVITY",
    12: "MEDICAL_EMERGENCY",
}

_ALERT_EFFECT: dict[int, str] = {
    1: "NO_SERVICE",
    2: "REDUCED_SERVICE",
    3: "SIGNIFICANT_DELAYS",
    4: "DETOUR",
    5: "ADDITIONAL_SERVICE",
    6: "MODIFIED_SERVICE",
    7: "OTHER_EFFECT",
    8: "UNKNOWN_EFFECT",
    9: "STOP_MOVED",
}


class GTFSRealtimeClient:
    """Async client for fetching and parsing GTFS-Realtime protobuf feeds.

    Implements in-memory caching with configurable TTL to avoid hammering
    the Rigas Satiksme feed endpoints.

    Args:
        http_client: Async HTTP client for feed requests.
        settings: Application settings with feed URLs and cache TTL.
    """

    def __init__(self, http_client: httpx.AsyncClient, settings: Settings) -> None:
        self._http_client = http_client
        self._settings = settings
        self._vehicle_cache: _CacheEntry | None = None
        self._trip_update_cache: _CacheEntry | None = None
        self._alerts_cache: _CacheEntry | None = None

    def _is_cache_fresh(self, cache: _CacheEntry | None) -> bool:
        """Check if a cache entry is still within TTL."""
        if cache is None:
            return False
        age = time.monotonic() - cache.fetched_at
        return age < self._settings.gtfs_rt_cache_ttl_seconds

    async def _fetch_feed(self, url: str) -> bytes:
        """Fetch raw protobuf bytes from a GTFS-RT endpoint.

        Args:
            url: Feed endpoint URL.

        Returns:
            Raw protobuf bytes.

        Raises:
            TransitDataError: If the HTTP request fails.
        """
        try:
            response = await self._http_client.get(url)
            response.raise_for_status()
        except httpx.TimeoutException as e:
            msg = (
                f"Transit feed timed out at {url}. "
                "The Rigas Satiksme data service may be temporarily unavailable."
            )
            raise TransitDataError(msg) from e
        except httpx.HTTPError as e:
            msg = f"Transit feed request failed for {url}: {e}"
            raise TransitDataError(msg) from e
        return response.content

    def _parse_feed(self, raw: bytes) -> gtfs_realtime_pb2.FeedMessage:
        """Parse raw bytes into a GTFS-RT FeedMessage.

        Args:
            raw: Raw protobuf bytes.

        Returns:
            Parsed FeedMessage.

        Raises:
            TransitDataError: If the protobuf is malformed.
        """
        feed = gtfs_realtime_pb2.FeedMessage()
        try:
            feed.ParseFromString(raw)
        except Exception as e:
            msg = f"Failed to parse GTFS-RT protobuf: {e}"
            raise TransitDataError(msg) from e
        return feed

    async def fetch_vehicle_positions(self) -> list[VehiclePositionData]:
        """Fetch and parse current vehicle positions.

        Returns cached data if within TTL.

        Returns:
            List of vehicle position records.
        """
        if self._is_cache_fresh(self._vehicle_cache) and self._vehicle_cache is not None:
            return self._vehicle_cache.data  # type: ignore[return-value]

        raw = await self._fetch_feed(self._settings.gtfs_rt_vehicle_positions_url)
        feed = self._parse_feed(raw)

        vehicles: list[VehiclePositionData] = []
        for entity in feed.entity:
            if not entity.HasField("vehicle"):
                continue
            vp = entity.vehicle
            vehicle_id = vp.vehicle.id if vp.HasField("vehicle") else ""
            trip_id = vp.trip.trip_id if vp.HasField("trip") and vp.trip.trip_id else None
            route_id = vp.trip.route_id if vp.HasField("trip") and vp.trip.route_id else None

            vehicles.append(
                VehiclePositionData(
                    vehicle_id=vehicle_id,
                    trip_id=trip_id,
                    route_id=route_id,
                    latitude=vp.position.latitude,
                    longitude=vp.position.longitude,
                    bearing=vp.position.bearing if vp.position.bearing else None,
                    speed=vp.position.speed if vp.position.speed else None,
                    current_stop_sequence=(
                        vp.current_stop_sequence if vp.current_stop_sequence else None
                    ),
                    current_status=_VEHICLE_STOP_STATUS.get(vp.current_status, "IN_TRANSIT_TO"),
                    stop_id=vp.stop_id if vp.stop_id else None,
                    timestamp=vp.timestamp,
                )
            )

        self._vehicle_cache = _CacheEntry(data=vehicles)

        logger.info(
            "transit.vehicle_positions.fetch_completed",
            count=len(vehicles),
            feed_timestamp=feed.header.timestamp,
        )
        return vehicles

    async def fetch_trip_updates(self) -> list[TripUpdateData]:
        """Fetch and parse trip updates with delay information.

        Returns cached data if within TTL.

        Returns:
            List of trip update records.
        """
        if self._is_cache_fresh(self._trip_update_cache) and self._trip_update_cache is not None:
            return self._trip_update_cache.data  # type: ignore[return-value]

        raw = await self._fetch_feed(self._settings.gtfs_rt_trip_updates_url)
        feed = self._parse_feed(raw)

        updates: list[TripUpdateData] = []
        for entity in feed.entity:
            if not entity.HasField("trip_update"):
                continue
            tu = entity.trip_update
            trip_id = tu.trip.trip_id if tu.trip.trip_id else ""
            route_id = tu.trip.route_id if tu.trip.route_id else None
            vehicle_id = tu.vehicle.id if tu.HasField("vehicle") and tu.vehicle.id else None

            stop_time_updates: list[StopTimeUpdateData] = []
            for stu in tu.stop_time_update:
                stop_time_updates.append(
                    StopTimeUpdateData(
                        stop_sequence=stu.stop_sequence,
                        stop_id=stu.stop_id if stu.stop_id else None,
                        arrival_delay=(stu.arrival.delay if stu.HasField("arrival") else None),
                        departure_delay=(
                            stu.departure.delay if stu.HasField("departure") else None
                        ),
                        arrival_time=(
                            stu.arrival.time
                            if stu.HasField("arrival") and stu.arrival.time
                            else None
                        ),
                        departure_time=(
                            stu.departure.time
                            if stu.HasField("departure") and stu.departure.time
                            else None
                        ),
                    )
                )

            updates.append(
                TripUpdateData(
                    trip_id=trip_id,
                    route_id=route_id,
                    vehicle_id=vehicle_id,
                    stop_time_updates=stop_time_updates,
                    timestamp=tu.timestamp,
                )
            )

        self._trip_update_cache = _CacheEntry(data=updates)

        logger.info(
            "transit.trip_updates.fetch_completed",
            count=len(updates),
            feed_timestamp=feed.header.timestamp,
        )
        return updates

    async def fetch_alerts(self) -> list[AlertData]:
        """Fetch and parse service alerts.

        Returns cached data if within TTL.

        Returns:
            List of alert records.
        """
        if self._is_cache_fresh(self._alerts_cache) and self._alerts_cache is not None:
            return self._alerts_cache.data  # type: ignore[return-value]

        raw = await self._fetch_feed(self._settings.gtfs_rt_alerts_url)
        feed = self._parse_feed(raw)

        alerts: list[AlertData] = []
        for entity in feed.entity:
            if not entity.HasField("alert"):
                continue
            al = entity.alert

            header = ""
            if al.header_text and al.header_text.translation:
                header = al.header_text.translation[0].text

            description = None
            if al.description_text and al.description_text.translation:
                description = al.description_text.translation[0].text

            route_ids: list[str] = []
            stop_ids: list[str] = []
            for ie in al.informed_entity:
                if ie.route_id:
                    route_ids.append(ie.route_id)
                if ie.stop_id:
                    stop_ids.append(ie.stop_id)

            alerts.append(
                AlertData(
                    header_text=header,
                    description_text=description,
                    cause=_ALERT_CAUSE.get(al.cause),
                    effect=_ALERT_EFFECT.get(al.effect),
                    route_ids=route_ids,
                    stop_ids=stop_ids,
                )
            )

        self._alerts_cache = _CacheEntry(data=alerts)

        logger.info(
            "transit.alerts.fetch_completed",
            count=len(alerts),
        )
        return alerts
