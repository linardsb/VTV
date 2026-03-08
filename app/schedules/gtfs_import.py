"""GTFS ZIP file parser for schedule import.

Parses standard GTFS files (agencies.txt, routes.txt, calendar.txt,
calendar_dates.txt, trips.txt, stop_times.txt) and returns model instances.
This module is pure parsing -- no database access. The service handles DB operations.
"""

import csv
import io
import zipfile
from dataclasses import dataclass, field
from datetime import date

from app.schedules.models import (
    Agency,
    Calendar,
    CalendarDate,
    Route,
    Shape,
    StopTime,
    Trip,
)
from app.stops.models import Stop

# ZIP bomb protection limits
MAX_UNCOMPRESSED_SIZE = 500_000_000  # 500MB total uncompressed limit
MAX_COMPRESSION_RATIO = 100  # Reject if ratio > 100:1
MAX_SINGLE_FILE_SIZE = 100_000_000  # 100MB per file inside ZIP


@dataclass
class GTFSParseResult:
    """Result of parsing a GTFS ZIP file."""

    agencies: list[Agency] = field(default_factory=lambda: list[Agency]())
    routes: list[Route] = field(default_factory=lambda: list[Route]())
    calendars: list[Calendar] = field(default_factory=lambda: list[Calendar]())
    calendar_dates: list[CalendarDate] = field(default_factory=lambda: list[CalendarDate]())
    trips: list[Trip] = field(default_factory=lambda: list[Trip]())
    stop_times: list[StopTime] = field(default_factory=lambda: list[StopTime]())
    stops: list[Stop] = field(default_factory=lambda: list[Stop]())
    shapes: list[Shape] = field(default_factory=lambda: list[Shape]())
    skipped_stop_times: int = 0
    warnings: list[str] = field(default_factory=lambda: list[str]())
    # Parallel parent-reference lists for FK resolution after flush.
    # route_agency_refs[i] is the Agency ORM object for routes[i].
    route_agency_refs: list[Agency] = field(default_factory=lambda: list[Agency]())
    calendar_date_calendar_refs: list[Calendar] = field(default_factory=lambda: list[Calendar]())
    trip_route_refs: list[Route] = field(default_factory=lambda: list[Route]())
    trip_calendar_refs: list[Calendar] = field(default_factory=lambda: list[Calendar]())
    stop_time_trip_refs: list[Trip] = field(default_factory=lambda: list[Trip]())
    stop_time_stop_refs: list[Stop | None] = field(default_factory=lambda: list[Stop | None]())


class GTFSImporter:
    """Parse GTFS ZIP files into model instances.

    Usage:
        importer = GTFSImporter(zip_bytes)
        result = importer.parse(stop_map={"1001": 42, "1002": 43})
    """

    def __init__(self, zip_data: bytes, feed_id: str) -> None:
        """Initialize with ZIP file bytes.

        Args:
            zip_data: Raw bytes of a GTFS ZIP file.
            feed_id: Feed identifier for multi-feed isolation.
        """
        self.zip_data = zip_data
        self.feed_id = feed_id
        self.warnings: list[str] = []

    def _validate_zip_safety(self) -> None:
        """Check ZIP for bomb patterns before extraction.

        Raises:
            ValueError: If ZIP exceeds safety limits.
        """
        with zipfile.ZipFile(io.BytesIO(self.zip_data)) as zf:
            total_uncompressed = sum(info.file_size for info in zf.infolist())
            compressed_size = len(self.zip_data)

            if total_uncompressed > MAX_UNCOMPRESSED_SIZE:
                msg = f"ZIP uncompressed size ({total_uncompressed} bytes) exceeds {MAX_UNCOMPRESSED_SIZE} byte limit"
                raise ValueError(msg)

            if compressed_size > 0:
                ratio = total_uncompressed / compressed_size
                if ratio > MAX_COMPRESSION_RATIO:
                    msg = f"ZIP compression ratio ({ratio:.0f}:1) exceeds {MAX_COMPRESSION_RATIO}:1 limit"
                    raise ValueError(msg)

            for info in zf.infolist():
                if info.file_size > MAX_SINGLE_FILE_SIZE:
                    msg = f"File {info.filename} ({info.file_size} bytes) exceeds {MAX_SINGLE_FILE_SIZE} byte limit"
                    raise ValueError(msg)

    def parse(self, stop_map: dict[str, int]) -> GTFSParseResult:
        """Parse all GTFS files from the ZIP.

        Args:
            stop_map: Mapping of GTFS stop_id strings to database stop.id integers.
                If empty, stops.txt will be parsed and returned in the result
                for the service to create before linking stop_times.

        Returns:
            GTFSParseResult with all parsed entities.
        """
        self._validate_zip_safety()
        with zipfile.ZipFile(io.BytesIO(self.zip_data)) as zf:
            file_names = zf.namelist()

            # Parse stops if stop_map is empty (fresh DB)
            stops: list[Stop] = []
            if not stop_map:
                stops = self._parse_stops(zf, file_names)
                # Build a temporary stop_map using GTFS IDs and Stop objects.
                # After flush, these objects will have real DB IDs.
                # For now, use index+1 as placeholder since stop_times need int IDs.
                # The service will resolve these after flushing stops.
                stop_map = {s.gtfs_stop_id: i for i, s in enumerate(stops)}

            # Parse agencies (create default if missing)
            agencies = self._parse_agencies(zf, file_names)
            agency_map = {a.gtfs_agency_id: a for a in agencies}

            # Parse routes (with agency references for FK resolution)
            routes, route_agency_refs = self._parse_routes(zf, file_names, agency_map)
            route_map = {r.gtfs_route_id: r for r in routes}

            # Parse calendars
            calendars = self._parse_calendars(zf, file_names)
            calendar_map = {c.gtfs_service_id: c for c in calendars}

            # Parse calendar dates (with calendar references)
            calendar_dates, cd_calendar_refs = self._parse_calendar_dates(
                zf, file_names, calendar_map
            )

            # Parse trips (with route and calendar references)
            trips, trip_route_refs, trip_calendar_refs = self._parse_trips(
                zf, file_names, route_map, calendar_map
            )
            trip_map = {t.gtfs_trip_id: t for t in trips}

            # Parse stop times (with trip and stop references)
            stop_times, stop_time_trip_refs, stop_time_stop_refs, skipped = self._parse_stop_times(
                zf, file_names, trip_map, stop_map, stops
            )

            # Parse shapes
            shapes = self._parse_shapes(zf, file_names)

        return GTFSParseResult(
            agencies=agencies,
            routes=routes,
            calendars=calendars,
            calendar_dates=calendar_dates,
            trips=trips,
            stop_times=stop_times,
            stops=stops,
            shapes=shapes,
            skipped_stop_times=skipped,
            warnings=self.warnings,
            route_agency_refs=route_agency_refs,
            calendar_date_calendar_refs=cd_calendar_refs,
            trip_route_refs=trip_route_refs,
            trip_calendar_refs=trip_calendar_refs,
            stop_time_trip_refs=stop_time_trip_refs,
            stop_time_stop_refs=stop_time_stop_refs,
        )

    def _read_csv(self, zf: zipfile.ZipFile, filename: str) -> csv.DictReader[str] | None:
        """Read a CSV file from the ZIP archive.

        Args:
            zf: Open ZipFile instance.
            filename: Name of the file to read.

        Returns:
            DictReader for the file, or None if not found.
        """
        if filename not in zf.namelist():
            return None
        text_stream = io.TextIOWrapper(zf.open(filename), encoding="utf-8-sig")
        return csv.DictReader(text_stream)

    def _parse_agencies(self, zf: zipfile.ZipFile, file_names: list[str]) -> list[Agency]:
        """Parse agency.txt or create a default agency.

        Args:
            zf: Open ZipFile instance.
            file_names: List of files in the ZIP.

        Returns:
            List of Agency model instances.
        """
        reader = self._read_csv(zf, "agency.txt")
        if reader is None:
            self.warnings.append("agency.txt not found, creating default agency")
            return [
                Agency(
                    gtfs_agency_id="default",
                    feed_id=self.feed_id,
                    agency_name="Default Agency",
                    agency_timezone="Europe/Riga",
                )
            ]
        _ = file_names  # consumed by _read_csv
        agencies: list[Agency] = []
        for row in reader:
            agencies.append(
                Agency(
                    gtfs_agency_id=row.get("agency_id", "default"),
                    feed_id=self.feed_id,
                    agency_name=row.get("agency_name", "Unknown"),
                    agency_url=row.get("agency_url") or None,
                    agency_timezone=row.get("agency_timezone", "Europe/Riga"),
                    agency_lang=row.get("agency_lang") or None,
                )
            )
        if not agencies:
            self.warnings.append("agency.txt is empty, creating default agency")
            agencies.append(
                Agency(
                    gtfs_agency_id="default",
                    feed_id=self.feed_id,
                    agency_name="Default Agency",
                    agency_timezone="Europe/Riga",
                )
            )
        return agencies

    def _parse_routes(
        self,
        zf: zipfile.ZipFile,
        file_names: list[str],
        agency_map: dict[str, Agency],
    ) -> tuple[list[Route], list[Agency]]:
        """Parse routes.txt.

        Args:
            zf: Open ZipFile instance.
            file_names: List of files in the ZIP.
            agency_map: Mapping of GTFS agency_id to Agency instances.

        Returns:
            Tuple of (routes list, parallel agency refs list).
        """
        reader = self._read_csv(zf, "routes.txt")
        if reader is None:
            self.warnings.append("routes.txt not found")
            return [], []
        _ = file_names
        routes: list[Route] = []
        agency_refs: list[Agency] = []
        default_agency = next(iter(agency_map.values())) if agency_map else None
        for row in reader:
            agency_id_str = row.get("agency_id", "")
            agency = agency_map.get(agency_id_str, default_agency)
            if agency is None:
                self.warnings.append(f"Skipping route {row.get('route_id', '?')}: no agency")
                continue

            route_type_str = row.get("route_type", "3")
            route_type = int(route_type_str) if route_type_str.isdigit() else 3

            sort_order_str = row.get("route_sort_order", "")
            sort_order = int(sort_order_str) if sort_order_str.isdigit() else None

            routes.append(
                Route(
                    gtfs_route_id=row.get("route_id", ""),
                    feed_id=self.feed_id,
                    agency_id=0,  # placeholder, resolved after agency flush
                    route_short_name=row.get("route_short_name", ""),
                    route_long_name=row.get("route_long_name", ""),
                    route_type=route_type,
                    route_color=row.get("route_color") or None,
                    route_text_color=row.get("route_text_color") or None,
                    route_sort_order=sort_order,
                )
            )
            agency_refs.append(agency)
        return routes, agency_refs

    def _parse_calendars(self, zf: zipfile.ZipFile, file_names: list[str]) -> list[Calendar]:
        """Parse calendar.txt.

        Args:
            zf: Open ZipFile instance.
            file_names: List of files in the ZIP.

        Returns:
            List of Calendar model instances.
        """
        reader = self._read_csv(zf, "calendar.txt")
        if reader is None:
            self.warnings.append("calendar.txt not found")
            return []
        _ = file_names
        calendars: list[Calendar] = []
        for row in reader:
            start_str = row.get("start_date", "")
            end_str = row.get("end_date", "")
            start_date = _parse_gtfs_date(start_str)
            end_date = _parse_gtfs_date(end_str)
            if start_date is None or end_date is None:
                self.warnings.append(
                    f"Skipping calendar {row.get('service_id', '?')}: invalid dates"
                )
                continue

            calendars.append(
                Calendar(
                    gtfs_service_id=row.get("service_id", ""),
                    feed_id=self.feed_id,
                    monday=row.get("monday", "0") == "1",
                    tuesday=row.get("tuesday", "0") == "1",
                    wednesday=row.get("wednesday", "0") == "1",
                    thursday=row.get("thursday", "0") == "1",
                    friday=row.get("friday", "0") == "1",
                    saturday=row.get("saturday", "0") == "1",
                    sunday=row.get("sunday", "0") == "1",
                    start_date=start_date,
                    end_date=end_date,
                )
            )
        return calendars

    def _parse_calendar_dates(
        self,
        zf: zipfile.ZipFile,
        file_names: list[str],
        calendar_map: dict[str, Calendar],
    ) -> tuple[list[CalendarDate], list[Calendar]]:
        """Parse calendar_dates.txt.

        Args:
            zf: Open ZipFile instance.
            file_names: List of files in the ZIP.
            calendar_map: Mapping of GTFS service_id to Calendar instances.

        Returns:
            Tuple of (calendar_dates list, parallel calendar refs list).
        """
        reader = self._read_csv(zf, "calendar_dates.txt")
        if reader is None:
            return [], []
        _ = file_names
        dates: list[CalendarDate] = []
        calendar_refs: list[Calendar] = []
        for row in reader:
            service_id = row.get("service_id", "")
            if service_id not in calendar_map:
                self.warnings.append(f"Skipping calendar_date: unknown service_id {service_id}")
                continue
            d = _parse_gtfs_date(row.get("date", ""))
            if d is None:
                continue
            exc_type_str = row.get("exception_type", "1")
            exc_type = int(exc_type_str) if exc_type_str.isdigit() else 1
            dates.append(
                CalendarDate(
                    calendar_id=0,  # placeholder, resolved after calendar flush
                    date=d,
                    exception_type=exc_type,
                )
            )
            calendar_refs.append(calendar_map[service_id])
        return dates, calendar_refs

    def _parse_trips(
        self,
        zf: zipfile.ZipFile,
        file_names: list[str],
        route_map: dict[str, Route],
        calendar_map: dict[str, Calendar],
    ) -> tuple[list[Trip], list[Route], list[Calendar]]:
        """Parse trips.txt.

        Args:
            zf: Open ZipFile instance.
            file_names: List of files in the ZIP.
            route_map: Mapping of GTFS route_id to Route instances.
            calendar_map: Mapping of GTFS service_id to Calendar instances.

        Returns:
            Tuple of (trips list, parallel route refs, parallel calendar refs).
        """
        reader = self._read_csv(zf, "trips.txt")
        if reader is None:
            self.warnings.append("trips.txt not found")
            return [], [], []
        _ = file_names
        trips: list[Trip] = []
        route_refs: list[Route] = []
        calendar_refs: list[Calendar] = []
        for row in reader:
            route_id_str = row.get("route_id", "")
            service_id = row.get("service_id", "")
            if route_id_str not in route_map:
                self.warnings.append(
                    f"Skipping trip {row.get('trip_id', '?')}: unknown route {route_id_str}"
                )
                continue
            if service_id not in calendar_map:
                self.warnings.append(
                    f"Skipping trip {row.get('trip_id', '?')}: unknown service {service_id}"
                )
                continue

            dir_str = row.get("direction_id", "")
            direction_id = int(dir_str) if dir_str.isdigit() else None

            trips.append(
                Trip(
                    gtfs_trip_id=row.get("trip_id", ""),
                    feed_id=self.feed_id,
                    route_id=0,  # placeholder, resolved after route flush
                    calendar_id=0,  # placeholder, resolved after calendar flush
                    direction_id=direction_id,
                    trip_headsign=row.get("trip_headsign") or None,
                    block_id=row.get("block_id") or None,
                    shape_id=row.get("shape_id") or None,
                )
            )
            route_refs.append(route_map[route_id_str])
            calendar_refs.append(calendar_map[service_id])
        return trips, route_refs, calendar_refs

    def _parse_stop_times(
        self,
        zf: zipfile.ZipFile,
        file_names: list[str],
        trip_map: dict[str, Trip],
        stop_map: dict[str, int],
        stops: list[Stop],
    ) -> tuple[list[StopTime], list[Trip], list[Stop | None], int]:
        """Parse stop_times.txt.

        Args:
            zf: Open ZipFile instance.
            file_names: List of files in the ZIP.
            trip_map: Mapping of GTFS trip_id to Trip instances.
            stop_map: Mapping of GTFS stop_id to index in stops list (if fresh DB)
                or database stop.id integers (if stops exist).
            stops: List of parsed Stop objects (empty if stops already in DB).

        Returns:
            Tuple of (stop_times list, parallel trip refs, skipped count).
        """
        reader = self._read_csv(zf, "stop_times.txt")
        if reader is None:
            self.warnings.append("stop_times.txt not found")
            return [], [], [], 0
        _ = file_names
        stop_times: list[StopTime] = []
        trip_refs: list[Trip] = []
        # If stops were parsed from GTFS, stop_map values are list indices.
        # We store the Stop object reference; the service will resolve after flush.
        uses_stop_objects = len(stops) > 0
        stop_refs: list[Stop | None] = []
        skipped = 0
        for row in reader:
            trip_id_str = row.get("trip_id", "")
            stop_id_str = row.get("stop_id", "")

            if trip_id_str not in trip_map:
                skipped += 1
                continue
            if stop_id_str not in stop_map:
                skipped += 1
                continue

            seq_str = row.get("stop_sequence", "0")
            sequence = int(seq_str) if seq_str.isdigit() else 0

            pickup_str = row.get("pickup_type", "0")
            pickup = int(pickup_str) if pickup_str.isdigit() else 0

            dropoff_str = row.get("drop_off_type", "0")
            dropoff = int(dropoff_str) if dropoff_str.isdigit() else 0

            # stop_id: use real DB id if stops exist, otherwise placeholder (0)
            stop_db_id = 0 if uses_stop_objects else stop_map[stop_id_str]

            stop_times.append(
                StopTime(
                    trip_id=0,  # placeholder, resolved after trip flush
                    stop_id=stop_db_id,
                    stop_sequence=sequence,
                    arrival_time=row.get("arrival_time", "00:00:00"),
                    departure_time=row.get("departure_time", "00:00:00"),
                    pickup_type=pickup,
                    drop_off_type=dropoff,
                )
            )
            trip_refs.append(trip_map[trip_id_str])
            stop_refs.append(stops[stop_map[stop_id_str]] if uses_stop_objects else None)
        if skipped > 0:
            self.warnings.append(f"Skipped {skipped} stop_times with unknown trip or stop")
        return stop_times, trip_refs, stop_refs, skipped

    def _parse_shapes(self, zf: zipfile.ZipFile, file_names: list[str]) -> list[Shape]:
        """Parse shapes.txt.

        Args:
            zf: Open ZipFile instance.
            file_names: List of files in the ZIP.

        Returns:
            List of Shape model instances.
        """
        reader = self._read_csv(zf, "shapes.txt")
        if reader is None:
            return []
        _ = file_names
        shapes: list[Shape] = []
        for row in reader:
            shape_id = row.get("shape_id", "")
            if not shape_id:
                continue

            lat_str = row.get("shape_pt_lat", "")
            lon_str = row.get("shape_pt_lon", "")
            seq_str = row.get("shape_pt_sequence", "0")
            dist_str = row.get("shape_dist_traveled", "")

            try:
                lat = float(lat_str)
                lon = float(lon_str)
            except (ValueError, TypeError):
                self.warnings.append(
                    f"Skipping shape point {shape_id}/{seq_str}: invalid coordinates"
                )
                continue

            sequence = int(seq_str) if seq_str.isdigit() else 0
            dist_traveled: float | None = None
            if dist_str:
                try:
                    dist_traveled = float(dist_str)
                except (ValueError, TypeError):
                    pass

            shapes.append(
                Shape(
                    gtfs_shape_id=shape_id,
                    feed_id=self.feed_id,
                    shape_pt_lat=lat,
                    shape_pt_lon=lon,
                    shape_pt_sequence=sequence,
                    shape_dist_traveled=dist_traveled,
                )
            )
        return shapes

    def _parse_stops(self, zf: zipfile.ZipFile, file_names: list[str]) -> list[Stop]:
        """Parse stops.txt.

        Args:
            zf: Open ZipFile instance.
            file_names: List of files in the ZIP.

        Returns:
            List of Stop model instances.
        """
        reader = self._read_csv(zf, "stops.txt")
        if reader is None:
            self.warnings.append("stops.txt not found")
            return []
        _ = file_names
        stops: list[Stop] = []
        for row in reader:
            stop_id = row.get("stop_id", "")
            if not stop_id:
                continue

            lat_str = row.get("stop_lat", "")
            lon_str = row.get("stop_lon", "")
            lat = float(lat_str) if lat_str else None
            lon = float(lon_str) if lon_str else None

            loc_type_str = row.get("location_type", "0")
            location_type = int(loc_type_str) if loc_type_str.isdigit() else 0

            stops.append(
                Stop(
                    gtfs_stop_id=stop_id,
                    stop_name=row.get("stop_name", stop_id),
                    stop_lat=lat,
                    stop_lon=lon,
                    stop_desc=row.get("stop_desc") or None,
                    location_type=location_type,
                    wheelchair_boarding=0,
                    is_active=True,
                )
            )
        return stops


def _parse_gtfs_date(date_str: str) -> date | None:
    """Parse a GTFS date string (YYYYMMDD) to a date object.

    Args:
        date_str: Date in YYYYMMDD format.

    Returns:
        date object or None if parsing fails.
    """
    if len(date_str) != 8:
        return None
    try:
        return date(int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8]))
    except ValueError:
        return None
