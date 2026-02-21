"""Tests for Redis vehicle position reader."""

# pyright: reportUnknownMemberType=false, reportMissingTypeStubs=false, reportArgumentType=false

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.transit.redis_reader import get_vehicles_from_redis


def _make_vehicle_json(
    vehicle_id: str = "v1",
    route_id: str = "22",
    feed_id: str = "riga",
) -> str:
    """Create a JSON vehicle position string."""
    return json.dumps(
        {
            "vehicle_id": vehicle_id,
            "route_id": route_id,
            "route_short_name": "22",
            "route_type": 3,
            "latitude": 56.9496,
            "longitude": 24.1052,
            "bearing": 180.0,
            "speed_kmh": 36.0,
            "delay_seconds": 60,
            "current_status": "IN_TRANSIT_TO",
            "next_stop_name": "Centraltirgus",
            "current_stop_name": None,
            "timestamp": "2023-11-14T22:13:20+00:00",
            "feed_id": feed_id,
            "operator_name": "Rigas Satiksme",
        }
    )


def _make_mock_settings() -> MagicMock:
    """Create mock settings with one feed."""
    settings = MagicMock()
    feed = MagicMock()
    feed.feed_id = "riga"
    feed.enabled = True
    settings.transit_feeds = [feed]
    return settings


@pytest.mark.asyncio
@patch("app.transit.redis_reader.get_settings")
@patch("app.transit.redis_reader.get_redis")
async def test_get_vehicles_all_feeds(
    mock_get_redis: AsyncMock,
    mock_get_settings: MagicMock,
) -> None:
    """Reads all vehicles from all configured feeds."""
    mock_redis = AsyncMock()
    mock_redis.smembers = AsyncMock(return_value={"v1", "v2"})
    mock_redis.mget = AsyncMock(
        return_value=[
            _make_vehicle_json("v1"),
            _make_vehicle_json("v2"),
        ]
    )
    mock_get_redis.return_value = mock_redis
    mock_get_settings.return_value = _make_mock_settings()

    result = await get_vehicles_from_redis()

    assert result.count == 2
    assert len(result.vehicles) == 2
    assert result.feed_id is None


@pytest.mark.asyncio
@patch("app.transit.redis_reader.get_settings")
@patch("app.transit.redis_reader.get_redis")
async def test_get_vehicles_by_feed(
    mock_get_redis: AsyncMock,
    mock_get_settings: MagicMock,
) -> None:
    """Feed filter reads only the specified feed."""
    mock_redis = AsyncMock()
    mock_redis.smembers = AsyncMock(return_value={"v1"})
    mock_redis.mget = AsyncMock(return_value=[_make_vehicle_json("v1")])
    mock_get_redis.return_value = mock_redis
    mock_get_settings.return_value = _make_mock_settings()

    result = await get_vehicles_from_redis(feed_id="riga")

    assert result.count == 1
    assert result.feed_id == "riga"
    # Verify only riga feed was read
    mock_redis.smembers.assert_called_once_with("feed:riga:vehicles")


@pytest.mark.asyncio
@patch("app.transit.redis_reader.get_settings")
@patch("app.transit.redis_reader.get_redis")
async def test_get_vehicles_by_route(
    mock_get_redis: AsyncMock,
    mock_get_settings: MagicMock,
) -> None:
    """Route filter returns only matching vehicles."""
    mock_redis = AsyncMock()
    mock_redis.smembers = AsyncMock(return_value={"v1", "v2"})
    mock_redis.mget = AsyncMock(
        return_value=[
            _make_vehicle_json("v1", route_id="22"),
            _make_vehicle_json("v2", route_id="15"),
        ]
    )
    mock_get_redis.return_value = mock_redis
    mock_get_settings.return_value = _make_mock_settings()

    result = await get_vehicles_from_redis(route_id="22")

    assert result.count == 1
    assert result.vehicles[0].route_id == "22"


@pytest.mark.asyncio
@patch("app.transit.redis_reader.get_settings")
@patch("app.transit.redis_reader.get_redis")
async def test_get_vehicles_empty_redis(
    mock_get_redis: AsyncMock,
    mock_get_settings: MagicMock,
) -> None:
    """Empty Redis returns count=0 and empty list."""
    mock_redis = AsyncMock()
    mock_redis.smembers = AsyncMock(return_value=set())
    mock_get_redis.return_value = mock_redis
    mock_get_settings.return_value = _make_mock_settings()

    result = await get_vehicles_from_redis()

    assert result.count == 0
    assert result.vehicles == []


@pytest.mark.asyncio
@patch("app.transit.redis_reader.get_settings")
@patch("app.transit.redis_reader.get_redis")
async def test_get_vehicles_expired_keys(
    mock_get_redis: AsyncMock,
    mock_get_settings: MagicMock,
) -> None:
    """Expired vehicle keys (mget returns None) are skipped."""
    mock_redis = AsyncMock()
    mock_redis.smembers = AsyncMock(return_value={"v1", "v2", "v3"})
    # v2 expired (None), v1 and v3 still valid
    mock_redis.mget = AsyncMock(
        return_value=[
            _make_vehicle_json("v1"),
            None,
            _make_vehicle_json("v3"),
        ]
    )
    mock_get_redis.return_value = mock_redis
    mock_get_settings.return_value = _make_mock_settings()

    result = await get_vehicles_from_redis()

    assert result.count == 2
    vehicle_ids = [v.vehicle_id for v in result.vehicles]
    assert "v1" in vehicle_ids
    assert "v3" in vehicle_ids
