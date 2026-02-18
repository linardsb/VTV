"""Tests for query_bus_status transit tool."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.agents.tools.transit.query_bus_status import (
    _delay_description,
    _severity,
    _validate_params,
    query_bus_status,
)

# --- Unit tests for helper functions ---


def test_delay_description_on_time():
    assert _delay_description(30) == "on time"
    assert _delay_description(-30) == "on time"
    assert _delay_description(0) == "on time"


def test_delay_description_late():
    assert _delay_description(180) == "3 min late"
    assert _delay_description(600) == "10 min late"


def test_delay_description_early():
    assert _delay_description(-180) == "3 min early"
    assert _delay_description(-600) == "10 min early"


def test_severity_normal():
    assert _severity(0) == "normal"
    assert _severity(120) == "normal"
    assert _severity(-120) == "normal"


def test_severity_warning():
    assert _severity(300) == "warning"
    assert _severity(-300) == "warning"


def test_severity_critical():
    assert _severity(700) == "critical"
    assert _severity(-700) == "critical"


def test_validate_params_status_missing():
    result = _validate_params("status", None, None, None)
    assert result is not None
    assert "vehicle_id or route_id" in result


def test_validate_params_status_with_route():
    result = _validate_params("status", "22", None, None)
    assert result is None


def test_validate_params_status_with_vehicle():
    result = _validate_params("status", None, "4521", None)
    assert result is None


def test_validate_params_route_overview_missing():
    result = _validate_params("route_overview", None, None, None)
    assert result is not None
    assert "route_id" in result


def test_validate_params_stop_departures_missing():
    result = _validate_params("stop_departures", None, None, None)
    assert result is not None
    assert "stop_id" in result


# --- Integration-style tests for the tool function ---


@pytest.mark.asyncio
async def test_query_bus_status_invalid_action():
    ctx = MagicMock()
    result = await query_bus_status(ctx, action="invalid_action")
    assert "Invalid action" in result
    assert "status" in result


@pytest.mark.asyncio
async def test_query_bus_status_status_missing_params():
    ctx = MagicMock()
    result = await query_bus_status(ctx, action="status")
    assert "vehicle_id or route_id" in result


@pytest.mark.asyncio
async def test_query_bus_status_route_overview_missing_params():
    ctx = MagicMock()
    result = await query_bus_status(ctx, action="route_overview")
    assert "route_id" in result


@pytest.mark.asyncio
async def test_query_bus_status_stop_departures_missing_params():
    ctx = MagicMock()
    result = await query_bus_status(ctx, action="stop_departures")
    assert "stop_id" in result


@pytest.mark.asyncio
async def test_query_bus_status_status_no_vehicles():
    ctx = MagicMock()
    ctx.deps.transit_http_client = AsyncMock()
    ctx.deps.settings = MagicMock()

    mock_client = AsyncMock()
    mock_client.fetch_vehicle_positions.return_value = []
    mock_client.fetch_trip_updates.return_value = []
    mock_client.fetch_alerts.return_value = []

    mock_static = MagicMock()

    with (
        patch(
            "app.core.agents.tools.transit.query_bus_status.GTFSRealtimeClient",
            return_value=mock_client,
        ),
        patch(
            "app.core.agents.tools.transit.query_bus_status.get_static_cache",
            return_value=mock_static,
        ),
    ):
        result = await query_bus_status(ctx, action="status", route_id="22")

    assert "No active vehicles" in result
    assert "route 22" in result


@pytest.mark.asyncio
async def test_query_bus_status_feed_error():
    ctx = MagicMock()
    ctx.deps.transit_http_client = AsyncMock()
    ctx.deps.settings = MagicMock()

    with (
        patch(
            "app.core.agents.tools.transit.query_bus_status.GTFSRealtimeClient",
            side_effect=RuntimeError("Connection refused"),
        ),
        patch("app.core.agents.tools.transit.query_bus_status.logger"),
    ):
        result = await query_bus_status(ctx, action="status", route_id="22")

    assert "Transit data error" in result
