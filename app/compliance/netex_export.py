"""NeTEx (Network Timetable Exchange) XML export.

Generates a PublicationDelivery XML document conforming to the European
Passenger Information Profile (EPIP). Transforms GTFS-aligned database
models into four NeTEx frames: ResourceFrame (operators), SiteFrame
(stop places), ServiceFrame (lines, day types), and TimetableFrame
(service journeys with calls).
"""

from collections import defaultdict
from datetime import UTC, datetime

from lxml import etree

from app.compliance.xml_namespaces import GML_NS, NETEX_NS, NETEX_NSMAP
from app.core.logging import get_logger
from app.schedules.models import Agency, Calendar, CalendarDate, Route, StopTime, Trip
from app.stops.models import Stop

logger = get_logger(__name__)

# GTFS route_type -> NeTEx TransportMode mapping
_ROUTE_TYPE_MAP: dict[int, str] = {
    0: "tram",
    1: "metro",
    2: "rail",
    3: "bus",
    4: "water",
    5: "cableway",
    6: "gondola",
    7: "funicular",
    11: "trolleyBus",
    12: "monorail",
}

# NeTEx day-of-week names matching Calendar boolean fields
_DAY_FIELDS: list[tuple[str, str]] = [
    ("monday", "Monday"),
    ("tuesday", "Tuesday"),
    ("wednesday", "Wednesday"),
    ("thursday", "Thursday"),
    ("friday", "Friday"),
    ("saturday", "Saturday"),
    ("sunday", "Sunday"),
]

# Wheelchair boarding -> NeTEx accessibility value
_WHEELCHAIR_MAP: dict[int, str] = {
    0: "unknown",
    1: "true",
    2: "false",
}


def _netex_id(codespace: str, element_type: str, local_id: str) -> str:
    """Build a NeTEx-compliant element ID.

    Args:
        codespace: Codespace prefix (e.g. "VTV").
        element_type: NeTEx element type (e.g. "Operator", "StopPlace").
        local_id: Local identifier (usually a GTFS ID).

    Returns:
        Formatted NeTEx ID string.
    """
    return f"{codespace}:{element_type}:{local_id}"


def _sub(parent: etree._Element, tag: str, text: str | None = None) -> etree._Element:
    """Create a namespaced sub-element under parent.

    Uses the default NeTEx namespace so tags render without prefix.

    Args:
        parent: Parent XML element.
        tag: Local tag name (without namespace).
        text: Optional text content.

    Returns:
        The created sub-element.
    """
    el = etree.SubElement(parent, f"{{{NETEX_NS}}}{tag}")
    if text is not None:
        el.text = text
    return el


class NeTExExporter:
    """Generates a NeTEx EPIP-compliant PublicationDelivery XML document.

    Follows the same constructor pattern as GTFSExporter: receives all
    model lists, builds internal lookup maps, and returns XML bytes.

    Args:
        agencies: List of Agency model instances.
        routes: List of Route model instances.
        calendars: List of Calendar model instances.
        calendar_dates: List of CalendarDate model instances.
        trips: List of Trip model instances.
        stop_times: List of StopTime model instances.
        stops: List of Stop model instances.
        codespace: NeTEx codespace prefix for element IDs.
    """

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
        codespace: str,
    ) -> None:
        self.agencies = agencies
        self.routes = routes
        self.calendars = calendars
        self.calendar_dates = calendar_dates
        self.trips = trips
        self.stop_times = stop_times
        self.stops = stops
        self._cs = codespace

        # Build lookup maps (same pattern as GTFSExporter)
        self._agency_gtfs: dict[int, str] = {a.id: a.gtfs_agency_id for a in agencies}
        self._route_gtfs: dict[int, str] = {r.id: r.gtfs_route_id for r in routes}
        self._calendar_gtfs: dict[int, str] = {c.id: c.gtfs_service_id for c in calendars}
        self._trip_gtfs: dict[int, str] = {t.id: t.gtfs_trip_id for t in trips}
        self._stop_gtfs: dict[int, str] = {s.id: s.gtfs_stop_id for s in stops}

        # Route -> agency map for OperatorRef
        self._route_agency: dict[int, int] = {r.id: r.agency_id for r in routes}

        # Trip -> route/calendar maps for LineRef/DayTypeRef
        self._trip_route: dict[int, int] = {t.id: t.route_id for t in trips}
        self._trip_calendar: dict[int, int] = {t.id: t.calendar_id for t in trips}

        # Group stop_times by trip_id for efficient TimetableFrame building
        self._stop_times_by_trip: dict[int, list[StopTime]] = defaultdict(list)
        for st in stop_times:
            self._stop_times_by_trip[st.trip_id].append(st)
        # Sort each group by stop_sequence
        for st_list in self._stop_times_by_trip.values():
            st_list.sort(key=lambda s: s.stop_sequence)

    def export(self) -> bytes:
        """Generate NeTEx XML bytes.

        Returns:
            UTF-8 encoded XML document with XML declaration.
        """
        logger.info(
            "compliance.netex.export_started",
            agency_count=len(self.agencies),
            route_count=len(self.routes),
            stop_count=len(self.stops),
            trip_count=len(self.trips),
        )
        root = self._build_publication_delivery()
        result: bytes = etree.tostring(
            root, xml_declaration=True, encoding="UTF-8", pretty_print=True
        )
        logger.info(
            "compliance.netex.export_completed",
            byte_size=len(result),
        )
        return result

    def _build_publication_delivery(self) -> etree._Element:
        """Build the root PublicationDelivery element with all frames."""
        root = etree.Element(
            f"{{{NETEX_NS}}}PublicationDelivery",
            nsmap=NETEX_NSMAP,  # type: ignore[arg-type]  # lxml accepts None keys
        )
        root.set("version", "1.2")

        _sub(root, "PublicationTimestamp", datetime.now(UTC).isoformat())
        _sub(root, "ParticipantRef", self._cs)

        data_objects = _sub(root, "dataObjects")
        composite = _sub(data_objects, "CompositeFrame")
        composite.set("id", _netex_id(self._cs, "CompositeFrame", "main"))
        composite.set("version", "1")

        frames = _sub(composite, "frames")
        self._build_resource_frame(frames)
        self._build_site_frame(frames)
        self._build_service_frame(frames)
        self._build_timetable_frame(frames)

        return root

    # --- ResourceFrame: Operators ---

    def _build_resource_frame(self, frames: etree._Element) -> None:
        """Build ResourceFrame with Operator elements from agencies."""
        frame = _sub(frames, "ResourceFrame")
        frame.set("id", _netex_id(self._cs, "ResourceFrame", "RF01"))
        frame.set("version", "1")

        organisations = _sub(frame, "organisations")
        for agency in self.agencies:
            operator = _sub(organisations, "Operator")
            operator.set("id", _netex_id(self._cs, "Operator", agency.gtfs_agency_id))
            operator.set("version", "1")
            _sub(operator, "Name", agency.agency_name)

            if agency.agency_url:
                contact = _sub(operator, "ContactDetails")
                _sub(contact, "Url", agency.agency_url)

            if agency.agency_lang:
                locale = _sub(operator, "Locale")
                _sub(locale, "DefaultLanguage", agency.agency_lang)

    # --- SiteFrame: StopPlaces and ScheduledStopPoints ---

    def _build_site_frame(self, frames: etree._Element) -> None:
        """Build SiteFrame with StopPlace and ScheduledStopPoint elements."""
        frame = _sub(frames, "SiteFrame")
        frame.set("id", _netex_id(self._cs, "SiteFrame", "SF01"))
        frame.set("version", "1")

        stop_places = _sub(frame, "stopPlaces")
        scheduled_points = _sub(frame, "scheduledStopPoints")

        for stop in self.stops:
            if stop.location_type == 1:
                self._build_stop_place(stop_places, stop)
            else:
                self._build_scheduled_stop_point(scheduled_points, stop)

    def _build_stop_place(self, parent: etree._Element, stop: Stop) -> None:
        """Build a StopPlace element for station/terminus stops."""
        sp = _sub(parent, "StopPlace")
        sp.set("id", _netex_id(self._cs, "StopPlace", stop.gtfs_stop_id))
        sp.set("version", "1")
        _sub(sp, "Name", stop.stop_name)

        if stop.stop_desc:
            _sub(sp, "Description", stop.stop_desc)

        if stop.stop_lat is not None and stop.stop_lon is not None:
            centroid = _sub(sp, "Centroid")
            location = _sub(centroid, "Location")
            lon_el = etree.SubElement(location, f"{{{GML_NS}}}pos")
            lon_el.text = f"{stop.stop_lat} {stop.stop_lon}"

        accessibility_value = _WHEELCHAIR_MAP.get(stop.wheelchair_boarding, "unknown")
        if accessibility_value != "unknown":
            access = _sub(sp, "AccessibilityAssessment")
            access.set("id", _netex_id(self._cs, "AccessibilityAssessment", stop.gtfs_stop_id))
            access.set("version", "1")
            _sub(access, "MobilityImpairedAccess", accessibility_value)

    def _build_scheduled_stop_point(self, parent: etree._Element, stop: Stop) -> None:
        """Build a ScheduledStopPoint element for regular stops."""
        ssp = _sub(parent, "ScheduledStopPoint")
        ssp.set("id", _netex_id(self._cs, "ScheduledStopPoint", stop.gtfs_stop_id))
        ssp.set("version", "1")
        _sub(ssp, "Name", stop.stop_name)

        if stop.stop_desc:
            _sub(ssp, "Description", stop.stop_desc)

        if stop.stop_lat is not None and stop.stop_lon is not None:
            location = _sub(ssp, "Location")
            _sub(location, "Longitude", str(stop.stop_lon))
            _sub(location, "Latitude", str(stop.stop_lat))

    # --- ServiceFrame: Lines and DayTypes ---

    def _build_service_frame(self, frames: etree._Element) -> None:
        """Build ServiceFrame with Line and DayType elements."""
        frame = _sub(frames, "ServiceFrame")
        frame.set("id", _netex_id(self._cs, "ServiceFrame", "SVF01"))
        frame.set("version", "1")

        # Lines (from Routes)
        lines = _sub(frame, "lines")
        for route in self.routes:
            self._build_line(lines, route)

        # DayTypes (from Calendars)
        day_types = _sub(frame, "dayTypes")
        for calendar in self.calendars:
            self._build_day_type(day_types, calendar)

        # OperatingPeriods (from Calendars)
        if self.calendars:
            op_periods = _sub(frame, "operatingPeriods")
            for calendar in self.calendars:
                period = _sub(op_periods, "OperatingPeriod")
                period.set(
                    "id",
                    _netex_id(self._cs, "OperatingPeriod", calendar.gtfs_service_id),
                )
                period.set("version", "1")
                _sub(period, "FromDate", str(calendar.start_date))
                _sub(period, "ToDate", str(calendar.end_date))

        # DayTypeAssignments (from CalendarDates)
        if self.calendar_dates:
            assignments = _sub(frame, "dayTypeAssignments")
            for i, cd in enumerate(self.calendar_dates):
                service_id = self._calendar_gtfs.get(cd.calendar_id, "unknown")
                assignment = _sub(assignments, "DayTypeAssignment")
                assignment.set(
                    "id",
                    _netex_id(self._cs, "DayTypeAssignment", f"{service_id}_{i}"),
                )
                assignment.set("version", "1")
                assignment.set("order", str(i + 1))
                _sub(assignment, "Date", str(cd.date))
                day_type_ref = _sub(assignment, "DayTypeRef")
                day_type_ref.set("ref", _netex_id(self._cs, "DayType", service_id))
                _sub(
                    assignment,
                    "isAvailable",
                    "true" if cd.exception_type == 1 else "false",
                )

    def _build_line(self, parent: etree._Element, route: Route) -> None:
        """Build a Line element from a Route model."""
        line = _sub(parent, "Line")
        line.set("id", _netex_id(self._cs, "Line", route.gtfs_route_id))
        line.set("version", "1")
        _sub(line, "Name", route.route_long_name)
        _sub(line, "ShortName", route.route_short_name)
        _sub(line, "TransportMode", _gtfs_route_type_to_netex(route.route_type))

        if route.route_color or route.route_text_color:
            presentation = _sub(line, "Presentation")
            if route.route_color:
                _sub(presentation, "Colour", route.route_color)
            if route.route_text_color:
                _sub(presentation, "TextColour", route.route_text_color)

        agency_id = self._agency_gtfs.get(route.agency_id)
        if agency_id:
            op_ref = _sub(line, "OperatorRef")
            op_ref.set("ref", _netex_id(self._cs, "Operator", agency_id))

    def _build_day_type(self, parent: etree._Element, calendar: Calendar) -> None:
        """Build a DayType element from a Calendar model."""
        day_type = _sub(parent, "DayType")
        day_type.set("id", _netex_id(self._cs, "DayType", calendar.gtfs_service_id))
        day_type.set("version", "1")

        props = _sub(day_type, "properties")
        prop = _sub(props, "PropertyOfDay")
        days_of_week = _sub(prop, "DaysOfWeek")

        active_days: list[str] = []
        for field_name, netex_name in _DAY_FIELDS:
            if getattr(calendar, field_name, False):
                active_days.append(netex_name)

        days_of_week.text = " ".join(active_days) if active_days else "Everyday"

    # --- TimetableFrame: ServiceJourneys ---

    def _build_timetable_frame(self, frames: etree._Element) -> None:
        """Build TimetableFrame with ServiceJourney elements."""
        frame = _sub(frames, "TimetableFrame")
        frame.set("id", _netex_id(self._cs, "TimetableFrame", "TF01"))
        frame.set("version", "1")

        journeys = _sub(frame, "vehicleJourneys")
        for trip in self.trips:
            self._build_service_journey(journeys, trip)

    def _build_service_journey(self, parent: etree._Element, trip: Trip) -> None:
        """Build a ServiceJourney element from a Trip model."""
        sj = _sub(parent, "ServiceJourney")
        sj.set("id", _netex_id(self._cs, "ServiceJourney", trip.gtfs_trip_id))
        sj.set("version", "1")

        # LineRef
        route_gtfs = self._route_gtfs.get(trip.route_id)
        if route_gtfs:
            line_ref = _sub(sj, "LineRef")
            line_ref.set("ref", _netex_id(self._cs, "Line", route_gtfs))

        # DayTypeRef
        cal_gtfs = self._calendar_gtfs.get(trip.calendar_id)
        if cal_gtfs:
            dt_ref = _sub(sj, "DayTypeRef")
            dt_ref.set("ref", _netex_id(self._cs, "DayType", cal_gtfs))

        # Direction
        if trip.direction_id is not None:
            _sub(sj, "DirectionType", "outbound" if trip.direction_id == 0 else "inbound")

        # Headsign
        if trip.trip_headsign:
            _sub(sj, "DestinationDisplay", trip.trip_headsign)

        # Calls (stop times)
        trip_stops = self._stop_times_by_trip.get(trip.id, [])
        if trip_stops:
            calls = _sub(sj, "calls")
            for st in trip_stops:
                self._build_call(calls, st)

    def _build_call(self, parent: etree._Element, st: StopTime) -> None:
        """Build a Call element from a StopTime model."""
        call = _sub(parent, "Call")
        call.set("order", str(st.stop_sequence))

        # ScheduledStopPointRef
        stop_gtfs = self._stop_gtfs.get(st.stop_id)
        if stop_gtfs:
            ref = _sub(call, "ScheduledStopPointRef")
            ref.set("ref", _netex_id(self._cs, "ScheduledStopPoint", stop_gtfs))

        # Arrival
        if st.arrival_time:
            arrival = _sub(call, "Arrival")
            _sub(arrival, "Time", st.arrival_time)

        # Departure
        if st.departure_time:
            departure = _sub(call, "Departure")
            _sub(departure, "Time", st.departure_time)

        # Request stop derived from pickup/drop-off type
        if st.pickup_type == 3 or st.drop_off_type == 3:
            _sub(call, "RequestStop", "true")


def _gtfs_route_type_to_netex(route_type: int) -> str:
    """Map a GTFS route_type integer to a NeTEx TransportMode string.

    Args:
        route_type: GTFS route type (0-12).

    Returns:
        NeTEx TransportMode string, defaults to "bus" for unknown types.
    """
    return _ROUTE_TYPE_MAP.get(route_type, "bus")
