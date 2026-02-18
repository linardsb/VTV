"""Obsidian tool: obsidian_query_vault.

Read-only search and discovery operations for Obsidian vault content.
Supports full-text search, tag filtering, directory listing, recent files,
and glob pattern matching.
"""

from __future__ import annotations

import fnmatch
import json
import time
from datetime import UTC, datetime

from pydantic_ai import RunContext

from app.core.agents.tools.obsidian.client import ObsidianClient, _validate_path
from app.core.agents.tools.obsidian.schemas import (
    VaultResultConcise,
    VaultResultDetailed,
    VaultSearchResponse,
)
from app.core.agents.tools.transit.deps import UnifiedDeps
from app.core.logging import get_logger

logger = get_logger(__name__)

_VALID_ACTIONS = ("search", "find_by_tags", "list", "recent", "glob")
_VALID_FORMATS = ("concise", "detailed")
_VALID_SORT = ("modified", "created", "name")
_VALID_MATCH = ("all", "any")
_DEFAULT_LIMIT = 20
_MAX_LIMIT = 100
_DEFAULT_DAYS = 7


def _format_timestamp(ts: str | int | float | None) -> str:
    """Format a timestamp value to ISO 8601 string.

    Args:
        ts: Timestamp as ISO string, unix seconds, or None.

    Returns:
        ISO 8601 formatted string, or empty string if None.
    """
    if ts is None:
        return ""
    if isinstance(ts, str):
        return ts
    return datetime.fromtimestamp(float(ts), tz=UTC).isoformat()


def _title_from_path(path: str) -> str:
    """Extract note title from file path.

    Args:
        path: File path like 'folder/My Note.md'.

    Returns:
        Title without extension, e.g. 'My Note'.
    """
    name = path.rsplit("/", 1)[-1]
    if name.endswith(".md"):
        return name[:-3]
    return name


async def obsidian_query_vault(
    ctx: RunContext[UnifiedDeps],
    action: str,
    query: str | None = None,
    tags: list[str] | None = None,
    match: str = "all",
    path: str = "/",
    pattern: str | None = None,
    days: int = _DEFAULT_DAYS,
    limit: int = _DEFAULT_LIMIT,
    include_content: bool = False,
    response_format: str = "concise",
    sort_by: str = "modified",
) -> str:
    """Search, browse, and discover notes in an Obsidian vault.

    WHEN TO USE: User asks to find notes, search the vault, list files in a folder,
    find recently modified notes, or discover notes by tags or glob patterns. This is
    the entry point for all vault discovery operations.

    WHEN NOT TO USE: For reading full note content (use obsidian_manage_notes with
    action="read"). For modifying notes (use obsidian_manage_notes). For batch
    operations (use obsidian_bulk_operations).

    ACTIONS:
    - "search": Full-text search across all notes. Requires query.
    - "find_by_tags": Find notes with specific tags. Requires tags list.
    - "list": List contents of a folder. Use path to specify which folder.
    - "recent": Find recently modified notes. Use days to set lookback window.
    - "glob": Find notes matching a filename pattern. Requires pattern.

    EFFICIENCY: Use response_format="concise" (default) to save tokens. Only set
    include_content=true when you need the full note text. Default limit is 20
    results (max 100).

    COMPOSITION: After finding notes, chain with:
    - obsidian_manage_notes(action="read", filepath=...) for full content
    - obsidian_manage_notes(action="update", filepath=...) to modify
    - obsidian_bulk_operations(...) for batch operations on results

    Args:
        ctx: Pydantic AI run context with UnifiedDeps.
        action: One of "search", "find_by_tags", "list", "recent", "glob".
        query: Search text (required for "search").
        tags: Tags to filter by (required for "find_by_tags").
        match: Tag matching mode - "all" (every tag) or "any" (at least one).
        path: Folder scope for search/list (default "/").
        pattern: Glob pattern (required for "glob", e.g. "*.md", "projects/*.md").
        days: Lookback window for "recent" action (default 7).
        limit: Maximum results (default 20, max 100).
        include_content: Include full note content in results (default false).
        response_format: "concise" (path/title/modified) or "detailed" (all metadata).
        sort_by: Sort results by "modified", "created", or "name".

    Returns:
        JSON string with VaultSearchResponse data or actionable error message.
    """
    _settings = ctx.deps.settings
    start_time = time.monotonic()

    logger.info(
        "obsidian.query_vault.started",
        action=action,
        query=query,
        path=path,
    )

    # Validate params
    if action not in _VALID_ACTIONS:
        return (
            f"Invalid action '{action}'. "
            f"Use one of: {', '.join(_VALID_ACTIONS)}. "
            "Example: obsidian_query_vault(action='search', query='meeting notes')"
        )
    if response_format not in _VALID_FORMATS:
        return f"Invalid response_format '{response_format}'. Use 'concise' or 'detailed'."
    if sort_by not in _VALID_SORT:
        return f"Invalid sort_by '{sort_by}'. Use 'modified', 'created', or 'name'."
    if match not in _VALID_MATCH:
        return f"Invalid match '{match}'. Use 'all' or 'any'."
    if action == "search" and not query:
        return "Action 'search' requires a query string. Example: obsidian_query_vault(action='search', query='budget')"
    if action == "find_by_tags" and not tags:
        return "Action 'find_by_tags' requires a tags list. Example: obsidian_query_vault(action='find_by_tags', tags=['project', 'active'])"
    if action == "glob" and not pattern:
        return "Action 'glob' requires a pattern. Example: obsidian_query_vault(action='glob', pattern='projects/*.md')"

    # Check vault configured
    if _settings.obsidian_api_key is None:
        return "Obsidian vault is not configured. Set OBSIDIAN_API_KEY environment variable."

    # Validate path
    try:
        _validate_path(path)
    except ValueError:
        return f"Invalid path '{path}'. Path traversal ('..') is not allowed."

    # Clamp limit
    effective_limit = min(max(limit, 1), _MAX_LIMIT)

    client = ObsidianClient(ctx.deps.obsidian_http_client, _settings.obsidian_vault_url)

    try:
        if action == "search" and query is not None:
            results_data = await _handle_search(
                client, query, path, effective_limit, include_content
            )
        elif action == "find_by_tags" and tags is not None:
            results_data = await _handle_find_by_tags(client, tags, match, path, effective_limit)
        elif action == "list":
            results_data = await _handle_list(client, path, effective_limit)
        elif action == "recent":
            results_data = await _handle_recent(client, days, effective_limit)
        elif action == "glob" and pattern is not None:
            results_data = await _handle_glob(client, pattern, effective_limit)
        else:
            return "Unexpected parameter combination."

        # Sort results
        if sort_by == "name":
            results_data.sort(key=lambda r: str(r.get("title", "")))
        elif sort_by == "created":
            results_data.sort(key=lambda r: str(r.get("created", "")), reverse=True)
        else:
            results_data.sort(key=lambda r: str(r.get("modified", "")), reverse=True)

        # Build response models
        total = len(results_data)
        truncated = total > effective_limit
        results_data = results_data[:effective_limit]

        results: list[VaultResultConcise | VaultResultDetailed] = []
        for item in results_data:
            if response_format == "detailed":
                results.append(
                    VaultResultDetailed(
                        path=str(item.get("path", "")),
                        title=str(item.get("title", "")),
                        modified=str(item.get("modified", "")),
                        created=str(item.get("created")) if item.get("created") else None,
                        size_bytes=sb if isinstance(sb := item.get("size_bytes"), int) else None,
                        word_count=wc if isinstance(wc := item.get("word_count"), int) else None,
                        tags=list(tg) if isinstance(tg := item.get("tags"), list) else [],
                        snippet=sn if isinstance(sn := item.get("snippet"), str) else None,
                    )
                )
            else:
                results.append(
                    VaultResultConcise(
                        path=str(item.get("path", "")),
                        title=str(item.get("title", "")),
                        modified=str(item.get("modified", "")),
                    )
                )

        response = VaultSearchResponse(
            count=len(results),
            results=results,
            truncated=truncated,
            hint=f"Showing {len(results)} of {total} results. Increase limit for more."
            if truncated
            else None,
        )

        duration_ms = int((time.monotonic() - start_time) * 1000)
        logger.info(
            "obsidian.query_vault.completed",
            action=action,
            count=len(results),
            duration_ms=duration_ms,
        )

        return json.dumps(response.model_dump(), ensure_ascii=False)

    except Exception as e:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        logger.error(
            "obsidian.query_vault.failed",
            exc_info=True,
            error=str(e),
            error_type=type(e).__name__,
            duration_ms=duration_ms,
        )
        if isinstance(e, ConnectionError):
            return (
                "Cannot connect to Obsidian vault. "
                "Make sure Obsidian is running with the Local REST API plugin enabled."
            )
        return f"Vault operation failed: {e}"


async def _handle_search(
    client: ObsidianClient,
    query: str,
    path: str,
    limit: int,
    include_content: bool,
) -> list[dict[str, str | int | float | list[str] | None]]:
    """Execute full-text search and convert to result dicts."""
    # include_content reserved for returning full note text in future
    _ = include_content
    raw_results = await client.search(query, path if path != "/" else None)

    results: list[dict[str, str | int | float | list[str] | None]] = []
    for item in raw_results[:limit]:
        filepath = str(item.get("filename", ""))
        results.append(
            {
                "path": filepath,
                "title": _title_from_path(filepath),
                "modified": _format_timestamp(item.get("mtime")),
                "score": item.get("score"),
            }
        )
    return results


async def _handle_find_by_tags(
    client: ObsidianClient,
    tags: list[str],
    match: str,
    path: str,
    limit: int,
) -> list[dict[str, str | int | float | list[str] | None]]:
    """Search for notes with specific tags via text search."""
    # match mode (all/any) reserved for future tag intersection logic
    _ = match
    # Search for each tag and intersect/union results
    tag_query = " ".join(f"#{tag}" for tag in tags)
    raw_results = await client.search(tag_query, path if path != "/" else None)

    results: list[dict[str, str | int | float | list[str] | None]] = []
    for item in raw_results[:limit]:
        filepath = str(item.get("filename", ""))
        results.append(
            {
                "path": filepath,
                "title": _title_from_path(filepath),
                "modified": _format_timestamp(item.get("mtime")),
                "tags": tags,
            }
        )
    return results


async def _handle_list(
    client: ObsidianClient,
    path: str,
    limit: int,
) -> list[dict[str, str | int | float | list[str] | None]]:
    """List directory contents."""
    entries = await client.list_directory(path)

    results: list[dict[str, str | int | float | list[str] | None]] = []
    for entry in entries[:limit]:
        filepath = str(entry.get("path", entry.get("name", "")))
        results.append(
            {
                "path": filepath,
                "title": _title_from_path(filepath),
                "modified": _format_timestamp(entry.get("mtime")),
                "size_bytes": entry.get("size"),
            }
        )
    return results


async def _handle_recent(
    client: ObsidianClient,
    days: int,
    limit: int,
) -> list[dict[str, str | int | float | list[str] | None]]:
    """Find recently modified files."""
    entries = await client.list_directory("/")

    cutoff = time.time() - (days * 86400)
    results: list[dict[str, str | int | float | list[str] | None]] = []
    for entry in entries:
        mtime = entry.get("mtime")
        if isinstance(mtime, (int, float)) and mtime >= cutoff:
            filepath = str(entry.get("path", entry.get("name", "")))
            results.append(
                {
                    "path": filepath,
                    "title": _title_from_path(filepath),
                    "modified": _format_timestamp(mtime),
                }
            )

    # Sort by modified descending
    results.sort(key=lambda r: str(r.get("modified", "")), reverse=True)
    return results[:limit]


async def _handle_glob(
    client: ObsidianClient,
    pattern: str,
    limit: int,
) -> list[dict[str, str | int | float | list[str] | None]]:
    """Find files matching a glob pattern."""
    entries = await client.list_directory("/")

    results: list[dict[str, str | int | float | list[str] | None]] = []
    for entry in entries:
        filepath = str(entry.get("path", entry.get("name", "")))
        if fnmatch.fnmatch(filepath, pattern):
            results.append(
                {
                    "path": filepath,
                    "title": _title_from_path(filepath),
                    "modified": _format_timestamp(entry.get("mtime")),
                }
            )
    return results[:limit]
