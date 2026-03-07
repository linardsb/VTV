"""Tests for get_route_schedule transit tool."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.agents.tools.transit.get_route_schedule import get_route_schedule
from app.core.agents.tools.transit.static_cache import (
    RouteInfo,
    StopTimeEntry,
    TripInfo,
)
from app.core.agents.tools.transit.utils import (
    classify_service_type,
    gtfs_time_to_display,
    gtfs_time_to_minutes,
    validate_date,
)

# --- Unit tests for helper functions ---


def testgtfs_time_to_minutes_normal():
    assert gtfs_time_to_minutes("06:30:00") == 390


def testgtfs_time_to_minutes_midnight():
    assert gtfs_time_to_minutes("00:00:00") == 0


def testgtfs_time_to_minutes_overnight():
    assert gtfs_time_to_minutes("25:30:00") == 1530


def testgtfs_time_to_minutes_short_format():
    assert gtfs_time_to_minutes("06:30") == 390


def testgtfs_time_to_display_normal():
    assert gtfs_time_to_display("06:30:00") == "06:30"


def testgtfs_time_to_display_overnight():
    assert gtfs_time_to_display("25:30:00") == "01:30"


def testgtfs_time_to_display_midnight():
    assert gtfs_time_to_display("24:00:00") == "00:00"


def testclassify_service_type_weekday():
    # 2026-02-16 is a Monday
    assert classify_service_type(date(2026, 2, 16)) == "weekday"


def testclassify_service_type_saturday():
    # 2026-02-21 is a Saturday
    assert classify_service_type(date(2026, 2, 21)) == "saturday"


def testclassify_service_type_sunday():
    # 2026-02-22 is a Sunday
    assert classify_service_type(date(2026, 2, 22)) == "sunday"


def testvalidate_date_none_returns_today():
    result = validate_date(None)
    assert isinstance(result, tuple)
    parsed_date, date_str = result
    assert isinstance(parsed_date, date)
    assert date_str == parsed_date.isoformat()


def testvalidate_date_valid():
    result = validate_date("2026-02-17")
    assert isinstance(result, tuple)
    parsed_date, date_str = result
    assert parsed_date == date(2026, 2, 17)
    assert date_str == "2026-02-17"


def testvalidate_date_invalid():
    result = validate_date("not-a-date")
    assert isinstance(result, str)
    assert "Invalid date" in result


# --- Tool function tests with mocks ---


def _make_ctx() -> MagicMock:
    ctx = MagicMock()
    ctx.deps.transit_http_client = AsyncMock()
    ctx.deps.settings = MagicMock()
    ctx.deps.db_session_factory = MagicMock()
    return ctx


def _make_mock_static() -> MagicMock:
    mock = MagicMock()
    mock.routes = {
        "bus_22": RouteInfo(
            route_id="bus_22",
            route_short_name="22",
            route_long_name="Centrs - Jugla",
            route_type=3,
        ),
    }
    mock.route_trips = {
        "bus_22": [
            TripInfo(
                trip_id="t1",
                route_id="bus_22",
                service_id="WD",
                direction_id=0,
                trip_headsign="Jugla",
            ),
            TripInfo(
                trip_id="t2",
                route_id="bus_22",
                service_id="WD",
                direction_id=1,
                trip_headsign="Centrs",
            ),
        ],
    }
    mock.trip_stop_times = {
        "t1": [
            StopTimeEntry(
                stop_id="s1", stop_sequence=1, arrival_time="06:00:00", departure_time="06:00:00"
            ),
            StopTimeEntry(
                stop_id="s2", stop_sequence=2, arrival_time="06:15:00", departure_time="06:15:00"
            ),
            StopTimeEntry(
                stop_id="s3", stop_sequence=3, arrival_time="06:30:00", departure_time="06:30:00"
            ),
        ],
        "t2": [
            StopTimeEntry(
                stop_id="s3", stop_sequence=1, arrival_time="07:00:00", departure_time="07:00:00"
            ),
            StopTimeEntry(
                stop_id="s2", stop_sequence=2, arrival_time="07:15:00", departure_time="07:15:00"
            ),
            StopTimeEntry(
                stop_id="s1", stop_sequence=3, arrival_time="07:30:00", departure_time="07:30:00"
            ),
        ],
    }
    mock.get_active_service_ids.return_value = {"WD"}
    return mock


@pytest.mark.asyncio
async def test_get_route_schedule_invalid_date():
    ctx = _make_ctx()
    result = await get_route_schedule(ctx, route_id="bus_22", date="not-a-date")
    assert "Invalid date" in result


@pytest.mark.asyncio
async def test_get_route_schedule_route_not_found():
    ctx = _make_ctx()
    mock_static = MagicMock()
    mock_static.routes = {}

    with patch(
        "app.core.agents.tools.transit.get_route_schedule.get_static_store",
        return_value=mock_static,
    ):
        result = await get_route_schedule(ctx, route_id="nonexistent", date="2026-02-17")

    assert "not found" in result


@pytest.mark.asyncio
async def test_get_route_schedule_no_service():
    ctx = _make_ctx()
    mock_static = _make_mock_static()
    mock_static.get_active_service_ids.return_value = set()

    with patch(
        "app.core.agents.tools.transit.get_route_schedule.get_static_store",
        return_value=mock_static,
    ):
        result = await get_route_schedule(ctx, route_id="bus_22", date="2026-12-25")

    assert "no scheduled service" in result


@pytest.mark.asyncio
async def test_get_route_schedule_success():
    ctx = _make_ctx()
    mock_static = _make_mock_static()

    with patch(
        "app.core.agents.tools.transit.get_route_schedule.get_static_store",
        return_value=mock_static,
    ):
        result = await get_route_schedule(ctx, route_id="bus_22", date="2026-02-17")

    import json

    data = json.loads(result)
    assert data["route_id"] == "bus_22"
    assert data["route_short_name"] == "22"
    assert data["trip_count"] == 2
    assert len(data["directions"]) == 2
    assert data["service_date"] == "2026-02-17"
    assert "summary" in data


@pytest.mark.asyncio
async def test_get_route_schedule_direction_filter():
    ctx = _make_ctx()
    mock_static = _make_mock_static()

    with patch(
        "app.core.agents.tools.transit.get_route_schedule.get_static_store",
        return_value=mock_static,
    ):
        result = await get_route_schedule(ctx, route_id="bus_22", date="2026-02-17", direction_id=0)

    import json

    data = json.loads(result)
    assert data["trip_count"] == 1
    assert len(data["directions"]) == 1
    assert data["directions"][0]["direction_id"] == 0


@pytest.mark.asyncio
async def test_get_route_schedule_feed_error():
    ctx = _make_ctx()

    with (
        patch(
            "app.core.agents.tools.transit.get_route_schedule.get_static_store",
            side_effect=RuntimeError("Connection refused"),
        ),
        patch("app.core.agents.tools.transit.get_route_schedule.logger"),
    ):
        result = await get_route_schedule(ctx, route_id="bus_22", date="2026-02-17")

    assert "Transit data error" in result


@pytest.mark.asyncio
async def test_get_route_schedule_time_window_filter():
    ctx = _make_ctx()
    mock_static = _make_mock_static()

    with patch(
        "app.core.agents.tools.transit.get_route_schedule.get_static_store",
        return_value=mock_static,
    ):
        # Only t2 departs at 07:00, t1 departs at 06:00 — filter to 06:30+
        result = await get_route_schedule(
            ctx, route_id="bus_22", date="2026-02-17", time_from="06:30"
        )

    import json

    data = json.loads(result)
    # Only t2 should match (departs at 07:00, which is >= 06:30)
    assert data["trip_count"] == 1


@pytest.mark.asyncio
async def test_get_route_schedule_no_trips_in_window():
    ctx = _make_ctx()
    mock_static = _make_mock_static()

    with patch(
        "app.core.agents.tools.transit.get_route_schedule.get_static_store",
        return_value=mock_static,
    ):
        result = await get_route_schedule(
            ctx, route_id="bus_22", date="2026-02-17", time_from="22:00", time_until="23:00"
        )

    assert "but none between" in result
