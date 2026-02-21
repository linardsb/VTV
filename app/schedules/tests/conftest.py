"""Shared test fixtures for the schedules feature."""

from datetime import date
from unittest.mock import AsyncMock

import pytest

from app.schedules.models import (
    Agency,
    Calendar,
    CalendarDate,
    Route,
    StopTime,
    Trip,
)
from app.shared.models import utcnow


def make_agency(**overrides: object) -> Agency:
    """Factory to create an Agency model instance with sensible defaults.

    Args:
        **overrides: Field values to override defaults.

    Returns:
        An Agency instance with all fields populated.
    """
    now = utcnow()
    defaults: dict[str, object] = {
        "id": 1,
        "gtfs_agency_id": "RS",
        "agency_name": "Rigas Satiksme",
        "agency_url": "https://www.rigassatiksme.lv",
        "agency_timezone": "Europe/Riga",
        "agency_lang": "lv",
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    return Agency(**defaults)


def make_route(**overrides: object) -> Route:
    """Factory to create a Route model instance with sensible defaults.

    Args:
        **overrides: Field values to override defaults.

    Returns:
        A Route instance with all fields populated.
    """
    now = utcnow()
    defaults: dict[str, object] = {
        "id": 1,
        "gtfs_route_id": "bus_22",
        "agency_id": 1,
        "route_short_name": "22",
        "route_long_name": "Centrs - Jugla",
        "route_type": 3,
        "route_color": "FF0000",
        "route_text_color": "FFFFFF",
        "route_sort_order": None,
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    return Route(**defaults)


def make_calendar(**overrides: object) -> Calendar:
    """Factory to create a Calendar model instance with sensible defaults.

    Args:
        **overrides: Field values to override defaults.

    Returns:
        A Calendar instance with all fields populated.
    """
    now = utcnow()
    defaults: dict[str, object] = {
        "id": 1,
        "gtfs_service_id": "weekday_1",
        "monday": True,
        "tuesday": True,
        "wednesday": True,
        "thursday": True,
        "friday": True,
        "saturday": False,
        "sunday": False,
        "start_date": date(2026, 1, 1),
        "end_date": date(2026, 12, 31),
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    return Calendar(**defaults)


def make_calendar_date(**overrides: object) -> CalendarDate:
    """Factory to create a CalendarDate model instance with sensible defaults.

    Args:
        **overrides: Field values to override defaults.

    Returns:
        A CalendarDate instance with all fields populated.
    """
    now = utcnow()
    defaults: dict[str, object] = {
        "id": 1,
        "calendar_id": 1,
        "date": date(2026, 3, 15),
        "exception_type": 2,
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    return CalendarDate(**defaults)


def make_trip(**overrides: object) -> Trip:
    """Factory to create a Trip model instance with sensible defaults.

    Args:
        **overrides: Field values to override defaults.

    Returns:
        A Trip instance with all fields populated.
    """
    now = utcnow()
    defaults: dict[str, object] = {
        "id": 1,
        "gtfs_trip_id": "trip_22_1",
        "route_id": 1,
        "calendar_id": 1,
        "direction_id": 0,
        "trip_headsign": "Jugla",
        "block_id": None,
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    return Trip(**defaults)


def make_stop_time(**overrides: object) -> StopTime:
    """Factory to create a StopTime model instance with sensible defaults.

    Args:
        **overrides: Field values to override defaults.

    Returns:
        A StopTime instance with all fields populated.
    """
    now = utcnow()
    defaults: dict[str, object] = {
        "id": 1,
        "trip_id": 1,
        "stop_id": 1,
        "stop_sequence": 1,
        "arrival_time": "08:00:00",
        "departure_time": "08:01:00",
        "pickup_type": 0,
        "drop_off_type": 0,
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    return StopTime(**defaults)


@pytest.fixture
def sample_agency() -> Agency:
    """A single default agency instance."""
    return make_agency()


@pytest.fixture
def sample_route() -> Route:
    """A single default route instance."""
    return make_route()


@pytest.fixture
def sample_routes() -> list[Route]:
    """Multiple route instances for list tests."""
    return [
        make_route(id=1, gtfs_route_id="bus_22", route_short_name="22", route_type=3),
        make_route(id=2, gtfs_route_id="trol_14", route_short_name="14", route_type=11),
        make_route(id=3, gtfs_route_id="tram_1", route_short_name="1", route_type=0),
    ]


@pytest.fixture
def sample_calendar() -> Calendar:
    """A single default calendar instance."""
    return make_calendar()


@pytest.fixture
def sample_trip() -> Trip:
    """A single default trip instance."""
    return make_trip()


@pytest.fixture
def sample_stop_times() -> list[StopTime]:
    """Multiple stop times for a trip."""
    return [
        make_stop_time(id=1, stop_sequence=1, arrival_time="08:00:00", departure_time="08:01:00"),
        make_stop_time(
            id=2, stop_sequence=2, arrival_time="08:05:00", departure_time="08:06:00", stop_id=2
        ),
        make_stop_time(
            id=3, stop_sequence=3, arrival_time="08:10:00", departure_time="08:11:00", stop_id=3
        ),
        make_stop_time(
            id=4, stop_sequence=4, arrival_time="08:15:00", departure_time="08:16:00", stop_id=4
        ),
        make_stop_time(
            id=5, stop_sequence=5, arrival_time="08:20:00", departure_time="08:21:00", stop_id=5
        ),
    ]


@pytest.fixture
def mock_db() -> AsyncMock:
    """Mock AsyncSession for repository tests."""
    return AsyncMock()
