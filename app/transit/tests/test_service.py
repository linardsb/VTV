"""Tests for transit service layer."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.agents.exceptions import TransitDataError
from app.core.agents.tools.transit.client import (
    StopTimeUpdateData,
    TripUpdateData,
    VehiclePositionData,
)
from app.transit.schemas import VehiclePosition, VehiclePositionsResponse
from app.transit.service import TransitService


def _make_vehicle_position(
    vehicle_id: str = "4521",
    trip_id: str | None = "trip_1",
    route_id: str | None = "22",
    latitude: float = 56.9496,
    longitude: float = 24.1052,
    bearing: float | None = 180.0,
    speed: float | None = 10.0,
    current_stop_sequence: int | None = 5,
    current_status: str = "IN_TRANSIT_TO",
    stop_id: str | None = "stop_100",
    timestamp: int = 1700000000,
) -> VehiclePositionData:
    """Create a VehiclePositionData for testing."""
    return VehiclePositionData(
        vehicle_id=vehicle_id,
        trip_id=trip_id,
        route_id=route_id,
        latitude=latitude,
        longitude=longitude,
        bearing=bearing,
        speed=speed,
        current_stop_sequence=current_stop_sequence,
        current_status=current_status,
        stop_id=stop_id,
        timestamp=timestamp,
    )


def _make_trip_update(
    trip_id: str = "trip_1",
    route_id: str | None = "22",
    delay: int = 120,
    stop_id: str | None = "stop_101",
) -> TripUpdateData:
    """Create a TripUpdateData for testing."""
    return TripUpdateData(
        trip_id=trip_id,
        route_id=route_id,
        vehicle_id=None,
        stop_time_updates=[
            StopTimeUpdateData(
                stop_sequence=6,
                stop_id=stop_id,
                arrival_delay=delay,
                departure_delay=delay,
                arrival_time=None,
                departure_time=None,
            ),
        ],
        timestamp=1700000000,
    )


def _make_static_cache() -> MagicMock:
    """Create a mock GTFSStaticCache."""
    cache = MagicMock()
    cache.get_route_name.return_value = "22"
    cache.get_stop_name.return_value = "Centraltirgus"
    cache.get_trip_route_id.return_value = "22"
    route_info = MagicMock()
    route_info.route_type = 3
    cache.routes = {"22": route_info, "15": route_info}
    return cache


@pytest.mark.asyncio
@patch("app.transit.service.get_static_cache")
@patch("app.transit.service.GTFSRealtimeClient")
async def test_get_vehicle_positions_success(
    mock_client_cls: MagicMock,
    mock_get_cache: AsyncMock,
) -> None:
    """Happy path: 3 vehicles with delays and stop names."""
    vehicles = [
        _make_vehicle_position(vehicle_id="v1", route_id="22", trip_id="t1"),
        _make_vehicle_position(vehicle_id="v2", route_id="15", trip_id="t2"),
        _make_vehicle_position(vehicle_id="v3", route_id="22", trip_id="t3"),
    ]
    trip_updates = [
        _make_trip_update(trip_id="t1", delay=60),
        _make_trip_update(trip_id="t2", delay=-30),
        _make_trip_update(trip_id="t3", delay=300),
    ]

    instance = mock_client_cls.return_value
    instance.fetch_vehicle_positions = AsyncMock(return_value=vehicles)
    instance.fetch_trip_updates = AsyncMock(return_value=trip_updates)
    mock_get_cache.return_value = _make_static_cache()

    mock_settings = MagicMock()
    mock_settings.poller_enabled = False
    service = TransitService(
        http_client=MagicMock(),
        settings=mock_settings,
    )
    response = await service.get_vehicle_positions()

    assert response.count == 3
    assert len(response.vehicles) == 3
    assert response.vehicles[0].route_short_name == "22"
    assert response.vehicles[0].delay_seconds == 60
    assert response.fetched_at != ""


@pytest.mark.asyncio
@patch("app.transit.service.get_static_cache")
@patch("app.transit.service.GTFSRealtimeClient")
async def test_get_vehicle_positions_with_route_filter(
    mock_client_cls: MagicMock,
    mock_get_cache: AsyncMock,
) -> None:
    """Route filter returns only matching vehicles."""
    vehicles = [
        _make_vehicle_position(vehicle_id="v1", route_id="22"),
        _make_vehicle_position(vehicle_id="v2", route_id="15"),
        _make_vehicle_position(vehicle_id="v3", route_id="22"),
    ]

    instance = mock_client_cls.return_value
    instance.fetch_vehicle_positions = AsyncMock(return_value=vehicles)
    instance.fetch_trip_updates = AsyncMock(return_value=[])
    mock_get_cache.return_value = _make_static_cache()

    mock_settings = MagicMock()
    mock_settings.poller_enabled = False
    service = TransitService(http_client=MagicMock(), settings=mock_settings)
    response = await service.get_vehicle_positions(route_id="22")

    assert response.count == 2
    assert all(v.route_id == "22" for v in response.vehicles)


@pytest.mark.asyncio
@patch("app.transit.service.get_static_cache")
@patch("app.transit.service.GTFSRealtimeClient")
async def test_get_vehicle_positions_empty(
    mock_client_cls: MagicMock,
    mock_get_cache: AsyncMock,
) -> None:
    """Empty vehicle list returns count=0."""
    instance = mock_client_cls.return_value
    instance.fetch_vehicle_positions = AsyncMock(return_value=[])
    instance.fetch_trip_updates = AsyncMock(return_value=[])
    mock_get_cache.return_value = _make_static_cache()

    mock_settings = MagicMock()
    mock_settings.poller_enabled = False
    service = TransitService(http_client=MagicMock(), settings=mock_settings)
    response = await service.get_vehicle_positions()

    assert response.count == 0
    assert response.vehicles == []


@pytest.mark.asyncio
@patch("app.transit.service.get_static_cache")
@patch("app.transit.service.GTFSRealtimeClient")
async def test_get_vehicle_positions_transit_error(
    mock_client_cls: MagicMock,
    mock_get_cache: AsyncMock,
) -> None:
    """TransitDataError propagates from service."""
    instance = mock_client_cls.return_value
    instance.fetch_vehicle_positions = AsyncMock(
        side_effect=TransitDataError("Feed unavailable"),
    )
    mock_get_cache.return_value = _make_static_cache()

    mock_settings = MagicMock()
    mock_settings.poller_enabled = False
    service = TransitService(http_client=MagicMock(), settings=mock_settings)

    with pytest.raises(TransitDataError, match="Feed unavailable"):
        await service.get_vehicle_positions()


@pytest.mark.asyncio
@patch("app.transit.service.get_static_cache")
@patch("app.transit.service.GTFSRealtimeClient")
async def test_get_vehicle_positions_speed_conversion(
    mock_client_cls: MagicMock,
    mock_get_cache: AsyncMock,
) -> None:
    """Speed converted from m/s to km/h."""
    vehicles = [_make_vehicle_position(speed=10.0)]

    instance = mock_client_cls.return_value
    instance.fetch_vehicle_positions = AsyncMock(return_value=vehicles)
    instance.fetch_trip_updates = AsyncMock(return_value=[])
    mock_get_cache.return_value = _make_static_cache()

    mock_settings = MagicMock()
    mock_settings.poller_enabled = False
    service = TransitService(http_client=MagicMock(), settings=mock_settings)
    response = await service.get_vehicle_positions()

    assert response.vehicles[0].speed_kmh == 36.0


@pytest.mark.asyncio
@patch("app.transit.service.get_static_cache")
@patch("app.transit.service.GTFSRealtimeClient")
async def test_get_vehicle_positions_null_speed_and_bearing(
    mock_client_cls: MagicMock,
    mock_get_cache: AsyncMock,
) -> None:
    """Null speed and bearing pass through as None."""
    vehicles = [_make_vehicle_position(speed=None, bearing=None)]

    instance = mock_client_cls.return_value
    instance.fetch_vehicle_positions = AsyncMock(return_value=vehicles)
    instance.fetch_trip_updates = AsyncMock(return_value=[])
    mock_get_cache.return_value = _make_static_cache()

    mock_settings = MagicMock()
    mock_settings.poller_enabled = False
    service = TransitService(http_client=MagicMock(), settings=mock_settings)
    response = await service.get_vehicle_positions()

    assert response.vehicles[0].speed_kmh is None
    assert response.vehicles[0].bearing is None


@pytest.mark.asyncio
@patch("app.transit.redis_reader.get_vehicles_from_redis")
async def test_get_vehicle_positions_redis_mode(
    mock_get_from_redis: AsyncMock,
) -> None:
    """When poller is enabled, delegates to Redis reader."""
    mock_response = VehiclePositionsResponse(
        count=1,
        vehicles=[
            VehiclePosition(
                vehicle_id="v1",
                route_id="22",
                route_short_name="22",
                route_type=3,
                latitude=56.9496,
                longitude=24.1052,
                bearing=180.0,
                speed_kmh=36.0,
                delay_seconds=0,
                current_status="IN_TRANSIT_TO",
                timestamp="2023-11-14T22:13:20+00:00",
                feed_id="riga",
                operator_name="Rigas Satiksme",
            )
        ],
        fetched_at="2023-11-14T22:13:20+00:00",
        feed_id="riga",
    )
    mock_get_from_redis.return_value = mock_response

    mock_settings = MagicMock()
    mock_settings.poller_enabled = True
    service = TransitService(http_client=MagicMock(), settings=mock_settings)
    response = await service.get_vehicle_positions(feed_id="riga")

    assert response.count == 1
    assert response.feed_id == "riga"
    mock_get_from_redis.assert_called_once_with(feed_id="riga", route_id=None)


@pytest.mark.asyncio
@patch("app.transit.redis_reader.get_vehicles_from_redis")
async def test_get_vehicle_positions_redis_with_feed_filter(
    mock_get_from_redis: AsyncMock,
) -> None:
    """Redis mode forwards both feed_id and route_id."""
    mock_response = VehiclePositionsResponse(
        count=0,
        vehicles=[],
        fetched_at="2023-11-14T22:13:20+00:00",
        feed_id="riga",
    )
    mock_get_from_redis.return_value = mock_response

    mock_settings = MagicMock()
    mock_settings.poller_enabled = True
    service = TransitService(http_client=MagicMock(), settings=mock_settings)
    response = await service.get_vehicle_positions(feed_id="riga", route_id="22")

    assert response.count == 0
    mock_get_from_redis.assert_called_once_with(feed_id="riga", route_id="22")
