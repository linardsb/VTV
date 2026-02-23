"""Tests for daily query quota tracker."""

from unittest.mock import patch

import pytest

from app.core.agents.quota import QueryQuotaTracker


def _make_tracker(daily_limit: int) -> QueryQuotaTracker:
    """Create a quota tracker that always uses in-memory fallback."""
    return QueryQuotaTracker(daily_limit=daily_limit)


@pytest.mark.asyncio
async def test_quota_allows_within_limit() -> None:
    tracker = _make_tracker(daily_limit=3)
    with patch("app.core.redis.get_redis", side_effect=Exception("no redis")):
        assert await tracker.check_and_increment("1.2.3.4") is True
        assert await tracker.check_and_increment("1.2.3.4") is True
        assert await tracker.check_and_increment("1.2.3.4") is True


@pytest.mark.asyncio
async def test_quota_rejects_over_limit() -> None:
    tracker = _make_tracker(daily_limit=2)
    with patch("app.core.redis.get_redis", side_effect=Exception("no redis")):
        assert await tracker.check_and_increment("1.2.3.4") is True
        assert await tracker.check_and_increment("1.2.3.4") is True
        assert await tracker.check_and_increment("1.2.3.4") is False


@pytest.mark.asyncio
async def test_quota_tracks_per_ip() -> None:
    tracker = _make_tracker(daily_limit=1)
    with patch("app.core.redis.get_redis", side_effect=Exception("no redis")):
        assert await tracker.check_and_increment("1.1.1.1") is True
        assert await tracker.check_and_increment("2.2.2.2") is True
        assert await tracker.check_and_increment("1.1.1.1") is False
        assert await tracker.check_and_increment("2.2.2.2") is False


@pytest.mark.asyncio
async def test_quota_get_remaining() -> None:
    tracker = _make_tracker(daily_limit=5)
    with patch("app.core.redis.get_redis", side_effect=Exception("no redis")):
        assert await tracker.get_remaining("1.2.3.4") == 5
        await tracker.check_and_increment("1.2.3.4")
        assert await tracker.get_remaining("1.2.3.4") == 4


@pytest.mark.asyncio
async def test_quota_get_remaining_at_zero() -> None:
    tracker = _make_tracker(daily_limit=1)
    with patch("app.core.redis.get_redis", side_effect=Exception("no redis")):
        await tracker.check_and_increment("1.2.3.4")
        assert await tracker.get_remaining("1.2.3.4") == 0
