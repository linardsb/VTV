"""Pydantic response schemas for transit tool outputs.

These models define the structured data returned by transit tools
(query_bus_status, get_route_schedule). The agent receives
JSON-serialized versions of these models.
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
