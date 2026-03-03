"""Shared test fixtures for compliance export tests.

All fixtures create in-memory model instances — no database session needed.
IDs are set manually for FK resolution in tests.
"""

import datetime

import pytest

from app.schedules.models import Agency, Calendar, CalendarDate, Route, StopTime, Trip
from app.stops.models import Stop
from app.transit.schemas import VehiclePosition


@pytest.fixture
def sample_agency() -> Agency:
    """Create a test Agency model instance."""
    agency = Agency()
    agency.id = 1
    agency.gtfs_agency_id = "TEST_AGENCY"
    agency.agency_name = "Test Transit Agency"
    agency.agency_url = "https://test-agency.example.com"
    agency.agency_timezone = "Europe/Riga"
    agency.agency_lang = "lv"
    return agency


@pytest.fixture
def sample_route(sample_agency: Agency) -> Route:
    """Create a test Route model instance linked to the sample agency."""
    route = Route()
    route.id = 1
    route.gtfs_route_id = "R1"
    route.agency_id = sample_agency.id
    route.route_short_name = "22"
    route.route_long_name = "Centrs - Imanta"
    route.route_type = 3  # bus
    route.route_color = "FF0000"
    route.route_text_color = "FFFFFF"
    route.route_sort_order = None
    route.is_active = True
    return route


@pytest.fixture
def sample_stop() -> Stop:
    """Create a test Stop model instance with location data."""
    stop = Stop()
    stop.id = 1
    stop.gtfs_stop_id = "S1"
    stop.stop_name = "Centrālā stacija"
    stop.stop_lat = 56.9496
    stop.stop_lon = 24.1134
    stop.location_type = 0
    stop.wheelchair_boarding = 1
    stop.is_active = True
    return stop


@pytest.fixture
def sample_station_stop() -> Stop:
    """Create a test Stop with location_type=1 (station)."""
    stop = Stop()
    stop.id = 2
    stop.gtfs_stop_id = "S2"
    stop.stop_name = "Centrālā stacija (stacija)"
    stop.stop_lat = 56.9497
    stop.stop_lon = 24.1135
    stop.location_type = 1
    stop.wheelchair_boarding = 1
    stop.is_active = True
    return stop


@pytest.fixture
def sample_calendar() -> Calendar:
    """Create a test Calendar with weekday service."""
    calendar = Calendar()
    calendar.id = 1
    calendar.gtfs_service_id = "WD"
    calendar.monday = True
    calendar.tuesday = True
    calendar.wednesday = True
    calendar.thursday = True
    calendar.friday = True
    calendar.saturday = False
    calendar.sunday = False
    calendar.start_date = datetime.date(2026, 1, 1)
    calendar.end_date = datetime.date(2026, 12, 31)
    return calendar


@pytest.fixture
def sample_calendar_date(sample_calendar: Calendar) -> CalendarDate:
    """Create a test CalendarDate exception."""
    cd = CalendarDate()
    cd.id = 1
    cd.calendar_id = sample_calendar.id
    cd.date = datetime.date(2026, 5, 1)
    cd.exception_type = 2  # removed
    return cd


@pytest.fixture
def sample_trip(sample_route: Route, sample_calendar: Calendar) -> Trip:
    """Create a test Trip linked to sample route and calendar."""
    trip = Trip()
    trip.id = 1
    trip.gtfs_trip_id = "T1"
    trip.route_id = sample_route.id
    trip.calendar_id = sample_calendar.id
    trip.direction_id = 0
    trip.trip_headsign = "Imanta"
    return trip


@pytest.fixture
def sample_stop_times(sample_trip: Trip, sample_stop: Stop) -> list[StopTime]:
    """Create test StopTimes for a trip with 3 stops."""
    times: list[StopTime] = []
    for i, (arr, dep) in enumerate(
        [("08:00:00", "08:01:00"), ("08:10:00", "08:11:00"), ("08:20:00", "08:20:00")]
    ):
        st = StopTime()
        st.id = i + 1
        st.trip_id = sample_trip.id
        st.stop_id = sample_stop.id
        st.stop_sequence = i + 1
        st.arrival_time = arr
        st.departure_time = dep
        st.pickup_type = 0
        st.drop_off_type = 0
        times.append(st)
    return times


@pytest.fixture
def sample_vehicle_position() -> VehiclePosition:
    """Create a test VehiclePosition schema instance."""
    return VehiclePosition(
        vehicle_id="4521",
        route_id="R1",
        route_short_name="22",
        route_type=3,
        latitude=56.9496,
        longitude=24.1134,
        bearing=180.0,
        speed_kmh=35.0,
        delay_seconds=120,
        current_status="IN_TRANSIT_TO",
        next_stop_name="Centrālā stacija",
        current_stop_name="Origo",
        timestamp="2026-03-03T12:00:00Z",
        feed_id="riga",
        operator_name="Rīgas Satiksme",
    )
