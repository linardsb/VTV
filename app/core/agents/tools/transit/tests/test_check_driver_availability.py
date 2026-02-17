"""Tests for check_driver_availability transit tool."""

import json
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.agents.tools.transit.check_driver_availability import (
    _classify_service_type,
    _validate_date,
    check_driver_availability,
)

# --- Helper functions ---


def _make_ctx() -> MagicMock:
    ctx = MagicMock()
    ctx.deps.http_client = AsyncMock()
    ctx.deps.settings = MagicMock()
    ctx.deps.settings.environment = "test"
    return ctx


def _make_mock_drivers(
    count: int = 5,
    shift: str = "morning",
    status: str = "available",
    route_ids: list[str] | None = None,
) -> list[dict[str, str | list[str] | None]]:
    """Build a list of mock driver dicts with controllable fields."""
    if route_ids is None:
        route_ids = ["bus_22", "bus_7"]
    drivers: list[dict[str, str | list[str] | None]] = []
    for i in range(count):
        drivers.append(
            {
                "driver_id": f"DRV-T{i + 1:03d}",
                "name": f"Test Driver {i + 1}",
                "license_categories": ["D"],
                "qualified_route_ids": route_ids,
                "shift": shift,
                "status": status,
                "phone": f"+371 2600 {i + 1:04d}" if status == "available" else None,
                "notes": None,
            }
        )
    return drivers


# --- Unit tests for helper functions ---


def test_validate_date_none_returns_today():
    result = _validate_date(None)
    assert isinstance(result, tuple)
    parsed_date, date_str = result
    assert isinstance(parsed_date, date)
    assert date_str == parsed_date.isoformat()


def test_validate_date_valid():
    result = _validate_date("2026-02-17")
    assert isinstance(result, tuple)
    parsed_date, date_str = result
    assert parsed_date == date(2026, 2, 17)
    assert date_str == "2026-02-17"


def test_validate_date_invalid():
    result = _validate_date("bad-date")
    assert isinstance(result, str)
    assert "Invalid date" in result


def test_classify_service_type_weekday():
    assert _classify_service_type(date(2026, 2, 17)) == "weekday"  # Tuesday


def test_classify_service_type_weekend():
    assert _classify_service_type(date(2026, 2, 21)) == "saturday"
    assert _classify_service_type(date(2026, 3, 1)) == "sunday"


# --- Tool function tests with mocks ---


@pytest.mark.asyncio
async def test_check_driver_availability_invalid_date():
    ctx = _make_ctx()
    result = await check_driver_availability(ctx, date="not-a-date")
    assert "Invalid date" in result


@pytest.mark.asyncio
async def test_check_driver_availability_invalid_shift():
    ctx = _make_ctx()
    result = await check_driver_availability(ctx, shift="graveyard")
    assert "Invalid shift" in result
    assert "morning" in result
    assert "afternoon" in result
    assert "evening" in result
    assert "night" in result


@pytest.mark.asyncio
async def test_check_driver_availability_all_drivers():
    ctx = _make_ctx()
    mock_drivers = (
        _make_mock_drivers(3, shift="morning", status="available")
        + _make_mock_drivers(1, shift="morning", status="on_duty")
        + _make_mock_drivers(1, shift="afternoon", status="on_leave")
    )

    with patch(
        "app.core.agents.tools.transit.check_driver_availability.get_driver_availability",
        return_value=mock_drivers,
    ):
        result = await check_driver_availability(ctx, date="2026-02-17")

    data = json.loads(result)
    assert data["total_drivers"] == 5
    assert data["available_count"] == 3
    assert len(data["drivers"]) == 5
    assert "5 total" in data["summary"]
    assert "3 available" in data["summary"]


@pytest.mark.asyncio
async def test_check_driver_availability_shift_filter():
    ctx = _make_ctx()
    mock_drivers = _make_mock_drivers(3, shift="morning", status="available")

    with patch(
        "app.core.agents.tools.transit.check_driver_availability.get_driver_availability",
        return_value=mock_drivers,
    ):
        result = await check_driver_availability(ctx, date="2026-02-17", shift="morning")

    data = json.loads(result)
    assert data["shift_filter"] == "morning"
    for driver in data["drivers"]:
        assert driver["shift"] == "morning"


@pytest.mark.asyncio
async def test_check_driver_availability_route_filter():
    ctx = _make_ctx()
    mock_drivers = _make_mock_drivers(2, route_ids=["bus_22", "bus_7"])

    with patch(
        "app.core.agents.tools.transit.check_driver_availability.get_driver_availability",
        return_value=mock_drivers,
    ):
        result = await check_driver_availability(ctx, date="2026-02-17", route_id="bus_22")

    data = json.loads(result)
    assert data["route_filter"] == "bus_22"
    for driver in data["drivers"]:
        assert "bus_22" in driver["qualified_route_ids"]


@pytest.mark.asyncio
async def test_check_driver_availability_combined_filters():
    ctx = _make_ctx()
    mock_drivers = _make_mock_drivers(2, shift="afternoon", route_ids=["bus_7", "bus_13"])

    with patch(
        "app.core.agents.tools.transit.check_driver_availability.get_driver_availability",
        return_value=mock_drivers,
    ):
        result = await check_driver_availability(
            ctx, date="2026-02-17", shift="afternoon", route_id="bus_7"
        )

    data = json.loads(result)
    assert data["shift_filter"] == "afternoon"
    assert data["route_filter"] == "bus_7"
    assert data["total_drivers"] == 2


@pytest.mark.asyncio
async def test_check_driver_availability_no_drivers_found():
    ctx = _make_ctx()

    with patch(
        "app.core.agents.tools.transit.check_driver_availability.get_driver_availability",
        return_value=[],
    ):
        result = await check_driver_availability(ctx, date="2026-02-17", shift="night")

    data = json.loads(result)
    assert data["total_drivers"] == 0
    assert data["available_count"] == 0
    assert "No drivers found" in data["summary"]
    assert "broadening" in data["summary"]


@pytest.mark.asyncio
async def test_check_driver_availability_shift_summary_counts():
    ctx = _make_ctx()
    mock_drivers = (
        _make_mock_drivers(2, shift="morning", status="available")
        + _make_mock_drivers(1, shift="morning", status="sick")
        + _make_mock_drivers(1, shift="evening", status="on_duty")
        + _make_mock_drivers(1, shift="evening", status="available")
    )

    with patch(
        "app.core.agents.tools.transit.check_driver_availability.get_driver_availability",
        return_value=mock_drivers,
    ):
        result = await check_driver_availability(ctx, date="2026-02-17")

    data = json.loads(result)
    shifts = {s["shift"]: s for s in data["shifts"]}

    assert "morning" in shifts
    assert shifts["morning"]["total_drivers"] == 3
    assert shifts["morning"]["available_count"] == 2
    assert shifts["morning"]["sick_count"] == 1

    assert "evening" in shifts
    assert shifts["evening"]["total_drivers"] == 2
    assert shifts["evening"]["on_duty_count"] == 1
    assert shifts["evening"]["available_count"] == 1


@pytest.mark.asyncio
async def test_check_driver_availability_token_cap():
    ctx = _make_ctx()
    mock_drivers = _make_mock_drivers(35, shift="morning", status="available")

    with patch(
        "app.core.agents.tools.transit.check_driver_availability.get_driver_availability",
        return_value=mock_drivers,
    ):
        result = await check_driver_availability(ctx, date="2026-02-17")

    data = json.loads(result)
    assert data["total_drivers"] == 35
    assert len(data["drivers"]) == 30  # capped at _MAX_DRIVERS_RESPONSE


@pytest.mark.asyncio
async def test_check_driver_availability_provider_error():
    ctx = _make_ctx()

    with patch(
        "app.core.agents.tools.transit.check_driver_availability.get_driver_availability",
        side_effect=RuntimeError("Connection refused"),
    ):
        result = await check_driver_availability(ctx, date="2026-02-17")

    assert "Driver data error" in result
    assert "Connection refused" in result


@pytest.mark.asyncio
async def test_check_driver_availability_specific_date():
    ctx = _make_ctx()
    mock_drivers = _make_mock_drivers(2, shift="morning", status="available")

    with patch(
        "app.core.agents.tools.transit.check_driver_availability.get_driver_availability",
        return_value=mock_drivers,
    ):
        result = await check_driver_availability(ctx, date="2026-03-01")

    data = json.loads(result)
    assert data["report_date"] == "2026-03-01"
    assert data["service_type"] == "sunday"
