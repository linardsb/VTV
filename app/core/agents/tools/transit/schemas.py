"""Pydantic response schemas for transit tool outputs.

These models define the structured data returned by transit tools
(query_bus_status, get_route_schedule, search_stops, get_adherence_report).
The agent receives JSON-serialized versions of these models.
"""

from pydantic import BaseModel, ConfigDict


class Position(BaseModel):
    """Geographic position of a vehicle.

    Attributes:
        latitude: WGS84 latitude.
        longitude: WGS84 longitude.
        bearing: Compass bearing in degrees (0-360), if available.
        speed_kmh: Speed in km/h, if available.
    """

    model_config = ConfigDict(strict=True)

    latitude: float
    longitude: float
    bearing: float | None = None
    speed_kmh: float | None = None


class Alert(BaseModel):
    """A GTFS-RT ServiceAlert affecting a trip or route.

    Attributes:
        header: Short alert title.
        description: Detailed alert text, if available.
        cause: Alert cause category, if available.
        effect: Alert effect category, if available.
    """

    model_config = ConfigDict(strict=True)

    header: str
    description: str | None = None
    cause: str | None = None
    effect: str | None = None


class BusStatus(BaseModel):
    """Real-time status of a single bus.

    Attributes:
        vehicle_id: Fleet vehicle identifier.
        route_id: GTFS route identifier.
        route_short_name: Human-readable route number (e.g., "22").
        trip_id: GTFS trip identifier, if available.
        direction: Trip headsign or direction description, if available.
        current_status: Vehicle status relative to a stop.
        current_stop_name: Name of the current/nearest stop, if available.
        next_stop_name: Name of the next stop, if available.
        position: Geographic position, if available.
        delay_seconds: Schedule deviation in seconds (positive=late, negative=early).
        delay_description: Human-readable delay text.
        predicted_arrival: ISO 8601 predicted arrival at next stop, if available.
        timestamp: ISO 8601 when position data was measured.
        severity: Operational severity based on delay thresholds.
        alerts: Active ServiceAlerts affecting this trip/route.
    """

    model_config = ConfigDict(strict=True)

    vehicle_id: str
    route_id: str
    route_short_name: str
    trip_id: str | None = None
    direction: str | None = None
    current_status: str
    current_stop_name: str | None = None
    next_stop_name: str | None = None
    position: Position | None = None
    delay_seconds: int = 0
    delay_description: str = "on time"
    predicted_arrival: str | None = None
    timestamp: str = ""
    severity: str = "normal"
    alerts: list[Alert] = []


class HeadwayInfo(BaseModel):
    """Headway analysis for vehicles on a route.

    Attributes:
        average_headway_minutes: Average gap between consecutive vehicles.
        expected_headway_minutes: Planned headway from schedule, if known.
        headway_deviation_minutes: Difference from expected headway, if known.
        is_bunched: True if two vehicles are within 2 minutes of each other.
    """

    model_config = ConfigDict(strict=True)

    average_headway_minutes: float
    expected_headway_minutes: float | None = None
    headway_deviation_minutes: float | None = None
    is_bunched: bool = False


class RouteOverview(BaseModel):
    """Aggregate status of all vehicles on a route.

    Attributes:
        route_id: GTFS route identifier.
        route_short_name: Human-readable route number.
        active_vehicles: Count of vehicles currently active on this route.
        vehicles: Individual status of each active vehicle.
        average_delay_seconds: Mean delay across all vehicles.
        on_time_count: Vehicles within +/- 300 seconds of schedule.
        late_count: Vehicles more than 300 seconds late.
        early_count: Vehicles more than 300 seconds early.
        headway: Headway analysis, if enough vehicles for calculation.
        summary: Pre-formatted text summary for agent to relay to user.
    """

    model_config = ConfigDict(strict=True)

    route_id: str
    route_short_name: str
    active_vehicles: int
    vehicles: list[BusStatus]
    average_delay_seconds: float
    on_time_count: int
    late_count: int
    early_count: int
    headway: HeadwayInfo | None = None
    summary: str


class StopDeparture(BaseModel):
    """A single upcoming departure at a stop.

    Attributes:
        route_id: GTFS route identifier.
        route_short_name: Human-readable route number.
        vehicle_id: Fleet vehicle identifier, if available.
        trip_id: GTFS trip identifier, if available.
        predicted_arrival: ISO 8601 predicted arrival, if available.
        scheduled_arrival: ISO 8601 scheduled arrival, if available.
        delay_seconds: Schedule deviation in seconds.
        delay_description: Human-readable delay text.
    """

    model_config = ConfigDict(strict=True)

    route_id: str
    route_short_name: str
    vehicle_id: str | None = None
    trip_id: str | None = None
    predicted_arrival: str | None = None
    scheduled_arrival: str | None = None
    delay_seconds: int = 0
    delay_description: str = "on time"


class StopDepartures(BaseModel):
    """Upcoming departures at a specific stop.

    Attributes:
        stop_id: GTFS stop identifier.
        stop_name: Human-readable stop name.
        departures: List of upcoming departures sorted by arrival time.
        summary: Pre-formatted text summary for agent to relay to user.
    """

    model_config = ConfigDict(strict=True)

    stop_id: str
    stop_name: str
    departures: list[StopDeparture]
    summary: str


# --- Schedule schemas (get_route_schedule) ---


class ScheduleStop(BaseModel):
    """A stop within a scheduled trip.

    Attributes:
        stop_sequence: Order of stop within the trip.
        stop_id: GTFS stop identifier.
        stop_name: Human-readable stop name.
        arrival_time: Arrival time in HH:MM display format.
        departure_time: Departure time in HH:MM display format.
    """

    model_config = ConfigDict(strict=True)

    stop_sequence: int
    stop_id: str
    stop_name: str
    arrival_time: str
    departure_time: str


class TripSchedule(BaseModel):
    """A single scheduled trip with summary timing.

    Attributes:
        trip_id: GTFS trip identifier.
        direction_id: Direction (0=outbound, 1=inbound), if available.
        headsign: Trip destination label, if available.
        first_departure: HH:MM departure from first stop.
        last_arrival: HH:MM arrival at last stop.
        stop_count: Number of stops in this trip.
    """

    model_config = ConfigDict(strict=True)

    trip_id: str
    direction_id: int | None = None
    headsign: str | None = None
    first_departure: str
    last_arrival: str
    stop_count: int


class DirectionSchedule(BaseModel):
    """Schedule for one direction of a route.

    Attributes:
        direction_id: Direction (0=outbound, 1=inbound), if available.
        headsign: Typical destination label for this direction, if available.
        trip_count: Total number of trips in this direction.
        first_departure: HH:MM of the earliest trip departure.
        last_departure: HH:MM of the latest trip departure.
        trips: Individual trip schedules (may be truncated for token efficiency).
    """

    model_config = ConfigDict(strict=True)

    direction_id: int | None = None
    headsign: str | None = None
    trip_count: int
    first_departure: str
    last_departure: str
    trips: list[TripSchedule]


class RouteSchedule(BaseModel):
    """Full schedule for a route on a specific date.

    Attributes:
        route_id: GTFS route identifier.
        route_short_name: Human-readable route number (e.g., "22").
        route_long_name: Full route name (e.g., "Centrs - Jugla").
        service_date: ISO date (YYYY-MM-DD) the schedule applies to.
        service_type: Day classification ("weekday", "saturday", "sunday").
        trip_count: Total number of scheduled trips across all directions.
        directions: Schedule broken down by direction.
        summary: Pre-formatted text summary for agent to relay to user.
    """

    model_config = ConfigDict(strict=True)

    route_id: str
    route_short_name: str
    route_long_name: str
    service_date: str
    service_type: str
    trip_count: int
    directions: list[DirectionSchedule]
    summary: str


# --- Stop search schemas (search_stops) ---


class StopResult(BaseModel):
    """A single stop returned from a search.

    Attributes:
        stop_id: GTFS stop identifier (use with query_bus_status stop_departures).
        stop_name: Human-readable stop name.
        stop_lat: WGS84 latitude, if available.
        stop_lon: WGS84 longitude, if available.
        distance_meters: Distance from search point in meters (nearby action only).
        routes: List of route short names serving this stop, if available.
    """

    model_config = ConfigDict(strict=True)

    stop_id: str
    stop_name: str
    stop_lat: float | None = None
    stop_lon: float | None = None
    distance_meters: int | None = None
    routes: list[str] | None = None


class StopSearchResults(BaseModel):
    """Results from a stop search operation.

    Attributes:
        action: The search action that was performed.
        query: The search text (for search action).
        result_count: Number of stops returned.
        total_matches: Total matches before limit was applied.
        stops: List of matching stops.
        summary: Pre-formatted text summary for agent to relay to user.
    """

    model_config = ConfigDict(strict=True)

    action: str
    query: str | None = None
    result_count: int
    total_matches: int
    stops: list[StopResult]
    summary: str


# --- Adherence report schemas (get_adherence_report) ---


class TripAdherence(BaseModel):
    """On-time status for a single scheduled trip.

    Attributes:
        trip_id: GTFS trip identifier.
        direction_id: Direction (0=outbound, 1=inbound), if available.
        headsign: Trip destination label, if available.
        scheduled_departure: HH:MM planned first stop departure.
        delay_seconds: Current schedule deviation (positive=late, negative=early).
        delay_description: Human-readable delay text.
        status: One of "on_time", "late", "early", "no_data".
        vehicle_id: Fleet vehicle on this trip, if known.
    """

    model_config = ConfigDict(strict=True)

    trip_id: str
    direction_id: int | None = None
    headsign: str | None = None
    scheduled_departure: str = "--:--"
    delay_seconds: int = 0
    delay_description: str = "on time"
    status: str = "on_time"
    vehicle_id: str | None = None


class RouteAdherence(BaseModel):
    """Aggregated on-time performance metrics for a single route.

    Attributes:
        route_id: GTFS route identifier.
        route_short_name: Human-readable route number.
        scheduled_trips: Total trips scheduled for the analysis period.
        tracked_trips: Trips with real-time data available.
        on_time_count: Trips within +/- 300 seconds of schedule.
        late_count: Trips more than 300 seconds late.
        early_count: Trips more than 300 seconds early.
        no_data_count: Scheduled trips without real-time data.
        on_time_percentage: Percentage of tracked trips that are on time.
        average_delay_seconds: Mean delay across tracked trips.
        worst_trip: Trip with highest absolute delay, if any tracked.
        trips: Individual trip details (may be truncated for token efficiency).
    """

    model_config = ConfigDict(strict=True)

    route_id: str
    route_short_name: str
    scheduled_trips: int
    tracked_trips: int
    on_time_count: int
    late_count: int
    early_count: int
    no_data_count: int
    on_time_percentage: float
    average_delay_seconds: float
    worst_trip: TripAdherence | None = None
    trips: list[TripAdherence] = []


class AdherenceReport(BaseModel):
    """On-time performance report for a route or the transit network.

    Attributes:
        report_type: "route" for single-route or "network" for all routes.
        route_id: GTFS route identifier (single-route report only).
        service_date: ISO date (YYYY-MM-DD) the report covers.
        service_type: Day classification ("weekday", "saturday", "sunday").
        time_from: Start of analysis window if filtered, else None.
        time_until: End of analysis window if filtered, else None.
        routes: Per-route metrics (one for route report, many for network).
        network_on_time_percentage: Overall network on-time % (network only).
        network_average_delay_seconds: Overall network avg delay (network only).
        summary: Pre-formatted text summary for agent to relay to user.
    """

    model_config = ConfigDict(strict=True)

    report_type: str
    route_id: str | None = None
    service_date: str
    service_type: str
    time_from: str | None = None
    time_until: str | None = None
    routes: list[RouteAdherence]
    network_on_time_percentage: float | None = None
    network_average_delay_seconds: float | None = None
    summary: str


# --- Driver availability schemas (check_driver_availability) ---


class DriverInfo(BaseModel):
    """Information about a single driver and their availability.

    Attributes:
        driver_id: Unique driver identifier (e.g., "DRV-001").
        name: Driver display name (e.g., "J. Bērziņš").
        license_categories: License categories held (e.g., ["D", "D1"]).
        qualified_route_ids: GTFS route IDs this driver is certified to operate.
        shift: Assigned shift ("morning", "afternoon", "evening", "night").
        status: Availability status ("available", "on_duty", "on_leave", "sick").
        phone: Contact phone number, if available.
        notes: Special notes (e.g., "overtime eligible", "trainee").
    """

    model_config = ConfigDict(strict=True)

    driver_id: str
    name: str
    license_categories: list[str]
    qualified_route_ids: list[str]
    shift: str
    status: str
    phone: str | None = None
    notes: str | None = None


class ShiftSummary(BaseModel):
    """Aggregate driver counts for a single shift.

    Attributes:
        shift: Shift name ("morning", "afternoon", "evening", "night").
        total_drivers: Total drivers assigned to this shift.
        available_count: Drivers with "available" status.
        on_duty_count: Drivers currently on duty.
        on_leave_count: Drivers on planned leave.
        sick_count: Drivers on sick leave.
    """

    model_config = ConfigDict(strict=True)

    shift: str
    total_drivers: int
    available_count: int
    on_duty_count: int
    on_leave_count: int
    sick_count: int


class DriverAvailabilityReport(BaseModel):
    """Driver availability report for a date, optionally filtered by shift/route.

    Attributes:
        report_date: ISO date (YYYY-MM-DD) the report covers.
        service_type: Day classification ("weekday", "saturday", "sunday").
        shift_filter: Shift filter applied, or None for all shifts.
        route_filter: Route filter applied, or None for all routes.
        total_drivers: Total matching drivers.
        available_count: Drivers available for assignment.
        shifts: Per-shift breakdown of driver counts.
        drivers: Individual driver details (capped for token efficiency).
        summary: Pre-formatted text summary for agent to relay to user.
    """

    model_config = ConfigDict(strict=True)

    report_date: str
    service_type: str
    shift_filter: str | None = None
    route_filter: str | None = None
    total_drivers: int
    available_count: int
    shifts: list[ShiftSummary]
    drivers: list[DriverInfo]
    summary: str
