"""GTFS ZIP export from database.

Generates a valid GTFS ZIP file containing:
- agency.txt, routes.txt, calendar.txt, calendar_dates.txt,
  trips.txt, stop_times.txt, stops.txt
"""

import csv
import io
import zipfile

from app.schedules.models import Agency, Calendar, CalendarDate, Route, Shape, StopTime, Trip
from app.stops.models import Stop


def _bool_to_gtfs(value: bool) -> str:
    """Convert boolean to GTFS "1"/"0"."""
    return "1" if value else "0"


def _date_to_gtfs(d: object) -> str:
    """Convert date to GTFS YYYYMMDD format (no hyphens)."""
    return str(d).replace("-", "")


def _write_csv(rows: list[dict[str, str]], fieldnames: list[str]) -> str:
    """Write rows to a CSV string."""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


class GTFSExporter:
    """Generates a GTFS-compliant ZIP file from database model instances."""

    def __init__(
        self,
        *,
        agencies: list[Agency],
        routes: list[Route],
        calendars: list[Calendar],
        calendar_dates: list[CalendarDate],
        trips: list[Trip],
        stop_times: list[StopTime],
        stops: list[Stop],
        shapes: list[Shape] | None = None,
    ) -> None:
        self.agencies = agencies
        self.routes = routes
        self.calendars = calendars
        self.calendar_dates = calendar_dates
        self.trips = trips
        self.stop_times = stop_times
        self.stops = stops
        self.shapes = shapes or []

        # Build lookup maps for GTFS IDs
        self._agency_gtfs: dict[int, str] = {a.id: a.gtfs_agency_id for a in agencies}
        self._route_gtfs: dict[int, str] = {r.id: r.gtfs_route_id for r in routes}
        self._calendar_gtfs: dict[int, str] = {c.id: c.gtfs_service_id for c in calendars}
        self._trip_gtfs: dict[int, str] = {t.id: t.gtfs_trip_id for t in trips}
        self._stop_gtfs: dict[int, str] = {s.id: s.gtfs_stop_id for s in stops}

    def export(self) -> bytes:
        """Generate GTFS ZIP bytes."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("agency.txt", self._agency_csv())
            zf.writestr("routes.txt", self._routes_csv())
            zf.writestr("calendar.txt", self._calendar_csv())
            if self.calendar_dates:
                zf.writestr("calendar_dates.txt", self._calendar_dates_csv())
            zf.writestr("trips.txt", self._trips_csv())
            zf.writestr("stop_times.txt", self._stop_times_csv())
            zf.writestr("stops.txt", self._stops_csv())
            if self.shapes:
                zf.writestr("shapes.txt", self._shapes_csv())
        return buf.getvalue()

    def _agency_csv(self) -> str:
        fields = ["agency_id", "agency_name", "agency_url", "agency_timezone", "agency_lang"]
        rows = [
            {
                "agency_id": a.gtfs_agency_id,
                "agency_name": a.agency_name,
                "agency_url": a.agency_url or "",
                "agency_timezone": a.agency_timezone,
                "agency_lang": a.agency_lang or "",
            }
            for a in self.agencies
        ]
        return _write_csv(rows, fields)

    def _routes_csv(self) -> str:
        fields = [
            "route_id",
            "agency_id",
            "route_short_name",
            "route_long_name",
            "route_type",
            "route_color",
            "route_text_color",
            "route_sort_order",
        ]
        rows = [
            {
                "route_id": r.gtfs_route_id,
                "agency_id": self._agency_gtfs.get(r.agency_id, ""),
                "route_short_name": r.route_short_name,
                "route_long_name": r.route_long_name,
                "route_type": str(r.route_type),
                "route_color": r.route_color or "",
                "route_text_color": r.route_text_color or "",
                "route_sort_order": str(r.route_sort_order)
                if r.route_sort_order is not None
                else "",
            }
            for r in self.routes
        ]
        return _write_csv(rows, fields)

    def _calendar_csv(self) -> str:
        fields = [
            "service_id",
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
            "start_date",
            "end_date",
        ]
        rows = [
            {
                "service_id": c.gtfs_service_id,
                "monday": _bool_to_gtfs(c.monday),
                "tuesday": _bool_to_gtfs(c.tuesday),
                "wednesday": _bool_to_gtfs(c.wednesday),
                "thursday": _bool_to_gtfs(c.thursday),
                "friday": _bool_to_gtfs(c.friday),
                "saturday": _bool_to_gtfs(c.saturday),
                "sunday": _bool_to_gtfs(c.sunday),
                "start_date": _date_to_gtfs(c.start_date),
                "end_date": _date_to_gtfs(c.end_date),
            }
            for c in self.calendars
        ]
        return _write_csv(rows, fields)

    def _calendar_dates_csv(self) -> str:
        fields = ["service_id", "date", "exception_type"]
        rows = [
            {
                "service_id": self._calendar_gtfs.get(cd.calendar_id, ""),
                "date": _date_to_gtfs(cd.date),
                "exception_type": str(cd.exception_type),
            }
            for cd in self.calendar_dates
        ]
        return _write_csv(rows, fields)

    def _trips_csv(self) -> str:
        fields = [
            "route_id",
            "service_id",
            "trip_id",
            "trip_headsign",
            "direction_id",
            "block_id",
            "shape_id",
        ]
        rows = [
            {
                "route_id": self._route_gtfs.get(t.route_id, ""),
                "service_id": self._calendar_gtfs.get(t.calendar_id, ""),
                "trip_id": t.gtfs_trip_id,
                "trip_headsign": t.trip_headsign or "",
                "direction_id": str(t.direction_id) if t.direction_id is not None else "",
                "block_id": t.block_id or "",
                "shape_id": t.shape_id or "",
            }
            for t in self.trips
        ]
        return _write_csv(rows, fields)

    def _stop_times_csv(self) -> str:
        fields = [
            "trip_id",
            "arrival_time",
            "departure_time",
            "stop_id",
            "stop_sequence",
            "pickup_type",
            "drop_off_type",
        ]
        rows = [
            {
                "trip_id": self._trip_gtfs.get(st.trip_id, ""),
                "arrival_time": st.arrival_time,
                "departure_time": st.departure_time,
                "stop_id": self._stop_gtfs.get(st.stop_id, ""),
                "stop_sequence": str(st.stop_sequence),
                "pickup_type": str(st.pickup_type),
                "drop_off_type": str(st.drop_off_type),
            }
            for st in self.stop_times
        ]
        return _write_csv(rows, fields)

    def _stops_csv(self) -> str:
        fields = [
            "stop_id",
            "stop_name",
            "stop_lat",
            "stop_lon",
            "stop_desc",
            "location_type",
            "parent_station",
            "wheelchair_boarding",
        ]
        rows = [
            {
                "stop_id": s.gtfs_stop_id,
                "stop_name": s.stop_name,
                "stop_lat": str(s.stop_lat) if s.stop_lat is not None else "",
                "stop_lon": str(s.stop_lon) if s.stop_lon is not None else "",
                "stop_desc": s.stop_desc or "",
                "location_type": str(s.location_type),
                "parent_station": self._stop_gtfs.get(s.parent_station_id, "")
                if s.parent_station_id is not None
                else "",
                "wheelchair_boarding": str(s.wheelchair_boarding),
            }
            for s in self.stops
        ]
        return _write_csv(rows, fields)

    def _shapes_csv(self) -> str:
        """Generate shapes.txt CSV content."""
        fields = [
            "shape_id",
            "shape_pt_lat",
            "shape_pt_lon",
            "shape_pt_sequence",
            "shape_dist_traveled",
        ]
        rows = [
            {
                "shape_id": s.gtfs_shape_id,
                "shape_pt_lat": str(s.shape_pt_lat),
                "shape_pt_lon": str(s.shape_pt_lon),
                "shape_pt_sequence": str(s.shape_pt_sequence),
                "shape_dist_traveled": str(s.shape_dist_traveled)
                if s.shape_dist_traveled is not None
                else "",
            }
            for s in self.shapes
        ]
        return _write_csv(rows, fields)
