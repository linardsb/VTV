# pyright: reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Unit tests for analytics routes."""

from __future__ import annotations

import datetime
from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.analytics.schemas import (
    DriverSummaryResponse,
    FleetSummaryResponse,
    OnTimePerformanceResponse,
    ShiftCoverageSummary,
)
from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.core.database import get_db
from app.core.rate_limit import limiter
from app.main import app

limiter.enabled = False


def _mock_admin_user() -> User:
    """Return a mock admin user for testing."""
    user = MagicMock(spec=User)
    user.id = 1
    user.email = "admin@vtv.lv"
    user.name = "Admin"
    user.role = "admin"
    user.is_active = True
    return user


@pytest.fixture(autouse=True)
def _setup_overrides() -> Generator[None, None, None]:
    """Set auth and db overrides before each test and clean up after."""
    app.dependency_overrides[get_current_user] = _mock_admin_user
    app.dependency_overrides[get_db] = lambda: AsyncMock()  # unused — AnalyticsService is patched
    yield
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_db, None)


def _fleet_response() -> FleetSummaryResponse:
    return FleetSummaryResponse(
        total_vehicles=10,
        active_vehicles=8,
        inactive_vehicles=1,
        in_maintenance=1,
        by_type=[],
        maintenance_due_7d=2,
        registration_expiring_30d=0,
        unassigned_vehicles=3,
        average_mileage_km=30000.0,
        generated_at=datetime.datetime.now(tz=datetime.UTC),
    )


def _driver_response() -> DriverSummaryResponse:
    return DriverSummaryResponse(
        total_drivers=15,
        available_drivers=10,
        on_duty_drivers=3,
        on_leave_drivers=1,
        sick_drivers=1,
        by_shift=[
            ShiftCoverageSummary(
                shift="morning",
                total=10,
                available=7,
                on_duty=2,
                on_leave=1,
                sick=0,
            ),
        ],
        license_expiring_30d=1,
        medical_expiring_30d=0,
        generated_at=datetime.datetime.now(tz=datetime.UTC),
    )


def _on_time_response() -> OnTimePerformanceResponse:
    return OnTimePerformanceResponse(
        service_date="2026-03-07",
        service_type="weekday",
        total_routes=5,
        network_on_time_percentage=85.0,
        network_average_delay_seconds=30.5,
        routes=[],
        generated_at=datetime.datetime.now(tz=datetime.UTC),
    )


@patch("app.analytics.routes.AnalyticsService")
def test_fleet_summary_endpoint(mock_service_cls: MagicMock) -> None:
    """GET /api/v1/analytics/fleet-summary returns 200 with valid data."""
    instance = MagicMock()
    instance.get_fleet_summary = AsyncMock(return_value=_fleet_response())
    mock_service_cls.return_value = instance

    client = TestClient(app)
    response = client.get("/api/v1/analytics/fleet-summary")
    assert response.status_code == 200
    data = response.json()
    assert data["total_vehicles"] == 10
    assert "by_type" in data


@patch("app.analytics.routes.AnalyticsService")
def test_driver_summary_endpoint(mock_service_cls: MagicMock) -> None:
    """GET /api/v1/analytics/driver-summary returns 200 with valid data."""
    instance = MagicMock()
    instance.get_driver_summary = AsyncMock(return_value=_driver_response())
    mock_service_cls.return_value = instance

    client = TestClient(app)
    response = client.get("/api/v1/analytics/driver-summary")
    assert response.status_code == 200
    data = response.json()
    assert data["total_drivers"] == 15


@patch("app.analytics.routes.AnalyticsService")
def test_on_time_performance_endpoint(mock_service_cls: MagicMock) -> None:
    """GET /api/v1/analytics/on-time-performance returns 200."""
    instance = MagicMock()
    instance.get_on_time_performance = AsyncMock(return_value=_on_time_response())
    mock_service_cls.return_value = instance

    client = TestClient(app)
    response = client.get("/api/v1/analytics/on-time-performance")
    assert response.status_code == 200
    data = response.json()
    assert data["total_routes"] == 5


@patch("app.analytics.routes.AnalyticsService")
def test_on_time_performance_bad_date(mock_service_cls: MagicMock) -> None:
    """GET on-time-performance returns 400 for invalid date."""
    instance = MagicMock()
    instance.get_on_time_performance = AsyncMock(side_effect=ValueError("Invalid date format"))
    mock_service_cls.return_value = instance

    client = TestClient(app)
    response = client.get("/api/v1/analytics/on-time-performance?date=2026-03-07")
    assert response.status_code == 400
    assert "Invalid date" in response.json()["detail"]


@patch("app.analytics.routes.AnalyticsService")
def test_on_time_performance_transit_unavailable(mock_service_cls: MagicMock) -> None:
    """GET on-time-performance returns 503 when transit data unavailable."""
    instance = MagicMock()
    instance.get_on_time_performance = AsyncMock(side_effect=Exception("Feed timeout"))
    mock_service_cls.return_value = instance

    client = TestClient(app)
    response = client.get("/api/v1/analytics/on-time-performance")
    assert response.status_code == 503
    assert "temporarily unavailable" in response.json()["detail"]


@patch("app.analytics.routes.AnalyticsService")
def test_overview_endpoint(mock_service_cls: MagicMock) -> None:
    """GET /api/v1/analytics/overview returns combined summary."""
    instance = MagicMock()
    instance.get_fleet_summary = AsyncMock(return_value=_fleet_response())
    instance.get_driver_summary = AsyncMock(return_value=_driver_response())
    instance.get_on_time_performance = AsyncMock(return_value=_on_time_response())
    mock_service_cls.return_value = instance

    client = TestClient(app)
    response = client.get("/api/v1/analytics/overview")
    assert response.status_code == 200
    data = response.json()
    assert "fleet" in data
    assert "drivers" in data
    assert "on_time" in data


@patch("app.analytics.routes.AnalyticsService")
def test_overview_degrades_on_transit_failure(mock_service_cls: MagicMock) -> None:
    """Overview returns 200 even when on-time data unavailable."""
    instance = MagicMock()
    instance.get_fleet_summary = AsyncMock(return_value=_fleet_response())
    instance.get_driver_summary = AsyncMock(return_value=_driver_response())
    instance.get_on_time_performance = AsyncMock(side_effect=Exception("Feed timeout"))
    mock_service_cls.return_value = instance

    client = TestClient(app)
    response = client.get("/api/v1/analytics/overview")
    assert response.status_code == 200
    data = response.json()
    assert data["fleet"]["total_vehicles"] == 10
    assert data["on_time"]["total_routes"] == 0


def test_endpoints_require_auth() -> None:
    """Analytics endpoints return 401 without authentication."""
    app.dependency_overrides.pop(get_current_user, None)
    client = TestClient(app)

    endpoints = [
        "/api/v1/analytics/fleet-summary",
        "/api/v1/analytics/driver-summary",
        "/api/v1/analytics/on-time-performance",
        "/api/v1/analytics/overview",
    ]
    for endpoint in endpoints:
        response = client.get(endpoint)
        assert response.status_code == 401, f"{endpoint} should require auth"
