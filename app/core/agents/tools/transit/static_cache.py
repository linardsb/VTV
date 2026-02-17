"""Lightweight cache for static GTFS data (route/stop/trip names + schedules).

Downloads and parses the GTFS ZIP to resolve IDs into human-readable
names, build schedule indexes, and resolve active services by date.
Refreshes daily.
"""

from __future__ import annotations

import csv
import io
import zipfile
from dataclasses import dataclass
from datetime import UTC, date, datetime

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
    service_id: str = ""
    direction_id: int | None = None
    trip_headsign: str | None = None


@dataclass
class StopTimeEntry:
    """A single scheduled stop time within a trip from stop_times.txt.

    Attributes:
        stop_id: GTFS stop identifier.
        stop_sequence: Order of stop within trip (1-indexed typically).
        arrival_time: GTFS HH:MM:SS format (may exceed 24:00:00 for overnight trips).
        departure_time: GTFS HH:MM:SS format (may exceed 24:00:00).
    """

    stop_id: str
    stop_sequence: int
    arrival_time: str
    departure_time: str


@dataclass
class CalendarEntry:
    """Weekly service pattern from calendar.txt.

    Attributes:
        service_id: Links to trips via TripInfo.service_id.
        monday: Service runs on Mondays.
        tuesday: Service runs on Tuesdays.
        wednesday: Service runs on Wednesdays.
        thursday: Service runs on Thursdays.
        friday: Service runs on Fridays.
        saturday: Service runs on Saturdays.
        sunday: Service runs on Sundays.
        start_date: YYYYMMDD inclusive start of service period.
        end_date: YYYYMMDD inclusive end of service period.
    """

    service_id: str
    monday: bool = False
    tuesday: bool = False
    wednesday: bool = False
    thursday: bool = False
    friday: bool = False
    saturday: bool = False
    sunday: bool = False
    start_date: str = ""
    end_date: str = ""


@dataclass
class CalendarDateException:
    """Single-day service exception from calendar_dates.txt.

    Attributes:
        service_id: Links to calendar entry.
        date: YYYYMMDD format.
        exception_type: 1=service added for this date, 2=service removed.
    """

    service_id: str
    date: str
    exception_type: int  # 1=added, 2=removed


class GTFSStaticCache:
    """In-memory cache for static GTFS data.

    Loads routes.txt, stops.txt, trips.txt, stop_times.txt, calendar.txt,
    and calendar_dates.txt from a GTFS ZIP file into dictionaries and
    indexes for fast lookups. Reloads when stale.
    """

    def __init__(self) -> None:
        self.routes: dict[str, RouteInfo] = {}
        self.stops: dict[str, StopInfo] = {}
        self.trips: dict[str, TripInfo] = {}
        self.calendar: list[CalendarEntry] = []
        self.calendar_dates: list[CalendarDateException] = []
        self.route_trips: dict[str, list[TripInfo]] = {}
        self.trip_stop_times: dict[str, list[StopTimeEntry]] = {}
        self.stop_routes: dict[str, list[str]] = {}
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
                self._parse_stop_times(zf)
                self._parse_calendar(zf)
                self._parse_calendar_dates(zf)
                self._build_route_trips_index()
                self._build_stop_routes_index()
        except (zipfile.BadZipFile, KeyError, csv.Error) as e:
            msg = f"Failed to parse GTFS ZIP: {e}"
            raise TransitDataError(msg) from e

        self._loaded_at = datetime.now(tz=UTC)

        logger.info(
            "transit.static_cache.load_completed",
            route_count=len(self.routes),
            stop_count=len(self.stops),
            trip_count=len(self.trips),
            stop_time_trips=len(self.trip_stop_times),
            calendar_entries=len(self.calendar),
            calendar_exceptions=len(self.calendar_dates),
            stop_routes_count=len(self.stop_routes),
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
                    service_id=row.get("service_id", ""),
                    direction_id=int(direction_str) if direction_str else None,
                    trip_headsign=row.get("trip_headsign") or None,
                )

    def _parse_stop_times(self, zf: zipfile.ZipFile) -> None:
        """Parse stop_times.txt from the GTFS ZIP into trip-indexed lookup."""
        if "stop_times.txt" not in zf.namelist():
            return
        with zf.open("stop_times.txt") as f:
            reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))
            for row in reader:
                trip_id = row.get("trip_id", "")
                entry = StopTimeEntry(
                    stop_id=row.get("stop_id", ""),
                    stop_sequence=int(row.get("stop_sequence", "0")),
                    arrival_time=row.get("arrival_time", ""),
                    departure_time=row.get("departure_time", ""),
                )
                if trip_id not in self.trip_stop_times:
                    self.trip_stop_times[trip_id] = []
                self.trip_stop_times[trip_id].append(entry)

        # Sort each trip's stops by sequence
        for stops in self.trip_stop_times.values():
            stops.sort(key=lambda s: s.stop_sequence)

    def _parse_calendar(self, zf: zipfile.ZipFile) -> None:
        """Parse calendar.txt from the GTFS ZIP."""
        if "calendar.txt" not in zf.namelist():
            return
        with zf.open("calendar.txt") as f:
            reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))
            for row in reader:
                self.calendar.append(
                    CalendarEntry(
                        service_id=row.get("service_id", ""),
                        monday=row.get("monday", "0") == "1",
                        tuesday=row.get("tuesday", "0") == "1",
                        wednesday=row.get("wednesday", "0") == "1",
                        thursday=row.get("thursday", "0") == "1",
                        friday=row.get("friday", "0") == "1",
                        saturday=row.get("saturday", "0") == "1",
                        sunday=row.get("sunday", "0") == "1",
                        start_date=row.get("start_date", ""),
                        end_date=row.get("end_date", ""),
                    )
                )

    def _parse_calendar_dates(self, zf: zipfile.ZipFile) -> None:
        """Parse calendar_dates.txt from the GTFS ZIP."""
        if "calendar_dates.txt" not in zf.namelist():
            return
        with zf.open("calendar_dates.txt") as f:
            reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))
            for row in reader:
                self.calendar_dates.append(
                    CalendarDateException(
                        service_id=row.get("service_id", ""),
                        date=row.get("date", ""),
                        exception_type=int(row.get("exception_type", "0")),
                    )
                )

    def _build_route_trips_index(self) -> None:
        """Build route_id → list[TripInfo] index from parsed trips."""
        self.route_trips = {}
        for trip in self.trips.values():
            if trip.route_id not in self.route_trips:
                self.route_trips[trip.route_id] = []
            self.route_trips[trip.route_id].append(trip)

    def _build_stop_routes_index(self) -> None:
        """Build stop_id → list[route_short_name] index from parsed data."""
        stop_route_sets: dict[str, set[str]] = {}
        for trip_id, stop_times in self.trip_stop_times.items():
            trip_info = self.trips.get(trip_id)
            if trip_info is None:
                continue
            route_name = self.get_route_name(trip_info.route_id)
            for st in stop_times:
                if st.stop_id not in stop_route_sets:
                    stop_route_sets[st.stop_id] = set()
                stop_route_sets[st.stop_id].add(route_name)
        self.stop_routes = {sid: sorted(routes) for sid, routes in stop_route_sets.items()}

    def get_active_service_ids(self, query_date: date) -> set[str]:
        """Determine which service_ids are active on a given date.

        Checks calendar.txt for weekly patterns within the date range,
        then applies calendar_dates.txt exceptions (add/remove).

        Args:
            query_date: The date to check service availability for.

        Returns:
            Set of active service_id strings for the given date.
        """
        day_name = query_date.strftime("%A").lower()
        date_str = query_date.strftime("%Y%m%d")
        active: set[str] = set()

        # Step 1: Check calendar.txt (regular weekly schedule)
        for entry in self.calendar:
            if entry.start_date <= date_str <= entry.end_date:
                if getattr(entry, day_name, False):
                    active.add(entry.service_id)

        # Step 2: Apply calendar_dates.txt exceptions
        for exc in self.calendar_dates:
            if exc.date == date_str:
                if exc.exception_type == 1:
                    active.add(exc.service_id)
                elif exc.exception_type == 2:
                    active.discard(exc.service_id)

        return active

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
