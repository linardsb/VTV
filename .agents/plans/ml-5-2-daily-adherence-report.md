# Plan: ML-5.2 Schedule Adherence Monitoring + Daily Report

## Context

Dispatchers see real-time delays via the existing `on-time-performance` endpoint, but managers lack daily trend reports for schedule revision decisions, driver training, and vehicle re-assignment. This feature automates the current manual spreadsheet process with a scheduled daily job that computes fleet-wide schedule adherence (overall %, per-route, per-hour), stores it in a `daily_adherence_reports` table, publishes a Slack/email summary, and fires a high-severity alert when overall adherence drops below a configurable threshold (default 85%).

## Security Context Assessment

**Active contexts:** CTX-RBAC, CTX-INPUT, CTX-INFRA

- **CTX-RBAC** — New `GET /v1/analytics/adherence/daily` endpoint needs `get_current_user` + rate limiting. Read-only, so no IDOR concern beyond standard auth.
- **CTX-INPUT** — `from`/`to` date query params need `max_length` + pattern validation.
- **CTX-INFRA** — Slack webhook URL stored as env var config (no hardcoded credentials). SMTP config also via env vars.

## Research Summary

### Existing Patterns (app/analytics/)
- **routes.py** — 4 endpoints on `APIRouter(prefix="/api/v1/analytics")`, uses `AnalyticsService(db)`, `@limiter.limit()`, `get_current_user` auth.
- **service.py** — `AnalyticsService` with async methods, delegates to `_compute_route_adherence()` from agent transit tools.
- **schemas.py** — Pydantic response models with `ConfigDict(from_attributes=True)`, `Literal` types for constrained strings.
- No models.py yet — analytics has been compute-only, no DB tables.

### Adherence Computation (app/core/agents/tools/transit/get_adherence_report.py)
- `_compute_route_adherence()` — per-route on-time %, average delay. Uses ±300s threshold.
- `GTFSStaticCache` from `static_store.py` — cached GTFS schedule data.
- `GTFSRealtimeClient` from `client.py` — async GTFS-RT fetcher.
- `RouteAdherence` schema — `on_time_count`, `late_count`, `early_count`, `on_time_percentage`, `average_delay_seconds`.

### Background Task Pattern (app/memory/lifecycle.py)
- `_run_at_hour(hour, name, coro_factory)` — daily UTC scheduler via `asyncio.sleep`.
- `start_memory_tasks()` / `stop_memory_tasks()` — registered in `app/main.py` lifespan.
- When `background_queue_enabled=True`, defers to arq cron jobs instead.

### Alert Integration (app/alerts/)
- `AlertInstanceCreate(title, severity, alert_type, source_entity_type, source_entity_id, details, rule_id)`.
- `AlertService(db).create_alert(data)` — programmatic alert creation.
- `AlertRuleType` — Literal with 11 values. Need to add `"schedule_adherence"`.
- Adding new alert type requires migration to update CHECK constraint (see `n7o8p9q0r1s2`).

### Config Pattern (app/core/config.py)
- Pydantic Settings with env var loading. Threshold pattern: `ml_stuck_distance_threshold_m: float = 20.0`.
- No existing Slack webhook or SMTP config.

## Test Landscape

### Existing Analytics Tests
- `app/analytics/tests/test_service.py` (217 lines) — `_make_result()`, `_mock_db_fleet_data()` helpers, `AsyncMock` for DB.
- `app/analytics/tests/test_routes.py` (217 lines) — `dependency_overrides` for auth+DB, `@patch("app.analytics.routes.AnalyticsService")`.
- `app/analytics/tests/conftest.py` — minimal (2 lines).

### Alert Test Patterns
- `app/alerts/tests/conftest.py` (111 lines) — `make_alert_rule()`, `make_alert_instance()` factories with `**overrides`.

### Job Queue Test Patterns
- `app/core/jobs/tests/conftest.py` (46 lines) — `mock_arq_pool`, `mock_settings_queue_enabled/disabled`.
- `app/core/jobs/tests/test_queue.py` — patch `get_settings` + `get_arq_pool`, assert `enqueue_job.assert_awaited_once_with(...)`.

### ML Evaluator Test Patterns
- `app/ml/tests/conftest.py` (102 lines) — `make_position_row()`, `mock_redis`, `mock_settings`.

## Type Check Baseline

| Target | Pyright | Mypy |
|--------|---------|------|
| `app/analytics/` | 0 errors | 0 errors |
| `app/core/config.py` | 0 errors | — |
| `app/core/jobs/` | 0 errors | — |

## Files to Create/Modify

| Action | File | Purpose |
|--------|------|---------|
| CREATE | `alembic/versions/o8p9q0r1s2t3_daily_adherence_reports.py` | Migration: `daily_adherence_reports` table + update alert rule_type CHECK |
| CREATE | `app/analytics/models.py` | `DailyAdherenceReport` SQLAlchemy model |
| UPDATE | `app/analytics/schemas.py` | Add `DailyAdherenceReportResponse`, `PerRouteAdherence`, `PerHourAdherence` |
| CREATE | `app/analytics/daily_adherence.py` | Compute + publish + alert logic, background task lifecycle |
| UPDATE | `app/analytics/routes.py` | Add `GET /api/v1/analytics/adherence/daily` endpoint |
| UPDATE | `app/core/config.py` | Add threshold, Slack webhook, SMTP config fields |
| UPDATE | `app/main.py` | Register `start_adherence_task()` / `stop_adherence_task()` in lifespan |
| UPDATE | `app/alerts/schemas.py` | Add `"schedule_adherence"` to `AlertRuleType` Literal |
| UPDATE | `app/alerts/models.py` | Add `"schedule_adherence"` to CHECK constraint string (code-level) |
| CREATE | `app/analytics/tests/test_daily_adherence.py` | Unit tests: compute, publish, threshold alert, date-range query |
| UPDATE | `app/analytics/tests/conftest.py` | Add `make_daily_adherence_report()` factory |
| UPDATE | `app/core/jobs/worker.py` | Add `run_daily_adherence` arq cron job |
| UPDATE | `app/core/jobs/routes.py` | Add `"run_daily_adherence"` to job status loop |

## Implementation Steps

### Step 1: Config additions
**File:** `app/core/config.py` (UPDATE)

Add to `Settings` class:
```python
# ML-5.2: Daily adherence report
analytics_adherence_enabled: bool = True
analytics_adherence_threshold_pct: float = 85.0
analytics_adherence_cron_hour: int = 6  # 06:00 UTC
analytics_adherence_slack_webhook: str | None = None
analytics_adherence_smtp_enabled: bool = False
analytics_adherence_smtp_host: str = "localhost"
analytics_adherence_smtp_port: int = 587
analytics_adherence_smtp_from: str = "vtv@example.com"
analytics_adherence_smtp_to: str = ""  # comma-separated
```

**Validation:** `uv run ruff check app/core/config.py && uv run pyright app/core/config.py`

### Step 2: Alert type extension
**Files:** `app/alerts/schemas.py`, `app/alerts/models.py` (UPDATE)

Add `"schedule_adherence"` to `AlertRuleType` Literal in schemas.py. Update the CHECK constraint string in models.py `__table_args__` to include the new value.

**Important:** Grep for all usages of `AlertRuleType` — the Literal is the source of truth, and the CHECK constraint in the migration must match.

**Validation:** `uv run ruff check app/alerts/schemas.py app/alerts/models.py && uv run pyright app/alerts/`

### Step 3: Migration
**File:** `alembic/versions/o8p9q0r1s2t3_daily_adherence_reports.py` (CREATE)

```python
revision = "o8p9q0r1s2t3"
down_revision = "n7o8p9q0r1s2"
```

**upgrade():**
1. Create `daily_adherence_reports` table:
   - `id: Integer, PK, autoincrement`
   - `report_date: Date, nullable=False, unique=True` (one report per day)
   - `overall_pct: Float, nullable=False`
   - `total_trips: Integer, nullable=False`
   - `on_time_trips: Integer, nullable=False`
   - `late_trips: Integer, nullable=False`
   - `early_trips: Integer, nullable=False`
   - `per_route_json: JSONB, nullable=False` (list of per-route breakdowns)
   - `per_hour_json: JSONB, nullable=False` (list of per-hour breakdowns)
   - `anomaly_count: Integer, nullable=False, default=0`
   - `alert_triggered: Boolean, nullable=False, default=False`
   - `created_at: DateTime(timezone=True), nullable=False`
   - `updated_at: DateTime(timezone=True), nullable=False`
2. Add index: `ix_daily_adherence_reports_report_date` on `report_date`
3. Drop + recreate `ck_alert_rules_rule_type` CHECK constraint with `"schedule_adherence"` added

**downgrade():**
1. Drop table `daily_adherence_reports`
2. Restore CHECK constraint without `"schedule_adherence"`

**Validation:** `uv run ruff check alembic/versions/o8p9q0r1s2t3_daily_adherence_reports.py`

### Step 4: SQLAlchemy model
**File:** `app/analytics/models.py` (CREATE)

```python
class DailyAdherenceReport(TimestampMixin, Base):
    __tablename__ = "daily_adherence_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    report_date: Mapped[datetime.date] = mapped_column(Date, unique=True, nullable=False)
    overall_pct: Mapped[float] = mapped_column(Float, nullable=False)
    total_trips: Mapped[int] = mapped_column(Integer, nullable=False)
    on_time_trips: Mapped[int] = mapped_column(Integer, nullable=False)
    late_trips: Mapped[int] = mapped_column(Integer, nullable=False)
    early_trips: Mapped[int] = mapped_column(Integer, nullable=False)
    per_route_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    per_hour_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    anomaly_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    alert_triggered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
```

Imports: `Base` from `app.core.database`, `TimestampMixin` from `app.shared.models`, standard SQLAlchemy types.

**Validation:** `uv run ruff check app/analytics/models.py && uv run pyright app/analytics/models.py`

### Step 5: Response schemas
**File:** `app/analytics/schemas.py` (UPDATE)

Add at end:
```python
class PerRouteAdherence(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    route_id: str
    route_short_name: str
    total_trips: int
    on_time_trips: int
    late_trips: int
    early_trips: int
    on_time_pct: float
    avg_delay_seconds: float

class PerHourAdherence(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    hour: int  # 0-23
    total_trips: int
    on_time_trips: int
    on_time_pct: float

class DailyAdherenceReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    report_date: datetime.date
    overall_pct: float
    total_trips: int
    on_time_trips: int
    late_trips: int
    early_trips: int
    per_route: list[PerRouteAdherence]
    per_hour: list[PerHourAdherence]
    anomaly_count: int
    alert_triggered: bool
    created_at: datetime.datetime
```

**Validation:** `uv run ruff check app/analytics/schemas.py && uv run pyright app/analytics/schemas.py`

### Step 6: Core service — daily_adherence.py
**File:** `app/analytics/daily_adherence.py` (CREATE)

This is the main service module. Structure:

```python
"""Daily schedule adherence computation, publishing, and background task lifecycle (ML-5.2)."""

import asyncio, datetime, json
from collections.abc import Awaitable, Callable
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.models import DailyAdherenceReport
from app.analytics.schemas import (
    DailyAdherenceReportResponse, PerRouteAdherence, PerHourAdherence,
)
from app.alerts.schemas import AlertInstanceCreate
from app.alerts.service import AlertService
from app.core.config import get_settings
from app.core.database import get_db_context
from app.core.logging import get_logger
from app.core.metrics import record_poller_tick
from app.core.agents.tools.transit.get_adherence_report import _compute_route_adherence
from app.core.agents.tools.transit.static_store import get_static_store
from app.core.agents.tools.transit.client import GTFSRealtimeClient

logger = get_logger(__name__)
_adherence_task: asyncio.Task[None] | None = None
```

**Functions:**

1. `async def compute_daily_report(target_date: datetime.date, db: AsyncSession) -> DailyAdherenceReport`
   - Get static store, get all routes, get trip updates for each route
   - Call `_compute_route_adherence()` per route
   - Aggregate: overall_pct, per_route_json, per_hour_json
   - Insert `DailyAdherenceReport` row (upsert on `report_date`)
   - Check threshold → if below, create alert via `AlertService`
   - Return the model instance

2. `async def publish_report(report: DailyAdherenceReport) -> None`
   - If Slack webhook configured: POST JSON summary via `httpx.AsyncClient`
   - If SMTP enabled: send email summary (use `aiosmtplib` or stdlib `smtplib` in executor)
   - Fail-open: log errors, never raise

3. `async def get_daily_reports(db: AsyncSession, date_from: datetime.date, date_to: datetime.date) -> list[DailyAdherenceReport]`
   - `select(DailyAdherenceReport).where(report_date >= date_from, report_date <= date_to).order_by(report_date)`

4. `async def _run_daily_adherence() -> None`
   - Yesterday's date (UTC)
   - `async with get_db_context() as db:` compute + publish
   - `record_poller_tick("daily_adherence")`

5. `async def _run_at_hour(hour, name, coro_factory)` — reuse pattern from `memory/lifecycle.py`

6. `start_adherence_task()` / `stop_adherence_task()` — lifecycle functions, check `analytics_adherence_enabled` + `background_queue_enabled`

**Key implementation notes:**
- Slack webhook: `httpx.AsyncClient.post(url, json=payload, timeout=10.0)` — no `verify=False`
- Email: run `smtplib.SMTP` in `asyncio.to_thread()` to avoid blocking
- Alert creation: `AlertInstanceCreate(title="Daily adherence below threshold", severity="high", alert_type="schedule_adherence", details={"overall_pct": report.overall_pct, "threshold": threshold, "report_date": str(report.report_date)})`
- All external calls wrapped in try/except with structured logging, never raise on publish failure
- Use `from __future__ import annotations` for forward refs

**Validation:** `uv run ruff format app/analytics/daily_adherence.py && uv run ruff check --fix app/analytics/daily_adherence.py && uv run pyright app/analytics/daily_adherence.py`

### Step 7: Route endpoint
**File:** `app/analytics/routes.py` (UPDATE)

Add import of `DailyAdherenceReportResponse` from schemas. Add endpoint:

```python
@router.get("/adherence/daily", response_model=list[DailyAdherenceReportResponse])
@limiter.limit("30/minute")
async def get_daily_adherence_reports(
    request: Request,
    date_from: str = Query(..., max_length=10, pattern=r"^\d{4}-\d{2}-\d{2}$"),  # noqa: B008
    date_to: str = Query(..., max_length=10, pattern=r"^\d{4}-\d{2}-\d{2}$"),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _current_user: User = Depends(get_current_user),  # noqa: B008
) -> list[DailyAdherenceReportResponse]:
```

- Parse dates with `datetime.date.fromisoformat()`, catch `ValueError` → 400
- Validate `date_from <= date_to`, cap range to 90 days
- Call `get_daily_reports(db, date_from_parsed, date_to_parsed)`
- Map model instances to response schemas (per_route_json → list[PerRouteAdherence], per_hour_json → list[PerHourAdherence])

**Validation:** `uv run ruff check app/analytics/routes.py && uv run pyright app/analytics/routes.py`

### Step 8: Lifespan registration
**File:** `app/main.py` (UPDATE)

Add imports:
```python
from app.analytics.daily_adherence import start_adherence_task, stop_adherence_task
```

In lifespan startup (after `start_memory_tasks()`):
```python
await start_adherence_task()
```

In shutdown coordinator registrations:
```python
coordinator.register(
    ShutdownTask(name="adherence_task", drain_timeout_s=3.0, drain=stop_adherence_task)
)
```

**Validation:** `uv run ruff check app/main.py && uv run pyright app/main.py`

### Step 9: Arq worker registration
**File:** `app/core/jobs/worker.py` (UPDATE)

Add `run_daily_adherence` function and cron job entry:
```python
async def run_daily_adherence(ctx: dict[str, Any]) -> str:
    _ = ctx
    from app.analytics.daily_adherence import _run_daily_adherence
    await _run_daily_adherence()
    return "daily_adherence_completed"
```

Add to `WorkerSettings.cron_jobs`:
```python
cron(run_daily_adherence, hour={settings.analytics_adherence_cron_hour}, minute={0}, second={0}, unique=True),
```

**Validation:** `uv run ruff check app/core/jobs/worker.py && uv run pyright app/core/jobs/worker.py`

### Step 9b: Jobs status route update
**File:** `app/core/jobs/routes.py` (UPDATE)

The job status endpoint hardcodes the job name loop at line 44:
```python
for job_name in ("run_compaction", "run_promotion"):
```

Update to include the new job:
```python
for job_name in ("run_compaction", "run_promotion", "run_daily_adherence"):
```

**Validation:** `uv run ruff check app/core/jobs/routes.py && uv run pyright app/core/jobs/routes.py`

### Step 10: Test conftest
**File:** `app/analytics/tests/conftest.py` (UPDATE)

```python
import datetime
from unittest.mock import MagicMock
from app.shared.models import utcnow

def make_daily_adherence_report(**overrides: object) -> MagicMock:
    """Factory for DailyAdherenceReport-like mock objects."""
    now = utcnow()
    defaults: dict[str, object] = {
        "id": 1,
        "report_date": datetime.date(2026, 4, 10),
        "overall_pct": 88.5,
        "total_trips": 200,
        "on_time_trips": 177,
        "late_trips": 15,
        "early_trips": 8,
        "per_route_json": [{"route_id": "1", "route_short_name": "1", "total_trips": 50, "on_time_trips": 44, "late_trips": 4, "early_trips": 2, "on_time_pct": 88.0, "avg_delay_seconds": 120.5}],
        "per_hour_json": [{"hour": 7, "total_trips": 30, "on_time_trips": 26, "on_time_pct": 86.7}],
        "anomaly_count": 3,
        "alert_triggered": False,
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock
```

**Validation:** `uv run ruff check app/analytics/tests/conftest.py && uv run pyright app/analytics/tests/conftest.py`

### Step 11: Unit tests
**File:** `app/analytics/tests/test_daily_adherence.py` (CREATE)

**Test cases (10+):**

1. `test_compute_daily_report_creates_row` — Mock static store + RT client, verify DB insert called, overall_pct computed correctly
2. `test_compute_daily_report_per_route_breakdown` — Verify per_route_json contains all routes with correct metrics
3. `test_compute_daily_report_per_hour_breakdown` — Verify per_hour_json groups trips by departure hour
4. `test_publish_report_slack_webhook` — Mock `httpx.AsyncClient.post`, verify called with correct URL and JSON payload
5. `test_publish_report_slack_fails_open` — Mock httpx to raise, verify no exception propagated, error logged
6. `test_publish_report_email_sent` — Mock SMTP, verify email send called
7. `test_publish_report_email_fails_open` — Mock SMTP to raise, verify no exception propagated
8. `test_threshold_below_triggers_alert` — Set overall_pct=75, verify `AlertService.create_alert()` called with severity="high"
9. `test_threshold_above_no_alert` — Set overall_pct=90, verify no alert created
10. `test_get_daily_reports_date_range` — Mock DB query, verify filter + ordering
11. `test_adherence_task_lifecycle` — Test `start_adherence_task()` creates task, `stop_adherence_task()` cancels
12. `test_adherence_endpoint_date_validation` — Test invalid date formats return 400

**Mocking patterns:**
- `@patch("app.analytics.daily_adherence.get_static_store")` — return mock static store
- `@patch("app.analytics.daily_adherence.GTFSRealtimeClient")` — return mock RT client
- `@patch("app.analytics.daily_adherence.AlertService")` — verify alert creation
- `AsyncMock` for DB session with `side_effect` for chained queries
- Follow `test_service.py` patterns for DB mocking

**Validation:** `uv run pytest app/analytics/tests/test_daily_adherence.py -v && uv run pyright app/analytics/tests/test_daily_adherence.py`

### Step 12: Route endpoint tests
Add adherence endpoint tests to existing `app/analytics/tests/test_routes.py` or create separate file. Test:
- 200 with valid date range
- 400 with invalid date format
- 400 with date_from > date_to
- 400 with range > 90 days
- Auth required (no token → 401/403)

**Validation:** `uv run pytest app/analytics/tests/ -v`

## Preflight Warnings

- `app/analytics/tests/test_routes.py` uses `app.dependency_overrides` fixture pattern — any new route test must follow same setup/teardown pattern to avoid test pollution (anti-pattern #56).
- `app/alerts/schemas.py:AlertRuleType` is a `Literal` type — adding a value updates the type everywhere it's referenced. Grep for `AlertRuleType` before modifying.
- `_compute_route_adherence()` is a module-private function in the agent tools package — importing it cross-feature is acceptable for read access (cross-feature read rule) but verify it remains stable.

## Security Checklist

For the new endpoint:
- [x] `get_current_user` dependency — authenticated access required
- [x] `@limiter.limit("30/minute")` rate limiting
- [x] Input validation: `date_from`/`date_to` via `Query(..., max_length=10, pattern=...)`
- [x] Error responses use `HTTPException` (no internal type leakage)
- [x] No ILIKE queries (date comparison only)

For Slack webhook:
- [x] URL from env var config, never hardcoded
- [x] `httpx.AsyncClient` with default SSL verification (no `verify=False`)
- [x] Timeout on HTTP call (10s)

For email:
- [x] SMTP config from env vars
- [x] Fail-open: publish errors logged, never raised to caller

## Verification

- [ ] `make lint` passes (ruff format + check)
- [ ] `make types` passes (mypy + pyright)
- [ ] `uv run pytest app/analytics/tests/ -v` — all tests pass
- [ ] `uv run pytest app/core/jobs/tests/ -v` — job queue tests still pass
- [ ] `uv run pytest app/alerts/tests/ -v` — alert tests still pass with new type
- [ ] `make security-audit-quick` passes
- [ ] Pyright errors ≤ 0 (baseline: 0 errors)
- [ ] New endpoint has auth + rate limiting
- [ ] Security convention tests pass: `uv run pytest app/tests/test_security.py -v`
