# pyright: reportUnknownMemberType=false
"""Tests for GTFS-Realtime client."""

import time
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.core.agents.exceptions import TransitDataError
from app.core.agents.tools.transit.client import GTFSRealtimeClient, _CacheEntry


def _make_settings() -> MagicMock:
    """Create mock settings with feed URLs and cache TTL."""
    settings = MagicMock()
    settings.gtfs_rt_vehicle_positions_url = "https://example.com/vehicles.pb"
    settings.gtfs_rt_trip_updates_url = "https://example.com/trips.pb"
    settings.gtfs_rt_alerts_url = "https://example.com/alerts.pb"
    settings.gtfs_rt_cache_ttl_seconds = 20
    return settings


def test_cache_entry_freshness():
    entry = _CacheEntry(data=[])
    settings = _make_settings()
    client = GTFSRealtimeClient(AsyncMock(), settings)
    assert client._is_cache_fresh(entry) is True


def test_cache_entry_stale():
    entry = _CacheEntry(data=[], fetched_at=time.monotonic() - 100)
    settings = _make_settings()
    client = GTFSRealtimeClient(AsyncMock(), settings)
    assert client._is_cache_fresh(entry) is False


def test_cache_entry_none():
    settings = _make_settings()
    client = GTFSRealtimeClient(AsyncMock(), settings)
    assert client._is_cache_fresh(None) is False


@pytest.mark.asyncio
async def test_fetch_feed_http_error():
    http_client = AsyncMock()
    http_client.get.side_effect = httpx.ConnectError("Connection refused")
    settings = _make_settings()
    client = GTFSRealtimeClient(http_client, settings)

    with pytest.raises(TransitDataError, match="Transit feed request failed"):
        await client._fetch_feed("https://example.com/feed.pb")


@pytest.mark.asyncio
async def test_parse_feed_malformed():
    settings = _make_settings()
    client = GTFSRealtimeClient(AsyncMock(), settings)

    with pytest.raises(TransitDataError, match="Failed to parse"):
        client._parse_feed(b"not-valid-protobuf")
