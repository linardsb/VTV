"""Tests for poller historical position write path."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import TransitFeedConfig
from app.transit.poller import FeedPoller


def _make_feed_config() -> TransitFeedConfig:
    return TransitFeedConfig(
        feed_id="test",
        operator_name="Test Operator",
        rt_vehicle_positions_url="http://test/vp.pb",
        rt_trip_updates_url="http://test/tu.pb",
        static_url="http://test/gtfs.zip",
    )


def _make_mock_redis() -> AsyncMock:
    """Create a mock Redis client with pipeline support."""
    mock_redis = AsyncMock()
    mock_pipeline = MagicMock()
    mock_pipeline.set = MagicMock()
    mock_pipeline.delete = MagicMock()
    mock_pipeline.sadd = MagicMock()
    mock_pipeline.expire = MagicMock()
    mock_pipeline.execute = AsyncMock(return_value=[])
    mock_redis.pipeline = MagicMock(return_value=mock_pipeline)
    mock_redis.publish = AsyncMock()
    return mock_redis


def _make_mock_vehicle() -> MagicMock:
    """Create a mock VehiclePositionData."""
    mock_vp = MagicMock()
    mock_vp.vehicle_id = "4521"
    mock_vp.route_id = "22"
    mock_vp.trip_id = None
    mock_vp.latitude = 56.9496
    mock_vp.longitude = 24.1052
    mock_vp.bearing = 180.0
    mock_vp.speed = 12.0
    mock_vp.timestamp = 1709827200
    mock_vp.current_status = "IN_TRANSIT_TO"
    mock_vp.stop_id = None
    mock_vp.current_stop_sequence = None
    return mock_vp


class TestPollerHistoryWrite:
    """Tests for the poller's historical position write path."""

    @pytest.mark.asyncio
    async def test_history_write_disabled_skips_db(self) -> None:
        """When position_history_enabled is False, no DB write occurs."""
        settings = MagicMock()
        settings.position_history_enabled = False
        settings.redis_vehicle_ttl_seconds = 120
        settings.poller_enabled = True

        poller = FeedPoller(feed_config=_make_feed_config(), settings=settings)
        mock_redis = _make_mock_redis()

        with (
            patch.object(poller, "_rt_client") as mock_rt,
            patch("app.transit.poller.get_static_store", new_callable=AsyncMock) as mock_store,
        ):
            mock_rt.fetch_vehicle_positions = AsyncMock(return_value=[])
            mock_rt.fetch_trip_updates = AsyncMock(return_value=[])
            mock_store.return_value = MagicMock()

            result = await poller.poll_once(mock_redis)

        assert result == 0

    @pytest.mark.asyncio
    async def test_history_write_failure_does_not_block_poller(self) -> None:
        """DB write failure must not prevent Redis writes or crash the poller."""
        settings = MagicMock()
        settings.position_history_enabled = True
        settings.redis_vehicle_ttl_seconds = 120
        settings.poller_enabled = True

        poller = FeedPoller(feed_config=_make_feed_config(), settings=settings)

        # Mock a DB session factory that raises
        @asynccontextmanager
        async def failing_db() -> AsyncIterator[AsyncMock]:
            raise RuntimeError("DB unavailable")
            yield AsyncMock()  # pragma: no cover

        poller._db_session_factory = failing_db

        mock_redis = _make_mock_redis()
        mock_vp = _make_mock_vehicle()

        mock_static = MagicMock()
        mock_static.get_trip_route_id.return_value = None
        mock_static.get_route_name.return_value = "22"
        mock_static.routes = {"22": MagicMock(route_type=3)}
        mock_static.get_stop_name.return_value = None

        with (
            patch.object(poller, "_rt_client") as mock_rt,
            patch("app.transit.poller.get_static_store", new_callable=AsyncMock) as mock_store,
        ):
            mock_rt.fetch_vehicle_positions = AsyncMock(return_value=[mock_vp])
            mock_rt.fetch_trip_updates = AsyncMock(return_value=[])
            mock_store.return_value = mock_static

            result = await poller.poll_once(mock_redis)

        # Redis write should still succeed
        assert result == 1
        mock_redis.pipeline.return_value.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_history_write_success(self) -> None:
        """When history is enabled and DB works, records are inserted."""
        settings = MagicMock()
        settings.position_history_enabled = True
        settings.redis_vehicle_ttl_seconds = 120
        settings.poller_enabled = True

        poller = FeedPoller(feed_config=_make_feed_config(), settings=settings)

        mock_db_session = AsyncMock()

        @asynccontextmanager
        async def mock_db_factory() -> AsyncIterator[AsyncMock]:
            yield mock_db_session

        poller._db_session_factory = mock_db_factory

        mock_redis = _make_mock_redis()
        mock_vp = _make_mock_vehicle()

        mock_static = MagicMock()
        mock_static.get_trip_route_id.return_value = None
        mock_static.get_route_name.return_value = "22"
        mock_static.routes = {"22": MagicMock(route_type=3)}
        mock_static.get_stop_name.return_value = None

        with (
            patch.object(poller, "_rt_client") as mock_rt,
            patch("app.transit.poller.get_static_store", new_callable=AsyncMock) as mock_store,
            patch(
                "app.transit.repository.batch_insert_positions",
                new_callable=AsyncMock,
                return_value=1,
            ) as mock_insert,
        ):
            mock_rt.fetch_vehicle_positions = AsyncMock(return_value=[mock_vp])
            mock_rt.fetch_trip_updates = AsyncMock(return_value=[])
            mock_store.return_value = mock_static

            result = await poller.poll_once(mock_redis)

        assert result == 1
        mock_insert.assert_awaited_once()
