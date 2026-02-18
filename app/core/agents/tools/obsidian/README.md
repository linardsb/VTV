# Obsidian Vault Tools

Four AI agent tools for managing an Obsidian vault via the Local REST API, enabling the VTV agent to search, create, update, and organize knowledge base content alongside transit operations.

## Key Flows

### Search and Discover (obsidian_query_vault)

1. Validate action, format, sort, match parameters
2. Check vault configuration (API key present)
3. Validate and sanitize path (reject traversal)
4. Dispatch to action handler (search, find_by_tags, list, recent, glob)
5. Sort results by modified/created/name
6. Build concise or detailed response models
7. Return JSON with count, results, truncation hint

### Note CRUD (obsidian_manage_notes)

1. Validate action and required parameters per action
2. Check vault configuration and path safety
3. For reads: fetch note, parse frontmatter, optionally extract section
4. For writes: serialize frontmatter, compose content, PUT via API
5. For updates: support 5 modes (append, prepend, replace_section, replace_all, patch_frontmatter)
6. For deletes: require `confirm=true` safety gate
7. Return JSON with operation result or note content

### Folder Operations (obsidian_manage_folders)

1. Validate action and path parameters
2. Create: PUT a `.gitkeep` placeholder file
3. Delete: check contents, require `recursive=true` for non-empty, require `confirm=true`
4. List: enumerate children with file/folder counts
5. Move: copy all contents recursively, delete originals

### Bulk Operations (obsidian_bulk_operations)

1. Validate action and targeting (explicit list OR glob pattern, not both)
2. Resolve targets from list or glob pattern match
3. Support `dry_run=true` for all actions (preview without side effects)
4. Execute with partial failure tolerance (track succeeded/failed counts)
5. Return detailed results with per-file failure messages

## Business Rules

1. All paths are sandboxed - directory traversal (`..`) is rejected with actionable error
2. Delete operations always require `confirm=true`
3. Bulk operations support `dry_run=true` for previewing changes
4. Result limits: default 20, max 100 for query operations
5. Bulk target limit: max 100 files per operation
6. Frontmatter is parsed/serialized manually (no YAML dependency)
7. Connection requires Obsidian running with Local REST API plugin enabled
8. SSL verification disabled for Obsidian's self-signed certificate

## Integration Points

- **UnifiedDeps** (`tools/transit/deps.py`): Shares the dependency injection dataclass with transit tools. `obsidian_http_client` field provides the configured httpx client.
- **Agent** (`agent.py`): All 4 tools registered alongside 5 transit tools on the unified `Agent[UnifiedDeps, str]`.
- **Config** (`core/config.py`): `obsidian_api_key` and `obsidian_vault_url` settings.
- **Exceptions** (`exceptions.py`): `ObsidianError` maps to HTTP 503 via global handler.

## Tool Interface

| Tool | Actions | Key Parameters |
|------|---------|----------------|
| `obsidian_query_vault` | search, find_by_tags, list, recent, glob | action, query, tags, path, pattern, days, limit, response_format, sort_by |
| `obsidian_manage_notes` | create, read, update, delete, move | action, filepath, content, mode, section, frontmatter, confirm |
| `obsidian_manage_folders` | create, delete, list, move | action, path, new_path, depth, recursive, confirm |
| `obsidian_bulk_operations` | move, tag, delete, update_frontmatter, create | action, targets, target_pattern, destination, tags, tag_mode, frontmatter, items, dry_run, confirm |

## Tests

**Location:** `app/core/agents/tools/obsidian/tests/`

| File | Tests | Coverage |
|------|-------|----------|
| `test_client.py` | 9 | ObsidianClient HTTP methods, path validation |
| `test_query_vault.py` | 13 | All 5 search actions, validation, edge cases |
| `test_manage_notes.py` | 18 | CRUD, frontmatter parsing/serialization, section extraction |
| `test_manage_folders.py` | 11 | Create/delete/list/move, safety gates |
| `test_bulk_operations.py` | 17 | All 5 bulk actions, dry_run, partial failures |
| **Total** | **68** | |
