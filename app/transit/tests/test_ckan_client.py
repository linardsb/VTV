"""Unit tests for CKANClient (CKAN Datastore SQL API client)."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.core.agents.exceptions import TransitDataError
from app.transit.ckan_client import CKANClient, _escape_ckan_value


def _make_settings() -> MagicMock:
    """Create a mock Settings object with CKAN config."""
    s = MagicMock()
    s.ckan_datastore_sql_url = "https://data.gov.lv/test/datastore_search_sql"
    s.ckan_cache_ttl_s = 300
    s.ckan_rate_limit_delay_s = 0.0  # No delay in tests
    return s


def _make_response(records: list[dict[str, Any]], success: bool = True) -> MagicMock:
    """Create a mock httpx Response with CKAN format."""
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    body: dict[str, Any] = {"success": success, "result": {"records": records}}
    resp.json.return_value = body
    return resp


@pytest.mark.asyncio
async def test_query_sql_success() -> None:
    """Happy path: POST to CKAN API, parse records."""
    records = [{"stop_id": "1", "stop_name": "Liepaja"}]
    http = AsyncMock(spec=httpx.AsyncClient)
    http.post.return_value = _make_response(records)
    settings = _make_settings()
    client = CKANClient(http, settings)

    with patch("app.transit.ckan_client.get_redis") as mock_redis:
        redis = AsyncMock()
        redis.get.return_value = None
        mock_redis.return_value = redis

        result = await client.query_sql("SELECT * FROM stops")

    assert result == records
    http.post.assert_called_once()


@pytest.mark.asyncio
async def test_query_sql_cached() -> None:
    """Second call returns from Redis, no HTTP request made."""
    cached_data = [{"stop_id": "2", "stop_name": "Ventspils"}]
    http = AsyncMock(spec=httpx.AsyncClient)
    settings = _make_settings()
    client = CKANClient(http, settings)

    with patch("app.transit.ckan_client.get_redis") as mock_redis:
        redis = AsyncMock()
        redis.get.return_value = json.dumps(cached_data)
        mock_redis.return_value = redis

        result = await client.query_sql("SELECT * FROM stops")

    assert result == cached_data
    http.post.assert_not_called()


@pytest.mark.asyncio
async def test_query_sql_cache_miss() -> None:
    """Cache miss triggers HTTP request and stores result."""
    records = [{"stop_id": "3"}]
    http = AsyncMock(spec=httpx.AsyncClient)
    http.post.return_value = _make_response(records)
    settings = _make_settings()
    client = CKANClient(http, settings)

    with patch("app.transit.ckan_client.get_redis") as mock_redis:
        redis = AsyncMock()
        redis.get.return_value = None
        mock_redis.return_value = redis

        result = await client.query_sql("SELECT * FROM stops WHERE id=3")

    assert result == records
    redis.set.assert_called_once()
    call_args = redis.set.call_args
    assert call_args[1]["ex"] == 300


@pytest.mark.asyncio
async def test_query_sql_pagination() -> None:
    """32000 records on first page triggers a second page fetch."""
    page1 = [{"id": str(i)} for i in range(32000)]
    page2 = [{"id": "extra"}]

    http = AsyncMock(spec=httpx.AsyncClient)
    http.post.side_effect = [
        _make_response(page1),
        _make_response(page2),
    ]
    settings = _make_settings()
    client = CKANClient(http, settings)

    with patch("app.transit.ckan_client.get_redis") as mock_redis:
        redis = AsyncMock()
        redis.get.return_value = None
        mock_redis.return_value = redis

        result = await client.query_sql("SELECT * FROM big_table")

    assert len(result) == 32001
    assert http.post.call_count == 2


@pytest.mark.asyncio
async def test_query_sql_pagination_exact_limit() -> None:
    """Exactly 32000 records triggers page 2 which returns empty."""
    page1 = [{"id": str(i)} for i in range(32000)]

    http = AsyncMock(spec=httpx.AsyncClient)
    http.post.side_effect = [
        _make_response(page1),
        _make_response([]),
    ]
    settings = _make_settings()
    client = CKANClient(http, settings)

    with patch("app.transit.ckan_client.get_redis") as mock_redis:
        redis = AsyncMock()
        redis.get.return_value = None
        mock_redis.return_value = redis

        result = await client.query_sql("SELECT * FROM table")

    assert len(result) == 32000
    assert http.post.call_count == 2


@pytest.mark.asyncio
async def test_query_sql_rate_limiting() -> None:
    """Rate limiter tracks last request time."""
    records = [{"id": "1"}]
    http = AsyncMock(spec=httpx.AsyncClient)
    http.post.return_value = _make_response(records)
    settings = _make_settings()
    settings.ckan_rate_limit_delay_s = 0.0  # No actual delay in test
    client = CKANClient(http, settings)

    with patch("app.transit.ckan_client.get_redis") as mock_redis:
        redis = AsyncMock()
        redis.get.return_value = None
        mock_redis.return_value = redis

        await client.query_sql("SELECT 1")
        assert client._last_request_time > 0.0


@pytest.mark.asyncio
async def test_query_sql_http_error() -> None:
    """httpx.HTTPError raises TransitDataError."""
    http = AsyncMock(spec=httpx.AsyncClient)
    http.post.side_effect = httpx.ConnectError("Connection refused")
    settings = _make_settings()
    client = CKANClient(http, settings)

    with patch("app.transit.ckan_client.get_redis") as mock_redis:
        redis = AsyncMock()
        redis.get.return_value = None
        mock_redis.return_value = redis

        with pytest.raises(TransitDataError, match=r"data\.gov\.lv"):
            await client.query_sql("SELECT 1")


@pytest.mark.asyncio
async def test_query_sql_timeout() -> None:
    """httpx.TimeoutException raises TransitDataError."""
    http = AsyncMock(spec=httpx.AsyncClient)
    http.post.side_effect = httpx.ReadTimeout("Timed out")
    settings = _make_settings()
    client = CKANClient(http, settings)

    with patch("app.transit.ckan_client.get_redis") as mock_redis:
        redis = AsyncMock()
        redis.get.return_value = None
        mock_redis.return_value = redis

        with pytest.raises(TransitDataError, match="timed out"):
            await client.query_sql("SELECT 1")


@pytest.mark.asyncio
async def test_query_sql_ckan_api_error() -> None:
    """CKAN API returning success=false raises TransitDataError."""
    http = AsyncMock(spec=httpx.AsyncClient)
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {
        "success": False,
        "error": {"message": "SQL syntax error"},
    }
    http.post.return_value = resp
    settings = _make_settings()
    client = CKANClient(http, settings)

    with patch("app.transit.ckan_client.get_redis") as mock_redis:
        redis = AsyncMock()
        redis.get.return_value = None
        mock_redis.return_value = redis

        with pytest.raises(TransitDataError, match="CKAN API error"):
            await client.query_sql("INVALID SQL")


def test_cache_key_deterministic() -> None:
    """Same SQL produces the same cache key."""
    settings = _make_settings()
    http = AsyncMock(spec=httpx.AsyncClient)
    client = CKANClient(http, settings)

    key1 = client._cache_key("SELECT * FROM stops")
    key2 = client._cache_key("SELECT * FROM stops")
    assert key1 == key2
    assert key1.startswith("ckan:")


def test_cache_key_different_sql() -> None:
    """Different SQL produces different cache keys."""
    settings = _make_settings()
    http = AsyncMock(spec=httpx.AsyncClient)
    client = CKANClient(http, settings)

    key1 = client._cache_key("SELECT * FROM stops")
    key2 = client._cache_key("SELECT * FROM routes")
    assert key1 != key2


def test_escape_value_single_quotes() -> None:
    """Single quotes are doubled."""
    assert _escape_ckan_value("O'Brien") == "O''Brien"


def test_escape_value_control_chars() -> None:
    """Control characters are stripped."""
    assert _escape_ckan_value("test\x00\x01\x0e") == "test"


def test_escape_value_combined() -> None:
    """Both quoting and stripping apply."""
    assert _escape_ckan_value("it's\x00 a test") == "it''s a test"


def test_escape_value_wildcards() -> None:
    """LIKE wildcard characters % and _ are escaped."""
    assert _escape_ckan_value("100%") == "100\\%"
    assert _escape_ckan_value("stop_1") == "stop\\_1"
    assert _escape_ckan_value("%_test_%") == "\\%\\_test\\_\\%"


def test_escape_value_backslash() -> None:
    """Backslashes are escaped."""
    assert _escape_ckan_value("a\\b") == "a\\\\b"
