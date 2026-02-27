"""Tests for search_stops transit tool."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.agents.tools.transit.search_stops import (
    _validate_search_params,
    search_stops,
)
from app.core.agents.tools.transit.static_cache import StopInfo
from app.shared.geo import haversine_distance

# --- Test helpers ---


def _make_ctx() -> MagicMock:
    """Create a mock RunContext with TransitDeps."""
    ctx = MagicMock()
    ctx.deps.transit_http_client = AsyncMock()
    ctx.deps.settings = MagicMock()
    return ctx


def _make_mock_static() -> MagicMock:
    """Create a mock GTFSStaticCache with sample Riga stop data."""
    mock = MagicMock()
    mock.stops = {
        "s1": StopInfo(
            stop_id="s1",
            stop_name="Brīvības iela",
            stop_lat=56.9496,
            stop_lon=24.1052,
        ),
        "s2": StopInfo(
            stop_id="s2",
            stop_name="Centrālā stacija",
            stop_lat=56.9440,
            stop_lon=24.1134,
        ),
        "s3": StopInfo(
            stop_id="s3",
            stop_name="Brīvības bulvāris",
            stop_lat=56.9550,
            stop_lon=24.1100,
        ),
        "s4": StopInfo(
            stop_id="s4",
            stop_name="Jugla",
            stop_lat=56.9800,
            stop_lon=24.1900,
        ),
        "s5": StopInfo(
            stop_id="s5",
            stop_name="Ziepniekkalns",
            stop_lat=56.9200,
            stop_lon=24.0500,
        ),
    }
    mock.stop_routes = {
        "s1": ["22", "3"],
        "s2": ["1", "22"],
        "s3": ["22"],
        "s4": ["15"],
        "s5": ["7"],
    }
    return mock


# --- Unit tests for helper functions ---


def test_haversine_distance_same_point() -> None:
    dist = haversine_distance(56.9496, 24.1052, 56.9496, 24.1052)
    assert dist == 0.0


def test_haversine_distance_known_pair() -> None:
    # Riga center (~56.9496, 24.1052) to Jugla (~56.98, 24.19)
    # Expected: roughly 6-7 km
    dist = haversine_distance(56.9496, 24.1052, 56.9800, 24.1900)
    assert 5000 < dist < 8000


def test_haversine_distance_short() -> None:
    # Two points ~600m apart
    dist = haversine_distance(56.9496, 24.1052, 56.9550, 24.1100)
    assert 500 < dist < 1000


def test_validate_search_params_invalid_action() -> None:
    result = _validate_search_params("invalid", None, None, None)
    assert result is not None
    assert "Invalid action" in result


def test_validate_search_params_search_missing_query() -> None:
    result = _validate_search_params("search", None, None, None)
    assert result is not None
    assert "query" in result


def test_validate_search_params_search_empty_query() -> None:
    result = _validate_search_params("search", "", None, None)
    assert result is not None
    assert "query" in result


def test_validate_search_params_search_valid() -> None:
    result = _validate_search_params("search", "Brīvības", None, None)
    assert result is None


def test_validate_search_params_nearby_missing_coords() -> None:
    result = _validate_search_params("nearby", None, 56.95, None)
    assert result is not None
    assert "latitude" in result or "longitude" in result


def test_validate_search_params_nearby_valid() -> None:
    result = _validate_search_params("nearby", None, 56.95, 24.11)
    assert result is None


# --- Tool function tests ---


@pytest.mark.asyncio
async def test_search_stops_invalid_action() -> None:
    ctx = _make_ctx()
    result = await search_stops(ctx, action="invalid")
    assert "Invalid action" in result


@pytest.mark.asyncio
async def test_search_stops_search_by_name() -> None:
    ctx = _make_ctx()
    mock_static = _make_mock_static()

    with patch(
        "app.core.agents.tools.transit.search_stops.get_static_cache",
        return_value=mock_static,
    ):
        result = await search_stops(ctx, action="search", query="Brīvības")

    import json

    data = json.loads(result)
    assert data["action"] == "search"
    assert data["query"] == "Brīvības"
    assert data["result_count"] == 2
    assert data["total_matches"] == 2
    names = [s["stop_name"] for s in data["stops"]]
    assert "Brīvības bulvāris" in names
    assert "Brīvības iela" in names


@pytest.mark.asyncio
async def test_search_stops_search_no_matches() -> None:
    ctx = _make_ctx()
    mock_static = _make_mock_static()

    with patch(
        "app.core.agents.tools.transit.search_stops.get_static_cache",
        return_value=mock_static,
    ):
        result = await search_stops(ctx, action="search", query="Nonexistent")

    import json

    data = json.loads(result)
    assert data["result_count"] == 0
    assert "No stops found" in data["summary"]


@pytest.mark.asyncio
async def test_search_stops_search_case_insensitive() -> None:
    ctx = _make_ctx()
    mock_static = _make_mock_static()

    with patch(
        "app.core.agents.tools.transit.search_stops.get_static_cache",
        return_value=mock_static,
    ):
        result = await search_stops(ctx, action="search", query="brīvības")

    import json

    data = json.loads(result)
    assert data["result_count"] == 2


@pytest.mark.asyncio
async def test_search_stops_nearby_finds_close_stops() -> None:
    ctx = _make_ctx()
    mock_static = _make_mock_static()

    with patch(
        "app.core.agents.tools.transit.search_stops.get_static_cache",
        return_value=mock_static,
    ):
        # Search near s1 (56.9496, 24.1052) with 1000m radius
        result = await search_stops(
            ctx,
            action="nearby",
            latitude=56.9496,
            longitude=24.1052,
            radius_meters=1000,
        )

    import json

    data = json.loads(result)
    assert data["action"] == "nearby"
    assert data["result_count"] >= 1
    # s1 should be at distance 0 or very close
    assert data["stops"][0]["stop_id"] == "s1"
    assert data["stops"][0]["distance_meters"] == 0


@pytest.mark.asyncio
async def test_search_stops_nearby_no_results() -> None:
    ctx = _make_ctx()
    mock_static = _make_mock_static()

    with patch(
        "app.core.agents.tools.transit.search_stops.get_static_cache",
        return_value=mock_static,
    ):
        # Search far from all stops with tiny radius
        result = await search_stops(
            ctx,
            action="nearby",
            latitude=57.5,
            longitude=25.0,
            radius_meters=100,
        )

    import json

    data = json.loads(result)
    assert data["result_count"] == 0
    assert "No stops found" in data["summary"]


@pytest.mark.asyncio
async def test_search_stops_nearby_sorted_by_distance() -> None:
    ctx = _make_ctx()
    mock_static = _make_mock_static()

    with patch(
        "app.core.agents.tools.transit.search_stops.get_static_cache",
        return_value=mock_static,
    ):
        # Large radius to get multiple results
        result = await search_stops(
            ctx,
            action="nearby",
            latitude=56.9496,
            longitude=24.1052,
            radius_meters=2000,
        )

    import json

    data = json.loads(result)
    if data["result_count"] >= 2:
        distances = [s["distance_meters"] for s in data["stops"]]
        assert distances == sorted(distances)


@pytest.mark.asyncio
async def test_search_stops_limit_respected() -> None:
    ctx = _make_ctx()
    mock_static = _make_mock_static()

    with patch(
        "app.core.agents.tools.transit.search_stops.get_static_cache",
        return_value=mock_static,
    ):
        result = await search_stops(ctx, action="search", query="a", limit=1)

    import json

    data = json.loads(result)
    assert data["result_count"] <= 1


@pytest.mark.asyncio
async def test_search_stops_routes_populated() -> None:
    ctx = _make_ctx()
    mock_static = _make_mock_static()

    with patch(
        "app.core.agents.tools.transit.search_stops.get_static_cache",
        return_value=mock_static,
    ):
        result = await search_stops(ctx, action="search", query="Brīvības iela")

    import json

    data = json.loads(result)
    assert data["result_count"] >= 1
    stop = data["stops"][0]
    assert stop["routes"] == ["22", "3"]


@pytest.mark.asyncio
async def test_search_stops_feed_error() -> None:
    ctx = _make_ctx()

    with (
        patch(
            "app.core.agents.tools.transit.search_stops.get_static_cache",
            side_effect=RuntimeError("Connection refused"),
        ),
        patch("app.core.agents.tools.transit.search_stops.logger"),
    ):
        result = await search_stops(ctx, action="search", query="test")

    assert "Transit data error" in result
