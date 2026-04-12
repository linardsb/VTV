# Plan: ML-4.1 Off-Route Detection

## Context

Off-route vehicles are the #1 fleet anomaly dispatchers want to know about (wrong turn, driver deviation, service change miscommunication). This feature adds a background evaluator that uses PostGIS route corridors to detect when a vehicle drifts >N meters from its assigned GTFS route shape for ≥3 consecutive position updates, then fires an alert.

**Architecture:** Pure background evaluator module under `app/ml/anomaly/` — no REST endpoints. Follows the geofence evaluator pattern (`app/geofences/evaluator.py`) exactly: 60s cycle, Redis state tracking, alert integration via `AlertInstanceRepository`.

## Security Context Assessment

- **CTX-RBAC:** Not applicable — no new REST endpoints
- **CTX-INPUT:** Not applicable — no user input
- **CTX-INFRA:** Minor — new config settings added to `app/core/config.py`
- **CTX-AUTH/FILE/AGENT:** Not applicable

## Research Summary

### Key Existing Components

| Component | File | Purpose |
|-----------|------|---------|
| Geofence evaluator (template) | `app/geofences/evaluator.py` (295 lines) | Background evaluator pattern: Redis vehicle scan, PostGIS check, alert creation, lifecycle |
| Shape model | `app/schedules/models.py:149-166` | `shapes` table: `gtfs_shape_id`, `shape_pt_lat`, `shape_pt_lon`, `shape_pt_sequence` |
| Route→Shape query | `app/schedules/repository.py:1087-1110` | `get_shapes_for_route(route_id)` — joins trips to get shape points |
| Vehicle position Redis | `app/transit/poller.py:156,264` | `vehicle:<id>` keys with `route_id`, `latitude`, `longitude` fields |
| Alert models | `app/alerts/models.py:39-81` | `AlertInstance` with `alert_type`, `source_entity_type`, dedup index |
| Alert schemas | `app/alerts/schemas.py:11-19` | `AlertRuleType` Literal — needs `"off_route"` added |
| Alert rule CHECK | `app/alerts/models.py:28-30` | `ck_alert_rules_rule_type` — needs `"off_route"` added |
| Alert creation helper | `app/geofences/evaluator.py:205-245` | `_create_alert_if_new()` — dedup pattern to follow |
| Config pattern | `app/core/config.py:262-264` | Geofence evaluator settings — pattern for new settings |
| App lifespan | `app/main.py:111-169` | Start/stop registration for background tasks |
| Redis client | `app/core/redis.py` | `get_redis()` singleton, `decode_responses=True` |
| DB context | `app/core/database.py` | `get_db_context()` for standalone sessions |
| Metrics | `app/core/metrics.py` | `record_poller_tick()` for liveness tracking |

### Route→Shape→Corridor Data Flow

1. GTFS import populates `shapes` table with per-point lat/lon/sequence
2. `Trip.shape_id` (String) links to `Shape.gtfs_shape_id` (String)
3. `Route` → `Trip.route_id` → `Trip.shape_id` → `Shape.gtfs_shape_id`
4. Redis vehicle data includes `route_id` (GTFS route short name like `"22"`)
5. **Gap:** Redis `route_id` is `route_short_name` (e.g. `"22"`), not the DB `Route.id` int. Must join via `Route.gtfs_route_id` or `Route.short_name`.

### Route ID Join Path (Critical)

Redis vehicle data stores `route_id` as GTFS route ID string (e.g. `"22"`) from `vp.route_id` in the GTFS-RT feed (`app/transit/poller.py:218,264`). This matches `Route.gtfs_route_id` (String(50), `app/schedules/models.py:45`).

**Join chain:** `redis route_id` → `Route.gtfs_route_id` → `Route.id` → `Trip.route_id` → `Trip.shape_id` → `Shape.gtfs_shape_id`

A route may have multiple shapes (outbound + inbound directions). Build a corridor per shape_id, then `ST_Union` them into one multi-corridor geometry.

### PostGIS Corridor Strategy

Use `text()` for the corridor query — the PostGIS aggregate `ST_MakeLine(... ORDER BY ...)` has no clean SQLAlchemy ORM equivalent:

```python
# Parameterized SQL — safe from injection
result = await db.execute(
    text("""
        SELECT ST_Union(corridor) AS corridor FROM (
            SELECT ST_Buffer(
                ST_MakeLine(
                    ST_SetSRID(ST_MakePoint(s.shape_pt_lon, s.shape_pt_lat), 4326)
                    ORDER BY s.shape_pt_sequence
                )::geography,
                :buffer_m
            )::geometry AS corridor
            FROM shapes s
            INNER JOIN (
                SELECT DISTINCT t.shape_id
                FROM trips t
                INNER JOIN routes r ON t.route_id = r.id
                WHERE r.gtfs_route_id = :gtfs_route_id
                  AND r.feed_id = :feed_id
                  AND t.shape_id IS NOT NULL
            ) shapes_for_route ON s.gtfs_shape_id = shapes_for_route.shape_id
            GROUP BY s.gtfs_shape_id
        ) sub
    """),
    {"gtfs_route_id": gtfs_route_id, "feed_id": feed_id, "buffer_m": buffer_m},
)
```

Using `::geography` for the buffer ensures meters (not degrees). Cast back to `::geometry` for `ST_Contains`. `ST_Union` merges outbound + inbound corridors into one geometry.

### Alert Dedup Strategy (Critical)

The existing `find_active_duplicate(rule_id, entity_type, entity_id)` uses `rule_id` as an FK to `alert_rules.id`. The geofence evaluator passes `geofence.id` (geofences table PK) which only works because those IDs happen to not collide with alert_rules IDs.

For off-route, **do NOT use `find_active_duplicate`**. Instead, write a direct dedup query on `alert_type + source_entity_id + status`:

```python
async def _find_active_off_route_alert(
    db: AsyncSession, vehicle_id: str
) -> AlertInstance | None:
    result = await db.execute(
        select(AlertInstance).where(
            AlertInstance.alert_type == "off_route",
            AlertInstance.source_entity_id == vehicle_id,
            AlertInstance.status == "active",
        )
    )
    return result.scalar_one_or_none()
```

This provides correct dedup: one active off-route alert per vehicle. Always insert with `rule_id=None`.

## Test Landscape

### Reference: Geofence Evaluator Tests (`app/geofences/tests/test_evaluator.py`, 275 lines)
- `TestEvaluateGeofencesOnce` (6 tests): vehicle enters/exits/dwell, empty vehicles, Redis state, errors
- `TestEvaluatorLifecycle` (2 tests): start/stop, disabled skip
- Mocking pattern: patch `get_redis`, `get_db_context`, check `alert_repo.create` calls
- Redis mock: `AsyncMock` with `scan_iter` as async generator, `get`/`set` as `AsyncMock`

### Alert Test Factories (`app/alerts/tests/conftest.py`)
- `make_alert_rule(**overrides)` / `make_alert_instance(**overrides)` — real model factories

### Key Mock Patterns
- Redis scan: async generator yielding key strings
- Redis get: `side_effect` lambda dispatching by key prefix
- DB context: `AsyncMock` yielding mock session
- PostGIS result: mock repo method returning list of model instances

## Type Check Baseline

| Feature | Pyright | Mypy |
|---------|---------|------|
| `app/geofences/` | 0 errors | 0 errors (13 files) |
| `app/transit/` | 0 errors | 0 errors (37 files) |
| `app/ml/` | N/A (new) | N/A (new) |

**Target:** 0 new errors. No new third-party libs needed — all PostGIS via SQLAlchemy `func.*`.

## Files to Create/Modify

| Action | File | Purpose |
|--------|------|---------|
| CREATE | `app/ml/__init__.py` | Package init |
| CREATE | `app/ml/anomaly/__init__.py` | Subpackage init |
| CREATE | `app/ml/anomaly/off_route.py` | Background evaluator: corridor build, containment check, consecutive tracking, alert firing |
| CREATE | `app/ml/anomaly/tests/__init__.py` | Test package init |
| CREATE | `app/ml/anomaly/tests/conftest.py` | Fixtures: mock Redis, mock DB, vehicle data factories |
| CREATE | `app/ml/anomaly/tests/test_off_route.py` | 12 unit tests covering all evaluator behaviors |
| UPDATE | `app/alerts/schemas.py:11-19` | Add `"off_route"` to `AlertRuleType` Literal |
| UPDATE | `app/alerts/models.py:28-30` | Add `"off_route"` to `ck_alert_rules_rule_type` CHECK constraint |
| UPDATE | `app/core/config.py:262-264` | Add 4 anomaly settings after geofence settings |
| UPDATE | `app/main.py:118-163` | Register start/stop for off-route evaluator |
| CREATE | `alembic/versions/xxx_add_off_route_alert_type.py` | Migration: alter CHECK constraint |

## Implementation Steps

### Step 1: Update alert type system
**Files:** `app/alerts/schemas.py`, `app/alerts/models.py`

Add `"off_route"` to `AlertRuleType` Literal (schemas.py:11-19):
```python
AlertRuleType = Literal[
    "delay_threshold",
    "maintenance_due",
    "registration_expiry",
    "manual",
    "geofence_enter",
    "geofence_exit",
    "geofence_dwell",
    "off_route",
]
```

Add `"off_route"` to CHECK constraint in models.py:28-30:
```python
CheckConstraint(
    "rule_type IN ('delay_threshold', 'maintenance_due', 'registration_expiry', 'manual', 'geofence_enter', 'geofence_exit', 'geofence_dwell', 'off_route')",
    name="ck_alert_rules_rule_type",
),
```

**Anti-pattern #11:** Grep for `AlertRuleType(` and all constructors of `AlertInstanceCreate(` — verify no tests hardcode the old set as exhaustive.

**Validation:** `uv run ruff check app/alerts/schemas.py app/alerts/models.py && uv run pyright app/alerts/`

### Step 2: Create migration for CHECK constraint
**File:** New Alembic migration

```bash
cd /Users/Berzins/Desktop/VTV && uv run alembic revision --autogenerate -m "add off_route alert type"
```

Then manually edit the generated migration to replace the CHECK constraint (autogenerate won't detect CHECK changes):

```python
def upgrade() -> None:
    op.drop_constraint("ck_alert_rules_rule_type", "alert_rules")
    op.create_check_constraint(
        "ck_alert_rules_rule_type",
        "alert_rules",
        "rule_type IN ('delay_threshold', 'maintenance_due', 'registration_expiry', 'manual', 'geofence_enter', 'geofence_exit', 'geofence_dwell', 'off_route')",
    )

def downgrade() -> None:
    op.drop_constraint("ck_alert_rules_rule_type", "alert_rules")
    op.create_check_constraint(
        "ck_alert_rules_rule_type",
        "alert_rules",
        "rule_type IN ('delay_threshold', 'maintenance_due', 'registration_expiry', 'manual', 'geofence_enter', 'geofence_exit', 'geofence_dwell')",
    )
```

**Validation:** `uv run alembic check` (no pending migrations)

### Step 3: Add config settings
**File:** `app/core/config.py`

Insert after geofence settings (line ~264):
```python
    # Off-route anomaly detection (ML-4.1)
    anomaly_offroute_enabled: bool = True
    anomaly_offroute_check_interval_seconds: int = 60
    anomaly_offroute_buffer_meters: int = 50
    anomaly_offroute_consecutive_hits: int = 3
```

**Validation:** `uv run pyright app/core/config.py`

### Step 4: Create package structure
**Files:** `app/ml/__init__.py`, `app/ml/anomaly/__init__.py`

Both empty `__init__.py` files. Ensure `app/ml/` and `app/ml/anomaly/` directories exist.

### Step 5: Create off-route evaluator
**File:** `app/ml/anomaly/off_route.py`

Structure (following `app/geofences/evaluator.py` exactly):

```python
# pyright: reportUnknownMemberType=false, reportMissingTypeStubs=false, reportArgumentType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Background off-route evaluator — detects vehicles outside their GTFS route corridors."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Sequence

from sqlalchemy import Float, String, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.alerts.repository import AlertInstanceRepository
from app.alerts.schemas import AlertInstanceCreate
from app.core.config import Settings, get_settings
from app.core.database import get_db_context
from app.core.logging import get_logger
from app.core.metrics import record_poller_tick
from app.core.redis import get_redis
from app.schedules.models import Route, Shape, Trip

_evaluator_task: asyncio.Task[None] | None = None
logger = get_logger(__name__)

REDIS_VEHICLE_PREFIX = "vehicle:"
REDIS_OFF_ROUTE_PREFIX = "off_route_state:"
```

**Key functions to implement:**

1. **`async def get_corridor_for_route(db: AsyncSession, gtfs_route_id: str, feed_id: str, buffer_m: int) -> Any | None`**
   - Use the `text()` SQL from "PostGIS Corridor Strategy" section above
   - Return the corridor WKB geometry or None if no shapes exist
   - Cache in `_corridor_cache: dict[str, Any] = {}` keyed by `f"{feed_id}:{gtfs_route_id}"`
   - Cache cleared when evaluator stops (in `stop_off_route_evaluator()`)

2. **`async def check_vehicle_in_corridor(db: AsyncSession, lat: float, lon: float, corridor: Any) -> bool`**
   - Use `text()`:
     ```python
     result = await db.execute(
         text("SELECT ST_Contains(:corridor::geometry, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326))"),
         {"corridor": corridor, "lon": lon, "lat": lat},
     )
     return bool(result.scalar())
     ```
   - Returns True if vehicle is inside the corridor

3. **`async def evaluate_off_route_once() -> int`**
   - Scan Redis `vehicle:*` keys (same as geofence evaluator)
   - For each vehicle with a `route_id` (and `feed_id`, default `"riga"`):
     - Get/build corridor for that route (keyed by `feed_id:route_id`)
     - Check containment
     - Read Redis `off_route_state:<vehicle_id>` → consecutive count (int, default 0)
     - If outside: increment count, store back with 5min TTL
     - If count >= threshold: fire alert via `_create_off_route_alert()`
     - If inside: reset count to 0 (delete key)
   - Log cycle completion
   - Return number of alerts fired

4. **`async def _create_off_route_alert(db: AsyncSession, alert_repo: AlertInstanceRepository, vehicle_id: str, route_id: str, consecutive_count: int) -> None`**
   - Dedup: call `_find_active_off_route_alert(db, vehicle_id)` — if exists, return early
   - Create `AlertInstanceCreate(alert_type="off_route", severity="high", rule_id=None, source_entity_type="vehicle", source_entity_id=vehicle_id, details={"route_id": route_id, "consecutive_hits": consecutive_count})`
   - See "Alert Dedup Strategy" section above — do NOT use `find_active_duplicate()`

5. **`async def _evaluator_loop(interval: int) -> None`** — infinite loop with sleep+try/except
6. **`async def start_off_route_evaluator(settings: Settings) -> None`** — create task if enabled
7. **`async def stop_off_route_evaluator() -> None`** — cancel task, handle CancelledError

**Corridor caching:** Use `_corridor_cache: dict[str, Any] = {}` at module level. Populated on first access per route, cleared when evaluator stops. This avoids rebuilding PostGIS corridors every 60s.

**Logging events:**
- `transit.anomaly.off_route.cycle_completed {total_vehicles, alerts_fired, interval}`
- `transit.anomaly.off_route.candidate {vehicle_id, route_id, consecutive_count}`
- `transit.anomaly.off_route.fired {vehicle_id, route_id, drift_m}`
- `transit.anomaly.off_route.reset {vehicle_id}` (vehicle returned to corridor)
- `transit.anomaly.off_route.no_corridor {route_id}` (no shape data for route)
- `transit.anomaly.off_route.cycle_failed {error_type}`
- `transit.anomaly.off_route.lifecycle_started {interval}`
- `transit.anomaly.off_route.lifecycle_stopped`
- `transit.anomaly.off_route.lifecycle_skipped {reason}`

**Anti-patterns to avoid:**
- #34: Redis await returns need `# type: ignore[misc]` on await lines
- #35: `redis.pipeline()` is sync — not used here, but don't introduce it
- #37: No bare `except: pass` — always log
- #38: Background task must handle CancelledError + Exception separately
- #16: Singleton close must handle closed event loops
- #9: No unused `ctx` params (not applicable — no Pydantic AI tools)

**Validation:** `uv run ruff format app/ml/ && uv run ruff check --fix app/ml/ && uv run pyright app/ml/ && uv run mypy app/ml/`

### Step 6: Register in app lifespan
**File:** `app/main.py`

Add after geofence evaluator start (line ~119):
```python
    # Start off-route anomaly evaluator (ML-4.1)
    from app.ml.anomaly.off_route import start_off_route_evaluator

    await start_off_route_evaluator(settings)
```

Add to shutdown (before `stop_geofence_evaluator`, line ~163):
```python
    from app.ml.anomaly.off_route import stop_off_route_evaluator

    await stop_off_route_evaluator()
```

**Validation:** `uv run pyright app/main.py`

### Step 7: Create test conftest
**File:** `app/ml/anomaly/tests/conftest.py`

Fixtures:
- `mock_redis()` → `AsyncMock` with `scan_iter`, `get`, `set`, `delete`
- `mock_db_context()` → context manager yielding `AsyncMock` session
- `_make_vehicle_data(vehicle_id, route_id, lat, lon)` → dict matching Redis JSON format
- `_make_corridor_mock()` → mock geometry object for PostGIS containment

### Step 8: Create evaluator tests
**File:** `app/ml/anomaly/tests/test_off_route.py`

12 tests in 3 classes:

**`TestEvaluateOffRouteOnce`** (8 tests):
1. `test_vehicle_inside_corridor_no_alert` — vehicle in corridor, count stays 0, no alert
2. `test_vehicle_outside_corridor_increments_count` — outside, count goes 1→2, no alert yet
3. `test_vehicle_outside_corridor_fires_at_threshold` — count reaches 3, alert created
4. `test_vehicle_returns_to_corridor_resets_count` — was at count 2, now inside → Redis key deleted
5. `test_no_vehicles_returns_zero` — empty Redis scan → returns 0
6. `test_vehicle_without_route_id_skipped` — missing `route_id` in data → skip
7. `test_no_shape_data_skips_route` — `get_corridor_for_route` returns None → skip + log warning
8. `test_alert_deduplication` — active alert exists → no duplicate created

**`TestCorridorCache`** (2 tests):
9. `test_corridor_cached_across_cycles` — DB queried once, second cycle uses cache
10. `test_config_buffer_meters_used` — custom buffer_meters passed to ST_Buffer

**`TestEvaluatorLifecycle`** (2 tests):
11. `test_start_stop_lifecycle` — starts task, stops cleanly
12. `test_start_skips_when_disabled` — `anomaly_offroute_enabled=False` → no task created

**Validation:** `uv run pytest app/ml/anomaly/tests/ -v --tb=short`

### Step 9: Update existing alert tests if needed

Grep for tests asserting exhaustive `AlertRuleType` values. If any test asserts the exact set of allowed types, add `"off_route"` to that set.

**Validation:** `uv run pytest app/alerts/tests/ -v --tb=short`

## Preflight Warnings

- **Alert type CHECK constraint** requires an Alembic migration — autogenerate won't detect CHECK changes, must write manually
- **Redis `route_id` is string** (`route_short_name` like `"22"`), not DB `Route.id` (int). The corridor query must match via `Route.gtfs_route_id` or `Route.short_name`
- **`ST_MakeLine` aggregate with ORDER BY** — requires PostgreSQL 9.0+, which is available
- **`::geography` cast** for meter-based buffer — ensure PostGIS geography type is available (standard with PostGIS)
- **Corridor cache invalidation** — if GTFS data is reimported while evaluator is running, cache becomes stale. Acceptable for MVP; document as known limitation
- **Anti-pattern #11:** Adding `"off_route"` to `AlertRuleType` may break test assertions that enumerate all types

## Security Checklist

No new endpoints — background evaluator only. Security concerns are minimal:
- [ ] Config settings use safe defaults (enabled=True, buffer=50m, hits=3)
- [ ] No user input processed — reads from Redis (internal) and DB (internal)
- [ ] Alert details JSONB contains no credentials or sensitive data
- [ ] Structured logging does not log raw Redis payloads (only extracted fields)

## Verification

- [ ] `uv run ruff format app/ml/ app/alerts/schemas.py app/alerts/models.py app/core/config.py && uv run ruff check --fix app/ml/ app/alerts/ app/core/config.py`
- [ ] `uv run pyright app/ml/ app/alerts/ app/core/config.py` — 0 errors
- [ ] `uv run mypy app/ml/ app/alerts/ app/core/config.py` — 0 errors
- [ ] `uv run pytest app/ml/anomaly/tests/ -v` — all 12 tests pass
- [ ] `uv run pytest app/alerts/tests/ -v` — no regressions
- [ ] `make check` passes (full lint + types + tests)
- [ ] `make security-audit-quick` passes
- [ ] `uv run pytest app/tests/test_security.py -v` — security convention tests pass
