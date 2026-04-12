# Plan: ML-1.3 Weather + Traffic Observations ETL

## Context

ETA prediction models need weather context (rain +15% delay, snow +40% delay) and traffic data (congestion factors, accident hotspots). This feature adds scheduled ETL pullers that ingest data from external sources into 4 new PostGIS-enabled tables for later spatial joins against stops/routes (ML-2.3).

Datasets update at different cadences: weather hourly, traffic counts daily, accidents annually — each needs its own scheduler and idempotent upsert logic.

## Security Context Assessment

**CTX-INPUT** — Active. External CSV parsing from government data sources. Must handle encoding errors, malformed rows, unexpected column counts defensively. Skip bad rows with warning logs, never crash the ETL.

CTX-RBAC, CTX-AUTH — Not active. No REST endpoints exposed; this is internal background ETL only.
CTX-INFRA — Mild. New config settings for external URLs and enable flags.

## Research Summary

### Existing Patterns to Follow

| Pattern | Reference File | Lines |
|---------|---------------|-------|
| TimescaleDB hypertable model (no TimestampMixin) | `app/transit/models.py` | 18-75 |
| Hypertable migration + compression + retention | `alembic/versions/b7c8d9e0f1a2_add_vehicle_positions_hypertable.py` | 21-85 |
| PostGIS Geometry column + GIST index | `app/geofences/models.py` | 53-56 |
| PostGIS migration + extension | `alembic/versions/b039c337be87_add_postgis_geometry_to_stops.py` | 24-61 |
| Hourly polling loop (`while running: poll; sleep`) | `app/transit/poller.py` | 281-298 |
| Daily scheduled task (`_run_at_hour`) | `app/memory/lifecycle.py` | 25-42 |
| Leader election via Redis SETNX | `app/transit/poller.py` | 307-345 |
| Circuit breaker for HTTP calls | `app/core/resilience.py` | 49-60 |
| Batch insert pattern | `app/transit/repository.py` | 29-51 |
| JSONB column on model | `app/transit/models.py` | 67 |
| Lifecycle start_/stop_ in lifespan | `app/main.py` | 109-150 |
| Config settings grouping | `app/core/config.py` | 85-159 |
| Backfill script pattern | `scripts/rechunk_documents.py` | 1-100+ |
| Makefile backfill target | `Makefile` | 101-105 |

### Key Decisions

1. **Geography vs Geometry** — Use `Geography("POINT", srid=4326)` from geoalchemy2 (not `Geometry`). Geography computes distances in meters natively, which ML-2.3 spatial joins need. Differs from existing stops/geofences which use `Geometry`.
2. **No TimestampMixin on hypertable** — Follow `VehiclePositionRecord` precedent. Use `observed_at` as partition column.
3. **Two scheduler patterns** — Hourly weather: FeedPoller-style `while running: poll; sleep(interval)`. Daily traffic: `_run_at_hour` from memory lifecycle.
4. **Leader election** — Separate Redis lock key `vtv:weather_etl:leader` prevents duplicate pulls across Gunicorn workers.
5. **External URLs in config** — Empty-string defaults with `_enabled` flags. Real URLs configured via env vars. No hardcoded government service URLs.

## Test Landscape

- Transit tests: 11 test files in `app/transit/tests/`
- No transit `conftest.py` — tests use module-level `_make_*` helpers
- HTTP mocking: `AsyncMock()` on httpx clients, no `respx` library
- CSV parsing: GTFS importer tests use `io.BytesIO` + `csv.DictReader` (see `app/schedules/tests/test_shapes.py`)
- Background task tests: `patch("...asyncio.create_task")` + `MagicMock()` (see `app/memory/tests/test_lifecycle.py`)
- DB context mock: `patch("...get_db_context")` returning `AsyncMock().__aenter__` (see `app/alerts/tests/test_evaluator.py`)

## Type Check Baseline

| Tool | Target | Errors |
|------|--------|--------|
| Pyright | `app/transit/` | **0** |
| Mypy | `app/transit/` (23 files) | **0** |
| Pyright | `app/main.py` | **0** |

## Files to Create/Modify

| Action | File | Purpose |
|--------|------|---------|
| CREATE | `alembic/versions/k4l5m6n7o8p9_weather_traffic_tables.py` | 4 new tables with PostGIS + hypertable |
| CREATE | `app/transit/weather_models.py` | SQLAlchemy models: WeatherStation, WeatherObservation |
| CREATE | `app/transit/traffic_models.py` | SQLAlchemy models: TrafficCount, TrafficAccident |
| CREATE | `app/transit/weather_etl.py` | Weather ETL: fetch, parse CSV, upsert, hourly scheduler, backfill |
| CREATE | `app/transit/traffic_etl.py` | Traffic ETL: fetch, parse CSV, upsert, daily scheduler, annual backfill |
| UPDATE | `app/core/config.py` | Add weather/traffic ETL settings |
| UPDATE | `app/main.py` | Register weather/traffic ETL in lifespan |
| UPDATE | `Makefile` | Add `weather-backfill` and `traffic-backfill` targets |
| CREATE | `scripts/weather_backfill.py` | One-shot historical weather backfill script |
| CREATE | `scripts/traffic_backfill.py` | One-shot traffic accident/count backfill script |
| CREATE | `app/transit/tests/test_weather_etl.py` | Weather ETL unit tests |
| CREATE | `app/transit/tests/test_traffic_etl.py` | Traffic ETL unit tests |

## Implementation Steps

### Step 1: Config settings (`app/core/config.py`)

Add after the `position_history_*` block (~line 159):

```python
# Weather ETL (ML-1.3)
weather_etl_enabled: bool = False
weather_station_url: str = ""  # data.gov.lv weather station metadata endpoint
weather_observations_url: str = ""  # data.gov.lv operative meteorological data endpoint
weather_phenomena_url: str = ""  # data.gov.lv road weather phenomena endpoint
weather_etl_interval_seconds: int = 3600  # 1 hour
weather_etl_leader_lock_ttl: int = 120
weather_history_retention_days: int = 365

# Traffic ETL (ML-1.3)
traffic_etl_enabled: bool = False
traffic_counts_url: str = ""  # data.lvceli.lv traffic count endpoint
traffic_accidents_url: str = ""  # CAIS accident dataset endpoint
traffic_etl_cron_hour: int = 4  # Daily pull at 04:00 UTC
```

**Validation:** `uv run ruff check app/core/config.py && uv run pyright app/core/config.py`

### Step 2: Weather models (`app/transit/weather_models.py`)

```python
"""SQLAlchemy models for weather observation storage (ML-1.3).

weather_observations is a TimescaleDB hypertable partitioned by observed_at.
Does not use TimestampMixin (same rationale as VehiclePositionRecord).
"""
```

Models:
- **WeatherStation**: `station_id` (str PK), `name` (str), `location` (Geography POINT 4326)
- **WeatherObservation**: `id` (int PK auto), `station_id` (FK → weather_stations), `observed_at` (DateTime tz, partition col), `temp_c` (Float nullable), `wind_mps` (Float nullable), `precip_mm` (Float nullable), `phenomena` (JSONB nullable), `location` (Geography POINT 4326 nullable)
  - `__table_args__`: UniqueConstraint(`station_id`, `observed_at`, name=`uq_weather_obs_station_time`), Index on (`station_id`, `observed_at`)

Use `from geoalchemy2 import Geography  # pyright: ignore[reportMissingTypeStubs]` and `Geography("POINT", srid=4326)  # pyright: ignore[reportUnknownArgumentType]`.

**Validation:** `uv run ruff check app/transit/weather_models.py && uv run pyright app/transit/weather_models.py`

### Step 3: Traffic models (`app/transit/traffic_models.py`)

Models:
- **TrafficCount**: `id` (int PK auto), `point_id` (str), `period_start` (Date), `period_end` (Date), `avg_count_per_day` (Float), `vehicle_class` (str nullable), `location` (Geography POINT 4326 nullable)
  - `__table_args__`: UniqueConstraint(`point_id`, `period_start`, `period_end`, `vehicle_class`, name=`uq_traffic_count_key`)
- **TrafficAccident**: `id` (int PK auto), `source_id` (str unique), `occurred_at` (DateTime tz), `severity` (str), `fatalities` (int default 0), `injuries` (int default 0), `location` (Geography POINT 4326 nullable)

**Validation:** `uv run ruff check app/transit/traffic_models.py && uv run pyright app/transit/traffic_models.py`

### Step 4: Alembic migration

Create `alembic/versions/k4l5m6n7o8p9_weather_traffic_tables.py` depending on head `9d9e77b5b0bf`.

`upgrade()`:
1. `CREATE EXTENSION IF NOT EXISTS postgis` (idempotent)
2. `op.create_table("weather_stations", ...)` with Geography column
3. `op.create_table("weather_observations", ...)` with FK, unique constraint, indexes
4. Check TimescaleDB availability → `create_hypertable('weather_observations', 'observed_at', chunk_time_interval => INTERVAL '1 day')` + compression + retention policy (`weather_history_retention_days` default 365)
5. `op.create_table("traffic_counts", ...)` with unique constraint
6. `op.create_table("traffic_accidents", ...)` with unique source_id index
7. GIST spatial indexes on all Geography columns

`downgrade()`: Drop tables in reverse order, remove TimescaleDB policies first.

**Validation:** `uv run alembic check` (no DB needed, just syntax)

### Step 5: Weather ETL (`app/transit/weather_etl.py`)

Structure:
```
Module-level:
  logger = get_logger(__name__)
  _weather_task: asyncio.Task[None] | None = None
  _weather_breaker = CircuitBreaker(name="weather-etl", failure_threshold=3, reset_timeout=300.0)

Functions:
  parse_weather_csv(text: str) -> list[dict[str, object]]
    - csv.DictReader on io.StringIO(text)
    - Skip rows with missing station_id/observed_at
    - Log warning per skipped row: "transit.weather.row_skipped"
    - Return list of dicts ready for upsert

  parse_phenomena_csv(text: str) -> dict[str, dict[str, object]]
    - Returns {station_id+timestamp: phenomena_dict} for JSONB merge

  async upsert_observations(db: AsyncSession, records: list[dict[str, object]]) -> int
    - Use INSERT ... ON CONFLICT (station_id, observed_at) DO UPDATE
    - For phenomena merge: jsonb_set or ||  operator to merge JSONB
    - Return count of rows affected

  async pull_meteo_observations(http_client: httpx.AsyncClient, settings: Settings) -> int
    - Fetch CSV from settings.weather_observations_url
    - Parse with parse_weather_csv()
    - Also fetch phenomena from settings.weather_phenomena_url
    - Merge phenomena into observations by station_id+timestamp
    - Upsert via get_db_context()
    - Log: "transit.weather.pull_completed" {count, duration_ms}
    - Return count

  async _weather_poll_loop() -> None
    - Acquire Redis leader lock (vtv:weather_etl:leader)
    - while _running: pull_meteo_observations(); sleep(interval)
    - Log per cycle: "transit.weather.cycle_completed"
    - Catch all exceptions per cycle (never crash loop)

  async start_weather_etl() -> None
    - Check settings.weather_etl_enabled
    - asyncio.create_task(_weather_poll_loop())
    - Log: "transit.weather.lifecycle_started"

  async stop_weather_etl() -> None
    - Cancel task, handle CancelledError
    - Log: "transit.weather.lifecycle_stopped"

  async backfill_weather(days: int = 365) -> int
    - One-shot: fetch archive data, upsert
    - Used by scripts/weather_backfill.py
```

**Validation:** `uv run ruff format app/transit/weather_etl.py && uv run ruff check --fix app/transit/weather_etl.py && uv run pyright app/transit/weather_etl.py`

### Step 6: Traffic ETL (`app/transit/traffic_etl.py`)

Structure:
```
Module-level:
  logger = get_logger(__name__)
  _traffic_task: asyncio.Task[None] | None = None

Functions:
  parse_traffic_counts_csv(text: str) -> list[dict[str, object]]
  parse_traffic_accidents_csv(text: str) -> list[dict[str, object]]

  async upsert_traffic_counts(db: AsyncSession, records: list[dict[str, object]]) -> int
    - ON CONFLICT (point_id, period_start, period_end, vehicle_class) DO UPDATE

  async upsert_traffic_accidents(db: AsyncSession, records: list[dict[str, object]]) -> int
    - ON CONFLICT (source_id) DO UPDATE

  async pull_traffic_counts(http_client: httpx.AsyncClient, settings: Settings) -> int
  async pull_traffic_accidents(http_client: httpx.AsyncClient, settings: Settings) -> int

  async _run_daily_traffic_pull() -> None
    - Uses _run_at_hour pattern (copy from memory/lifecycle.py, parameterized)
    - Runs at settings.traffic_etl_cron_hour (default 04:00 UTC)
    - Leader lock: vtv:traffic_etl:leader

  async start_traffic_etl() -> None
  async stop_traffic_etl() -> None

  async backfill_traffic_counts() -> int
  async backfill_traffic_accidents() -> int
```

**Validation:** `uv run ruff format app/transit/traffic_etl.py && uv run ruff check --fix app/transit/traffic_etl.py && uv run pyright app/transit/traffic_etl.py`

### Step 7: Lifespan integration (`app/main.py`)

After the `await start_memory_tasks()` block (~line 122), add:

```python
# Start weather ETL background task (ML-1.3)
from app.transit.weather_etl import start_weather_etl
await start_weather_etl()

# Start traffic ETL background task (ML-1.3)
from app.transit.traffic_etl import start_traffic_etl
await start_traffic_etl()
```

In shutdown section (before `await stop_memory_tasks()`):

```python
from app.transit.weather_etl import stop_weather_etl
from app.transit.traffic_etl import stop_traffic_etl
await stop_weather_etl()
await stop_traffic_etl()
```

**Validation:** `uv run pyright app/main.py`

### Step 8: Backfill scripts

**`scripts/weather_backfill.py`** — Following `scripts/rechunk_documents.py` pattern:
- `argparse` with `--dry-run`, `--days` (default 365)
- `sys.path.insert(0, ...)` for app imports
- `asyncio.run(main())`
- Calls `backfill_weather(days=args.days)`

**`scripts/traffic_backfill.py`** — Same pattern:
- `argparse` with `--dry-run`, `--type` (counts|accidents|all)
- Calls `backfill_traffic_counts()` and/or `backfill_traffic_accidents()`

**Validation:** `uv run ruff check scripts/weather_backfill.py scripts/traffic_backfill.py`

### Step 9: Makefile targets

Add after `rechunk-dry-run` target:

```makefile
weather-backfill: ## Backfill weather observations from archive (ML-1.3)
	uv run python scripts/weather_backfill.py

traffic-backfill: ## Backfill traffic counts and accidents (ML-1.3)
	uv run python scripts/traffic_backfill.py
```

Update `.PHONY` line to include `weather-backfill traffic-backfill`.

**Validation:** `make help | grep -E "weather|traffic"`

### Step 10: Weather ETL tests (`app/transit/tests/test_weather_etl.py`)

Tests (15+ total, split across weather and traffic):

**CSV parsing (3):**
1. `test_parse_weather_csv_valid_rows` — Happy path: 3 rows parsed correctly
2. `test_parse_weather_csv_missing_required_fields` — Rows without station_id/observed_at skipped
3. `test_parse_weather_csv_malformed_numbers` — Non-numeric temp/wind handled gracefully

**Phenomena JSONB merge (2):**
4. `test_parse_phenomena_csv_groups_by_station_time` — Phenomena grouped correctly
5. `test_upsert_merges_phenomena_jsonb` — Existing JSONB merged with new phenomena data

**Upsert idempotency (2):**
6. `test_upsert_observations_conflict_updates` — ON CONFLICT updates existing row
7. `test_upsert_observations_empty_list_noop` — Empty input returns 0

**PostGIS location encoding (1):**
8. `test_observation_record_has_geography_point` — Model column is Geography POINT 4326

**Scheduled task gating (2):**
9. `test_start_weather_etl_creates_task_when_enabled` — Task created when `weather_etl_enabled=True`
10. `test_start_weather_etl_skips_when_disabled` — No task when disabled

**HTTP failure (1):**
11. `test_pull_meteo_observations_http_error_logged` — httpx error logged, not raised

**Stop semantics (1):**
12. `test_stop_weather_etl_cancels_task` — Task cancelled and awaited

**Validation:** `uv run pytest app/transit/tests/test_weather_etl.py -v`

### Step 11: Traffic ETL tests (`app/transit/tests/test_traffic_etl.py`)

**CSV parsing (2):**
1. `test_parse_traffic_counts_csv_valid` — Happy path
2. `test_parse_traffic_accidents_csv_valid` — Happy path with severity/location

**Upsert idempotency (2):**
3. `test_upsert_traffic_counts_conflict_updates` — ON CONFLICT on composite key
4. `test_upsert_traffic_accidents_conflict_on_source_id` — ON CONFLICT on source_id

**Scheduled task (2):**
5. `test_start_traffic_etl_creates_task_when_enabled`
6. `test_stop_traffic_etl_cancels_task`

**Validation:** `uv run pytest app/transit/tests/test_traffic_etl.py -v`

## Preflight Warnings

- `app/transit/tests/test_poller.py` uses `_make_feed_config()` and `_make_mock_settings()` — new ETL tests should NOT modify these; create separate helpers.
- `app/main.py` lifespan has exact ordering of start/stop calls — insert weather/traffic ETL between memory tasks and reranker warmup (startup) and before `stop_memory_tasks` (shutdown).
- `app/core/config.py` Settings class is large (~300 lines). Add new settings in a clearly marked section. Don't interleave with existing groups.

## Security Checklist

No REST endpoints exposed, but CSV parsing from external sources requires:
- [ ] Skip rows with missing required fields (log warning, don't crash)
- [ ] Handle encoding errors in CSV (`errors="replace"` or `errors="ignore"`)
- [ ] Limit response size on HTTP fetch (cap at 50MB to prevent memory exhaustion)
- [ ] Validate numeric fields before DB insert (reject NaN, inf)
- [ ] No credential exposure in logs (URLs may contain API keys → use `_redact_url`)
- [ ] Leader election prevents duplicate concurrent pulls

## Verification

- [ ] `make check` passes (lint + types + tests)
- [ ] `make security-audit-quick` passes
- [ ] Pyright errors ≤ baseline (0 errors before)
- [ ] `uv run pytest app/transit/tests/test_weather_etl.py app/transit/tests/test_traffic_etl.py -v` — 17+ tests pass
- [ ] `make weather-backfill` and `make traffic-backfill` targets exist
- [ ] `uv run alembic upgrade head` succeeds (if DB running)
- [ ] Background tasks log `transit.weather.lifecycle_started` and `transit.traffic.lifecycle_started` on app start (when enabled)
