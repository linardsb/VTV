# VTV Agent Service — MVP Tool Designs

> Obsidian vault tools for the unified AI agent service.
> All tools use the `obsidian_` prefix and follow [Anthropic's tool design guidance](https://www.anthropic.com/engineering/writing-tools-for-agents).

---

## Design Principles

1. **Consolidate related operations** — one tool per domain, not one tool per API call
2. **Token efficiency** — `include_content` defaults to false; `response_format` controls verbosity
3. **Smart defaults** — pagination limits, auto-create parent dirs, sensible sort orders
4. **Actionable errors** — suggest fixes, not just error codes ("Note 'x.md' not found. Did you mean 'y.md'?")
5. **Destructive operation guards** — `confirm: true` required for all deletes
6. **Dry run for bulk** — preview changes before committing

---

## Tool Overview

| Tool | Purpose | Actions | Read/Write |
|------|---------|---------|------------|
| `obsidian_query_vault` | Find & discover | search, find_by_tags, list, recent, glob | Read-only |
| `obsidian_manage_notes` | Note CRUD | create, read, update, delete, move | Read + Write |
| `obsidian_manage_folders` | Folder ops | create, delete, list, move | Read + Write |
| `obsidian_bulk_operations` | Batch ops | move, tag, delete, update_frontmatter, create | Write (with dry_run) |

---

## Tool 1: `obsidian_query_vault`

**Purpose:** All read-only search and discovery operations. Never modifies anything.

**Mental model:** "I need to find something in my vault."

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `action` | enum | Yes | — | `"search"` \| `"find_by_tags"` \| `"list"` \| `"recent"` \| `"glob"` |
| `query` | string | Conditional | — | Search text (for `search`), glob pattern (for `glob`) |
| `tags` | list[string] | Conditional | — | Tags to search for (for `find_by_tags`) |
| `match` | enum | No | `"all"` | `"all"` \| `"any"` — tag matching mode |
| `path` | string | No | `"/"` | Scope search to a specific folder |
| `pattern` | string | Conditional | — | Glob pattern (for `glob` action) |
| `days` | int | No | `7` | Look-back window (for `recent` action) |
| `limit` | int | No | `20` | Max results (1–100) |
| `include_content` | bool | No | `false` | Include full note content in results |
| `response_format` | enum | No | `"concise"` | `"concise"` \| `"detailed"` |
| `sort_by` | enum | No | `"modified"` | `"modified"` \| `"created"` \| `"name"` |

### Action Details

#### `search` — Full-text search across vault
```json
{
  "action": "search",
  "query": "transit schedule optimization",
  "path": "projects/",
  "limit": 10,
  "response_format": "concise"
}
```
Returns matching notes ranked by relevance. `concise` returns paths + titles + match snippets. `detailed` adds frontmatter, tags, word count.

#### `find_by_tags` — Search by frontmatter tags
```json
{
  "action": "find_by_tags",
  "tags": ["vtv", "architecture"],
  "match": "all",
  "limit": 20
}
```
`match: "all"` = notes with ALL specified tags. `match: "any"` = notes with ANY specified tag.

#### `list` — List contents of a path
```json
{
  "action": "list",
  "path": "projects/vtv/",
  "response_format": "detailed"
}
```
Returns direct children of the specified folder. Use `obsidian_manage_folders(action="list")` for depth control.

#### `recent` — Recently modified files
```json
{
  "action": "recent",
  "days": 3,
  "limit": 10,
  "sort_by": "modified"
}
```

#### `glob` — Pattern matching on file paths
```json
{
  "action": "glob",
  "pattern": "daily/2026-02-*.md",
  "include_content": false
}
```

### Response Formats

**Concise** (default — optimized for token efficiency):
```json
{
  "count": 3,
  "results": [
    {"path": "projects/vtv/plan.md", "title": "VTV Master Plan", "modified": "2026-02-11T14:30:00Z"},
    {"path": "projects/vtv/architecture.md", "title": "Architecture Decisions", "modified": "2026-02-10T09:15:00Z"}
  ],
  "truncated": false,
  "hint": null
}
```

**Detailed**:
```json
{
  "count": 3,
  "results": [
    {
      "path": "projects/vtv/plan.md",
      "title": "VTV Master Plan",
      "modified": "2026-02-11T14:30:00Z",
      "created": "2026-02-08T10:00:00Z",
      "size_bytes": 73216,
      "word_count": 12450,
      "tags": ["vtv", "planning", "transit"],
      "frontmatter": {"status": "active", "priority": "high"},
      "snippet": "...unified CMS portal for managing Riga's transit operations..."
    }
  ],
  "truncated": false,
  "hint": null
}
```

**Truncated response** (follows Anthropic guidance on helpful truncation):
```json
{
  "count": 247,
  "results": ["...first 20 results..."],
  "truncated": true,
  "hint": "247 results found, showing first 20. Try narrowing with: path='projects/', or more specific query terms, or find_by_tags for tag-based filtering."
}
```

---

## Tool 2: `obsidian_manage_notes`

**Purpose:** Create, read, update, delete, and move individual notes. One note at a time.

**Mental model:** "I need to work with a specific note."

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `action` | enum | Yes | — | `"create"` \| `"read"` \| `"update"` \| `"delete"` \| `"move"` |
| `filepath` | string | Yes | — | Path relative to vault root (e.g., `"projects/vtv/plan.md"`) |
| `content` | string | Conditional | — | Note content (for `create`, `update`) |
| `frontmatter` | dict | No | `null` | YAML frontmatter fields (for `create`, `patch_frontmatter` mode) |
| `mode` | enum | Conditional | — | Update mode: `"append"` \| `"prepend"` \| `"replace_section"` \| `"replace_all"` \| `"patch_frontmatter"` |
| `section` | string | Conditional | — | Heading name (for `read` section-only or `replace_section` mode) |
| `new_filepath` | string | Conditional | — | Destination path (for `move` action) |
| `create_dirs` | bool | No | `true` | Auto-create parent folders if they don't exist |
| `confirm` | bool | Conditional | `false` | Must be `true` for `delete` action |

### Action Details

#### `create` — Create a new note
```json
{
  "action": "create",
  "filepath": "projects/vtv/meeting-notes/2026-02-11.md",
  "content": "# Meeting Notes — Feb 11\n\nDiscussed tool architecture...",
  "frontmatter": {
    "date": "2026-02-11",
    "tags": ["vtv", "meeting"],
    "status": "draft"
  },
  "create_dirs": true
}
```
- Fails if file already exists (use `update` with `mode: "replace_all"` for overwrite)
- `create_dirs: true` auto-creates `projects/vtv/meeting-notes/` if it doesn't exist
- Frontmatter is serialized as YAML front matter block

#### `read` — Read note content
```json
{
  "action": "read",
  "filepath": "projects/vtv/plan.md"
}
```

**Section-scoped read** (token-efficient — reads only one heading):
```json
{
  "action": "read",
  "filepath": "projects/vtv/plan.md",
  "section": "Architecture Decisions"
}
```
Returns only the content under `## Architecture Decisions` heading until the next heading of equal or higher level.

#### `update` — Modify existing note
```json
{
  "action": "update",
  "filepath": "projects/vtv/plan.md",
  "mode": "append",
  "content": "\n## New Section\n\nAdded during planning session."
}
```

**Update modes:**

| Mode | Behavior |
|------|----------|
| `append` | Add content to end of note |
| `prepend` | Add content after frontmatter, before existing body |
| `replace_section` | Replace content under a specific heading (requires `section` param) |
| `replace_all` | Replace entire note content (destructive — keeps frontmatter if not provided) |
| `patch_frontmatter` | Merge `frontmatter` dict into existing frontmatter (add/update fields, set `null` to remove) |

**Replace a specific section:**
```json
{
  "action": "update",
  "filepath": "projects/vtv/plan.md",
  "mode": "replace_section",
  "section": "Architecture Decisions",
  "content": "## Architecture Decisions\n\nRevised after tool design session..."
}
```

**Patch frontmatter** (merge, don't replace):
```json
{
  "action": "update",
  "filepath": "projects/vtv/plan.md",
  "mode": "patch_frontmatter",
  "frontmatter": {
    "status": "in-progress",
    "reviewed_by": "dispatcher-team",
    "old_field": null
  }
}
```
Sets `status` and `reviewed_by`, removes `old_field`.

#### `delete` — Delete a note (requires confirmation)
```json
{
  "action": "delete",
  "filepath": "inbox/old-draft.md",
  "confirm": true
}
```
Fails with actionable error if `confirm` is not `true`: "Delete requires confirm: true. This permanently removes 'inbox/old-draft.md'."

#### `move` — Move or rename a note
```json
{
  "action": "move",
  "filepath": "inbox/vtv-notes.md",
  "new_filepath": "projects/vtv/notes.md",
  "create_dirs": true
}
```
Auto-creates destination directories. Fails if destination already exists.

### Error Response Format

```json
{
  "error": true,
  "code": "NOT_FOUND",
  "message": "Note 'projects/vtv/plann.md' not found.",
  "suggestion": "Did you mean 'projects/vtv/plan.md'? Use obsidian_query_vault(action='search', query='plan') to find notes.",
  "available_matches": ["projects/vtv/plan.md", "projects/vtv/planning-notes.md"]
}
```

---

## Tool 3: `obsidian_manage_folders`

**Purpose:** Create, delete, list, and move folders.

**Mental model:** "I need to organize my vault structure."

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `action` | enum | Yes | — | `"create"` \| `"delete"` \| `"list"` \| `"move"` |
| `path` | string | Yes | — | Folder path relative to vault root |
| `new_path` | string | Conditional | — | Destination path (for `move` action) |
| `depth` | int | No | `1` | Directory listing depth (`1` = direct children, `-1` = full recursive tree) |
| `include_files` | bool | No | `true` | Include files in listing |
| `include_subfolders` | bool | No | `true` | Include subfolders in listing |
| `recursive` | bool | No | `false` | Allow deleting non-empty folders |
| `confirm` | bool | Conditional | `false` | Must be `true` for `delete` action |

### Action Details

#### `create` — Create folder (nested, like `mkdir -p`)
```json
{
  "action": "create",
  "path": "projects/vtv/meeting-notes/2026"
}
```
Creates all intermediate directories. No-op if folder already exists.

#### `delete` — Delete folder
```json
{
  "action": "delete",
  "path": "archive/old-project",
  "recursive": true,
  "confirm": true
}
```
- `recursive: false` (default) — fails if folder is not empty
- `recursive: true` — deletes folder and all contents
- Always requires `confirm: true`

Error if non-empty without recursive:
```json
{
  "error": true,
  "code": "FOLDER_NOT_EMPTY",
  "message": "Folder 'archive/old-project' contains 15 files and 3 subfolders. Set recursive: true to delete all contents, or use obsidian_bulk_operations to selectively remove items first."
}
```

#### `list` — List folder contents with depth control
```json
{
  "action": "list",
  "path": "projects/",
  "depth": 2,
  "include_files": true,
  "include_subfolders": true
}
```

**Response:**
```json
{
  "path": "projects/",
  "children": [
    {"name": "vtv/", "type": "folder", "children": [
      {"name": "plan.md", "type": "file", "modified": "2026-02-11T14:30:00Z", "size_bytes": 73216},
      {"name": "architecture.md", "type": "file", "modified": "2026-02-10T09:15:00Z", "size_bytes": 4096},
      {"name": "meeting-notes/", "type": "folder", "item_count": 8}
    ]},
    {"name": "personal/", "type": "folder", "item_count": 23}
  ],
  "total_files": 10,
  "total_folders": 3
}
```

`depth: 1` = direct children only (fast, focused). `depth: -1` = full recursive tree (use with caution on large vaults).

#### `move` — Move or rename folder
```json
{
  "action": "move",
  "path": "inbox/vtv-stuff",
  "new_path": "projects/vtv"
}
```

---

## Tool 4: `obsidian_bulk_operations`

**Purpose:** Batch operations on multiple notes/folders. Supports dry run for safe preview.

**Mental model:** "I need to do something to many items at once."

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `action` | enum | Yes | — | `"move"` \| `"tag"` \| `"delete"` \| `"update_frontmatter"` \| `"create"` |
| `targets` | list[string] | Conditional | — | Explicit list of file/folder paths |
| `target_pattern` | string | Conditional | — | Glob pattern as alternative to explicit targets |
| `destination` | string | Conditional | — | Destination folder (for `move` action) |
| `tags` | list[string] | Conditional | — | Tags to add/remove (for `tag` action) |
| `tag_mode` | enum | No | `"add"` | `"add"` \| `"remove"` |
| `frontmatter` | dict | Conditional | — | Fields to merge (for `update_frontmatter`; set value to `null` to remove a field) |
| `items` | list[object] | Conditional | — | Items to create (for `create` action) |
| `confirm` | bool | Conditional | `false` | Must be `true` for `delete` action |
| `dry_run` | bool | No | `false` | Preview changes without applying |

### Targeting

Two mutually exclusive targeting modes. Supply ONE of:

- **`targets`** — explicit list: `["inbox/note1.md", "inbox/note2.md", "inbox/note3.md"]`
- **`target_pattern`** — glob: `"inbox/*.md"` or `"projects/**/draft-*.md"`

### Action Details

#### `move` — Move multiple items to a destination folder
```json
{
  "action": "move",
  "target_pattern": "inbox/*.md",
  "destination": "projects/vtv/",
  "dry_run": true
}
```

**Dry run response:**
```json
{
  "dry_run": true,
  "action": "move",
  "matched": 12,
  "preview": [
    {"from": "inbox/vtv-notes.md", "to": "projects/vtv/vtv-notes.md"},
    {"from": "inbox/architecture.md", "to": "projects/vtv/architecture.md"}
  ],
  "hint": "Set dry_run: false to apply these changes."
}
```

#### `tag` — Add or remove tags from multiple notes
```json
{
  "action": "tag",
  "target_pattern": "projects/vtv/**/*.md",
  "tags": ["vtv", "transit", "active"],
  "tag_mode": "add",
  "dry_run": false
}
```

**Response:**
```json
{
  "dry_run": false,
  "action": "tag",
  "matched": 15,
  "succeeded": 15,
  "failed": 0,
  "tag_mode": "add",
  "tags_applied": ["vtv", "transit", "active"]
}
```

#### `delete` — Delete multiple items
```json
{
  "action": "delete",
  "targets": ["archive/old1.md", "archive/old2.md", "archive/old3.md"],
  "confirm": true,
  "dry_run": true
}
```

Always recommend dry run first for delete. Error without `confirm`:
```json
{
  "error": true,
  "code": "CONFIRM_REQUIRED",
  "message": "Bulk delete requires confirm: true. This would permanently remove 3 items. Recommend running with dry_run: true first."
}
```

#### `update_frontmatter` — Batch update frontmatter fields
```json
{
  "action": "update_frontmatter",
  "target_pattern": "projects/vtv/**/*.md",
  "frontmatter": {
    "project": "vtv",
    "status": "active",
    "deprecated_field": null
  }
}
```
Merges fields into existing frontmatter. Set a field to `null` to remove it.

#### `create` — Batch create multiple notes
```json
{
  "action": "create",
  "items": [
    {
      "filepath": "projects/vtv/routes/route-22.md",
      "content": "# Route 22\n\nCentrs — Jugla",
      "frontmatter": {"type": "route", "route_id": 22}
    },
    {
      "filepath": "projects/vtv/routes/route-7.md",
      "content": "# Route 7\n\nAbrenes iela — Ziepniekkalns",
      "frontmatter": {"type": "route", "route_id": 7}
    }
  ]
}
```

### Response Format (all actions)

```json
{
  "dry_run": false,
  "action": "move",
  "matched": 12,
  "succeeded": 11,
  "failed": 1,
  "failures": [
    {"path": "inbox/locked-file.md", "error": "Permission denied"}
  ],
  "hint": null
}
```

Partial failure tolerance: continues processing remaining items if one fails, reports all failures at the end.

---

## Agent Workflow Examples

### "Organize my project notes"

```
1. obsidian_query_vault(action="search", query="VTV transit", response_format="concise")
   → 12 matching notes

2. obsidian_manage_folders(action="create", path="projects/vtv")
   → Created

3. obsidian_bulk_operations(action="move", targets=[...12 paths...],
                            destination="projects/vtv", dry_run=true)
   → "Would move 12 files to projects/vtv/"

4. obsidian_bulk_operations(action="move", targets=[...],
                            destination="projects/vtv", dry_run=false)
   → "Moved 12 files"

5. obsidian_bulk_operations(action="tag", target_pattern="projects/vtv/*.md",
                            tags=["vtv", "transit"], tag_mode="add")
   → "Added tags to 12 notes"
```

### "Summarize my recent work"

```
1. obsidian_query_vault(action="recent", days=3, limit=10, response_format="concise")
   → 10 paths + titles

2. obsidian_manage_notes(action="read", filepath="daily/2026-02-11.md")
   → Full content

3. obsidian_manage_notes(action="read", filepath="projects/vtv/plan.md",
                         section="Architecture Decisions")
   → Just one section (token-efficient)
```

### "Create a project template"

```
1. obsidian_manage_folders(action="create", path="projects/new-project")
   → Created

2. obsidian_bulk_operations(action="create", items=[
     {filepath: "projects/new-project/README.md", content: "# New Project\n\n..."},
     {filepath: "projects/new-project/tasks.md", content: "# Tasks\n\n- [ ] ..."},
     {filepath: "projects/new-project/notes.md", content: "# Notes\n\n"}
   ])
   → Created 3 notes
```

### "Clean up old inbox notes"

```
1. obsidian_query_vault(action="glob", pattern="inbox/*.md",
                        response_format="detailed", sort_by="modified")
   → 47 notes, oldest first

2. obsidian_bulk_operations(action="delete",
                            target_pattern="inbox/draft-*.md",
                            dry_run=true)
   → "Would delete 23 draft notes"

3. obsidian_bulk_operations(action="delete",
                            target_pattern="inbox/draft-*.md",
                            confirm=true, dry_run=false)
   → "Deleted 23 notes"
```

---

## Implementation Notes

### Backend: Obsidian Local REST API

All tools communicate with Obsidian via the [Local REST API plugin](https://github.com/coddingtonbear/obsidian-local-rest-api):

- Base URL: `https://127.0.0.1:27124`
- Auth: `Bearer {OBSIDIAN_API_KEY}`
- Endpoints: vault file CRUD, search, Dataview DQL queries

### Pydantic AI Integration

Each tool maps to a Pydantic AI tool registered on the `obsidian-agent`:

```python
@obsidian_agent.tool
async def obsidian_query_vault(
    ctx: RunContext[ObsidianDeps],
    action: Literal["search", "find_by_tags", "list", "recent", "glob"],
    query: str | None = None,
    tags: list[str] | None = None,
    # ... other params
) -> str:
    """Find, search, and discover content in the vault. ..."""
```

### Safety Constraints

- `obsidian_query_vault` is strictly read-only
- All delete operations require `confirm: true`
- Bulk operations support `dry_run` for safe preview
- Path sandboxing prevents `../` directory traversal
- No tool can access files outside the configured vault path

### Architecture Reference (from mcp-obsidian)

Patterns adopted from [mcp-obsidian](https://github.com/MarkusPfundstein/mcp-obsidian):

- **Handler registry** — tools registered in a dictionary, not if/elif chains
- **Abstract base class** — `ToolHandler` with `get_tool_description()` + `run_tool()`
- **Closure-based error wrapping** — `_safe_call(f)` pattern for HTTP error handling
- **Partial failure tolerance** — batch ops continue on individual item errors
- **Destructive operation guards** — `confirm` parameter pattern

Improvements over mcp-obsidian:
- `httpx` async instead of synchronous `requests`
- Connection pooling via shared `httpx.AsyncClient`
- `pydantic-settings` for typed configuration
- `dry_run` support for bulk operations
- Response format control (`concise` / `detailed`)
- Section-scoped reads for token efficiency
