"""Tests for obsidian_manage_folders tool."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.agents.tools.obsidian.manage_folders import obsidian_manage_folders


def _make_ctx(api_key: str | None = "test-key") -> MagicMock:
    """Create mock RunContext with UnifiedDeps for manage folders tests."""
    ctx = MagicMock()
    ctx.deps.settings.obsidian_api_key = api_key
    ctx.deps.settings.obsidian_vault_url = "https://127.0.0.1:27124"
    ctx.deps.obsidian_http_client = AsyncMock()
    ctx.deps.transit_http_client = AsyncMock()
    return ctx


# --- Validation tests ---


@pytest.mark.asyncio
async def test_invalid_action_returns_error() -> None:
    """Invalid action returns a descriptive error message listing valid actions."""
    ctx = _make_ctx()
    result = await obsidian_manage_folders(ctx, action="archive", path="projects/")
    assert "Invalid action" in result
    assert "archive" in result
    assert "list" in result


@pytest.mark.asyncio
async def test_delete_requires_confirm() -> None:
    """Action 'delete' without confirm=True returns a safety error."""
    ctx = _make_ctx()
    result = await obsidian_manage_folders(
        ctx, action="delete", path="projects/old/", confirm=False
    )
    assert "confirm=true" in result or "confirm" in result


@pytest.mark.asyncio
async def test_move_requires_new_path() -> None:
    """Action 'move' without new_path returns an error."""
    ctx = _make_ctx()
    result = await obsidian_manage_folders(ctx, action="move", path="projects/old/", new_path=None)
    assert "requires new_path" in result


@pytest.mark.asyncio
async def test_vault_not_configured() -> None:
    """When obsidian_api_key is None, returns a configuration error."""
    ctx = _make_ctx(api_key=None)
    result = await obsidian_manage_folders(ctx, action="list", path="projects/")
    assert "not configured" in result
    assert "OBSIDIAN_API_KEY" in result


@pytest.mark.asyncio
async def test_invalid_path_rejected() -> None:
    """path with '..' returns a path traversal error."""
    ctx = _make_ctx()
    result = await obsidian_manage_folders(ctx, action="list", path="../secrets/")
    assert "not allowed" in result


@pytest.mark.asyncio
async def test_invalid_move_new_path_rejected() -> None:
    """new_path with '..' in a move action returns a path traversal error."""
    ctx = _make_ctx()
    result = await obsidian_manage_folders(
        ctx, action="move", path="projects/old/", new_path="../outside/new/"
    )
    assert "not allowed" in result


# --- Functional tests ---


@pytest.mark.asyncio
async def test_list_returns_contents() -> None:
    """Action 'list' returns a FolderListResponse with files and folders."""
    ctx = _make_ctx()
    fake_entries = [
        {"name": "note.md", "type": "file", "mtime": 1739880000, "size": 1024},
        {"name": "subfolder", "type": "folder"},
    ]

    with patch(
        "app.core.agents.tools.obsidian.manage_folders.ObsidianClient.list_directory",
        new_callable=AsyncMock,
        return_value=fake_entries,
    ):
        result = await obsidian_manage_folders(ctx, action="list", path="projects/")

    data = json.loads(result)
    assert data["path"] == "projects/"
    assert data["total_files"] == 1
    assert data["total_folders"] == 1
    assert len(data["children"]) == 2

    names = [child["name"] for child in data["children"]]
    assert "note.md" in names
    assert "subfolder" in names


@pytest.mark.asyncio
async def test_list_include_files_false_excludes_files() -> None:
    """Action 'list' with include_files=False omits files from children."""
    ctx = _make_ctx()
    fake_entries = [
        {"name": "note.md", "type": "file", "mtime": 1739880000},
        {"name": "subfolder", "type": "folder"},
    ]

    with patch(
        "app.core.agents.tools.obsidian.manage_folders.ObsidianClient.list_directory",
        new_callable=AsyncMock,
        return_value=fake_entries,
    ):
        result = await obsidian_manage_folders(
            ctx, action="list", path="projects/", include_files=False
        )

    data = json.loads(result)
    assert data["total_files"] == 1  # still counted
    child_names = [child["name"] for child in data["children"]]
    assert "note.md" not in child_names
    assert "subfolder" in child_names


@pytest.mark.asyncio
async def test_create_creates_gitkeep() -> None:
    """Action 'create' calls put_note with a .gitkeep placeholder file."""
    ctx = _make_ctx()

    with patch(
        "app.core.agents.tools.obsidian.manage_folders.ObsidianClient.put_note",
        new_callable=AsyncMock,
    ) as mock_put:
        result = await obsidian_manage_folders(ctx, action="create", path="projects/new-folder")

    mock_put.assert_called_once()
    call_args = mock_put.call_args
    # The first positional argument should be the .gitkeep path
    gitkeep_path = call_args[0][0]
    assert ".gitkeep" in gitkeep_path
    assert "projects/new-folder" in gitkeep_path

    data = json.loads(result)
    assert data["success"] is True
    assert data["action"] == "create"
    assert data["path"] == "projects/new-folder"


@pytest.mark.asyncio
async def test_delete_empty_folder_succeeds() -> None:
    """Action 'delete' on an empty folder with confirm=True returns success."""
    ctx = _make_ctx()

    with patch(
        "app.core.agents.tools.obsidian.manage_folders.ObsidianClient.list_directory",
        new_callable=AsyncMock,
        return_value=[],
    ):
        result = await obsidian_manage_folders(
            ctx, action="delete", path="projects/empty/", confirm=True
        )

    data = json.loads(result)
    assert data["success"] is True
    assert data["action"] == "delete"


@pytest.mark.asyncio
async def test_delete_non_empty_without_recursive_returns_error() -> None:
    """Action 'delete' on a non-empty folder without recursive=True returns an error."""
    ctx = _make_ctx()
    fake_entries = [
        {"name": "note.md", "type": "file"},
    ]

    with patch(
        "app.core.agents.tools.obsidian.manage_folders.ObsidianClient.list_directory",
        new_callable=AsyncMock,
        return_value=fake_entries,
    ):
        result = await obsidian_manage_folders(
            ctx, action="delete", path="projects/full/", confirm=True, recursive=False
        )

    assert "not empty" in result
    assert "recursive=true" in result


@pytest.mark.asyncio
async def test_move_returns_success() -> None:
    """Action 'move' lists source, copies files, and returns FolderOperationResult."""
    ctx = _make_ctx()
    fake_entries = [
        {"name": "note.md", "path": "projects/old/note.md", "type": "file"},
    ]

    with (
        patch(
            "app.core.agents.tools.obsidian.manage_folders.ObsidianClient.list_directory",
            new_callable=AsyncMock,
            return_value=fake_entries,
        ),
        patch(
            "app.core.agents.tools.obsidian.manage_folders.ObsidianClient.get_note",
            new_callable=AsyncMock,
            return_value="# Note content",
        ),
        patch(
            "app.core.agents.tools.obsidian.manage_folders.ObsidianClient.put_note",
            new_callable=AsyncMock,
        ),
        patch(
            "app.core.agents.tools.obsidian.manage_folders.ObsidianClient.delete_note",
            new_callable=AsyncMock,
        ),
    ):
        result = await obsidian_manage_folders(
            ctx, action="move", path="projects/old/", new_path="archive/old/"
        )

    data = json.loads(result)
    assert data["success"] is True
    assert data["action"] == "move"
    assert "archive/old" in data["path"]
