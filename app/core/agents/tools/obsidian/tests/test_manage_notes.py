"""Tests for obsidian_manage_notes tool and helper functions."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.agents.tools.obsidian.manage_notes import (
    _extract_section,
    _parse_frontmatter,
    _serialize_frontmatter,
    obsidian_manage_notes,
)


def _make_ctx(api_key: str | None = "test-key") -> MagicMock:
    """Create mock RunContext with UnifiedDeps for manage notes tests."""
    ctx = MagicMock()
    ctx.deps.settings.obsidian_api_key = api_key
    ctx.deps.settings.obsidian_vault_url = "https://127.0.0.1:27124"
    ctx.deps.obsidian_http_client = AsyncMock()
    ctx.deps.transit_http_client = AsyncMock()
    return ctx


# --- Helper function tests (pure, synchronous) ---


def test_serialize_frontmatter_basic() -> None:
    """_serialize_frontmatter produces valid YAML block for string and list values."""
    fm: dict[str, str | list[str] | int | float | bool | None] = {
        "title": "My Note",
        "tags": ["project", "active"],
        "priority": 1,
    }
    result = _serialize_frontmatter(fm)

    assert result.startswith("---\n")
    assert result.endswith("---\n")
    assert "title: My Note" in result
    assert "tags:" in result
    assert "  - project" in result
    assert "  - active" in result
    assert "priority: 1" in result


def test_serialize_frontmatter_skips_none() -> None:
    """_serialize_frontmatter omits keys with None values."""
    fm: dict[str, str | list[str] | int | float | bool | None] = {
        "title": "Test",
        "author": None,
    }
    result = _serialize_frontmatter(fm)

    assert "title: Test" in result
    assert "author" not in result


def test_serialize_frontmatter_quotes_special_chars() -> None:
    """_serialize_frontmatter quotes string values containing special YAML chars."""
    fm: dict[str, str | list[str] | int | float | bool | None] = {
        "url": "https://example.com:8080",
    }
    result = _serialize_frontmatter(fm)

    assert '"https://example.com:8080"' in result


def test_serialize_frontmatter_bool() -> None:
    """_serialize_frontmatter renders booleans as true/false."""
    fm: dict[str, str | list[str] | int | float | bool | None] = {
        "published": True,
        "draft": False,
    }
    result = _serialize_frontmatter(fm)

    assert "published: true" in result
    assert "draft: false" in result


def test_parse_frontmatter_basic() -> None:
    """_parse_frontmatter extracts a frontmatter dict from valid YAML block."""
    content = "---\ntitle: My Note\nauthor: Berzins\n---\n\n# Body text here"
    fm, body = _parse_frontmatter(content)

    assert fm["title"] == "My Note"
    assert fm["author"] == "Berzins"
    assert "# Body text here" in body


def test_parse_frontmatter_list_values() -> None:
    """_parse_frontmatter parses list values in frontmatter."""
    content = "---\ntags:\n  - project\n  - active\n---\n\nBody"
    fm, body = _parse_frontmatter(content)

    assert fm["tags"] == ["project", "active"]
    assert "Body" in body


def test_parse_frontmatter_no_frontmatter() -> None:
    """_parse_frontmatter returns empty dict and full content when no frontmatter."""
    content = "# Just a heading\n\nSome body text."
    fm, body = _parse_frontmatter(content)

    assert fm == {}
    assert body == content


def test_parse_frontmatter_empty_value_starts_list() -> None:
    """_parse_frontmatter handles key with empty value followed by list items."""
    content = "---\ntags:\n  - alpha\n  - beta\n---\n\nBody"
    fm, _body = _parse_frontmatter(content)

    assert isinstance(fm["tags"], list)
    assert "alpha" in fm["tags"]
    assert "beta" in fm["tags"]


def test_extract_section_returns_heading_content() -> None:
    """_extract_section returns the heading line and content until next same-level heading."""
    content = "# Doc\n\n## Meeting Notes\n\nSome notes here.\n\n## Other Section\n\nOther content."
    result = _extract_section(content, "## Meeting Notes")

    assert result is not None
    assert "## Meeting Notes" in result
    assert "Some notes here." in result
    assert "## Other Section" not in result


def test_extract_section_returns_none_when_not_found() -> None:
    """_extract_section returns None when the heading does not exist."""
    content = "# Doc\n\n## Existing Section\n\nContent."
    result = _extract_section(content, "## Missing Section")

    assert result is None


def test_extract_section_case_insensitive() -> None:
    """_extract_section matches headings case-insensitively."""
    content = "## Meeting Notes\n\nContent here."
    result = _extract_section(content, "meeting notes")

    assert result is not None
    assert "Content here." in result


# --- obsidian_manage_notes tool tests ---


@pytest.mark.asyncio
async def test_invalid_action_returns_error() -> None:
    """Invalid action returns a descriptive error message."""
    ctx = _make_ctx()
    result = await obsidian_manage_notes(ctx, action="publish", filepath="notes/test.md")
    assert "Invalid action" in result
    assert "publish" in result


@pytest.mark.asyncio
async def test_create_requires_content() -> None:
    """Action 'create' without content returns an error."""
    ctx = _make_ctx()
    result = await obsidian_manage_notes(
        ctx, action="create", filepath="notes/new.md", content=None
    )
    assert "requires content" in result


@pytest.mark.asyncio
async def test_delete_requires_confirm() -> None:
    """Action 'delete' without confirm=True returns a safety error."""
    ctx = _make_ctx()
    result = await obsidian_manage_notes(
        ctx, action="delete", filepath="notes/old.md", confirm=False
    )
    assert "confirm=true" in result or "confirm" in result


@pytest.mark.asyncio
async def test_vault_not_configured() -> None:
    """When obsidian_api_key is None, returns a configuration error."""
    ctx = _make_ctx(api_key=None)
    result = await obsidian_manage_notes(ctx, action="read", filepath="notes/test.md")
    assert "not configured" in result
    assert "OBSIDIAN_API_KEY" in result


@pytest.mark.asyncio
async def test_invalid_filepath_rejected() -> None:
    """filepath with '..' returns a path traversal error."""
    ctx = _make_ctx()
    result = await obsidian_manage_notes(ctx, action="read", filepath="../secrets/config.md")
    assert "not allowed" in result


@pytest.mark.asyncio
async def test_update_requires_mode() -> None:
    """Action 'update' without mode parameter returns an error."""
    ctx = _make_ctx()
    result = await obsidian_manage_notes(
        ctx, action="update", filepath="notes/test.md", content="new content", mode=None
    )
    assert "requires mode" in result


@pytest.mark.asyncio
async def test_move_requires_new_filepath() -> None:
    """Action 'move' without new_filepath returns an error."""
    ctx = _make_ctx()
    result = await obsidian_manage_notes(
        ctx, action="move", filepath="notes/old.md", new_filepath=None
    )
    assert "requires new_filepath" in result


@pytest.mark.asyncio
async def test_read_returns_note() -> None:
    """Action 'read' calls get_note and returns JSON with NoteContent structure."""
    ctx = _make_ctx()
    note_content = "---\ntitle: My Note\n---\n\n# My Note\n\nThis is the body with some words."

    with patch(
        "app.core.agents.tools.obsidian.manage_notes.ObsidianClient.get_note",
        new_callable=AsyncMock,
        return_value=note_content,
    ):
        result = await obsidian_manage_notes(ctx, action="read", filepath="projects/my-note.md")

    data = json.loads(result)
    assert data["path"] == "projects/my-note.md"
    assert data["title"] == "my-note"
    assert "body" in data["content"] or "My Note" in data["content"]
    assert data["word_count"] > 0
    assert data["frontmatter"] is not None
    assert data["frontmatter"]["title"] == "My Note"


@pytest.mark.asyncio
async def test_read_section_returns_only_section() -> None:
    """Action 'read' with section parameter returns only that section."""
    ctx = _make_ctx()
    note_content = "# Doc\n\n## Meeting Notes\n\nNotes content.\n\n## Action Items\n\nTasks here."

    with patch(
        "app.core.agents.tools.obsidian.manage_notes.ObsidianClient.get_note",
        new_callable=AsyncMock,
        return_value=note_content,
    ):
        result = await obsidian_manage_notes(
            ctx,
            action="read",
            filepath="projects/doc.md",
            section="## Meeting Notes",
        )

    data = json.loads(result)
    assert "Meeting Notes" in data["content"]
    assert "Action Items" not in data["content"]


@pytest.mark.asyncio
async def test_create_puts_note_with_content() -> None:
    """Action 'create' calls put_note and returns NoteOperationResult."""
    ctx = _make_ctx()

    with patch(
        "app.core.agents.tools.obsidian.manage_notes.ObsidianClient.put_note",
        new_callable=AsyncMock,
    ) as mock_put:
        result = await obsidian_manage_notes(
            ctx,
            action="create",
            filepath="projects/new-note.md",
            content="# New Note\n\nContent.",
        )

    mock_put.assert_called_once()
    data = json.loads(result)
    assert data["success"] is True
    assert data["action"] == "create"
    assert data["path"] == "projects/new-note.md"


@pytest.mark.asyncio
async def test_delete_with_confirm_deletes_note() -> None:
    """Action 'delete' with confirm=True calls delete_note and returns success."""
    ctx = _make_ctx()

    with patch(
        "app.core.agents.tools.obsidian.manage_notes.ObsidianClient.delete_note",
        new_callable=AsyncMock,
    ) as mock_delete:
        result = await obsidian_manage_notes(
            ctx,
            action="delete",
            filepath="projects/old-note.md",
            confirm=True,
        )

    mock_delete.assert_called_once()
    data = json.loads(result)
    assert data["success"] is True
    assert data["action"] == "delete"
