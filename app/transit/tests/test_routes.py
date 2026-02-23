"""Tests for transit REST API routes."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.core.agents.exceptions import TransitDataError
from app.core.rate_limit import limiter
from app.main import app
from app.transit.schemas import VehiclePosition, VehiclePositionsResponse

# Disable rate limiting during tests
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


# Override auth dependencies for testing
app.dependency_overrides[get_current_user] = _mock_admin_user


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
    mock_service.get_vehicle_positions.assert_called_once_with(route_id="22", feed_id=None)


@pytest.mark.asyncio
@patch("app.transit.routes.get_transit_service")
async def test_get_vehicles_with_feed_id(mock_get_service: MagicMock) -> None:
    """GET /api/v1/transit/vehicles?feed_id=riga passes feed filter to service."""
    mock_service = MagicMock()
    mock_service.get_vehicle_positions = AsyncMock(return_value=_make_response(1))
    mock_get_service.return_value = mock_service

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/v1/transit/vehicles?feed_id=riga")

    assert response.status_code == 200
    mock_service.get_vehicle_positions.assert_called_once_with(route_id=None, feed_id="riga")


@pytest.mark.asyncio
@patch("app.transit.routes.get_transit_service")
async def test_get_vehicles_with_both_filters(mock_get_service: MagicMock) -> None:
    """GET /api/v1/transit/vehicles?feed_id=riga&route_id=22 passes both filters."""
    mock_service = MagicMock()
    mock_service.get_vehicle_positions = AsyncMock(return_value=_make_response(1))
    mock_get_service.return_value = mock_service

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/v1/transit/vehicles?feed_id=riga&route_id=22")

    assert response.status_code == 200
    mock_service.get_vehicle_positions.assert_called_once_with(route_id="22", feed_id="riga")


@pytest.mark.asyncio
@patch("app.transit.routes.get_settings")
async def test_get_feeds(mock_get_settings: MagicMock) -> None:
    """GET /api/v1/transit/feeds returns configured feeds."""
    feed1 = MagicMock()
    feed1.feed_id = "riga"
    feed1.operator_name = "Rigas Satiksme"
    feed1.enabled = True
    feed1.poll_interval_seconds = 10

    feed2 = MagicMock()
    feed2.feed_id = "jurmala"
    feed2.operator_name = "Jurmala Transit"
    feed2.enabled = False
    feed2.poll_interval_seconds = 15

    settings = MagicMock()
    settings.transit_feeds = [feed1, feed2]
    mock_get_settings.return_value = settings

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/v1/transit/feeds")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["feed_id"] == "riga"
    assert data[0]["enabled"] is True
    assert data[1]["feed_id"] == "jurmala"
    assert data[1]["enabled"] is False


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
