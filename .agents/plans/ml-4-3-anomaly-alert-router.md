# Plan: ML-4.3 Anomaly Detection Routing + Deduplication

## Context

Three anomaly detectors exist (off_route, stuck_vehicle, gps_gap/feed_outage) but each has its own inline cooldown + dedup logic. This causes: duplicated policy code across detectors, no centralized severity routing, and no REST endpoint for the CMS to query recent anomalies. ML-4.3 adds a central `AnomalyAlertRouter` that owns all routing/cooldown/dedup policy, making detectors pure detection functions.

## Security Context Assessment

| Context | Applies? | Reason |
|---------|----------|--------|
| CTX-RBAC | **Yes** | New `GET /v1/ml/anomalies/recent` endpoint needs auth + role gating |
| CTX-INPUT | **Yes** | Query params (limit, type filter, severity filter) need validation |
| CTX-AUTH | No | No auth flow changes |
| CTX-FILE | No | No file handling |
| CTX-AGENT | No | No agent tool changes |
| CTX-INFRA | No | No Docker/nginx/config infrastructure changes |

## Research Summary

### Existing Detector Architecture

| File | Role |
|------|------|
| `app/ml/anomaly/off_route.py` | PostGIS corridor containment detection, has inline cooldown + dedup |
| `app/ml/anomaly/stuck.py` | TimescaleDB movement analysis, inline cooldown via `ml:stuck:{vid}` |
| `app/ml/anomaly/gps_gap.py` | GPS gap + feed outage detection, inline cooldown via `ml:gps_gap:{vid}` |
| `app/ml/anomaly/evaluator.py` | Orchestrator for stuck + gps_gap, calls `find_active_duplicate()` for DB dedup |
| `app/alerts/service.py` | `AlertService.create_alert(data: AlertInstanceCreate) -> AlertInstanceResponse` |
| `app/alerts/repository.py:163-177` | `find_active_duplicate(rule_id, entity_type, entity_id)` — DB-level dedup |
| `app/alerts/schemas.py` | `AlertInstanceCreate` with `alert_type: AlertRuleType` (includes all 4 anomaly types) |
| `app/alerts/models.py` | `AlertInstance` table with severity, status, alert_type, details JSONB |

### Key Patterns

- **Redis cooldown:** `await redis.set(key, "1", ex=ttl)` / `await redis.get(key)` — returns `b"1"` or `None`
- **Current cooldown keys:** `ml:stuck:{vid}`, `ml:gps_gap:{vid}`, `ml:feed_outage:{feed_id}`
- **New cooldown keys:** `anomaly:cooldown:{type}:{entity_id}` with severity-based TTL
- **Old keys expire naturally** (TTL ≤ 15 min) — no migration script needed
- **Config pattern:** `app/core/config.py` flat attrs, e.g. `anomaly_cooldown_critical_seconds: int = 300`
- **Pagination:** `PaginationParams` + `PaginatedResponse[T]` from `app.shared.schemas`
- **Rate limiting:** `@limiter.limit("30/minute")` with `request: Request` param
- **Auth:** `require_role(["admin", "dispatcher", "viewer"])` from `app.auth.dependencies`

### Architecture Decision: No New Table

Reuse `alert_instances` with filtered query: `WHERE alert_type IN ('stuck_vehicle', 'gps_gap', 'feed_outage', 'off_route')`. Creating a separate `anomalies` table would duplicate the schema. The "Redis stream" option from the spec was evaluated and rejected — alerts need persistence and status tracking (acknowledged/resolved).

### Architecture Decision: Endpoint in `app/ml/anomaly/routes.py`

CLAUDE.md says ML has "no REST endpoints." However, anomaly data is semantically an ML feature. Creating the route in `app/transit/routes.py` would violate VSA boundaries. We create `app/ml/anomaly/routes.py` with its own router and update CLAUDE.md's ML description to note this exception.

### Architecture Decision: Channel Matrix is Config-Only

No Slack/SMS integration exists. The channel matrix is a config dict that the router reads and logs for observability. `route()` only calls `AlertService.create_alert()`. Channel dispatch is a future task.

## Test Landscape

### Existing Test Files
| File | Tests | Key Patterns |
|------|-------|--------------|
| `app/ml/tests/test_evaluator.py` | 2 | Orchestrator mock, error handling |
| `app/ml/tests/test_stuck.py` | 7 | Redis cooldown mock, `make_position_row` |
| `app/ml/tests/test_gps_gap.py` | 7 | Feed suppression, cooldown active=`b"1"` |
| `app/ml/anomaly/tests/test_off_route.py` | 12 | Corridor caching, consecutive hits |
| `app/alerts/tests/test_service.py` | 11 | AlertService mock, `make_alert_instance` |
| `app/alerts/tests/test_routes.py` | 8 | Auth override, RBAC, pagination |

### Available Fixtures
- `app/ml/tests/conftest.py`: `make_position_row`, `make_gap_row`, `mock_redis`, `mock_settings`, `mock_db`, `make_db_result`
- `app/ml/anomaly/tests/conftest.py`: `make_vehicle_data`, `mock_redis` (AsyncMock), `mock_db_context`
- `app/alerts/tests/conftest.py`: `make_alert_rule`, `make_alert_instance`, `sample_alert`, `mock_db`

### Auth Test Pattern
```python
app.dependency_overrides[get_current_user] = lambda: _mock_user("admin")
# ... test ...
app.dependency_overrides.pop(get_current_user, None)
```

## Type Check Baseline

| Area | Pyright | MyPy |
|------|---------|------|
| `app/ml/` (23 files) | 0 errors | 0 errors |
| `app/alerts/` (13 files) | 0 errors | 0 errors |
| `app/transit/routes.py` | 0 errors | 0 errors |

**Target:** 0 new errors introduced.

## Files to Create/Modify

| Action | File | Purpose |
|--------|------|---------|
| CREATE | `app/ml/anomaly/router.py` | Central `AnomalyAlertRouter` — severity routing, Redis cooldowns, channel matrix |
| CREATE | `app/ml/anomaly/schemas.py` | `AnomalyEvent` dataclass, `AnomalyResponse` schema, `AnomalyChannelConfig` |
| CREATE | `app/ml/anomaly/routes.py` | `GET /api/v1/ml/anomalies/recent` — paginated, filtered, auth-gated |
| CREATE | `app/ml/anomaly/tests/test_router.py` | 12+ unit tests for router logic |
| UPDATE | `app/ml/anomaly/evaluator.py` | Remove inline dedup, call `AnomalyAlertRouter.route()` instead |
| UPDATE | `app/ml/anomaly/stuck.py` | Remove inline cooldown logic, return raw `AnomalyEvent` list |
| UPDATE | `app/ml/anomaly/gps_gap.py` | Remove inline cooldown logic, return raw `AnomalyEvent` list |
| UPDATE | `app/ml/anomaly/off_route.py` | Remove inline cooldown logic, return raw `AnomalyEvent` list |
| UPDATE | `app/core/config.py` | Add ML-4.3 settings (cooldown TTLs, channel matrix, feature flag) |
| UPDATE | `app/main.py` | Register anomaly router |

## Implementation Steps

### Step 1: Config settings (`app/core/config.py`)

Add after existing ML-4.2 settings (~line 280):

```python
# Anomaly alert routing (ML-4.3)
anomaly_routing_enabled: bool = True
anomaly_cooldown_critical_seconds: int = 300   # 5 min
anomaly_cooldown_warning_seconds: int = 1800   # 30 min
anomaly_recent_window_hours: int = 24
```

**Validation:** `uv run ruff check app/core/config.py && uv run pyright app/core/config.py`

### Step 2: Schemas (`app/ml/anomaly/schemas.py`)

Create `AnomalyEvent` frozen dataclass (detector output) and `AnomalyResponse` Pydantic schema (API response):

```python
from __future__ import annotations
import datetime
from dataclasses import dataclass
from typing import Literal
from pydantic import BaseModel, Field

AnomalyType = Literal["off_route", "stuck_vehicle", "gps_gap", "feed_outage"]
AnomalySeverity = Literal["critical", "high", "medium", "low"]
AnomalyChannel = Literal["dashboard", "slack", "sms", "pager"]

@dataclass(frozen=True)
class AnomalyEvent:
    """Detector output — immutable event before routing policy."""
    anomaly_type: AnomalyType
    severity: AnomalySeverity
    source_entity_type: str  # "vehicle" or "feed"
    source_entity_id: str
    title: str
    details: dict[str, str | int | float | bool | None]
    detected_at: datetime.datetime

CHANNEL_MATRIX: dict[AnomalyType, list[AnomalyChannel]] = {
    "off_route": ["dashboard", "slack"],
    "stuck_vehicle": ["dashboard", "slack"],
    "gps_gap": ["dashboard"],
    "feed_outage": ["slack", "pager"],
}

class AnomalyResponse(BaseModel):
    """API response for a single anomaly alert."""
    id: int
    title: str
    severity: str
    alert_type: str
    source_entity_type: str | None
    source_entity_id: str | None
    details: dict[str, str | int | float | bool | None] | None
    status: str
    created_at: datetime.datetime
```

**Validation:** `uv run ruff format app/ml/anomaly/schemas.py && uv run ruff check app/ml/anomaly/schemas.py && uv run pyright app/ml/anomaly/schemas.py`

### Step 3: Router (`app/ml/anomaly/router.py`)

Central routing class:

```python
class AnomalyAlertRouter:
    """Routes anomaly events to alert channels with Redis cooldowns (ML-4.3)."""

    def __init__(self, redis: Redis, settings: Settings) -> None:
        self._redis = redis
        self._settings = settings

    async def route(self, event: AnomalyEvent, db: AsyncSession) -> bool:
        """Route an anomaly event. Returns True if alert was created, False if suppressed."""
        # 1. Check Redis cooldown
        cooldown_key = f"anomaly:cooldown:{event.anomaly_type}:{event.source_entity_id}"
        if await self._redis.get(cooldown_key) is not None:
            logger.info("anomaly.router.cooldown_suppressed", ...)
            return False

        # 2. Create alert via AlertInstanceRepository
        alert_data = AlertInstanceCreate(
            title=event.title,
            severity=_map_severity(event.severity),
            alert_type=event.anomaly_type,
            source_entity_type=event.source_entity_type,
            source_entity_id=event.source_entity_id,
            details=event.details,
        )
        repo = AlertInstanceRepository(db)
        await repo.create(alert_data)

        # 3. Set cooldown
        ttl = (self._settings.anomaly_cooldown_critical_seconds
               if event.severity == "critical"
               else self._settings.anomaly_cooldown_warning_seconds)
        await self._redis.set(cooldown_key, "1", ex=ttl)

        # 4. Log channel routing (config-only, no dispatch yet)
        channels = CHANNEL_MATRIX.get(event.anomaly_type, ["dashboard"])
        logger.info("anomaly.router.alert_created", channels=channels, ...)
        return True
```

**Validation:** `uv run ruff format app/ml/anomaly/router.py && uv run ruff check app/ml/anomaly/router.py && uv run pyright app/ml/anomaly/router.py`

### Step 4: Refactor detectors — remove inline cooldown/dedup

**`app/ml/anomaly/stuck.py`:**
- Remove Redis cooldown check (`redis.get(f"ml:stuck:{vid}")`) and set (`redis.set(...)`)
- Change return type from `list[AlertInstanceCreate]` to `list[AnomalyEvent]`
- Remove `redis` parameter from `check()` if no longer needed for detection logic
- Build `AnomalyEvent` instead of `AlertInstanceCreate`

**`app/ml/anomaly/gps_gap.py`:**
- Same pattern: remove cooldown, return `list[AnomalyEvent]`
- Feed outage events: `source_entity_type="feed"`, `source_entity_id=feed_id`

**`app/ml/anomaly/off_route.py`:**
- Remove cooldown check, return `list[AnomalyEvent]`
- Keep PostGIS corridor logic intact

**`app/ml/anomaly/evaluator.py`:**
- Remove `find_active_duplicate()` calls
- Create `AnomalyAlertRouter` instance
- For each detector's events, call `router.route(event, db)`
- Log total created vs suppressed

**Validation:** `uv run ruff check app/ml/anomaly/ && uv run pyright app/ml/anomaly/ && uv run mypy app/ml/anomaly/`

### Step 5: REST endpoint (`app/ml/anomaly/routes.py`)

```python
router = APIRouter(prefix="/api/v1/ml/anomalies", tags=["anomalies"])

ANOMALY_TYPES = {"stuck_vehicle", "gps_gap", "feed_outage", "off_route"}

@router.get("/recent", response_model=PaginatedResponse[AnomalyResponse])
@limiter.limit("30/minute")
async def list_recent_anomalies(
    request: Request,
    pagination: PaginationParams = Depends(),
    alert_type: str | None = Query(None, max_length=50),
    severity: str | None = Query(None, max_length=20),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_role(["admin", "dispatcher", "viewer"])),
) -> PaginatedResponse[AnomalyResponse]:
    """List recent anomaly alerts with optional filters."""
    # Query alert_instances WHERE alert_type IN ANOMALY_TYPES
    # Apply optional type/severity filters
    # Order by created_at DESC
    # Return paginated response
```

**Validation:** `uv run ruff check app/ml/anomaly/routes.py && uv run pyright app/ml/anomaly/routes.py`

### Step 6: Register router (`app/main.py`)

```python
from app.ml.anomaly.routes import router as anomaly_router
# ...
app.include_router(anomaly_router)
```

**Validation:** `uv run ruff check app/main.py && uv run pyright app/main.py`

### Step 7: Tests (`app/ml/anomaly/tests/test_router.py`)

12+ tests mapping to spec:

| # | Test | Category |
|---|------|----------|
| 1 | `test_route_off_route_dispatches_to_dashboard_slack` | Router dispatches per type |
| 2 | `test_route_stuck_vehicle_dispatches_to_dashboard_slack` | Router dispatches per type |
| 3 | `test_route_gps_gap_dispatches_to_dashboard_only` | Router dispatches per type |
| 4 | `test_cooldown_suppresses_duplicate_anomaly` | Cooldown enforcement |
| 5 | `test_cooldown_allows_after_expiry` | Cooldown enforcement |
| 6 | `test_critical_severity_uses_short_cooldown` | Severity escalation |
| 7 | `test_warning_severity_uses_long_cooldown` | Severity escalation |
| 8 | `test_feed_outage_routes_to_slack_pager` | Channel selection |
| 9 | `test_stuck_critical_routes_to_dashboard_slack_sms` | Channel selection |
| 10 | `test_endpoint_requires_auth` | Endpoint auth |
| 11 | `test_cooldown_key_cleared_on_resolve` | Cooldown reset (if applicable) |
| 12 | `test_anomaly_response_schema_matches_spec` | Alert payload schema |

**Additional tests:**
| 13 | `test_endpoint_pagination` | Pagination params |
| 14 | `test_endpoint_filters_by_type` | Type filter |
| 15 | `test_endpoint_filters_by_severity` | Severity filter |

**Validation:** `uv run pytest app/ml/anomaly/tests/test_router.py -v && uv run pyright app/ml/anomaly/tests/test_router.py`

### Step 8: Update existing detector tests

Update `test_stuck.py`, `test_gps_gap.py`, `test_off_route.py`, `test_evaluator.py` to reflect:
- Detectors return `AnomalyEvent` not `AlertInstanceCreate`
- No Redis cooldown assertions in detector tests (moved to router tests)
- Evaluator tests mock `AnomalyAlertRouter.route()` instead of `find_active_duplicate()`

**Validation:** `uv run pytest app/ml/ -v`

## Preflight Warnings

- `app/ml/anomaly/evaluator.py` has inline `find_active_duplicate()` calls — must be replaced, not layered
- `app/ml/anomaly/stuck.py` has inline `redis.get/set` for cooldowns — must be removed
- `app/ml/anomaly/gps_gap.py` same pattern
- Existing tests assert on cooldown behavior within detector tests — must be updated
- `AlertRuleType` Literal in `app/alerts/schemas.py` already includes all 4 anomaly types — no change needed

## Security Checklist

- [x] `AlertRuleType` already includes anomaly types — no new Literal values needed
- [ ] `require_role(["admin", "dispatcher", "viewer"])` on `GET /recent`
- [ ] `@limiter.limit("30/minute")` rate limiting
- [ ] `alert_type` and `severity` query params have `max_length` constraints
- [ ] Error responses use `AppError` hierarchy (404 for not found)
- [ ] No `escape_like()` needed (no ILIKE queries — exact match filters only)
- [ ] Auth test: no token → 401/403
- [ ] RBAC test: unauthorized role → 403

## Verification

- [ ] `make lint` passes (ruff format + check)
- [ ] `make types` passes (mypy + pyright)
- [ ] `make test` passes (all 1969+ tests)
- [ ] `make security-audit-quick` passes
- [ ] Pyright errors = 0 (baseline was 0)
- [ ] New endpoint has auth + rate limiting
- [ ] 12+ new tests pass
- [ ] Existing ML tests still pass after detector refactor
- [ ] Security convention tests pass: `uv run pytest app/tests/test_security.py -v`

## Acceptance Criteria (from spec)

1. Trigger all 3 anomaly types for same vehicle → exactly 3 alerts (one per type), no duplicates
2. Trigger same anomaly 30s later → suppressed by cooldown
3. `GET /v1/ml/anomalies/recent` returns events in reverse-chronological order
4. Channel matrix logged per anomaly type
5. Critical cooldown = 5 min, warning cooldown = 30 min
