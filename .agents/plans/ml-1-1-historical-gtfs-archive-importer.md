# Plan: ML-1.1 Historical GTFS Archive Importer

## Context

Current GTFS importer (`app/schedules/gtfs_import.py` + `service.py`) only ingests the "latest" Rīgas Satiksme feed — overwriting prior data on every run. ML training needs the full temporal history (~64 monthly snapshots since 2018) to learn seasonal variations (summer vs winter routes, school vs holiday calendars). This feature creates a CLI + background-compatible importer that downloads all available GTFS snapshots from data.gov.lv, de-duplicates via SHA-256, and stores each in snapshot-scoped shadow tables.

**No new REST endpoints.** This is a CLI tool + Makefile target only.

## Security Context Assessment

| Context | Active? | Reason |
|---------|---------|--------|
| CTX-AUTH | No | No endpoints, CLI only |
| CTX-RBAC | No | No endpoints |
| CTX-FILE | **Yes** | Downloads + processes ZIP files from external source |
| CTX-AGENT | No | No agent tool involvement |
| CTX-INFRA | **Yes** | New config settings, Makefile target, CLI script |
| CTX-INPUT | **Yes** | External API data (data.gov.lv), ZIP contents |

**CTX-FILE requirements:** ZIP bomb protection (reuse existing `GTFSImporter._validate_zip_safety()`), SHA-256 integrity, corrupt ZIP fallback with cleanup.
**CTX-INFRA requirements:** Config via env vars, no hardcoded URLs.
**CTX-INPUT requirements:** Validate API response structure, sanitize resource metadata.

## Research Summary

### Existing GTFS Architecture

- **Parser:** `app/schedules/gtfs_import.py:55` — `GTFSImporter` class. Pure parsing, no DB. Takes `zip_data: bytes` + `feed_id: str`. Returns `GTFSParseResult` dataclass with entities + parallel FK ref lists. ZIP bomb protection built in (500MB/100:1/100MB limits).
- **Service:** `app/schedules/service.py:560` — `import_gtfs()` orchestrates parse → bulk upsert via repository.
- **Repository:** `app/schedules/repository.py` — `pg_insert().on_conflict_do_update()` with constraint names.
- **Models:** `app/schedules/models.py` — Agency, Route, Calendar, CalendarDate, Trip, StopTime, Shape. All have `feed_id` column, `TimestampMixin`, unique constraints on `(feed_id, gtfs_*)`.

### Key Patterns to Follow

- **Background tasks:** `app/memory/lifecycle.py` — global `_task`, `asyncio.create_task()`, `get_db_context()` for sessions.
- **HTTP client:** `app/transit/poller.py:52` — `httpx.AsyncClient` with connection pooling, timeouts.
- **TimescaleDB:** `alembic/versions/b7c8d9e0f1a2_add_vehicle_positions_hypertable.py` — hypertable creation, compression policy, retention.
- **CLI scripts:** `scripts/rechunk_documents.py`, `scripts/seed_demo_data.py` — use `asyncio.run()` with `get_db_context()`.
- **Config:** `app/core/config.py:18` — `TransitFeedConfig` + `Settings` with env var overrides.

### Current Migration Head

`9d9e77b5b0bf` (create_memory_entries)

## Test Landscape

- **ZIP test helper:** `app/schedules/tests/test_gtfs_import.py` — `_make_gtfs_zip(**files)` creates in-memory ZIPs from CSV strings.
- **Schedules factories:** `app/schedules/tests/conftest.py` — `make_agency()`, `make_route()`, `make_calendar()`, `make_trip()`, `make_stop_time()`.
- **HTTP mock pattern:** `app/transit/tests/test_routes.py` — `AsyncMock` for service layer, `@patch` for dependencies.
- **Background task tests:** `app/transit/tests/test_poller.py` — mock httpx responses, test polling cycle.
- **No existing endpoint tests needed** — this feature has no REST endpoints.

## Type Check Baseline

| Directory | Pyright | MyPy |
|-----------|---------|------|
| `app/transit/` | **0 errors** | **0 errors** |
| `app/schedules/` | **0 errors** | **0 errors** |

Zero-error baseline. New code must not introduce regressions.

## Files to Create/Modify

| Action | File | Purpose |
|--------|------|---------|
| CREATE | `app/transit/snapshot_models.py` | SQLAlchemy models for `gtfs_snapshots` + shadow tables |
| CREATE | `app/transit/snapshot_schemas.py` | Pydantic schemas for snapshot metadata |
| CREATE | `app/transit/snapshot_repository.py` | DB operations for snapshots + shadow table bulk inserts |
| CREATE | `app/transit/historical_gtfs_importer.py` | Core importer: list/download/dedup/import logic |
| CREATE | `alembic/versions/xxxx_add_gtfs_snapshot_tables.py` | Migration for new tables |
| CREATE | `scripts/backfill_gtfs_history.py` | CLI entrypoint |
| CREATE | `app/transit/tests/test_historical_gtfs_importer.py` | Unit tests (12+) |
| UPDATE | `app/core/config.py` | Add `data_gov_lv_base_url` + `data_gov_lv_dataset_id` settings |
| UPDATE | `Makefile` | Add `gtfs-backfill` target |

## Implementation Steps

### Step 1: Config settings
**File:** `app/core/config.py` — UPDATE
**Action:** Add settings to `Settings` class:
```python
# Historical GTFS archive (data.gov.lv)
data_gov_lv_base_url: str = "https://data.gov.lv/dati/api/3"
data_gov_lv_dataset_id: str = "rigas-satiksmes-marsrutu-saraksti-gtfs"
gtfs_backfill_rate_limit_seconds: float = 1.0
```
**Validation:** `uv run ruff check app/core/config.py && uv run pyright app/core/config.py`

### Step 2: Snapshot models
**File:** `app/transit/snapshot_models.py` — CREATE

Models:
- `GtfsSnapshot` — id (PK), feed_name (str50), snapshot_date (Date), resource_id (str100, unique), sha256 (str64), row_counts_json (JSON), imported_at (DateTime UTC), status (Literal["pending","complete","failed"]). Inherits `Base, TimestampMixin`.
- `GtfsSnapshotTrip` — id (PK), snapshot_id (FK → gtfs_snapshots, CASCADE), gtfs_trip_id, gtfs_route_id, gtfs_service_id, direction_id, trip_headsign, shape_id. Unique on (snapshot_id, gtfs_trip_id).
- `GtfsSnapshotStopTime` — id (PK), snapshot_id (FK), gtfs_trip_id, gtfs_stop_id, stop_sequence, arrival_time (str8), departure_time (str8). Unique on (snapshot_id, gtfs_trip_id, stop_sequence).
- `GtfsSnapshotCalendar` — id (PK), snapshot_id (FK), gtfs_service_id, mon-sun booleans, start_date, end_date. Unique on (snapshot_id, gtfs_service_id).

Shadow tables store GTFS string IDs (not FK ints) — they are denormalized for ML training, not for FK joins to main tables. This avoids cross-snapshot FK resolution complexity.

**Validation:** `uv run ruff check app/transit/snapshot_models.py && uv run pyright app/transit/snapshot_models.py`

### Step 3: Snapshot schemas
**File:** `app/transit/snapshot_schemas.py` — CREATE

Pydantic models:
- `SnapshotMeta` — resource_id, name, description, url, format, created, last_modified, snapshot_date (extracted from name/date)
- `SnapshotImportResult` — snapshot_id, snapshot_date, trips_count, stop_times_count, calendars_count, skipped (bool if duplicate)
- `BackfillProgress` — total_available, imported, skipped_duplicate, failed, current_resource_id

**Validation:** `uv run ruff check app/transit/snapshot_schemas.py && uv run pyright app/transit/snapshot_schemas.py`

### Step 4: Snapshot repository
**File:** `app/transit/snapshot_repository.py` — CREATE

Functions (all async, take `AsyncSession`):
- `get_snapshot_by_resource_id(db, resource_id) -> GtfsSnapshot | None`
- `get_snapshot_by_sha256(db, sha256) -> GtfsSnapshot | None`
- `create_snapshot(db, snapshot) -> GtfsSnapshot`
- `update_snapshot_status(db, snapshot_id, status, row_counts)`
- `bulk_insert_snapshot_trips(db, snapshot_id, trips: list[GtfsSnapshotTrip])`
- `bulk_insert_snapshot_stop_times(db, snapshot_id, stop_times: list[GtfsSnapshotStopTime])`
- `bulk_insert_snapshot_calendars(db, snapshot_id, calendars: list[GtfsSnapshotCalendar])`
- `get_imported_resource_ids(db) -> set[str]` — for fast duplicate check

Use `session.execute(insert(...))` with batched chunks (1000 rows per execute) for bulk inserts.

**Validation:** `uv run ruff check app/transit/snapshot_repository.py && uv run pyright app/transit/snapshot_repository.py`

### Step 5: Historical GTFS importer
**File:** `app/transit/historical_gtfs_importer.py` — CREATE

Class: `HistoricalGtfsImporter`
- `__init__(settings, db_session_factory)` — stores config, creates httpx.AsyncClient
- `async list_available_snapshots() -> list[SnapshotMeta]` — calls `{base_url}/action/package_show?id={dataset_id}`, parses resources list, filters for ZIP format, sorts by date, extracts snapshot_date from resource name/created date.
- `async download_snapshot(url: str) -> bytes` — downloads with timeout (120s), streams to bytes, validates size.
- `async import_snapshot(meta: SnapshotMeta) -> SnapshotImportResult` — downloads ZIP, computes sha256, checks duplicate by resource_id OR sha256 (skip if found), reuses `GTFSImporter.parse()` for CSV extraction, maps parsed entities to snapshot shadow models (denormalized — store gtfs string IDs, not DB FKs), bulk inserts via repository, updates snapshot status.
- `async backfill(since_date, until_date, dry_run) -> BackfillProgress` — lists snapshots, filters by date range, respects rate limit (`asyncio.sleep`), calls `import_snapshot` for each, tracks progress, resumable via `get_imported_resource_ids()`.
- `async close()` — closes httpx client.

**Logging:** `transit.historical_importer.{action}_{state}` — backfill_started, snapshot_download_started, snapshot_download_completed, snapshot_import_completed, snapshot_skipped_duplicate, snapshot_import_failed, backfill_completed.

**Error handling:** Per-snapshot try/except — log failure, mark snapshot as "failed", continue to next. Don't abort entire backfill on single failure.

**Validation:** `uv run ruff check app/transit/historical_gtfs_importer.py && uv run pyright app/transit/historical_gtfs_importer.py`

### Step 6: Alembic migration
**File:** `alembic/versions/xxxx_add_gtfs_snapshot_tables.py` — CREATE (via `make db-revision m="add gtfs snapshot tables for historical archive"`)

Tables: `gtfs_snapshots`, `gtfs_snapshot_trips`, `gtfs_snapshot_stop_times`, `gtfs_snapshot_calendars`.
Indexes: `ix_snapshot_date` on gtfs_snapshots, `ix_snapshot_trip_id` on trips, composite indexes for ML queries.

**Note:** Do NOT create TimescaleDB hypertables for these tables. They are append-only archive data with date-range queries, not time-series. Standard PostgreSQL tables with date indexes are sufficient. TimescaleDB compression can be added later if storage becomes an issue.

**Validation:** `uv run alembic upgrade head` (requires running DB)

### Step 7: CLI script
**File:** `scripts/backfill_gtfs_history.py` — CREATE

```python
"""CLI entrypoint for historical GTFS archive backfill."""
import argparse, asyncio, sys
# Parse args: --since YYYY-MM, --until YYYY-MM, --dry-run
# Create HistoricalGtfsImporter with get_settings() + get_db_context
# Call backfill(), print progress, exit with 0/1
```

Use `argparse` (no extra deps). Print progress as structured log lines. Exit code 1 on any failures.

**Validation:** `uv run ruff check scripts/backfill_gtfs_history.py && uv run pyright scripts/backfill_gtfs_history.py`

### Step 8: Makefile target
**File:** `Makefile` — UPDATE

Add after the `er-diagram` target:
```makefile
gtfs-backfill: ## Backfill historical GTFS snapshots from data.gov.lv
	uv run python scripts/backfill_gtfs_history.py --since $(or $(SINCE),2018-05) $(if $(UNTIL),--until $(UNTIL)) $(if $(DRY_RUN),--dry-run)
```

Add `gtfs-backfill` to `.PHONY` list.

**Validation:** `make help | grep gtfs`

### Step 9: Unit tests
**File:** `app/transit/tests/test_historical_gtfs_importer.py` — CREATE

12+ tests using pytest + AsyncMock:

1. `test_list_available_snapshots_parses_resources` — mock httpx response with sample data.gov.lv JSON, verify SnapshotMeta list
2. `test_list_available_snapshots_filters_non_zip` — resources with format != "ZIP" excluded
3. `test_duplicate_detection_by_resource_id` — mock repo returns existing, verify skip
4. `test_duplicate_detection_by_sha256` — different resource_id but same content hash, verify skip
5. `test_import_snapshot_writes_shadow_tables` — mock repo bulk inserts called with correct data
6. `test_import_snapshot_maps_gtfs_ids_correctly` — verify denormalized string IDs in shadow models
7. `test_rate_limiting_between_downloads` — verify `asyncio.sleep` called between snapshots
8. `test_resumability_skips_already_imported` — mock `get_imported_resource_ids` returns set, verify skipped
9. `test_backfill_continues_on_single_failure` — one snapshot raises, rest still imported
10. `test_corrupt_zip_marks_failed` — invalid ZIP bytes → snapshot status "failed", no abort
11. `test_backfill_dry_run_no_writes` — dry_run=True → no repo write calls
12. `test_download_respects_size_limit` — oversized response raises, logged

Use `_make_gtfs_zip()` helper pattern from `app/schedules/tests/test_gtfs_import.py`. Mock httpx.AsyncClient responses with `AsyncMock`. Mock `snapshot_repository` functions.

**Validation:** `uv run pytest app/transit/tests/test_historical_gtfs_importer.py -v`

## Anti-Pattern Checklist

| # | Rule | Applies? | Mitigation |
|---|------|----------|------------|
| 1 | No `assert` in production | Yes | Use `if` guards, not assert |
| 4 | Mock exceptions must match catch | Yes | Catch `httpx.HTTPStatusError` → mock with same |
| 5 | No unused imports | Yes | Only import what's used |
| 7 | Test helpers need return types | Yes | Annotate all helpers |
| 11 | Schema field additions break consumers | No | New schemas only |
| 16 | Singleton close handles closed loops | Yes | try/except RuntimeError on `client.aclose()` |
| 17 | `verify=False` needs noqa | No | Use default SSL |
| 34 | Redis stubs | No | No Redis in this feature |
| 37 | Bare `except: pass` | Yes | Always log in except |
| 50 | Wrap error-path DB updates | Yes | try/except on status update |

## Preflight Warnings

None — all target files are new (CREATE). No existing fragile patterns to break.

## Security Checklist

No new endpoints, so endpoint-level checks don't apply. File/infra/input checks:
- [ ] ZIP bomb protection via existing `GTFSImporter._validate_zip_safety()`
- [ ] SHA-256 integrity check before import
- [ ] Download size limit enforced (streaming with byte counter)
- [ ] data.gov.lv base URL from config (not hardcoded)
- [ ] No credentials in config (data.gov.lv is public API)
- [ ] Structured logging — no URLs with credentials logged
- [ ] Corrupt/malformed ZIP handled gracefully (no crash)

## Verification

- [ ] `make check` passes (lint + types + tests)
- [ ] `make security-audit-quick` passes
- [ ] Pyright errors = 0 for `app/transit/` (baseline: 0)
- [ ] MyPy errors = 0 for `app/transit/` (baseline: 0)
- [ ] `uv run pytest app/transit/tests/test_historical_gtfs_importer.py -v` — 12+ tests pass
- [ ] `make gtfs-backfill DRY_RUN=1 SINCE=2025-10` — dry run completes without error
- [ ] Security convention tests pass: `uv run pytest app/tests/test_security.py -v`
