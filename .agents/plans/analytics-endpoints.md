# Plan: Analytics REST Endpoints

## Feature Metadata
**Feature Type**: New Capability
**Estimated Complexity**: Medium
**Primary Systems Affected**: analytics (new), vehicles (read), drivers (read), transit (read), schedules (read)

## Feature Description

The VTV platform currently has no dedicated analytics REST endpoints. The only analytics logic lives in the `get_adherence_report` agent tool, which is inaccessible to the CMS frontend via REST. The frontend analytics dashboard needs structured summary data from four domains: on-time performance (GTFS-RT), fleet status (vehicles table), driver coverage (drivers table), and route utilization (schedules + transit).

This feature creates a new `app/analytics/` vertical slice that provides read-only aggregation endpoints. It does NOT create new database tables — it queries existing tables (vehicles, drivers, routes, trips, calendars) and existing services (TransitService, GTFSStaticCache) to produce dashboard-ready summaries. The adherence computation logic from the agent tool is extracted into a shared helper so both the REST endpoint and the agent tool can reuse it without duplication.

Four endpoints are exposed under `/api/v1/analytics/`: fleet summary, driver summary, on-time performance, and a combined overview that returns all three in one call for initial dashboard load.

## User Story

As a planner or administrator
I want to view fleet status, driver coverage, and on-time performance summaries via REST endpoints
So that the CMS analytics dashboard can render charts and KPI cards without relying on the AI agent chat interface.

## Solution Approach

Create a pure aggregation layer — no new models, no migrations. The analytics service reads from existing repositories (VehicleRepository, DriverRepository) and existing transit infrastructure (TransitService, GTFSStaticCache, GTFSRealtimeClient). Each endpoint returns pre-computed summary objects optimized for frontend chart rendering.

**Approach Decision:**
We chose a thin aggregation service over existing repositories because:
- Analytics queries span multiple feature boundaries (vehicles + drivers + transit + schedules)
- Summary shapes differ from CRUD response schemas (counts, percentages, grouped breakdowns)
- No write operations — read-only cross-feature queries are explicitly allowed by VTV conventions

**Alternatives Considered:**
- Extending each feature's routes with summary endpoints: Rejected because analytics queries cross feature boundaries and would violate VSA encapsulation
- Materializing analytics into a separate table with background jobs: Rejected as premature — real-time aggregation over small datasets (~1000 vehicles, ~200 drivers) is sub-second
- Reusing agent tool JSON output directly: Rejected because agent tool responses are optimized for LLM token efficiency (truncated, text summaries) not frontend chart rendering

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, logging patterns, type checking requirements
- `app/shared/schemas.py` — PaginationParams, PaginatedResponse, ErrorResponse patterns
- `app/shared/models.py` — TimestampMixin (not needed here but understand the pattern)

### Similar Features (Examples to Follow)
- `app/transit/routes.py` (lines 1-48) — Read-only REST route pattern with rate limiting, auth, Query params
- `app/transit/service.py` (lines 30-110) — Service pattern that aggregates data from multiple sources
- `app/transit/schemas.py` (lines 1-66) — Pydantic response schema pattern for REST endpoints
- `app/vehicles/repository.py` (lines 50-131) — Repository list/count query patterns to reuse
- `app/drivers/repository.py` (lines 52-131) — Repository list/count query patterns to reuse

### Existing Data Sources (Read to Understand Available Fields)
- `app/vehicles/models.py` (lines 16-53) — Vehicle fields: status (active/inactive/maintenance), vehicle_type (bus/trolleybus/tram), mileage_km, registration_expiry, next_maintenance_date, current_driver_id
- `app/drivers/models.py` (lines 16-48) — Driver fields: status (available/on_duty/on_leave/sick), default_shift, license_expiry_date, medical_cert_expiry, qualified_route_ids
- `app/schedules/models.py` (lines 36-52) — Route fields: gtfs_route_id, route_short_name, route_type, is_active
- `app/core/agents/tools/transit/get_adherence_report.py` (lines 43-157) — Adherence computation logic: _classify_trip_status, _compute_route_adherence helpers

### Files to Modify
- `app/main.py` (line 164) — Register analytics_router after compliance_router
- `app/tests/test_security.py` — New analytics routes will be auto-discovered by TestAllEndpointsRequireAuth (no changes needed if auth dependency is added correctly)

## Implementation Plan

### Phase 1: Foundation (Schemas)
Define all response schemas for the four analytics endpoints. No database interaction yet.

### Phase 2: Core Implementation (Service + Routes)
Build the analytics service that queries existing repositories and transit infrastructure. Wire up routes with auth and rate limiting.

### Phase 3: Integration & Validation (Tests + Router Registration)
Unit tests for service logic, route tests for endpoint behavior, register router in main.py.

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.

---

### Task 1: Create Analytics Response Schemas
**File:** `app/analytics/schemas.py` (create new)
**Action:** CREATE

Create response schemas for all four analytics endpoints. These are REST-optimized (not agent-optimized) — full data for chart rendering, no truncation.

```python
"""Pydantic response schemas for analytics endpoints.

These models are optimized for the CMS frontend dashboard.
They provide pre-computed summaries from existing data sources
(vehicles, drivers, transit, schedules).
"""

import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

VehicleType = Literal["bus", "trolleybus", "tram"]
VehicleStatus = Literal["active", "inactive", "maintenance"]
DriverStatus = Literal["available", "on_duty", "on_leave", "sick"]
DriverShift = Literal["morning", "afternoon", "evening", "night"]
AdherenceStatus = Literal["on_time", "late", "early", "no_data"]
```

Define these schema classes:

1. **`FleetTypeSummary`** — Per vehicle_type counts:
   - `vehicle_type: VehicleType`
   - `total: int`
   - `active: int`
   - `inactive: int`
   - `in_maintenance: int`

2. **`FleetSummaryResponse`** — Fleet overview:
   - `total_vehicles: int`
   - `active_vehicles: int`
   - `inactive_vehicles: int`
   - `in_maintenance: int`
   - `by_type: list[FleetTypeSummary]`
   - `maintenance_due_7d: int` — vehicles with next_maintenance_date within 7 days
   - `registration_expiring_30d: int` — vehicles with registration_expiry within 30 days
   - `unassigned_vehicles: int` — active vehicles with no current_driver_id
   - `average_mileage_km: float`
   - `generated_at: datetime.datetime`
   - `model_config = ConfigDict(from_attributes=True)`

3. **`ShiftCoverageSummary`** — Per shift counts:
   - `shift: DriverShift`
   - `total: int`
   - `available: int`
   - `on_duty: int`
   - `on_leave: int`
   - `sick: int`

4. **`DriverSummaryResponse`** — Driver coverage overview:
   - `total_drivers: int`
   - `available_drivers: int`
   - `on_duty_drivers: int`
   - `on_leave_drivers: int`
   - `sick_drivers: int`
   - `by_shift: list[ShiftCoverageSummary]`
   - `license_expiring_30d: int` — drivers with license_expiry_date within 30 days
   - `medical_expiring_30d: int` — drivers with medical_cert_expiry within 30 days
   - `generated_at: datetime.datetime`
   - `model_config = ConfigDict(from_attributes=True)`

5. **`RoutePerformanceSummary`** — Per route on-time metrics:
   - `route_id: str`
   - `route_short_name: str`
   - `scheduled_trips: int`
   - `tracked_trips: int`
   - `on_time_count: int`
   - `late_count: int`
   - `early_count: int`
   - `on_time_percentage: float`
   - `average_delay_seconds: float`

6. **`OnTimePerformanceResponse`** — Network adherence:
   - `service_date: str` — ISO date
   - `service_type: str` — weekday/saturday/sunday
   - `time_from: str | None`
   - `time_until: str | None`
   - `total_routes: int`
   - `network_on_time_percentage: float`
   - `network_average_delay_seconds: float`
   - `routes: list[RoutePerformanceSummary]` — sorted by worst on-time%
   - `generated_at: datetime.datetime`

7. **`AnalyticsOverviewResponse`** — Combined dashboard load:
   - `fleet: FleetSummaryResponse`
   - `drivers: DriverSummaryResponse`
   - `on_time: OnTimePerformanceResponse`

All response classes must have `model_config = ConfigDict(from_attributes=True)`.

**Per-task validation:**
- `uv run ruff format app/analytics/schemas.py`
- `uv run ruff check --fix app/analytics/schemas.py`
- `uv run mypy app/analytics/schemas.py`
- `uv run pyright app/analytics/schemas.py`

---

### Task 2: Create Analytics `__init__.py`
**File:** `app/analytics/__init__.py` (create new)
**Action:** CREATE

Create an empty `__init__.py` for the analytics package.

**Per-task validation:**
- `uv run ruff format app/analytics/__init__.py`
- `uv run ruff check --fix app/analytics/__init__.py`

---

### Task 3: Create Test `__init__.py`
**File:** `app/analytics/tests/__init__.py` (create new)
**Action:** CREATE

Create an empty `__init__.py` for the analytics test package.

**Per-task validation:**
- `uv run ruff format app/analytics/tests/__init__.py`
- `uv run ruff check --fix app/analytics/tests/__init__.py`

---

### Task 4: Create Analytics Service
**File:** `app/analytics/service.py` (create new)
**Action:** CREATE

Create the analytics service that aggregates data from existing repositories and transit infrastructure. This is the core business logic layer.

**Required imports:**
```python
from __future__ import annotations

import datetime
import time

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.schemas import (
    DriverSummaryResponse,
    FleetSummaryResponse,
    FleetTypeSummary,
    OnTimePerformanceResponse,
    RoutePerformanceSummary,
    ShiftCoverageSummary,
)
from app.core.logging import get_logger
from app.drivers.models import Driver
from app.vehicles.models import Vehicle

logger = get_logger(__name__)
```

Define class **`AnalyticsService`** with `__init__(self, db: AsyncSession) -> None`.

**Method 1: `async def get_fleet_summary(self) -> FleetSummaryResponse`**
- Query `Vehicle` table with `is_active` filter variations
- Use `func.count()` with `case()` or multiple queries for status/type breakdowns
- Implementation approach: Run a single query that groups by `vehicle_type` and `status` using `func.count()`, then pivot results in Python. This avoids N+1 queries.
- For `maintenance_due_7d`: `select(func.count()).select_from(Vehicle).where(Vehicle.is_active.is_(True), Vehicle.next_maintenance_date <= today + timedelta(days=7), Vehicle.next_maintenance_date >= today)`
- For `registration_expiring_30d`: same pattern with `registration_expiry` and 30 days
- For `unassigned_vehicles`: `Vehicle.is_active.is_(True)` AND `Vehicle.current_driver_id.is_(None)` AND `Vehicle.status == "active"`
- For `average_mileage_km`: `func.avg(Vehicle.mileage_km)` where `is_active`
- Add structured logging: `analytics.fleet_summary.started`, `analytics.fleet_summary.completed` with `duration_ms`
- Use `datetime.datetime.now(tz=datetime.UTC)` for `generated_at`

**Method 2: `async def get_driver_summary(self) -> DriverSummaryResponse`**
- Query `Driver` table grouped by `status` and `default_shift`
- For `license_expiring_30d`: `Driver.is_active.is_(True)` AND `Driver.license_expiry_date <= today + 30d` AND `>= today`
- For `medical_expiring_30d`: same pattern with `medical_cert_expiry`
- Build `ShiftCoverageSummary` list from grouped results
- Add structured logging: `analytics.driver_summary.started`, `analytics.driver_summary.completed`

**Method 3: `async def get_on_time_performance(self, *, route_id: str | None = None, date: str | None = None, time_from: str | None = None, time_until: str | None = None) -> OnTimePerformanceResponse`**
- This method uses the transit infrastructure (NOT the database) to compute adherence
- Import and use:
  ```python
  import httpx
  from app.core.agents.tools.transit.client import GTFSRealtimeClient, TripUpdateData
  from app.core.agents.tools.transit.static_cache import get_static_cache
  from app.core.agents.tools.transit.utils import (
      classify_service_type,
      gtfs_time_to_minutes,
      validate_date,
  )
  from app.core.config import get_settings
  ```
- Reuse the existing `_classify_trip_status` and `_compute_route_adherence` from `app.core.agents.tools.transit.get_adherence_report` by importing them directly:
  ```python
  from app.core.agents.tools.transit.get_adherence_report import (
      _classify_trip_status,
      _compute_route_adherence,
  )
  ```
  NOTE: These are module-private functions (prefixed with `_`). Importing them directly is acceptable here because extracting them to a shared module would be premature (only 2 consumers). If a third consumer appears, extract to `app/shared/`.
- Logic flow (mirrors the agent tool but returns structured schema, not JSON string):
  1. Validate date with `validate_date(date)`. If result is a string, raise `ValueError(result)`.
  2. Create `GTFSRealtimeClient` and fetch trip updates
  3. Get static cache, active service IDs for the date
  4. If `route_id` provided, compute single-route adherence
  5. Otherwise, compute network-wide adherence (find routes with RT data, compute each, sort by worst)
  6. Cap at 25 routes (more than agent's 15 since REST serves charts)
  7. Build and return `OnTimePerformanceResponse`
- IMPORTANT: This method needs its own httpx client. Create a short-lived one:
  ```python
  settings = get_settings()
  async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0)) as http_client:
      ...
  ```
- Add structured logging: `analytics.on_time.started`, `analytics.on_time.completed`
- Wrap the entire body in try/except. On exception, log `analytics.on_time.failed` with `exc_info=True, error=str(e), error_type=type(e).__name__` and re-raise.

**Per-task validation:**
- `uv run ruff format app/analytics/service.py`
- `uv run ruff check --fix app/analytics/service.py`
- `uv run mypy app/analytics/service.py`
- `uv run pyright app/analytics/service.py`

---

### Task 5: Create Analytics Routes
**File:** `app/analytics/routes.py` (create new)
**Action:** CREATE

Create REST endpoints following the pattern in `app/transit/routes.py`.

**Required imports:**
```python
# pyright: reportUnknownMemberType=false, reportUntypedFunctionDecorator=false
"""Analytics REST API routes for dashboard summary data.

Endpoints:
- GET /api/v1/analytics/fleet-summary - Fleet status breakdown
- GET /api/v1/analytics/driver-summary - Driver coverage breakdown
- GET /api/v1/analytics/on-time-performance - On-time adherence metrics
- GET /api/v1/analytics/overview - Combined dashboard summary
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.schemas import (
    AnalyticsOverviewResponse,
    DriverSummaryResponse,
    FleetSummaryResponse,
    OnTimePerformanceResponse,
)
from app.analytics.service import AnalyticsService
from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.core.database import get_db
from app.core.logging import get_logger
from app.core.rate_limit import limiter

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])
```

**Endpoint 1: `GET /api/v1/analytics/fleet-summary`**
- Rate limit: `30/minute`
- Auth: `_current_user: User = Depends(get_current_user)` (with `# noqa: B008`)
- DB: `db: AsyncSession = Depends(get_db)` (with `# noqa: B008`)
- Response model: `FleetSummaryResponse`
- Body: `service = AnalyticsService(db)` then `return await service.get_fleet_summary()`
- Log: `analytics.api.fleet_summary_requested`

**Endpoint 2: `GET /api/v1/analytics/driver-summary`**
- Same pattern as fleet-summary
- Response model: `DriverSummaryResponse`
- Log: `analytics.api.driver_summary_requested`

**Endpoint 3: `GET /api/v1/analytics/on-time-performance`**
- Rate limit: `10/minute` (heavier — hits external GTFS-RT feeds)
- Query params:
  - `route_id: str | None = Query(None, max_length=100, pattern=r"^[\w\-.:]+$")`
  - `date: str | None = Query(None, max_length=10, pattern=r"^\d{4}-\d{2}-\d{2}$")`
  - `time_from: str | None = Query(None, max_length=5, pattern=r"^\d{2}:\d{2}$")`
  - `time_until: str | None = Query(None, max_length=5, pattern=r"^\d{2}:\d{2}$")`
- Response model: `OnTimePerformanceResponse`
- Body: call `service.get_on_time_performance(route_id=route_id, date=date, time_from=time_from, time_until=time_until)`
- Catch `ValueError` from service and return `HTTPException(status_code=400, detail=str(e))`
- Catch `Exception` broadly and return `HTTPException(status_code=503, detail="Transit data temporarily unavailable")`
  - IMPORTANT: Log the exception before raising 503: `logger.warning("analytics.api.on_time_failed", error=str(e), error_type=type(e).__name__)`
- Log: `analytics.api.on_time_requested`

**Endpoint 4: `GET /api/v1/analytics/overview`**
- Rate limit: `10/minute`
- Auth + DB dependencies
- Response model: `AnalyticsOverviewResponse`
- Body: call all three service methods, assemble into `AnalyticsOverviewResponse`
- For on-time, wrap in try/except and provide a fallback empty response if transit data is unavailable (log warning but don't fail the whole overview)
- Log: `analytics.api.overview_requested`

Add `_ = request` after the function signature for all endpoints (the `request` param is required by slowapi but unused directly — prevents ARG001).

Add ruff per-file-ignore for `ARG001` in `pyproject.toml` if not already present for this file. Check `pyproject.toml` first — the pattern `"app/[feature]/routes.py" = ["ARG001"]` is used for other routes files. Add `"app/analytics/routes.py" = ["ARG001"]`.

**Per-task validation:**
- `uv run ruff format app/analytics/routes.py`
- `uv run ruff check --fix app/analytics/routes.py`
- `uv run mypy app/analytics/routes.py`
- `uv run pyright app/analytics/routes.py`

---

### Task 6: Update pyproject.toml for ARG001 Exemption
**File:** `pyproject.toml` (modify existing)
**Action:** UPDATE

Add `"app/analytics/routes.py" = ["ARG001"]` to `[tool.ruff.lint.per-file-ignores]` section, following the same pattern as existing route files (e.g., `app/transit/routes.py`, `app/vehicles/routes.py`).

Check if `app/vehicles/routes.py` already has an ARG001 exemption. If not, add it too (it uses `request` param for slowapi). The existing exemptions are on lines 91-99 of `pyproject.toml`.

**Per-task validation:**
- `uv run ruff format pyproject.toml` (no-op but confirms valid TOML)
- `uv run ruff check --fix app/analytics/routes.py`

---

### Task 7: Create Service Unit Tests
**File:** `app/analytics/tests/test_service.py` (create new)
**Action:** CREATE

Test the analytics service with mocked database sessions. Follow patterns from `app/vehicles/tests/test_service.py`.

**Required imports:**
```python
"""Unit tests for analytics service."""

from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.analytics.schemas import (
    DriverSummaryResponse,
    FleetSummaryResponse,
    OnTimePerformanceResponse,
)
from app.analytics.service import AnalyticsService
```

**Test 1: `test_fleet_summary_empty_db`**
- Mock `db.execute()` to return empty result sets (scalar_one returns 0, scalars().all() returns [])
- Assert `FleetSummaryResponse` with all zeros
- Assert `generated_at` is recent (within 5 seconds)

**Test 2: `test_fleet_summary_with_vehicles`**
- Create mock Vehicle objects with various statuses and types
- Mock the grouped query to return realistic counts
- Assert correct breakdown by type and status
- Assert `maintenance_due_7d` and `registration_expiring_30d` counts

**Test 3: `test_driver_summary_empty_db`**
- Similar to fleet empty test
- Assert all zeros and empty `by_shift` list

**Test 4: `test_driver_summary_with_drivers`**
- Mock grouped driver data
- Assert correct shift breakdown and expiry counts

**Test 5: `test_on_time_performance_returns_response`**
- Patch `httpx.AsyncClient`, `GTFSRealtimeClient`, `get_static_cache`, `get_settings`
- Mock trip updates and static cache data
- Assert `OnTimePerformanceResponse` is returned with expected fields

**Test 6: `test_on_time_performance_invalid_date`**
- Pass `date="not-a-date"`
- Assert `ValueError` is raised

**Test 7: `test_on_time_performance_transit_error`**
- Mock `GTFSRealtimeClient.fetch_trip_updates` to raise `httpx.ConnectError`
- Assert the exception propagates (service re-raises)

Mark no tests as `@pytest.mark.integration` — all use mocks.

NOTE on mocking DB queries: The service uses raw SQLAlchemy `select()` + `func.count()` queries directly (not going through a repository). Mock `self.db.execute()` to return `MagicMock` objects with `.scalar_one()` and `.scalars().all()` chains. Use `AsyncMock` for `execute`.

**Per-task validation:**
- `uv run ruff format app/analytics/tests/test_service.py`
- `uv run ruff check --fix app/analytics/tests/test_service.py`
- `uv run pytest app/analytics/tests/test_service.py -v`

---

### Task 8: Create Route Unit Tests
**File:** `app/analytics/tests/test_routes.py` (create new)
**Action:** CREATE

Test the REST endpoints using FastAPI TestClient. Follow patterns from `app/vehicles/tests/test_routes.py`.

**Required imports:**
```python
"""Unit tests for analytics routes."""

from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.analytics.schemas import (
    DriverSummaryResponse,
    FleetSummaryResponse,
    FleetTypeSummary,
    OnTimePerformanceResponse,
    ShiftCoverageSummary,
)
from app.main import app
```

**Setup fixture:**
```python
@pytest.fixture()
def client():
    """Create test client with auth override."""
    from app.auth.dependencies import get_current_user
    from app.core.database import get_db

    mock_user = MagicMock()
    mock_user.id = 1
    mock_user.role = "admin"

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_db] = lambda: AsyncMock()

    yield TestClient(app)

    app.dependency_overrides.clear()
```

IMPORTANT: The fixture MUST clear `dependency_overrides` after yield (anti-pattern #56).

**Test 1: `test_fleet_summary_endpoint`**
- Patch `AnalyticsService.get_fleet_summary` to return a valid `FleetSummaryResponse`
- `GET /api/v1/analytics/fleet-summary`
- Assert 200 and response contains `total_vehicles`

**Test 2: `test_driver_summary_endpoint`**
- Same pattern, patch `get_driver_summary`

**Test 3: `test_on_time_performance_endpoint`**
- Patch `get_on_time_performance`
- Assert 200

**Test 4: `test_on_time_performance_bad_date`**
- Patch service to raise `ValueError("Invalid date")`
- Assert 400

**Test 5: `test_on_time_performance_transit_unavailable`**
- Patch service to raise `Exception("Feed timeout")`
- Assert 503

**Test 6: `test_overview_endpoint`**
- Patch all three service methods
- Assert 200 and response has `fleet`, `drivers`, `on_time` keys

**Test 7: `test_overview_degrades_on_transit_failure`**
- Patch fleet and driver to succeed, on_time to raise `Exception`
- Assert 200 (overview should gracefully degrade)

**Test 8: `test_endpoints_require_auth`**
- Remove `get_current_user` override
- `GET /api/v1/analytics/fleet-summary` without auth
- Assert 401 (not 403 — anti-pattern #55)

Disable limiter in tests: add `from app.core.rate_limit import limiter` at top of file, then `limiter.enabled = False` AFTER all imports (anti-pattern #13).

**Per-task validation:**
- `uv run ruff format app/analytics/tests/test_routes.py`
- `uv run ruff check --fix app/analytics/tests/test_routes.py`
- `uv run pytest app/analytics/tests/test_routes.py -v`

---

### Task 9: Create Test Conftest
**File:** `app/analytics/tests/conftest.py` (create new)
**Action:** CREATE

Create a minimal conftest with shared fixtures if needed. At minimum:

```python
"""Shared fixtures for analytics tests."""
```

This may remain nearly empty. If shared mock factories emerge during Task 7/8, add them here.

**Per-task validation:**
- `uv run ruff format app/analytics/tests/conftest.py`
- `uv run ruff check --fix app/analytics/tests/conftest.py`

---

### Task 10: Register Router in main.py
**File:** `app/main.py` (modify existing)
**Action:** UPDATE

Add the analytics router import and registration:

1. Add import after line 48 (`from app.vehicles.routes import router as vehicles_router`):
   ```python
   from app.analytics.routes import router as analytics_router
   ```

2. Add router registration after line 164 (`app.include_router(compliance_router)`):
   ```python
   app.include_router(analytics_router)
   ```

**Per-task validation:**
- `uv run ruff format app/main.py`
- `uv run ruff check --fix app/main.py`
- `uv run mypy app/main.py`

---

## Migration

No migration required. This feature is read-only over existing tables.

## Logging Events

- `analytics.fleet_summary.started` — Fleet summary computation begins
- `analytics.fleet_summary.completed` — Fleet summary done (includes `duration_ms`, `total_vehicles`)
- `analytics.driver_summary.started` — Driver summary computation begins
- `analytics.driver_summary.completed` — Driver summary done (includes `duration_ms`, `total_drivers`)
- `analytics.on_time.started` — On-time performance computation begins (includes `route_id`, `date`)
- `analytics.on_time.completed` — On-time done (includes `duration_ms`, `total_routes`, `network_on_time_pct`)
- `analytics.on_time.failed` — On-time computation failed (includes `exc_info`, `error`, `error_type`, `duration_ms`)
- `analytics.api.fleet_summary_requested` — REST endpoint hit
- `analytics.api.driver_summary_requested` — REST endpoint hit
- `analytics.api.on_time_requested` — REST endpoint hit (includes `route_id`, `date`)
- `analytics.api.on_time_failed` — REST on-time returned 503 (includes `error`, `error_type`)
- `analytics.api.overview_requested` — REST overview endpoint hit

## Testing Strategy

### Unit Tests
**Location:** `app/analytics/tests/test_service.py`
- FleetSummaryResponse computation with empty DB
- FleetSummaryResponse computation with vehicles of various statuses/types
- DriverSummaryResponse computation with empty DB
- DriverSummaryResponse computation with drivers of various shifts/statuses
- OnTimePerformanceResponse with mocked GTFS data
- OnTimePerformanceResponse with invalid date
- OnTimePerformanceResponse with transit feed error

**Location:** `app/analytics/tests/test_routes.py`
- All four endpoints return 200 with valid auth and mocked service
- on-time endpoint returns 400 for invalid date
- on-time endpoint returns 503 when transit unavailable
- overview gracefully degrades when on-time fails
- Endpoints return 401 without auth

### Edge Cases
- Empty database (zero vehicles, zero drivers) — all counts are 0, percentages are 0.0
- No GTFS-RT data available — on-time returns empty routes list, 0% on-time
- All vehicles in maintenance — maintenance count equals total
- No drivers on shift — shift list is empty or has zero counts

## Acceptance Criteria

This feature is complete when:
- [ ] `GET /api/v1/analytics/fleet-summary` returns vehicle counts by type/status with maintenance and registration alerts
- [ ] `GET /api/v1/analytics/driver-summary` returns driver counts by shift/status with license and medical expiry alerts
- [ ] `GET /api/v1/analytics/on-time-performance` returns route adherence metrics from live GTFS-RT data
- [ ] `GET /api/v1/analytics/overview` returns all three summaries in one call with graceful degradation
- [ ] All endpoints require authentication (caught by TestAllEndpointsRequireAuth)
- [ ] All type checkers pass (mypy + pyright)
- [ ] All tests pass (unit)
- [ ] Structured logging follows `analytics.component.action_state` pattern
- [ ] No type suppressions added (except pyright file-level directives for slowapi)
- [ ] Router registered in `app/main.py`
- [ ] No regressions in existing tests

## Completion Checklist

Before marking this plan as fully executed:
- [ ] All 10 tasks completed in order
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
uv run pytest app/analytics/tests/ -v
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

- Shared utilities used: `get_logger()` from `app.core.logging`, `get_db()` from `app.core.database`, `get_settings()` from `app.core.config`, `escape_like()` from `app.shared.utils` (if needed for any future text filtering)
- Core modules used: `app.core.rate_limit.limiter`, `app.auth.dependencies.get_current_user`
- Cross-feature reads: `app.vehicles.models.Vehicle`, `app.drivers.models.Driver`, `app.core.agents.tools.transit.*` (client, static_cache, utils, get_adherence_report)
- New dependencies: None — all libraries already in pyproject.toml
- New env vars: None

## Known Pitfalls

The executing agent MUST follow all 59 Python anti-pattern rules from `@_shared/python-anti-patterns.md`. Key rules for this feature:

- **Rule 1**: No `assert` in production code — use `if` checks
- **Rule 5**: No unused imports — only import what's used
- **Rule 9**: ARG001 for unused `request` param — add `_ = request` in route functions
- **Rule 13**: `limiter.enabled = False` in tests AFTER all imports
- **Rule 18**: ARG001 applies to ALL unused params — add `_ = param` with comment
- **Rule 39**: `from datetime import date` shadows field names — use `import datetime` and `datetime.date`
- **Rule 40**: FastAPI `Query(None)` needs `# noqa: B008`
- **Rule 44**: Never log URLs that may contain credentials
- **Rule 55**: `HTTPBearer(auto_error=False)` for 401 not 403 (auth is handled by existing `get_current_user`)
- **Rule 56**: `dependency_overrides` must be cleared in test fixtures

**Additional considerations:**
- The `_compute_route_adherence` and `_classify_trip_status` functions are imported from the agent tool module with underscore prefix. This is intentional — they are stable internal helpers. Document the import with a comment.
- The on-time endpoint creates a short-lived httpx client per request. This is acceptable for an analytics endpoint called infrequently (~1/min). If this becomes a bottleneck, refactor to use the transit service singleton.
- The overview endpoint catches on-time failures independently to avoid blocking fleet/driver data. The fallback creates an empty `OnTimePerformanceResponse` with zero values.

## Notes

- **No database models or migrations** — this is a pure aggregation layer
- **Future extension**: Add `GET /api/v1/analytics/route/{route_id}/performance` for single-route deep-dive with per-trip details
- **Future extension**: Add time-series historical data once a data warehouse or materialized views are implemented
- **Performance**: Fleet and driver summaries are simple COUNT queries (~1ms). On-time performance hits external GTFS-RT feeds (100-500ms). The overview endpoint parallelizes DB queries but runs on-time sequentially.
- **Security**: All endpoints require auth. Rate limiting is stricter on on-time (10/min) due to external feed dependency. No PII is exposed in analytics responses.

## Pre-Implementation Checklist

The executing agent MUST verify before writing any code:
- [ ] Read all files listed in "Relevant Files" section
- [ ] Understood the solution approach (read-only aggregation, no new models)
- [ ] Clear on task execution order (schemas -> service -> routes -> tests -> registration)
- [ ] Validation commands are executable in this environment
- [ ] Confirmed `app/analytics/` directory does not already exist
