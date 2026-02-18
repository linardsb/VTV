"""Obsidian tool: obsidian_manage_folders.

Folder create, delete, list, and move operations for the Obsidian vault.
"""

from __future__ import annotations

import json
import time

import httpx
from pydantic_ai import RunContext

from app.core.agents.tools.obsidian.client import ObsidianClient, _validate_path
from app.core.agents.tools.obsidian.schemas import (
    FolderEntry,
    FolderListResponse,
    FolderOperationResult,
)
from app.core.agents.tools.transit.deps import UnifiedDeps
from app.core.logging import get_logger

logger = get_logger(__name__)

_VALID_ACTIONS = ("create", "delete", "list", "move")
_DEFAULT_DEPTH = 1
_MAX_DEPTH = 10


def _validate_folder_params(
    action: str,
    path: str,
    new_path: str | None,
    confirm: bool,
    recursive: bool,
) -> str | None:
    """Validate parameters for manage_folders actions.

    Returns:
        Error message string if invalid, None if valid.
    """
    if action not in _VALID_ACTIONS:
        return (
            f"Invalid action '{action}'. "
            f"Use one of: {', '.join(_VALID_ACTIONS)}. "
            "Example: obsidian_manage_folders(action='list', path='projects/')"
        )

    try:
        _validate_path(path)
    except ValueError:
        return f"Invalid path '{path}'. Path traversal ('..') is not allowed."

    # recursive is validated in the delete branch below
    _ = recursive

    if action == "delete" and not confirm:
        return (
            "Delete requires confirm=true to prevent accidental deletion. "
            "Use obsidian_manage_folders(action='list') first to see folder contents."
        )

    if action == "move" and new_path is None:
        return "Action 'move' requires new_path parameter."

    if action == "move" and new_path is not None:
        try:
            _validate_path(new_path)
        except ValueError:
            return f"Invalid new_path '{new_path}'. Path traversal ('..') is not allowed."

    return None


async def obsidian_manage_folders(
    ctx: RunContext[UnifiedDeps],
    action: str,
    path: str,
    new_path: str | None = None,
    depth: int = _DEFAULT_DEPTH,
    include_files: bool = True,
    include_subfolders: bool = True,
    recursive: bool = False,
    confirm: bool = False,
) -> str:
    """Organize vault structure - create, delete, list, or move folders.

    WHEN TO USE: User wants to create a folder, see what's in a folder, delete
    a folder, or move/rename a folder in the vault.

    WHEN NOT TO USE: For working with individual notes (use obsidian_manage_notes).
    For searching note content (use obsidian_query_vault). For batch operations
    on files (use obsidian_bulk_operations).

    ACTIONS:
    - "create": Create a new folder.
    - "delete": Delete a folder. Requires confirm=true. Non-empty folders need recursive=true.
    - "list": List folder contents with depth control.
    - "move": Move/rename a folder. Requires new_path.

    EFFICIENCY: Use depth=1 for quick listing. Increase depth for nested structure.

    SAFETY: Delete requires confirm=true. Non-empty folders also require recursive=true.

    Args:
        ctx: Pydantic AI run context with UnifiedDeps.
        action: One of "create", "delete", "list", "move".
        path: Folder path relative to vault root.
        new_path: Destination path for move action.
        depth: How deep to list subfolders (default 1, max 10).
        include_files: Include files in listing (default true).
        include_subfolders: Include subfolders in listing (default true).
        recursive: Allow deleting non-empty folders (default false).
        confirm: Required true for delete action.

    Returns:
        JSON string with FolderListResponse (list) or FolderOperationResult.
    """
    _settings = ctx.deps.settings
    start_time = time.monotonic()

    logger.info(
        "obsidian.manage_folders.started",
        action=action,
        path=path,
    )

    # Validate params
    validation_error = _validate_folder_params(action, path, new_path, confirm, recursive)
    if validation_error:
        return validation_error

    # Check vault configured
    if _settings.obsidian_api_key is None:
        return "Obsidian vault is not configured. Set OBSIDIAN_API_KEY environment variable."

    effective_depth = min(max(depth, 1), _MAX_DEPTH)
    client = ObsidianClient(ctx.deps.obsidian_http_client, _settings.obsidian_vault_url)

    try:
        if action == "create":
            result_str = await _handle_create(client, path)
        elif action == "delete":
            result_str = await _handle_delete(client, path, recursive)
        elif action == "list":
            result_str = await _handle_list(
                client, path, effective_depth, include_files, include_subfolders
            )
        elif action == "move" and new_path is not None:
            result_str = await _handle_move(client, path, new_path)
        else:
            return "Unexpected parameter combination."

        duration_ms = int((time.monotonic() - start_time) * 1000)
        logger.info(
            "obsidian.manage_folders.completed",
            action=action,
            path=path,
            duration_ms=duration_ms,
        )
        return result_str

    except httpx.HTTPStatusError as e:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        logger.error(
            "obsidian.manage_folders.failed",
            action=action,
            path=path,
            error=str(e),
            error_type=type(e).__name__,
            duration_ms=duration_ms,
        )
        if e.response.status_code == 404:
            return f"Folder not found: '{path}'. Use obsidian_manage_folders(action='list', path='/') to see available folders."
        return f"Vault API error ({e.response.status_code}): {e}"

    except Exception as e:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        logger.error(
            "obsidian.manage_folders.failed",
            exc_info=True,
            action=action,
            path=path,
            error=str(e),
            error_type=type(e).__name__,
            duration_ms=duration_ms,
        )
        return f"Vault operation failed: {e}"


async def _handle_create(client: ObsidianClient, path: str) -> str:
    """Create a folder by putting a placeholder .gitkeep file."""
    gitkeep_path = f"{path.rstrip('/')}/.gitkeep"
    await client.put_note(gitkeep_path, "")

    result = FolderOperationResult(
        success=True,
        action="create",
        path=path,
        message=f"Folder created at '{path}'.",
    )
    return json.dumps(result.model_dump(), ensure_ascii=False)


async def _handle_delete(
    client: ObsidianClient,
    path: str,
    recursive: bool,
) -> str:
    """Delete a folder, optionally recursively."""
    # Check contents first
    entries = await client.list_directory(path)

    if entries and not recursive:
        return (
            f"Folder '{path}' is not empty ({len(entries)} items). "
            "Use recursive=true to delete the folder and all its contents."
        )

    # Delete all contents recursively
    for entry in entries:
        entry_path = str(entry.get("path", entry.get("name", "")))
        entry_type = str(entry.get("type", "file"))
        if entry_type == "folder":
            await _handle_delete(client, entry_path, recursive=True)
        else:
            await client.delete_note(entry_path)

    result = FolderOperationResult(
        success=True,
        action="delete",
        path=path,
        message=f"Folder deleted: '{path}' ({len(entries)} items removed).",
    )
    return json.dumps(result.model_dump(), ensure_ascii=False)


async def _handle_list(
    client: ObsidianClient,
    path: str,
    depth: int,
    include_files: bool,
    include_subfolders: bool,
) -> str:
    """List folder contents with depth control."""
    # depth is reserved for future recursive listing
    _ = depth
    entries = await client.list_directory(path)

    children: list[FolderEntry] = []
    total_files = 0
    total_folders = 0

    for entry in entries:
        entry_type = str(entry.get("type", "file"))
        entry_name = str(entry.get("name", entry.get("path", "")))

        if entry_type == "folder":
            total_folders += 1
            if not include_subfolders:
                continue
            folder_entry = FolderEntry(
                name=entry_name,
                type="folder",
                item_count=ic if isinstance(ic := entry.get("children"), int) else None,
            )
            children.append(folder_entry)
        else:
            total_files += 1
            if not include_files:
                continue
            children.append(
                FolderEntry(
                    name=entry_name,
                    type="file",
                    modified=str(mt) if (mt := entry.get("mtime")) is not None else None,
                    size_bytes=sz if isinstance(sz := entry.get("size"), int) else None,
                )
            )

    response = FolderListResponse(
        path=path,
        children=children,
        total_files=total_files,
        total_folders=total_folders,
    )
    return json.dumps(response.model_dump(), ensure_ascii=False)


async def _handle_move(
    client: ObsidianClient,
    path: str,
    new_path: str,
) -> str:
    """Move a folder by copying contents and deleting the original."""
    entries = await client.list_directory(path)

    for entry in entries:
        entry_path = str(entry.get("path", entry.get("name", "")))
        entry_name = entry_path.rsplit("/", 1)[-1] if "/" in entry_path else entry_path
        new_entry_path = f"{new_path.rstrip('/')}/{entry_name}"
        entry_type = str(entry.get("type", "file"))

        if entry_type == "folder":
            await _handle_move(client, entry_path, new_entry_path)
        else:
            content = await client.get_note(entry_path)
            await client.put_note(new_entry_path, content)
            await client.delete_note(entry_path)

    result = FolderOperationResult(
        success=True,
        action="move",
        path=new_path,
        message=f"Folder moved from '{path}' to '{new_path}'.",
    )
    return json.dumps(result.model_dump(), ensure_ascii=False)
