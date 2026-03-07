# pyright: reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Unit tests for analytics service."""

from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.analytics.schemas import (
    DriverSummaryResponse,
    FleetSummaryResponse,
    OnTimePerformanceResponse,
)
from app.analytics.service import AnalyticsService


def _make_result(*, all_rows: list[object] | None = None, scalar: object = 0) -> MagicMock:
    """Create a mock SQLAlchemy result with .all() and .scalar_one()."""
    result = MagicMock()
    if all_rows is not None:
        result.all.return_value = all_rows
    result.scalar_one.return_value = scalar
    return result


def _mock_db_empty() -> AsyncMock:
    """Create a mock DB session that returns empty results for all queries."""
    db = AsyncMock()
    # Order: grouped query, then scalar queries (maintenance_due, reg_expiry, unassigned, avg_mileage)
    db.execute = AsyncMock(
        side_effect=[
            _make_result(all_rows=[]),  # grouped counts
            _make_result(scalar=0),  # maintenance_due_7d
            _make_result(scalar=0),  # registration_expiring_30d
            _make_result(scalar=0),  # unassigned_vehicles
            _make_result(scalar=None),  # average_mileage_km (None → 0.0)
        ]
    )
    return db


def _make_row(*values: object) -> MagicMock:
    """Create a mock SQLAlchemy Row with __getitem__ support."""
    row = MagicMock()
    row.__getitem__ = lambda _self, i: values[i]
    return row


def _mock_db_fleet_data() -> AsyncMock:
    """Create a mock DB session with realistic fleet data."""
    db = AsyncMock()
    db.execute = AsyncMock(
        side_effect=[
            _make_result(
                all_rows=[
                    _make_row("bus", "active", 10),
                    _make_row("bus", "maintenance", 2),
                    _make_row("tram", "active", 5),
                ]
            ),
            _make_result(scalar=3),  # maintenance_due_7d
            _make_result(scalar=1),  # registration_expiring_30d
            _make_result(scalar=4),  # unassigned_vehicles
            _make_result(scalar=45000.5),  # average_mileage_km
        ]
    )
    return db


def _mock_db_driver_data() -> AsyncMock:
    """Create a mock DB session with realistic driver data."""
    db = AsyncMock()
    db.execute = AsyncMock(
        side_effect=[
            _make_result(
                all_rows=[
                    _make_row("morning", "available", 8),
                    _make_row("morning", "on_duty", 5),
                    _make_row("afternoon", "available", 3),
                ]
            ),
            _make_result(scalar=2),  # license_expiring_30d
            _make_result(scalar=1),  # medical_expiring_30d
        ]
    )
    return db


@pytest.mark.asyncio
async def test_fleet_summary_empty_db() -> None:
    """Fleet summary with no vehicles returns all zeros."""
    db = _mock_db_empty()
    service = AnalyticsService(db)
    result = await service.get_fleet_summary()

    assert isinstance(result, FleetSummaryResponse)
    assert result.total_vehicles == 0
    assert result.active_vehicles == 0
    assert result.by_type == []
    assert result.average_mileage_km == 0.0
    now = datetime.datetime.now(tz=datetime.UTC)
    assert abs((now - result.generated_at).total_seconds()) < 5


@pytest.mark.asyncio
async def test_fleet_summary_with_vehicles() -> None:
    """Fleet summary correctly groups vehicles by type and status."""
    db = _mock_db_fleet_data()
    service = AnalyticsService(db)
    result = await service.get_fleet_summary()

    assert isinstance(result, FleetSummaryResponse)
    assert result.total_vehicles == 17  # 10 + 2 + 5
    assert result.active_vehicles == 15  # 10 + 5
    assert result.in_maintenance == 2
    assert result.maintenance_due_7d == 3
    assert result.registration_expiring_30d == 1
    assert result.unassigned_vehicles == 4
    assert result.average_mileage_km == 45000.5
    assert len(result.by_type) == 2  # bus and tram


@pytest.mark.asyncio
async def test_driver_summary_empty_db() -> None:
    """Driver summary with no drivers returns all zeros."""
    db = _mock_db_empty()
    service = AnalyticsService(db)
    result = await service.get_driver_summary()

    assert isinstance(result, DriverSummaryResponse)
    assert result.total_drivers == 0
    assert result.available_drivers == 0
    assert result.by_shift == []


@pytest.mark.asyncio
async def test_driver_summary_with_drivers() -> None:
    """Driver summary correctly groups drivers by shift and status."""
    db = _mock_db_driver_data()
    service = AnalyticsService(db)
    result = await service.get_driver_summary()

    assert isinstance(result, DriverSummaryResponse)
    assert result.total_drivers == 16  # 8 + 5 + 3
    assert result.available_drivers == 11  # 8 + 3
    assert result.on_duty_drivers == 5
    assert result.license_expiring_30d == 2
    assert result.medical_expiring_30d == 1
    assert len(result.by_shift) == 2  # morning and afternoon


@pytest.mark.asyncio
async def test_on_time_performance_invalid_date() -> None:
    """On-time performance raises ValueError for invalid date."""
    db = AsyncMock()
    service = AnalyticsService(db)
    with pytest.raises(ValueError, match="date"):
        await service.get_on_time_performance(date="not-a-date")


@pytest.mark.asyncio
@patch("app.analytics.service.get_settings")
@patch("app.analytics.service.get_static_cache")
@patch("app.analytics.service.GTFSRealtimeClient")
async def test_on_time_performance_returns_response(
    mock_client_cls: MagicMock,
    mock_static_cache: AsyncMock,
    mock_settings: MagicMock,
) -> None:
    """On-time performance returns valid response with mocked GTFS data."""
    # Settings
    mock_settings.return_value = MagicMock()

    # Static cache
    cache = MagicMock()
    cache.get_active_service_ids.return_value = {"service_1"}
    cache.routes = {}
    cache.trips = {}
    cache.route_trips = {}
    cache.trip_stop_times = {}
    mock_static_cache.return_value = cache

    # GTFS-RT client — no trip updates
    client_instance = MagicMock()
    client_instance.fetch_trip_updates = AsyncMock(return_value=[])
    mock_client_cls.return_value = client_instance

    db = AsyncMock()
    service = AnalyticsService(db)
    result = await service.get_on_time_performance()

    assert isinstance(result, OnTimePerformanceResponse)
    assert result.total_routes == 0
    assert result.network_on_time_percentage == 0.0
    assert result.routes == []


@pytest.mark.asyncio
@patch("app.analytics.service.get_settings")
@patch("app.analytics.service.get_static_cache")
@patch("app.analytics.service.GTFSRealtimeClient")
async def test_on_time_performance_transit_error(
    mock_client_cls: MagicMock,
    mock_static_cache: AsyncMock,
    mock_settings: MagicMock,
) -> None:
    """On-time performance propagates transit errors."""
    mock_settings.return_value = MagicMock()
    mock_static_cache.side_effect = Exception("Feed timeout")

    db = AsyncMock()
    service = AnalyticsService(db)
    with pytest.raises(Exception, match="Feed timeout"):
        await service.get_on_time_performance()
