# Plan: ML-3.1 E-Ticket ↔ GTFS-RT Correlation Pipeline

## Context

E-ticket records contain `(vehicle_number, validated_at)` but lack `stop_id`. To reconstruct per-stop passenger counts, we must join e-ticket taps against the vehicle's GPS trace at tap time, then find the nearest stop via PostGIS. This produces a trainable dataset: passenger load per (trip, stop_sequence, date).

**Operational constraint:** `vehicle_positions` has 90-day retention with compression after 7 days. The correlation pipeline MUST run within this window or GPS data is permanently lost. Nightly batch runs are mandatory, not optional.

## Security Context Assessment

**No REST endpoints** -- this is an internal ML pipeline module. No CTX-RBAC or CTX-INPUT contexts apply. SQL injection prevention via parameterized `text()` queries (existing pattern). No user-facing input.

## Research Summary

### Key Models

| Model | Table | Key Columns | File |
|-------|-------|-------------|------|
| `VehiclePositionRecord` | `vehicle_positions` | `vehicle_id` (str), `recorded_at`, `latitude`, `longitude`, `trip_id` (str, nullable) | `app/transit/models.py:19-76` |
| `EticketValidation` | `eticket_validations` | `vehicle_number` (str), `validated_at`, `route_code`, `transport_type` | `app/transit/models.py:78-105` |
| `Stop` | `stops` | `gtfs_stop_id`, `stop_lat`, `stop_lon`, `geom` (PostGIS POINT) | `app/stops/models.py:16-43` |
| `Vehicle` | `vehicles` | `fleet_number` (str, unique), `vehicle_type`, `capacity` (int, nullable) | `app/vehicles/models.py:16-53` |

### Join Key: vehicle_number ↔ vehicle_id

`eticket_validations.vehicle_number` comes from Riga transit's e-ticket system. `vehicle_positions.vehicle_id` comes from GTFS-RT feeds. These may NOT use identical formats. The `vehicles.fleet_number` column is documented as mapping to GTFS-RT `vehicle_id`.

**Strategy:** Direct join `vehicle_number = vehicle_id` as primary path. Add a correlation rate metric and log unmatched records. If correlation rate < 80%, the operator should investigate format mismatches and populate a mapping override in config. This is an expected data quality issue per the 80% target in the spec.

### Reference Feature: eta_features.py

Follow the exact same structural pattern:
- Frozen dataclass for single record output
- SQL constants in a separate `_queries.py` module
- Pandera schema for DataFrame validation
- Batch extraction function returning `pd.DataFrame`
- CLI entry point with `--dry-run`, `--validate`, `--out`
- Safe defaults (0, 0.0) when joins produce no match
- Structured logging with `get_logger(__name__)`

### PostGIS Patterns (from stops/repository.py:143-159)

```python
from geoalchemy2.functions import ST_DWithin, ST_MakePoint, ST_SetSRID, ST_Distance
# Uses geography type for meter-based radius, use_spheroid=True
```

Raw SQL pattern (from queries.py:55-61): `ST_DWithin(geom, ST_MakePoint(:lon, :lat)::geography, 100)`

### Materialized View Decision

TimescaleDB continuous aggregates cannot span two hypertables. Instead: batch extraction function writes to Parquet (like eta_features) or a regular `ml_load_features` table. For MVP, Parquet output is sufficient -- a DB-resident table can be added later when the ML training pipeline needs direct SQL access.

## Test Landscape

**Template:** `app/ml/features/tests/test_eta_features.py` (335 lines)

**Available fixtures** (from `app/ml/features/tests/conftest.py`):
- `make_eta_features_dict(**overrides)` -- all 18 fields with defaults
- `make_eta_features_df(n, **overrides)` -- n-row DataFrame
- `mock_db_session` -- AsyncMock with execute/commit
- `make_mapping_result(rows)` -- mock SQLAlchemy result proxy

**Mock patterns:** AsyncMock for DB session, substring-matched SQL dispatch in `_build_mock_db()`, MagicMock for settings. All ML tests are unit tests (no `@pytest.mark.integration`).

**Existing e-ticket test factories** (`app/transit/tests/conftest.py`):
- `make_eticket_line()`, `make_eticket_txt()`, `make_eticket_zip()`

## Type Check Baseline

| Tool | Errors | Notes |
|------|--------|-------|
| Pyright | 0 | 12 file-level directives across `app/ml/` |
| Mypy | 0 | 1 inline `type: ignore[misc]` in test |

New files must add pyright directives: `reportUnknownMemberType=false, reportUnknownVariableType=false` (for pandas/Pandera).

## Files to Create/Modify

| Action | File | Purpose |
|--------|------|---------|
| CREATE | `app/ml/features/load_queries.py` | SQL constants for spatial-temporal correlation |
| CREATE | `app/ml/features/vehicle_capacity.py` | Default capacity lookup + DB override resolution |
| CREATE | `app/ml/features/load_features.py` | Core correlation + load feature extraction |
| CREATE | `app/ml/features/load_validation.py` | Pandera schema for load features DataFrame |
| CREATE | `app/ml/features/load_cli.py` | CLI entry point (separate from eta __main__.py) |
| CREATE | `app/ml/features/tests/test_vehicle_capacity.py` | Capacity lookup tests |
| CREATE | `app/ml/features/tests/test_load_features.py` | Correlation + extraction tests |
| CREATE | `app/ml/features/tests/test_load_validation.py` | Pandera schema tests |
| UPDATE | `app/ml/features/tests/conftest.py` | Add load feature factories |
| UPDATE | `app/core/config.py` | Add ML load correlation config settings |
| UPDATE | `Makefile` | Add `make load-features` target |

## Implementation Steps

### Step 1: Config settings

**File:** `app/core/config.py` -- UPDATE

Add settings after existing ML anomaly settings (~line 186):

```python
# ML-3.1: E-ticket ↔ GTFS-RT load correlation
ml_load_time_window_seconds: int = 60  # ±60s for position match
ml_load_distance_threshold_m: float = 100.0  # ST_DWithin radius for nearest stop
ml_load_batch_size: int = 10000  # Rows per batch in correlation query
ml_load_min_correlation_pct: float = 80.0  # Warn if below this
```

**Validation:** `uv run ruff check app/core/config.py && uv run pyright app/core/config.py`

### Step 2: SQL queries

**File:** `app/ml/features/load_queries.py` -- CREATE

Three SQL constants:

1. **CORRELATE_TAPS_SQL** -- For each e-ticket validation in a time range, find the closest vehicle_position (by recorded_at, ±window) and the nearest stop (ST_DWithin, ≤threshold):
   ```sql
   SELECT
       ev.id AS eticket_id,
       ev.vehicle_number,
       ev.validated_at,
       ev.route_code,
       ev.transport_type,
       vp.trip_id AS gtfs_trip_id,
       vp.latitude AS vp_lat,
       vp.longitude AS vp_lon,
       vp.recorded_at AS position_at,
       s.id AS stop_id,
       s.gtfs_stop_id,
       st_sub.stop_sequence
   FROM eticket_validations ev
   JOIN LATERAL (
       SELECT vp2.trip_id, vp2.latitude, vp2.longitude, vp2.recorded_at
       FROM vehicle_positions vp2
       WHERE vp2.vehicle_id = ev.vehicle_number
         AND vp2.recorded_at BETWEEN ev.validated_at - INTERVAL ':window_s seconds'
                                AND ev.validated_at + INTERVAL ':window_s seconds'
       ORDER BY ABS(EXTRACT(EPOCH FROM (vp2.recorded_at - ev.validated_at)))
       LIMIT 1
   ) vp ON true
   JOIN LATERAL (
       SELECT s2.id, s2.gtfs_stop_id
       FROM stops s2
       WHERE s2.geom IS NOT NULL
         AND ST_DWithin(s2.geom, ST_SetSRID(ST_MakePoint(vp.longitude, vp.latitude), 4326)::geography, :distance_m)
       ORDER BY ST_Distance(s2.geom, ST_SetSRID(ST_MakePoint(vp.longitude, vp.latitude), 4326)::geography)
       LIMIT 1
   ) s ON true
   LEFT JOIN LATERAL (
       SELECT st2.stop_sequence
       FROM stop_times st2
       JOIN trips t ON st2.trip_id = t.id
       WHERE t.gtfs_trip_id = vp.trip_id
         AND st2.stop_id = s.id
       LIMIT 1
   ) st_sub ON true
   WHERE ev.validated_at >= :from_ts
     AND ev.validated_at < :to_ts
   ```

2. **UNCORRELATED_COUNT_SQL** -- Count e-ticket records with no position match (for correlation rate metric).

3. **TOTAL_TAPS_SQL** -- Total e-ticket count in range (for correlation rate denominator).

**Note:** The `INTERVAL ':window_s seconds'` placeholder won't work with parameterized queries. Use Python string formatting for the interval constant (it's an integer from settings, not user input) with a comment explaining why. Pattern: `f"INTERVAL '{window_s} seconds'"` where `window_s` comes from `settings.ml_load_time_window_seconds`.

**Validation:** `uv run ruff format app/ml/features/load_queries.py && uv run ruff check app/ml/features/load_queries.py && uv run pyright app/ml/features/load_queries.py`

### Step 3: Vehicle capacity lookup

**File:** `app/ml/features/vehicle_capacity.py` -- CREATE

```python
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false
"""Vehicle capacity lookup for passenger load factor calculation (ML-3.1)."""
from __future__ import annotations
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.logging import get_logger

logger = get_logger(__name__)

# Default capacities by transport type (Riga Satiksme fleet)
DEFAULT_CAPACITY: dict[str, int] = {
    "bus": 60,
    "articulated_bus": 100,  # Solaris Urbino 18
    "tram": 200,
    "trolleybus": 80,
}

CAPACITY_BY_VEHICLE_SQL = """
SELECT v.fleet_number, v.capacity, v.vehicle_type
FROM vehicles v
WHERE v.fleet_number = ANY(:vehicle_numbers)
  AND v.capacity IS NOT NULL
"""

async def get_vehicle_capacities(
    db: AsyncSession,
    vehicle_numbers: list[str],
) -> dict[str, int]:
    """Resolve capacity for each vehicle: DB override > type default > 60.

    Returns: {vehicle_number: capacity}
    """
    # 1. Query DB for explicit capacity overrides
    # 2. Fill remaining from DEFAULT_CAPACITY by transport_type
    # 3. Fallback: 60 (standard bus)
```

Pure function `get_default_capacity(transport_type: str) -> int` for the dict lookup.

**Validation:** `uv run ruff format app/ml/features/vehicle_capacity.py && uv run ruff check app/ml/features/vehicle_capacity.py && uv run pyright app/ml/features/vehicle_capacity.py`

### Step 4: Core correlation + feature extraction

**File:** `app/ml/features/load_features.py` -- CREATE

```python
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false
"""E-ticket ↔ GTFS-RT passenger load correlation pipeline (ML-3.1)."""
```

Two main functions:

**`correlate_taps_to_stops(db, from_ts, to_ts, settings) -> pd.DataFrame`**
- Execute CORRELATE_TAPS_SQL with settings-based window/distance
- Execute TOTAL_TAPS_SQL + UNCORRELATED_COUNT_SQL for correlation rate
- Log correlation rate; warn if < `ml_load_min_correlation_pct`
- Return DataFrame with columns: `eticket_id, vehicle_number, validated_at, route_code, transport_type, gtfs_trip_id, stop_id, gtfs_stop_id, stop_sequence, vp_lat, vp_lon, position_at`

**`extract_load_features(db, from_ts, to_ts, settings) -> pd.DataFrame`**
- Call `correlate_taps_to_stops()` to get raw correlations
- Call `get_vehicle_capacities()` for all distinct vehicle_numbers
- Group by (gtfs_trip_id, stop_sequence, date):
  - `tap_count`: count of e-ticket validations
  - `cumulative_load`: running sum of tap_count from stop_sequence=1 to current
  - `capacity`: from vehicle_capacity lookup
  - `load_factor_pct`: (cumulative_load / capacity) * 100, capped at 100
  - `date`: date portion of validated_at
  - `hour`: hour of first tap in group
  - `route_code`: from e-ticket record
  - `transport_type`: from e-ticket record
- Return final DataFrame

**Validation:** `uv run ruff format app/ml/features/load_features.py && uv run ruff check app/ml/features/load_features.py && uv run pyright app/ml/features/load_features.py`

### Step 5: Pandera validation schema

**File:** `app/ml/features/load_validation.py` -- CREATE

Follow `validation.py` pattern. Schema for load features DataFrame:

| Column | Type | Constraints |
|--------|------|-------------|
| `gtfs_trip_id` | str | nullable (some taps may lack trip correlation) |
| `stop_sequence` | int | nullable, >= 0 |
| `stop_id` | int | nullable |
| `date` | datetime.date | not null |
| `hour` | int | 0-23 |
| `route_code` | str | not null |
| `transport_type` | str | not null |
| `tap_count` | int | >= 1 |
| `cumulative_load` | int | >= 1 |
| `capacity` | int | >= 1 |
| `load_factor_pct` | float | 0.0-100.0 |

`validate_load_features(df) -> pd.DataFrame` -- raises `SchemaError` on failure.

**Validation:** `uv run ruff format app/ml/features/load_validation.py && uv run ruff check app/ml/features/load_validation.py && uv run pyright app/ml/features/load_validation.py`

### Step 6: CLI entry point

**File:** `app/ml/features/load_cli.py` -- CREATE

Follow `__main__.py` pattern. Separate file because eta's __main__.py is self-contained.

```
python -m app.ml.features.load_cli --from 2026-03-01 --to 2026-03-31 --out /tmp/load_features.parquet
python -m app.ml.features.load_cli --from 2026-03-01 --to 2026-03-31 --dry-run
python -m app.ml.features.load_cli --from 2026-03-01 --to 2026-03-31 --validate
```

Same structure: argparse, async `_main()`, `get_db_context()`, structured logging, Parquet output.

Add `if __name__ == "__main__"` block.

**Validation:** `uv run ruff format app/ml/features/load_cli.py && uv run ruff check app/ml/features/load_cli.py && uv run pyright app/ml/features/load_cli.py`

### Step 7: Test conftest additions

**File:** `app/ml/features/tests/conftest.py` -- UPDATE

Add factories:

```python
def make_correlated_tap(**overrides: Any) -> dict[str, Any]:
    """Factory for a single correlated e-ticket ↔ position row."""
    defaults = {
        "eticket_id": 1,
        "vehicle_number": "4521",
        "validated_at": SAMPLE_OBSERVED_AT,
        "route_code": "22",
        "transport_type": "bus",
        "gtfs_trip_id": "trip_001",
        "stop_id": 100,
        "gtfs_stop_id": "stop_100",
        "stop_sequence": 5,
        "vp_lat": 56.9496,
        "vp_lon": 24.1052,
        "position_at": SAMPLE_OBSERVED_AT + timedelta(seconds=3),
    }
    defaults.update(overrides)
    return defaults

def make_load_features_df(n: int = 5, **overrides: Any) -> pd.DataFrame:
    """Factory for load features DataFrame."""
    ...
```

**Validation:** `uv run ruff check app/ml/features/tests/conftest.py && uv run pyright app/ml/features/tests/conftest.py`

### Step 8: Vehicle capacity tests

**File:** `app/ml/features/tests/test_vehicle_capacity.py` -- CREATE

Tests (2 required):
1. `test_get_default_capacity_known_types` -- bus=60, tram=200, trolleybus=80, articulated_bus=100
2. `test_get_default_capacity_unknown_type` -- falls back to 60

Tests requiring DB mock (2 required):
3. `test_get_vehicle_capacities_db_override` -- DB returns capacity=75 for vehicle "4521", overrides default
4. `test_get_vehicle_capacities_fallback_to_type_default` -- DB returns no capacity, uses transport_type default

**Validation:** `uv run pytest app/ml/features/tests/test_vehicle_capacity.py -v && uv run pyright app/ml/features/tests/test_vehicle_capacity.py`

### Step 9: Load features tests

**File:** `app/ml/features/tests/test_load_features.py` -- CREATE

Follow `test_eta_features.py` pattern with substring-matched SQL dispatch.

**SQL pattern constants:**
```python
_CORRELATE = "eticket_validations ev"
_TOTAL_TAPS = "COUNT(*) AS total"
_UNCORRELATED = "uncorrelated"
_CAPACITY = "v.fleet_number, v.capacity"
```

**Tests (12+ required):**

Spatial-temporal join correctness (3):
1. `test_correlate_single_tap_matches_position` -- one e-ticket, one position within window → matched
2. `test_correlate_no_position_in_window` -- position outside ±60s → not in result
3. `test_correlate_nearest_stop_within_radius` -- position maps to closest stop ≤100m

Capacity lookup (2):
4. `test_capacity_from_db_override` -- vehicle has explicit capacity
5. `test_capacity_default_by_transport_type` -- no DB record, uses type default

Load factor math (2):
6. `test_load_factor_calculation` -- 30 taps, capacity 60 = 50%
7. `test_cumulative_load_across_stops` -- stop 1: 10 taps, stop 2: 5 taps → cumulative at stop 2 = 15

Unmatched record handling (2):
8. `test_correlation_rate_logged_above_threshold` -- ≥80% correlation, info log
9. `test_correlation_rate_warning_below_threshold` -- <80%, warning log

Feature determinism (1):
10. `test_same_input_produces_same_output` -- run twice, compare DataFrames

Per-vehicle override resolution (2):
11. `test_mixed_vehicles_different_capacities` -- two vehicles, different types, correct capacities
12. `test_vehicle_with_no_capacity_or_type` -- unknown vehicle, fallback to 60

**Validation:** `uv run pytest app/ml/features/tests/test_load_features.py -v && uv run pyright app/ml/features/tests/test_load_features.py`

### Step 10: Validation schema tests

**File:** `app/ml/features/tests/test_load_validation.py` -- CREATE

Tests:
1. `test_valid_load_features_pass` -- well-formed DataFrame passes
2. `test_negative_tap_count_fails` -- tap_count < 1 rejected
3. `test_load_factor_out_of_range_fails` -- load_factor_pct > 100 rejected
4. `test_hour_out_of_range_fails` -- hour > 23 rejected

**Validation:** `uv run pytest app/ml/features/tests/test_load_validation.py -v`

### Step 11: Makefile target

**File:** `Makefile` -- UPDATE

Add after `gtfs-backfill` targets:

```makefile
# ML-3.1: E-ticket ↔ GTFS-RT passenger load correlation
load-features:
	uv run python -m app.ml.features.load_cli --from $(FROM) --to $(TO) --out $(OUT) --validate

load-features-dry-run:
	uv run python -m app.ml.features.load_cli --from $(FROM) --to $(TO) --dry-run
```

**Validation:** `make help | grep load`

## Preflight Warnings

- `vehicle_positions` has **90-day retention** -- correlation MUST run within this window
- `trip_id` in `vehicle_positions` is a **STRING** (GTFS-RT identifier), not integer FK. Join with `trips.gtfs_trip_id`
- `eticket_validations.vehicle_number` and `vehicle_positions.vehicle_id` may use **different formats** -- monitor correlation rate
- LATERAL JOINs on compressed hypertable chunks may be slow -- add `EXPLAIN ANALYZE` logging for batch sizes > 50k
- PostGIS `ST_DWithin` with `::geography` cast is required for meter-based radius (not `geometry`)

## Verification

- [ ] `uv run ruff format app/ml/features/ && uv run ruff check --fix app/ml/features/` passes
- [ ] `uv run pyright app/ml/` -- 0 errors (baseline: 0)
- [ ] `uv run mypy app/ml/` -- 0 errors (baseline: 0)
- [ ] `uv run pytest app/ml/features/tests/ -v` -- all tests pass
- [ ] `make check` passes (lint + types + full test suite)
- [ ] No new REST endpoints (no security convention test updates needed)
- [ ] Correlation rate logging works: info when ≥80%, warning when <80%
