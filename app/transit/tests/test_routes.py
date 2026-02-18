"""Tests for transit REST API routes."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.agents.exceptions import TransitDataError
from app.main import app
from app.transit.schemas import VehiclePosition, VehiclePositionsResponse


def _make_response(count: int = 2) -> VehiclePositionsResponse:
    """Create a mock VehiclePositionsResponse."""
    vehicles = [
        VehiclePosition(
            vehicle_id=f"v{i}",
            route_id="22",
            route_short_name="22",
            route_type=3,
            latitude=56.9496,
            longitude=24.1052,
            bearing=180.0,
            speed_kmh=36.0,
            delay_seconds=60,
            current_status="IN_TRANSIT_TO",
            next_stop_name="Centraltirgus",
            current_stop_name="Stacija",
            timestamp="2023-11-14T22:13:20+00:00",
        )
        for i in range(count)
    ]
    return VehiclePositionsResponse(
        count=count,
        vehicles=vehicles,
        fetched_at="2023-11-14T22:13:20+00:00",
    )


@pytest.mark.asyncio
@patch("app.transit.routes.get_transit_service")
async def test_get_vehicles_success(mock_get_service: MagicMock) -> None:
    """GET /api/v1/transit/vehicles returns 200 with vehicle data."""
    mock_service = MagicMock()
    mock_service.get_vehicle_positions = AsyncMock(return_value=_make_response(2))
    mock_get_service.return_value = mock_service

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/v1/transit/vehicles")

    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 2
    assert len(data["vehicles"]) == 2


@pytest.mark.asyncio
@patch("app.transit.routes.get_transit_service")
async def test_get_vehicles_with_route_filter(mock_get_service: MagicMock) -> None:
    """GET /api/v1/transit/vehicles?route_id=22 passes filter to service."""
    mock_service = MagicMock()
    mock_service.get_vehicle_positions = AsyncMock(return_value=_make_response(1))
    mock_get_service.return_value = mock_service

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/v1/transit/vehicles?route_id=22")

    assert response.status_code == 200
    mock_service.get_vehicle_positions.assert_called_once_with(route_id="22")


@pytest.mark.asyncio
@patch("app.transit.routes.get_transit_service")
async def test_get_vehicles_transit_error(mock_get_service: MagicMock) -> None:
    """TransitDataError maps to HTTP 503."""
    mock_service = MagicMock()
    mock_service.get_vehicle_positions = AsyncMock(
        side_effect=TransitDataError("Feed unavailable"),
    )
    mock_get_service.return_value = mock_service

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/v1/transit/vehicles")

    assert response.status_code == 503
