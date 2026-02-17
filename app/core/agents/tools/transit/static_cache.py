"""Lightweight cache for static GTFS data (route/stop/trip names).

Downloads and parses the GTFS ZIP to resolve IDs into human-readable
names for enriching real-time data. Refreshes daily.
"""

from __future__ import annotations

import csv
import io
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx

from app.core.agents.exceptions import TransitDataError
from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class RouteInfo:
    """Static route information from routes.txt."""

    route_id: str
    route_short_name: str
    route_long_name: str
    route_type: int  # 0=tram, 3=bus, 11=trolleybus


@dataclass
class StopInfo:
    """Static stop information from stops.txt."""

    stop_id: str
    stop_name: str
    stop_lat: float | None = None
    stop_lon: float | None = None


@dataclass
class TripInfo:
    """Static trip information from trips.txt."""

    trip_id: str
    route_id: str
    direction_id: int | None = None
    trip_headsign: str | None = None


class GTFSStaticCache:
    """In-memory cache for static GTFS data.

    Loads routes.txt, stops.txt, and trips.txt from a GTFS ZIP file
    into dictionaries for fast ID-to-name lookups. Reloads when stale.
    """

    def __init__(self) -> None:
        self.routes: dict[str, RouteInfo] = {}
        self.stops: dict[str, StopInfo] = {}
        self.trips: dict[str, TripInfo] = {}
        self._loaded_at: datetime | None = None

    async def load(self, http_client: httpx.AsyncClient, gtfs_url: str) -> None:
        """Download and parse a GTFS ZIP file.

        Args:
            http_client: Async HTTP client for downloading.
            gtfs_url: URL of the GTFS ZIP file.

        Raises:
            TransitDataError: If download or parsing fails.
        """
        try:
            response = await http_client.get(gtfs_url)
            response.raise_for_status()
        except httpx.HTTPError as e:
            msg = f"Failed to download GTFS static feed from {gtfs_url}: {e}"
            raise TransitDataError(msg) from e

        try:
            zip_bytes = io.BytesIO(response.content)
            with zipfile.ZipFile(zip_bytes) as zf:
                self._parse_routes(zf)
                self._parse_stops(zf)
                self._parse_trips(zf)
        except (zipfile.BadZipFile, KeyError, csv.Error) as e:
            msg = f"Failed to parse GTFS ZIP: {e}"
            raise TransitDataError(msg) from e

        self._loaded_at = datetime.now(tz=UTC)

        logger.info(
            "transit.static_cache.load_completed",
            route_count=len(self.routes),
            stop_count=len(self.stops),
            trip_count=len(self.trips),
        )

    def _parse_routes(self, zf: zipfile.ZipFile) -> None:
        """Parse routes.txt from the GTFS ZIP."""
        if "routes.txt" not in zf.namelist():
            return
        with zf.open("routes.txt") as f:
            reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))
            for row in reader:
                route_id = row.get("route_id", "")
                self.routes[route_id] = RouteInfo(
                    route_id=route_id,
                    route_short_name=row.get("route_short_name", route_id),
                    route_long_name=row.get("route_long_name", ""),
                    route_type=int(row.get("route_type", "3")),
                )

    def _parse_stops(self, zf: zipfile.ZipFile) -> None:
        """Parse stops.txt from the GTFS ZIP."""
        if "stops.txt" not in zf.namelist():
            return
        with zf.open("stops.txt") as f:
            reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))
            for row in reader:
                stop_id = row.get("stop_id", "")
                lat_str = row.get("stop_lat", "")
                lon_str = row.get("stop_lon", "")
                self.stops[stop_id] = StopInfo(
                    stop_id=stop_id,
                    stop_name=row.get("stop_name", stop_id),
                    stop_lat=float(lat_str) if lat_str else None,
                    stop_lon=float(lon_str) if lon_str else None,
                )

    def _parse_trips(self, zf: zipfile.ZipFile) -> None:
        """Parse trips.txt from the GTFS ZIP."""
        if "trips.txt" not in zf.namelist():
            return
        with zf.open("trips.txt") as f:
            reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))
            for row in reader:
                trip_id = row.get("trip_id", "")
                direction_str = row.get("direction_id", "")
                self.trips[trip_id] = TripInfo(
                    trip_id=trip_id,
                    route_id=row.get("route_id", ""),
                    direction_id=int(direction_str) if direction_str else None,
                    trip_headsign=row.get("trip_headsign") or None,
                )

    def is_stale(self, ttl_hours: int) -> bool:
        """Check if cached data is older than TTL.

        Args:
            ttl_hours: Maximum age in hours before data is considered stale.

        Returns:
            True if cache needs refreshing.
        """
        if self._loaded_at is None:
            return True
        age_hours = (datetime.now(tz=UTC) - self._loaded_at).total_seconds() / 3600
        return age_hours >= ttl_hours

    def get_route_name(self, route_id: str) -> str:
        """Get human-readable route name, falling back to route_id.

        Args:
            route_id: GTFS route identifier.

        Returns:
            Route short name or the route_id if not found.
        """
        info = self.routes.get(route_id)
        return info.route_short_name if info else route_id

    def get_stop_name(self, stop_id: str) -> str:
        """Get human-readable stop name, falling back to stop_id.

        Args:
            stop_id: GTFS stop identifier.

        Returns:
            Stop name or the stop_id if not found.
        """
        info = self.stops.get(stop_id)
        return info.stop_name if info else stop_id

    def get_trip_route_id(self, trip_id: str) -> str | None:
        """Look up the route_id for a given trip.

        Args:
            trip_id: GTFS trip identifier.

        Returns:
            Route ID or None if trip not found.
        """
        info = self.trips.get(trip_id)
        return info.route_id if info else None

    def get_trip_headsign(self, trip_id: str) -> str | None:
        """Look up the headsign (direction label) for a given trip.

        Args:
            trip_id: GTFS trip identifier.

        Returns:
            Trip headsign or None if not found.
        """
        info = self.trips.get(trip_id)
        return info.trip_headsign if info else None


# --- Module-level singleton ---

_static_cache: GTFSStaticCache | None = None


async def get_static_cache(http_client: httpx.AsyncClient, settings: Settings) -> GTFSStaticCache:
    """Get or create the static GTFS cache singleton.

    Downloads and parses the GTFS ZIP on first call, then returns
    cached data until the TTL expires.

    Args:
        http_client: Async HTTP client for downloading.
        settings: Application settings with GTFS URL and TTL.

    Returns:
        Populated GTFSStaticCache instance.
    """
    global _static_cache
    if _static_cache is None or _static_cache.is_stale(settings.gtfs_static_cache_ttl_hours):
        _static_cache = GTFSStaticCache()
        await _static_cache.load(http_client, settings.gtfs_static_url)
    return _static_cache
