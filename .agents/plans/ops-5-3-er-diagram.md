# Plan: OPS-5.3 — Database ER Diagram from SQLAlchemy Models

## Context

23 migrations, no diagram, no single place to understand the schema. Onboarding and refactor discussions both need it. Add a `make er-diagram` target that generates a Mermaid ER diagram from SQLAlchemy metadata and writes it to `docs/schema/er.md`. Commit the generated output so it is viewable in GitHub without running the target locally.

## Security Context Assessment

- **CTX-INFRA** — Modifies Makefile and adds a script. No credentials, no Docker changes. Low risk.
- No other contexts apply — no endpoints, no auth, no file uploads, no agent tools, no user input.

## Research Summary

### Model Import Chain
`alembic/env.py` imports model modules to populate `Base.metadata`. Current imports (lines 10–18):
```
app.auth.models, app.drivers.models, app.events.models, app.knowledge.models,
app.schedules.models, app.skills.models, app.stops.models, app.transit.models,
app.vehicles.models
```

**Missing from alembic** (but models exist): `app.fleet.models`, `app.geofences.models`, `app.memory.models`, `app.alerts.models`. The ER script must import ALL 13 model modules.

### All Model Modules (13 files)
| Module | Key Tables |
|--------|-----------|
| `app.auth.models` | `users` |
| `app.drivers.models` | `drivers` |
| `app.events.models` | `operational_events` |
| `app.fleet.models` | `tracked_devices` |
| `app.geofences.models` | `geofences`, `geofence_events` |
| `app.knowledge.models` | `documents`, `tags`, `document_chunks`, `document_tags` |
| `app.memory.models` | `memory_entries` |
| `app.schedules.models` | `agencies`, `routes`, `calendars`, `calendar_dates`, `trips`, `stop_times`, `shapes` |
| `app.skills.models` | `agent_skills` |
| `app.stops.models` | `stops` |
| `app.transit.models` | `vehicle_positions` |
| `app.vehicles.models` | `vehicles`, `maintenance_records` |
| `app.alerts.models` | `alert_rules`, `alert_instances` |

**Total: ~24 tables** (including association table `document_tags`).

### Special Column Types
- `pgvector.Vector(1024)` — `document_chunks.embedding`, `memory_entries.embedding`
- `geoalchemy2.Geometry` — `stops.geom`, `geofences.geometry`
- `JSONB` — `operational_events.goals`, `alert_rules.threshold_config`, `alert_instances.details`, `memory_entries.metadata_json`, `vehicle_positions.obd_data`
- `TimestampMixin` — all models get `created_at`, `updated_at`

### Makefile Conventions
- Script targets use `uv run python scripts/{name}.py`
- Help comments via `## description`
- `.PHONY` declaration on line 1

### Script Conventions
- Standalone Python scripts (no async needed for metadata-only access)
- Existing pattern: `rechunk_documents.py` uses argparse, `seed_admin.py` is minimal
- `scripts/` directory is excluded from pyright scope (`include = ["app"]`)
- Ruff allows `T201` (print) in `scripts/**/*.py`

### Pre-commit Hook Pattern
- Local hooks in `.pre-commit-config.yaml` under `repo: local`
- Custom script hooks: `entry: scripts/pre-commit`, `language: script`, `pass_filenames: false`

## Test Landscape

- No tests exist for scripts — convention is Makefile integration testing
- `app/tests/test_security.py` has script existence checks (`test_backup_script_exists`)
- No existing Mermaid content validation tests
- `docs/schema/` directory does not exist yet

## Type Check Baseline

- **Pyright on `scripts/`**: 187 errors (excluded from CI scope via `include = ["app"]`)
- **Project-wide pyright**: 0 errors — scripts don't affect CI
- New script will NOT regress pyright CI since `scripts/` is out of scope

## Files to Create/Modify

| Action | File | Purpose |
|--------|------|---------|
| CREATE | `scripts/generate_er_diagram.py` | Import all models, walk `Base.metadata.tables`, emit Mermaid `erDiagram` |
| CREATE | `docs/schema/er.md` | Generated output — Mermaid ER diagram |
| UPDATE | `Makefile` | Add `er-diagram` target |
| UPDATE | `alembic/env.py` | Add missing model imports (fleet, geofences, memory, alerts) |

## Implementation Steps

### Step 1: Fix missing model imports in `alembic/env.py`

Add the 4 missing model imports so alembic and the ER script share a consistent model set.

**File:** `alembic/env.py` (after line 18, before the `# noqa` line)

Add imports for:
```python
import app.alerts.models
import app.fleet.models
import app.geofences.models
import app.memory.models
```

Keep alphabetical order among the import block. The existing `app.vehicles.models  # noqa: F401` stays last.

**Validation:** `uv run alembic check` (should report no new migrations needed)

### Step 2: Create `scripts/generate_er_diagram.py`

**File:** `scripts/generate_er_diagram.py` (CREATE)

The script:
1. Imports all model modules (same list as alembic/env.py + the 4 we just added)
2. Imports `Base` from `app.core.database`
3. Iterates `Base.metadata.sorted_tables` for deterministic order
4. For each table:
   - Emits column names with Mermaid-compatible types (map SQLAlchemy types → simple names)
   - Marks PK columns with `PK`
   - Marks FK columns with `FK`
5. For each foreign key constraint across all tables:
   - Emits a Mermaid relationship line (`||--o{`, `}o--||`, etc.)
   - Determines cardinality from nullable + unique constraints
6. Writes output to stdout (Makefile redirects to file)

**Type mapping** (SQLAlchemy → Mermaid display):
- `Integer`, `BigInteger` → `int`
- `String`, `Text` → `string`
- `Boolean` → `bool`
- `DateTime` → `datetime`
- `Float` → `float`
- `UUID` → `uuid`
- `JSON`, `JSONB` → `jsonb`
- `LargeBinary` → `bytes`
- `Enum` → `enum`
- `Geometry` (GeoAlchemy2) → `geometry`
- `Vector` (pgvector) → `vector`
- Unknown → type class name lowercased

**Relationship cardinality logic:**
- FK column nullable → `}o--||` (zero-or-one to one)
- FK column not nullable → `}|--||` (exactly-one to one)
- Self-referencing FK → same rules, but show as self-relation

**Output format:**
```markdown
# Database Schema — ER Diagram

> Auto-generated by `make er-diagram` from SQLAlchemy models.
> Do not edit manually — re-run after migrations.

```mermaid
erDiagram
    users {
        uuid id PK
        string email
        ...
    }
    vehicles {
        uuid id PK
        uuid current_driver_id FK
        ...
    }
    vehicles }o--|| drivers : "current_driver_id"
    ...
`` `
```

**Key decisions:**
- Use `sorted_tables` for deterministic output (topological FK order)
- Print to stdout — Makefile does the redirect, keeping script composable
- No database connection needed — metadata introspection only
- No async — pure synchronous script
- Sanitize column names: replace spaces/special chars (shouldn't occur, but defensive)
- Skip `TimestampMixin` columns (`created_at`, `updated_at`) from diagram to reduce noise — NO, include them since they're real columns

**Validation:** `uv run python scripts/generate_er_diagram.py | head -20` (should output valid Mermaid header)

### Step 3: Add Makefile target

**File:** `Makefile`

Add after the `rechunk-dry-run` target (around line 105), before the `# === Agent evals` section:

```makefile
er-diagram: ## Generate Mermaid ER diagram from SQLAlchemy models
	uv run python scripts/generate_er_diagram.py > docs/schema/er.md
	@echo "ER diagram written to docs/schema/er.md"
```

Also add `er-diagram` to the `.PHONY` list on line 1.

**Validation:** `make er-diagram` runs without error

### Step 4: Create `docs/schema/` directory and generate initial output

```bash
mkdir -p docs/schema
make er-diagram
```

Verify `docs/schema/er.md` contains valid Mermaid with `erDiagram` keyword and all ~24 tables.

**Validation:**
- `grep -c "erDiagram" docs/schema/er.md` → 1
- `grep -c "{" docs/schema/er.md` → ≥24 (one `{` per table block)
- Visual: open in GitHub preview or Mermaid live editor

### Step 5 (optional): Add convention test for ER diagram existence

**File:** `app/tests/test_security.py` — add a test class following existing script-check patterns:

```python
class TestERDiagram:
    def test_er_diagram_script_exists(self) -> None:
        from pathlib import Path
        assert Path("scripts/generate_er_diagram.py").exists()

    def test_er_diagram_output_exists(self) -> None:
        from pathlib import Path
        er = Path("docs/schema/er.md")
        assert er.exists(), "Run 'make er-diagram' to generate"
        content = er.read_text()
        assert "erDiagram" in content
```

**Validation:** `uv run pytest app/tests/test_security.py::TestERDiagram -v`

## Preflight Warnings

None — this task creates new files only. No existing code is modified except:
- `alembic/env.py`: adding imports (append-only, safe)
- `Makefile`: adding a target (append-only, safe)
- `app/tests/test_security.py`: adding a test class (append-only, safe)

## Security Checklist

Not applicable — no new endpoints, no user input, no auth changes. The script reads metadata in-process and writes to stdout.

- [x] No credentials in script (metadata-only, no DB connection)
- [x] No user input handling
- [x] Output is deterministic and safe (Mermaid markdown)

## Verification

- [ ] `make er-diagram` generates `docs/schema/er.md`
- [ ] Output contains all ~24 tables with columns
- [ ] Foreign key relationships rendered as Mermaid arrows
- [ ] `docs/schema/er.md` renders correctly in GitHub Mermaid preview
- [ ] `make check` passes (lint + types + tests)
- [ ] `uv run pytest app/tests/test_security.py::TestERDiagram -v` passes
- [ ] Pyright errors ≤ baseline (0 errors — scripts out of scope)
- [ ] Re-running `make er-diagram` produces identical output (deterministic)
