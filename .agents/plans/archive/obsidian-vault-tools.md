# Plan: Obsidian Vault Tools (4 Tools)

## Feature Metadata
**Feature Type**: New Capability
**Estimated Complexity**: High
**Primary Systems Affected**: `app/core/agents/tools/obsidian/`, `app/core/agents/agent.py`, `app/core/agents/service.py`, `app/core/config.py`, `app/core/agents/exceptions.py`

## Feature Description

Add 4 Obsidian vault tools to the VTV AI agent, completing the MVP scope of 9 tools (5 transit + 4 vault). These tools let the agent search, read, write, and batch-manage notes in a user's Obsidian vault via the [Obsidian Local REST API plugin](https://github.com/coddingtonbear/obsidian-local-rest-api).

The tools are: `obsidian_query_vault` (read-only search/discovery), `obsidian_manage_notes` (CRUD on individual notes), `obsidian_manage_folders` (folder operations), and `obsidian_bulk_operations` (batch ops with dry_run). All communicate with `https://127.0.0.1:27124` using a Bearer token, through a shared `ObsidianClient` wrapper built on `httpx.AsyncClient`.

The agent's deps type changes from `TransitDeps` to `UnifiedDeps` (a new dataclass holding both transit and obsidian HTTP clients). This is the main cross-cutting change — it affects `agent.py`, `service.py`, and all 5 existing transit tools (their `RunContext[TransitDeps]` becomes `RunContext[UnifiedDeps]`).

## User Story

As a transit dispatcher or administrator using the AI chat sidebar
I want the agent to search, read, create, and organize notes in my Obsidian vault
So that I can manage operational knowledge without leaving the VTV platform

## Solution Approach

Build a new `app/core/agents/tools/obsidian/` package mirroring the structure of the transit tools. A thin `ObsidianClient` wraps the Obsidian Local REST API (vault CRUD, search). Each tool function delegates to this client, then formats results as JSON strings for the agent.

**Approach Decision:**
We chose a shared `ObsidianClient` class (like `GTFSRealtimeClient`) because:
- All 4 tools hit the same REST API with the same auth and SSL config
- Connection pooling via a single `httpx.AsyncClient` avoids per-request overhead
- Error handling (connection refused, auth failure, not found) is centralized

**Unified Deps:**
The Pydantic AI agent uses a single `deps_type`. We create `UnifiedDeps` containing both HTTP clients and settings. Transit tools access `ctx.deps.transit_http_client`; Obsidian tools access `ctx.deps.obsidian_http_client`. This is a one-time migration — all 5 transit tools get a find-and-replace of `ctx.deps.http_client` → `ctx.deps.transit_http_client`.

**Alternatives Considered:**
- **Two separate agents**: Rejected — PRD explicitly says "one agent, all tools"
- **Obsidian deps as optional field**: Rejected — complicates type checking. `UnifiedDeps` with both clients is cleaner.
- **Direct filesystem access**: Rejected — Obsidian Local REST API handles frontmatter parsing, search indexing, and plugin-aware file management

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, logging patterns, type checking requirements, Python anti-patterns
- `reference/mvp-tool-designs.md` — Full Obsidian tool specs (parameters, responses, error formats, workflows)
- `app/core/config.py` (lines 1-84) — Settings class; add `obsidian_api_key` and `obsidian_vault_url` here
- `app/core/agents/exceptions.py` (lines 1-92) — Exception hierarchy; add `ObsidianError` here

### Pattern Files (Examples to Follow)
- `app/core/agents/tools/transit/deps.py` (lines 1-43) — Deps dataclass + factory; replicate for UnifiedDeps
- `app/core/agents/tools/transit/search_stops.py` (lines 1-60) — Multi-action tool pattern: validation, constants, structured logging, JSON output
- `app/core/agents/tools/transit/client.py` (lines 1-50) — HTTP client wrapper pattern with caching
- `app/core/agents/tools/transit/schemas.py` (lines 1-84) — Pydantic response models with `ConfigDict(strict=True)`

### Files to Modify
- `app/core/config.py` — Add Obsidian settings fields
- `app/core/agents/exceptions.py` — Add `ObsidianError` class + register handler
- `app/core/agents/tools/transit/deps.py` — Replace `TransitDeps` with `UnifiedDeps`
- `app/core/agents/agent.py` — Change deps type, add 4 obsidian tools, update system prompt
- `app/core/agents/service.py` — Change deps type, close both HTTP clients
- `app/main.py` — No changes needed (agent router already registered)
- All 5 transit tool files — Change `RunContext[TransitDeps]` to `RunContext[UnifiedDeps]`
- `.env.example` — Uncomment Obsidian vars

### Files to Create
- `app/core/agents/tools/obsidian/__init__.py`
- `app/core/agents/tools/obsidian/client.py` — ObsidianClient HTTP wrapper
- `app/core/agents/tools/obsidian/schemas.py` — Pydantic response models
- `app/core/agents/tools/obsidian/query_vault.py` — Tool 1
- `app/core/agents/tools/obsidian/manage_notes.py` — Tool 2
- `app/core/agents/tools/obsidian/manage_folders.py` — Tool 3
- `app/core/agents/tools/obsidian/bulk_operations.py` — Tool 4
- `app/core/agents/tools/obsidian/tests/__init__.py`
- `app/core/agents/tools/obsidian/tests/test_client.py`
- `app/core/agents/tools/obsidian/tests/test_query_vault.py`
- `app/core/agents/tools/obsidian/tests/test_manage_notes.py`
- `app/core/agents/tools/obsidian/tests/test_manage_folders.py`
- `app/core/agents/tools/obsidian/tests/test_bulk_operations.py`

## Tool Interfaces

### Tool 1: `obsidian_query_vault`
```python
async def obsidian_query_vault(
    ctx: RunContext[UnifiedDeps],
    action: str,  # "search" | "find_by_tags" | "list" | "recent" | "glob"
    query: str | None = None,
    tags: list[str] | None = None,
    match: str = "all",  # "all" | "any"
    path: str = "/",
    pattern: str | None = None,
    days: int = 7,
    limit: int = 20,
    include_content: bool = False,
    response_format: str = "concise",  # "concise" | "detailed"
    sort_by: str = "modified",  # "modified" | "created" | "name"
) -> str:
```

### Tool 2: `obsidian_manage_notes`
```python
async def obsidian_manage_notes(
    ctx: RunContext[UnifiedDeps],
    action: str,  # "create" | "read" | "update" | "delete" | "move"
    filepath: str,
    content: str | None = None,
    frontmatter: dict[str, str | list[str] | int | float | bool | None] | None = None,
    mode: str | None = None,  # "append" | "prepend" | "replace_section" | "replace_all" | "patch_frontmatter"
    section: str | None = None,
    new_filepath: str | None = None,
    create_dirs: bool = True,
    confirm: bool = False,
) -> str:
```

### Tool 3: `obsidian_manage_folders`
```python
async def obsidian_manage_folders(
    ctx: RunContext[UnifiedDeps],
    action: str,  # "create" | "delete" | "list" | "move"
    path: str,
    new_path: str | None = None,
    depth: int = 1,
    include_files: bool = True,
    include_subfolders: bool = True,
    recursive: bool = False,
    confirm: bool = False,
) -> str:
```

### Tool 4: `obsidian_bulk_operations`
```python
async def obsidian_bulk_operations(
    ctx: RunContext[UnifiedDeps],
    action: str,  # "move" | "tag" | "delete" | "update_frontmatter" | "create"
    targets: list[str] | None = None,
    target_pattern: str | None = None,
    destination: str | None = None,
    tags: list[str] | None = None,
    tag_mode: str = "add",  # "add" | "remove"
    frontmatter: dict[str, str | list[str] | int | float | bool | None] | None = None,
    items: list[dict[str, str | dict[str, str | list[str] | int | float | bool | None] | None]] | None = None,
    confirm: bool = False,
    dry_run: bool = False,
) -> str:
```

## Implementation Plan

### Phase 1: Foundation (Tasks 1-5)
Config, exceptions, unified deps migration, schemas, and the HTTP client.

### Phase 2: Tool Implementation (Tasks 6-9)
The 4 tool functions with full validation, logging, and error handling.

### Phase 3: Agent Integration (Tasks 10-11)
Register tools with agent, update system prompt.

### Phase 4: Testing (Tasks 12-16)
Unit tests for client + 4 tools.

### Phase 5: Transit Tool Migration (Task 17)
Update all 5 transit tools to use `UnifiedDeps`.

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.

---

### Task 1: Add Obsidian Settings to Config
**File:** `app/core/config.py` (modify)
**Action:** UPDATE

Add two fields to the `Settings` class, after the `gtfs_static_cache_ttl_hours` line (line 56):

```python
    # Obsidian Local REST API
    obsidian_api_key: str | None = None
    obsidian_vault_url: str = "https://127.0.0.1:27124"
```

Both have defaults so existing deployments without Obsidian continue to work. `obsidian_api_key = None` means vault tools are disabled (client should check this).

Also update `.env.example` — uncomment the Obsidian vars (lines 40-42):
```bash
# Obsidian Vault
OBSIDIAN_API_KEY=your-obsidian-api-key
OBSIDIAN_VAULT_URL=https://127.0.0.1:27124
```

**Per-task validation:**
- `uv run ruff format app/core/config.py`
- `uv run ruff check --fix app/core/config.py` passes
- `uv run mypy app/core/config.py` passes
- `uv run pyright app/core/config.py` passes

---

### Task 2: Add ObsidianError Exception
**File:** `app/core/agents/exceptions.py` (modify)
**Action:** UPDATE

Add `ObsidianError` after `TransitDataError` (line 41):

```python
class ObsidianError(AgentError):
    """Obsidian vault operation failed (vault unreachable, auth failed, note not found)."""
    pass
```

Add it to the exception handler — map to HTTP 503 (same as TransitDataError). In `agent_exception_handler`, add to the isinstance chain:

```python
    elif isinstance(exc, (TransitDataError, ObsidianError)):
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
```

Add to `setup_agent_exception_handlers`:
```python
    app.add_exception_handler(ObsidianError, handler)
```

**Per-task validation:**
- `uv run ruff format app/core/agents/exceptions.py`
- `uv run ruff check --fix app/core/agents/exceptions.py` passes
- `uv run mypy app/core/agents/exceptions.py` passes

---

### Task 3: Create UnifiedDeps (Replace TransitDeps)
**File:** `app/core/agents/tools/transit/deps.py` (modify)
**Action:** UPDATE

Rename `TransitDeps` to `UnifiedDeps`. Add an `obsidian_http_client` field. Rename `http_client` to `transit_http_client`. Update the factory function.

The file should become:

```python
"""Agent dependency injection types.

Provides UnifiedDeps dataclass injected into all agent tools via RunContext,
and a factory function for creating configured instances.
"""

from dataclasses import dataclass

import httpx

from app.core.config import Settings, get_settings


@dataclass
class UnifiedDeps:
    """Dependencies injected into all agent tools via RunContext.

    Attributes:
        transit_http_client: Connection-pooled async HTTP client for GTFS-RT fetching.
        obsidian_http_client: Async HTTP client for Obsidian Local REST API (SSL verification disabled for self-signed cert).
        settings: Application settings containing feed URLs, cache TTL, and Obsidian config.
    """

    transit_http_client: httpx.AsyncClient
    obsidian_http_client: httpx.AsyncClient
    settings: Settings


# Keep TransitDeps as an alias for backwards compatibility during migration
TransitDeps = UnifiedDeps


def create_unified_deps(settings: Settings | None = None) -> UnifiedDeps:
    """Create UnifiedDeps with configured httpx clients.

    Args:
        settings: Optional settings override. Uses get_settings() if None.

    Returns:
        Configured UnifiedDeps instance.
    """
    if settings is None:
        settings = get_settings()
    transit_client = httpx.AsyncClient(
        timeout=httpx.Timeout(10.0, connect=5.0),
        limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
    )
    obsidian_client = httpx.AsyncClient(
        timeout=httpx.Timeout(10.0, connect=5.0),
        limits=httpx.Limits(max_connections=5, max_keepalive_connections=3),
        verify=False,  # Obsidian Local REST API uses self-signed cert
        headers={"Authorization": f"Bearer {settings.obsidian_api_key or ''}"},
    )
    return UnifiedDeps(
        transit_http_client=transit_client,
        obsidian_http_client=obsidian_client,
        settings=settings,
    )


# Keep old name as alias for backwards compatibility
create_transit_deps = create_unified_deps
```

**CRITICAL:** The aliases `TransitDeps = UnifiedDeps` and `create_transit_deps = create_unified_deps` ensure all existing imports still work. The transit tools currently import `TransitDeps` and `RunContext[TransitDeps]` — these will resolve to `UnifiedDeps` via the alias.

**Per-task validation:**
- `uv run ruff format app/core/agents/tools/transit/deps.py`
- `uv run ruff check --fix app/core/agents/tools/transit/deps.py` passes
- `uv run mypy app/core/agents/tools/transit/deps.py` passes
- `uv run pyright app/core/agents/tools/transit/deps.py` passes

---

### Task 4: Update Transit Tools to Use `transit_http_client`
**Action:** UPDATE (5 files)

In each of the 5 transit tool files, replace `ctx.deps.http_client` with `ctx.deps.transit_http_client`. These are simple find-and-replace operations.

**Files to modify:**
1. `app/core/agents/tools/transit/query_bus_status.py` — all occurrences of `ctx.deps.http_client`
2. `app/core/agents/tools/transit/get_route_schedule.py` — all occurrences
3. `app/core/agents/tools/transit/search_stops.py` — all occurrences
4. `app/core/agents/tools/transit/get_adherence_report.py` — all occurrences
5. `app/core/agents/tools/transit/check_driver_availability.py` — all occurrences

Also update `app/transit/service.py` — the transit REST API service. Replace `self._http_client` usage if it creates `GTFSRealtimeClient(self._http_client, ...)` and `get_static_cache(self._http_client, ...)`. Read the file first to confirm exact patterns.

**Per-task validation:**
- `uv run ruff format app/core/agents/tools/transit/` `app/transit/`
- `uv run ruff check --fix app/core/agents/tools/transit/` `app/transit/` passes
- `uv run mypy app/core/agents/tools/transit/` `app/transit/` passes
- `uv run pytest app/core/agents/tools/transit/tests/ -v` — all 104 tests pass
- `uv run pytest app/transit/tests/ -v` — all 9 tests pass

---

### Task 5: Update Agent Service
**File:** `app/core/agents/service.py` (modify)
**Action:** UPDATE

Change the import and deps creation:
- Replace `from app.core.agents.tools.transit.deps import TransitDeps, create_transit_deps` with `from app.core.agents.tools.transit.deps import UnifiedDeps, create_unified_deps`
- Change `self._deps: TransitDeps = create_transit_deps()` to `self._deps: UnifiedDeps = create_unified_deps()`
- Update `close()` to close both clients:

```python
    async def close(self) -> None:
        """Close HTTP clients used by agent tools."""
        try:
            await self._deps.transit_http_client.aclose()
        except RuntimeError:
            pass
        try:
            await self._deps.obsidian_http_client.aclose()
        except RuntimeError:
            pass
```

**Per-task validation:**
- `uv run ruff format app/core/agents/service.py`
- `uv run ruff check --fix app/core/agents/service.py` passes
- `uv run mypy app/core/agents/service.py` passes

---

### Task 6: Create Obsidian Package and Schemas
**File:** `app/core/agents/tools/obsidian/__init__.py` (create new)
**Action:** CREATE

```python
"""Obsidian vault tools for the VTV AI agent."""
```

**File:** `app/core/agents/tools/obsidian/tests/__init__.py` (create new)
**Action:** CREATE

Empty file.

**File:** `app/core/agents/tools/obsidian/schemas.py` (create new)
**Action:** CREATE

Define Pydantic response models for all 4 tools. Every model uses `model_config = ConfigDict(strict=True)`.

**Models to define:**

```python
from pydantic import BaseModel, ConfigDict

class VaultResultConcise(BaseModel):
    """Concise search result for token efficiency."""
    model_config = ConfigDict(strict=True)
    path: str
    title: str
    modified: str

class VaultResultDetailed(BaseModel):
    """Detailed search result with metadata."""
    model_config = ConfigDict(strict=True)
    path: str
    title: str
    modified: str
    created: str | None = None
    size_bytes: int | None = None
    word_count: int | None = None
    tags: list[str] = []
    frontmatter: dict[str, str | list[str] | int | float | bool | None] | None = None
    snippet: str | None = None

class VaultSearchResponse(BaseModel):
    """Response from obsidian_query_vault."""
    model_config = ConfigDict(strict=True)
    count: int
    results: list[VaultResultConcise | VaultResultDetailed]
    truncated: bool = False
    hint: str | None = None

class NoteContent(BaseModel):
    """Response from reading a note."""
    model_config = ConfigDict(strict=True)
    path: str
    title: str
    content: str
    frontmatter: dict[str, str | list[str] | int | float | bool | None] | None = None
    word_count: int

class NoteOperationResult(BaseModel):
    """Response from create/update/delete/move operations."""
    model_config = ConfigDict(strict=True)
    success: bool
    action: str
    path: str
    message: str

class FolderEntry(BaseModel):
    """A file or folder entry in a directory listing."""
    model_config = ConfigDict(strict=True)
    name: str
    type: str  # "file" | "folder"
    modified: str | None = None
    size_bytes: int | None = None
    item_count: int | None = None
    children: list[FolderEntry] | None = None

class FolderListResponse(BaseModel):
    """Response from folder list operation."""
    model_config = ConfigDict(strict=True)
    path: str
    children: list[FolderEntry]
    total_files: int
    total_folders: int

class BulkOperationResult(BaseModel):
    """Response from bulk operations."""
    model_config = ConfigDict(strict=True)
    dry_run: bool
    action: str
    matched: int
    succeeded: int = 0
    failed: int = 0
    failures: list[dict[str, str]] = []
    preview: list[dict[str, str]] | None = None
    hint: str | None = None

class VaultError(BaseModel):
    """Actionable error response for agent consumption."""
    model_config = ConfigDict(strict=True)
    error: bool = True
    code: str
    message: str
    suggestion: str | None = None
    available_matches: list[str] | None = None
```

Ensure `FolderEntry` model reference is forward-compatible (it references itself for nested children). Use `from __future__ import annotations` at top of file.

**Per-task validation:**
- `uv run ruff format app/core/agents/tools/obsidian/schemas.py`
- `uv run ruff check --fix app/core/agents/tools/obsidian/schemas.py` passes
- `uv run mypy app/core/agents/tools/obsidian/schemas.py` passes
- `uv run pyright app/core/agents/tools/obsidian/schemas.py` passes

---

### Task 7: Create ObsidianClient
**File:** `app/core/agents/tools/obsidian/client.py` (create new)
**Action:** CREATE

A thin HTTP wrapper around the Obsidian Local REST API. Encapsulates auth, SSL, error handling, and path sandboxing.

**Class: `ObsidianClient`**

Constructor:
```python
def __init__(self, http_client: httpx.AsyncClient, vault_url: str) -> None:
```

**Methods:**

```python
async def search(self, query: str, path: str | None = None) -> list[dict[str, str | int | float | None]]:
    """Full-text search via POST /search/simple/."""

async def get_note(self, filepath: str) -> str:
    """Read note content via GET /vault/{filepath}."""

async def put_note(self, filepath: str, content: str) -> None:
    """Create or overwrite note via PUT /vault/{filepath}."""

async def patch_note(self, filepath: str, content: str, mode: str = "append") -> None:
    """Partial update via PATCH /vault/{filepath} with X-Heading or Content-Insertion-Position headers."""

async def delete_note(self, filepath: str) -> None:
    """Delete note via DELETE /vault/{filepath}."""

async def list_directory(self, path: str = "/") -> list[dict[str, str | int | None]]:
    """List directory contents via GET /vault/ with Accept: application/json."""
```

**Path sandboxing:** Every method MUST call `_validate_path(filepath)` before making HTTP requests. This function rejects paths containing `..` or starting with `/`.

```python
def _validate_path(path: str) -> str:
    """Sanitize and validate vault path.

    Args:
        path: Relative path within the vault.

    Returns:
        Cleaned path string.

    Raises:
        ValueError: If path contains directory traversal.
    """
    if ".." in path:
        msg = f"Path traversal not allowed: '{path}'"
        raise ValueError(msg)
    return path.lstrip("/")
```

**Error handling:** Wrap `httpx.HTTPStatusError` and `httpx.ConnectError` into descriptive strings. Do NOT raise `ObsidianError` from the client — let the tool functions handle it. Return error dicts that tools can format for the agent.

**Structured logging:**
- `obsidian.client.request_started` — method, path
- `obsidian.client.request_completed` — method, path, status_code, duration_ms
- `obsidian.client.request_failed` — method, path, error, error_type

**Per-task validation:**
- `uv run ruff format app/core/agents/tools/obsidian/client.py`
- `uv run ruff check --fix app/core/agents/tools/obsidian/client.py` passes
- `uv run mypy app/core/agents/tools/obsidian/client.py` passes
- `uv run pyright app/core/agents/tools/obsidian/client.py` passes

---

### Task 8: Implement `obsidian_query_vault`
**File:** `app/core/agents/tools/obsidian/query_vault.py` (create new)
**Action:** CREATE

Read-only search/discovery tool. Follow the pattern from `search_stops.py`.

**Constants:**
```python
_VALID_ACTIONS = ("search", "find_by_tags", "list", "recent", "glob")
_VALID_FORMATS = ("concise", "detailed")
_VALID_SORT = ("modified", "created", "name")
_VALID_MATCH = ("all", "any")
_DEFAULT_LIMIT = 20
_MAX_LIMIT = 100
_DEFAULT_DAYS = 7
```

**Function signature:** As defined in Tool Interfaces section above.

**Agent-optimized docstring must include:**
1. WHEN TO USE — "Find, search, and discover content in the vault"
2. WHEN NOT TO USE — "Don't use for modifying notes (use obsidian_manage_notes) or batch operations (use obsidian_bulk_operations)"
3. ACTIONS with brief descriptions
4. EFFICIENCY tips — "Use response_format='concise' to save tokens. Only set include_content=true when you need full note text."
5. COMPOSITION — "Chain with obsidian_manage_notes(action='read') to get full content of a found note."
6. Return type — "JSON string with count, results, truncated flag, and optional hint"

**Implementation flow:**
1. Reference ctx: `_settings = ctx.deps.settings`
2. Validate action, format, sort, match params — return error string if invalid
3. Check `_settings.obsidian_api_key` is not None — return error if vault not configured
4. Clamp limit to 1-100
5. Create `ObsidianClient(ctx.deps.obsidian_http_client, _settings.obsidian_vault_url)`
6. Dispatch to action handler
7. Build response model, serialize to JSON, return

**Action handlers** (private functions):
- `_handle_search` — calls `client.search(query)`, filters by path
- `_handle_find_by_tags` — calls `client.search()`, filters results by tag intersection
- `_handle_list` — calls `client.list_directory(path)`, converts to results
- `_handle_recent` — calls `client.list_directory("/")` recursively, filters by date within `days`
- `_handle_glob` — calls `client.list_directory("/")` recursively, matches with `fnmatch`

**Error handling:** Catch `httpx.ConnectError` and `ValueError` (from path validation). Return descriptive error strings, not exceptions.

**Per-task validation:**
- `uv run ruff format app/core/agents/tools/obsidian/query_vault.py`
- `uv run ruff check --fix app/core/agents/tools/obsidian/query_vault.py` passes
- `uv run mypy app/core/agents/tools/obsidian/query_vault.py` passes
- `uv run pyright app/core/agents/tools/obsidian/query_vault.py` passes

---

### Task 9: Implement `obsidian_manage_notes`
**File:** `app/core/agents/tools/obsidian/manage_notes.py` (create new)
**Action:** CREATE

CRUD + move for individual notes.

**Constants:**
```python
_VALID_ACTIONS = ("create", "read", "update", "delete", "move")
_VALID_MODES = ("append", "prepend", "replace_section", "replace_all", "patch_frontmatter")
```

**Agent-optimized docstring must include:**
1. WHEN TO USE — "Work with a specific note - create, read, update, delete, or move"
2. ACTIONS — list each with 1-line description
3. EFFICIENCY — "Use section param for read to get only one heading's content"
4. SAFETY — "Delete requires confirm=true. Use obsidian_query_vault first to verify the file exists."
5. COMPOSITION — "Find notes with obsidian_query_vault, then use this tool to read/modify them."

**Validation function** `_validate_manage_params(...)` — returns error string or None:
- `create` requires `content`
- `update` requires `mode` and (`content` or `frontmatter` for patch_frontmatter)
- `replace_section` requires `section` and `content`
- `delete` requires `confirm=True`
- `move` requires `new_filepath`
- All actions validate filepath with `_validate_path()`

**Action handlers:**
- `_handle_create` — `client.put_note(filepath, content_with_frontmatter)`. Fail if exists (check first with GET, expect 404).
- `_handle_read` — `client.get_note(filepath)`. If `section` is provided, extract only that heading's content.
- `_handle_update` — dispatch by mode. `append`/`prepend`: read current, modify, write back. `replace_section`: parse headings, replace target section. `replace_all`: `client.put_note()`. `patch_frontmatter`: read, parse YAML, merge, write back.
- `_handle_delete` — `client.delete_note(filepath)`.
- `_handle_move` — read source, create at destination, delete source.

**Frontmatter handling:** When creating notes with `frontmatter` dict, serialize as YAML front matter block (`---\nkey: value\n---\n`). Use manual YAML serialization (simple key-value pairs) to avoid adding a dependency. Lists serialize as YAML lists, nulls omit the key.

**Per-task validation:**
- `uv run ruff format app/core/agents/tools/obsidian/manage_notes.py`
- `uv run ruff check --fix app/core/agents/tools/obsidian/manage_notes.py` passes
- `uv run mypy app/core/agents/tools/obsidian/manage_notes.py` passes
- `uv run pyright app/core/agents/tools/obsidian/manage_notes.py` passes

---

### Task 10: Implement `obsidian_manage_folders`
**File:** `app/core/agents/tools/obsidian/manage_folders.py` (create new)
**Action:** CREATE

Folder create/delete/list/move operations.

**Constants:**
```python
_VALID_ACTIONS = ("create", "delete", "list", "move")
_DEFAULT_DEPTH = 1
_MAX_DEPTH = 10
```

**Agent-optimized docstring must include:**
1. WHEN TO USE — "Organize vault structure - create, delete, list, or move folders"
2. EFFICIENCY — "Use depth=1 for quick listing. Use depth=-1 for full recursive tree (slow on large vaults)."
3. SAFETY — "Delete requires confirm=true. Non-empty folders require recursive=true."

**Validation function:**
- `delete` requires `confirm=True`
- `move` requires `new_path`
- Validate path with `_validate_path()`

**Action handlers:**
- `_handle_create` — create folder by putting a placeholder `.gitkeep` file or using the Obsidian API folder creation
- `_handle_delete` — list contents first. If non-empty and not recursive, return error. If recursive+confirm, delete all contents then folder.
- `_handle_list` — `client.list_directory(path)`, recurse to `depth` levels, build `FolderListResponse`
- `_handle_move` — create destination, move all contents, delete source

**Per-task validation:**
- `uv run ruff format app/core/agents/tools/obsidian/manage_folders.py`
- `uv run ruff check --fix app/core/agents/tools/obsidian/manage_folders.py` passes
- `uv run mypy app/core/agents/tools/obsidian/manage_folders.py` passes
- `uv run pyright app/core/agents/tools/obsidian/manage_folders.py` passes

---

### Task 11: Implement `obsidian_bulk_operations`
**File:** `app/core/agents/tools/obsidian/bulk_operations.py` (create new)
**Action:** CREATE

Batch operations with dry_run support.

**Constants:**
```python
_VALID_ACTIONS = ("move", "tag", "delete", "update_frontmatter", "create")
_VALID_TAG_MODES = ("add", "remove")
_MAX_TARGETS = 100
```

**Agent-optimized docstring must include:**
1. WHEN TO USE — "Batch operations on multiple notes - move, tag, delete, update frontmatter, or create"
2. TARGETING — "Use either targets (explicit list) OR target_pattern (glob), not both"
3. DRY RUN — "Always recommend dry_run=true first for destructive operations"
4. SAFETY — "Delete requires confirm=true AND dry_run recommended"
5. COMPOSITION — "Use obsidian_query_vault(action='glob') to preview which files match before using target_pattern"

**Implementation flow:**
1. Validate action, targeting (exactly one of targets/target_pattern for non-create actions)
2. If `target_pattern`: resolve glob to file list using `ObsidianClient.list_directory` + fnmatch
3. If `dry_run`: build preview response without executing
4. Execute action on each target with partial failure tolerance
5. Return `BulkOperationResult` as JSON

**Action handlers:**
- `_handle_bulk_move` — move each target to destination folder
- `_handle_bulk_tag` — read each note, parse frontmatter, add/remove tags, write back
- `_handle_bulk_delete` — delete each target (requires confirm)
- `_handle_bulk_update_frontmatter` — read, merge frontmatter, write back
- `_handle_bulk_create` — create each item from `items` list

**Partial failure:** Use a results accumulator. On individual item failure, record `{path, error}` and continue. Return total succeeded/failed counts.

**Per-task validation:**
- `uv run ruff format app/core/agents/tools/obsidian/bulk_operations.py`
- `uv run ruff check --fix app/core/agents/tools/obsidian/bulk_operations.py` passes
- `uv run mypy app/core/agents/tools/obsidian/bulk_operations.py` passes
- `uv run pyright app/core/agents/tools/obsidian/bulk_operations.py` passes

---

### Task 12: Register Tools with Agent
**File:** `app/core/agents/agent.py` (modify)
**Action:** UPDATE

Add imports for the 4 obsidian tools:
```python
from app.core.agents.tools.obsidian.query_vault import obsidian_query_vault
from app.core.agents.tools.obsidian.manage_notes import obsidian_manage_notes
from app.core.agents.tools.obsidian.manage_folders import obsidian_manage_folders
from app.core.agents.tools.obsidian.bulk_operations import obsidian_bulk_operations
```

Change the import: `from app.core.agents.tools.transit.deps import TransitDeps` → `from app.core.agents.tools.transit.deps import UnifiedDeps`

Update `create_agent` return type and deps_type:
```python
def create_agent(model: str | Model | None = None) -> Agent[UnifiedDeps, str]:
```

```python
    return Agent(
        model,
        deps_type=UnifiedDeps,
        output_type=str,
        system_prompt=SYSTEM_PROMPT,
        tools=[
            # Transit (5 read-only)
            query_bus_status,
            get_route_schedule,
            search_stops,
            get_adherence_report,
            check_driver_availability,
            # Obsidian vault (4)
            obsidian_query_vault,
            obsidian_manage_notes,
            obsidian_manage_folders,
            obsidian_bulk_operations,
        ],
    )
```

Update module-level singleton type:
```python
agent: Agent[UnifiedDeps, str] = create_agent()
```

Update `SYSTEM_PROMPT` to mention vault capabilities:
```python
SYSTEM_PROMPT: str = (
    "You are a transit operations and knowledge management assistant "
    "for Riga's municipal bus system (VTV). "
    "You help dispatchers and administrators with transit queries, "
    "schedule information, operational insights, and Obsidian vault management. "
    "You can search, read, create, update, and organize notes in the user's vault. "
    "Be concise, accurate, and helpful. "
    "When you don't have enough information to answer, say so clearly. "
    "For destructive operations (delete), always confirm with the user first."
)
```

**Per-task validation:**
- `uv run ruff format app/core/agents/agent.py`
- `uv run ruff check --fix app/core/agents/agent.py` passes
- `uv run mypy app/core/agents/agent.py` passes

---

### Task 13: Create Client Unit Tests
**File:** `app/core/agents/tools/obsidian/tests/test_client.py` (create new)
**Action:** CREATE

Test `ObsidianClient` methods with mocked httpx responses.

**Test helpers** (all must have return type annotations):
- `_make_client() -> ObsidianClient` — creates client with `MagicMock` httpx client

**Tests (all `@pytest.mark.asyncio`):**

1. `test_search_success` — mock POST `/search/simple/` returning 200 with JSON results. Assert client returns parsed list.
2. `test_get_note_success` — mock GET `/vault/path.md` returning 200 with text content. Assert returns string.
3. `test_get_note_not_found` — mock GET returning 404. Assert raises `httpx.HTTPStatusError`.
4. `test_put_note_success` — mock PUT `/vault/path.md` returning 204. Assert no exception.
5. `test_delete_note_success` — mock DELETE returning 204.
6. `test_list_directory_success` — mock GET `/vault/` returning JSON directory listing.
7. `test_validate_path_traversal` — call `_validate_path("../etc/passwd")`. Assert raises ValueError.
8. `test_validate_path_clean` — call `_validate_path("projects/vtv/note.md")`. Assert returns cleaned path.

**Per-task validation:**
- `uv run ruff format app/core/agents/tools/obsidian/tests/test_client.py`
- `uv run ruff check --fix app/core/agents/tools/obsidian/tests/test_client.py` passes
- `uv run pytest app/core/agents/tools/obsidian/tests/test_client.py -v` — all 8 pass

---

### Task 14: Create `obsidian_query_vault` Tests
**File:** `app/core/agents/tools/obsidian/tests/test_query_vault.py` (create new)
**Action:** CREATE

Test the `obsidian_query_vault` tool function with mocked `ObsidianClient`.

**Mock strategy:** Patch `app.core.agents.tools.obsidian.query_vault.ObsidianClient` — mock `search`, `list_directory` as `AsyncMock`. Create `RunContext` mock with `deps` containing a MagicMock `obsidian_http_client` and mock settings (with `obsidian_api_key="test-key"`, `obsidian_vault_url="https://127.0.0.1:27124"`).

**Tests (all `@pytest.mark.asyncio`):**

1. `test_search_success` — mock search returning 3 results. Call with `action="search", query="test"`. Assert JSON output has `count=3`.
2. `test_search_empty` — mock search returning empty. Assert `count=0`.
3. `test_list_success` — mock list returning folder contents. Call with `action="list", path="projects/"`. Assert results.
4. `test_invalid_action` — call with `action="invalid"`. Assert error string returned (not exception).
5. `test_vault_not_configured` — mock settings with `obsidian_api_key=None`. Assert error string about vault not configured.
6. `test_limit_clamping` — call with `limit=200`. Assert it's clamped to 100 internally.
7. `test_path_traversal_rejected` — call with `path="../etc"`. Assert error string.

**Per-task validation:**
- `uv run ruff format app/core/agents/tools/obsidian/tests/test_query_vault.py`
- `uv run ruff check --fix app/core/agents/tools/obsidian/tests/test_query_vault.py` passes
- `uv run pytest app/core/agents/tools/obsidian/tests/test_query_vault.py -v` — all 7 pass

---

### Task 15: Create `obsidian_manage_notes` Tests
**File:** `app/core/agents/tools/obsidian/tests/test_manage_notes.py` (create new)
**Action:** CREATE

**Tests (all `@pytest.mark.asyncio`):**

1. `test_create_note_success` — mock client, call with `action="create"`. Assert success response.
2. `test_read_note_success` — mock `get_note` returning content. Assert content in response.
3. `test_read_note_section` — mock `get_note` returning multi-section content. Call with `section="Heading"`. Assert only that section returned.
4. `test_update_append` — mock `get_note` + `put_note`. Call with `mode="append"`. Assert `put_note` called with appended content.
5. `test_delete_requires_confirm` — call with `action="delete", confirm=False`. Assert error string about confirm required.
6. `test_delete_success` — call with `confirm=True`. Assert success.
7. `test_move_success` — mock get/put/delete sequence. Assert source deleted, destination created.
8. `test_invalid_action` — assert error string.
9. `test_create_missing_content` — assert error string about content required.

**Per-task validation:**
- `uv run ruff format app/core/agents/tools/obsidian/tests/test_manage_notes.py`
- `uv run ruff check --fix app/core/agents/tools/obsidian/tests/test_manage_notes.py` passes
- `uv run pytest app/core/agents/tools/obsidian/tests/test_manage_notes.py -v` — all 9 pass

---

### Task 16: Create `obsidian_manage_folders` Tests
**File:** `app/core/agents/tools/obsidian/tests/test_manage_folders.py` (create new)
**Action:** CREATE

**Tests (all `@pytest.mark.asyncio`):**

1. `test_create_folder_success` — assert success response.
2. `test_list_folder_success` — mock directory listing. Assert `FolderListResponse` structure in JSON.
3. `test_list_folder_with_depth` — assert depth parameter respected.
4. `test_delete_requires_confirm` — assert error without confirm.
5. `test_delete_non_empty_requires_recursive` — mock non-empty folder. Assert error about recursive.
6. `test_move_success` — assert success.
7. `test_invalid_action` — assert error string.

**Per-task validation:**
- `uv run ruff format app/core/agents/tools/obsidian/tests/test_manage_folders.py`
- `uv run ruff check --fix app/core/agents/tools/obsidian/tests/test_manage_folders.py` passes
- `uv run pytest app/core/agents/tools/obsidian/tests/test_manage_folders.py -v` — all 7 pass

---

### Task 17: Create `obsidian_bulk_operations` Tests
**File:** `app/core/agents/tools/obsidian/tests/test_bulk_operations.py` (create new)
**Action:** CREATE

**Tests (all `@pytest.mark.asyncio`):**

1. `test_move_dry_run` — call with `dry_run=True`. Assert preview response without side effects.
2. `test_move_execute` — call with `dry_run=False`. Assert files moved.
3. `test_tag_add_success` — mock 3 notes, add tags. Assert all succeeded.
4. `test_delete_requires_confirm` — assert error without confirm.
5. `test_delete_dry_run` — assert preview without deletion.
6. `test_partial_failure` — mock 3 targets, 1 fails. Assert `succeeded=2, failed=1, failures=[...]`.
7. `test_create_batch` — provide `items` list. Assert all created.
8. `test_targeting_mutual_exclusion` — provide both `targets` and `target_pattern`. Assert error.
9. `test_invalid_action` — assert error string.

**Per-task validation:**
- `uv run ruff format app/core/agents/tools/obsidian/tests/test_bulk_operations.py`
- `uv run ruff check --fix app/core/agents/tools/obsidian/tests/test_bulk_operations.py` passes
- `uv run pytest app/core/agents/tools/obsidian/tests/test_bulk_operations.py -v` — all 9 pass

---

## Migration

Not applicable — no database tables. All Obsidian data is stored in the vault, accessed via REST API.

## Logging Events

- `obsidian.client.request_started` — HTTP request to vault API (method, path)
- `obsidian.client.request_completed` — successful response (status_code, duration_ms)
- `obsidian.client.request_failed` — HTTP error (error, error_type, duration_ms)
- `obsidian.query_vault.started` — tool invoked (action, query, path)
- `obsidian.query_vault.completed` — results returned (action, count, duration_ms)
- `obsidian.query_vault.failed` — error (action, error, error_type, duration_ms)
- `obsidian.manage_notes.started` — note operation (action, filepath)
- `obsidian.manage_notes.completed` — success (action, filepath, duration_ms)
- `obsidian.manage_notes.failed` — error (action, filepath, error, duration_ms)
- `obsidian.manage_folders.started` — folder operation (action, path)
- `obsidian.manage_folders.completed` — success (action, path, duration_ms)
- `obsidian.bulk_operations.started` — batch operation (action, target_count, dry_run)
- `obsidian.bulk_operations.completed` — results (action, matched, succeeded, failed, duration_ms)

## Testing Strategy

### Unit Tests
**Location:** `app/core/agents/tools/obsidian/tests/`
- `test_client.py` — HTTP wrapper methods, path validation, error handling (8 tests)
- `test_query_vault.py` — Search, list, recent, glob, validation, config checks (7 tests)
- `test_manage_notes.py` — CRUD, section reads, confirm guards, validation (9 tests)
- `test_manage_folders.py` — Create, list, delete guards, move, validation (7 tests)
- `test_bulk_operations.py` — Dry run, partial failure, targeting, confirm guards (9 tests)

**Total new tests: 40**

### Edge Cases
- Vault not configured (`obsidian_api_key=None`) — returns helpful error, not crash
- Path traversal (`../`) — rejected at validation layer
- Empty search results — returns `count=0, results=[]`
- Delete without confirm — returns actionable error string
- Bulk operation with all failures — returns `succeeded=0, failed=N, failures=[...]`
- Connection refused (Obsidian not running) — returns descriptive error string

## Acceptance Criteria

This feature is complete when:
- [ ] All 4 Obsidian tools registered with the Pydantic AI agent (9 tools total)
- [ ] Agent deps type is `UnifiedDeps` with both transit and obsidian HTTP clients
- [ ] All 5 existing transit tools work unchanged (113 tests pass)
- [ ] Path sandboxing prevents `../` traversal in all tools
- [ ] Delete operations require `confirm=true`
- [ ] Bulk operations support `dry_run=true`
- [ ] Vault-not-configured returns helpful error (not crash)
- [ ] Agent-optimized docstrings on all 4 tools
- [ ] All type checkers pass (mypy + pyright)
- [ ] All tests pass (40 new + 113 existing = 153+ total agent tests)
- [ ] Structured logging follows `obsidian.{component}.{action}_{state}` pattern
- [ ] No type suppressions added (except existing ones)

## Completion Checklist

Before marking this plan as fully executed:
- [ ] All tasks completed in order (1-17)
- [ ] Per-task validations passed
- [ ] Full validation pyramid passed (Levels 1-4)
- [ ] No deviations from plan (or deviations documented with reasons)
- [ ] Ready for `/commit`

## Final Validation (5-Level Pyramid)

Run each level in order — every one must pass with 0 errors:

**Level 1: Syntax & Style**
```bash
uv run ruff format .
uv run ruff check --fix .
```

**Level 2: Type Safety**
```bash
uv run mypy app/
uv run pyright app/
```

**Level 3: Unit Tests (feature-specific)**
```bash
uv run pytest app/core/agents/tools/obsidian/tests/ -v
```

**Level 4: Full Test Suite (unit)**
```bash
uv run pytest -v -m "not integration"
```

**Level 5: Server Validation (if Obsidian running)**
```bash
curl -sk https://127.0.0.1:27124 -H "Authorization: Bearer $OBSIDIAN_API_KEY" | python -m json.tool
```

**Success definition:** Levels 1-4 exit code 0, all tests pass, zero errors or warnings. Level 5 optional.

## Dependencies

- **Shared utilities used:** None from `app/shared/`
- **Core modules used:**
  - `app.core.config.Settings`, `app.core.config.get_settings` — vault URL, API key
  - `app.core.agents.exceptions.ObsidianError` — error propagation (new)
  - `app.core.logging.get_logger` — structured logging
- **New dependencies:** None — `httpx` already installed; YAML frontmatter handled with manual serialization
- **New env vars:** `OBSIDIAN_API_KEY` (string, required for vault tools), `OBSIDIAN_VAULT_URL` (string, default `https://127.0.0.1:27124`)

## Known Pitfalls

The executing agent MUST follow these rules to avoid common errors:

1. **No `assert` in production code** — Ruff S101 forbids assert outside test files. Use conditional checks instead.
2. **No `object` type hints** — Import and use actual types directly.
3. **Mock exceptions must match catch blocks** — If code catches `httpx.ConnectError`, mock with `httpx.ConnectError`, not `Exception`.
4. **No unused imports or variables** — Ruff F401/F841. Only import what you use.
5. **No unnecessary noqa/type-ignore** — Ruff RUF100.
6. **Test helper functions need return type annotations** — e.g., `def _make_ctx() -> MagicMock:`.
7. **No EN DASH in strings** — Use `-` (U+002D), never `–` (U+2013). Watch docstrings and error messages.
8. **`ctx` must be referenced** — Every tool function must use `ctx.deps` (e.g., `_settings = ctx.deps.settings`). Ruff ARG001 flags unused params.
9. **Path sandboxing is CRITICAL** — Every file/folder path from the agent MUST go through `_validate_path()` before any HTTP call. Directory traversal is a security vulnerability.
10. **`httpx.AsyncClient(verify=False)` for Obsidian** — The Local REST API uses a self-signed certificate at `https://127.0.0.1:27124`. Without `verify=False`, all requests fail with SSL errors.
11. **Schema field additions break ALL consumers** — When defining `FolderEntry` with self-referential `children`, use `from __future__ import annotations` for forward references.
12. **`TransitDeps` alias must remain** — The alias `TransitDeps = UnifiedDeps` in deps.py is critical. All transit tools import `TransitDeps` — removing it breaks 5 files + 104 tests.
13. **Test `limiter.enabled = False`** — If any test file imports from `app.main`, the slowapi limiter activates. Place all imports first, then `limiter.enabled = False`.
14. **No `type: ignore` in test files** — Use pyright file-level `# pyright: reportArgumentType=false` instead.
15. **Manual YAML frontmatter serialization** — Do NOT add a `python-frontmatter` dependency. Serialize frontmatter as `---\nkey: value\n---\n` manually. Keep it simple: string values, list values as `\n- item`, null values omitted.
16. **Frontmatter dict type must be consistent** — Use `dict[str, str | list[str] | int | float | bool | None]` everywhere. Don't create narrower types that need widening later.

## Notes

- **Obsidian Local REST API must be running** for the tools to work. When `obsidian_api_key` is None, all tools return a helpful error message ("Obsidian vault is not configured. Set OBSIDIAN_API_KEY environment variable.") instead of crashing.
- **No new dependencies** — YAML frontmatter is serialized manually. The Obsidian REST API handles most complexity (search indexing, file watching, plugin integration).
- **Token efficiency** — All tools default to concise output. `include_content=false` and `response_format="concise"` prevent large payloads from consuming the agent's context window.
- **Future: Dataview DQL** — The Obsidian REST API supports Dataview DQL queries. This could power more advanced `find_by_tags` and analytics queries in a future iteration.

## Pre-Implementation Checklist

The executing agent MUST verify before writing any code:
- [ ] Read all files listed in "Relevant Files" section
- [ ] Read `reference/mvp-tool-designs.md` for full tool specifications
- [ ] Understood the `UnifiedDeps` migration strategy (alias-based backwards compatibility)
- [ ] Understood the transit tool pattern (search_stops.py) for validation, logging, JSON output
- [ ] Understood path sandboxing requirements (reject `..` in all file/folder paths)
- [ ] Clear on task execution order (config -> exceptions -> deps -> transit migration -> schemas -> client -> tools -> agent -> tests)
- [ ] Validation commands are executable in this environment
