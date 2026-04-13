# pyright: reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Unit tests for route performance analytics endpoints (ML-5.1)."""

from __future__ import annotations

import datetime
from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.analytics.schemas import (
    RouteAnomalyResponse,
    RouteDelayByStopResponse,
    RouteLoadTrendResponse,
    RoutePerformanceTrendResponse,
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
    app.dependency_overrides[get_db] = lambda: AsyncMock()
    yield
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_db, None)


def _perf_response() -> RoutePerformanceTrendResponse:
    return RoutePerformanceTrendResponse(
        route_id="1",
        route_short_name="1",
        window_days=7,
        overall_on_time_percentage=85.0,
        overall_average_delay_seconds=30.0,
        data=[],
        generated_at=datetime.datetime.now(tz=datetime.UTC).isoformat(),
    )


def _delay_response() -> RouteDelayByStopResponse:
    return RouteDelayByStopResponse(
        route_id="1",
        route_short_name="1",
        window_days=7,
        stops=[],
        generated_at=datetime.datetime.now(tz=datetime.UTC).isoformat(),
    )


def _load_response() -> RouteLoadTrendResponse:
    return RouteLoadTrendResponse(
        route_id="1",
        route_short_name="1",
        window_days=7,
        data=[],
        generated_at=datetime.datetime.now(tz=datetime.UTC).isoformat(),
    )


def _anomaly_response() -> RouteAnomalyResponse:
    return RouteAnomalyResponse(
        route_id="1",
        route_short_name="1",
        window_days=7,
        total_anomalies=0,
        data=[],
        generated_at=datetime.datetime.now(tz=datetime.UTC).isoformat(),
    )


# --- Schema tests ---


class TestSchemaInstantiation:
    """Verify all 4 response schema models can be instantiated."""

    def test_perf_response_schema(self) -> None:
        resp = _perf_response()
        assert resp.route_id == "1"
        assert resp.window_days == 7
        assert resp.data == []

    def test_delay_response_schema(self) -> None:
        resp = _delay_response()
        assert resp.route_id == "1"
        assert resp.stops == []

    def test_load_response_schema(self) -> None:
        resp = _load_response()
        assert resp.route_id == "1"
        assert resp.data == []

    def test_anomaly_response_schema(self) -> None:
        resp = _anomaly_response()
        assert resp.total_anomalies == 0
        assert resp.data == []


# --- Endpoint tests ---


class TestRoutePerformanceEndpoint:
    """Test GET /api/v1/analytics/route-performance."""

    @patch("app.analytics.routes.AnalyticsService")
    def test_returns_200(self, mock_svc_cls: MagicMock) -> None:
        mock_svc = mock_svc_cls.return_value
        mock_svc.get_route_performance = AsyncMock(return_value=_perf_response())
        client = TestClient(app)
        resp = client.get("/api/v1/analytics/route-performance?route_id=1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["route_id"] == "1"

    def test_requires_auth(self) -> None:
        app.dependency_overrides.pop(get_current_user, None)
        client = TestClient(app)
        resp = client.get("/api/v1/analytics/route-performance?route_id=1")
        assert resp.status_code == 401
        app.dependency_overrides[get_current_user] = _mock_admin_user

    def test_validates_route_id_format(self) -> None:
        client = TestClient(app)
        resp = client.get("/api/v1/analytics/route-performance?route_id=../etc/passwd")
        assert resp.status_code == 422

    def test_validates_window_enum(self) -> None:
        client = TestClient(app)
        resp = client.get("/api/v1/analytics/route-performance?route_id=1&window=999")
        assert resp.status_code == 422


class TestRouteDelayByStopEndpoint:
    """Test GET /api/v1/analytics/route-delay-by-stop."""

    @patch("app.analytics.routes.AnalyticsService")
    def test_returns_200(self, mock_svc_cls: MagicMock) -> None:
        mock_svc = mock_svc_cls.return_value
        mock_svc.get_route_delay_by_stop = AsyncMock(return_value=_delay_response())
        client = TestClient(app)
        resp = client.get("/api/v1/analytics/route-delay-by-stop?route_id=1")
        assert resp.status_code == 200


class TestRouteLoadTrendEndpoint:
    """Test GET /api/v1/analytics/route-load-trend."""

    @patch("app.analytics.routes.AnalyticsService")
    def test_returns_200(self, mock_svc_cls: MagicMock) -> None:
        mock_svc = mock_svc_cls.return_value
        mock_svc.get_route_load_trend = AsyncMock(return_value=_load_response())
        client = TestClient(app)
        resp = client.get("/api/v1/analytics/route-load-trend?route_id=1")
        assert resp.status_code == 200


class TestRouteAnomalyEndpoint:
    """Test GET /api/v1/analytics/route-anomalies."""

    @patch("app.analytics.routes.AnalyticsService")
    def test_returns_200(self, mock_svc_cls: MagicMock) -> None:
        mock_svc = mock_svc_cls.return_value
        mock_svc.get_route_anomalies = AsyncMock(return_value=_anomaly_response())
        client = TestClient(app)
        resp = client.get("/api/v1/analytics/route-anomalies?route_id=1")
        assert resp.status_code == 200
