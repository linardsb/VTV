"""Obsidian tool: obsidian_bulk_operations.

Batch operations on multiple notes with dry_run support for previewing
changes before execution.
"""

from __future__ import annotations

import fnmatch
import json
import time

import httpx
from pydantic_ai import RunContext

from app.core.agents.tools.obsidian.client import ObsidianClient, _validate_path
from app.core.agents.tools.obsidian.manage_notes import _parse_frontmatter, _serialize_frontmatter
from app.core.agents.tools.obsidian.schemas import BulkOperationResult
from app.core.agents.tools.transit.deps import UnifiedDeps
from app.core.logging import get_logger

logger = get_logger(__name__)

_VALID_ACTIONS = ("move", "tag", "delete", "update_frontmatter", "create")
_VALID_TAG_MODES = ("add", "remove")
_MAX_TARGETS = 100


def _validate_bulk_params(
    action: str,
    targets: list[str] | None,
    target_pattern: str | None,
    destination: str | None,
    tags: list[str] | None,
    items: list[dict[str, str | dict[str, str | list[str] | int | float | bool | None] | None]]
    | None,
    confirm: bool,
    frontmatter: dict[str, str | list[str] | int | float | bool | None] | None,
) -> str | None:
    """Validate parameters for bulk operations.

    Returns:
        Error message string if invalid, None if valid.
    """
    if action not in _VALID_ACTIONS:
        return (
            f"Invalid action '{action}'. "
            f"Use one of: {', '.join(_VALID_ACTIONS)}. "
            "Example: obsidian_bulk_operations(action='tag', targets=['a.md', 'b.md'], tags=['project'])"
        )

    # For non-create actions, exactly one targeting method required
    if action != "create":
        if targets is not None and target_pattern is not None:
            return (
                "Provide either targets (explicit list) OR target_pattern (glob), not both. "
                "Use obsidian_query_vault(action='glob') to preview which files match a pattern."
            )
        if targets is None and target_pattern is None:
            return (
                f"Action '{action}' requires either targets (list of file paths) "
                "or target_pattern (glob pattern). "
                "Example: targets=['notes/a.md', 'notes/b.md'] or target_pattern='notes/*.md'"
            )

    # Validate targets paths
    if targets is not None:
        for target in targets:
            try:
                _validate_path(target)
            except ValueError:
                return f"Invalid target path '{target}'. Path traversal ('..') is not allowed."

    # Action-specific validation
    if action == "move" and destination is None:
        return "Action 'move' requires destination parameter (folder path)."

    if action == "tag" and not tags:
        return "Action 'tag' requires tags parameter."

    if action == "delete" and not confirm:
        return (
            "Bulk delete requires confirm=true. "
            "Use dry_run=true first to preview which files would be deleted."
        )

    if action == "update_frontmatter" and frontmatter is None:
        return "Action 'update_frontmatter' requires frontmatter parameter."

    if action == "create" and not items:
        return "Action 'create' requires items parameter (list of {filepath, content, frontmatter?} dicts)."

    return None


async def _resolve_targets(
    client: ObsidianClient,
    targets: list[str] | None,
    target_pattern: str | None,
) -> list[str]:
    """Resolve target files from explicit list or glob pattern.

    Args:
        client: Obsidian client for listing files.
        targets: Explicit list of file paths.
        target_pattern: Glob pattern to match files.

    Returns:
        List of resolved file paths.
    """
    if targets is not None:
        return targets[:_MAX_TARGETS]

    if target_pattern is not None:
        entries = await client.list_directory("/")
        matched: list[str] = []
        for entry in entries:
            filepath = str(entry.get("path", entry.get("name", "")))
            if fnmatch.fnmatch(filepath, target_pattern):
                matched.append(filepath)
                if len(matched) >= _MAX_TARGETS:
                    break
        return matched

    return []


async def obsidian_bulk_operations(
    ctx: RunContext[UnifiedDeps],
    action: str,
    targets: list[str] | None = None,
    target_pattern: str | None = None,
    destination: str | None = None,
    tags: list[str] | None = None,
    tag_mode: str = "add",
    frontmatter: dict[str, str | list[str] | int | float | bool | None] | None = None,
    items: list[dict[str, str | dict[str, str | list[str] | int | float | bool | None] | None]]
    | None = None,
    confirm: bool = False,
    dry_run: bool = False,
) -> str:
    """Batch operations on multiple notes - move, tag, delete, update frontmatter, or create.

    WHEN TO USE: User wants to perform the same operation on many notes at once.
    Move files to a folder, add/remove tags, bulk delete, update frontmatter fields,
    or create multiple notes.

    WHEN NOT TO USE: For single-note operations (use obsidian_manage_notes). For
    searching/finding notes (use obsidian_query_vault). For folder operations
    (use obsidian_manage_folders).

    TARGETING: Use either targets (explicit list of file paths) OR target_pattern
    (glob pattern), not both. Use obsidian_query_vault(action='glob') to preview
    which files match before using target_pattern.

    DRY RUN: Always use dry_run=true first for destructive operations. Shows what
    would happen without making changes.

    SAFETY: Delete requires confirm=true AND dry_run is recommended first.

    COMPOSITION: Use obsidian_query_vault(action='glob') to preview file matches,
    then pass those as targets to this tool.

    Args:
        ctx: Pydantic AI run context with UnifiedDeps.
        action: One of "move", "tag", "delete", "update_frontmatter", "create".
        targets: Explicit list of file paths to operate on.
        target_pattern: Glob pattern to match files (e.g., "projects/*.md").
        destination: Target folder for move action.
        tags: Tags to add/remove for tag action.
        tag_mode: "add" or "remove" for tag action (default "add").
        frontmatter: Key-value pairs for update_frontmatter action.
        items: List of {filepath, content, frontmatter?} dicts for create action.
        confirm: Required true for delete action.
        dry_run: Preview changes without executing (default false).

    Returns:
        JSON string with BulkOperationResult data.
    """
    _settings = ctx.deps.settings
    start_time = time.monotonic()

    logger.info(
        "obsidian.bulk_operations.started",
        action=action,
        target_count=len(targets) if targets else 0,
        dry_run=dry_run,
    )

    # Validate params
    validation_error = _validate_bulk_params(
        action, targets, target_pattern, destination, tags, items, confirm, frontmatter
    )
    if validation_error:
        return validation_error

    if tag_mode not in _VALID_TAG_MODES:
        return f"Invalid tag_mode '{tag_mode}'. Use 'add' or 'remove'."

    # Check vault configured
    if _settings.obsidian_api_key is None:
        return "Obsidian vault is not configured. Set OBSIDIAN_API_KEY environment variable."

    client = ObsidianClient(ctx.deps.obsidian_http_client, _settings.obsidian_vault_url)

    try:
        # Resolve targets
        resolved = await _resolve_targets(client, targets, target_pattern)

        if action == "create" and items is not None:
            result_str = await _handle_bulk_create(client, items, dry_run)
        elif not resolved:
            result = BulkOperationResult(
                dry_run=dry_run,
                action=action,
                matched=0,
                hint="No files matched the targets or pattern. Use obsidian_query_vault to verify paths.",
            )
            result_str = json.dumps(result.model_dump(), ensure_ascii=False)
        elif action == "move" and destination is not None:
            result_str = await _handle_bulk_move(client, resolved, destination, dry_run)
        elif action == "tag" and tags is not None:
            result_str = await _handle_bulk_tag(client, resolved, tags, tag_mode, dry_run)
        elif action == "delete":
            result_str = await _handle_bulk_delete(client, resolved, dry_run)
        elif action == "update_frontmatter" and frontmatter is not None:
            result_str = await _handle_bulk_update_frontmatter(
                client, resolved, frontmatter, dry_run
            )
        else:
            return "Unexpected parameter combination."

        duration_ms = int((time.monotonic() - start_time) * 1000)
        logger.info(
            "obsidian.bulk_operations.completed",
            action=action,
            matched=len(resolved) if action != "create" else (len(items) if items else 0),
            dry_run=dry_run,
            duration_ms=duration_ms,
        )
        return result_str

    except Exception as e:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        logger.error(
            "obsidian.bulk_operations.failed",
            exc_info=True,
            action=action,
            error=str(e),
            error_type=type(e).__name__,
            duration_ms=duration_ms,
        )
        return f"Bulk operation failed: {e}"


async def _handle_bulk_move(
    client: ObsidianClient,
    targets: list[str],
    destination: str,
    dry_run: bool,
) -> str:
    """Move multiple files to a destination folder."""
    if dry_run:
        preview = [
            {"from": t, "to": f"{destination.rstrip('/')}/{t.rsplit('/', 1)[-1]}"} for t in targets
        ]
        result = BulkOperationResult(
            dry_run=True, action="move", matched=len(targets), preview=preview
        )
        return json.dumps(result.model_dump(), ensure_ascii=False)

    succeeded = 0
    failures: list[dict[str, str]] = []
    for target in targets:
        filename = target.rsplit("/", 1)[-1]
        new_path = f"{destination.rstrip('/')}/{filename}"
        try:
            content = await client.get_note(target)
            await client.put_note(new_path, content)
            await client.delete_note(target)
            succeeded += 1
        except (httpx.HTTPStatusError, httpx.ConnectError) as e:
            failures.append({"path": target, "error": str(e)})

    result = BulkOperationResult(
        dry_run=False,
        action="move",
        matched=len(targets),
        succeeded=succeeded,
        failed=len(failures),
        failures=failures,
    )
    return json.dumps(result.model_dump(), ensure_ascii=False)


async def _handle_bulk_tag(
    client: ObsidianClient,
    targets: list[str],
    tags: list[str],
    tag_mode: str,
    dry_run: bool,
) -> str:
    """Add or remove tags from multiple notes."""
    if dry_run:
        preview = [{"path": t, "action": f"{tag_mode} tags: {', '.join(tags)}"} for t in targets]
        result = BulkOperationResult(
            dry_run=True, action="tag", matched=len(targets), preview=preview
        )
        return json.dumps(result.model_dump(), ensure_ascii=False)

    succeeded = 0
    failures: list[dict[str, str]] = []
    for target in targets:
        try:
            content = await client.get_note(target)
            fm_dict, body = _parse_frontmatter(content)

            existing_tags: list[str] = []
            raw_tags = fm_dict.get("tags")
            if isinstance(raw_tags, list):
                existing_tags = raw_tags
            elif isinstance(raw_tags, str):
                existing_tags = [raw_tags]

            if tag_mode == "add":
                updated_tags = list(set(existing_tags + tags))
            else:
                updated_tags = [t for t in existing_tags if t not in tags]

            fm_dict["tags"] = updated_tags
            new_content = _serialize_frontmatter(fm_dict) + "\n" + body
            await client.put_note(target, new_content)
            succeeded += 1
        except (httpx.HTTPStatusError, httpx.ConnectError) as e:
            failures.append({"path": target, "error": str(e)})

    result = BulkOperationResult(
        dry_run=False,
        action="tag",
        matched=len(targets),
        succeeded=succeeded,
        failed=len(failures),
        failures=failures,
    )
    return json.dumps(result.model_dump(), ensure_ascii=False)


async def _handle_bulk_delete(
    client: ObsidianClient,
    targets: list[str],
    dry_run: bool,
) -> str:
    """Delete multiple notes."""
    if dry_run:
        preview = [{"path": t, "action": "delete"} for t in targets]
        result = BulkOperationResult(
            dry_run=True, action="delete", matched=len(targets), preview=preview
        )
        return json.dumps(result.model_dump(), ensure_ascii=False)

    succeeded = 0
    failures: list[dict[str, str]] = []
    for target in targets:
        try:
            await client.delete_note(target)
            succeeded += 1
        except (httpx.HTTPStatusError, httpx.ConnectError) as e:
            failures.append({"path": target, "error": str(e)})

    result = BulkOperationResult(
        dry_run=False,
        action="delete",
        matched=len(targets),
        succeeded=succeeded,
        failed=len(failures),
        failures=failures,
    )
    return json.dumps(result.model_dump(), ensure_ascii=False)


async def _handle_bulk_update_frontmatter(
    client: ObsidianClient,
    targets: list[str],
    frontmatter: dict[str, str | list[str] | int | float | bool | None],
    dry_run: bool,
) -> str:
    """Update frontmatter fields on multiple notes."""
    if dry_run:
        preview = [
            {"path": t, "action": f"update frontmatter: {list(frontmatter.keys())}"}
            for t in targets
        ]
        result = BulkOperationResult(
            dry_run=True, action="update_frontmatter", matched=len(targets), preview=preview
        )
        return json.dumps(result.model_dump(), ensure_ascii=False)

    succeeded = 0
    failures: list[dict[str, str]] = []
    for target in targets:
        try:
            content = await client.get_note(target)
            fm_dict, body = _parse_frontmatter(content)

            for key, value in frontmatter.items():
                if value is None:
                    fm_dict.pop(key, None)
                elif isinstance(value, list):
                    fm_dict[key] = value
                else:
                    fm_dict[key] = str(value)

            new_content = _serialize_frontmatter(fm_dict) + "\n" + body
            await client.put_note(target, new_content)
            succeeded += 1
        except (httpx.HTTPStatusError, httpx.ConnectError) as e:
            failures.append({"path": target, "error": str(e)})

    result = BulkOperationResult(
        dry_run=False,
        action="update_frontmatter",
        matched=len(targets),
        succeeded=succeeded,
        failed=len(failures),
        failures=failures,
    )
    return json.dumps(result.model_dump(), ensure_ascii=False)


async def _handle_bulk_create(
    client: ObsidianClient,
    items: list[dict[str, str | dict[str, str | list[str] | int | float | bool | None] | None]],
    dry_run: bool,
) -> str:
    """Create multiple notes from items list."""
    if dry_run:
        preview = [{"path": str(item.get("filepath", "")), "action": "create"} for item in items]
        result = BulkOperationResult(
            dry_run=True, action="create", matched=len(items), preview=preview
        )
        return json.dumps(result.model_dump(), ensure_ascii=False)

    succeeded = 0
    failures: list[dict[str, str]] = []
    for item in items:
        filepath = str(item.get("filepath", ""))
        content = str(item.get("content", ""))
        fm = item.get("frontmatter")

        if fm is not None and isinstance(fm, dict):
            content = _serialize_frontmatter(fm) + "\n" + content

        try:
            _validate_path(filepath)
            await client.put_note(filepath, content)
            succeeded += 1
        except (httpx.HTTPStatusError, httpx.ConnectError, ValueError) as e:
            failures.append({"path": filepath, "error": str(e)})

    result = BulkOperationResult(
        dry_run=False,
        action="create",
        matched=len(items),
        succeeded=succeeded,
        failed=len(failures),
        failures=failures,
    )
    return json.dumps(result.model_dump(), ensure_ascii=False)
