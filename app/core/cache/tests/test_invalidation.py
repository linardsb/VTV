# pyright: reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportCallIssue=false
"""Unit tests for CacheInvalidator and convenience functions."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.cache.invalidation import (
    CacheInvalidator,
    invalidate_geofence_cache,
    invalidate_stop_cache,
    invalidate_vehicle_position_cache,
)


@pytest.fixture
def mock_redis() -> AsyncMock:
    """Create a mock Redis client."""
    redis = AsyncMock()
    redis.delete = AsyncMock(return_value=1)
    redis.scan = AsyncMock(return_value=(0, [b"key1", b"key2"]))
    return redis


class TestCacheInvalidator:
    """Tests for CacheInvalidator core methods."""

    async def test_invalidate_exact_keys(self, mock_redis: AsyncMock) -> None:
        """Exact-key invalidation calls redis.delete and returns count."""
        mock_redis.delete = AsyncMock(return_value=2)
        inv = CacheInvalidator(redis=mock_redis)

        result = await inv.invalidate("stops", "stops:1", "stops:2")

        assert result == 2
        mock_redis.delete.assert_awaited_once_with("stops:1", "stops:2")

    async def test_invalidate_empty_keys_returns_zero(self, mock_redis: AsyncMock) -> None:
        """Calling invalidate with no keys returns 0 without touching Redis."""
        inv = CacheInvalidator(redis=mock_redis)

        result = await inv.invalidate("stops")

        assert result == 0
        mock_redis.delete.assert_not_awaited()

    async def test_invalidate_pattern_multi_page(self, mock_redis: AsyncMock) -> None:
        """Pattern invalidation with 2 scan pages deletes all matched keys."""
        mock_redis.scan = AsyncMock(
            side_effect=[
                (42, [b"stops:1", b"stops:2"]),
                (0, [b"stops:3"]),
            ]
        )
        mock_redis.delete = AsyncMock(side_effect=[2, 1])
        inv = CacheInvalidator(redis=mock_redis)

        result = await inv.invalidate_pattern("stops:*", namespace="stops")

        assert result == 3
        assert mock_redis.scan.await_count == 2
        assert mock_redis.delete.await_count == 2

    async def test_invalidate_pattern_single_page(self, mock_redis: AsyncMock) -> None:
        """Pattern invalidation with all keys in one page."""
        mock_redis.scan = AsyncMock(return_value=(0, [b"stops:1"]))
        mock_redis.delete = AsyncMock(return_value=1)
        inv = CacheInvalidator(redis=mock_redis)

        result = await inv.invalidate_pattern("stops:*", namespace="stops")

        assert result == 1
        mock_redis.scan.assert_awaited_once()

    async def test_invalidate_pattern_no_matches(self, mock_redis: AsyncMock) -> None:
        """Pattern invalidation with no matches returns 0."""
        mock_redis.scan = AsyncMock(return_value=(0, []))
        inv = CacheInvalidator(redis=mock_redis)

        result = await inv.invalidate_pattern("stops:*", namespace="stops")

        assert result == 0
        mock_redis.delete.assert_not_awaited()

    async def test_redis_failure_swallowed(self, mock_redis: AsyncMock) -> None:
        """Redis errors are caught and logged, not raised."""
        mock_redis.delete = AsyncMock(side_effect=ConnectionError("down"))
        inv = CacheInvalidator(redis=mock_redis)

        result = await inv.invalidate("stops", "stops:1")

        assert result == 0


class TestConvenienceFunctions:
    """Tests for module-level invalidation hooks."""

    @patch(
        "app.core.cache.invalidation.get_redis",
        new_callable=AsyncMock,
    )
    async def test_stop_cache_specific_id(self, mock_get_redis: AsyncMock) -> None:
        """invalidate_stop_cache(42) deletes stops:42."""
        mock_redis = AsyncMock()
        mock_redis.delete = AsyncMock(return_value=1)
        mock_get_redis.return_value = mock_redis

        result = await invalidate_stop_cache(42)

        assert result == 1
        mock_redis.delete.assert_awaited_once_with("stops:42")

    @patch(
        "app.core.cache.invalidation.get_redis",
        new_callable=AsyncMock,
    )
    async def test_stop_cache_all(self, mock_get_redis: AsyncMock) -> None:
        """invalidate_stop_cache() with no ID scans stops:* pattern."""
        mock_redis = AsyncMock()
        mock_redis.scan = AsyncMock(return_value=(0, [b"stops:1"]))
        mock_redis.delete = AsyncMock(return_value=1)
        mock_get_redis.return_value = mock_redis

        result = await invalidate_stop_cache()

        assert result == 1
        mock_redis.scan.assert_awaited_once()

    @patch(
        "app.core.cache.invalidation.get_redis",
        new_callable=AsyncMock,
    )
    async def test_geofence_cache_invalidation(self, mock_get_redis: AsyncMock) -> None:
        """invalidate_geofence_cache scans geofences:spatial:* pattern."""
        mock_redis = AsyncMock()
        mock_redis.scan = AsyncMock(return_value=(0, [b"geofences:spatial:1"]))
        mock_redis.delete = AsyncMock(return_value=1)
        mock_get_redis.return_value = mock_redis

        result = await invalidate_geofence_cache()

        assert result == 1
        mock_redis.scan.assert_awaited_once()

    @patch(
        "app.core.cache.invalidation.get_redis",
        new_callable=AsyncMock,
    )
    async def test_vehicle_position_cache_specific(self, mock_get_redis: AsyncMock) -> None:
        """invalidate_vehicle_position_cache with feed+vehicle deletes exact key."""
        mock_redis = AsyncMock()
        mock_redis.delete = AsyncMock(return_value=1)
        mock_get_redis.return_value = mock_redis

        result = await invalidate_vehicle_position_cache(feed_id="riga", vehicle_id="bus42")

        assert result == 1
        mock_redis.delete.assert_awaited_once_with("vehicle:riga:bus42")


class TestMetrics:
    """Test Prometheus metric recording."""

    @patch("app.core.cache.invalidation.REDIS_CACHE_INVALIDATIONS")
    @patch("app.core.cache.invalidation.get_settings")
    async def test_metric_emission_when_enabled(
        self,
        mock_get_settings: MagicMock,
        mock_counter: MagicMock,
    ) -> None:
        """With metrics_enabled=True, counter is incremented."""
        mock_get_settings.return_value.metrics_enabled = True
        mock_redis = AsyncMock()
        mock_redis.delete = AsyncMock(return_value=3)
        inv = CacheInvalidator(redis=mock_redis)

        await inv.invalidate("stops", "stops:1", "stops:2", "stops:3")

        mock_counter.labels.assert_called_once_with(cache_name="stops")
        mock_counter.labels.return_value.inc.assert_called_once_with(3)
