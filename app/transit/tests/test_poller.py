"""Tests for the GTFS-RT background poller."""

# pyright: reportUnknownMemberType=false, reportMissingTypeStubs=false, reportArgumentType=false

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.agents.tools.transit.client import (
    StopTimeUpdateData,
    TripUpdateData,
    VehiclePositionData,
)
from app.core.config import TransitFeedConfig
from app.transit.poller import FeedPoller, start_pollers, stop_pollers


def _make_feed_config() -> TransitFeedConfig:
    """Create a test feed config."""
    return TransitFeedConfig(
        feed_id="riga",
        operator_name="Rigas Satiksme",
        rt_vehicle_positions_url="https://example.com/vehicle_positions.pb",
        rt_trip_updates_url="https://example.com/trip_updates.pb",
        static_url="https://example.com/gtfs.zip",
        poll_interval_seconds=10,
    )


def _make_mock_settings() -> MagicMock:
    """Create mock settings for poller tests."""
    settings = MagicMock()
    settings.redis_vehicle_ttl_seconds = 120
    settings.poller_enabled = True
    settings.gtfs_rt_cache_ttl_seconds = 10
    settings.gtfs_static_cache_ttl_hours = 24
    settings.transit_feeds = [_make_feed_config()]
    return settings


def _make_vehicle_position(
    vehicle_id: str = "4521",
    trip_id: str | None = "trip_1",
    route_id: str | None = "22",
    speed: float | None = 10.0,
    stop_id: str | None = "stop_100",
    current_stop_sequence: int | None = 5,
) -> VehiclePositionData:
    """Create a VehiclePositionData for testing."""
    return VehiclePositionData(
        vehicle_id=vehicle_id,
        trip_id=trip_id,
        route_id=route_id,
        latitude=56.9496,
        longitude=24.1052,
        bearing=180.0,
        speed=speed,
        current_stop_sequence=current_stop_sequence,
        current_status="IN_TRANSIT_TO",
        stop_id=stop_id,
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
    cache.routes = {"22": route_info}
    return cache


@pytest.mark.asyncio
async def test_enrich_vehicle_basic() -> None:
    """Basic enrichment resolves route name and feed info."""
    poller = FeedPoller(feed_config=_make_feed_config(), settings=_make_mock_settings())
    vp = _make_vehicle_position()
    static = _make_static_cache()

    result = poller._enrich_vehicle(vp, {}, static)

    assert result["feed_id"] == "riga"
    assert result["operator_name"] == "Rigas Satiksme"
    assert result["route_id"] == "22"
    assert result["route_short_name"] == "22"
    assert result["vehicle_id"] == "4521"
    await poller.close()


@pytest.mark.asyncio
async def test_enrich_vehicle_with_delay() -> None:
    """Delay is extracted from matching trip update."""
    poller = FeedPoller(feed_config=_make_feed_config(), settings=_make_mock_settings())
    vp = _make_vehicle_position()
    tu = TripUpdateData(
        trip_id="trip_1",
        route_id="22",
        vehicle_id=None,
        stop_time_updates=[
            StopTimeUpdateData(
                stop_sequence=6,
                stop_id="stop_101",
                arrival_delay=120,
                departure_delay=120,
                arrival_time=None,
                departure_time=None,
            ),
        ],
        timestamp=1700000000,
    )
    static = _make_static_cache()

    result = poller._enrich_vehicle(vp, {"trip_1": tu}, static)

    assert result["delay_seconds"] == 120
    await poller.close()


@pytest.mark.asyncio
async def test_enrich_vehicle_speed_conversion() -> None:
    """Speed converts from m/s to km/h."""
    poller = FeedPoller(feed_config=_make_feed_config(), settings=_make_mock_settings())
    vp = _make_vehicle_position(speed=10.0)
    static = _make_static_cache()

    result = poller._enrich_vehicle(vp, {}, static)

    assert result["speed_kmh"] == 36.0
    await poller.close()


@pytest.mark.asyncio
async def test_enrich_vehicle_no_route() -> None:
    """Vehicle with no route_id and no trip_id gets empty route."""
    poller = FeedPoller(feed_config=_make_feed_config(), settings=_make_mock_settings())
    vp = _make_vehicle_position(route_id=None, trip_id=None)
    static = _make_static_cache()

    result = poller._enrich_vehicle(vp, {}, static)

    assert result["route_id"] == ""
    assert result["route_short_name"] == ""
    await poller.close()


@pytest.mark.asyncio
@patch("app.transit.poller.get_static_cache")
@patch("app.transit.poller.GTFSRealtimeClient")
async def test_poll_once_writes_to_redis(
    mock_client_cls: MagicMock,
    mock_get_cache: AsyncMock,
) -> None:
    """poll_once writes vehicles to Redis with correct key pattern."""
    settings = _make_mock_settings()
    poller = FeedPoller(feed_config=_make_feed_config(), settings=settings)

    vehicles = [
        _make_vehicle_position(vehicle_id="v1"),
        _make_vehicle_position(vehicle_id="v2"),
    ]

    instance = mock_client_cls.return_value
    instance.fetch_vehicle_positions = AsyncMock(return_value=vehicles)
    instance.fetch_trip_updates = AsyncMock(return_value=[])
    mock_get_cache.return_value = _make_static_cache()

    mock_redis = MagicMock()
    mock_pipe = MagicMock()
    mock_pipe.execute = AsyncMock(return_value=[])
    mock_redis.pipeline.return_value = mock_pipe

    count = await poller.poll_once(mock_redis)

    assert count == 2
    assert mock_pipe.set.call_count == 2
    # Verify key pattern
    first_call_args = mock_pipe.set.call_args_list[0]
    assert first_call_args[0][0] == "vehicle:riga:v1"
    # Verify feed vehicle tracking
    mock_pipe.sadd.assert_called_once()
    mock_pipe.execute.assert_called_once()
    await poller.close()


@pytest.mark.asyncio
@patch("app.transit.poller.get_static_cache")
@patch("app.transit.poller.GTFSRealtimeClient")
async def test_poll_once_handles_fetch_error(
    mock_client_cls: MagicMock,
    mock_get_cache: AsyncMock,
) -> None:
    """Fetch errors are caught and logged, returning 0 vehicles."""
    settings = _make_mock_settings()
    poller = FeedPoller(feed_config=_make_feed_config(), settings=settings)

    instance = mock_client_cls.return_value
    instance.fetch_vehicle_positions = AsyncMock(
        side_effect=Exception("Network error"),
    )
    mock_get_cache.return_value = _make_static_cache()

    mock_redis = AsyncMock()
    count = await poller.poll_once(mock_redis)

    assert count == 0
    await poller.close()


@pytest.mark.asyncio
@patch("app.transit.poller.get_redis")
@patch("app.transit.poller.get_settings")
async def test_start_stop_pollers(
    mock_get_settings: MagicMock,
    mock_get_redis: AsyncMock,
) -> None:
    """start_pollers creates tasks, stop_pollers cancels them."""
    from app.transit import poller

    # Clear module-level state
    poller._poller_tasks.clear()
    poller._feed_pollers.clear()

    settings = _make_mock_settings()
    mock_get_settings.return_value = settings
    mock_get_redis.return_value = AsyncMock()

    # Patch FeedPoller.run to just sleep forever
    with patch.object(FeedPoller, "run", new_callable=AsyncMock) as mock_run:
        mock_run.side_effect = asyncio.CancelledError()

        await start_pollers()
        assert len(poller._poller_tasks) == 1
        assert len(poller._feed_pollers) == 1

        await stop_pollers()
        assert len(poller._poller_tasks) == 0
        assert len(poller._feed_pollers) == 0
