# pyright: reportUnknownArgumentType=false, reportUnknownVariableType=false
"""Pluggable feed clients for non-GTFS-RT transit data sources.

Provides DaugavpilsScraper (JSON API scraper) and GpsTextClient (CSV-like
GPS text parser). Both normalize to VehiclePositionData, matching the
GTFSRealtimeClient interface so FeedPoller can use them interchangeably.
"""

from __future__ import annotations

import re
import time
from typing import Protocol, runtime_checkable

import httpx

from app.core.agents.exceptions import TransitDataError
from app.core.agents.tools.transit.client import (
    TripUpdateData,
    VehiclePositionData,
)
from app.core.config import Settings, TransitFeedConfig
from app.core.logging import get_logger

logger = get_logger(__name__)

# Latvia bounding box for input validation
_LAT_MIN, _LAT_MAX = 55.5, 58.1
_LON_MIN, _LON_MAX = 20.5, 28.3
_MAX_FUTURE_SECONDS = 300  # 5 minutes
_MAX_STALE_SECONDS = 86400  # 24 hours
_VEHICLE_ID_RE = re.compile(r"^[\w\-.:]{1,64}$")


@runtime_checkable
class FeedClient(Protocol):
    """Interface for feed data fetchers."""

    async def fetch_vehicle_positions(self) -> list[VehiclePositionData]: ...

    async def fetch_trip_updates(self) -> list[TripUpdateData]: ...


def _is_valid_coordinates(lat: float, lon: float) -> bool:
    """Check if coordinates fall within Latvia bounding box."""
    return _LAT_MIN <= lat <= _LAT_MAX and _LON_MIN <= lon <= _LON_MAX


def _is_valid_vehicle_id(vehicle_id: str) -> bool:
    """Check if vehicle_id matches allowed pattern."""
    return bool(_VEHICLE_ID_RE.match(vehicle_id))


def _is_valid_timestamp(ts: int) -> bool:
    """Check if timestamp is within acceptable staleness/future bounds."""
    now = int(time.time())
    return (now - _MAX_STALE_SECONDS) <= ts <= (now + _MAX_FUTURE_SECONDS)


class DaugavpilsScraper:
    """Scrapes vehicle positions from satiksme.daugavpils.lv JSON API.

    Expected JSON response: list of objects with lat, lng, route, id,
    bearing, speed fields. Format is provisional -- update _parse_vehicle()
    if the actual API differs.
    """

    def __init__(
        self,
        feed_config: TransitFeedConfig,
        http_client: httpx.AsyncClient,
    ) -> None:
        self._feed_config = feed_config
        self._http_client = http_client

    async def fetch_vehicle_positions(self) -> list[VehiclePositionData]:
        """Fetch and parse vehicle positions from the scraper endpoint."""
        feed_id = self._feed_config.feed_id
        url = self._feed_config.rt_vehicle_positions_url
        start = time.monotonic()

        try:
            response = await self._http_client.get(url, timeout=10.0)
            response.raise_for_status()
        except httpx.HTTPError as e:
            raise TransitDataError(
                f"Failed to fetch {feed_id} scraper data: {type(e).__name__}"
            ) from e

        try:
            data = response.json()
        except ValueError as e:
            raise TransitDataError(f"Invalid JSON from {feed_id} scraper") from e

        if not isinstance(data, list):
            raise TransitDataError(f"Expected JSON array from {feed_id} scraper")

        now_ts = int(time.time())
        vehicles: list[VehiclePositionData] = []
        raw_count = len(data)

        for entry in data:
            if not isinstance(entry, dict):
                continue
            parsed = self._parse_vehicle(entry, now_ts)
            if parsed is not None:
                vehicles.append(parsed)

        duration_ms = round((time.monotonic() - start) * 1000)
        logger.info(
            "transit.scraper.fetch_completed",
            feed_id=feed_id,
            raw_count=raw_count,
            valid_count=len(vehicles),
            duration_ms=duration_ms,
        )
        return vehicles

    async def fetch_trip_updates(self) -> list[TripUpdateData]:
        """Non-GTFS-RT feeds don't provide trip updates."""
        return []

    def _parse_vehicle(
        self,
        entry: dict[str, object],
        now_ts: int,
    ) -> VehiclePositionData | None:
        """Parse a single vehicle entry, returning None if invalid."""
        try:
            lat = float(str(entry.get("lat", "")))
            lon = float(str(entry.get("lng", "")))
        except (ValueError, TypeError):
            logger.warning(
                "transit.scraper.vehicle_invalid",
                feed_id=self._feed_config.feed_id,
                reason="invalid_coordinates",
            )
            return None

        if not _is_valid_coordinates(lat, lon):
            logger.warning(
                "transit.scraper.vehicle_invalid",
                feed_id=self._feed_config.feed_id,
                reason="coordinates_out_of_range",
            )
            return None

        vehicle_id = str(entry.get("id", ""))
        if not _is_valid_vehicle_id(vehicle_id):
            logger.warning(
                "transit.scraper.vehicle_invalid",
                feed_id=self._feed_config.feed_id,
                reason="invalid_vehicle_id",
            )
            return None

        # Use provided timestamp or current time
        raw_ts = entry.get("timestamp")
        ts = int(float(str(raw_ts))) if raw_ts is not None else now_ts
        if not _is_valid_timestamp(ts):
            logger.warning(
                "transit.scraper.vehicle_invalid",
                feed_id=self._feed_config.feed_id,
                reason="timestamp_out_of_range",
            )
            return None

        bearing_raw = entry.get("bearing")
        bearing = float(str(bearing_raw)) if bearing_raw is not None else None
        speed_raw = entry.get("speed")
        speed = float(str(speed_raw)) if speed_raw is not None else None
        route_id = str(entry.get("route", ""))

        return VehiclePositionData(
            vehicle_id=vehicle_id,
            trip_id=None,
            route_id=route_id if route_id else None,
            latitude=lat,
            longitude=lon,
            bearing=bearing,
            speed=speed,
            current_stop_sequence=None,
            current_status="IN_TRANSIT_TO",
            stop_id=None,
            timestamp=ts,
        )


class GpsTextClient:
    """Parses GPS text feeds from marsruti.lv/{city}/gps.txt.

    Expected format: semicolon-delimited lines with 7 fields:
    vehicle_id;lat;lon;bearing;speed;route_id;timestamp

    Format is provisional -- the parser tolerates minor variations
    (extra whitespace, missing trailing fields).
    """

    def __init__(
        self,
        feed_config: TransitFeedConfig,
        http_client: httpx.AsyncClient,
    ) -> None:
        self._feed_config = feed_config
        self._http_client = http_client

    async def fetch_vehicle_positions(self) -> list[VehiclePositionData]:
        """Fetch and parse vehicle positions from GPS text endpoint."""
        feed_id = self._feed_config.feed_id
        url = self._feed_config.rt_vehicle_positions_url
        start = time.monotonic()

        try:
            response = await self._http_client.get(url, timeout=10.0)
            response.raise_for_status()
        except httpx.HTTPError as e:
            raise TransitDataError(f"Failed to fetch {feed_id} GPS text: {type(e).__name__}") from e

        text = response.text
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        now_ts = int(time.time())
        vehicles: list[VehiclePositionData] = []
        raw_lines = len(lines)

        for line in lines:
            parsed = self._parse_line(line, now_ts)
            if parsed is not None:
                vehicles.append(parsed)

        duration_ms = round((time.monotonic() - start) * 1000)
        logger.info(
            "transit.gps_text.fetch_completed",
            feed_id=feed_id,
            raw_lines=raw_lines,
            valid_count=len(vehicles),
            duration_ms=duration_ms,
        )
        return vehicles

    async def fetch_trip_updates(self) -> list[TripUpdateData]:
        """Non-GTFS-RT feeds don't provide trip updates."""
        return []

    def _parse_line(
        self,
        line: str,
        now_ts: int,
    ) -> VehiclePositionData | None:
        """Parse a single GPS text line, returning None if malformed."""
        parts = line.split(";")
        if len(parts) < 6:
            logger.warning(
                "transit.gps_text.line_malformed",
                feed_id=self._feed_config.feed_id,
                reason="insufficient_fields",
                field_count=len(parts),
            )
            return None

        vehicle_id = parts[0].strip()
        if not _is_valid_vehicle_id(vehicle_id):
            logger.warning(
                "transit.gps_text.vehicle_invalid",
                feed_id=self._feed_config.feed_id,
                reason="invalid_vehicle_id",
            )
            return None

        try:
            lat = float(parts[1].strip())
            lon = float(parts[2].strip())
        except (ValueError, IndexError):
            logger.warning(
                "transit.gps_text.vehicle_invalid",
                feed_id=self._feed_config.feed_id,
                reason="invalid_coordinates",
            )
            return None

        if not _is_valid_coordinates(lat, lon):
            logger.warning(
                "transit.gps_text.vehicle_invalid",
                feed_id=self._feed_config.feed_id,
                reason="coordinates_out_of_range",
            )
            return None

        try:
            bearing = float(parts[3].strip()) if parts[3].strip() else None
        except (ValueError, IndexError):
            bearing = None

        try:
            speed = float(parts[4].strip()) if parts[4].strip() else None
        except (ValueError, IndexError):
            speed = None

        route_id = parts[5].strip() if len(parts) > 5 else ""

        # Timestamp is optional 7th field
        ts = now_ts
        if len(parts) > 6 and parts[6].strip():
            try:
                ts = int(float(parts[6].strip()))
            except (ValueError, IndexError):
                ts = now_ts

        if not _is_valid_timestamp(ts):
            logger.warning(
                "transit.gps_text.vehicle_invalid",
                feed_id=self._feed_config.feed_id,
                reason="timestamp_out_of_range",
            )
            return None

        return VehiclePositionData(
            vehicle_id=vehicle_id,
            trip_id=None,
            route_id=route_id if route_id else None,
            latitude=lat,
            longitude=lon,
            bearing=bearing,
            speed=speed,
            current_stop_sequence=None,
            current_status="IN_TRANSIT_TO",
            stop_id=None,
            timestamp=ts,
        )


def create_feed_client(
    feed_config: TransitFeedConfig,
    http_client: httpx.AsyncClient,
    settings: Settings,
) -> FeedClient:
    """Create the appropriate feed client based on feed_type.

    Args:
        feed_config: Feed configuration with feed_type discriminator.
        http_client: Shared async HTTP client.
        settings: Application settings (used by GTFSRealtimeClient).

    Returns:
        A FeedClient implementation matching the feed_type.
    """
    if feed_config.feed_type == "scraper":
        return DaugavpilsScraper(feed_config=feed_config, http_client=http_client)
    if feed_config.feed_type == "gps_text":
        return GpsTextClient(feed_config=feed_config, http_client=http_client)
    # Default: standard GTFS-RT protobuf client
    from app.core.agents.tools.transit.client import GTFSRealtimeClient

    return GTFSRealtimeClient(http_client=http_client, settings=settings)
