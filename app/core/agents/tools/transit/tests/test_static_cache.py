"""Tests for GTFSStaticCache schedule extensions (calendar, service resolution)."""

from datetime import date

from app.core.agents.tools.transit.static_cache import (
    CalendarDateException,
    CalendarEntry,
    GTFSStaticCache,
    RouteInfo,
    StopTimeEntry,
    TripInfo,
)


def _make_cache_with_calendar() -> GTFSStaticCache:
    """Create a GTFSStaticCache with calendar and calendar_dates populated."""
    cache = GTFSStaticCache()
    cache.calendar = [
        CalendarEntry(
            service_id="WD",
            monday=True,
            tuesday=True,
            wednesday=True,
            thursday=True,
            friday=True,
            saturday=False,
            sunday=False,
            start_date="20260101",
            end_date="20261231",
        ),
        CalendarEntry(
            service_id="SAT",
            monday=False,
            tuesday=False,
            wednesday=False,
            thursday=False,
            friday=False,
            saturday=True,
            sunday=False,
            start_date="20260101",
            end_date="20261231",
        ),
        CalendarEntry(
            service_id="SUN",
            monday=False,
            tuesday=False,
            wednesday=False,
            thursday=False,
            friday=False,
            saturday=False,
            sunday=True,
            start_date="20260101",
            end_date="20261231",
        ),
    ]
    cache.calendar_dates = []
    return cache


def test_get_active_service_ids_weekday():
    cache = _make_cache_with_calendar()
    # 2026-02-17 is a Tuesday
    result = cache.get_active_service_ids(date(2026, 2, 17))
    assert result == {"WD"}


def test_get_active_service_ids_saturday():
    cache = _make_cache_with_calendar()
    # 2026-02-21 is a Saturday
    result = cache.get_active_service_ids(date(2026, 2, 21))
    assert result == {"SAT"}


def test_get_active_service_ids_sunday():
    cache = _make_cache_with_calendar()
    # 2026-02-22 is a Sunday
    result = cache.get_active_service_ids(date(2026, 2, 22))
    assert result == {"SUN"}


def test_get_active_service_ids_exception_add():
    cache = _make_cache_with_calendar()
    # Add holiday service on a Tuesday (2026-02-17)
    cache.calendar_dates = [
        CalendarDateException(
            service_id="HOLIDAY",
            date="20260217",
            exception_type=1,  # added
        ),
    ]
    result = cache.get_active_service_ids(date(2026, 2, 17))
    assert "WD" in result
    assert "HOLIDAY" in result


def test_get_active_service_ids_exception_remove():
    cache = _make_cache_with_calendar()
    # Remove weekday service on a Tuesday (2026-02-17) — e.g. national holiday
    cache.calendar_dates = [
        CalendarDateException(
            service_id="WD",
            date="20260217",
            exception_type=2,  # removed
        ),
    ]
    result = cache.get_active_service_ids(date(2026, 2, 17))
    assert "WD" not in result


def test_get_active_service_ids_outside_date_range():
    cache = _make_cache_with_calendar()
    # Date outside the calendar range (2025)
    result = cache.get_active_service_ids(date(2025, 6, 15))
    assert result == set()


def test_build_stop_routes_index():
    cache = GTFSStaticCache()
    cache.routes = {
        "r1": RouteInfo(route_id="r1", route_short_name="22", route_long_name="", route_type=3),
        "r2": RouteInfo(route_id="r2", route_short_name="3", route_long_name="", route_type=3),
    }
    cache.trips = {
        "t1": TripInfo(trip_id="t1", route_id="r1", service_id="WD"),
        "t2": TripInfo(trip_id="t2", route_id="r2", service_id="WD"),
    }
    cache.trip_stop_times = {
        "t1": [
            StopTimeEntry(
                stop_id="s1", stop_sequence=1, arrival_time="06:00", departure_time="06:00"
            ),
            StopTimeEntry(
                stop_id="s2", stop_sequence=2, arrival_time="06:10", departure_time="06:10"
            ),
        ],
        "t2": [
            StopTimeEntry(
                stop_id="s2", stop_sequence=1, arrival_time="07:00", departure_time="07:00"
            ),
            StopTimeEntry(
                stop_id="s3", stop_sequence=2, arrival_time="07:10", departure_time="07:10"
            ),
        ],
    }
    cache._build_stop_routes_index()

    assert cache.stop_routes["s1"] == ["22"]
    assert cache.stop_routes["s2"] == ["22", "3"]  # sorted alphabetically
    assert cache.stop_routes["s3"] == ["3"]
