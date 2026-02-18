"""Obsidian tool: obsidian_manage_notes.

CRUD operations and move for individual notes in the Obsidian vault.
"""

from __future__ import annotations

import json
import re
import time

import httpx
from pydantic_ai import RunContext

from app.core.agents.tools.obsidian.client import ObsidianClient, _validate_path
from app.core.agents.tools.obsidian.schemas import NoteContent, NoteOperationResult
from app.core.agents.tools.transit.deps import UnifiedDeps
from app.core.logging import get_logger

logger = get_logger(__name__)

_VALID_ACTIONS = ("create", "read", "update", "delete", "move")
_VALID_MODES = ("append", "prepend", "replace_section", "replace_all", "patch_frontmatter")


def _serialize_frontmatter(
    frontmatter: dict[str, str | list[str] | int | float | bool | None],
) -> str:
    """Serialize a frontmatter dict to YAML front matter block.

    Args:
        frontmatter: Key-value pairs for front matter.

    Returns:
        YAML front matter string with --- delimiters.
    """
    lines: list[str] = ["---"]
    for key, value in frontmatter.items():
        if value is None:
            continue
        if isinstance(value, bool):
            lines.append(f"{key}: {'true' if value else 'false'}")
        elif isinstance(value, list):
            lines.append(f"{key}:")
            for item in value:
                lines.append(f"  - {item}")
        elif isinstance(value, (int, float)):
            lines.append(f"{key}: {value}")
        else:
            # String value - quote if it contains special YAML chars
            if any(c in str(value) for c in ":#{}[]|>&*!%@`"):
                lines.append(f'{key}: "{value}"')
            else:
                lines.append(f"{key}: {value}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def _parse_frontmatter(
    content: str,
) -> tuple[dict[str, str | list[str] | int | float | bool | None], str]:
    """Parse YAML front matter from note content.

    Args:
        content: Full note markdown content.

    Returns:
        Tuple of (frontmatter dict, body content after front matter).
    """
    fm: dict[str, str | list[str] | int | float | bool | None] = {}
    body = content

    if content.startswith("---\n"):
        end_idx = content.find("\n---\n", 4)
        if end_idx != -1:
            fm_text = content[4:end_idx]
            body = content[end_idx + 5 :]

            current_key: str | None = None
            current_list: list[str] = []

            for line in fm_text.split("\n"):
                list_match = re.match(r"^\s+-\s+(.+)$", line)
                kv_match = re.match(r"^(\w[\w\s-]*?):\s*(.*)$", line)

                if list_match and current_key is not None:
                    current_list.append(list_match.group(1).strip())
                else:
                    if current_key is not None and current_list:
                        fm[current_key] = current_list
                        current_list = []
                        current_key = None

                    if kv_match:
                        key = kv_match.group(1).strip()
                        value = kv_match.group(2).strip().strip('"').strip("'")
                        if not value:
                            current_key = key
                            current_list = []
                        else:
                            fm[key] = value

            if current_key is not None and current_list:
                fm[current_key] = current_list

    return fm, body


def _validate_manage_params(
    action: str,
    filepath: str,
    content: str | None,
    mode: str | None,
    section: str | None,
    new_filepath: str | None,
    confirm: bool,
    frontmatter: dict[str, str | list[str] | int | float | bool | None] | None,
) -> str | None:
    """Validate parameters for manage_notes actions.

    Returns:
        Error message string if invalid, None if valid.
    """
    if action not in _VALID_ACTIONS:
        return (
            f"Invalid action '{action}'. "
            f"Use one of: {', '.join(_VALID_ACTIONS)}. "
            "Example: obsidian_manage_notes(action='read', filepath='notes/meeting.md')"
        )

    try:
        _validate_path(filepath)
    except ValueError:
        return f"Invalid filepath '{filepath}'. Path traversal ('..') is not allowed."

    if action == "create" and content is None:
        return "Action 'create' requires content. Example: obsidian_manage_notes(action='create', filepath='notes/new.md', content='# My Note')"

    if action == "update":
        if mode is None:
            return "Action 'update' requires mode. Use one of: append, prepend, replace_section, replace_all, patch_frontmatter."
        if mode not in _VALID_MODES:
            return f"Invalid mode '{mode}'. Use one of: {', '.join(_VALID_MODES)}."
        if mode == "replace_section" and (section is None or content is None):
            return "Mode 'replace_section' requires both section and content parameters."
        if mode == "patch_frontmatter" and frontmatter is None:
            return "Mode 'patch_frontmatter' requires frontmatter parameter."
        if mode in ("append", "prepend", "replace_all") and content is None:
            return f"Mode '{mode}' requires content parameter."

    if action == "delete" and not confirm:
        return (
            "Delete requires confirm=true to prevent accidental deletion. "
            "Use obsidian_query_vault first to verify the file exists."
        )

    if action == "move" and new_filepath is None:
        return "Action 'move' requires new_filepath parameter."

    if action == "move" and new_filepath is not None:
        try:
            _validate_path(new_filepath)
        except ValueError:
            return f"Invalid new_filepath '{new_filepath}'. Path traversal ('..') is not allowed."

    return None


async def obsidian_manage_notes(
    ctx: RunContext[UnifiedDeps],
    action: str,
    filepath: str,
    content: str | None = None,
    frontmatter: dict[str, str | list[str] | int | float | bool | None] | None = None,
    mode: str | None = None,
    section: str | None = None,
    new_filepath: str | None = None,
    create_dirs: bool = True,
    confirm: bool = False,
) -> str:
    """Work with a specific note - create, read, update, delete, or move.

    WHEN TO USE: User wants to create a new note, read a specific note's content,
    update/append to a note, delete a note, or move a note to a different location.

    WHEN NOT TO USE: For searching/finding notes (use obsidian_query_vault). For
    batch operations on multiple notes (use obsidian_bulk_operations). For folder
    operations (use obsidian_manage_folders).

    ACTIONS:
    - "create": Create a new note with content and optional frontmatter.
    - "read": Read a note's full content. Use section param for just one heading.
    - "update": Modify a note. Requires mode (append/prepend/replace_section/replace_all/patch_frontmatter).
    - "delete": Delete a note. Requires confirm=true.
    - "move": Move/rename a note. Requires new_filepath.

    EFFICIENCY: Use section param with "read" to get only one heading's content.

    SAFETY: Delete requires confirm=true. Use obsidian_query_vault first to verify
    the file exists before deleting.

    COMPOSITION: Find notes with obsidian_query_vault, then use this tool to
    read/modify them.

    Args:
        ctx: Pydantic AI run context with UnifiedDeps.
        action: One of "create", "read", "update", "delete", "move".
        filepath: Relative path to the note (e.g., "projects/vtv/notes.md").
        content: Note content for create/update operations.
        frontmatter: YAML front matter dict for create or patch_frontmatter mode.
        mode: Update mode - "append", "prepend", "replace_section", "replace_all", "patch_frontmatter".
        section: Heading name to read or replace (e.g., "## Meeting Notes").
        new_filepath: Destination path for move action.
        create_dirs: Auto-create parent directories (default true).
        confirm: Required true for delete action.

    Returns:
        JSON string with NoteContent (read) or NoteOperationResult (create/update/delete/move).
    """
    _settings = ctx.deps.settings
    start_time = time.monotonic()
    # create_dirs is reserved for future directory auto-creation
    _ = create_dirs

    logger.info(
        "obsidian.manage_notes.started",
        action=action,
        filepath=filepath,
    )

    # Validate params
    validation_error = _validate_manage_params(
        action, filepath, content, mode, section, new_filepath, confirm, frontmatter
    )
    if validation_error:
        return validation_error

    # Check vault configured
    if _settings.obsidian_api_key is None:
        return "Obsidian vault is not configured. Set OBSIDIAN_API_KEY environment variable."

    client = ObsidianClient(ctx.deps.obsidian_http_client, _settings.obsidian_vault_url)

    try:
        if action == "create":
            result_str = await _handle_create(client, filepath, content or "", frontmatter)
        elif action == "read":
            result_str = await _handle_read(client, filepath, section)
        elif action == "update":
            result_str = await _handle_update(
                client, filepath, content, mode or "append", section, frontmatter
            )
        elif action == "delete":
            result_str = await _handle_delete(client, filepath)
        elif action == "move" and new_filepath is not None:
            result_str = await _handle_move(client, filepath, new_filepath)
        else:
            return "Unexpected parameter combination."

        duration_ms = int((time.monotonic() - start_time) * 1000)
        logger.info(
            "obsidian.manage_notes.completed",
            action=action,
            filepath=filepath,
            duration_ms=duration_ms,
        )
        return result_str

    except httpx.HTTPStatusError as e:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        logger.error(
            "obsidian.manage_notes.failed",
            action=action,
            filepath=filepath,
            error=str(e),
            error_type=type(e).__name__,
            duration_ms=duration_ms,
        )
        if e.response.status_code == 404:
            return f"Note not found: '{filepath}'. Use obsidian_query_vault(action='search') to find the correct path."
        return f"Vault API error ({e.response.status_code}): {e}"

    except Exception as e:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        logger.error(
            "obsidian.manage_notes.failed",
            exc_info=True,
            action=action,
            filepath=filepath,
            error=str(e),
            error_type=type(e).__name__,
            duration_ms=duration_ms,
        )
        return f"Vault operation failed: {e}"


async def _handle_create(
    client: ObsidianClient,
    filepath: str,
    content: str,
    frontmatter: dict[str, str | list[str] | int | float | bool | None] | None,
) -> str:
    """Create a new note with optional frontmatter."""
    full_content = content
    if frontmatter:
        full_content = _serialize_frontmatter(frontmatter) + "\n" + content

    await client.put_note(filepath, full_content)

    result = NoteOperationResult(
        success=True,
        action="create",
        path=filepath,
        message=f"Note created at '{filepath}'.",
    )
    return json.dumps(result.model_dump(), ensure_ascii=False)


async def _handle_read(
    client: ObsidianClient,
    filepath: str,
    section: str | None,
) -> str:
    """Read a note's content, optionally filtering to a specific section."""
    raw_content = await client.get_note(filepath)

    if section:
        # Extract content under the specified heading
        section_content = _extract_section(raw_content, section)
        if section_content is None:
            return f"Section '{section}' not found in '{filepath}'. Available headings: {_list_headings(raw_content)}"
        display_content = section_content
    else:
        display_content = raw_content

    fm_dict, body = _parse_frontmatter(raw_content)
    word_count = len(body.split())

    title = filepath.rsplit("/", 1)[-1]
    if title.endswith(".md"):
        title = title[:-3]

    result = NoteContent(
        path=filepath,
        title=title,
        content=display_content,
        frontmatter=fm_dict if fm_dict else None,
        word_count=word_count,
    )
    return json.dumps(result.model_dump(), ensure_ascii=False)


async def _handle_update(
    client: ObsidianClient,
    filepath: str,
    content: str | None,
    mode: str,
    section: str | None,
    frontmatter: dict[str, str | list[str] | int | float | bool | None] | None,
) -> str:
    """Update a note with the specified mode."""
    if mode == "append" and content is not None:
        await client.patch_note(filepath, content, mode="append")
    elif mode == "prepend" and content is not None:
        await client.patch_note(filepath, content, mode="prepend")
    elif mode == "replace_all" and content is not None:
        await client.put_note(filepath, content)
    elif mode == "replace_section" and section is not None and content is not None:
        existing = await client.get_note(filepath)
        updated = _replace_section(existing, section, content)
        if updated is None:
            return f"Section '{section}' not found in '{filepath}'. Available headings: {_list_headings(existing)}"
        await client.put_note(filepath, updated)
    elif mode == "patch_frontmatter" and frontmatter is not None:
        existing = await client.get_note(filepath)
        fm_dict, body = _parse_frontmatter(existing)
        for key, value in frontmatter.items():
            if value is None:
                fm_dict.pop(key, None)
            elif isinstance(value, list):
                fm_dict[key] = value
            else:
                fm_dict[key] = str(value)
        new_content = _serialize_frontmatter(fm_dict) + "\n" + body
        await client.put_note(filepath, new_content)
    else:
        return f"Invalid update parameters for mode '{mode}'."

    result = NoteOperationResult(
        success=True,
        action="update",
        path=filepath,
        message=f"Note updated at '{filepath}' (mode: {mode}).",
    )
    return json.dumps(result.model_dump(), ensure_ascii=False)


async def _handle_delete(client: ObsidianClient, filepath: str) -> str:
    """Delete a note."""
    await client.delete_note(filepath)

    result = NoteOperationResult(
        success=True,
        action="delete",
        path=filepath,
        message=f"Note deleted: '{filepath}'.",
    )
    return json.dumps(result.model_dump(), ensure_ascii=False)


async def _handle_move(
    client: ObsidianClient,
    filepath: str,
    new_filepath: str,
) -> str:
    """Move a note by reading, creating at new path, and deleting original."""
    content = await client.get_note(filepath)
    await client.put_note(new_filepath, content)
    await client.delete_note(filepath)

    result = NoteOperationResult(
        success=True,
        action="move",
        path=new_filepath,
        message=f"Note moved from '{filepath}' to '{new_filepath}'.",
    )
    return json.dumps(result.model_dump(), ensure_ascii=False)


def _extract_section(content: str, heading: str) -> str | None:
    """Extract content under a specific heading.

    Args:
        content: Full markdown content.
        heading: Heading text (e.g., "## Meeting Notes").

    Returns:
        Section content or None if heading not found.
    """
    lines = content.split("\n")
    in_section = False
    section_level = 0
    section_lines: list[str] = []

    # Normalize heading - strip leading #
    heading_clean = heading.lstrip("#").strip()

    for line in lines:
        heading_match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading_match:
            level = len(heading_match.group(1))
            title = heading_match.group(2).strip()

            if title.lower() == heading_clean.lower():
                in_section = True
                section_level = level
                section_lines.append(line)
                continue

            if in_section and level <= section_level:
                break

        if in_section:
            section_lines.append(line)

    if not section_lines:
        return None
    return "\n".join(section_lines)


def _replace_section(content: str, heading: str, new_content: str) -> str | None:
    """Replace content under a specific heading.

    Args:
        content: Full markdown content.
        heading: Heading text to find and replace under.
        new_content: New content for the section.

    Returns:
        Updated content or None if heading not found.
    """
    lines = content.split("\n")
    heading_clean = heading.lstrip("#").strip()
    result_lines: list[str] = []
    in_section = False
    section_level = 0
    found = False

    for line in lines:
        heading_match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading_match:
            level = len(heading_match.group(1))
            title = heading_match.group(2).strip()

            if title.lower() == heading_clean.lower():
                in_section = True
                section_level = level
                found = True
                result_lines.append(line)
                result_lines.append(new_content)
                continue

            if in_section and level <= section_level:
                in_section = False

        if not in_section:
            result_lines.append(line)

    if not found:
        return None
    return "\n".join(result_lines)


def _list_headings(content: str) -> str:
    """List all headings in a markdown document.

    Args:
        content: Markdown content.

    Returns:
        Comma-separated list of headings.
    """
    headings: list[str] = []
    for line in content.split("\n"):
        heading_match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading_match:
            headings.append(heading_match.group(0).strip())
    return ", ".join(headings) if headings else "(no headings found)"
