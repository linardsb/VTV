"""Tests for obsidian_bulk_operations tool."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.agents.tools.obsidian.bulk_operations import obsidian_bulk_operations


def _make_ctx(api_key: str | None = "test-key") -> MagicMock:
    """Create mock RunContext with UnifiedDeps for bulk operations tests."""
    ctx = MagicMock()
    ctx.deps.settings.obsidian_api_key = api_key
    ctx.deps.settings.obsidian_vault_url = "https://127.0.0.1:27124"
    ctx.deps.obsidian_http_client = AsyncMock()
    ctx.deps.transit_http_client = AsyncMock()
    return ctx


# --- Validation tests ---


@pytest.mark.asyncio
async def test_invalid_action_returns_error() -> None:
    """Invalid action returns a descriptive error message."""
    ctx = _make_ctx()
    result = await obsidian_bulk_operations(ctx, action="publish", targets=["notes/a.md"])
    assert "Invalid action" in result
    assert "publish" in result


@pytest.mark.asyncio
async def test_delete_requires_confirm() -> None:
    """Action 'delete' without confirm=True returns a safety error."""
    ctx = _make_ctx()
    result = await obsidian_bulk_operations(
        ctx, action="delete", targets=["notes/a.md", "notes/b.md"], confirm=False
    )
    assert "confirm=true" in result or "confirm" in result


@pytest.mark.asyncio
async def test_both_targets_and_pattern_rejected() -> None:
    """Providing both targets and target_pattern returns an error."""
    ctx = _make_ctx()
    result = await obsidian_bulk_operations(
        ctx,
        action="tag",
        targets=["notes/a.md"],
        target_pattern="notes/*.md",
        tags=["test"],
    )
    assert "not both" in result or "either" in result.lower()


@pytest.mark.asyncio
async def test_neither_targets_nor_pattern_rejected() -> None:
    """Providing neither targets nor target_pattern returns an error."""
    ctx = _make_ctx()
    result = await obsidian_bulk_operations(
        ctx, action="tag", targets=None, target_pattern=None, tags=["test"]
    )
    assert "requires either targets" in result or "targets" in result


@pytest.mark.asyncio
async def test_create_requires_items() -> None:
    """Action 'create' without items returns an error."""
    ctx = _make_ctx()
    result = await obsidian_bulk_operations(ctx, action="create", items=None)
    assert "requires items" in result


@pytest.mark.asyncio
async def test_vault_not_configured() -> None:
    """When obsidian_api_key is None, returns a configuration error."""
    ctx = _make_ctx(api_key=None)
    result = await obsidian_bulk_operations(
        ctx, action="tag", targets=["notes/a.md"], tags=["test"]
    )
    assert "not configured" in result
    assert "OBSIDIAN_API_KEY" in result


@pytest.mark.asyncio
async def test_invalid_target_path_rejected() -> None:
    """Target path with '..' returns a path traversal error."""
    ctx = _make_ctx()
    result = await obsidian_bulk_operations(
        ctx, action="tag", targets=["../secrets/config.md"], tags=["test"]
    )
    assert "not allowed" in result


@pytest.mark.asyncio
async def test_tag_requires_tags_param() -> None:
    """Action 'tag' without tags parameter returns an error."""
    ctx = _make_ctx()
    result = await obsidian_bulk_operations(ctx, action="tag", targets=["notes/a.md"], tags=None)
    assert "requires tags" in result


@pytest.mark.asyncio
async def test_move_requires_destination() -> None:
    """Action 'move' without destination returns an error."""
    ctx = _make_ctx()
    result = await obsidian_bulk_operations(
        ctx, action="move", targets=["notes/a.md"], destination=None
    )
    assert "requires destination" in result


# --- Functional tests ---


@pytest.mark.asyncio
async def test_dry_run_move_preview() -> None:
    """dry_run=True for move returns a preview without making changes."""
    ctx = _make_ctx()

    with patch(
        "app.core.agents.tools.obsidian.bulk_operations.ObsidianClient.get_note",
        new_callable=AsyncMock,
    ) as mock_get:
        result = await obsidian_bulk_operations(
            ctx,
            action="move",
            targets=["notes/alpha.md", "notes/beta.md"],
            destination="archive/",
            dry_run=True,
        )

    # dry_run should not read any notes
    mock_get.assert_not_called()

    data = json.loads(result)
    assert data["dry_run"] is True
    assert data["action"] == "move"
    assert data["matched"] == 2
    assert data["preview"] is not None
    assert len(data["preview"]) == 2
    assert data["preview"][0]["from"] == "notes/alpha.md"
    assert "archive/" in data["preview"][0]["to"]


@pytest.mark.asyncio
async def test_bulk_tag_adds_tags() -> None:
    """Bulk tag action reads note, adds tags to frontmatter, and writes updated content."""
    ctx = _make_ctx()
    note_content = "---\ntitle: Test Note\ntags:\n  - existing\n---\n\n# Body"

    with (
        patch(
            "app.core.agents.tools.obsidian.bulk_operations.ObsidianClient.get_note",
            new_callable=AsyncMock,
            return_value=note_content,
        ) as mock_get,
        patch(
            "app.core.agents.tools.obsidian.bulk_operations.ObsidianClient.put_note",
            new_callable=AsyncMock,
        ) as mock_put,
    ):
        result = await obsidian_bulk_operations(
            ctx,
            action="tag",
            targets=["notes/test.md"],
            tags=["new-tag"],
            tag_mode="add",
        )

    mock_get.assert_called_once_with("notes/test.md")
    mock_put.assert_called_once()

    put_args = mock_put.call_args
    written_content = put_args[0][1]
    assert "new-tag" in written_content
    assert "existing" in written_content

    data = json.loads(result)
    assert data["succeeded"] == 1
    assert data["failed"] == 0
    assert data["action"] == "tag"


@pytest.mark.asyncio
async def test_bulk_tag_remove_tags() -> None:
    """Bulk tag with tag_mode='remove' removes specified tags from frontmatter."""
    ctx = _make_ctx()
    note_content = "---\ntags:\n  - keep\n  - remove-me\n---\n\n# Body"

    with (
        patch(
            "app.core.agents.tools.obsidian.bulk_operations.ObsidianClient.get_note",
            new_callable=AsyncMock,
            return_value=note_content,
        ),
        patch(
            "app.core.agents.tools.obsidian.bulk_operations.ObsidianClient.put_note",
            new_callable=AsyncMock,
        ) as mock_put,
    ):
        result = await obsidian_bulk_operations(
            ctx,
            action="tag",
            targets=["notes/test.md"],
            tags=["remove-me"],
            tag_mode="remove",
        )

    put_args = mock_put.call_args
    written_content = put_args[0][1]
    assert "remove-me" not in written_content
    assert "keep" in written_content

    data = json.loads(result)
    assert data["succeeded"] == 1


@pytest.mark.asyncio
async def test_bulk_create_creates_notes() -> None:
    """Bulk create action calls put_note for each item in items list."""
    ctx = _make_ctx()
    items: list[dict[str, str | dict[str, str | list[str] | int | float | bool | None] | None]] = [
        {"filepath": "notes/alpha.md", "content": "# Alpha"},
        {"filepath": "notes/beta.md", "content": "# Beta"},
    ]

    with patch(
        "app.core.agents.tools.obsidian.bulk_operations.ObsidianClient.put_note",
        new_callable=AsyncMock,
    ) as mock_put:
        result = await obsidian_bulk_operations(ctx, action="create", items=items)

    assert mock_put.call_count == 2

    called_paths = [call[0][0] for call in mock_put.call_args_list]
    assert "notes/alpha.md" in called_paths
    assert "notes/beta.md" in called_paths

    data = json.loads(result)
    assert data["succeeded"] == 2
    assert data["failed"] == 0
    assert data["action"] == "create"
    assert data["dry_run"] is False


@pytest.mark.asyncio
async def test_dry_run_create_returns_preview() -> None:
    """dry_run=True for create returns preview without creating any notes."""
    ctx = _make_ctx()
    items: list[dict[str, str | dict[str, str | list[str] | int | float | bool | None] | None]] = [
        {"filepath": "notes/alpha.md", "content": "# Alpha"},
        {"filepath": "notes/beta.md", "content": "# Beta"},
    ]

    with patch(
        "app.core.agents.tools.obsidian.bulk_operations.ObsidianClient.put_note",
        new_callable=AsyncMock,
    ) as mock_put:
        result = await obsidian_bulk_operations(ctx, action="create", items=items, dry_run=True)

    mock_put.assert_not_called()
    data = json.loads(result)
    assert data["dry_run"] is True
    assert data["matched"] == 2
    assert data["preview"] is not None
    assert len(data["preview"]) == 2


@pytest.mark.asyncio
async def test_bulk_delete_with_confirm_deletes_files() -> None:
    """Bulk delete with confirm=True calls delete_note for each target."""
    ctx = _make_ctx()

    with patch(
        "app.core.agents.tools.obsidian.bulk_operations.ObsidianClient.delete_note",
        new_callable=AsyncMock,
    ) as mock_delete:
        result = await obsidian_bulk_operations(
            ctx,
            action="delete",
            targets=["notes/alpha.md", "notes/beta.md"],
            confirm=True,
        )

    assert mock_delete.call_count == 2
    data = json.loads(result)
    assert data["succeeded"] == 2
    assert data["failed"] == 0


@pytest.mark.asyncio
async def test_bulk_update_frontmatter_updates_fields() -> None:
    """bulk update_frontmatter patches specified keys in each note's frontmatter."""
    ctx = _make_ctx()
    note_content = "---\ntitle: Old Title\nstatus: draft\n---\n\n# Body"

    with (
        patch(
            "app.core.agents.tools.obsidian.bulk_operations.ObsidianClient.get_note",
            new_callable=AsyncMock,
            return_value=note_content,
        ),
        patch(
            "app.core.agents.tools.obsidian.bulk_operations.ObsidianClient.put_note",
            new_callable=AsyncMock,
        ) as mock_put,
    ):
        result = await obsidian_bulk_operations(
            ctx,
            action="update_frontmatter",
            targets=["notes/test.md"],
            frontmatter={"status": "published"},
        )

    put_args = mock_put.call_args
    written_content = put_args[0][1]
    assert "published" in written_content

    data = json.loads(result)
    assert data["succeeded"] == 1
    assert data["action"] == "update_frontmatter"


@pytest.mark.asyncio
async def test_no_matched_files_returns_empty_result() -> None:
    """When targets list is empty after resolution, returns matched=0 result."""
    ctx = _make_ctx()

    with patch(
        "app.core.agents.tools.obsidian.bulk_operations.ObsidianClient.list_directory",
        new_callable=AsyncMock,
        return_value=[],
    ):
        result = await obsidian_bulk_operations(
            ctx,
            action="tag",
            target_pattern="nonexistent/*.md",
            tags=["test"],
        )

    data = json.loads(result)
    assert data["matched"] == 0
    assert data["hint"] is not None
