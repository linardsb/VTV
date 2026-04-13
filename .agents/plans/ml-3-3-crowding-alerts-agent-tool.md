# Plan: ML-3.3 Crowding Alerts + Agent Tool

## Context

Predictions without action are dashboards. Dispatchers need proactive crowding alerts so they can deploy overflow vehicles 10+ minutes before arrival. This feature adds:
1. `predict_passenger_load` agent tool — exposes load predictions via chat
2. `crowding_evaluator.py` background task — 2-min cycle, fires alerts for `overcrowded` predictions
3. Both share a single `LoadPredictionService` singleton (mirrors `ETAService`)

## Security Context Assessment

**Active:** CTX-AGENT (new agent tool), CTX-RBAC (alert system integration)
**Not applicable:** CTX-AUTH, CTX-FILE, CTX-INFRA, CTX-INPUT (no new endpoints, no file handling, no user input queries)

CTX-AGENT requirements:
- Tool returns JSON strings, no credentials in responses
- Tool errors are user-safe messages (no stack traces)
- Structured logging with no raw prompt data

CTX-RBAC requirements:
- Alert creation uses existing RBAC-protected alert system
- No new REST endpoints (tool is agent-internal, evaluator is background)

## Research Summary

### Reference patterns
| Pattern | File | Lines |
|---------|------|-------|
| ML service singleton | `app/ml/eta_service.py` | 58–362 |
| Agent tool (predict) | `app/core/agents/tools/transit/predict_eta.py` | 1–93 |
| Background evaluator | `app/alerts/evaluator.py` | 1–232 |
| Alert dedup check | `app/alerts/repository.py` | 224–238 |
| Alert creation | `app/alerts/evaluator.py` | 162–172 |
| Tool registration | `app/core/agents/agent.py` | 1–26 |
| Transit agent tools | `app/core/agents/agents/transit.py` | 27–33 |
| Lifespan startup | `app/main.py` | 126–132 |
| Shutdown coordinator | `app/main.py` | 196–205 |
| Config feature flags | `app/core/config.py` | 252–254, 271–273, 305–308 |
| Load model | `app/ml/models/load_gbm.py` | 266–285 |
| CrowdingBucket type | `app/ml/models/schemas.py` | 11, 73–81 |

### Key shared utilities
- `get_logger(__name__)` — structured logging
- `get_db_context()` — async DB context manager
- `get_redis()` — async Redis client
- `record_poller_tick(name)` — liveness metrics
- `AlertInstanceRepository.find_active_duplicate()` — dedup
- `AlertInstanceCreate` — alert creation schema
- `ModelRegistry` — model loading + version tracking

## Test Landscape

### Existing fixtures available
- `app/alerts/tests/conftest.py`: `make_alert_rule()`, `make_alert_instance()`, `sample_rule`, `sample_alert`
- `app/ml/tests/conftest.py`: `make_position_row()`, `mock_redis`, `mock_settings`
- `app/core/agents/tests/conftest.py`: `ManualClock`, `_reset_skill_cache`, `_reset_provider_breakers`
- Root `conftest.py`: `mock_settings` fixture

### Template files
- Agent tool tests: `app/core/agents/tools/transit/tests/test_predict_eta.py`
- Evaluator tests: `app/alerts/tests/test_evaluator.py`, `app/geofences/tests/test_evaluator.py`
- ML service tests: `app/ml/tests/test_eta_service.py`

### Mock patterns
- Redis: `MagicMock()` with `AsyncMock` for get/set, `scan_iter` as async generator
- DB context: `AsyncMock` with `__aenter__`/`__aexit__`
- ML model: `service._model = mock_model; service._model_version = 1`
- Alert repo: `AsyncMock()` for `find_active_duplicate`, `create`

## Type Check Baseline

| Directory | Pyright | Mypy |
|-----------|---------|------|
| `app/alerts/` | 0 errors | 0 errors (13 files) |
| `app/ml/` | 0 errors | 0 errors (47 files) |
| `app/core/agents/` | 0 errors | 0 errors (114 files) |
| `app/transit/` | 0 errors | 0 errors (38 files) |

**All clean.** Any errors introduced are regressions.

## Files to Create/Modify

| Action | File | Purpose |
|--------|------|---------|
| CREATE | `app/ml/load_service.py` | LoadPredictionService singleton (mirrors ETAService) |
| CREATE | `app/alerts/crowding_evaluator.py` | Background task: 2-min cycle, crowding alert creation |
| CREATE | `app/core/agents/tools/transit/predict_passenger_load.py` | Agent tool: predict load for vehicle at stop |
| CREATE | `app/ml/tests/test_load_service.py` | Unit tests for LoadPredictionService |
| CREATE | `app/alerts/tests/test_crowding_evaluator.py` | Unit tests for crowding evaluator |
| CREATE | `app/core/agents/tools/transit/tests/test_predict_passenger_load.py` | Unit tests for agent tool |
| UPDATE | `app/core/config.py` | Add `alerts_crowding_enabled`, `alerts_crowding_check_interval_seconds` |
| UPDATE | `app/alerts/schemas.py` | Add `"crowding_prediction"` to `AlertRuleType` |
| UPDATE | `app/alerts/models.py` | Add `"crowding_prediction"` to CHECK constraint string |
| CREATE | `alembic/versions/..._add_crowding_prediction_alert_type.py` | Migration: drop/recreate `ck_alert_rules_rule_type` CHECK constraint |
| UPDATE | `app/main.py` | Register crowding evaluator (startup + shutdown) |
| UPDATE | `app/core/agents/agent.py` | Import + register predict_passenger_load tool |
| UPDATE | `app/core/agents/agents/transit.py` | Import + register predict_passenger_load in TransitAgent |

## Implementation Steps

### Step 1: Add config settings
**File:** `app/core/config.py` (UPDATE)

Add after line 254 (`alerts_check_interval_seconds`):
```python
# ML-3.3: Crowding prediction alerts
alerts_crowding_enabled: bool = True
alerts_crowding_check_interval_seconds: int = 120  # 2 min cycle
alerts_crowding_dedup_minutes: int = 30
```

**Validation:** `uv run ruff check app/core/config.py && uv run pyright app/core/config.py`

### Step 2: Add `"crowding_prediction"` to alert schemas + models + migration
**File:** `app/alerts/schemas.py` (UPDATE)

Add `"crowding_prediction"` to the `AlertRuleType` Literal (line 11–24). Must grep for `AlertRuleType` across codebase to check all consumers.

**File:** `app/alerts/models.py` (UPDATE)

Add `'crowding_prediction'` to the CHECK constraint string in `__table_args__` (line 29):
```python
"rule_type IN ('delay_threshold', 'maintenance_due', 'registration_expiry', 'manual', 'geofence_enter', 'geofence_exit', 'geofence_dwell', 'stuck_vehicle', 'gps_gap', 'feed_outage', 'off_route', 'schedule_adherence', 'crowding_prediction')",
```

**File:** `alembic/versions/..._add_crowding_prediction_alert_type.py` (CREATE)

Migration to drop and recreate the `ck_alert_rules_rule_type` CHECK constraint with the new value. Follow the pattern from `n7o8p9q0r1s2_add_off_route_alert_type.py`:
```python
def upgrade():
    op.drop_constraint("ck_alert_rules_rule_type", "alert_rules")
    op.create_check_constraint(
        "ck_alert_rules_rule_type", "alert_rules",
        "rule_type IN ('delay_threshold', 'maintenance_due', 'registration_expiry', 'manual', 'geofence_enter', 'geofence_exit', 'geofence_dwell', 'stuck_vehicle', 'gps_gap', 'feed_outage', 'off_route', 'schedule_adherence', 'crowding_prediction')"
    )

def downgrade():
    op.drop_constraint("ck_alert_rules_rule_type", "alert_rules")
    op.create_check_constraint(
        "ck_alert_rules_rule_type", "alert_rules",
        "rule_type IN ('delay_threshold', 'maintenance_due', 'registration_expiry', 'manual', 'geofence_enter', 'geofence_exit', 'geofence_dwell', 'stuck_vehicle', 'gps_gap', 'feed_outage', 'off_route', 'schedule_adherence')"
    )
```

Generate with: `make db-revision m="add crowding_prediction alert type"`

**Validation:** `uv run ruff check app/alerts/schemas.py app/alerts/models.py && uv run pyright app/alerts/schemas.py app/alerts/models.py`

### Step 3: Create LoadPredictionService singleton
**File:** `app/ml/load_service.py` (CREATE)

Mirror `app/ml/eta_service.py` structure:
- `LoadPredictionService` class with `_model`, `_model_version`, `_last_reload_check`
- `_maybe_reload()` — checks registry every `eta_model_reload_interval_seconds`
- `_ensure_model_loaded() -> bool` — lazy first-call load from `ModelRegistry` (model name: `"load_gbm"`)
- `predict(db, vehicle_id, trip_id, stop_sequence) -> dict[str, Any]` — calls `LoadModel.predict(features)`, returns dict with `predicted_passenger_count`, `load_factor_pct`, `crowding_bucket`, `confidence_lower`, `confidence_upper`, `fallback`
- Fallback: if model unavailable, return `{"fallback": True, "crowding_bucket": None, "predicted_passenger_count": None}`
- Module-level singleton: `get_load_service(settings)`, `reset_load_service()`
- Add pyright file-level directive matching `eta_service.py` line 1
- Structured logging: `ml.load_service.predict_started/completed/fallback_used/reload_completed`

**Validation:** `uv run ruff format app/ml/load_service.py && uv run ruff check app/ml/load_service.py && uv run pyright app/ml/load_service.py`

### Step 4: Create crowding evaluator
**File:** `app/alerts/crowding_evaluator.py` (CREATE)

Mirror `app/alerts/evaluator.py` lifecycle pattern:
- `_crowding_task: asyncio.Task[None] | None = None`
- `evaluate_crowding_once(settings) -> int`:
  1. Get `LoadPredictionService` via `get_load_service(settings)`
  2. Get active vehicle positions from Redis (`vehicle:*` scan)
  3. For each vehicle with an active trip:
     - Predict load at next 3 stops via `load_service.predict()`
     - If `crowding_bucket == "overcrowded"`:
       - Check `find_active_duplicate(rule_id, "vehicle", vehicle_id)` for dedup
       - Create alert via `AlertInstanceCreate` with details: `route_id`, `vehicle_id`, `next_stop`, `predicted_load_factor`, `predicted_arrival_at`
  4. Call `record_poller_tick("crowding_evaluator")`
  5. Return count of new alerts
- `_evaluator_loop(settings, interval)` — while True, sleep, evaluate, log
- `start_crowding_evaluator(settings)` — gate on `settings.alerts_crowding_enabled`
- `stop_crowding_evaluator()` — cancel task, handle CancelledError
- Add pyright file-level directive matching `evaluator.py` line 1
- Structured logging: `alerts.crowding_evaluator.cycle_completed/cycle_failed/lifecycle_started/lifecycle_stopped/lifecycle_skipped`
- Crowding bucket → alert severity mapping:
  - `"overcrowded"` → `"critical"`
  - `"full"` → `"high"` (optional future extension)
- Fail-open: if `LoadPredictionService` model is unavailable, skip cycle (log warning, return 0)

**Validation:** `uv run ruff format app/alerts/crowding_evaluator.py && uv run ruff check app/alerts/crowding_evaluator.py && uv run pyright app/alerts/crowding_evaluator.py`

### Step 5: Create agent tool
**File:** `app/core/agents/tools/transit/predict_passenger_load.py` (CREATE)

Mirror `predict_eta.py` exactly:
```python
async def predict_passenger_load(
    ctx: RunContext[UnifiedDeps],
    vehicle_id: str,
    stop_id: str,
) -> str:
```

- Docstring follows 5-principle agent tool format (WHEN TO USE, WHEN NOT TO USE, COMPOSITION)
- WHEN TO USE: "Which buses will be crowded?", "How full is bus X at stop Y?"
- WHEN NOT TO USE: For current position use query_bus_status; for ETA use predict_eta
- COMPOSITION: Use search_stops to get stop_id, query_bus_status to get vehicle_id
- `_settings = ctx.deps.settings` (satisfies ARG001)
- Get `LoadPredictionService` via `get_load_service(_settings)`
- Call `load_service.predict(db, vehicle_id, stop_id)`
- Return `json.dumps(result, ensure_ascii=False)`
- Error handling: return user-safe error string
- Structured logging: `agent.predict_passenger_load.started/completed/failed`

**Validation:** `uv run ruff format app/core/agents/tools/transit/predict_passenger_load.py && uv run ruff check app/core/agents/tools/transit/predict_passenger_load.py && uv run pyright app/core/agents/tools/transit/predict_passenger_load.py`

### Step 6: Register tool in agent.py
**File:** `app/core/agents/agent.py` (UPDATE)

Add import after line 22 (`predict_eta`):
```python
from app.core.agents.tools.transit.predict_passenger_load import predict_passenger_load
```

Register tool in the agent creation (same pattern as other tools).

**Validation:** `uv run pyright app/core/agents/agent.py`

### Step 7: Register tool in transit agent
**File:** `app/core/agents/agents/transit.py` (UPDATE)

Add import alongside `predict_eta` (line 31):
```python
from app.core.agents.tools.transit.predict_passenger_load import predict_passenger_load
```

Register in the TransitAgent tool list.

**Validation:** `uv run pyright app/core/agents/agents/transit.py`

### Step 8: Register evaluator in lifespan
**File:** `app/main.py` (UPDATE)

**Imports:** Add at top:
```python
from app.alerts.crowding_evaluator import start_crowding_evaluator, stop_crowding_evaluator
```

**Startup:** Add after line 129 (`start_geofence_evaluator`):
```python
# Start crowding prediction evaluator (ML-3.3)
await start_crowding_evaluator(settings)
```

**Shutdown:** Add after geofence_evaluator shutdown (line 205):
```python
coordinator.register(
    ShutdownTask(
        name="crowding_evaluator",
        drain_timeout_s=3.0,
        drain=stop_crowding_evaluator,
    )
)
```

**Validation:** `uv run ruff check app/main.py && uv run pyright app/main.py`

### Step 9: Write LoadPredictionService tests
**File:** `app/ml/tests/test_load_service.py` (CREATE)

Tests (4+):
1. `test_lazy_load_model` — first `predict()` call loads model from registry
2. `test_hot_reload_on_version_change` — `_maybe_reload()` updates model when version changes
3. `test_fallback_when_model_missing` — returns fallback dict when registry has no model
4. `test_singleton_getter` — `get_load_service()` returns same instance, `reset_load_service()` clears it
5. `test_predict_returns_expected_fields` — result dict has all required keys

Mock pattern: patch `ModelRegistry`, inject mock model with `service._model = mock_model`.

**Validation:** `uv run pytest app/ml/tests/test_load_service.py -v`

### Step 10: Write crowding evaluator tests
**File:** `app/alerts/tests/test_crowding_evaluator.py` (CREATE)

Tests (5+):
1. `test_evaluate_no_vehicles_returns_zero` — empty Redis scan → 0 alerts
2. `test_evaluate_creates_alert_for_overcrowded` — overcrowded prediction → alert created
3. `test_evaluate_deduplicates_alerts` — `find_active_duplicate` returns existing → no new alert
4. `test_evaluate_skips_non_overcrowded` — `crowding_bucket="moderate"` → no alert
5. `test_lifecycle_start_stop` — `start_crowding_evaluator` / `stop_crowding_evaluator` clean lifecycle
6. `test_lifecycle_skips_when_disabled` — `alerts_crowding_enabled=False` → task not created
7. `test_evaluate_handles_model_unavailable` — service.predict raises → returns 0, logs warning

Mock pattern: patch `get_redis`, `get_db_context`, `AlertInstanceRepository`, `get_load_service`.

**Validation:** `uv run pytest app/alerts/tests/test_crowding_evaluator.py -v`

### Step 11: Write agent tool tests
**File:** `app/core/agents/tools/transit/tests/test_predict_passenger_load.py` (CREATE)

Tests (4+):
1. `test_predict_load_returns_json` — valid JSON with expected fields
2. `test_predict_load_fallback_in_response` — fallback=True when model unavailable
3. `test_predict_load_logs_started_completed` — structlog capture_logs assertion
4. `test_predict_load_handles_service_error` — RuntimeError → user-safe error string
5. `test_predict_load_missing_db_session_factory` — None factory → graceful error

Mock pattern: patch `get_load_service`, mock `ctx.deps` with `_make_ctx()` helper.

**Validation:** `uv run pytest app/core/agents/tools/transit/tests/test_predict_passenger_load.py -v`

## Preflight Warnings

- `app/alerts/schemas.py:11` — `AlertRuleType` is a Literal used in models and schemas. Adding a new value requires checking all consumers (anti-pattern #11). Grep for `AlertRuleType` and `rule_type` across `app/alerts/`.
- `app/core/agents/agent.py` — tool list is import-ordered. New import must maintain alphabetical/domain order.
- `app/main.py` — import section and lifespan are dense. Insert at correct position to maintain logical grouping.
- `app/core/agents/agents/transit.py:10` — `__all__` must include any new patched symbols.

## Security Checklist

No new REST endpoints — N/A for most items.
- [x] Agent tool returns JSON strings only (no credentials/internal state)
- [x] Tool error messages are user-safe (no stack traces, no internal paths)
- [x] Structured logging uses domain.component.action pattern (no raw prompts)
- [x] Evaluator uses `get_db_context()` (proper session lifecycle)
- [x] Alert creation uses existing RBAC-protected repository layer

## Verification

- [ ] `uv run ruff format app/ml/load_service.py app/alerts/crowding_evaluator.py app/core/agents/tools/transit/predict_passenger_load.py`
- [ ] `uv run ruff check app/ml/ app/alerts/ app/core/agents/ app/transit/`
- [ ] `uv run pyright app/ml/ app/alerts/ app/core/agents/ app/transit/` — 0 errors (baseline: 0)
- [ ] `uv run mypy app/ml/ app/alerts/ app/core/agents/ app/transit/` — 0 errors (baseline: 0)
- [ ] `uv run pytest app/ml/tests/test_load_service.py app/alerts/tests/test_crowding_evaluator.py app/core/agents/tools/transit/tests/test_predict_passenger_load.py -v` — all pass
- [ ] `make check` — full suite passes
- [ ] `make security-audit-quick` — no new findings
