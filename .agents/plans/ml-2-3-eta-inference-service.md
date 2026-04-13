# Plan: ML-2.3 ETA Inference Service + Agent Tool Integration

## Context

A trained LightGBM ETA model exists (ML-2.2) but has no serving layer. This feature exposes predictions via:
1. **ETAService** singleton — in-memory model cache, hot-reload, graceful fallback
2. **REST endpoint** — `GET /v1/transit/vehicles/{vehicle_id}/eta?stop_id=X`
3. **predict_eta agent tool** — dispatchers ask "when will bus 22-47 reach Brīvības?"
4. **query_route_delays enhancement** — optional ML forecast inclusion

In-process inference is correct at VTV's scale (<10k predictions/day, LightGBM cold-start <50ms).

## Security Context Assessment

**Active contexts:** CTX-RBAC, CTX-INPUT, CTX-AGENT

- **CTX-RBAC:** New REST endpoint needs `get_current_user` + rate limiting. Agent tool inherits agent auth.
- **CTX-INPUT:** `vehicle_id` and `stop_id` path/query params need `max_length` + `pattern` constraints.
- **CTX-AGENT:** New agent tool — docstring must follow 5-principle LLM-optimized format. Tool returns must not leak model internals. Error returns as strings.

## Research Summary

### ML Module (app/ml/)
- **registry.py:23** — `ModelRegistry` with JSON persistence, `get_production(name)` returns version pointer
- **models/eta_gbm.py:239-249** — `ETAModel.predict(features: ETAFeatures) -> ETAPrediction` (frozen dataclass)
- **models/schemas.py:1-41** — `ETAPrediction(predicted_delay_s, confidence_lower, confidence_upper)`, `ModelMetadata`
- **features/eta_features.py** — `extract_features(db, trip_id, stop_sequence, observed_at) -> ETAFeatures` (async, 18 fields)
- **features/queries.py** — Parameterized SQL for feature extraction (delay, weather, traffic, headway)

### Transit Module (app/transit/)
- **routes.py:33** — Router prefix `/api/v1/transit`, tag `["transit"]`
- **routes.py:45** — Rate limit pattern: `@limiter.limit("30/minute")`
- **routes.py:92-141** — `GET /vehicles/{vehicle_id}/history` as endpoint pattern reference
- **schemas.py** — `VehiclePosition` with `ConfigDict(strict=True)` pattern
- **models.py:19-75** — `VehiclePositionRecord` TimescaleDB hypertable (vehicle_id, trip_id, route_id, delay_seconds)
- **static_cache.py:116-150** — `GTFSStaticCache.trip_stop_times[trip_id] -> list[StopTimeEntry]` for scheduled time lookup

### Agent Tools (app/core/agents/tools/transit/)
- **query_bus_status.py:55-139** — Tool pattern: async fn with `RunContext[UnifiedDeps]`, returns JSON string, try/except with error string fallback
- **deps.py:20-42** — `UnifiedDeps` dataclass with `db_session_factory`, `settings`, HTTP clients
- **Registration:** Tool functions added to `tools=[...]` list in `create_agent()` (agent.py:113-151)

### Transit Agent (app/core/agents/agents/transit.py)
- **Lines 67-122** — System prompt with Latvian glossary, response format rules
- **Lines 154-160** — 5 tools currently: query_bus_status, get_route_schedule, search_stops, get_adherence_report, check_driver_availability

### Config (app/core/config.py)
- **Lines 275-282** — ML-related flags section. No ETA service config yet — must add.

### Model Registry Format (models/registry.json)
```json
{ "models": { "eta_gbm": { "versions": { "1": { "artifact": "path", "metrics": {...} } }, "production": 1 } } }
```

## Test Landscape

### Existing Fixtures
| Module | Key Factories |
|--------|--------------|
| `app/ml/tests/conftest.py` | `mock_redis()`, `mock_settings()`, `mock_db()`, `make_position_row()` |
| `app/ml/features/tests/conftest.py` | `make_eta_features_dict()`, `make_eta_features_df()`, `make_mapping_result()` |
| `app/ml/models/tests/conftest.py` | `sample_training_df()`, `trained_model()`, `tmp_registry()`, `registered_model()` |
| `app/transit/tests/conftest.py` | `make_eticket_line()`, `make_eticket_txt()` |
| `app/core/agents/tests/conftest.py` | `make_agent_result()`, `make_skill_meta()`, `make_breaker()` |

### Testing Patterns
- **Route tests:** `app.dependency_overrides[get_current_user]` override + `limiter.enabled = False`
- **Agent tool tests:** `RunContext` mock with `MagicMock()`, async fn tests, error message assertions
- **ML model tests:** `trained_model` session-scoped fixture, `ModelRegistry` with temp dir
- **All unit tests** — no `@pytest.mark.integration` in affected modules

## Type Check Baseline

| Module | Pyright | Mypy |
|--------|---------|------|
| `app/ml/` | 25 (pre-existing: Settings attr, test conftest) | 13 (same root causes) |
| `app/transit/` | 0 | 0 |
| `app/core/agents/` | 0 | 0 |

All pre-existing errors are from ML-1.2 load features / ML-3 anomaly detection (missing Settings fields, test conftest symbols). Unrelated to ML-2.3.

## Files to Create/Modify

| Action | File | Purpose |
|--------|------|---------|
| CREATE | `app/ml/eta_service.py` | ETAService singleton — model cache, predict, hot-reload, fallback |
| CREATE | `app/ml/tests/test_eta_service.py` | ETAService unit tests (8 tests) |
| CREATE | `app/transit/schemas_eta.py` | `ETAResponse` Pydantic schema for REST endpoint |
| UPDATE | `app/transit/routes.py` | Add `GET /vehicles/{vehicle_id}/eta` endpoint |
| UPDATE | `app/transit/service.py` | Add `get_eta()` method delegating to ETAService |
| CREATE | `app/core/agents/tools/transit/predict_eta.py` | `predict_eta` agent tool |
| CREATE | `app/core/agents/tools/transit/tests/test_predict_eta.py` | Agent tool tests (5 tests) |
| UPDATE | `app/core/agents/agents/transit.py` | Add predict_eta to tool list + system prompt |
| UPDATE | `app/core/config.py` | Add ETA service config fields |
| UPDATE | `app/transit/tests/test_routes.py` | Add ETA endpoint tests (5 tests) |
| UPDATE | `app/core/agents/evals/schemas.py` | Add `predict_eta` to KNOWN_TOOLS (DONE — preflight) |
| UPDATE | `app/core/agents/tests/test_transit_agent.py` | Relax tool set assertion to `issubset` (DONE — preflight) |

## Implementation Steps

### Step 1: Config — Add ETA service settings
**File:** `app/core/config.py`
**Action:** Add to Settings class in ML section:
```python
# ETA Inference (ML-2.3)
eta_service_enabled: bool = True
eta_model_reload_interval_seconds: int = 300  # 5 min hot-reload check
eta_fallback_enabled: bool = True
```
**Validation:** `uv run ruff check app/core/config.py && uv run pyright app/core/config.py`

### Step 2: ETAService singleton
**File:** CREATE `app/ml/eta_service.py`
**Action:**
- `ETAService` class with `__init__(settings, registry_path)`:
  - `_model: ETAModel | None` — cached loaded model
  - `_model_version: int | None` — current version
  - `_last_reload_check: float` — monotonic timestamp
- `async def predict(self, db: AsyncSession, vehicle_id: str, stop_id: str) -> dict[str, Any]`:
  1. Resolve `vehicle_id` → latest `trip_id` from `vehicle_positions` (most recent record)
  2. Resolve `stop_id` → `stop_sequence` from GTFS static cache
  3. Call `extract_features(db, trip_id, stop_sequence, observed_at)`
  4. Call `self._model.predict(features)` → `ETAPrediction`
  5. Look up scheduled arrival from `GTFSStaticCache.trip_stop_times`
  6. Return dict with `predicted_arrival_at`, `delay_s`, `confidence_interval`, `model_version`, `fallback`
- `def _maybe_reload(self)` — check registry version pointer vs cached, reload if changed (sync, <50ms)
- `_ensure_model_loaded()` — lazy load on first predict call
- Fallback: if model load fails or features unavailable, return scheduled time + historical avg delay with `fallback: true`
- Module-level `_eta_service: ETAService | None = None` + `get_eta_service(settings) -> ETAService`
- Logging: `ml.eta_service.model_loaded`, `ml.eta_service.prediction_completed`, `ml.eta_service.fallback_used`, `ml.eta_service.reload_completed`
**Validation:** `uv run ruff format app/ml/eta_service.py && uv run ruff check --fix app/ml/eta_service.py && uv run pyright app/ml/eta_service.py`

### Step 3: ETA response schema
**File:** CREATE `app/transit/schemas_eta.py`
**Action:**
```python
from pydantic import BaseModel, ConfigDict, Field

class ETAResponse(BaseModel):
    model_config = ConfigDict(strict=True)
    vehicle_id: str
    stop_id: str
    predicted_arrival_at: str = Field(description="ISO 8601 UTC predicted arrival")
    delay_s: int = Field(description="Predicted delay in seconds (positive = late)")
    confidence_lower_s: int = Field(description="10th percentile delay bound")
    confidence_upper_s: int = Field(description="90th percentile delay bound")
    scheduled_arrival_at: str | None = Field(None, description="ISO 8601 scheduled arrival if known")
    model_version: str | None = Field(None, description="Model version used, null if fallback")
    fallback: bool = Field(False, description="True if using scheduled time instead of ML prediction")
    source: Literal["model", "fallback"] = "model"
```
**Validation:** `uv run ruff format app/transit/schemas_eta.py && uv run ruff check --fix app/transit/schemas_eta.py && uv run pyright app/transit/schemas_eta.py`

### Step 4: Transit service — add get_eta method
**File:** `app/transit/service.py`
**Action:** Add `async def get_eta(self, db: AsyncSession, vehicle_id: str, stop_id: str) -> ETAResponse`:
- Import and call `get_eta_service(settings).predict(db, vehicle_id, stop_id)`
- Map result dict → `ETAResponse` schema
- Log `transit.eta.requested` and `transit.eta.completed`
**Validation:** `uv run ruff check app/transit/service.py && uv run pyright app/transit/service.py`

### Step 5: REST endpoint
**File:** `app/transit/routes.py`
**Action:** Add endpoint after existing vehicle endpoints:
```python
@router.get("/vehicles/{vehicle_id}/eta", response_model=ETAResponse)
@limiter.limit("30/minute")
async def get_vehicle_eta(
    request: Request,
    vehicle_id: str = Path(max_length=100, pattern=r"^[\w\-.:]+$"),
    stop_id: str = Query(..., max_length=100, pattern=r"^[\w\-.:]+$"),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> ETAResponse:
```
- Delegate to `TransitService.get_eta(db, vehicle_id, stop_id)`
- Import `ETAResponse` from `schemas_eta`
**Validation:** `uv run ruff check app/transit/routes.py && uv run pyright app/transit/routes.py`

### Step 6: predict_eta agent tool
**File:** CREATE `app/core/agents/tools/transit/predict_eta.py`
**Action:**
- Async tool function: `async def predict_eta(ctx: RunContext[UnifiedDeps], vehicle_id: str, stop_id: str) -> str`
- LLM-optimized docstring with WHEN TO USE / WHEN NOT TO USE / COMPOSITION sections
- Get DB session from `ctx.deps.db_session_factory`
- Call `get_eta_service(ctx.deps.settings).predict(db, vehicle_id, stop_id)`
- Return `json.dumps(result, ensure_ascii=False)`
- Error fallback: return error string (never raise from tools)
- Logging: `agent.predict_eta.started`, `agent.predict_eta.completed`, `agent.predict_eta.failed`
**Validation:** `uv run ruff check app/core/agents/tools/transit/predict_eta.py && uv run pyright app/core/agents/tools/transit/predict_eta.py`

### Step 7: Register tool in transit agent
**File:** `app/core/agents/agents/transit.py`
**Action:**
- Import `predict_eta` from `app.core.agents.tools.transit.predict_eta`
- Add to `tools=[...]` list in `create_agent()` (after check_driver_availability)
- Add to `TRANSIT_SYSTEM_PROMPT`: short section "### ETA Predictions" explaining when to use predict_eta vs query_bus_status
- Add Latvian glossary term: `ETA/ierašanās laiks` (arrival time)
**Validation:** `uv run ruff check app/core/agents/agents/transit.py && uv run pyright app/core/agents/agents/transit.py`

### Step 8: Also register in unified agent if separate
**File:** Check `app/core/agents/agent.py` (or wherever unified agent creates tool list)
**Action:** Add `predict_eta` to the unified agent's tools list if tools are listed separately from transit agent.
**Validation:** `uv run ruff check app/core/agents/agent.py && uv run pyright app/core/agents/agent.py`

### Step 9: ETAService unit tests
**File:** CREATE `app/ml/tests/test_eta_service.py`
**Tests (8):**
1. `test_predict_happy_path` — mock model + features, verify ETAPrediction returned with correct fields
2. `test_predict_returns_confidence_interval` — verify lower/upper bounds present
3. `test_fallback_on_model_load_failure` — model path missing → fallback with scheduled time
4. `test_fallback_on_feature_extraction_failure` — DB query fails → fallback
5. `test_hot_reload_detects_version_change` — mock registry version bump → model reloaded
6. `test_hot_reload_skips_when_interval_not_elapsed` — verify cooldown respected
7. `test_get_eta_service_singleton` — same instance returned on repeated calls
8. `test_predict_logs_structured_event` — verify `ml.eta_service.prediction_completed` logged with expected fields

**Mocking pattern:** Patch `ModelRegistry`, `ETAModel.predict`, `extract_features`, `GTFSStaticCache`
**Validation:** `uv run pytest app/ml/tests/test_eta_service.py -v`

### Step 10: REST endpoint tests
**File:** `app/transit/tests/test_routes.py`
**Tests (5):**
1. `test_get_vehicle_eta_success` — mock service → 200 with ETAResponse fields
2. `test_get_vehicle_eta_not_found` — vehicle not tracked → 404
3. `test_get_vehicle_eta_fallback` — model unavailable → 200 with `fallback: true`
4. `test_get_vehicle_eta_requires_auth` — no token → 401/403
5. `test_get_vehicle_eta_invalid_stop_id` — stop_id too long → 422

**Pattern:** Follow existing test_routes.py auth override + service patch pattern
**Validation:** `uv run pytest app/transit/tests/test_routes.py -v`

### Step 11: Agent tool tests
**File:** CREATE `app/core/agents/tools/transit/tests/test_predict_eta.py`
**Tests (5):**
1. `test_predict_eta_returns_json` — mock ETAService → valid JSON response string
2. `test_predict_eta_fallback_in_response` — model failure → JSON with `fallback: true`
3. `test_predict_eta_logs_started_completed` — structured log assertions
4. `test_predict_eta_handles_db_error` — DB unavailable → error string (not exception)
5. `test_predict_eta_missing_db_session_factory` — `ctx.deps.db_session_factory is None` → graceful error

**Pattern:** Follow test_query_bus_status.py — mock context, AsyncMock deps
**Validation:** `uv run pytest app/core/agents/tools/transit/tests/test_predict_eta.py -v`

### Step 12: Transit agent test update
**File:** `app/core/agents/tests/test_transit_agent.py`
**Action:** Update tool count assertion from 5 → 6 (add predict_eta to expected tool list)
**Validation:** `uv run pytest app/core/agents/tests/test_transit_agent.py -v`

### Step 13: Final validation
**Action:** Run full suite
```bash
uv run ruff format app/ml/ app/transit/ app/core/agents/
uv run ruff check --fix app/ml/ app/transit/ app/core/agents/
uv run pyright app/ml/ app/transit/ app/core/agents/
uv run mypy app/ml/ app/transit/ app/core/agents/
uv run pytest app/ml/tests/ app/transit/tests/ app/core/agents/tests/ -v --tb=short
```

## Preflight Warnings

- **Transit agent tool count assertion** in `test_transit_agent.py` — hardcoded `assert len(tools) == 5`. Must update to 6 in Step 12.
- **Unified agent tool list** — may be separate from transit agent. Check `agent.py` for duplicate tool registration.
- **Settings attrs** — 25 pre-existing pyright errors in `app/ml/` from missing Settings fields. Don't confuse with new errors.
- **Model registry singleton** — `ModelRegistry` uses `@lru_cache`. ETAService should NOT also use `@lru_cache` — use module-level variable pattern instead for testability.

## Security Checklist

For the new `GET /v1/transit/vehicles/{vehicle_id}/eta` endpoint:
- [ ] `Depends(get_current_user)` auth dependency
- [ ] `@limiter.limit("30/minute")` rate limiting
- [ ] `vehicle_id: Path(max_length=100, pattern=r"^[\w\-.:]+$")` input validation
- [ ] `stop_id: Query(max_length=100, pattern=r"^[\w\-.:]+$")` input validation
- [ ] Error responses use `AppError` hierarchy (404 for not found, no internal leakage)
- [ ] Model version string sanitized (no file paths in response)
- [ ] Agent tool returns error string, never raises

For the `predict_eta` agent tool:
- [ ] DB session null check before use
- [ ] No credential/path exposure in tool response
- [ ] LLM-optimized docstring with WHEN TO USE sections

## Verification

- [ ] `make check` passes (lint + types + tests)
- [ ] `make security-audit-quick` passes
- [ ] New endpoint has auth + rate limiting
- [ ] Pyright `app/transit/` stays at 0 errors
- [ ] Pyright `app/core/agents/` stays at 0 errors
- [ ] Pyright `app/ml/` stays at ≤25 errors (pre-existing baseline)
- [ ] `GET /v1/transit/vehicles/22-47/eta?stop_id=1234` returns ETAResponse with model_version
- [ ] Agent query "when does bus 22-47 reach Brīvības?" triggers predict_eta tool
- [ ] Force fallback (bad model path) → endpoint returns `fallback: true` with scheduled time
- [ ] Security convention tests pass: `uv run pytest app/tests/test_security.py -v`
- [ ] Transit agent test updated: tool count == 6
