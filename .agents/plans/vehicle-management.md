# Plan: Vehicle Management

## Feature Metadata
**Feature Type**: New Capability
**Estimated Complexity**: Medium
**Primary Systems Affected**: `app/vehicles/` (new), `app/drivers/` (cross-read), `app/schedules/` (cross-read for routes), `app/main.py` (router registration)

## Feature Description

Vehicle Management adds fleet/vehicle CRUD operations to the VTV transit operations platform. Each vehicle represents a physical bus, trolleybus, or tram in the Rigas Satiksme fleet — identified by a unique fleet number (e.g., "4521") that matches the `vehicle_id` field in GTFS-RT position data.

The feature tracks vehicle metadata (manufacturer, model year, license plate, capacity), operational status (active, inactive, in maintenance), current driver assignment, qualified routes, and maintenance history. Maintenance records form a separate sub-resource capturing service type, mileage at service, cost, and next scheduled date.

This extends the existing driver management feature by establishing the vehicle-driver pairing that dispatchers need for shift planning. The fleet number linkage to GTFS-RT positions means the dashboard can eventually show which specific vehicle (with its maintenance history and assigned driver) is at each map position.

## User Story

As a transit administrator
I want to manage the vehicle fleet with maintenance tracking and driver assignments
So that I can track vehicle availability, plan maintenance schedules, and pair drivers with vehicles for shift operations.

## Solution Approach

We implement Vehicle Management as a standard vertical slice under `app/vehicles/` following the exact patterns established by the drivers feature. Two SQLAlchemy models: `Vehicle` (fleet metadata + status + current driver FK) and `MaintenanceRecord` (service history linked to vehicle). The driver assignment is a nullable FK on the Vehicle model pointing to `drivers.id` — simple and sufficient for "one driver currently assigned to one vehicle" without a separate join table.

Route qualification uses a comma-separated string field (`qualified_route_ids`) matching the same pattern drivers use for `qualified_route_ids`. This avoids a many-to-many join table for MVP while remaining consistent with the existing codebase pattern.

**Approach Decision:**
We chose a single nullable FK (`current_driver_id`) for driver assignment because:
- It matches the simplicity level of the rest of the MVP
- One vehicle has at most one currently assigned driver
- Historical assignment tracking is a Phase 3 concern
- No join table complexity for a 1:0..1 relationship

**Alternatives Considered:**
- **Separate VehicleDriverAssignment table**: Rejected because it adds join table complexity for a relationship that's effectively 1:0..1 in the current phase. Can be added later if historical assignment tracking is needed.
- **JSON field for route qualification**: Rejected because the existing `qualified_route_ids` CSV pattern on drivers is established and consistent. Switching to JSON for one feature creates inconsistency.
- **Separate VehicleRoute many-to-many table**: Rejected for MVP — CSV string is the established pattern. Extract to a proper join table when the codebase hits the three-feature threshold.

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, logging patterns, type checking requirements
- `app/shared/models.py` (lines 10-41) — `TimestampMixin`, `utcnow()`, `Base` import pattern
- `app/shared/schemas.py` (lines 11-64) — `PaginationParams`, `PaginatedResponse[T]`
- `app/shared/utils.py` (lines 6-15) — `escape_like()` for ILIKE search
- `app/core/database.py` (lines 40-79) — `Base`, `get_db()` dependency
- `app/core/exceptions.py` (lines 14-58) — `AppError`, `NotFoundError`, `DomainValidationError`
- `app/core/logging.py` — `get_logger(__name__)` pattern

### Similar Features (Examples to Follow)
- `app/drivers/models.py` (lines 16-49) — Mapped column syntax, TimestampMixin, status field, CSV qualified_route_ids
- `app/drivers/schemas.py` (lines 8-80) — Base/Create/Update/Response schema hierarchy with field validators
- `app/drivers/repository.py` (lines 26-195) — CRUD + search + filter + count pattern
- `app/drivers/service.py` (lines 23-200) — Service layer with pagination, duplicate checks, structured logging
- `app/drivers/routes.py` (lines 20-97) — Router with RBAC, rate limiting, pagination params
- `app/drivers/exceptions.py` (lines 1-21) — Feature-specific exception hierarchy
- `app/drivers/tests/conftest.py` (lines 12-76) — Factory function pattern for test fixtures
- `app/drivers/tests/test_routes.py` — Route testing with mocked service
- `app/drivers/tests/test_service.py` — Service testing with mocked repository
- `app/events/models.py` (lines 18-42) — ForeignKey to drivers.id pattern, JSONB column

### Files to Modify
- `app/main.py` (lines 149-160) — Register vehicles_router

## Implementation Plan

### Phase 1: Foundation
Define schemas and models — the data contract and database structure. Vehicle model with fleet metadata, status tracking, driver FK, and route qualification. MaintenanceRecord model for service history. Pydantic schemas for all CRUD operations.

### Phase 2: Core Implementation
Repository with full CRUD + search + filters for both vehicles and maintenance records. Service layer with business logic (duplicate fleet number check, driver assignment validation, maintenance scheduling). Routes with RBAC enforcement.

### Phase 3: Integration & Validation
Exception classes, router registration, unit tests for service and routes, and the full validation pyramid.

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.

### Task 1: Create Vehicle Schemas
**File:** `app/vehicles/schemas.py` (create new)
**Action:** CREATE

Create Pydantic schemas for vehicles and maintenance records:

```python
"""Vehicle management schemas."""

import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

VehicleType: type = Literal["bus", "trolleybus", "tram"]
VehicleStatus: type = Literal["active", "inactive", "maintenance"]
MaintenanceType: type = Literal["scheduled", "unscheduled", "inspection", "repair"]
```

**VehicleBase:**
- `fleet_number: str` — Field(min_length=1, max_length=20), unique fleet identifier matching GTFS-RT vehicle_id
- `vehicle_type: VehicleType` — bus, trolleybus, or tram
- `license_plate: str` — Field(min_length=1, max_length=20)
- `manufacturer: str | None` — Field(None, max_length=100)
- `model_name: str | None` — Field(None, max_length=100)
- `model_year: int | None` — Field(None, ge=1950, le=2100)
- `capacity: int | None` — Field(None, ge=1, le=500), passenger capacity
- `qualified_route_ids: str | None` — Field(None, max_length=500), comma-separated route IDs
- `notes: str | None` — Field(None, max_length=2000)

**VehicleCreate(VehicleBase):**
- Inherits all fields from VehicleBase (no extra fields needed)

**VehicleUpdate(BaseModel):**
- All fields optional with `| None` union types
- `fleet_number: str | None` — Field(None, min_length=1, max_length=20)
- `vehicle_type: VehicleType | None` — Field(None)
- `license_plate: str | None` — Field(None, min_length=1, max_length=20)
- `manufacturer: str | None` — Field(None, max_length=100)
- `model_name: str | None` — Field(None, max_length=100)
- `model_year: int | None` — Field(None, ge=1950, le=2100)
- `capacity: int | None` — Field(None, ge=1, le=500)
- `status: VehicleStatus | None` — Field(None)
- `current_driver_id: int | None` — Field(None)
- `mileage_km: int | None` — Field(None, ge=0)
- `qualified_route_ids: str | None` — Field(None, max_length=500)
- `registration_expiry: datetime.date | None` — Field(None)
- `next_maintenance_date: datetime.date | None` — Field(None)
- `notes: str | None` — Field(None, max_length=2000)
- Add `@model_validator(mode="before")` with `@classmethod` to reject empty PATCH bodies (anti-pattern rule 52)

**VehicleResponse(VehicleBase):**
- `id: int`
- `status: VehicleStatus`
- `current_driver_id: int | None`
- `mileage_km: int`
- `registration_expiry: datetime.date | None`
- `next_maintenance_date: datetime.date | None`
- `is_active: bool`
- `created_at: datetime.datetime`
- `updated_at: datetime.datetime`
- `model_config = ConfigDict(from_attributes=True)`

**MaintenanceRecordCreate(BaseModel):**
- `maintenance_type: MaintenanceType`
- `description: str` — Field(min_length=1, max_length=2000)
- `performed_date: datetime.date`
- `mileage_at_service: int | None` — Field(None, ge=0)
- `cost_eur: float | None` — Field(None, ge=0)
- `next_scheduled_date: datetime.date | None`
- `performed_by: str | None` — Field(None, max_length=200)
- `notes: str | None` — Field(None, max_length=2000)

**MaintenanceRecordResponse(MaintenanceRecordCreate):**
- `id: int`
- `vehicle_id: int`
- `created_at: datetime.datetime`
- `updated_at: datetime.datetime`
- `model_config = ConfigDict(from_attributes=True)`

Follow the pattern from `app/drivers/schemas.py` (lines 8-80).

**Per-task validation:**
- `uv run ruff format app/vehicles/schemas.py`
- `uv run ruff check --fix app/vehicles/schemas.py`
- `uv run mypy app/vehicles/schemas.py`
- `uv run pyright app/vehicles/schemas.py`

---

### Task 2: Create Vehicle Models
**File:** `app/vehicles/models.py` (create new)
**Action:** CREATE

Create SQLAlchemy models for vehicles and maintenance records:

```python
"""Vehicle management database models."""

import datetime

from sqlalchemy import Boolean, Date, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.shared.models import TimestampMixin
```

**Vehicle(Base, TimestampMixin):**
- `__tablename__ = "vehicles"`
- `id: Mapped[int]` — mapped_column(primary_key=True, index=True)
- `fleet_number: Mapped[str]` — mapped_column(String(20), unique=True, nullable=False, index=True)
- `vehicle_type: Mapped[str]` — mapped_column(String(20), nullable=False), stores "bus"/"trolleybus"/"tram"
- `license_plate: Mapped[str]` — mapped_column(String(20), nullable=False)
- `manufacturer: Mapped[str | None]` — mapped_column(String(100), nullable=True)
- `model_name: Mapped[str | None]` — mapped_column(String(100), nullable=True)
- `model_year: Mapped[int | None]` — mapped_column(Integer, nullable=True)
- `capacity: Mapped[int | None]` — mapped_column(Integer, nullable=True)
- `status: Mapped[str]` — mapped_column(String(20), nullable=False, default="active")
- `current_driver_id: Mapped[int | None]` — mapped_column(Integer, ForeignKey("drivers.id", ondelete="SET NULL"), nullable=True)
- `mileage_km: Mapped[int]` — mapped_column(Integer, nullable=False, default=0)
- `qualified_route_ids: Mapped[str | None]` — mapped_column(String(500), nullable=True)
- `registration_expiry: Mapped[datetime.date | None]` — mapped_column(Date, nullable=True)
- `next_maintenance_date: Mapped[datetime.date | None]` — mapped_column(Date, nullable=True)
- `notes: Mapped[str | None]` — mapped_column(Text, nullable=True)
- `is_active: Mapped[bool]` — mapped_column(Boolean, default=True, nullable=False)

**MaintenanceRecord(Base, TimestampMixin):**
- `__tablename__ = "maintenance_records"`
- `id: Mapped[int]` — mapped_column(primary_key=True, index=True)
- `vehicle_id: Mapped[int]` — mapped_column(Integer, ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=False, index=True)
- `maintenance_type: Mapped[str]` — mapped_column(String(20), nullable=False)
- `description: Mapped[str]` — mapped_column(Text, nullable=False)
- `performed_date: Mapped[datetime.date]` — mapped_column(Date, nullable=False)
- `mileage_at_service: Mapped[int | None]` — mapped_column(Integer, nullable=True)
- `cost_eur: Mapped[float | None]` — mapped_column(Float, nullable=True)
- `next_scheduled_date: Mapped[datetime.date | None]` — mapped_column(Date, nullable=True)
- `performed_by: Mapped[str | None]` — mapped_column(String(200), nullable=True)
- `notes: Mapped[str | None]` — mapped_column(Text, nullable=True)

Follow the pattern from `app/drivers/models.py` (lines 16-49) and `app/events/models.py` (lines 18-42) for ForeignKey.

**Per-task validation:**
- `uv run ruff format app/vehicles/models.py`
- `uv run ruff check --fix app/vehicles/models.py`
- `uv run mypy app/vehicles/models.py`
- `uv run pyright app/vehicles/models.py`

---

### Task 3: Create Vehicle Exceptions
**File:** `app/vehicles/exceptions.py` (create new)
**Action:** CREATE

Create feature-specific exception hierarchy:

```python
"""Vehicle management exceptions."""

from app.core.exceptions import AppError, DomainValidationError, NotFoundError


class VehicleError(AppError):
    """Base exception for vehicle operations."""


class VehicleNotFoundError(NotFoundError):
    """Vehicle not found (404)."""

    def __init__(self, vehicle_id: int) -> None:
        super().__init__(f"Vehicle with id {vehicle_id} not found")


class VehicleAlreadyExistsError(DomainValidationError):
    """Vehicle with this fleet number already exists (422)."""

    def __init__(self, fleet_number: str) -> None:
        super().__init__(f"Vehicle with fleet number '{fleet_number}' already exists")


class MaintenanceRecordNotFoundError(NotFoundError):
    """Maintenance record not found (404)."""

    def __init__(self, record_id: int) -> None:
        super().__init__(f"Maintenance record with id {record_id} not found")


class DriverAssignmentError(DomainValidationError):
    """Driver assignment validation error (422)."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
```

Follow the pattern from `app/drivers/exceptions.py`.

**Per-task validation:**
- `uv run ruff format app/vehicles/exceptions.py`
- `uv run ruff check --fix app/vehicles/exceptions.py`
- `uv run mypy app/vehicles/exceptions.py`

---

### Task 4: Create Vehicle Repository
**File:** `app/vehicles/repository.py` (create new)
**Action:** CREATE

Create async repository with full CRUD + search + filters:

```python
"""Vehicle management repository."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.utils import escape_like
from app.vehicles.models import MaintenanceRecord, Vehicle
from app.vehicles.schemas import MaintenanceRecordCreate, VehicleCreate, VehicleUpdate
```

**VehicleRepository:**
- `__init__(self, db: AsyncSession) -> None`

Methods (follow `app/drivers/repository.py` lines 26-195):

1. `async def get(self, vehicle_id: int) -> Vehicle | None` — select by PK
2. `async def get_by_fleet_number(self, fleet_number: str) -> Vehicle | None` — unique field lookup
3. `async def list(self, *, offset: int = 0, limit: int = 20, search: str | None = None, vehicle_type: str | None = None, status: str | None = None, active_only: bool = True) -> list[Vehicle]`
   - Search matches fleet_number, license_plate, manufacturer, model_name via ILIKE with `escape_like()`
   - Filter by vehicle_type, status, is_active
   - Order by fleet_number ASC
4. `async def count(self, *, search: str | None = None, vehicle_type: str | None = None, status: str | None = None, active_only: bool = True) -> int` — matching count for pagination
5. `async def create(self, data: VehicleCreate) -> Vehicle` — model_dump(), add, commit, refresh
6. `async def update(self, vehicle: Vehicle, data: VehicleUpdate) -> Vehicle` — exclude_unset=True pattern
7. `async def delete(self, vehicle: Vehicle) -> None` — delete, commit

**MaintenanceRecordRepository:**
- `__init__(self, db: AsyncSession) -> None`

Methods:
1. `async def get(self, record_id: int) -> MaintenanceRecord | None`
2. `async def list_by_vehicle(self, vehicle_id: int, *, offset: int = 0, limit: int = 20) -> list[MaintenanceRecord]` — ordered by performed_date DESC
3. `async def count_by_vehicle(self, vehicle_id: int) -> int`
4. `async def create(self, vehicle_id: int, data: MaintenanceRecordCreate) -> MaintenanceRecord`

Use `func.count()` for count queries (follow `app/drivers/repository.py` count pattern).
Use `escape_like()` from `app/shared/utils` for all ILIKE queries (anti-pattern rule 41).

**Per-task validation:**
- `uv run ruff format app/vehicles/repository.py`
- `uv run ruff check --fix app/vehicles/repository.py`
- `uv run mypy app/vehicles/repository.py`
- `uv run pyright app/vehicles/repository.py`

---

### Task 5: Create Vehicle Service
**File:** `app/vehicles/service.py` (create new)
**Action:** CREATE

Create service layer with business logic, validation, and structured logging:

```python
"""Vehicle management service."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.shared.schemas import PaginatedResponse, PaginationParams
from app.vehicles.exceptions import (
    DriverAssignmentError,
    MaintenanceRecordNotFoundError,
    VehicleAlreadyExistsError,
    VehicleNotFoundError,
)
from app.vehicles.models import MaintenanceRecord, Vehicle
from app.vehicles.repository import MaintenanceRecordRepository, VehicleRepository
from app.vehicles.schemas import (
    MaintenanceRecordCreate,
    MaintenanceRecordResponse,
    VehicleCreate,
    VehicleResponse,
    VehicleUpdate,
)

logger = get_logger(__name__)
```

**VehicleService:**
- `__init__(self, db: AsyncSession) -> None` — creates `self.vehicle_repo = VehicleRepository(db)` and `self.maintenance_repo = MaintenanceRecordRepository(db)`

Methods (follow `app/drivers/service.py` lines 32-200):

1. **get_vehicle(vehicle_id: int) -> VehicleResponse:**
   - Log: `vehicles.fetch_started`
   - Fetch from repo, raise `VehicleNotFoundError` if None
   - Log: `vehicles.fetch_completed`
   - Return `VehicleResponse.model_validate(vehicle)`

2. **list_vehicles(pagination, search, vehicle_type, status, active_only) -> PaginatedResponse[VehicleResponse]:**
   - Log: `vehicles.list_started` with filter params
   - Call repo.list() and repo.count() with matching filters
   - Build `PaginatedResponse[VehicleResponse]`
   - Log: `vehicles.list_completed` with total count

3. **create_vehicle(data: VehicleCreate) -> VehicleResponse:**
   - Log: `vehicles.create_started`
   - Check duplicate fleet_number via `get_by_fleet_number()` → raise `VehicleAlreadyExistsError`
   - Call repo.create()
   - Log: `vehicles.create_completed` with vehicle_id
   - Return validated response

4. **update_vehicle(vehicle_id: int, data: VehicleUpdate) -> VehicleResponse:**
   - Log: `vehicles.update_started`
   - Fetch vehicle, raise NotFound if None
   - If fleet_number changed, check for duplicates
   - If current_driver_id is being set, validate driver exists (read from drivers repo) — import `DriverRepository` from `app.drivers.repository` and instantiate with `self.db`
   - Call repo.update()
   - Log: `vehicles.update_completed`
   - Return validated response

5. **delete_vehicle(vehicle_id: int) -> None:**
   - Log: `vehicles.delete_started`
   - Fetch vehicle, raise NotFound if None
   - Call repo.delete()
   - Log: `vehicles.delete_completed`

6. **assign_driver(vehicle_id: int, driver_id: int | None) -> VehicleResponse:**
   - Log: `vehicles.driver_assign_started`
   - Fetch vehicle, raise NotFound if None
   - If driver_id is not None: validate driver exists via DriverRepository, raise `DriverAssignmentError` if not found
   - If driver_id is not None: check no other active vehicle has this driver assigned (query repo for vehicles with current_driver_id == driver_id, exclude current vehicle)
   - Update vehicle.current_driver_id, commit
   - Log: `vehicles.driver_assign_completed`
   - Return validated response

7. **add_maintenance_record(vehicle_id: int, data: MaintenanceRecordCreate) -> MaintenanceRecordResponse:**
   - Log: `vehicles.maintenance_create_started`
   - Fetch vehicle, raise NotFound if None
   - Call maintenance_repo.create()
   - If data.next_scheduled_date: update vehicle.next_maintenance_date
   - If data.mileage_at_service and data.mileage_at_service > vehicle.mileage_km: update vehicle.mileage_km
   - Log: `vehicles.maintenance_create_completed`
   - Return validated response

8. **get_maintenance_history(vehicle_id: int, pagination) -> PaginatedResponse[MaintenanceRecordResponse]:**
   - Fetch vehicle, raise NotFound if None
   - Call maintenance_repo.list_by_vehicle() and count_by_vehicle()
   - Return paginated response

For the driver validation in `update_vehicle` and `assign_driver`, import and instantiate `DriverRepository`:
```python
from app.drivers.repository import DriverRepository
# Inside method:
driver_repo = DriverRepository(self.db)
driver = await driver_repo.get(driver_id)
if driver is None:
    raise DriverAssignmentError(f"Driver with id {driver_id} not found")
```

Store `self.db` reference in `__init__` for cross-feature repository access.

**Per-task validation:**
- `uv run ruff format app/vehicles/service.py`
- `uv run ruff check --fix app/vehicles/service.py`
- `uv run mypy app/vehicles/service.py`
- `uv run pyright app/vehicles/service.py`

---

### Task 6: Create Vehicle Routes
**File:** `app/vehicles/routes.py` (create new)
**Action:** CREATE

Create FastAPI router with 8 endpoints, RBAC enforcement, and rate limiting:

```python
"""Vehicle management API routes."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, require_role
from app.auth.models import User
from app.core.database import get_db
from app.core.rate_limit import limiter
from app.shared.schemas import PaginatedResponse, PaginationParams
from app.vehicles.schemas import (
    MaintenanceRecordCreate,
    MaintenanceRecordResponse,
    VehicleCreate,
    VehicleResponse,
    VehicleUpdate,
)
from app.vehicles.service import VehicleService

router = APIRouter(prefix="/api/v1/vehicles", tags=["vehicles"])


def get_service(db: AsyncSession = Depends(get_db)) -> VehicleService:  # noqa: B008
    """Create vehicle service instance."""
    return VehicleService(db)
```

**Endpoints (8 total):**

1. **GET /** → `PaginatedResponse[VehicleResponse]`
   - Rate limit: 30/minute
   - Auth: `get_current_user` (all roles can read)
   - Query params: pagination (page, page_size), search (str | None), vehicle_type (str | None), status (str | None), active_only (bool = True)
   - Pattern: follow `app/drivers/routes.py` lines 28-44

2. **GET /{vehicle_id}** → `VehicleResponse`
   - Rate limit: 30/minute
   - Auth: `get_current_user`

3. **POST /** → `VehicleResponse` (status_code=201)
   - Rate limit: 10/minute
   - Auth: `require_role("admin", "editor")`
   - Body: `VehicleCreate`

4. **PATCH /{vehicle_id}** → `VehicleResponse`
   - Rate limit: 10/minute
   - Auth: `require_role("admin", "editor")`
   - Body: `VehicleUpdate`

5. **DELETE /{vehicle_id}** → None (status_code=204)
   - Rate limit: 10/minute
   - Auth: `require_role("admin")`

6. **POST /{vehicle_id}/assign-driver** → `VehicleResponse`
   - Rate limit: 10/minute
   - Auth: `require_role("admin", "dispatcher")`
   - Query param: `driver_id: int | None = Query(None)` — pass None to unassign. Use `# noqa: B008` on Query(None).

7. **POST /{vehicle_id}/maintenance** → `MaintenanceRecordResponse` (status_code=201)
   - Rate limit: 10/minute
   - Auth: `require_role("admin", "editor")`
   - Body: `MaintenanceRecordCreate`

8. **GET /{vehicle_id}/maintenance** → `PaginatedResponse[MaintenanceRecordResponse]`
   - Rate limit: 30/minute
   - Auth: `get_current_user`
   - Query params: pagination

Every endpoint MUST include auth dependency — `TestAllEndpointsRequireAuth` auto-discovers routes and fails CI otherwise.

Follow the exact pattern from `app/drivers/routes.py` (lines 20-97) for rate limiter decorator syntax:
```python
@router.get("/")
@limiter.limit("30/minute")
async def list_vehicles(
    request: Request,
    pagination: PaginationParams = Depends(),  # noqa: B008
    search: str | None = Query(None),  # noqa: B008
    ...
    service: VehicleService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(get_current_user),  # noqa: B008
) -> PaginatedResponse[VehicleResponse]:
```

Import `Request` from `starlette.requests` (required by slowapi limiter).

**Per-task validation:**
- `uv run ruff format app/vehicles/routes.py`
- `uv run ruff check --fix app/vehicles/routes.py`
- `uv run mypy app/vehicles/routes.py`
- `uv run pyright app/vehicles/routes.py`

---

### Task 7: Create `__init__.py`
**File:** `app/vehicles/__init__.py` (create new)
**Action:** CREATE

Create empty init file to make vehicles a proper Python package:

```python
"""Vehicle management feature."""
```

**Per-task validation:**
- `uv run ruff format app/vehicles/__init__.py`
- `uv run ruff check --fix app/vehicles/__init__.py`

---

### Task 8: Create Test Conftest
**File:** `app/vehicles/tests/__init__.py` (create new)
**Action:** CREATE

Empty init for test package:
```python
"""Vehicle management tests."""
```

Then create:

**File:** `app/vehicles/tests/conftest.py` (create new)
**Action:** CREATE

Create test fixtures and factory functions:

```python
"""Vehicle management test fixtures."""

import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.shared.models import utcnow
from app.vehicles.schemas import VehicleResponse, MaintenanceRecordResponse
```

**Factory Functions:**

1. `make_vehicle(**overrides: object) -> MagicMock` — returns MagicMock with sensible defaults:
   - id=1, fleet_number="4521", vehicle_type="bus", license_plate="AB-1234"
   - manufacturer="Solaris", model_name="Urbino 12", model_year=2020, capacity=90
   - status="active", current_driver_id=None, mileage_km=50000
   - qualified_route_ids="1,3,22", registration_expiry=date(2027, 6, 15)
   - next_maintenance_date=date(2026, 4, 1), notes=None, is_active=True
   - created_at=utcnow(), updated_at=utcnow()
   - Apply overrides via `for key, value in overrides.items(): setattr(mock, key, value)`

2. `make_maintenance_record(**overrides: object) -> MagicMock` — returns MagicMock with defaults:
   - id=1, vehicle_id=1, maintenance_type="scheduled", description="Regular service"
   - performed_date=date.today(), mileage_at_service=50000, cost_eur=350.0
   - next_scheduled_date=date + 90 days, performed_by="Fleet Workshop", notes=None
   - created_at=utcnow(), updated_at=utcnow()

Follow pattern from `app/drivers/tests/conftest.py` (lines 12-76).

**Per-task validation:**
- `uv run ruff format app/vehicles/tests/conftest.py`
- `uv run ruff check --fix app/vehicles/tests/conftest.py`

---

### Task 9: Create Service Tests
**File:** `app/vehicles/tests/test_service.py` (create new)
**Action:** CREATE

Create unit tests for the VehicleService:

```python
"""Vehicle service unit tests."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.vehicles.exceptions import (
    DriverAssignmentError,
    VehicleAlreadyExistsError,
    VehicleNotFoundError,
)
from app.vehicles.schemas import VehicleCreate, VehicleUpdate
from app.vehicles.service import VehicleService

from .conftest import make_vehicle
```

**Test cases (minimum 12):**

1. `test_get_vehicle_success` — mock repo.get returns vehicle, assert VehicleResponse
2. `test_get_vehicle_not_found` — mock repo.get returns None, assert VehicleNotFoundError
3. `test_list_vehicles_with_pagination` — mock repo.list + count, assert PaginatedResponse fields
4. `test_list_vehicles_with_search` — verify search param passed through
5. `test_create_vehicle_success` — mock no duplicate, repo.create returns vehicle
6. `test_create_vehicle_duplicate_fleet_number` — mock get_by_fleet_number returns existing, assert VehicleAlreadyExistsError
7. `test_update_vehicle_success` — mock repo.get + update
8. `test_update_vehicle_not_found` — assert VehicleNotFoundError
9. `test_update_vehicle_duplicate_fleet_number` — change fleet_number to existing one
10. `test_delete_vehicle_success` — mock repo.get + delete
11. `test_delete_vehicle_not_found` — assert VehicleNotFoundError
12. `test_assign_driver_success` — mock driver exists, no conflict
13. `test_assign_driver_not_found` — driver doesn't exist, assert DriverAssignmentError
14. `test_assign_driver_unassign` — driver_id=None clears assignment
15. `test_add_maintenance_record_success` — creates record, updates vehicle mileage
16. `test_add_maintenance_record_vehicle_not_found` — assert VehicleNotFoundError

Use `AsyncMock` for all repository methods. Patch `VehicleRepository` and `MaintenanceRecordRepository` at the module level. Use `@pytest.fixture` with autouse to set up mock service.

Pattern: Follow `app/drivers/tests/test_service.py` for mock setup and assertion patterns.

**Per-task validation:**
- `uv run ruff format app/vehicles/tests/test_service.py`
- `uv run ruff check --fix app/vehicles/tests/test_service.py`
- `uv run pytest app/vehicles/tests/test_service.py -v`

---

### Task 10: Create Route Tests
**File:** `app/vehicles/tests/test_routes.py` (create new)
**Action:** CREATE

Create unit tests for the vehicle API routes:

```python
"""Vehicle route unit tests."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.vehicles.schemas import VehicleResponse, MaintenanceRecordResponse

from .conftest import make_vehicle, make_maintenance_record
```

**Setup pattern (follow `app/drivers/tests/test_routes.py`):**
- `mock_user` fixture returning MagicMock(id=1, role="admin", email="test@test.com", is_active=True)
- `override_deps` fixture (autouse) that overrides `get_current_user` to return mock_user and `get_db` to return AsyncMock
- Teardown: clear `app.dependency_overrides` (anti-pattern rule 56 — save/restore pattern)
- `client` fixture returning `TestClient(app)`

**Test cases (minimum 14):**

1. `test_list_vehicles_200` — GET /api/v1/vehicles/ returns 200
2. `test_list_vehicles_with_filters` — search, vehicle_type, status params
3. `test_get_vehicle_200` — GET /api/v1/vehicles/1 returns 200
4. `test_get_vehicle_404` — service raises VehicleNotFoundError → 404
5. `test_create_vehicle_201` — POST with valid body → 201
6. `test_create_vehicle_422_duplicate` — VehicleAlreadyExistsError → 422
7. `test_update_vehicle_200` — PATCH with valid body → 200
8. `test_update_vehicle_404` — VehicleNotFoundError → 404
9. `test_delete_vehicle_204` — DELETE → 204
10. `test_delete_vehicle_404` — VehicleNotFoundError → 404
11. `test_assign_driver_200` — POST /api/v1/vehicles/1/assign-driver?driver_id=1 → 200
12. `test_assign_driver_unassign` — POST without driver_id → 200
13. `test_create_maintenance_201` — POST /api/v1/vehicles/1/maintenance → 201
14. `test_get_maintenance_history_200` — GET /api/v1/vehicles/1/maintenance → 200

Patch `VehicleService` at `app.vehicles.routes.VehicleService` or use dependency override for `get_service`.

**Per-task validation:**
- `uv run ruff format app/vehicles/tests/test_routes.py`
- `uv run ruff check --fix app/vehicles/tests/test_routes.py`
- `uv run pytest app/vehicles/tests/test_routes.py -v`

---

### Task 11: Register Router
**File:** `app/main.py` (modify existing)
**Action:** UPDATE

Add at the import section (near existing router imports):
```python
from app.vehicles.routes import router as vehicles_router
```

Add at the router registration section (after `app.include_router(events_router)`):
```python
app.include_router(vehicles_router)
```

**Per-task validation:**
- `uv run ruff format app/main.py`
- `uv run ruff check --fix app/main.py`
- `uv run mypy app/main.py`

---

### Task 12: Create Database Migration
**Action:** CREATE migration

**If database is running:**
```bash
uv run alembic revision --autogenerate -m "add vehicles and maintenance records tables"
uv run alembic upgrade head
```

**If database is NOT running (manual fallback):**
Create migration at `alembic/versions/{hash}_add_vehicles_and_maintenance_records_tables.py`:

**vehicles table:**
| Column | Type | Constraints |
|--------|------|-------------|
| id | Integer | PK, autoincrement, index |
| fleet_number | String(20) | NOT NULL, UNIQUE, index |
| vehicle_type | String(20) | NOT NULL |
| license_plate | String(20) | NOT NULL |
| manufacturer | String(100) | nullable |
| model_name | String(100) | nullable |
| model_year | Integer | nullable |
| capacity | Integer | nullable |
| status | String(20) | NOT NULL, default="active" |
| current_driver_id | Integer | FK→drivers.id ON DELETE SET NULL, nullable |
| mileage_km | Integer | NOT NULL, default=0 |
| qualified_route_ids | String(500) | nullable |
| registration_expiry | Date | nullable |
| next_maintenance_date | Date | nullable |
| notes | Text | nullable |
| is_active | Boolean | NOT NULL, default=True |
| created_at | DateTime(tz) | NOT NULL |
| updated_at | DateTime(tz) | NOT NULL |

**maintenance_records table:**
| Column | Type | Constraints |
|--------|------|-------------|
| id | Integer | PK, autoincrement, index |
| vehicle_id | Integer | FK→vehicles.id ON DELETE CASCADE, NOT NULL, index |
| maintenance_type | String(20) | NOT NULL |
| description | Text | NOT NULL |
| performed_date | Date | NOT NULL |
| mileage_at_service | Integer | nullable |
| cost_eur | Float | nullable |
| next_scheduled_date | Date | nullable |
| performed_by | String(200) | nullable |
| notes | Text | nullable |
| created_at | DateTime(tz) | NOT NULL |
| updated_at | DateTime(tz) | NOT NULL |

Down revision: chain from the latest existing migration.

**Per-task validation:**
- `uv run ruff format alembic/versions/*.py`
- `uv run ruff check --fix alembic/versions/*.py`

---

## Migration

**Prefer autogenerate when database is running:**
```bash
uv run alembic revision --autogenerate -m "add vehicles and maintenance records tables"
uv run alembic upgrade head
```

**When database may not be running:** Manual migration is an acceptable fallback. Column types, nullable flags, and foreign keys specified in Task 12 above.

## Logging Events

- `vehicles.fetch_started` — when fetching a single vehicle by ID
- `vehicles.fetch_completed` — vehicle successfully retrieved
- `vehicles.list_started` — when listing vehicles with filter params
- `vehicles.list_completed` — list completed with total count
- `vehicles.create_started` — when creating a new vehicle
- `vehicles.create_completed` — vehicle created with vehicle_id
- `vehicles.create_failed` — duplicate fleet number or validation error
- `vehicles.update_started` — when updating vehicle
- `vehicles.update_completed` — vehicle updated
- `vehicles.delete_started` — when deleting vehicle
- `vehicles.delete_completed` — vehicle deleted
- `vehicles.driver_assign_started` — when assigning/unassigning driver
- `vehicles.driver_assign_completed` — driver assignment updated
- `vehicles.driver_assign_failed` — driver not found or already assigned
- `vehicles.maintenance_create_started` — when adding maintenance record
- `vehicles.maintenance_create_completed` — record created
- `vehicles.maintenance_list_started` — when listing maintenance history

## Testing Strategy

### Unit Tests
**Location:** `app/vehicles/tests/test_service.py`
- VehicleService CRUD operations (get, list, create, update, delete)
- Driver assignment validation (success, not found, already assigned, unassign)
- Maintenance record creation with mileage/date side effects
- Duplicate fleet number detection on create and update

**Location:** `app/vehicles/tests/test_routes.py`
- All 8 endpoints return correct status codes
- Error responses map correctly (404, 422)
- Pagination parameters passed through
- RBAC enforcement (admin-only delete)

### Integration Tests
**Location:** `app/vehicles/tests/test_service.py`
**Mark with:** `@pytest.mark.integration`
- Full CRUD cycle with real database (create → read → update → delete)
- Driver assignment with real driver record
- Maintenance record cascade delete when vehicle deleted

### Edge Cases
- Create vehicle with fleet_number that already exists → 422
- Update vehicle fleet_number to one that already exists → 422
- Delete vehicle with maintenance records → cascade delete records
- Assign driver already assigned to another vehicle → 422
- Assign non-existent driver → 422
- Unassign driver (driver_id=None) → clears assignment
- Empty PATCH body → 422 (model_validator rejects)
- Search with special characters (%, _) → properly escaped
- List with all filters combined → correct query composition

## Acceptance Criteria

This feature is complete when:
- [ ] 8 REST endpoints operational under `/api/v1/vehicles/`
- [ ] Vehicle CRUD with duplicate fleet_number prevention
- [ ] Driver assignment with conflict detection (no double-assignment)
- [ ] Maintenance record sub-resource with vehicle-linked history
- [ ] Maintenance mileage/date side effects update parent vehicle
- [ ] All type checkers pass (mypy + pyright) with 0 errors
- [ ] All tests pass (minimum 30 tests across service + routes)
- [ ] Structured logging follows `vehicles.component.action_state` pattern
- [ ] No type suppressions added (no `# type: ignore` in production code)
- [ ] Router registered in `app/main.py`
- [ ] No regressions in existing tests (753+ existing tests still pass)
- [ ] RBAC enforced on all endpoints (TestAllEndpointsRequireAuth passes)

## Completion Checklist

Before marking this plan as fully executed:
- [ ] All 12 tasks completed in order
- [ ] Per-task validations passed
- [ ] Full validation pyramid passed (Levels 1-5)
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
uv run pytest app/vehicles/tests/ -v
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

- **Shared utilities used:** `TimestampMixin`, `utcnow()`, `PaginationParams`, `PaginatedResponse`, `escape_like()`, `get_db()`, `get_logger()`, `AppError`, `NotFoundError`, `DomainValidationError`
- **Core modules used:** `app.core.database` (Base, get_db), `app.core.exceptions`, `app.core.logging`, `app.core.rate_limit` (limiter), `app.auth.dependencies` (get_current_user, require_role)
- **Cross-feature reads:** `app.drivers.repository.DriverRepository` (for driver assignment validation)
- **New dependencies:** None — all libraries already in pyproject.toml
- **New env vars:** None

## Known Pitfalls

The executing agent MUST follow all 59 Python anti-pattern rules loaded via `@_shared/python-anti-patterns.md`. Key rules for this feature:

- **Rule 5:** No unused imports or variables — only import what's used
- **Rule 11:** Schema field additions break ALL consumers — grep for schema names if modifying
- **Rule 18:** ARG001 applies to ALL unused params — use `_ = param` or `_current_user: User`
- **Rule 39:** `from datetime import date` shadows field names — use `import datetime` and `datetime.date`
- **Rule 40:** FastAPI `Query(None)` needs `# noqa: B008`
- **Rule 41:** ILIKE search params must use `escape_like()`
- **Rule 52:** Empty PATCH bodies must be rejected via `@model_validator(mode="before")`
- **Rule 54:** Constrained string fields must use `Literal[...]`
- **Rule 55:** HTTPBearer(auto_error=False) — already handled by existing auth dependencies
- **Rule 56:** `app.dependency_overrides` leaks between tests — save/restore in fixtures

## Notes

- The `fleet_number` field on vehicles intentionally matches the `vehicle_id` field in GTFS-RT `VehiclePosition` data. This enables linking real-time vehicle positions to their fleet metadata in future dashboard enhancements.
- The `current_driver_id` FK uses `ondelete="SET NULL"` so deleting a driver doesn't cascade-delete the vehicle — it just clears the assignment.
- The `MaintenanceRecord` FK uses `ondelete="CASCADE"` because maintenance records are meaningless without their parent vehicle.
- Route qualification (`qualified_route_ids` CSV) follows the same pattern as drivers. When a third feature needs this pattern, extract to a shared utility or proper join table.
- Future enhancements (not in this plan): vehicle-route assignment history, fuel consumption tracking, insurance records, GPS device pairing.

## Pre-Implementation Checklist

The executing agent MUST verify before writing any code:
- [ ] Read all files listed in "Relevant Files" section
- [ ] Understood the solution approach and why alternatives were rejected
- [ ] Clear on task execution order (schemas → models → exceptions → repository → service → routes → tests → register)
- [ ] Validation commands are executable in this environment
