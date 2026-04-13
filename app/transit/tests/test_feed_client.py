"""Tests for pluggable feed clients (DaugavpilsScraper, GpsTextClient)."""

# pyright: reportUnknownMemberType=false, reportMissingTypeStubs=false, reportArgumentType=false

import time
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.core.agents.exceptions import TransitDataError
from app.core.agents.tools.transit.client import GTFSRealtimeClient
from app.core.config import TransitFeedConfig
from app.transit.feed_client import (
    DaugavpilsScraper,
    GpsTextClient,
    create_feed_client,
)


def _make_feed_config(
    feed_type: str = "gtfs_rt",
    feed_id: str = "test",
) -> TransitFeedConfig:
    """Create a test feed config with the given feed_type."""
    return TransitFeedConfig(
        feed_id=feed_id,
        operator_name="Test Transit",
        rt_vehicle_positions_url="https://example.com/data",
        feed_type=feed_type,
    )


def _make_http_client() -> AsyncMock:
    """Create a mock httpx.AsyncClient."""
    return AsyncMock(spec=httpx.AsyncClient)


def _now_ts() -> int:
    """Current POSIX timestamp."""
    return int(time.time())


# --- DaugavpilsScraper tests ---


@pytest.mark.asyncio
async def test_scraper_success() -> None:
    """Valid JSON response produces VehiclePositionData list."""
    now = _now_ts()
    http = _make_http_client()
    response = MagicMock()
    response.json.return_value = [
        {
            "id": "bus-42",
            "lat": 55.88,
            "lng": 26.53,
            "route": "5",
            "bearing": 90.0,
            "speed": 8.5,
            "timestamp": now,
        },
        {
            "id": "bus-43",
            "lat": 55.89,
            "lng": 26.54,
            "route": "3",
            "bearing": 180.0,
            "speed": 12.0,
            "timestamp": now,
        },
    ]
    response.raise_for_status = MagicMock()
    http.get = AsyncMock(return_value=response)

    config = _make_feed_config(feed_type="scraper", feed_id="daugavpils")
    scraper = DaugavpilsScraper(feed_config=config, http_client=http)
    vehicles = await scraper.fetch_vehicle_positions()

    assert len(vehicles) == 2
    assert vehicles[0].vehicle_id == "bus-42"
    assert vehicles[0].latitude == 55.88
    assert vehicles[0].longitude == 26.53
    assert vehicles[0].route_id == "5"
    assert vehicles[1].vehicle_id == "bus-43"


@pytest.mark.asyncio
async def test_scraper_invalid_coordinates() -> None:
    """Vehicle with coordinates outside Latvia bbox is skipped."""
    http = _make_http_client()
    response = MagicMock()
    response.json.return_value = [
        {"id": "bus-1", "lat": 40.0, "lng": 26.0, "route": "1"},  # lat too low
    ]
    response.raise_for_status = MagicMock()
    http.get = AsyncMock(return_value=response)

    config = _make_feed_config(feed_type="scraper", feed_id="daugavpils")
    scraper = DaugavpilsScraper(feed_config=config, http_client=http)
    vehicles = await scraper.fetch_vehicle_positions()

    assert len(vehicles) == 0


@pytest.mark.asyncio
async def test_scraper_invalid_vehicle_id() -> None:
    """Vehicle with special chars in ID is skipped."""
    http = _make_http_client()
    response = MagicMock()
    response.json.return_value = [
        {"id": "bus<script>", "lat": 56.0, "lng": 26.0, "route": "1"},
    ]
    response.raise_for_status = MagicMock()
    http.get = AsyncMock(return_value=response)

    config = _make_feed_config(feed_type="scraper", feed_id="daugavpils")
    scraper = DaugavpilsScraper(feed_config=config, http_client=http)
    vehicles = await scraper.fetch_vehicle_positions()

    assert len(vehicles) == 0


@pytest.mark.asyncio
async def test_scraper_http_error() -> None:
    """HTTP connection error raises TransitDataError."""
    http = _make_http_client()
    http.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

    config = _make_feed_config(feed_type="scraper", feed_id="daugavpils")
    scraper = DaugavpilsScraper(feed_config=config, http_client=http)

    with pytest.raises(TransitDataError):
        await scraper.fetch_vehicle_positions()


@pytest.mark.asyncio
async def test_scraper_empty_response() -> None:
    """Empty JSON array returns empty list."""
    http = _make_http_client()
    response = MagicMock()
    response.json.return_value = []
    response.raise_for_status = MagicMock()
    http.get = AsyncMock(return_value=response)

    config = _make_feed_config(feed_type="scraper", feed_id="daugavpils")
    scraper = DaugavpilsScraper(feed_config=config, http_client=http)
    vehicles = await scraper.fetch_vehicle_positions()

    assert vehicles == []


# --- GpsTextClient tests ---


@pytest.mark.asyncio
async def test_gps_text_success() -> None:
    """Valid GPS text lines produce VehiclePositionData list."""
    now = _now_ts()
    http = _make_http_client()
    response = MagicMock()
    response.text = f"bus-10;56.50;21.01;90;10.5;3;{now}\nbus-11;56.51;21.02;180;8.0;5;{now}\n"
    response.raise_for_status = MagicMock()
    http.get = AsyncMock(return_value=response)

    config = _make_feed_config(feed_type="gps_text", feed_id="liepaja")
    client = GpsTextClient(feed_config=config, http_client=http)
    vehicles = await client.fetch_vehicle_positions()

    assert len(vehicles) == 2
    assert vehicles[0].vehicle_id == "bus-10"
    assert vehicles[0].latitude == 56.50
    assert vehicles[0].longitude == 21.01
    assert vehicles[0].speed == 10.5
    assert vehicles[0].route_id == "3"
    assert vehicles[1].vehicle_id == "bus-11"


@pytest.mark.asyncio
async def test_gps_text_malformed_line() -> None:
    """Line with insufficient fields is skipped, others parsed."""
    now = _now_ts()
    http = _make_http_client()
    response = MagicMock()
    response.text = (
        "bad;data\n"  # only 2 fields
        f"bus-10;56.50;21.01;90;10.5;3;{now}\n"
    )
    response.raise_for_status = MagicMock()
    http.get = AsyncMock(return_value=response)

    config = _make_feed_config(feed_type="gps_text", feed_id="liepaja")
    client = GpsTextClient(feed_config=config, http_client=http)
    vehicles = await client.fetch_vehicle_positions()

    assert len(vehicles) == 1
    assert vehicles[0].vehicle_id == "bus-10"


@pytest.mark.asyncio
async def test_gps_text_invalid_coordinates() -> None:
    """Line with out-of-range coordinates is skipped."""
    now = _now_ts()
    http = _make_http_client()
    response = MagicMock()
    response.text = f"bus-10;40.00;21.01;90;10.5;3;{now}\n"  # lat out of range
    response.raise_for_status = MagicMock()
    http.get = AsyncMock(return_value=response)

    config = _make_feed_config(feed_type="gps_text", feed_id="liepaja")
    client = GpsTextClient(feed_config=config, http_client=http)
    vehicles = await client.fetch_vehicle_positions()

    assert len(vehicles) == 0


@pytest.mark.asyncio
async def test_gps_text_http_error() -> None:
    """HTTP connection error raises TransitDataError."""
    http = _make_http_client()
    http.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

    config = _make_feed_config(feed_type="gps_text", feed_id="liepaja")
    client = GpsTextClient(feed_config=config, http_client=http)

    with pytest.raises(TransitDataError):
        await client.fetch_vehicle_positions()


@pytest.mark.asyncio
async def test_gps_text_empty_response() -> None:
    """Empty body returns empty list."""
    http = _make_http_client()
    response = MagicMock()
    response.text = ""
    response.raise_for_status = MagicMock()
    http.get = AsyncMock(return_value=response)

    config = _make_feed_config(feed_type="gps_text", feed_id="liepaja")
    client = GpsTextClient(feed_config=config, http_client=http)
    vehicles = await client.fetch_vehicle_positions()

    assert vehicles == []


# --- Factory tests ---


def test_create_feed_client_gtfs_rt() -> None:
    """feed_type='gtfs_rt' returns GTFSRealtimeClient."""
    config = _make_feed_config(feed_type="gtfs_rt")
    http = _make_http_client()
    settings = MagicMock()
    client = create_feed_client(config, http, settings)
    assert isinstance(client, GTFSRealtimeClient)


def test_create_feed_client_scraper() -> None:
    """feed_type='scraper' returns DaugavpilsScraper."""
    config = _make_feed_config(feed_type="scraper")
    http = _make_http_client()
    settings = MagicMock()
    client = create_feed_client(config, http, settings)
    assert isinstance(client, DaugavpilsScraper)


def test_create_feed_client_gps_text() -> None:
    """feed_type='gps_text' returns GpsTextClient."""
    config = _make_feed_config(feed_type="gps_text")
    http = _make_http_client()
    settings = MagicMock()
    client = create_feed_client(config, http, settings)
    assert isinstance(client, GpsTextClient)


# --- Trip updates return empty ---


@pytest.mark.asyncio
async def test_scraper_trip_updates_empty() -> None:
    """DaugavpilsScraper.fetch_trip_updates() always returns empty list."""
    config = _make_feed_config(feed_type="scraper")
    scraper = DaugavpilsScraper(feed_config=config, http_client=_make_http_client())
    assert await scraper.fetch_trip_updates() == []


@pytest.mark.asyncio
async def test_gps_text_trip_updates_empty() -> None:
    """GpsTextClient.fetch_trip_updates() always returns empty list."""
    config = _make_feed_config(feed_type="gps_text")
    client = GpsTextClient(feed_config=config, http_client=_make_http_client())
    assert await client.fetch_trip_updates() == []
