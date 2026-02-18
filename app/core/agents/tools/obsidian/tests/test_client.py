"""Tests for ObsidianClient and _validate_path."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.core.agents.tools.obsidian.client import ObsidianClient, _validate_path


def _make_http_client() -> AsyncMock:
    """Create a mock async HTTP client."""
    return AsyncMock()


def _make_response(status_code: int = 200, json_data: object = None, text: str = "") -> MagicMock:
    """Create a mock httpx response."""
    response = MagicMock()
    response.status_code = status_code
    response.text = text
    if json_data is not None:
        response.json.return_value = json_data
    response.raise_for_status = MagicMock()
    return response


# --- _validate_path tests ---


def test_validate_path_rejects_traversal() -> None:
    """_validate_path raises ValueError for paths containing '..'."""
    with pytest.raises(ValueError, match="Path traversal not allowed"):
        _validate_path("../secrets/config.md")


def test_validate_path_rejects_embedded_traversal() -> None:
    """_validate_path raises ValueError for embedded '..' in path."""
    with pytest.raises(ValueError, match="Path traversal not allowed"):
        _validate_path("notes/../../../etc/passwd")


def test_validate_path_accepts_valid() -> None:
    """_validate_path accepts a normal relative path."""
    result = _validate_path("projects/vtv/notes.md")
    assert result == "projects/vtv/notes.md"


def test_validate_path_strips_leading_slash() -> None:
    """_validate_path strips a leading slash from the path."""
    result = _validate_path("/projects/vtv/notes.md")
    assert result == "projects/vtv/notes.md"


def test_validate_path_accepts_simple_filename() -> None:
    """_validate_path accepts a simple filename without directory."""
    result = _validate_path("note.md")
    assert result == "note.md"


# --- ObsidianClient tests ---


@pytest.mark.asyncio
async def test_search_calls_api() -> None:
    """client.search() calls POST /search/simple/ with query body."""
    http_client = _make_http_client()
    response = _make_response(json_data=[{"filename": "notes/test.md", "score": 1.0}])
    http_client.post.return_value = response

    client = ObsidianClient(http_client, "https://127.0.0.1:27124")
    results = await client.search("meeting notes")

    http_client.post.assert_called_once()
    call_args = http_client.post.call_args
    assert "/search/simple/" in call_args[0][0]
    assert call_args[1]["content"] == "meeting notes"
    assert len(results) == 1
    assert results[0]["filename"] == "notes/test.md"


@pytest.mark.asyncio
async def test_get_note_calls_api() -> None:
    """client.get_note() calls GET /vault/{path} and returns text."""
    http_client = _make_http_client()
    response = _make_response(text="# My Note\n\nContent here.")
    http_client.get.return_value = response

    client = ObsidianClient(http_client, "https://127.0.0.1:27124")
    content = await client.get_note("projects/my-note.md")

    http_client.get.assert_called_once()
    call_args = http_client.get.call_args
    assert "/vault/projects/my-note.md" in call_args[0][0]
    assert content == "# My Note\n\nContent here."


@pytest.mark.asyncio
async def test_put_note_calls_api() -> None:
    """client.put_note() calls PUT /vault/{path} with markdown content."""
    http_client = _make_http_client()
    response = _make_response(status_code=204)
    http_client.put.return_value = response

    client = ObsidianClient(http_client, "https://127.0.0.1:27124")
    await client.put_note("projects/new-note.md", "# New Note\n\nBody.")

    http_client.put.assert_called_once()
    call_args = http_client.put.call_args
    assert "/vault/projects/new-note.md" in call_args[0][0]
    assert call_args[1]["content"] == "# New Note\n\nBody."
    assert call_args[1]["headers"]["Content-Type"] == "text/markdown"


@pytest.mark.asyncio
async def test_delete_note_calls_api() -> None:
    """client.delete_note() calls DELETE /vault/{path}."""
    http_client = _make_http_client()
    response = _make_response(status_code=204)
    http_client.delete.return_value = response

    client = ObsidianClient(http_client, "https://127.0.0.1:27124")
    await client.delete_note("projects/old-note.md")

    http_client.delete.assert_called_once()
    call_args = http_client.delete.call_args
    assert "/vault/projects/old-note.md" in call_args[0][0]


@pytest.mark.asyncio
async def test_list_directory_calls_api() -> None:
    """client.list_directory() calls GET /vault/{path}/ with JSON accept header."""
    http_client = _make_http_client()
    entries = [{"name": "note.md", "type": "file"}]
    response = _make_response(json_data=entries)
    http_client.get.return_value = response

    client = ObsidianClient(http_client, "https://127.0.0.1:27124")
    result = await client.list_directory("projects/")

    http_client.get.assert_called_once()
    call_args = http_client.get.call_args
    assert "/vault/" in call_args[0][0]
    assert call_args[1]["headers"]["Accept"] == "application/json"
    assert result == entries


@pytest.mark.asyncio
async def test_patch_note_calls_api() -> None:
    """client.patch_note() calls PATCH /vault/{path} with correct insertion header."""
    http_client = _make_http_client()
    response = _make_response(status_code=200)
    http_client.patch.return_value = response

    client = ObsidianClient(http_client, "https://127.0.0.1:27124")
    await client.patch_note("daily/2026-02-18.md", "\n- New item", mode="append")

    http_client.patch.assert_called_once()
    call_args = http_client.patch.call_args
    assert "/vault/daily/2026-02-18.md" in call_args[0][0]
    assert call_args[1]["headers"]["Content-Insertion-Position"] == "end"


@pytest.mark.asyncio
async def test_patch_note_prepend_sets_beginning_header() -> None:
    """client.patch_note() with mode='prepend' sets insertion header to 'beginning'."""
    http_client = _make_http_client()
    response = _make_response(status_code=200)
    http_client.patch.return_value = response

    client = ObsidianClient(http_client, "https://127.0.0.1:27124")
    await client.patch_note("daily/2026-02-18.md", "## Header\n", mode="prepend")

    call_args = http_client.patch.call_args
    assert call_args[1]["headers"]["Content-Insertion-Position"] == "beginning"


@pytest.mark.asyncio
async def test_get_note_rejects_traversal_path() -> None:
    """client.get_note() raises ValueError when path contains '..'."""
    http_client = _make_http_client()
    client = ObsidianClient(http_client, "https://127.0.0.1:27124")

    with pytest.raises(ValueError, match="Path traversal not allowed"):
        await client.get_note("../etc/passwd")

    http_client.get.assert_not_called()


@pytest.mark.asyncio
async def test_search_raises_on_connect_error() -> None:
    """client.search() propagates httpx.ConnectError when vault is unreachable."""
    http_client = _make_http_client()
    http_client.post.side_effect = httpx.ConnectError("Connection refused")

    client = ObsidianClient(http_client, "https://127.0.0.1:27124")

    with pytest.raises(httpx.ConnectError):
        await client.search("test query")
