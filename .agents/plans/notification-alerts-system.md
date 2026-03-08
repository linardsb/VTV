# Plan: Notification/Alerts System

## Feature Metadata
**Feature Type**: New Capability
**Estimated Complexity**: High
**Primary Systems Affected**: New `app/alerts/` vertical slice, `app/core/config.py`, `app/main.py`, `alembic/versions/`

## Feature Description

The VTV platform's PRD references an alerts indicator in the dashboard layout ("Status: 42 active · 3 delayed · 1 alert") but no backend alerting system exists. This feature creates a complete `app/alerts/` vertical slice that provides:

1. **Alert Rules** — Configurable threshold definitions (delay thresholds, maintenance due windows, registration expiry windows, geofence radius violations) stored in the database with per-rule enable/disable.
2. **Alert Instances** — System-generated or manually-created alert records linked to source entities (vehicles, routes, drivers) with severity levels and lifecycle management (active → acknowledged → resolved).
3. **REST API** — CRUD for alert rules (admin-only), list/filter/acknowledge/resolve for alert instances (admin + dispatcher), summary endpoint for dashboard badge counts.
4. **Background Evaluator** — A periodic task that evaluates active rules against current system state (vehicle maintenance dates, registration expiry, transit delays from Redis) and creates alert instances when thresholds are breached, with deduplication to avoid duplicate alerts for the same condition.

This feature does NOT include WebSocket push delivery (that can be layered on top in a future iteration using the existing `ws_manager` pattern from transit). The REST polling approach is sufficient for the dashboard and keeps the initial implementation focused.

## User Story

As a **dispatcher or administrator**
I want to **see active alerts for delay thresholds, upcoming maintenance, and expiring registrations on my dashboard**
So that **I can proactively respond to operational issues before they impact service quality**

## Security Contexts

**Active contexts** (detected from feature scope):
- **CTX-RBAC**: Feature adds 7+ new REST endpoints with role-based access control. Alert rules management is admin-only; alert viewing/acknowledging is admin+dispatcher; alert summary is available to all authenticated users.
- **CTX-INPUT**: Feature accepts search queries, filter parameters (severity, status, alert_type, entity references), and threshold values in alert rule definitions. All query params need `max_length` constraints and proper validation.

**Not applicable:**
- CTX-AUTH: No changes to auth flow, tokens, or sessions
- CTX-FILE: No file uploads
- CTX-AGENT: No agent tool integration in this phase
- CTX-INFRA: No Docker/nginx/CORS changes

## Solution Approach

We build a new `app/alerts/` vertical slice following the established events module pattern (closest analog — both are CRUD-heavy operational data features). The alerts system has two main dimensions:

**Alert Rules** are configuration records defining what to watch for. Each rule has a `rule_type` (Literal), a `threshold` (JSONB for type-specific config), `severity`, and an `enabled` flag. Rules are managed by admins only.

**Alert Instances** are the concrete occurrences — "Vehicle RS-1047 maintenance overdue by 3 days" — created either by the background evaluator or manually by dispatchers. Each instance tracks its lifecycle: `active` → `acknowledged` → `resolved`, with timestamps for each transition and an optional `acknowledged_by` user reference.

**Background Evaluator:** A lightweight async task (similar to transit poller pattern) that runs on a configurable interval (default 60s). It loads active rules, evaluates each against current system state, and creates alert instances with deduplication (same `rule_id` + `source_entity_type` + `source_entity_id` combination won't create a duplicate if an active/acknowledged alert already exists). The evaluator runs inside the app lifespan, not as a separate process.

**Approach Decision:**
We chose database-stored rules + periodic evaluation because:
- Rules are user-configurable without code changes or restarts
- Deduplication is straightforward with DB unique constraints
- Follows existing poller pattern (background asyncio task in lifespan)
- No additional infrastructure required (no message queue, no separate worker)

**Alternatives Considered:**
- **Event-driven alerts (Redis Pub/Sub triggers)**: Rejected because it would require hooking into every data mutation point. The periodic evaluator is simpler and catches all state changes regardless of source.
- **External alerting service (e.g., Alertmanager)**: Rejected because VTV targets self-contained deployment with minimal infrastructure. Adding a separate alerting service contradicts the "minimal tech stack" principle.
- **Cron job / Celery worker**: Rejected because VTV doesn't use Celery. The in-process asyncio task pattern (like transit poller) is already proven in this codebase.

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, logging patterns, type checking requirements
- `app/core/config.py` (lines 30-210) — Settings class pattern, feature flags, threshold config
- `app/core/database.py` — `Base`, `get_db()`, `get_db_context()`, `AsyncSessionLocal`
- `app/core/exceptions.py` — `AppError`, `NotFoundError`, `DomainValidationError` hierarchy
- `app/core/logging.py` — `get_logger()` function
- `app/core/redis.py` — `get_redis()` for reading transit delay data from Redis
- `app/core/rate_limit.py` — `limiter` instance for route decorators
- `app/shared/models.py` (lines 1-42) — `TimestampMixin`, `utcnow()`
- `app/shared/schemas.py` (lines 1-89) — `PaginationParams`, `PaginatedResponse[T]`
- `app/shared/utils.py` — `escape_like()` for ILIKE queries

### Similar Features (Examples to Follow)
- `app/events/schemas.py` (lines 1-93) — Literal types for enums, `model_validator(mode="before")` for empty PATCH rejection, `ConfigDict(from_attributes=True)`
- `app/events/models.py` (lines 1-42) — Model with `Base + TimestampMixin`, JSONB column, ForeignKey with `ondelete`, indexed columns
- `app/events/repository.py` (lines 1-80) — Class-based repository with async CRUD, count, filtered list with offset/limit
- `app/events/service.py` (lines 1-111) — Service with injected `AsyncSession`, repository delegation, structured logging
- `app/events/routes.py` (lines 1-126) — Router with `require_role()`, `limiter.limit()`, `PaginatedResponse`, service dependency
- `app/events/exceptions.py` (lines 1-17) — Feature exception hierarchy
- `app/events/tests/conftest.py` (lines 1-75) — `make_*()` factory, `sample_*` fixtures, `mock_db`
- `app/transit/poller.py` (lines 51-130) — Background task pattern with `asyncio.create_task()`, leader lock, graceful shutdown

### Files to Modify
- `app/main.py` (line 166) — Register `alerts_router` after analytics_router
- `app/core/config.py` (line 187) — Add alerts feature flag and evaluator interval settings

## Implementation Plan

### Phase 1: Foundation
Define schemas, models, exceptions, and configuration. This establishes the data layer before any business logic.

### Phase 2: Core Implementation
Build the repository, service, and routes following the events module pattern. This gives us the full CRUD API.

### Phase 3: Background Evaluator
Implement the periodic evaluation task that checks rules against system state and creates alert instances automatically.

### Phase 4: Integration & Validation
Register the router, add configuration, write comprehensive tests, and validate the complete feature.

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.

### Task 1: Create Alert Schemas
**File:** `app/alerts/schemas.py` (create new)
**Action:** CREATE

Create Pydantic schemas for the alerts feature:

1. Define Literal type aliases:
   - `AlertSeverityType = Literal["critical", "high", "medium", "low", "info"]`
   - `AlertStatusType = Literal["active", "acknowledged", "resolved"]`
   - `AlertRuleType = Literal["delay_threshold", "maintenance_due", "registration_expiry", "manual"]`
   - `SourceEntityType = Literal["vehicle", "route", "driver"]`

2. Define `AlertRuleBase(BaseModel)`:
   - `name: str` — `Field(..., min_length=1, max_length=200)` — human-readable rule name
   - `description: str | None` — `Field(None, max_length=1000)`
   - `rule_type: AlertRuleType` — what kind of check this rule performs
   - `severity: AlertSeverityType` — default severity for alerts generated by this rule
   - `threshold_config: dict[str, int | float | str | bool]` — type-specific thresholds (e.g., `{"delay_seconds": 600}` for delay, `{"days_before": 7}` for maintenance)
   - `enabled: bool` — `Field(default=True)` — whether evaluator checks this rule

3. Define `AlertRuleCreate(AlertRuleBase)` — no additional fields

4. Define `AlertRuleUpdate(BaseModel)` — all fields optional:
   - Same fields as `AlertRuleBase` but all `| None`
   - Add `@model_validator(mode="before")` with `@classmethod` to reject empty body (pattern from `app/events/schemas.py` lines 75-82)

5. Define `AlertRuleResponse(AlertRuleBase)`:
   - `id: int`, `created_at: datetime.datetime`, `updated_at: datetime.datetime`
   - `model_config = ConfigDict(from_attributes=True)`

6. Define `AlertInstanceBase(BaseModel)`:
   - `title: str` — `Field(..., min_length=1, max_length=300)` — human-readable description
   - `severity: AlertSeverityType`
   - `alert_type: AlertRuleType` — copied from the rule that generated it
   - `source_entity_type: SourceEntityType | None` — `Field(None)` — what entity triggered this
   - `source_entity_id: str | None` — `Field(None, max_length=100)` — ID of the source entity (string to handle fleet_number, route_id, driver_id)
   - `details: dict[str, int | float | str | bool | None] | None` — `Field(None)` — JSONB for type-specific context

7. Define `AlertInstanceCreate(AlertInstanceBase)`:
   - `rule_id: int | None` — `Field(None)` — NULL for manually created alerts

8. Define `AlertInstanceResponse(AlertInstanceBase)`:
   - `id: int`, `status: AlertStatusType`, `rule_id: int | None`
   - `created_at: datetime.datetime`, `updated_at: datetime.datetime`
   - `acknowledged_at: datetime.datetime | None`, `acknowledged_by_id: int | None`
   - `resolved_at: datetime.datetime | None`
   - `model_config = ConfigDict(from_attributes=True)`

9. Define `AlertAcknowledge(BaseModel)`:
   - `note: str | None` — `Field(None, max_length=1000)` — optional note when acknowledging

10. Define `AlertSummaryResponse(BaseModel)`:
    - `total_active: int`, `critical: int`, `high: int`, `medium: int`, `low: int`, `info: int`

Add the file-level pyright directive: `# pyright: reportUnknownVariableType=false`
Add module docstring: `"""Pydantic schemas for the notification/alerts feature."""`

Import: `import datetime` (not `from datetime import datetime`), `from typing import Literal`, `from pydantic import BaseModel, ConfigDict, Field, model_validator`, `from typing import Any` (for model_validator return)

**Per-task validation:**
- `uv run ruff format app/alerts/schemas.py`
- `uv run ruff check --fix app/alerts/schemas.py`
- `uv run mypy app/alerts/schemas.py`
- `uv run pyright app/alerts/schemas.py`

---

### Task 2: Create Alert Models
**File:** `app/alerts/models.py` (create new)
**Action:** CREATE

Create SQLAlchemy models for alert rules and alert instances:

1. Define `AlertRule(Base, TimestampMixin)`:
   - `__tablename__ = "alert_rules"`
   - `id: Mapped[int]` — `mapped_column(primary_key=True, index=True)`
   - `name: Mapped[str]` — `mapped_column(String(200), nullable=False)`
   - `description: Mapped[str | None]` — `mapped_column(Text, nullable=True)`
   - `rule_type: Mapped[str]` — `mapped_column(String(30), nullable=False)` — with CheckConstraint
   - `severity: Mapped[str]` — `mapped_column(String(20), nullable=False, default="medium")`
   - `threshold_config: Mapped[dict[str, Any]]` — `mapped_column(JSONB, nullable=False, default=dict)`
   - `enabled: Mapped[bool]` — `mapped_column(default=True, nullable=False)`
   - Add `__table_args__` with `CheckConstraint("rule_type IN ('delay_threshold', 'maintenance_due', 'registration_expiry', 'manual')", name="ck_alert_rules_rule_type")` and `CheckConstraint("severity IN ('critical', 'high', 'medium', 'low', 'info')", name="ck_alert_rules_severity")`

2. Define `AlertInstance(Base, TimestampMixin)`:
   - `__tablename__ = "alert_instances"`
   - `id: Mapped[int]` — `mapped_column(primary_key=True, index=True)`
   - `title: Mapped[str]` — `mapped_column(String(300), nullable=False)`
   - `severity: Mapped[str]` — `mapped_column(String(20), nullable=False, default="medium")`
   - `status: Mapped[str]` — `mapped_column(String(20), nullable=False, default="active", index=True)`
   - `alert_type: Mapped[str]` — `mapped_column(String(30), nullable=False)`
   - `rule_id: Mapped[int | None]` — `mapped_column(Integer, ForeignKey("alert_rules.id", ondelete="SET NULL"), nullable=True, index=True)`
   - `source_entity_type: Mapped[str | None]` — `mapped_column(String(20), nullable=True)`
   - `source_entity_id: Mapped[str | None]` — `mapped_column(String(100), nullable=True, index=True)`
   - `details: Mapped[dict[str, Any] | None]` — `mapped_column(JSONB, nullable=True, default=None)`
   - `acknowledged_at: Mapped[datetime.datetime | None]` — `mapped_column(DateTime(timezone=True), nullable=True)`
   - `acknowledged_by_id: Mapped[int | None]` — `mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)`
   - `resolved_at: Mapped[datetime.datetime | None]` — `mapped_column(DateTime(timezone=True), nullable=True)`
   - Add `__table_args__` with `CheckConstraint("status IN ('active', 'acknowledged', 'resolved')", name="ck_alert_instances_status")` and a `UniqueConstraint("rule_id", "source_entity_type", "source_entity_id", "status", name="uq_alert_dedup")` — but use a partial unique index approach instead (see note below)
   - For deduplication: add `Index("ix_alert_dedup", "rule_id", "source_entity_type", "source_entity_id", unique=True, postgresql_where=text("status = 'active'"))` — this only enforces uniqueness for active alerts, allowing resolved alerts to exist alongside new ones

Imports: `import datetime`, `from typing import Any`, `from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, text`, `from sqlalchemy.dialects.postgresql import JSONB`, `from sqlalchemy.orm import Mapped, mapped_column`, `from app.core.database import Base`, `from app.shared.models import TimestampMixin`

Add module docstring: `"""SQLAlchemy models for the notification/alerts feature."""`

**Per-task validation:**
- `uv run ruff format app/alerts/models.py`
- `uv run ruff check --fix app/alerts/models.py`
- `uv run mypy app/alerts/models.py`
- `uv run pyright app/alerts/models.py`

---

### Task 3: Create Alert Exceptions
**File:** `app/alerts/exceptions.py` (create new)
**Action:** CREATE

Follow the pattern from `app/events/exceptions.py`:

```python
"""Feature-specific exceptions for the notification/alerts feature.

Inherits from core exceptions for automatic HTTP status code mapping:
- AlertNotFoundError -> 404
- AlertRuleNotFoundError -> 404
- AlertError -> 500
"""

from app.core.exceptions import AppError, NotFoundError


class AlertError(AppError):
    """Base exception for alert-related errors."""


class AlertNotFoundError(NotFoundError):
    """Raised when an alert instance is not found by ID."""


class AlertRuleNotFoundError(NotFoundError):
    """Raised when an alert rule is not found by ID."""
```

**Per-task validation:**
- `uv run ruff format app/alerts/exceptions.py`
- `uv run ruff check --fix app/alerts/exceptions.py`
- `uv run mypy app/alerts/exceptions.py`

---

### Task 4: Create Alert Repository
**File:** `app/alerts/repository.py` (create new)
**Action:** CREATE

Create class-based repository following `app/events/repository.py` pattern:

1. Define `AlertRuleRepository(db: AsyncSession)`:
   - `async def get(self, rule_id: int) -> AlertRule | None` — single rule by ID
   - `async def list(self, *, offset: int = 0, limit: int = 100, enabled_only: bool = False) -> list[AlertRule]` — with optional `enabled_only` filter
   - `async def count(self, *, enabled_only: bool = False) -> int`
   - `async def create(self, data: AlertRuleCreate) -> AlertRule`
   - `async def update(self, rule: AlertRule, data: AlertRuleUpdate) -> AlertRule`
   - `async def delete(self, rule: AlertRule) -> None`
   - `async def get_enabled_rules(self) -> list[AlertRule]` — shorthand for `list(enabled_only=True, limit=1000)`

2. Define `AlertInstanceRepository(db: AsyncSession)`:
   - `async def get(self, alert_id: int) -> AlertInstance | None`
   - `async def list(self, *, offset: int = 0, limit: int = 100, status: str | None = None, severity: str | None = None, alert_type: str | None = None, source_entity_type: str | None = None, source_entity_id: str | None = None) -> list[AlertInstance]` — filtered list with ordering by severity (critical first) then `created_at` desc
   - `async def count(self, *, status: str | None = None, severity: str | None = None, alert_type: str | None = None, source_entity_type: str | None = None, source_entity_id: str | None = None) -> int`
   - `async def create(self, data: AlertInstanceCreate) -> AlertInstance` — build `AlertInstance` from schema data, setting `status="active"`
   - `async def acknowledge(self, alert: AlertInstance, user_id: int) -> AlertInstance` — set `status="acknowledged"`, `acknowledged_at=utcnow()`, `acknowledged_by_id=user_id`
   - `async def resolve(self, alert: AlertInstance) -> AlertInstance` — set `status="resolved"`, `resolved_at=utcnow()`
   - `async def find_active_duplicate(self, rule_id: int, source_entity_type: str, source_entity_id: str) -> AlertInstance | None` — check for existing active alert with same rule+entity combo (deduplication query)
   - `async def get_summary(self) -> dict[str, int]` — count active alerts grouped by severity, return `{"total_active": N, "critical": N, "high": N, ...}`

For severity ordering in list query, use: `.order_by(case((AlertInstance.severity == "critical", 1), (AlertInstance.severity == "high", 2), (AlertInstance.severity == "medium", 3), (AlertInstance.severity == "low", 4), (AlertInstance.severity == "info", 5), else_=6), AlertInstance.created_at.desc())`

Import `case` from `sqlalchemy` for the ordering expression.

Imports: `from __future__ import annotations`, `from sqlalchemy import case, func, select`, `from sqlalchemy.ext.asyncio import AsyncSession`, models, schemas, `from app.shared.models import utcnow`

**Per-task validation:**
- `uv run ruff format app/alerts/repository.py`
- `uv run ruff check --fix app/alerts/repository.py`
- `uv run mypy app/alerts/repository.py`

---

### Task 5: Create Alert Service
**File:** `app/alerts/service.py` (create new)
**Action:** CREATE

Create `AlertService` following `app/events/service.py` pattern:

1. `__init__(self, db: AsyncSession)` — create `AlertRuleRepository` and `AlertInstanceRepository`

2. **Rule CRUD methods:**
   - `async def get_rule(self, rule_id: int) -> AlertRuleResponse` — with logging, raise `AlertRuleNotFoundError`
   - `async def list_rules(self, pagination: PaginationParams, *, enabled_only: bool = False) -> PaginatedResponse[AlertRuleResponse]`
   - `async def create_rule(self, data: AlertRuleCreate) -> AlertRuleResponse`
   - `async def update_rule(self, rule_id: int, data: AlertRuleUpdate) -> AlertRuleResponse`
   - `async def delete_rule(self, rule_id: int) -> None`

3. **Instance methods:**
   - `async def get_alert(self, alert_id: int) -> AlertInstanceResponse` — with logging, raise `AlertNotFoundError`
   - `async def list_alerts(self, pagination: PaginationParams, *, status: str | None = None, severity: str | None = None, alert_type: str | None = None, source_entity_type: str | None = None, source_entity_id: str | None = None) -> PaginatedResponse[AlertInstanceResponse]`
   - `async def create_alert(self, data: AlertInstanceCreate) -> AlertInstanceResponse` — for manual alert creation
   - `async def acknowledge_alert(self, alert_id: int, user_id: int) -> AlertInstanceResponse` — transition to acknowledged
   - `async def resolve_alert(self, alert_id: int) -> AlertInstanceResponse` — transition to resolved
   - `async def get_summary(self) -> AlertSummaryResponse` — dashboard badge counts

4. **Logging pattern** (follow events module):
   - `logger.info("alerts.rule.create_started", name=data.name)`
   - `logger.info("alerts.rule.create_completed", rule_id=rule.id)`
   - `logger.warning("alerts.instance.fetch_failed", alert_id=alert_id, reason="not_found")`
   - `logger.info("alerts.instance.acknowledge_completed", alert_id=alert_id, user_id=user_id)`

Imports: `from __future__ import annotations`, `from sqlalchemy.ext.asyncio import AsyncSession`, `from app.core.logging import get_logger`, exceptions, repository, schemas, `from app.shared.schemas import PaginatedResponse, PaginationParams`

**Per-task validation:**
- `uv run ruff format app/alerts/service.py`
- `uv run ruff check --fix app/alerts/service.py`
- `uv run mypy app/alerts/service.py`

---

### Task 6: Create Alert Routes
**File:** `app/alerts/routes.py` (create new)
**Action:** CREATE

Create FastAPI router following `app/events/routes.py` pattern:

```python
router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])
```

Add pyright directive at top: `# pyright: reportUnknownMemberType=false, reportUntypedFunctionDecorator=false`

1. **Service dependency:**
   ```python
   def get_service(db: AsyncSession = Depends(get_db)) -> AlertService:  # noqa: B008
       return AlertService(db)
   ```

2. **Alert Rule endpoints (admin-only):**
   - `GET /rules` — `list_rules` — `require_role("admin")`, `limiter.limit("30/minute")`, `PaginationParams`, optional `enabled_only: bool = Query(False)`
   - `GET /rules/{rule_id}` — `get_rule` — `require_role("admin")`, `limiter.limit("30/minute")`
   - `POST /rules` — `create_rule` — `require_role("admin")`, `limiter.limit("10/minute")`, `status.HTTP_201_CREATED`
   - `PATCH /rules/{rule_id}` — `update_rule` — `require_role("admin")`, `limiter.limit("10/minute")`
   - `DELETE /rules/{rule_id}` — `delete_rule` — `require_role("admin")`, `limiter.limit("10/minute")`, `status.HTTP_204_NO_CONTENT`

3. **Alert Instance endpoints:**
   - `GET /` — `list_alerts` — `require_role("admin", "dispatcher")`, `limiter.limit("30/minute")`, filter params: `status`, `severity`, `alert_type`, `source_entity_type`, `source_entity_id` (all `Query(None)` with `max_length` where string)
   - `GET /summary` — `get_summary` — `require_role("admin", "dispatcher", "editor", "viewer")`, `limiter.limit("60/minute")` — lightweight for dashboard polling
   - `GET /{alert_id}` — `get_alert` — `require_role("admin", "dispatcher")`, `limiter.limit("30/minute")`
   - `POST /` — `create_alert` — `require_role("admin", "dispatcher")`, `limiter.limit("10/minute")`, `status.HTTP_201_CREATED` — manual alert creation
   - `POST /{alert_id}/acknowledge` — `acknowledge_alert` — `require_role("admin", "dispatcher")`, `limiter.limit("10/minute")` — pass `current_user.id` to service
   - `POST /{alert_id}/resolve` — `resolve_alert` — `require_role("admin", "dispatcher")`, `limiter.limit("10/minute")`

IMPORTANT: Every endpoint MUST have `require_role()` dependency — `TestAllEndpointsRequireAuth` in `app/tests/test_security.py` will fail CI otherwise.

Each endpoint must accept `request: Request` as first param (for rate limiter) and include `_ = request` to satisfy ARG001.

String `Query()` params must have `max_length` constraints (CTX-INPUT):
- `status: str | None = Query(None, max_length=20)`
- `severity: str | None = Query(None, max_length=20)`
- `alert_type: str | None = Query(None, max_length=30)`
- `source_entity_type: str | None = Query(None, max_length=20)`
- `source_entity_id: str | None = Query(None, max_length=100)`

Imports: `from fastapi import APIRouter, Depends, Query, status`, `from fastapi.requests import Request`, `from sqlalchemy.ext.asyncio import AsyncSession`, `from app.auth.dependencies import require_role`, `from app.auth.models import User`, `from app.core.database import get_db`, `from app.core.rate_limit import limiter`, schemas, service, `from app.shared.schemas import PaginatedResponse, PaginationParams`

**Per-task validation:**
- `uv run ruff format app/alerts/routes.py`
- `uv run ruff check --fix app/alerts/routes.py`
- `uv run mypy app/alerts/routes.py`

---

### Task 7: Create Background Alert Evaluator
**File:** `app/alerts/evaluator.py` (create new)
**Action:** CREATE

Create the background task that periodically evaluates alert rules:

1. Define module-level state:
   ```python
   _evaluator_task: asyncio.Task[None] | None = None
   logger = get_logger(__name__)
   ```

2. Define `async def evaluate_rules_once(settings: Settings) -> int`:
   - Get DB session via `get_db_context()` (standalone context, not request-scoped)
   - Load all enabled rules via `AlertRuleRepository.get_enabled_rules()`
   - For each rule, call the appropriate evaluator based on `rule.rule_type`:
     - `"maintenance_due"` → `_evaluate_maintenance_due(rule, db)`
     - `"registration_expiry"` → `_evaluate_registration_expiry(rule, db)`
     - `"delay_threshold"` → `_evaluate_delay_threshold(rule, settings)`
     - `"manual"` → skip (manual rules are never auto-evaluated)
   - Return total count of new alerts created
   - Wrap entire function in `try/except Exception` with `logger.error("alerts.evaluator.cycle_failed", ...)` — evaluator must never crash

3. Define `async def _evaluate_maintenance_due(rule: AlertRule, db: AsyncSession) -> int`:
   - Query `Vehicle` model where `next_maintenance_date IS NOT NULL` and `next_maintenance_date <= today + threshold_days`
   - `threshold_days` from `rule.threshold_config.get("days_before", 7)`
   - For each matching vehicle, check deduplication via `AlertInstanceRepository.find_active_duplicate(rule.id, "vehicle", vehicle.fleet_number)`
   - If no duplicate, create `AlertInstance` with `title=f"Maintenance due for vehicle {vehicle.fleet_number}"`, `severity=rule.severity`, `source_entity_type="vehicle"`, `source_entity_id=vehicle.fleet_number`
   - Return count of new alerts

4. Define `async def _evaluate_registration_expiry(rule: AlertRule, db: AsyncSession) -> int`:
   - Similar to maintenance_due but checks `registration_expiry` field
   - `threshold_days` from `rule.threshold_config.get("days_before", 30)`

5. Define `async def _evaluate_delay_threshold(rule: AlertRule, settings: Settings) -> int`:
   - Get Redis client via `get_redis()`
   - Read vehicle positions from Redis keys (pattern: `vehicle:{feed_id}:*`)
   - Parse JSON, check `delay` field against `rule.threshold_config.get("delay_seconds", 600)`
   - For vehicles exceeding threshold, create alerts with dedup check
   - Use `get_db_context()` for the DB session needed for dedup + insert
   - Handle Redis unavailability gracefully: `except Exception` with logging, return 0

6. Define `async def _evaluator_loop(settings: Settings, interval: int) -> None`:
   - `while True` loop with `await asyncio.sleep(interval)` at the start
   - Call `evaluate_rules_once(settings)`
   - Log: `logger.info("alerts.evaluator.cycle_completed", new_alerts=count, interval=interval)`
   - Catch `asyncio.CancelledError` separately (re-raise), catch `Exception` (log and continue)

7. Define `async def start_evaluator(settings: Settings) -> None`:
   - Check `settings.alerts_enabled` (added in Task 9)
   - Create background task: `_evaluator_task = asyncio.create_task(_evaluator_loop(settings, settings.alerts_check_interval_seconds))`
   - Log: `logger.info("alerts.evaluator.lifecycle_started", interval=settings.alerts_check_interval_seconds)`

8. Define `async def stop_evaluator() -> None`:
   - Cancel `_evaluator_task` if not None
   - `await` the task with `try/except (asyncio.CancelledError, Exception)` — both handled
   - Log: `logger.info("alerts.evaluator.lifecycle_stopped")`

Imports: `import asyncio`, `import datetime`, `from contextlib import asynccontextmanager` (not needed if using get_db_context), `from sqlalchemy import select`, `from sqlalchemy.ext.asyncio import AsyncSession`, `from app.alerts.models import AlertInstance, AlertRule`, `from app.alerts.repository import AlertInstanceRepository, AlertRuleRepository`, `from app.alerts.schemas import AlertInstanceCreate`, `from app.core.config import Settings`, `from app.core.database import get_db_context`, `from app.core.logging import get_logger`, `from app.core.redis import get_redis`, `from app.vehicles.models import Vehicle`

**Per-task validation:**
- `uv run ruff format app/alerts/evaluator.py`
- `uv run ruff check --fix app/alerts/evaluator.py`
- `uv run mypy app/alerts/evaluator.py`

---

### Task 8: Create `__init__.py`
**File:** `app/alerts/__init__.py` (create new)
**Action:** CREATE

Create empty `__init__.py` with module docstring:
```python
"""Notification/Alerts feature — configurable alert rules with background evaluation."""
```

Also create `app/alerts/tests/__init__.py`:
```python
"""Tests for the notification/alerts feature."""
```

**Per-task validation:**
- `uv run ruff format app/alerts/__init__.py app/alerts/tests/__init__.py`
- `uv run ruff check --fix app/alerts/__init__.py app/alerts/tests/__init__.py`

---

### Task 9: Add Configuration Settings
**File:** `app/core/config.py` (modify existing)
**Action:** UPDATE

Add these settings to the `Settings` class, after the `netex_participant_ref` field (around line 187):

```python
    # Alerts system
    alerts_enabled: bool = True
    alerts_check_interval_seconds: int = 60
```

These control the background evaluator. The evaluator is disabled by default in test environments (tests set `alerts_enabled=False`).

**Per-task validation:**
- `uv run ruff format app/core/config.py`
- `uv run ruff check --fix app/core/config.py`
- `uv run mypy app/core/config.py`

---

### Task 10: Register Router and Evaluator in Main App
**File:** `app/main.py` (modify existing)
**Action:** UPDATE

1. Add import at top (with other router imports, around line 24):
   ```python
   from app.alerts.evaluator import start_evaluator, stop_evaluator
   from app.alerts.routes import router as alerts_router
   ```

2. In the `lifespan` function, after the WebSocket subscriber start block (after line 109), add:
   ```python
       # Start alert evaluator background task
       await start_evaluator(settings)
       logger.info("alerts.evaluator.lifecycle_started")
   ```

3. In the shutdown section (before `await close_transit_service()` on line 119), add:
   ```python
       await stop_evaluator()
       logger.info("alerts.evaluator.lifecycle_stopped")
   ```

4. After the last `include_router` line (after analytics_router on line 166), add:
   ```python
   app.include_router(alerts_router)
   ```

**Per-task validation:**
- `uv run ruff format app/main.py`
- `uv run ruff check --fix app/main.py`
- `uv run mypy app/main.py`

---

### Task 11: Create Test Fixtures
**File:** `app/alerts/tests/conftest.py` (create new)
**Action:** CREATE

Follow `app/events/tests/conftest.py` pattern:

1. Define `make_alert_rule(**overrides: object) -> AlertRule` factory:
   - Defaults: `id=1, name="High Delay Alert", rule_type="delay_threshold", severity="high", threshold_config={"delay_seconds": 600}, enabled=True, created_at=utcnow(), updated_at=utcnow()`

2. Define `make_alert_instance(**overrides: object) -> AlertInstance` factory:
   - Defaults: `id=1, title="Vehicle RS-1047 delayed 12 min", severity="high", status="active", alert_type="delay_threshold", rule_id=1, source_entity_type="vehicle", source_entity_id="RS-1047", details={"delay_seconds": 720}, acknowledged_at=None, acknowledged_by_id=None, resolved_at=None, created_at=utcnow(), updated_at=utcnow()`

3. Fixtures: `sample_rule`, `sample_rules` (3 rules of different types), `sample_alert`, `sample_alerts` (3 alerts of different severities/statuses), `mock_db`

**Per-task validation:**
- `uv run ruff format app/alerts/tests/conftest.py`
- `uv run ruff check --fix app/alerts/tests/conftest.py`

---

### Task 12: Create Service Tests
**File:** `app/alerts/tests/test_service.py` (create new)
**Action:** CREATE

Test the `AlertService` class with mocked repositories:

1. **Rule CRUD tests:**
   - `test_get_rule_success` — mock repository.get returns rule, verify response
   - `test_get_rule_not_found` — mock repository.get returns None, assert `AlertRuleNotFoundError`
   - `test_list_rules` — mock repository.list + count, verify pagination
   - `test_create_rule` — mock repository.create, verify response
   - `test_update_rule_success` — mock get + update
   - `test_update_rule_not_found` — mock get returns None
   - `test_delete_rule_success` — mock get + delete
   - `test_delete_rule_not_found` — mock get returns None

2. **Instance tests:**
   - `test_get_alert_success` — mock get, verify response
   - `test_get_alert_not_found` — assert `AlertNotFoundError`
   - `test_list_alerts_with_filters` — mock list + count with filter params
   - `test_create_alert_manual` — mock create, verify response
   - `test_acknowledge_alert_success` — mock get + acknowledge, verify status change
   - `test_acknowledge_alert_not_found` — assert `AlertNotFoundError`
   - `test_resolve_alert_success` — mock get + resolve
   - `test_get_summary` — mock `get_summary`, verify response mapping

Service setup pattern (from events tests):
```python
from unittest.mock import AsyncMock
from app.alerts.service import AlertService

def make_service() -> AlertService:
    mock_db = AsyncMock()
    svc = AlertService(mock_db)
    svc.rule_repository = AsyncMock()
    svc.instance_repository = AsyncMock()
    return svc
```

**Per-task validation:**
- `uv run ruff format app/alerts/tests/test_service.py`
- `uv run ruff check --fix app/alerts/tests/test_service.py`
- `uv run pytest app/alerts/tests/test_service.py -v`

---

### Task 13: Create Route Tests
**File:** `app/alerts/tests/test_routes.py` (create new)
**Action:** CREATE

Test the REST endpoints using `TestClient` with mocked service:

1. **RBAC tests (CTX-RBAC):**
   - `test_list_alerts_requires_auth` — no token → 401/403
   - `test_list_rules_requires_admin` — dispatcher token → 403
   - `test_summary_allows_all_roles` — viewer token → 200
   - `test_create_alert_requires_dispatcher` — viewer → 403, dispatcher → 201
   - `test_acknowledge_requires_dispatcher` — viewer → 403

2. **Happy path tests:**
   - `test_list_alerts_success` — verify pagination response
   - `test_get_alert_success` — verify single alert
   - `test_create_alert_success` — verify 201 + response body
   - `test_acknowledge_alert_success` — verify status transition
   - `test_resolve_alert_success`
   - `test_get_summary_success` — verify summary counts
   - `test_list_rules_success` — admin can list rules
   - `test_create_rule_success` — admin can create rule
   - `test_update_rule_success`
   - `test_delete_rule_success` — verify 204

3. **Input validation tests (CTX-INPUT):**
   - `test_list_alerts_invalid_status` — invalid filter value
   - `test_create_rule_empty_name` — empty name → 422

Use `app.dependency_overrides` pattern. CRITICAL: save, clear, yield, then restore overrides (anti-pattern #56).

**Per-task validation:**
- `uv run ruff format app/alerts/tests/test_routes.py`
- `uv run ruff check --fix app/alerts/tests/test_routes.py`
- `uv run pytest app/alerts/tests/test_routes.py -v`

---

### Task 14: Create Evaluator Tests
**File:** `app/alerts/tests/test_evaluator.py` (create new)
**Action:** CREATE

Test the background evaluator logic:

1. `test_evaluate_maintenance_due_creates_alert` — mock Vehicle query returning vehicle with overdue maintenance, verify alert created
2. `test_evaluate_maintenance_due_dedup` — mock existing active alert, verify no duplicate created
3. `test_evaluate_registration_expiry` — mock vehicle with expiring registration
4. `test_evaluate_delay_threshold` — mock Redis with delayed vehicle data, verify alert created
5. `test_evaluate_delay_threshold_redis_unavailable` — mock Redis raising error, verify graceful handling (returns 0, no crash)
6. `test_evaluator_loop_handles_exceptions` — verify loop continues after evaluation error
7. `test_start_stop_evaluator` — verify task creation and cancellation

Mock `get_db_context` and `get_redis` at the module level (`app.alerts.evaluator.get_db_context`).

**Per-task validation:**
- `uv run ruff format app/alerts/tests/test_evaluator.py`
- `uv run ruff check --fix app/alerts/tests/test_evaluator.py`
- `uv run pytest app/alerts/tests/test_evaluator.py -v`

---

## Migration

**If database is running:**
```bash
uv run alembic revision --autogenerate -m "add alert_rules and alert_instances tables"
uv run alembic upgrade head
```

**If database is NOT running (fallback):** Create migration manually with these tables:

**Table: `alert_rules`**
- `id`: Integer, primary_key, autoincrement
- `name`: String(200), nullable=False
- `description`: Text, nullable=True
- `rule_type`: String(30), nullable=False — CHECK IN ('delay_threshold', 'maintenance_due', 'registration_expiry', 'manual')
- `severity`: String(20), nullable=False, default='medium' — CHECK IN ('critical', 'high', 'medium', 'low', 'info')
- `threshold_config`: JSONB, nullable=False, default='{}'
- `enabled`: Boolean, nullable=False, default=True
- `created_at`: DateTime(timezone=True), nullable=False
- `updated_at`: DateTime(timezone=True), nullable=False

**Table: `alert_instances`**
- `id`: Integer, primary_key, autoincrement
- `title`: String(300), nullable=False
- `severity`: String(20), nullable=False, default='medium'
- `status`: String(20), nullable=False, default='active', index=True — CHECK IN ('active', 'acknowledged', 'resolved')
- `alert_type`: String(30), nullable=False
- `rule_id`: Integer, ForeignKey('alert_rules.id', ondelete='SET NULL'), nullable=True, index=True
- `source_entity_type`: String(20), nullable=True
- `source_entity_id`: String(100), nullable=True, index=True
- `details`: JSONB, nullable=True
- `acknowledged_at`: DateTime(timezone=True), nullable=True
- `acknowledged_by_id`: Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True
- `resolved_at`: DateTime(timezone=True), nullable=True
- `created_at`: DateTime(timezone=True), nullable=False
- `updated_at`: DateTime(timezone=True), nullable=False

**Indexes:**
- `ix_alert_dedup` on `(rule_id, source_entity_type, source_entity_id)` WHERE `status = 'active'` — partial unique index

## Logging Events

- `alerts.rule.create_started` — when admin creates a new rule
- `alerts.rule.create_completed` — rule successfully saved (includes rule_id)
- `alerts.rule.update_completed` — rule updated
- `alerts.rule.delete_completed` — rule deleted
- `alerts.instance.create_started` — manual or evaluator alert creation
- `alerts.instance.create_completed` — alert saved (includes alert_id, severity, alert_type)
- `alerts.instance.acknowledge_completed` — alert acknowledged (includes alert_id, user_id)
- `alerts.instance.resolve_completed` — alert resolved
- `alerts.instance.fetch_failed` — alert not found
- `alerts.evaluator.lifecycle_started` — evaluator task started (includes interval)
- `alerts.evaluator.lifecycle_stopped` — evaluator task stopped
- `alerts.evaluator.cycle_completed` — one evaluation cycle done (includes new_alerts count)
- `alerts.evaluator.cycle_failed` — evaluation cycle error (includes error, error_type)

## Testing Strategy

### Unit Tests
**Location:** `app/alerts/tests/test_service.py`
- AlertService rule CRUD — 8 tests (success + not_found for each operation)
- AlertService instance operations — 8 tests (list, create, acknowledge, resolve, summary, not_found cases)

**Location:** `app/alerts/tests/test_evaluator.py`
- Evaluator rule type handlers — 5 tests (maintenance, registration, delay, dedup, redis failure)
- Evaluator lifecycle — 2 tests (start/stop, exception handling)

### Route Tests
**Location:** `app/alerts/tests/test_routes.py`
- RBAC enforcement — 5 tests (auth required, admin-only rules, role restrictions)
- Happy path — 10 tests (all endpoints)
- Input validation — 2 tests (invalid filters, empty name)

### Edge Cases
- Empty threshold_config on rule creation — should use defaults
- Acknowledge already-acknowledged alert — should be idempotent or raise
- Resolve already-resolved alert — should be idempotent or raise
- Evaluator with no enabled rules — should complete with 0 new alerts
- Redis unavailable during delay evaluation — should log warning, return 0
- Vehicle with NULL maintenance date — should be skipped by evaluator

## Acceptance Criteria

This feature is complete when:
- [ ] `app/alerts/` vertical slice created with all 7 files (schemas, models, exceptions, repository, service, routes, evaluator)
- [ ] 7+ REST endpoints functional (5 rule CRUD + list/get/create/acknowledge/resolve instances + summary)
- [ ] Background evaluator runs on configurable interval, creates alerts with deduplication
- [ ] 3 automatic evaluators work: maintenance_due, registration_expiry, delay_threshold
- [ ] RBAC enforced: rules admin-only, instances admin+dispatcher, summary all authenticated
- [ ] All type checkers pass (mypy + pyright)
- [ ] All tests pass (30+ unit + route tests)
- [ ] Structured logging follows `alerts.component.action_state` pattern
- [ ] No type suppressions added (except standard pyright directives on routes file)
- [ ] Router registered in `app/main.py`
- [ ] Evaluator starts/stops in app lifespan
- [ ] No regressions in existing tests
- [ ] Security context requirements met (CTX-RBAC + CTX-INPUT)

## Completion Checklist

Before marking this plan as fully executed:
- [ ] All 14 tasks completed in order
- [ ] Per-task validations passed
- [ ] Full validation pyramid passed (Levels 1-4)
- [ ] No deviations from plan (or deviations documented with reasons)
- [ ] Ready for `/commit`

## Final Validation (5-Level Pyramid)

Run each level in order — every one must pass with 0 errors:

**Level 1: Syntax & Style**
```bash
uv run ruff format .
uv run ruff check --fix .
```

**Level 2: Type Safety**
```bash
uv run mypy app/
uv run pyright app/
```

**Level 3: Unit Tests (feature-specific)**
```bash
uv run pytest app/alerts/tests/ -v
```

**Level 4: Full Test Suite (unit)**
```bash
uv run pytest -v -m "not integration"
```

**Level 5: Server Validation (if Docker running)**
```bash
curl -s http://localhost:8123/health
```

**Success definition:** Levels 1-4 exit code 0, all tests pass, zero errors or warnings. Level 5 optional.

## Dependencies

- **Shared utilities used:** `PaginationParams`, `PaginatedResponse[T]` from `app.shared.schemas`; `TimestampMixin`, `utcnow()` from `app.shared.models`; `escape_like()` from `app.shared.utils` (if adding search)
- **Core modules used:** `Base` from `app.core.database`; `get_db`, `get_db_context` from `app.core.database`; `get_logger` from `app.core.logging`; `get_redis` from `app.core.redis`; `limiter` from `app.core.rate_limit`; `require_role` from `app.auth.dependencies`; `Settings`, `get_settings` from `app.core.config`
- **Cross-feature reads:** `Vehicle` model from `app.vehicles.models` (for maintenance/registration evaluators)
- **New dependencies:** None — all libraries already in `pyproject.toml`
- **New env vars:** `ALERTS_ENABLED` (default True), `ALERTS_CHECK_INTERVAL_SECONDS` (default 60) — add to `.env.example` if it exists

## Known Pitfalls

The executing agent MUST follow all 59 Python anti-pattern rules from `_shared/python-anti-patterns.md`. Key ones for this feature:

- **Rule 1**: No `assert` in production code — use `if not x:` checks
- **Rule 5**: No unused imports — only import what's used
- **Rule 8**: No EN DASH — use ASCII hyphen `-`
- **Rule 11**: Schema field additions break consumers — grep for `AlertRuleCreate(` etc. before modifying schemas
- **Rule 18**: ARG001 for unused params — add `_ = request` in route handlers
- **Rule 37**: No bare `except: pass` — always log in except blocks
- **Rule 38**: Background tasks must handle CancelledError and Exception separately
- **Rule 39**: `from datetime import date` shadows field names — use `import datetime` and `datetime.date`
- **Rule 40**: `Query(None)` needs `# noqa: B008`
- **Rule 54**: Constrained string fields must use `Literal[...]`
- **Rule 56**: `app.dependency_overrides` leaks between tests — save/restore in fixtures

**Additional:**
- The partial unique index `ix_alert_dedup` requires PostgreSQL-specific syntax (`postgresql_where`). This is fine since VTV only targets PostgreSQL.
- The evaluator reads from `app.vehicles.models.Vehicle` (cross-feature read) — this is allowed per CLAUDE.md cross-feature access rules.
- The `threshold_config` JSONB field uses `dict[str, int | float | str | bool]` in schemas but `dict[str, Any]` in models — this is intentional (models are more permissive, schemas validate input).

## Notes

- **Future enhancement: WebSocket push** — When real-time alert delivery is needed, add a Redis Pub/Sub channel (`alerts:new`) that the evaluator publishes to, and extend the existing `ws_manager` or create a dedicated alerts WebSocket endpoint. The data model supports this without changes.
- **Future enhancement: Alert rules UI** — The CMS will need an admin page for managing alert rules. The REST API is designed to support this.
- **Future enhancement: Email/SMS notifications** — Add a `notification_channels` JSONB field to `AlertRule` and a delivery service. Out of scope for this phase.
- **Performance consideration:** The evaluator queries vehicles table on every cycle. For large fleets (1000+ vehicles), consider caching or incremental checks. For the current RS fleet (~1097 vehicles), the simple query approach is sufficient.
- **GDPR:** Alert instances may reference driver IDs indirectly (via events or vehicles). The 90-day auto-cleanup from TimescaleDB doesn't apply here — consider adding a separate retention policy for old resolved alerts if needed.

## Pre-Implementation Checklist

The executing agent MUST verify before writing any code:
- [ ] Read all files listed in "Relevant Files" section
- [ ] Reviewed existing events module for pattern conformance
- [ ] Understood the solution approach and why alternatives were rejected
- [ ] Clear on task execution order (schemas → models → exceptions → repository → service → routes → evaluator → config → main → tests)
- [ ] Validation commands are executable in this environment
