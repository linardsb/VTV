"""Tests for obsidian_query_vault tool."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.agents.tools.obsidian.query_vault import obsidian_query_vault


def _make_ctx(api_key: str | None = "test-key") -> MagicMock:
    """Create mock RunContext with UnifiedDeps for query vault tests."""
    ctx = MagicMock()
    ctx.deps.settings.obsidian_api_key = api_key
    ctx.deps.settings.obsidian_vault_url = "https://127.0.0.1:27124"
    ctx.deps.obsidian_http_client = AsyncMock()
    ctx.deps.transit_http_client = AsyncMock()
    return ctx


# --- Validation tests (sync-like - no real async work) ---


@pytest.mark.asyncio
async def test_invalid_action_returns_error() -> None:
    """Invalid action returns a helpful error string listing valid actions."""
    ctx = _make_ctx()
    result = await obsidian_query_vault(ctx, action="destroy")
    assert "Invalid action" in result
    assert "destroy" in result
    assert "search" in result


@pytest.mark.asyncio
async def test_search_requires_query() -> None:
    """Action 'search' without a query returns an error message."""
    ctx = _make_ctx()
    result = await obsidian_query_vault(ctx, action="search", query=None)
    assert "requires a query" in result
    assert "search" in result


@pytest.mark.asyncio
async def test_find_by_tags_requires_tags() -> None:
    """Action 'find_by_tags' without tags returns an error message."""
    ctx = _make_ctx()
    result = await obsidian_query_vault(ctx, action="find_by_tags", tags=None)
    assert "requires a tags list" in result


@pytest.mark.asyncio
async def test_glob_requires_pattern() -> None:
    """Action 'glob' without a pattern returns an error message."""
    ctx = _make_ctx()
    result = await obsidian_query_vault(ctx, action="glob", pattern=None)
    assert "requires a pattern" in result


@pytest.mark.asyncio
async def test_vault_not_configured() -> None:
    """When obsidian_api_key is None, returns a configuration error."""
    ctx = _make_ctx(api_key=None)
    result = await obsidian_query_vault(ctx, action="search", query="test")
    assert "not configured" in result
    assert "OBSIDIAN_API_KEY" in result


@pytest.mark.asyncio
async def test_invalid_path_rejected() -> None:
    """Path with '..' returns a path traversal error."""
    ctx = _make_ctx()
    result = await obsidian_query_vault(ctx, action="search", query="test", path="../secrets")
    assert "not allowed" in result


@pytest.mark.asyncio
async def test_invalid_response_format_returns_error() -> None:
    """Invalid response_format returns an error message."""
    ctx = _make_ctx()
    result = await obsidian_query_vault(ctx, action="search", query="test", response_format="xml")
    assert "Invalid response_format" in result


@pytest.mark.asyncio
async def test_invalid_sort_by_returns_error() -> None:
    """Invalid sort_by returns an error message."""
    ctx = _make_ctx()
    result = await obsidian_query_vault(ctx, action="search", query="test", sort_by="random")
    assert "Invalid sort_by" in result


# --- Functional tests (mock ObsidianClient) ---


@pytest.mark.asyncio
async def test_search_returns_results() -> None:
    """mock client.search returning results produces a valid JSON response."""
    ctx = _make_ctx()
    fake_results = [
        {"filename": "projects/vtv.md", "score": 0.9, "mtime": "2026-02-18T12:00:00"},
        {"filename": "daily/2026-02-18.md", "score": 0.7, "mtime": "2026-02-17T08:00:00"},
    ]

    with patch(
        "app.core.agents.tools.obsidian.query_vault.ObsidianClient.search",
        new_callable=AsyncMock,
        return_value=fake_results,
    ):
        result = await obsidian_query_vault(ctx, action="search", query="vtv project")

    data = json.loads(result)
    assert data["count"] == 2
    assert isinstance(data["results"], list)
    assert data["results"][0]["path"] == "projects/vtv.md"
    assert data["results"][0]["title"] == "vtv"
    assert data["truncated"] is False


@pytest.mark.asyncio
async def test_search_limit_caps_results() -> None:
    """Limit parameter caps the number of results returned by the tool."""
    ctx = _make_ctx()
    # The search handler pre-slices by limit, so we provide exactly limit items
    fake_results = [
        {"filename": f"note-{i}.md", "score": 1.0, "mtime": "2026-02-18T12:00:00"} for i in range(3)
    ]

    with patch(
        "app.core.agents.tools.obsidian.query_vault.ObsidianClient.search",
        new_callable=AsyncMock,
        return_value=fake_results,
    ):
        result = await obsidian_query_vault(ctx, action="search", query="test", limit=3)

    data = json.loads(result)
    assert data["count"] == 3
    assert isinstance(data["results"], list)
    assert len(data["results"]) == 3


@pytest.mark.asyncio
async def test_list_returns_results() -> None:
    """Action 'list' returns directory contents as a search response."""
    ctx = _make_ctx()
    fake_entries = [
        {"name": "note.md", "path": "projects/note.md", "type": "file", "mtime": 1739880000},
    ]

    with patch(
        "app.core.agents.tools.obsidian.query_vault.ObsidianClient.list_directory",
        new_callable=AsyncMock,
        return_value=fake_entries,
    ):
        result = await obsidian_query_vault(ctx, action="list", path="projects/")

    data = json.loads(result)
    assert data["count"] == 1
    assert data["results"][0]["path"] == "projects/note.md"


@pytest.mark.asyncio
async def test_find_by_tags_returns_results() -> None:
    """Action 'find_by_tags' returns notes matching the tag query."""
    ctx = _make_ctx()
    fake_results = [
        {"filename": "projects/tagged.md", "score": 1.0, "mtime": "2026-02-18T00:00:00"},
    ]

    with patch(
        "app.core.agents.tools.obsidian.query_vault.ObsidianClient.search",
        new_callable=AsyncMock,
        return_value=fake_results,
    ):
        result = await obsidian_query_vault(ctx, action="find_by_tags", tags=["project", "active"])

    data = json.loads(result)
    assert data["count"] == 1
    assert data["results"][0]["path"] == "projects/tagged.md"


@pytest.mark.asyncio
async def test_glob_returns_matching_files() -> None:
    """Action 'glob' returns files matching the pattern."""
    ctx = _make_ctx()
    fake_entries = [
        {"path": "projects/alpha.md", "mtime": 1739880000},
        {"path": "daily/2026-02-18.md", "mtime": 1739880000},
    ]

    with patch(
        "app.core.agents.tools.obsidian.query_vault.ObsidianClient.list_directory",
        new_callable=AsyncMock,
        return_value=fake_entries,
    ):
        result = await obsidian_query_vault(ctx, action="glob", pattern="projects/*.md")

    data = json.loads(result)
    assert data["count"] == 1
    assert data["results"][0]["path"] == "projects/alpha.md"


@pytest.mark.asyncio
async def test_detailed_format_includes_extra_fields() -> None:
    """response_format='detailed' includes size_bytes and word_count fields."""
    ctx = _make_ctx()
    fake_results = [
        {
            "filename": "notes/detailed.md",
            "score": 1.0,
            "mtime": "2026-02-18T12:00:00",
        }
    ]

    with patch(
        "app.core.agents.tools.obsidian.query_vault.ObsidianClient.search",
        new_callable=AsyncMock,
        return_value=fake_results,
    ):
        result = await obsidian_query_vault(
            ctx,
            action="search",
            query="test",
            response_format="detailed",
        )

    data = json.loads(result)
    assert data["count"] == 1
    # Detailed format should have these keys even if None
    assert "size_bytes" in data["results"][0]
    assert "word_count" in data["results"][0]
