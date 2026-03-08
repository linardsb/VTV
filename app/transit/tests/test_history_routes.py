"""Tests for historical position REST API endpoints."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
def mock_current_user() -> AsyncMock:
    """Mock authenticated user with dispatcher role."""
    mock_user = AsyncMock()
    mock_user.id = 1
    mock_user.email = "dispatcher@test.com"
    mock_user.role = "dispatcher"
    mock_user.is_active = True
    return mock_user


@pytest.mark.asyncio
class TestVehicleHistoryEndpoint:
    """Tests for GET /api/v1/transit/vehicles/{vehicle_id}/history."""

    async def test_vehicle_history_returns_positions(self, mock_current_user: AsyncMock) -> None:
        """Happy path: returns historical positions for a vehicle."""
        from app.auth.dependencies import get_current_user
        from app.core.database import get_db
        from app.transit.schemas import HistoricalPosition, VehicleHistoryResponse

        mock_response = VehicleHistoryResponse(
            vehicle_id="4521",
            count=1,
            positions=[
                HistoricalPosition(
                    recorded_at="2026-03-07T12:00:00+00:00",
                    vehicle_id="4521",
                    route_id="22",
                    route_short_name="22",
                    latitude=56.9496,
                    longitude=24.1052,
                    delay_seconds=30,
                    current_status="IN_TRANSIT_TO",
                    feed_id="riga",
                )
            ],
            from_time="2026-03-07T00:00:00+00:00",
            to_time="2026-03-07T23:59:59+00:00",
        )

        mock_service = AsyncMock()
        mock_service.get_history = AsyncMock(return_value=mock_response)

        app.dependency_overrides[get_current_user] = lambda: mock_current_user
        app.dependency_overrides[get_db] = lambda: AsyncMock()

        try:
            with patch("app.transit.routes.get_transit_service", return_value=mock_service):
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.get(
                        "/api/v1/transit/vehicles/4521/history",
                        params={
                            "from_time": "2026-03-07T00:00:00",
                            "to_time": "2026-03-07T23:59:59",
                        },
                    )

            assert response.status_code == 200
            data = response.json()
            assert data["vehicle_id"] == "4521"
            assert data["count"] == 1
            assert len(data["positions"]) == 1
            assert data["positions"][0]["delay_seconds"] == 30
        finally:
            app.dependency_overrides.clear()

    async def test_vehicle_history_missing_params_returns_422(
        self, mock_current_user: AsyncMock
    ) -> None:
        """Missing required time parameters returns 422."""
        from app.auth.dependencies import get_current_user
        from app.core.database import get_db

        app.dependency_overrides[get_current_user] = lambda: mock_current_user
        app.dependency_overrides[get_db] = lambda: AsyncMock()

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(
                    "/api/v1/transit/vehicles/4521/history",
                )

            assert response.status_code == 422
        finally:
            app.dependency_overrides.clear()

    async def test_vehicle_history_unauthorized_role_returns_403(self) -> None:
        """User with viewer role gets 403 on history endpoint."""
        from app.auth.dependencies import get_current_user
        from app.core.database import get_db

        viewer_user = AsyncMock()
        viewer_user.id = 2
        viewer_user.email = "viewer@test.com"
        viewer_user.role = "viewer"
        viewer_user.is_active = True

        app.dependency_overrides[get_current_user] = lambda: viewer_user
        app.dependency_overrides[get_db] = lambda: AsyncMock()

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(
                    "/api/v1/transit/vehicles/4521/history",
                    params={
                        "from_time": "2026-03-07T00:00:00",
                        "to_time": "2026-03-07T23:59:59",
                    },
                )

            assert response.status_code == 403
        finally:
            app.dependency_overrides.clear()


@pytest.mark.asyncio
class TestRouteDelayTrendEndpoint:
    """Tests for GET /api/v1/transit/routes/{route_id}/delay-trend."""

    async def test_delay_trend_returns_data_points(self, mock_current_user: AsyncMock) -> None:
        """Happy path: returns aggregated delay trend data."""
        from app.auth.dependencies import get_current_user
        from app.core.database import get_db
        from app.transit.schemas import (
            RouteDelayTrendPoint,
            RouteDelayTrendResponse,
        )

        mock_response = RouteDelayTrendResponse(
            route_id="22",
            route_short_name="22",
            interval_minutes=60,
            count=1,
            data_points=[
                RouteDelayTrendPoint(
                    time_bucket="2026-03-07T12:00:00+00:00",
                    avg_delay_seconds=45.2,
                    min_delay_seconds=-5,
                    max_delay_seconds=120,
                    sample_count=38,
                )
            ],
            from_time="2026-03-07T00:00:00+00:00",
            to_time="2026-03-07T23:59:59+00:00",
        )

        mock_service = AsyncMock()
        mock_service.get_delay_trend = AsyncMock(return_value=mock_response)

        app.dependency_overrides[get_current_user] = lambda: mock_current_user
        app.dependency_overrides[get_db] = lambda: AsyncMock()

        try:
            with patch("app.transit.routes.get_transit_service", return_value=mock_service):
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.get(
                        "/api/v1/transit/routes/22/delay-trend",
                        params={
                            "from_time": "2026-03-07T00:00:00",
                            "to_time": "2026-03-07T23:59:59",
                        },
                    )

            assert response.status_code == 200
            data = response.json()
            assert data["route_id"] == "22"
            assert data["count"] == 1
            assert data["data_points"][0]["sample_count"] == 38
            assert data["data_points"][0]["avg_delay_seconds"] == 45.2
        finally:
            app.dependency_overrides.clear()

    async def test_delay_trend_custom_interval(self, mock_current_user: AsyncMock) -> None:
        """Custom interval_minutes parameter is accepted."""
        from app.auth.dependencies import get_current_user
        from app.core.database import get_db
        from app.transit.schemas import RouteDelayTrendResponse

        mock_response = RouteDelayTrendResponse(
            route_id="22",
            route_short_name="22",
            interval_minutes=15,
            count=0,
            data_points=[],
            from_time="2026-03-07T00:00:00+00:00",
            to_time="2026-03-07T23:59:59+00:00",
        )

        mock_service = AsyncMock()
        mock_service.get_delay_trend = AsyncMock(return_value=mock_response)

        app.dependency_overrides[get_current_user] = lambda: mock_current_user
        app.dependency_overrides[get_db] = lambda: AsyncMock()

        try:
            with patch("app.transit.routes.get_transit_service", return_value=mock_service):
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.get(
                        "/api/v1/transit/routes/22/delay-trend",
                        params={
                            "from_time": "2026-03-07T00:00:00",
                            "to_time": "2026-03-07T23:59:59",
                            "interval_minutes": 15,
                        },
                    )

            assert response.status_code == 200
            data = response.json()
            assert data["interval_minutes"] == 15
        finally:
            app.dependency_overrides.clear()
