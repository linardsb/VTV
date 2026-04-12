# Plan: ML-1.2 E-Ticket Validation Data Pipeline

## Context

E-ticket validation data is the most valuable ML dataset in VTV — every tap-on since 2018 mapped to vehicle + route + direction + time. Combined with GPS positions, it enables passenger load prediction. The dataset is ~45 GB uncompressed across 67 monthly archives (~100MB each). Needs a staged backfill with TimescaleDB compression from day one.

## Security Context Assessment

- **CTX-INFRA** — New config settings for archive base URL, no hardcoded credentials
- **CTX-INPUT** — Parsing untrusted TXT files from external archives (encoding, malformed lines)
- **CTX-FILE** — ZIP archive handling (bomb protection, temp file cleanup)
- No REST endpoints added → CTX-RBAC/CTX-AUTH not applicable

## Research Summary

**Reference files:**
- `app/transit/models.py:18-75` — VehiclePositionRecord (hypertable model template, no TimestampMixin)
- `alembic/versions/b7c8d9e0f1a2_...py` — Hypertable migration (create_hypertable, compression, retention)
- `app/transit/repository.py:29-51` — batch_insert_positions() bulk insert pattern
- `app/core/database.py:46-59` — `get_db_context()` for standalone scripts
- `scripts/rechunk_documents.py:37-189` — CLI script template (argparse, async main, exit codes)
- `app/core/config.py:155-159` — TimescaleDB tuning settings pattern

**Latest migration:** `9d9e77b5b0bf` (create_memory_entries) → new migration chains from this

## Test Landscape

- Transit tests in `app/transit/tests/` (10 files, no conftest.py yet)
- GTFS import tests in `app/schedules/tests/test_gtfs_import.py` — ZIP creation via `_make_gtfs_zip()` helper with `io.BytesIO + zipfile`
- Integration tests use `@pytest.mark.integration` + `@pytest.mark.asyncio` + `test_db_session` fixture
- Factory pattern: `make_*(**overrides)` functions in conftest
- HTTP mocking: `@patch` + `AsyncMock` for client classes

## Type Check Baseline

- **Pyright `app/transit/`:** 0 errors
- **Mypy `app/transit/`:** 0 errors (23 source files)
- **Pyright `scripts/`:** 170 errors (pre-existing, unrelated — `update_vehicle_statuses.py`, `generate_er_diagram.py`)

## Files to Create/Modify

| Action | File | Purpose |
|--------|------|---------|
| CREATE | `alembic/versions/h1i2j3k4l5m6_eticket_validations.py` | Hypertable + tracking table migration |
| UPDATE | `app/transit/models.py` | Add EticketValidation + EticketImport models |
| CREATE | `app/transit/eticket_importer.py` | EticketRecord dataclass, parse_eticket_txt, import_monthly_archive, backfill_all |
| CREATE | `scripts/backfill_eticket_data.py` | CLI: --month, --all, --dry-run |
| CREATE | `app/transit/tests/conftest.py` | make_eticket_record factory, sample TXT helpers |
| CREATE | `app/transit/tests/test_eticket_importer.py` | 12+ tests |
| UPDATE | `app/core/config.py` | Add eticket_* settings |
| UPDATE | `Makefile` | Add eticket-backfill targets |

## Implementation Steps

### Step 1: Config settings

**File:** `app/core/config.py` (UPDATE)

Add after the `position_history_*` block (~line 159):

```python
# E-ticket validation data pipeline (ML-1.2)
eticket_archive_base_url: str = "https://data.rigassatiksme.lv/eticket/"
eticket_batch_size: int = 5000
eticket_compression_after_days: int = 30
eticket_retention_years: int = 5
eticket_max_archive_size_mb: int = 500  # ZIP bomb guard
```

**Validation:** `uv run ruff check app/core/config.py && uv run pyright app/core/config.py`

### Step 2: SQLAlchemy models

**File:** `app/transit/models.py` (UPDATE — append after VehiclePositionRecord class)

Add these two classes at the end of the file:

```python
class EticketValidation(Base):
    """A single e-ticket tap-on record.

    Stored in TimescaleDB hypertable partitioned by validated_at.
    No TimestampMixin — same rationale as VehiclePositionRecord.
    """

    __tablename__ = "eticket_validations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    record_id: Mapped[str] = mapped_column(String(50), nullable=False)
    depot: Mapped[str] = mapped_column(String(50), nullable=False)
    transport_type: Mapped[str] = mapped_column(String(20), nullable=False)
    vehicle_number: Mapped[str] = mapped_column(String(20), nullable=False)
    route_name: Mapped[str] = mapped_column(String(100), nullable=False)
    route_code: Mapped[str] = mapped_column(String(20), nullable=False)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    validation_id: Mapped[str] = mapped_column(String(50), nullable=False)
    validated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True,
    )

    __table_args__ = (
        Index("ix_eticket_route_time", "route_code", "validated_at"),
        Index("ix_eticket_vehicle_time", "vehicle_number", "validated_at"),
    )


class EticketImport(TimestampMixin, Base):
    """Tracks which monthly archives have been imported (resume semantics)."""

    __tablename__ = "eticket_imports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    archive_month: Mapped[str] = mapped_column(String(7), unique=True, nullable=False)  # "2026-01"
    record_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="in_progress")
```

Add `from app.shared.models import TimestampMixin` to imports. `EticketImport` uses `TimestampMixin` (low-volume tracking table). `EticketValidation` does NOT (high-volume hypertable, same pattern as `VehiclePositionRecord`).

**Validation:** `uv run ruff check app/transit/models.py && uv run pyright app/transit/models.py`

### Step 3: Alembic migration

**File:** `alembic/versions/h1i2j3k4l5m6_eticket_validations.py` (CREATE)

- `down_revision = "9d9e77b5b0bf"`
- Create `eticket_validations` table with columns from model
- Create `eticket_imports` tracking table
- Create composite indexes
- Check TimescaleDB availability (same pattern as `b7c8d9e0f1a2`)
- If available: `create_hypertable('eticket_validations', 'validated_at', chunk_time_interval => INTERVAL '7 days')`
- Compression: `compress_segmentby = 'route_code, vehicle_number'`, `compress_orderby = 'validated_at DESC'`
- Compression policy: 30 days (configurable later)
- Retention policy: 5 years (`INTERVAL '1825 days'`)
- Downgrade: remove policies, drop both tables

**Validation:** `uv run alembic check` (no runtime needed, just syntax)

### Step 4: E-ticket importer module

**File:** `app/transit/eticket_importer.py` (CREATE)

Core functions:

Define `EticketRecord` dataclass at module level:

```python
@dataclasses.dataclass(frozen=True, slots=True)
class EticketRecord:
    record_id: str
    depot: str
    transport_type: str
    vehicle_number: str
    route_name: str
    route_code: str
    direction: str
    validation_id: str
    validated_at: datetime.datetime
```

1. `parse_eticket_txt(path: Path) -> Iterator[EticketRecord]`
   - Open file with `encoding="latin-1"` (source data is Latin-1)
   - Skip header line, parse semicolon-delimited fields
   - Yield `EticketRecord` instances
   - Log + skip malformed lines (don't abort entire file)
   - Structured logging: `eticket.parser.line_skipped` with line number + reason

2. `import_monthly_archive(archive_url: str, archive_month: str, *, db: AsyncSession, settings: Settings, dry_run: bool = False) -> int`
   - Check `eticket_imports` for existing completed import → skip if found
   - Download ZIP via httpx to temp dir (streaming, size guard via `eticket_max_archive_size_mb`)
   - Extract TXT files from ZIP
   - For each TXT: stream through `parse_eticket_txt`, batch-collect into lists of `eticket_batch_size`
   - Bulk insert via `asyncpg.copy_records_to_table` for speed (get raw connection from session bind)
   - On completion: insert/update `eticket_imports` row with status="completed"
   - On error: set status="failed", re-raise
   - Cleanup: delete temp files in `finally` block
   - Structured logging: `eticket.importer.archive_started`, `eticket.importer.archive_completed`, `eticket.importer.archive_failed`

3. `backfill_all(*, db: AsyncSession, settings: Settings, dry_run: bool = False) -> int`
   - Generate archive URLs for all months from 2018-01 to current
   - Query `eticket_imports` for completed months → skip those
   - Loop remaining months oldest-first, call `import_monthly_archive`
   - Return total records imported

**Key patterns:**
- Use `get_logger(__name__)` for structured logging
- All functions fully typed (return types, parameter types)
- No `Any` without justification
- Temp file cleanup in `finally` blocks
- ZIP bomb guard: check `ZipInfo.file_size` sum before extracting

**Raw asyncpg COPY pattern:**
```python
# Get raw asyncpg connection from SQLAlchemy async session
raw_conn = await db.connection()
asyncpg_conn = await raw_conn.get_raw_connection()
# asyncpg_conn is the underlying asyncpg.Connection
await asyncpg_conn.copy_records_to_table(
    "eticket_validations",
    records=batch,
    columns=["record_id", "depot", "transport_type", ...],
)
```

**Validation:** `uv run ruff check app/transit/eticket_importer.py && uv run pyright app/transit/eticket_importer.py`

### Step 5: CLI backfill script

**File:** `scripts/backfill_eticket_data.py` (CREATE)

Follow `scripts/rechunk_documents.py` pattern:
- `sys.path.insert(0, ...)` for `app.*` imports
- `_parse_args()` → argparse with `--month YYYY-MM`, `--all`, `--dry-run`, `--batch-size`
- `async def main(args) -> int` using `get_db_context()`
- `if __name__ == "__main__":` with `asyncio.run(main(args))`
- Exit code 0 on success, 1 on error
- Print summary: months processed, records imported, elapsed time

**Validation:** `uv run ruff check scripts/backfill_eticket_data.py && uv run pyright scripts/backfill_eticket_data.py`

### Step 6: Makefile targets

**File:** `Makefile` (UPDATE)

Add after the `rechunk-dry-run` target (~line 105):

```makefile
eticket-backfill: ## Backfill single month (usage: make eticket-backfill MONTH=2026-01)
	@test -n "$(MONTH)" || (echo "Usage: make eticket-backfill MONTH=2026-01" && exit 1)
	uv run python scripts/backfill_eticket_data.py --month $(MONTH)

eticket-backfill-all: ## Backfill ALL months (~45GB, alert ops first)
	uv run python scripts/backfill_eticket_data.py --all

eticket-backfill-dry-run: ## Preview e-ticket backfill without importing
	uv run python scripts/backfill_eticket_data.py --dry-run $(if $(MONTH),--month $(MONTH),--all)
```

**Validation:** `make help | grep eticket`

### Step 7: Test conftest with factories

**File:** `app/transit/tests/conftest.py` (CREATE)

```python
import datetime
import io
import zipfile

import pytest


def make_eticket_line(
    *,
    record_id: str = "REC001",
    depot: str = "Riga-1",
    transport_type: str = "bus",
    vehicle_number: str = "4521",
    route_name: str = "Maršruts 22",
    route_code: str = "22",
    direction: str = "A",
    validation_id: str = "VAL001",
    validated_at: str = "2026-01-15 08:30:00",
) -> str:
    """Build a single semicolon-delimited e-ticket TXT line."""
    return ";".join([
        record_id, depot, transport_type, vehicle_number,
        route_name, route_code, direction, validation_id, validated_at,
    ])


def make_eticket_txt(lines: list[str], *, encoding: str = "latin-1") -> bytes:
    """Build in-memory TXT content with header."""
    header = "record_id;depot;transport_type;vehicle_number;route_name;route_code;direction;validation_id;validated_at"
    content = "\n".join([header, *lines])
    return content.encode(encoding)


def make_eticket_zip(txt_files: dict[str, bytes]) -> bytes:
    """Build in-memory ZIP archive with named TXT files."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in txt_files.items():
            zf.writestr(name, data)
    return buf.getvalue()
```

**Validation:** `uv run ruff check app/transit/tests/conftest.py && uv run pyright app/transit/tests/conftest.py`

### Step 8: Tests (12+ tests)

**File:** `app/transit/tests/test_eticket_importer.py` (CREATE)

**Unit tests (no DB):**
1. `test_parse_eticket_txt_basic` — Parse 3 valid lines, verify field mapping
2. `test_parse_eticket_txt_latin1_encoding` — Parse lines with Latvian diacritics (ā, č, ē, ģ, ī, ķ, ļ, ņ, š, ū, ž)
3. `test_parse_eticket_txt_skip_malformed` — Lines with missing fields are skipped, count returned
4. `test_parse_eticket_txt_empty_file` — Header-only file yields 0 records
5. `test_zip_bomb_guard` — Archive with file_size sum > max rejected
6. `test_import_skips_completed_month` — Mock DB returns completed import → no download
7. `test_archive_url_generation` — Verify URL pattern for month "2026-01"

**Integration tests:**
8. `test_bulk_copy_inserts_records` — `@pytest.mark.integration` — Parse sample TXT, COPY to hypertable, verify count
9. `test_duplicate_import_prevented` — Insert tracking row, re-run → 0 new records

**Resume / error handling:**
10. `test_import_sets_failed_on_error` — Mock download failure → tracking row status="failed"
11. `test_temp_files_cleaned_on_failure` — Verify temp dir empty after failed import
12. `test_backfill_all_skips_completed` — 3 months, 1 completed → only 2 processed

**Schema & policies:**
13. `test_eticket_validation_model_columns` — Verify model has all expected columns
14. `test_eticket_import_model_columns` — Verify tracking model columns
15. `test_compression_policy_in_migration` — `@pytest.mark.integration` — Query `timescaledb_information.compression_settings` for eticket_validations, assert segmentby includes route_code + vehicle_number
16. `test_storage_budget_guardrail_rejects_oversized` — Archive with estimated uncompressed size > `eticket_max_archive_size_mb` is rejected before extraction

Mock patterns:
- `@patch("app.transit.eticket_importer.httpx.AsyncClient")` for download mocking
- `tmp_path` fixture for temp file tests
- `make_eticket_txt()` and `make_eticket_zip()` from conftest

**Validation:** `uv run pytest app/transit/tests/test_eticket_importer.py -v --tb=short`

## Preflight Warnings

- No existing transit conftest.py — Step 7 creates it fresh (no merge conflicts)
- `scripts/` has 170 pre-existing pyright errors — new script should NOT add to them; add file-level pyright directives if needed for asyncpg raw connection typing
- The `asyncpg` raw connection access through SQLAlchemy may need `# type: ignore[attr-defined]` — verify at implementation time
- Latin-1 encoding: Python's `open(encoding="latin-1")` handles all single-byte values (no decode errors possible), but field content may contain unexpected characters

## Security Checklist

No REST endpoints → auth/rate-limit N/A. File-handling security:

- [x] ZIP bomb guard via `ZipInfo.file_size` sum check
- [x] Temp file cleanup in `finally` blocks (CTX-FILE)
- [x] No hardcoded archive URL (env-configurable via Settings)
- [x] Streaming download with size limit (no unbounded memory)
- [x] Latin-1→UTF-8 encoding handled safely
- [x] No user-facing input (CLI only, not web-accessible)
- [x] Structured logging with no credential exposure

## Anti-Pattern Checklist

Per `python-anti-patterns.md`:
- No `assert` in production code (#1)
- No `object` type hints — use actual types (#2)
- All functions fully typed (#7)
- No EN DASH (#8)
- No unused imports (#5)
- `dict.get()` walrus narrowing if needed (#19)
- No bare `except: pass` — always log (#37)
- Background tasks handle CancelledError + Exception (#38)

## Verification

- [ ] `uv run ruff format app/transit/eticket_*.py scripts/backfill_eticket_data.py`
- [ ] `uv run ruff check app/transit/ scripts/backfill_eticket_data.py`
- [ ] `uv run pyright app/transit/` — 0 errors (baseline: 0)
- [ ] `uv run mypy app/transit/` — 0 errors (baseline: 0)
- [ ] `uv run pytest app/transit/tests/test_eticket_importer.py -v` — 12+ pass
- [ ] `make check` passes (full suite)
- [ ] `make help | grep eticket` shows both targets
- [ ] `make security-audit-quick` passes
