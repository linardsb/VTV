# Plan: ML-4.2 Stuck Vehicle + GPS Gap Detection

## Context

Two anomaly detectors for the `app/ml/anomaly/` package:
1. **Stuck Vehicle** — vehicle moved < 20m over last 10 min during active trip. Catches breakdowns, accidents, traffic pileups.
2. **GPS Gap** — no position updates from active vehicle in last 5 min. Catches hardware failures, driver offline, feed outages.

Feed-wide gap suppression: if >= 50% of a feed's vehicles gap simultaneously, fire one `feed_outage` alert instead of per-vehicle spam.

## Security Context Assessment

**Active:** CTX-INPUT (TimescaleDB queries from vehicle data), CTX-INFRA (new config settings, background task lifecycle)
**Not active:** CTX-AUTH, CTX-RBAC (no new endpoints), CTX-FILE, CTX-AGENT

## Research Summary

### Reference Pattern
`app/geofences/evaluator.py` — complete background evaluator with Redis state, DB ops, alert creation, lifecycle start/stop. **This is the primary template.**

### Key Models
- `VehiclePositionRecord` (`app/transit/models.py:19-76`): `vehicle_id`, `latitude`, `longitude`, `recorded_at`, `trip_id`, `current_status`, `feed_id`, `speed_kmh`. Index: `(vehicle_id, recorded_at)`.
- `StopTime` (`app/schedules/models.py:125-147`): `trip_id` (FK int), `stop_sequence`, `arrival_time` (str "HH:MM:SS"), `departure_time` (str). For layover exclusion.
- `AlertInstanceCreate` (`app/alerts/schemas.py:79-82`): `title`, `severity`, `alert_type` (Literal), `source_entity_type`, `source_entity_id`, `details`, `rule_id`.

### Alert Type Extension
`AlertRuleType` in `app/alerts/schemas.py:11-19` is a `Literal[...]`. Must add `"stuck_vehicle"`, `"gps_gap"`, `"feed_outage"`. Only 3 files reference it: `app/alerts/schemas.py`, `app/geofences/README.md` (docs only), `.agents/plans/` (docs only). Safe to extend.

### Infrastructure
- `get_db_context()` from `app/core/database` for background task sessions
- `get_redis()` from `app/core/redis` for cooldown keys
- `AlertInstanceRepository` from `app/alerts/repository` for alert creation + dedup via `find_active_duplicate()`
- `record_poller_tick()` from `app/core/metrics` for liveness gauge
- `get_settings()` from `app/core/config` for thresholds
- Lifespan in `app/main.py:76-169` — add start/stop calls

## Test Landscape

### Factories Available
- `_make_vehicle_position()` in `app/transit/tests/test_service.py` — `VehiclePositionData` (not the DB model)
- `make_stop_time()` in `app/schedules/tests/conftest.py`
- `make_alert_instance()` in `app/alerts/tests/conftest.py`

### Mock Patterns
- Redis: `MagicMock()` for pipeline (anti-pattern #35), `AsyncMock()` for get/set
- DB context: patch `get_db_context` returning `AsyncMock(__aenter__=..., __aexit__=...)`
- Repositories: `AsyncMock()` instances
- `scan_iter`: async generator function assigned to mock attribute

### Reference Test File
`app/geofences/tests/test_evaluator.py` — closest pattern (background evaluator tests)

## Type Check Baseline

`app/ml/` does not exist — creating from scratch. All adjacent directories are **zero errors** (pyright + mypy): `app/transit/`, `app/alerts/`, `app/geofences/`, `app/schedules/`.

## Files to Create/Modify

| Action | File | Purpose |
|--------|------|---------|
| CREATE | `app/ml/__init__.py` | ML package init |
| CREATE | `app/ml/anomaly/__init__.py` | Anomaly detection sub-package init |
| CREATE | `app/ml/anomaly/stuck.py` | StuckVehicleEvaluator — 10-min window, < 20m movement |
| CREATE | `app/ml/anomaly/gps_gap.py` | GPSGapEvaluator — 5-min no-update + feed-wide suppression |
| CREATE | `app/ml/anomaly/evaluator.py` | Background loop orchestrating both detectors |
| CREATE | `app/ml/tests/__init__.py` | Test package init |
| CREATE | `app/ml/tests/conftest.py` | Shared fixtures and factories |
| CREATE | `app/ml/tests/test_stuck.py` | Stuck detection tests (7 tests) |
| CREATE | `app/ml/tests/test_gps_gap.py` | GPS gap detection tests (6 tests) |
| CREATE | `app/ml/tests/test_evaluator.py` | Orchestrator lifecycle tests (2 tests) |
| UPDATE | `app/alerts/schemas.py:11-19` | Add "stuck_vehicle", "gps_gap", "feed_outage" to AlertRuleType |
| UPDATE | `app/core/config.py` | Add ML anomaly settings (enabled, intervals, thresholds) |
| UPDATE | `app/main.py` | Add start/stop for anomaly evaluator in lifespan |

## Implementation Steps

### Step 1: Extend AlertRuleType
**File:** `app/alerts/schemas.py`
**Action:** Add 3 new literals to `AlertRuleType`:
```python
AlertRuleType = Literal[
    "delay_threshold",
    "maintenance_due",
    "registration_expiry",
    "manual",
    "geofence_enter",
    "geofence_exit",
    "geofence_dwell",
    "stuck_vehicle",
    "gps_gap",
    "feed_outage",
]
```
**Validation:** `uv run ruff check app/alerts/schemas.py && uv run pyright app/alerts/schemas.py`

### Step 2: Add Config Settings
**File:** `app/core/config.py`
**Action:** Add to `Settings` class:
```python
# ML anomaly detection (ML-4.2)
ml_anomaly_evaluator_enabled: bool = True
ml_anomaly_check_interval_seconds: int = 60
ml_stuck_distance_threshold_m: float = 20.0
ml_stuck_time_window_minutes: int = 10
ml_gps_gap_threshold_minutes: int = 5
ml_gps_gap_feed_outage_pct: int = 50
ml_anomaly_cooldown_seconds: int = 900  # 15-min cooldown per vehicle per alert type
```
**Validation:** `uv run pyright app/core/config.py`

### Step 3: Create Package Structure
**Files:** `app/ml/__init__.py`, `app/ml/anomaly/__init__.py`, `app/ml/tests/__init__.py`
**Action:** Empty `__init__.py` files.

### Step 4: Create StuckVehicleEvaluator
**File:** `app/ml/anomaly/stuck.py`
**Action:** Create class with:
- `async def check(self, db: AsyncSession, redis: Redis, settings: Settings) -> list[AlertInstanceCreate]`
- Query `vehicle_positions` for last N minutes per vehicle with active `trip_id`
- Compute total distance via haversine between consecutive positions (using `app.shared.geo.haversine_distance`)
- Exclude vehicles at terminal/scheduled layover stops: cross-reference `StopTime` where current time is between `arrival_time` and `departure_time` at last `stop_sequence`
- Redis cooldown check: `ml:stuck:{vehicle_id}` with TTL from settings
- Return list of `AlertInstanceCreate` objects ready to persist

Key design decisions:
- Use raw SQL via `text()` for the TimescaleDB window query (matches `app/transit/repository.py` pattern)
- Haversine for distance (not PostGIS ST_Distance, since we have lat/lon floats not geometry columns)
- Cooldown via Redis SET with EX, check via GET before creating alert

**Validation:** `uv run ruff format app/ml/anomaly/stuck.py && uv run ruff check --fix app/ml/anomaly/stuck.py && uv run pyright app/ml/anomaly/stuck.py`

### Step 5: Create GPSGapEvaluator
**File:** `app/ml/anomaly/gps_gap.py`
**Action:** Create class with:
- `async def check(self, db: AsyncSession, redis: Redis, settings: Settings) -> list[AlertInstanceCreate]`
- Query `MAX(recorded_at)` per `vehicle_id` grouped by `feed_id` where `trip_id IS NOT NULL`
- If `NOW() - MAX(recorded_at) > gap_threshold` for a vehicle, it's a gap candidate
- Feed-wide suppression: count gap vehicles per feed. If `gap_count / total_count >= feed_outage_pct / 100`, emit one `feed_outage` alert per feed instead of per-vehicle `gps_gap` alerts
- Redis cooldown: `ml:gps_gap:{vehicle_id}` and `ml:feed_outage:{feed_id}` keys

**Validation:** `uv run ruff format app/ml/anomaly/gps_gap.py && uv run ruff check --fix app/ml/anomaly/gps_gap.py && uv run pyright app/ml/anomaly/gps_gap.py`

### Step 6: Create Background Evaluator Orchestrator
**File:** `app/ml/anomaly/evaluator.py`
**Action:** Follow `app/geofences/evaluator.py` pattern exactly:
- `_evaluator_task: asyncio.Task[None] | None = None`
- `async def evaluate_anomalies_once() -> int` — runs both StuckVehicleEvaluator and GPSGapEvaluator, persists alerts via `AlertInstanceRepository`, deduplicates via `find_active_duplicate()`, returns count
- `async def _evaluator_loop(interval: int) -> None` — sleep-check-log loop with `CancelledError` + `Exception` handling
- `async def start_anomaly_evaluator(settings: Settings) -> None` — guarded by `settings.ml_anomaly_evaluator_enabled`
- `async def stop_anomaly_evaluator() -> None` — cancel + await with error handling
- `record_poller_tick("anomaly_evaluator")` on success
- Logging: `ml.anomaly_evaluator.{action}_{state}` pattern

Add pyright file-level directive (line 1): `# pyright: reportUnknownMemberType=false, reportMissingTypeStubs=false` (for Redis types, matching geofence evaluator)

**Validation:** `uv run pyright app/ml/anomaly/evaluator.py`

### Step 7: Wire Into Lifespan
**File:** `app/main.py`
**Action:**
- Add import at top (with other evaluator imports ~line 24-46): `from app.ml.anomaly.evaluator import start_anomaly_evaluator, stop_anomaly_evaluator`
- In startup (after geofence evaluator, ~line 123): `await start_anomaly_evaluator(settings)`
- In shutdown: register via `ShutdownCoordinator` (NOT direct `await stop_*()`). Add after the geofence_evaluator registration (~line 184):
  ```python
  coordinator.register(
      ShutdownTask(name="anomaly_evaluator", drain_timeout_s=3.0, drain=stop_anomaly_evaluator)
  )
  ```
  **IMPORTANT:** The codebase uses `ShutdownCoordinator` + `ShutdownTask` for all shutdown logic (see `app/core/shutdown.py`). Do NOT use direct `await stop_*()` calls.

**Validation:** `uv run pyright app/main.py`

### Step 8: Create Test Conftest
**File:** `app/ml/tests/conftest.py`
**Action:** Create shared fixtures:
- `make_vehicle_position_record(**overrides)` — factory for `VehiclePositionRecord` model instances (not the transit `VehiclePositionData` schema)
- `mock_redis()` — `MagicMock()` with async get/set
- `mock_settings()` — `MagicMock(spec=Settings)` with ML anomaly defaults

### Step 9: Create Stuck Detection Tests
**File:** `app/ml/tests/test_stuck.py`
**Action:** 7 tests:
1. `test_stuck_vehicle_detected` — vehicle with < 20m movement over 10 min, active trip -> returns alert
2. `test_vehicle_moving_normally` — vehicle with > 20m movement -> no alert
3. `test_no_positions_in_window` — no recent positions -> no alert (not stuck, just no data)
4. `test_terminal_stop_excluded` — vehicle at last stop_sequence of trip -> no alert
5. `test_layover_excluded` — vehicle at stop within arrival/departure window -> no alert
6. `test_cooldown_suppresses_duplicate` — Redis cooldown key exists -> no alert
7. `test_cooldown_expired_fires_again` — Redis cooldown key absent -> alert fires

Mock patterns: patch `get_db_context`, `get_redis`. Mock `db.execute()` returning position rows. Mock `redis.get()` for cooldown checks, `redis.set()` for cooldown writes.

**Validation:** `uv run pytest app/ml/tests/test_stuck.py -v`

### Step 10: Create GPS Gap Detection Tests
**File:** `app/ml/tests/test_gps_gap.py`
**Action:** 6 tests:
1. `test_gps_gap_detected` — vehicle with no updates for 6 min during active trip -> alert
2. `test_vehicle_recently_updated` — last update 2 min ago -> no alert
3. `test_feed_wide_suppression` — 80% of feed vehicles have gap -> one `feed_outage`, no per-vehicle alerts
4. `test_partial_feed_gap_no_suppression` — 30% gap -> per-vehicle `gps_gap` alerts, no `feed_outage`
5. `test_cooldown_suppresses_gap_alert` — Redis cooldown active -> skip
6. `test_feed_outage_cooldown` — feed_outage cooldown key exists -> skip duplicate feed alert

**Validation:** `uv run pytest app/ml/tests/test_gps_gap.py -v`

### Step 11: Create Evaluator Orchestrator Tests
**File:** `app/ml/tests/test_evaluator.py`
**Action:** 2 tests:
1. `test_evaluate_anomalies_once_creates_alerts` — both detectors return alerts, all persisted via repository
2. `test_evaluate_anomalies_handles_errors` — one detector raises Exception, other still runs, error logged

**Validation:** `uv run pytest app/ml/tests/test_evaluator.py -v`

### Step 12: Full Validation
Run complete suite:
```bash
uv run ruff format app/ml/ app/alerts/schemas.py app/core/config.py app/main.py
uv run ruff check --fix app/ml/ app/alerts/schemas.py app/core/config.py app/main.py
uv run pyright app/ml/ app/alerts/schemas.py app/core/config.py app/main.py
uv run mypy app/ml/ app/alerts/schemas.py app/core/config.py app/main.py
uv run pytest app/ml/tests/ -v
uv run pytest app/alerts/tests/ -v  # regression check for AlertRuleType change
```

## Design Decisions

1. **No shared base class yet** — per three-feature rule, `BaseAnomalyEvaluator` extraction happens when the 3rd detector lands (ML-4.3+). For now, `StuckVehicleEvaluator` and `GPSGapEvaluator` are standalone classes.
2. **Distance in Python, not SQL** — `vehicle_positions` stores `float` lat/lon, not PostGIS geometry. SQL fetches `(vehicle_id, latitude, longitude, recorded_at)` rows for the time window. Python-side `haversine_distance()` from `app.shared.geo` computes total distance per vehicle by iterating consecutive positions. This is simpler to test and sufficient for ~500 vehicles.
3. **SQL only for data retrieval** — use `text()` with `.bindparams()` to fetch positions in the time window (matching `app/transit/repository.py` pattern). All distance/gap logic lives in Python methods for testability.
4. **Single orchestrator evaluator** — one background task runs both detectors in sequence (not parallel), keeping the lifecycle simple. Each detector is a class with a `check()` method returning alert candidates.
5. **Cooldown via Redis SET/GET** — simpler than alert dedup for anomaly detection since anomalies can recur (a vehicle can get stuck again after recovering). Cooldown prevents spam within a window but allows re-firing after expiry.
6. **"Active trip" = `trip_id IS NOT NULL` on last position (v1)** — GTFS-RT pollers drop `trip_id` when trips end, so a non-null `trip_id` on the most recent position is a reliable proxy for "vehicle is on an active trip." No stop_times cross-reference needed for the gap check itself. Layover/terminal exclusion (stuck detector only) still uses stop_times.
7. **`feed_outage` uses `source_entity_type=None`** — the `SourceEntityType` Literal is `["vehicle", "route", "driver"]`. Rather than adding `"feed"` (which would require updating all consumers), feed outage alerts use `source_entity_type=None` with `source_entity_id=None` and store `feed_id` in the `details` dict: `details={"feed_id": "riga", "gap_count": 45, "total_count": 50}`.

## Preflight Warnings

- `AlertRuleType` is a `Literal` — adding values is backwards-compatible (existing values still valid). No constructor breakage.
- **Confirmed safe:** No tests in `app/alerts/tests/` or `app/tests/` reference `AlertRuleType` or `SourceEntityType` directly. No regression risk from extending the Literal.
- Redis mock must be `MagicMock()` for pipeline operations (anti-pattern #35).
- `StopTime.trip_id` is an `int` FK, but `VehiclePositionRecord.trip_id` is a `str` (GTFS trip ID). The cross-reference query must join via `Trip.gtfs_trip_id` (string) to `VehiclePositionRecord.trip_id`, then `Trip.id` (int) to `StopTime.trip_id`.

## Security Checklist

No new endpoints — only background tasks. Security concerns:
- [x] No user input accepted (internal evaluator only)
- [x] All DB queries via SQLAlchemy parameterized `text()` with `.bindparams()`
- [x] No credentials in log output (only vehicle_id, feed_id, counts)
- [x] Redis keys use fixed prefixes (no user-controlled data in key names)
- [x] Config settings have safe defaults

## Verification

- [ ] `make check` passes (lint + types + tests)
- [ ] `make security-audit-quick` passes
- [ ] Pyright errors = 0 for `app/ml/` (baseline: directory didn't exist)
- [ ] All 15 tests pass: `uv run pytest app/ml/tests/ -v`
- [ ] Alerts regression: `uv run pytest app/alerts/tests/ -v`
- [ ] Stuck test: vehicle < 20m in 10 min -> alert created
- [ ] GPS gap test: no update for 6 min -> alert created
- [ ] Feed outage test: >= 50% feed gap -> 1 feed_outage, not N per-vehicle alerts
- [ ] Cooldown test: duplicate alert within 15 min -> suppressed
- [ ] Layover/terminal exclusion: vehicle at scheduled stop -> no false positive
