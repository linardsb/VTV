"""Unit tests for search_intercity_stops and search_intercity_routes agent tools."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.agents.exceptions import TransitDataError
from app.core.agents.tools.transit.search_intercity import (
    search_intercity_routes,
    search_intercity_stops,
)
from app.transit.ckan_client import _escape_ckan_value


def _make_ctx() -> MagicMock:
    """Create a mock RunContext with UnifiedDeps for intercity tools."""
    ctx = MagicMock()
    ctx.deps.ckan_http_client = AsyncMock()
    ctx.deps.settings = MagicMock()
    ctx.deps.settings.ckan_datastore_sql_url = "https://data.gov.lv/test"
    ctx.deps.settings.ckan_cache_ttl_s = 300
    ctx.deps.settings.ckan_rate_limit_delay_s = 0.0
    ctx.deps.db_session_factory = MagicMock()
    return ctx


@pytest.mark.asyncio
async def test_search_stops_by_name() -> None:
    """Name query returns matching stops as JSON."""
    ctx = _make_ctx()
    records = [
        {"stop_id": "100", "stop_name": "Liepaja AS", "stop_lat": 56.51, "stop_lon": 21.01},
    ]

    with patch("app.core.agents.tools.transit.search_intercity.CKANClient") as mock_cls:
        instance = AsyncMock()
        instance.query_sql.return_value = records
        mock_cls.return_value = instance

        result = await search_intercity_stops(ctx, query="Liepaja")

    data = json.loads(result)
    assert data["result_count"] == 1
    assert data["stops"][0]["stop_name"] == "Liepaja AS"


@pytest.mark.asyncio
async def test_search_stops_by_proximity() -> None:
    """Proximity search returns stops sorted by distance."""
    ctx = _make_ctx()
    records = [
        {"stop_id": "1", "stop_name": "Far", "stop_lat": 57.0, "stop_lon": 24.0},
        {"stop_id": "2", "stop_name": "Near", "stop_lat": 56.9497, "stop_lon": 24.1053},
    ]

    with patch("app.core.agents.tools.transit.search_intercity.CKANClient") as mock_cls:
        instance = AsyncMock()
        instance.query_sql.return_value = records
        mock_cls.return_value = instance

        result = await search_intercity_stops(ctx, latitude=56.9496, longitude=24.1052)

    data = json.loads(result)
    assert data["result_count"] == 2
    # Near stop should be first (closer)
    assert data["stops"][0]["stop_name"] == "Near"
    assert "distance_m" in data["stops"][0]


@pytest.mark.asyncio
async def test_search_stops_no_params() -> None:
    """No query or lat/lon returns actionable error message."""
    ctx = _make_ctx()
    result = await search_intercity_stops(ctx)
    assert "provide either" in result.lower()


@pytest.mark.asyncio
async def test_search_stops_partial_coords() -> None:
    """Only latitude without longitude returns error."""
    ctx = _make_ctx()
    result = await search_intercity_stops(ctx, latitude=56.5)
    assert "both latitude and longitude" in result.lower()


@pytest.mark.asyncio
async def test_search_stops_limit_clamped() -> None:
    """Limit > 50 is clamped to 50."""
    ctx = _make_ctx()
    records = [{"stop_id": "1", "stop_name": "Test", "stop_lat": 56.5, "stop_lon": 21.0}]

    with patch("app.core.agents.tools.transit.search_intercity.CKANClient") as mock_cls:
        instance = AsyncMock()
        instance.query_sql.return_value = records
        mock_cls.return_value = instance

        result = await search_intercity_stops(ctx, query="Test", limit=100)

    # Should succeed (clamped internally)
    data = json.loads(result)
    assert data["result_count"] == 1
    # Verify the SQL used LIMIT 50, not 100
    sql_arg = instance.query_sql.call_args[0][0]
    assert "LIMIT 50" in sql_arg


@pytest.mark.asyncio
async def test_search_stops_ckan_error() -> None:
    """CKANClient raising TransitDataError returns graceful error."""
    ctx = _make_ctx()

    with patch("app.core.agents.tools.transit.search_intercity.CKANClient") as mock_cls:
        instance = AsyncMock()
        instance.query_sql.side_effect = TransitDataError("Connection failed")
        mock_cls.return_value = instance

        with pytest.raises(TransitDataError):
            await search_intercity_stops(ctx, query="Test")


@pytest.mark.asyncio
async def test_search_stops_empty_results() -> None:
    """No matches returns empty array JSON."""
    ctx = _make_ctx()

    with patch("app.core.agents.tools.transit.search_intercity.CKANClient") as mock_cls:
        instance = AsyncMock()
        instance.query_sql.return_value = []
        mock_cls.return_value = instance

        result = await search_intercity_stops(ctx, query="Nonexistent")

    data = json.loads(result)
    assert data["result_count"] == 0
    assert data["stops"] == []


@pytest.mark.asyncio
async def test_search_stops_no_ckan_client() -> None:
    """Missing ckan_http_client raises TransitDataError."""
    ctx = _make_ctx()
    ctx.deps.ckan_http_client = None

    with pytest.raises(TransitDataError, match="not configured"):
        await search_intercity_stops(ctx, query="Test")


@pytest.mark.asyncio
async def test_search_routes_by_name() -> None:
    """Route name query returns matching routes."""
    ctx = _make_ctx()
    records = [
        {
            "route_id": "R1",
            "route_short_name": "100",
            "route_long_name": "Riga - Liepaja",
        },
    ]

    with patch("app.core.agents.tools.transit.search_intercity.CKANClient") as mock_cls:
        instance = AsyncMock()
        instance.query_sql.return_value = records
        mock_cls.return_value = instance

        result = await search_intercity_routes(ctx, query="Liepaja")

    data = json.loads(result)
    assert data["result_count"] == 1
    assert data["routes"][0]["route_long_name"] == "Riga - Liepaja"


@pytest.mark.asyncio
async def test_search_routes_by_stop() -> None:
    """Stop name filter returns routes via JOIN query."""
    ctx = _make_ctx()
    records = [
        {
            "route_id": "R2",
            "route_short_name": "200",
            "route_long_name": "Riga - Ventspils",
        },
    ]

    with patch("app.core.agents.tools.transit.search_intercity.CKANClient") as mock_cls:
        instance = AsyncMock()
        instance.query_sql.return_value = records
        mock_cls.return_value = instance

        result = await search_intercity_routes(ctx, stop_name="Ventspils AS")

    data = json.loads(result)
    assert data["result_count"] == 1
    # Verify the SQL includes JOIN
    sql_arg = instance.query_sql.call_args[0][0]
    assert "JOIN" in sql_arg


@pytest.mark.asyncio
async def test_search_routes_no_params() -> None:
    """No query or stop_name returns actionable error."""
    ctx = _make_ctx()
    result = await search_intercity_routes(ctx)
    assert "provide" in result.lower()


@pytest.mark.asyncio
async def test_search_routes_ckan_error() -> None:
    """CKANClient error propagates as TransitDataError."""
    ctx = _make_ctx()

    with patch("app.core.agents.tools.transit.search_intercity.CKANClient") as mock_cls:
        instance = AsyncMock()
        instance.query_sql.side_effect = TransitDataError("Timeout")
        mock_cls.return_value = instance

        with pytest.raises(TransitDataError):
            await search_intercity_routes(ctx, query="Test")


@pytest.mark.asyncio
async def test_search_routes_empty_results() -> None:
    """No matching routes returns empty array."""
    ctx = _make_ctx()

    with patch("app.core.agents.tools.transit.search_intercity.CKANClient") as mock_cls:
        instance = AsyncMock()
        instance.query_sql.return_value = []
        mock_cls.return_value = instance

        result = await search_intercity_routes(ctx, query="Nonexistent")

    data = json.loads(result)
    assert data["result_count"] == 0
    assert data["routes"] == []


def test_escape_ckan_value_sql_injection() -> None:
    """SQL injection attempts are escaped."""
    injected = "'; DROP TABLE stops; --"
    escaped = _escape_ckan_value(injected)
    assert "DROP TABLE" in escaped  # Text preserved
    assert "''" in escaped  # Quotes escaped


def test_escape_ckan_value_wildcards() -> None:
    """LIKE wildcard injection is prevented."""
    assert "\\%" in _escape_ckan_value("100%")
    assert "\\_" in _escape_ckan_value("stop_1")
