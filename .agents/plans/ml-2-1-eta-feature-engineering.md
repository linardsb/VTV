# Plan: ML-2.1 ETA Feature Engineering Pipeline

## Context

ML training data quality dominates model quality. This feature centralises feature engineering in one module so the training set, online inference, and eval all use the same feature code — no train/serve skew. Creates `app/ml/features/eta_features.py` — a deterministic feature extraction job that joins `vehicle_positions` (TimescaleDB) with `gtfs_stop_times` + `weather_observations` + `traffic_counts`/`traffic_accidents` to produce a training matrix. One row per (trip_id, stop_sequence) with 18 features (8 categorical, 10 numeric).

## Security Context Assessment

**Active contexts:** None directly — this is an internal batch/ETL pipeline with no REST endpoints, no user-facing input, and no file uploads. The CLI script accepts `--from`/`--to`/`--out` args but reads only from the internal DB and writes to a local file path.

**Note:** If REST endpoints are added later (e.g., feature store API), CTX-RBAC + CTX-INPUT will apply at that time.

## Research Summary

### Source Tables (all fields confirmed via model inspection)

| Table | Model Location | Key Fields for Features |
|-------|----------------|------------------------|
| `vehicle_positions` | `app/transit/models.py:19` | `trip_id`, `recorded_at`, `delay_seconds`, `route_id`, `speed_kmh`, `latitude`, `longitude` |
| `stop_times` | `app/schedules/models.py:125` | `trip_id` (FK→trips.id), `stop_id` (FK→stops.id), `stop_sequence`, `arrival_time`, `departure_time` |
| `trips` | `app/schedules/models.py:104` | `gtfs_trip_id`, `route_id` (FK→routes.id), `calendar_id` (FK→calendars.id), `direction_id` |
| `routes` | `app/schedules/models.py:38` | `gtfs_route_id`, `route_type`, `route_short_name`, `agency_id` |
| `calendars` | `app/schedules/models.py:59` | `monday`..`sunday`, `start_date`, `end_date`, `gtfs_service_id` |
| `stops` | `app/stops/models.py` | `gtfs_stop_id`, `stop_name`, `stop_lat`, `stop_lon` |
| `weather_observations` | `app/transit/weather_models.py:34` | `station_id`, `observed_at`, `temp_c`, `wind_mps`, `precip_mm`, `phenomena`, `location` |
| `traffic_counts` | `app/transit/traffic_models.py:17` | `point_id`, `period_start`, `period_end`, `avg_count_per_day`, `location` |
| `traffic_accidents` | `app/transit/traffic_models.py:47` | `source_id`, `occurred_at`, `severity`, `location` |

### VSA Patterns to Follow

**Reference:** `app/transit/weather_etl.py` and `app/transit/eticket_importer.py` — batch ETL with `get_db_context()`, structured logging, defensive type coercion.

**CLI Entry Pattern:** `scripts/backfill_gtfs_history.py` — `sys.path.insert(0, ...)`, argparse, `asyncio.run(main())`.

### Key Dependencies & Utilities

- `app.core.database.get_db_context()` — standalone async session for batch jobs
- `app.core.logging.get_logger(__name__)` — structured logging
- `app.core.config.get_settings()` — @lru_cache settings singleton
- No pandas/pandera/pyarrow in current deps — must add

## Test Landscape

### Existing Fixtures to Reuse

| Fixture | Location | Purpose |
|---------|----------|---------|
| `make_vehicle_position()` | `app/transit/tests/test_service.py:17` | VehiclePositionData factory |
| `make_stop_time()` | `app/schedules/tests/conftest.py:152` | StopTime factory with arrival/departure |
| `make_trip()` | `app/schedules/tests/conftest.py:126` | Trip factory |
| `make_calendar()` | `app/schedules/tests/conftest.py:73` | Calendar with day-of-week bools |
| `make_route()` | `app/schedules/tests/conftest.py:44` | Route factory |
| `mock_db` | `app/schedules/tests/conftest.py:233` | AsyncMock session |

### ETL Test Pattern (from test_weather_etl.py)

1. CSV/data parsing tests (pure unit, no DB)
2. Upsert tests (AsyncMock for db.execute/commit)
3. Missing-data / edge-case tests (graceful None handling)
4. Task lifecycle tests (start/stop with settings flags)

### Mock Patterns

- `AsyncMock()` for db session, `db.execute.assert_called_once()`
- `MagicMock()` for settings with attribute overrides
- `@pytest.mark.integration` + `@pytest.mark.asyncio` for real DB tests

## Type Check Baseline

| Directory | Pyright | Mypy |
|-----------|---------|------|
| `app/transit/` | 0 errors | 0 errors (37 files) |
| `app/schedules/` | 0 errors | 0 errors (16 files) |
| `app/ml/` | N/A (new) | N/A (new) |

**New dependency considerations:**
- `pandas`: Has `pandas-stubs` package — add to dev deps
- `pandera`: Lacks `py.typed` — needs mypy `ignore_missing_imports` override
- `pyarrow`: Has `pyarrow-stubs` — add to dev deps
- Pyright global `reportMissingTypeStubs = "none"` covers stub-missing libraries

## Files to Create/Modify

| Action | File | Purpose |
|--------|------|---------|
| CREATE | `app/ml/__init__.py` | ML package init |
| CREATE | `app/ml/features/__init__.py` | Features subpackage init |
| CREATE | `app/ml/features/eta_features.py` | ETAFeatures dataclass + extract_features + extract_features_batch |
| CREATE | `app/ml/features/validation.py` | Pandera schema for 18-feature DataFrame validation |
| CREATE | `app/ml/features/queries.py` | Raw SQL queries for feature extraction (keep SQL separate from logic) |
| CREATE | `app/ml/features/tests/__init__.py` | Test package init |
| CREATE | `app/ml/features/tests/conftest.py` | Fixtures: make_feature_row, sample DataFrames |
| CREATE | `app/ml/features/tests/test_eta_features.py` | 8 per-feature tests + 2 missing-data + 1 parity + 1 batch equivalence |
| CREATE | `app/ml/features/tests/test_validation.py` | Pandera schema validation tests |
| CREATE | `alembic/versions/ml21_eta_features_materialized_view.py` | Migration: CREATE MATERIALIZED VIEW ml_eta_features_v1 |
| UPDATE | `pyproject.toml` | Add pandas, pandera, pyarrow deps + pandas-stubs, pyarrow-stubs dev deps + mypy override for pandera |
| CREATE | `app/ml/features/__main__.py` | CLI entry: `python -m app.ml.features.eta_features` |

## Implementation Steps

### Step 1: Add Dependencies to pyproject.toml

**File:** `pyproject.toml`

Add to `[project] dependencies`:
```
"pandas>=2.2.0",
"pandera>=0.21.0",
"pyarrow>=17.0.0",
```

Add to `[dependency-groups] dev`:
```
"pandas-stubs>=2.2.0",
"pyarrow-stubs>=17.0",
```

Add mypy override after the existing overrides (after line 240):
```toml
# pandera lacks py.typed marker
[[tool.mypy.overrides]]
module = "pandera.*"
ignore_missing_imports = true
```

**Run:** `uv sync && uv run python -c "import pandas; import pandera; import pyarrow; print('OK')"`

**Validation:** `uv run ruff check pyproject.toml`

---

### Step 2: Create app/ml Package Structure

**Files:** Create empty `__init__.py` files:
- `app/ml/__init__.py`
- `app/ml/features/__init__.py`
- `app/ml/features/tests/__init__.py`

**Validation:** `ls app/ml/features/tests/__init__.py`

---

### Step 3: Create Feature Extraction SQL Queries

**File:** `app/ml/features/queries.py`

Contains raw SQL strings as constants, used by both online and batch paths. This separates SQL from Python logic for testability.

Key queries:
- `VEHICLE_DELAY_AT_STOP_SQL` — Joins `vehicle_positions` with `stop_times`+`trips` to find the actual delay at each stop. Uses `trip_id` match and temporal proximity (closest position record to scheduled arrival).
- `HISTORICAL_AVG_DELAY_SQL` — Computes historical average delay per (route_id, stop_sequence, hour_of_day, day_of_week) over a lookback window.
- `WEATHER_AT_TIME_SQL` — Finds the nearest weather observation to a given timestamp using `station_id` proximity and time window (±30 min).
- `TRAFFIC_ROLLING_7D_SQL` — Rolling 7-day traffic count for nearest measurement point.
- `ACCIDENT_COUNT_NEARBY_SQL` — Count of accidents within 500m radius in the last 30 days using `ST_DWithin`.
- `SCHEDULED_HEADWAY_SQL` — Time gap between consecutive trips on same route at same stop.
- `PREV_STOP_DELAY_SQL` — Delay at previous stop_sequence for same trip.

All queries use parameterized placeholders (`:trip_id`, `:observed_at`). No string interpolation.

```python
"""SQL queries for ETA feature extraction.

All queries use SQLAlchemy text() parameterized placeholders.
No string interpolation — prevents SQL injection.
"""

from __future__ import annotations

# Query: Get vehicle delay observation closest to scheduled arrival
VEHICLE_DELAY_AT_STOP_SQL = """
SELECT vp.delay_seconds, vp.recorded_at, vp.speed_kmh
FROM vehicle_positions vp
JOIN trips t ON t.gtfs_trip_id = vp.trip_id
WHERE t.id = :trip_id
  AND vp.recorded_at BETWEEN :scheduled_time - INTERVAL '5 minutes'
                         AND :scheduled_time + INTERVAL '10 minutes'
ORDER BY ABS(EXTRACT(EPOCH FROM (vp.recorded_at - :scheduled_time)))
LIMIT 1
"""

# ... (other queries follow same pattern)
```

**Validation:** `uv run ruff format app/ml/features/queries.py && uv run ruff check app/ml/features/queries.py`

---

### Step 4: Create ETAFeatures Dataclass

**File:** `app/ml/features/eta_features.py`

```python
"""ETA feature engineering pipeline (ML-2.1).

Deterministic feature extraction joining vehicle_positions (TimescaleDB)
with gtfs_stop_times + weather_observations + traffic data to produce
a training matrix. One row per (trip_id, stop_sequence).

Online path: extract_features(trip_id, stop_sequence, observed_at) -> ETAFeatures
Offline path: extract_features_batch(from_ts, to_ts) -> pd.DataFrame
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger

if TYPE_CHECKING:
    import pandas as pd

logger = get_logger(__name__)
```

**ETAFeatures dataclass** (frozen=True, 18 fields):

Categorical (8):
- `day_of_week: int` — 0=Monday..6=Sunday
- `month: int` — 1-12
- `is_school_day: bool` — derived from GTFS calendar (weekday + not holiday + school term)
- `is_holiday: bool` — from calendar_dates exception_type=2
- `weather_bucket: str` — Literal["clear", "rain", "snow", "fog", "other"]
- `route_type: int` — GTFS route_type (3=bus, 0=tram, etc.)
- `direction: int` — 0 or 1 from trips.direction_id
- `operator: str` — agency name from routes→agencies join

Numeric (10):
- `time_of_day_hour: float` — fractional hour (e.g., 8.5 = 8:30)
- `scheduled_headway_s: float` — seconds between consecutive trips at this stop
- `historical_avg_delay_at_stop_s: float` — avg delay for this route/stop/hour/dow over lookback
- `prev_stop_actual_delay_s: float` — actual delay at previous stop_sequence (0.0 if first stop)
- `trip_elapsed_pct: float` — stop_sequence / max_stop_sequence for this trip (0.0-1.0)
- `temp_c: float` — temperature from nearest weather station (default 0.0)
- `wind_mps: float` — wind speed from nearest station (default 0.0)
- `precip_mm_last_hr: float` — precipitation in last hour (default 0.0)
- `traffic_count_rolling_7d: float` — 7-day rolling avg traffic count at nearest point (default 0.0)
- `accident_count_within_500m: int` — accidents within 500m in last 30 days (default 0)

**Functions:**
- `_parse_gtfs_time(time_str: str) -> float` — Convert "HH:MM:SS" to fractional hours
- `_classify_weather(phenomena: dict | None, precip_mm: float | None) -> str` — Map to weather bucket
- `async def extract_features(db: AsyncSession, trip_id: int, stop_sequence: int, observed_at: datetime.datetime) -> ETAFeatures` — Online path
- `async def extract_features_batch(db: AsyncSession, from_ts: datetime.datetime, to_ts: datetime.datetime) -> pd.DataFrame` — Offline batch path using a single large SQL query
- Each query wrapped in try/except with fallback defaults and structured logging for missing data

**Missing data strategy:** Each numeric field has a safe default (0.0 or 0). Log at `debug` level when falling back. Never raise on missing weather/traffic data — these are optional enrichments.

**Validation:** `uv run ruff format app/ml/features/eta_features.py && uv run ruff check app/ml/features/eta_features.py && uv run pyright app/ml/features/eta_features.py`

---

### Step 5: Create Pandera Validation Schema

**File:** `app/ml/features/validation.py`

```python
"""Pandera schema validation for ETA feature DataFrames (ML-2.1).

Validates the 18-feature training matrix produced by extract_features_batch().
Catches data quality issues (nulls, range violations, type mismatches) before
they propagate to model training.
"""

from __future__ import annotations

import pandera as pa  # pyright: ignore[reportMissingTypeStubs]
from pandera import Check, Column, DataFrameSchema  # pyright: ignore[reportMissingTypeStubs]
```

**Schema definition:** `ETA_FEATURES_SCHEMA = DataFrameSchema({...})`

Column checks:
- `day_of_week`: int, `Check.in_range(0, 6)`
- `month`: int, `Check.in_range(1, 12)`
- `is_school_day`: bool
- `is_holiday`: bool
- `weather_bucket`: str, `Check.isin(["clear", "rain", "snow", "fog", "other"])`
- `route_type`: int, `Check.in_range(0, 12)` (GTFS spec)
- `direction`: int, `Check.isin([0, 1])`
- `operator`: str
- `time_of_day_hour`: float, `Check.in_range(0.0, 48.0)` (GTFS allows >24h)
- `scheduled_headway_s`: float, `Check.ge(0)`
- `historical_avg_delay_at_stop_s`: float
- `prev_stop_actual_delay_s`: float
- `trip_elapsed_pct`: float, `Check.in_range(0.0, 1.0)`
- `temp_c`: float, `Check.in_range(-60.0, 60.0)`
- `wind_mps`: float, `Check.ge(0)`
- `precip_mm_last_hr`: float, `Check.ge(0)`
- `traffic_count_rolling_7d`: float, `Check.ge(0)`
- `accident_count_within_500m`: int, `Check.ge(0)`

**Functions:**
- `validate_features(df: pd.DataFrame) -> pd.DataFrame` — Validates and returns, raises `pa.errors.SchemaError` on failure
- `detect_outliers(df: pd.DataFrame) -> pd.DataFrame` — Returns rows where any numeric feature exceeds 3σ from mean

**Validation:** `uv run ruff format app/ml/features/validation.py && uv run ruff check app/ml/features/validation.py && uv run pyright app/ml/features/validation.py`

---

### Step 6: Create CLI Entry Point

**File:** `app/ml/features/__main__.py`

```python
"""CLI entry point for ETA feature extraction (ML-2.1).

Usage:
    python -m app.ml.features.eta_features --from 2026-03-01 --to 2026-03-31 --out /tmp/features.parquet
    python -m app.ml.features.eta_features --from 2026-03-01 --to 2026-03-31 --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import datetime
import sys

from app.core.config import get_settings
from app.core.database import get_db_context
from app.core.logging import get_logger, setup_logging

logger = get_logger(__name__)
```

**Functions:**
- `_parse_args() -> argparse.Namespace` — `--from` (required, YYYY-MM-DD), `--to` (required), `--out` (Parquet path, default stdout summary), `--dry-run` (log plan without executing), `--validate` (run pandera after extraction)
- `async def _main() -> int` — Parse args, setup logging, open `get_db_context()`, call `extract_features_batch()`, optionally validate, write parquet via `df.to_parquet(path)`, log summary stats
- `if __name__ == "__main__": sys.exit(asyncio.run(_main()))`

**Validation:** `uv run ruff format app/ml/features/__main__.py && uv run ruff check app/ml/features/__main__.py && uv run pyright app/ml/features/__main__.py`

---

### Step 7: Create Alembic Migration for Materialized View

**File:** `alembic/versions/ml21_eta_features_materialized_view.py`

Generate via: `uv run alembic revision -m "add ml_eta_features_v1 materialized view"`

The materialized view joins all source tables into the 18-feature matrix. Uses `CONCURRENTLY` index for refresh support.

```python
def upgrade() -> None:
    op.execute("""
        CREATE MATERIALIZED VIEW ml_eta_features_v1 AS
        WITH trip_stops AS (
            SELECT
                t.id AS trip_id,
                t.gtfs_trip_id,
                t.direction_id,
                t.route_id AS route_fk,
                st.stop_sequence,
                st.stop_id,
                st.arrival_time,
                st.departure_time
            FROM stop_times st
            JOIN trips t ON st.trip_id = t.id
        )
        SELECT
            ts.trip_id,
            ts.stop_sequence,
            -- Categorical features derived from schedule + lookup tables
            EXTRACT(DOW FROM vp.recorded_at)::int AS day_of_week,
            EXTRACT(MONTH FROM vp.recorded_at)::int AS month,
            -- ... remaining feature columns ...
            vp.delay_seconds AS actual_delay_s
        FROM trip_stops ts
        LEFT JOIN LATERAL (
            SELECT * FROM vehicle_positions vp2
            WHERE vp2.trip_id = ts.gtfs_trip_id
            ORDER BY vp2.recorded_at
            LIMIT 1
        ) vp ON true
        -- Additional LEFT JOINs for weather, traffic
    """)
    op.execute("""
        CREATE UNIQUE INDEX CONCURRENTLY idx_eta_features_trip_stop
        ON ml_eta_features_v1 (trip_id, stop_sequence)
    """)

def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ml_eta_features_v1")
```

**Note:** The exact SQL will be refined during implementation based on data volume testing. The materialized view is a performance optimization — the Python extraction path is the source of truth.

**Validation:** `uv run alembic check` (dry-run migration validation)

---

### Step 8: Create Test Fixtures

**File:** `app/ml/features/tests/conftest.py`

Factories:
- `make_eta_features(**overrides) -> dict[str, ...]` — Returns dict with all 18 fields + sensible defaults
- `make_eta_features_df(n: int = 10) -> pd.DataFrame` — Returns DataFrame of n rows using factory
- `make_vehicle_position_row(**overrides) -> dict` — Simplified row dict for DB mock results
- `make_weather_row(**overrides) -> dict` — Weather observation row
- `mock_db_with_results(results: list) -> AsyncMock` — Pre-configured AsyncMock returning given result rows

**Validation:** `uv run ruff format app/ml/features/tests/conftest.py && uv run ruff check app/ml/features/tests/conftest.py`

---

### Step 9: Create Unit Tests

**File:** `app/ml/features/tests/test_eta_features.py`

12+ tests:

**Per-feature extraction tests (8):**
1. `test_day_of_week_extraction` — Monday=0, Sunday=6
2. `test_weather_bucket_classification` — rain/snow/fog/clear mapping from phenomena + precip
3. `test_is_school_day_logic` — Weekday + active calendar + not holiday = True
4. `test_time_of_day_hour_parsing` — "08:30:00" → 8.5, "25:00:00" → 25.0
5. `test_trip_elapsed_pct_calculation` — stop_sequence / max_sequence
6. `test_historical_avg_delay_aggregation` — Correct grouping by route/stop/hour/dow
7. `test_prev_stop_delay_first_stop` — First stop returns 0.0
8. `test_scheduled_headway_calculation` — Correct gap between consecutive trips

**Missing-data fallback tests (2):**
9. `test_missing_weather_uses_defaults` — No weather row → temp_c=0.0, wind_mps=0.0, precip=0.0
10. `test_missing_traffic_uses_defaults` — No traffic/accident data → 0.0/0 defaults

**Train/serve parity regression (1):**
11. `test_online_matches_batch_for_single_row` — `extract_features()` output matches corresponding row from `extract_features_batch()` for same (trip_id, stop_sequence, observed_at)

**Batch equivalence (1):**
12. `test_batch_returns_dataframe_with_correct_columns` — Verify all 18 columns present + correct dtypes

**Validation tests** (in test_validation.py):
13. `test_valid_features_pass_schema` — Happy path
14. `test_invalid_day_of_week_fails` — day_of_week=7 rejected
15. `test_negative_headway_fails` — negative scheduled_headway rejected
16. `test_outlier_detection_flags_extreme_values` — 100σ value flagged

**Validation:** `uv run pytest app/ml/features/tests/ -v --tb=short`

---

### Step 10: Pyright/Mypy File-Level Directives

Add to files that use pandera (which lacks type stubs):
- `app/ml/features/validation.py` — `# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false`
- `app/ml/features/tests/test_validation.py` — Same directives

Add to files that use pandas heavily:
- `app/ml/features/eta_features.py` — `# pyright: reportUnknownMemberType=false` (pandas accessor chains)
- `app/ml/features/__main__.py` — Same

**Validation:** `uv run pyright app/ml/ && uv run mypy app/ml/`

## Feature Mapping: Dataclass Fields → Source Data

| # | Feature | Type | Source Table(s) | Derivation |
|---|---------|------|-----------------|------------|
| 1 | `day_of_week` | int | `vehicle_positions.recorded_at` | `EXTRACT(DOW)` |
| 2 | `month` | int | `vehicle_positions.recorded_at` | `EXTRACT(MONTH)` |
| 3 | `is_school_day` | bool | `calendars` + `calendar_dates` | Weekday + calendar active + no holiday exception |
| 4 | `is_holiday` | bool | `calendar_dates` | `exception_type = 2` on that date |
| 5 | `weather_bucket` | str | `weather_observations.phenomena` + `precip_mm` | Python classifier function |
| 6 | `route_type` | int | `routes.route_type` | Direct lookup via trips→routes |
| 7 | `direction` | int | `trips.direction_id` | Direct lookup (default 0) |
| 8 | `operator` | str | `agencies.agency_name` | Via routes→agencies join |
| 9 | `time_of_day_hour` | float | `stop_times.arrival_time` | Parse "HH:MM:SS" → float hours |
| 10 | `scheduled_headway_s` | float | `stop_times` | Time gap to previous trip at same stop |
| 11 | `historical_avg_delay_at_stop_s` | float | `vehicle_positions` | AVG(delay_seconds) grouped by route/stop/hour/dow |
| 12 | `prev_stop_actual_delay_s` | float | `vehicle_positions` | Delay at stop_sequence-1 for same trip |
| 13 | `trip_elapsed_pct` | float | `stop_times` | stop_sequence / MAX(stop_sequence) for trip |
| 14 | `temp_c` | float | `weather_observations.temp_c` | Nearest station, nearest time (±30min) |
| 15 | `wind_mps` | float | `weather_observations.wind_mps` | Same join as temp_c |
| 16 | `precip_mm_last_hr` | float | `weather_observations.precip_mm` | Same join as temp_c |
| 17 | `traffic_count_rolling_7d` | float | `traffic_counts` | 7-day rolling avg at nearest point |
| 18 | `accident_count_within_500m` | int | `traffic_accidents` | `ST_DWithin(location, stop_location, 500)` last 30d |

## Preflight Warnings

- **No existing `app/ml/` directory** — entirely new package, no fragile existing code to break
- **pandas accessor chains** trigger pyright `reportUnknownMemberType` — use file-level directive
- **pandera** lacks `py.typed` — needs both mypy override and pyright file-level directive
- **`stop_times.arrival_time` is String(8)**, not a time type — must parse manually (supports >24:00 GTFS times)
- **`vehicle_positions.trip_id` is String(200)** matching `trips.gtfs_trip_id` (not `trips.id` FK) — join on string, not int
- **`traffic_accidents.location` is Geography** — `ST_DWithin` requires geography-compatible distance (meters, not degrees)

## Verification

- [ ] `uv sync` succeeds with new dependencies
- [ ] `uv run ruff format app/ml/ && uv run ruff check app/ml/` — 0 errors
- [ ] `uv run pyright app/ml/` — 0 errors
- [ ] `uv run mypy app/ml/` — 0 errors
- [ ] `uv run pytest app/ml/features/tests/ -v` — all 16 tests pass
- [ ] `make check` passes (full lint + types + tests — no regressions)
- [ ] Pyright errors ≤ baseline (0 in transit/, 0 in schedules/)
- [ ] `python -m app.ml.features.eta_features --help` prints usage

## Notes

- The materialized view migration (Step 7) can be deferred if the Python extraction path is sufficient for initial training runs. The view is a performance optimization for repeated reads.
- `extract_features_batch()` should use a single large SQL query with CTEs rather than N+1 per-row queries. The online `extract_features()` path can use individual queries since it processes one row at a time.
- Holiday detection for Latvia: initially use `calendar_dates` exception_type=2. A future enhancement could integrate a Latvian public holiday calendar.
- `is_school_day` is an approximation: weekday + not holiday + September-June. Exact school calendar integration deferred.
