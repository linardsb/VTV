"""Tests for get_adherence_report transit tool."""

import json
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.agents.tools.transit.client import StopTimeUpdateData, TripUpdateData
from app.core.agents.tools.transit.get_adherence_report import (
    _classify_trip_status,
    get_adherence_report,
)
from app.core.agents.tools.transit.static_cache import (
    RouteInfo,
    StopTimeEntry,
    TripInfo,
)
from app.core.agents.tools.transit.utils import (
    delay_description,
    gtfs_time_to_display,
    gtfs_time_to_minutes,
    validate_date,
)

# --- Helper functions ---


def _make_ctx() -> MagicMock:
    ctx = MagicMock()
    ctx.deps.transit_http_client = AsyncMock()
    ctx.deps.settings = MagicMock()
    return ctx


def _make_mock_static() -> MagicMock:
    """Create mock static cache with bus_22 route and 3 trips."""
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
                direction_id=0,
                trip_headsign="Jugla",
            ),
            TripInfo(
                trip_id="t3",
                route_id="bus_22",
                service_id="WD",
                direction_id=1,
                trip_headsign="Centrs",
            ),
        ],
    }
    mock.trips = {
        "t1": mock.route_trips["bus_22"][0],
        "t2": mock.route_trips["bus_22"][1],
        "t3": mock.route_trips["bus_22"][2],
    }
    mock.trip_stop_times = {
        "t1": [
            StopTimeEntry(
                stop_id="s1", stop_sequence=1, arrival_time="06:00:00", departure_time="06:00:00"
            ),
            StopTimeEntry(
                stop_id="s2", stop_sequence=2, arrival_time="06:15:00", departure_time="06:15:00"
            ),
        ],
        "t2": [
            StopTimeEntry(
                stop_id="s1", stop_sequence=1, arrival_time="08:00:00", departure_time="08:00:00"
            ),
            StopTimeEntry(
                stop_id="s2", stop_sequence=2, arrival_time="08:15:00", departure_time="08:15:00"
            ),
        ],
        "t3": [
            StopTimeEntry(
                stop_id="s2", stop_sequence=1, arrival_time="07:00:00", departure_time="07:00:00"
            ),
            StopTimeEntry(
                stop_id="s1", stop_sequence=2, arrival_time="07:15:00", departure_time="07:15:00"
            ),
        ],
    }
    mock.get_active_service_ids.return_value = {"WD"}
    return mock


def _make_trip_update(
    trip_id: str,
    delay_seconds: int,
    vehicle_id: str | None = None,
    route_id: str | None = None,
) -> TripUpdateData:
    """Build a TripUpdateData with one StopTimeUpdateData."""
    return TripUpdateData(
        trip_id=trip_id,
        route_id=route_id,
        vehicle_id=vehicle_id,
        stop_time_updates=[
            StopTimeUpdateData(
                stop_sequence=1,
                stop_id="s1",
                arrival_delay=delay_seconds,
                departure_delay=delay_seconds,
                arrival_time=None,
                departure_time=None,
            ),
        ],
        timestamp=1708200000,
    )


# --- Unit tests for helper functions ---


def testgtfs_time_to_minutes_normal():
    assert gtfs_time_to_minutes("06:30:00") == 390


def testgtfs_time_to_minutes_overnight():
    assert gtfs_time_to_minutes("25:30:00") == 1530


def testgtfs_time_to_display_normal():
    assert gtfs_time_to_display("06:30:00") == "06:30"


def testgtfs_time_to_display_overnight():
    assert gtfs_time_to_display("25:30:00") == "01:30"


def testvalidate_date_none_returns_today():
    result = validate_date(None)
    assert isinstance(result, tuple)
    parsed_date, date_str = result
    assert isinstance(parsed_date, date)
    assert date_str == parsed_date.isoformat()


def testvalidate_date_invalid():
    result = validate_date("bad-date")
    assert isinstance(result, str)
    assert "Invalid date" in result


def test_classify_trip_status_on_time():
    assert _classify_trip_status(0) == "on_time"
    assert _classify_trip_status(120) == "on_time"
    assert _classify_trip_status(-120) == "on_time"
    assert _classify_trip_status(300) == "on_time"  # exactly at threshold


def test_classify_trip_status_late_and_early():
    assert _classify_trip_status(400) == "late"
    assert _classify_trip_status(-400) == "early"
    assert _classify_trip_status(600) == "late"
    assert _classify_trip_status(-600) == "early"


def testdelay_description_values():
    assert delay_description(0) == "on time"
    assert delay_description(300) == "5 min late"
    assert delay_description(-180) == "3 min early"
    assert delay_description(30) == "on time"


# --- Tool function tests with mocks ---


@pytest.mark.asyncio
async def test_get_adherence_report_invalid_date():
    ctx = _make_ctx()
    result = await get_adherence_report(ctx, route_id="bus_22", date="not-a-date")
    assert "Invalid date" in result


@pytest.mark.asyncio
async def test_get_adherence_report_route_not_found():
    ctx = _make_ctx()
    mock_static = MagicMock()
    mock_static.routes = {}

    mock_client = AsyncMock()
    mock_client.fetch_trip_updates.return_value = []

    with (
        patch(
            "app.core.agents.tools.transit.get_adherence_report.GTFSRealtimeClient",
            return_value=mock_client,
        ),
        patch(
            "app.core.agents.tools.transit.get_adherence_report.get_static_cache",
            return_value=mock_static,
        ),
    ):
        result = await get_adherence_report(ctx, route_id="nonexistent", date="2026-02-17")

    assert "not found" in result


@pytest.mark.asyncio
async def test_get_adherence_report_no_service():
    ctx = _make_ctx()
    mock_static = _make_mock_static()
    mock_static.get_active_service_ids.return_value = set()

    mock_client = AsyncMock()
    mock_client.fetch_trip_updates.return_value = []

    with (
        patch(
            "app.core.agents.tools.transit.get_adherence_report.GTFSRealtimeClient",
            return_value=mock_client,
        ),
        patch(
            "app.core.agents.tools.transit.get_adherence_report.get_static_cache",
            return_value=mock_static,
        ),
    ):
        result = await get_adherence_report(ctx, route_id="bus_22", date="2026-12-25")

    assert "no scheduled service" in result


@pytest.mark.asyncio
async def test_get_adherence_report_single_route_success():
    """Route with 3 trips: t1 on-time (120s), t2 late (400s), t3 no data."""
    ctx = _make_ctx()
    mock_static = _make_mock_static()

    mock_client = AsyncMock()
    mock_client.fetch_trip_updates.return_value = [
        _make_trip_update("t1", 120, vehicle_id="v1"),
        _make_trip_update("t2", 400, vehicle_id="v2"),
    ]

    with (
        patch(
            "app.core.agents.tools.transit.get_adherence_report.GTFSRealtimeClient",
            return_value=mock_client,
        ),
        patch(
            "app.core.agents.tools.transit.get_adherence_report.get_static_cache",
            return_value=mock_static,
        ),
    ):
        result = await get_adherence_report(ctx, route_id="bus_22", date="2026-02-17")

    data = json.loads(result)
    assert data["report_type"] == "route"
    assert data["route_id"] == "bus_22"
    route = data["routes"][0]
    assert route["scheduled_trips"] == 3
    assert route["tracked_trips"] == 2
    assert route["on_time_count"] == 1
    assert route["late_count"] == 1
    assert route["no_data_count"] == 1
    assert route["on_time_percentage"] == 50.0
    assert "22" in data["summary"]


@pytest.mark.asyncio
async def test_get_adherence_report_all_on_time():
    ctx = _make_ctx()
    mock_static = _make_mock_static()

    mock_client = AsyncMock()
    mock_client.fetch_trip_updates.return_value = [
        _make_trip_update("t1", 60, vehicle_id="v1"),
        _make_trip_update("t2", -30, vehicle_id="v2"),
        _make_trip_update("t3", 120, vehicle_id="v3"),
    ]

    with (
        patch(
            "app.core.agents.tools.transit.get_adherence_report.GTFSRealtimeClient",
            return_value=mock_client,
        ),
        patch(
            "app.core.agents.tools.transit.get_adherence_report.get_static_cache",
            return_value=mock_static,
        ),
    ):
        result = await get_adherence_report(ctx, route_id="bus_22", date="2026-02-17")

    data = json.loads(result)
    route = data["routes"][0]
    assert route["on_time_percentage"] == 100.0
    assert route["tracked_trips"] == 3
    assert route["no_data_count"] == 0


@pytest.mark.asyncio
async def test_get_adherence_report_network_report():
    """Network report with two routes having real-time data."""
    ctx = _make_ctx()
    mock_static = _make_mock_static()
    # Add a second route
    mock_static.routes["bus_7"] = RouteInfo(
        route_id="bus_7",
        route_short_name="7",
        route_long_name="Abrenes - Ziepniekkalns",
        route_type=3,
    )
    mock_static.route_trips["bus_7"] = [
        TripInfo(
            trip_id="t4",
            route_id="bus_7",
            service_id="WD",
            direction_id=0,
            trip_headsign="Ziepniekkalns",
        ),
    ]
    mock_static.trips["t4"] = mock_static.route_trips["bus_7"][0]
    mock_static.trip_stop_times["t4"] = [
        StopTimeEntry(
            stop_id="s3", stop_sequence=1, arrival_time="06:30:00", departure_time="06:30:00"
        ),
    ]

    mock_client = AsyncMock()
    mock_client.fetch_trip_updates.return_value = [
        _make_trip_update("t1", 100, vehicle_id="v1", route_id="bus_22"),
        _make_trip_update("t4", 500, vehicle_id="v4", route_id="bus_7"),
    ]

    with (
        patch(
            "app.core.agents.tools.transit.get_adherence_report.GTFSRealtimeClient",
            return_value=mock_client,
        ),
        patch(
            "app.core.agents.tools.transit.get_adherence_report.get_static_cache",
            return_value=mock_static,
        ),
    ):
        result = await get_adherence_report(ctx, date="2026-02-17")

    data = json.loads(result)
    assert data["report_type"] == "network"
    assert len(data["routes"]) == 2
    assert data["network_on_time_percentage"] is not None
    assert data["network_average_delay_seconds"] is not None
    # Sorted by worst first — route 7 has 0% on-time (late 500s)
    assert data["routes"][0]["route_short_name"] == "7"


@pytest.mark.asyncio
async def test_get_adherence_report_time_window_filter():
    """time_from=07:00 should exclude t1 (06:00) but include t2 (08:00) and t3 (07:00)."""
    ctx = _make_ctx()
    mock_static = _make_mock_static()

    mock_client = AsyncMock()
    mock_client.fetch_trip_updates.return_value = [
        _make_trip_update("t1", 100, vehicle_id="v1"),
        _make_trip_update("t2", 200, vehicle_id="v2"),
        _make_trip_update("t3", 50, vehicle_id="v3"),
    ]

    with (
        patch(
            "app.core.agents.tools.transit.get_adherence_report.GTFSRealtimeClient",
            return_value=mock_client,
        ),
        patch(
            "app.core.agents.tools.transit.get_adherence_report.get_static_cache",
            return_value=mock_static,
        ),
    ):
        result = await get_adherence_report(
            ctx, route_id="bus_22", date="2026-02-17", time_from="07:00"
        )

    data = json.loads(result)
    route = data["routes"][0]
    # Only t2 (08:00) and t3 (07:00) should be included
    assert route["scheduled_trips"] == 2
    trip_ids = [t["trip_id"] for t in route["trips"]]
    assert "t1" not in trip_ids
    assert "t2" in trip_ids
    assert "t3" in trip_ids


@pytest.mark.asyncio
async def test_get_adherence_report_worst_trip_identified():
    ctx = _make_ctx()
    mock_static = _make_mock_static()

    mock_client = AsyncMock()
    mock_client.fetch_trip_updates.return_value = [
        _make_trip_update("t1", 100, vehicle_id="v1"),
        _make_trip_update("t2", -700, vehicle_id="v2"),  # worst (highest abs)
        _make_trip_update("t3", 400, vehicle_id="v3"),
    ]

    with (
        patch(
            "app.core.agents.tools.transit.get_adherence_report.GTFSRealtimeClient",
            return_value=mock_client,
        ),
        patch(
            "app.core.agents.tools.transit.get_adherence_report.get_static_cache",
            return_value=mock_static,
        ),
    ):
        result = await get_adherence_report(ctx, route_id="bus_22", date="2026-02-17")

    data = json.loads(result)
    route = data["routes"][0]
    assert route["worst_trip"] is not None
    assert route["worst_trip"]["trip_id"] == "t2"
    assert route["worst_trip"]["delay_seconds"] == -700


@pytest.mark.asyncio
async def test_get_adherence_report_feed_error():
    ctx = _make_ctx()

    with (
        patch(
            "app.core.agents.tools.transit.get_adherence_report.GTFSRealtimeClient",
            side_effect=RuntimeError("Connection refused"),
        ),
        patch("app.core.agents.tools.transit.get_adherence_report.logger"),
    ):
        result = await get_adherence_report(ctx, route_id="bus_22", date="2026-02-17")

    assert "Transit data error" in result


@pytest.mark.asyncio
async def test_get_adherence_report_no_realtime_data():
    """All trips with no real-time data -> no_data status, 0% on-time."""
    ctx = _make_ctx()
    mock_static = _make_mock_static()

    mock_client = AsyncMock()
    mock_client.fetch_trip_updates.return_value = []

    with (
        patch(
            "app.core.agents.tools.transit.get_adherence_report.GTFSRealtimeClient",
            return_value=mock_client,
        ),
        patch(
            "app.core.agents.tools.transit.get_adherence_report.get_static_cache",
            return_value=mock_static,
        ),
    ):
        result = await get_adherence_report(ctx, route_id="bus_22", date="2026-02-17")

    data = json.loads(result)
    route = data["routes"][0]
    assert route["tracked_trips"] == 0
    assert route["no_data_count"] == 3
    assert route["on_time_percentage"] == 0.0
    assert route["worst_trip"] is None
