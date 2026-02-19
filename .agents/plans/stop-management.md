# Plan: Stop Management — CRUD with Geolocation & Proximity Search

## Feature Metadata
**Feature Type**: New Capability
**Estimated Complexity**: Medium
**Primary Systems Affected**: `app/stops/` (new), `app/main.py`, `alembic/`, `pyproject.toml`

## Feature Description

Stop management is the first database-backed CRUD feature in VTV. It provides a REST API for creating, reading, updating, deleting, and searching transit stops with geographic coordinates. This is the CMS-facing data layer — administrators and editors manage stop records that correspond to GTFS `stops.txt` entries.

Stops are stored in PostgreSQL with plain `Float` columns for latitude/longitude (no PostGIS extension required). Proximity search uses the Haversine formula in Python, consistent with the existing agent tool `search_stops` in `app/core/agents/tools/transit/search_stops.py`. Each stop has a `gtfs_stop_id` field linking it to the GTFS feed, plus operator-managed metadata (description, wheelchair accessibility, location type, parent station reference, active status).

This feature follows VTV's vertical slice architecture: schemas, models, repository, service, exceptions, routes, and tests — all self-contained under `app/stops/`.

## User Story

As a transit administrator
I want to manage stop records (create, view, edit, delete) and search stops by name or proximity
So that I can maintain accurate stop data for route planning and GTFS export

## Solution Approach

We implement a standard VSA feature slice using plain float columns for coordinates and in-memory Haversine for proximity search. This is deliberately simple — no PostGIS dependency, no new database extensions, no GeoAlchemy2.

**Approach Decision:**
We chose plain float columns + Haversine because:
- Consistent with existing codebase (agent tool `search_stops` already does this)
- No new dependencies or PostgreSQL extensions required
- Riga has ~2000 stops — in-memory distance calculation is fast enough
- PostGIS can be added later if spatial indexing becomes necessary

**Alternatives Considered:**
- GeoAlchemy2 + PostGIS `ST_DWithin`: Rejected because it adds a dependency, requires PostGIS extension in PostgreSQL, and is overkill for ~2000 stops. Database-level spatial queries would be beneficial at 50,000+ records.
- SQL-based distance calculation (`func.sqrt(func.pow(...))`): Rejected because Pythagorean approximation is inaccurate at high latitudes (Riga is at 56.9°N) and the Haversine function already exists in the codebase.

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, logging patterns, type checking requirements
- `reference/vsa-patterns.md` — Repository, service, routes, model, schema patterns with exact code templates

### Similar Features (Examples to Follow)
- `app/transit/schemas.py` — Pydantic schema pattern (ConfigDict, Field usage)
- `app/transit/service.py` — Service with singleton pattern, structured logging, close function
- `app/transit/routes.py` — FastAPI router with rate limiting, pyright directives, slowapi integration
- `app/transit/tests/test_service.py` — Test patterns (mocking, factory helpers, async tests)
- `app/core/agents/tools/transit/search_stops.py` (lines 33-53) — Haversine distance function to reuse

### Shared Utilities to Use
- `app/shared/schemas.py` — `PaginationParams`, `PaginatedResponse[T]`, `ErrorResponse`
- `app/shared/models.py` — `TimestampMixin`, `utcnow()`
- `app/core/database.py` — `Base`, `get_db()`, `AsyncSessionLocal`
- `app/core/exceptions.py` — `NotFoundError`, `ValidationError`, `DatabaseError`
- `app/core/logging.py` — `get_logger(__name__)`

### Files to Modify
- `app/main.py` — Register `stops_router`
- `alembic/env.py` — Import stop model for autogenerate discovery
- `pyproject.toml` — Add per-file-ignores for `app/stops/routes.py`

## Implementation Plan

### Phase 1: Foundation (Tasks 1-4)
Define data structures: schemas, model, exceptions. These have no runtime dependencies beyond shared utilities.

### Phase 2: Core Implementation (Tasks 5-8)
Build repository (database CRUD), service (business logic + logging), and routes (HTTP endpoints). Wire into the application.

### Phase 3: Testing & Validation (Tasks 9-12)
Write unit tests for repository, service, and routes. Run full validation pyramid.

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.

---

### Task 1: Create package init
**File:** `app/stops/__init__.py` (create new)
**Action:** CREATE

Create an empty `__init__.py` to make `app/stops/` a Python package.

```python
"""Stop management feature — CRUD with geolocation and proximity search."""
```

**Per-task validation:**
- `uv run ruff format app/stops/__init__.py`
- `uv run ruff check --fix app/stops/__init__.py`

---

### Task 2: Create schemas
**File:** `app/stops/schemas.py` (create new)
**Action:** CREATE

Define Pydantic request/response schemas following the pattern in `reference/vsa-patterns.md` (Schema Pattern section).

Create these classes:

**`StopBase(BaseModel)`** — shared fields:
- `stop_name: str` — `Field(..., min_length=1, max_length=200, description="Human-readable stop name (Latvian)")`
- `gtfs_stop_id: str` — `Field(..., min_length=1, max_length=50, description="GTFS stop_id identifier")`
- `stop_lat: float | None = None` — `Field(None, ge=-90, le=90, description="WGS84 latitude")`
- `stop_lon: float | None = None` — `Field(None, ge=-180, le=180, description="WGS84 longitude")`
- `stop_desc: str | None = None` — `Field(None, max_length=500, description="Stop description")`
- `location_type: int = Field(default=0, ge=0, le=4, description="GTFS location_type (0=stop, 1=station)")`
- `parent_station_id: int | None = None` — FK reference to parent station (nullable)
- `wheelchair_boarding: int = Field(default=0, ge=0, le=2, description="GTFS wheelchair_boarding")`

**`StopCreate(StopBase)`** — for POST requests. No additional fields.

**`StopUpdate(BaseModel)`** — for PATCH requests. ALL fields optional (use `None` defaults):
- Same fields as `StopBase` but all `Optional` with `None` defaults
- `is_active: bool | None = None`

**`StopResponse(StopBase)`** — for GET responses:
- `id: int`
- `is_active: bool`
- `created_at: datetime`
- `updated_at: datetime`
- `model_config = ConfigDict(from_attributes=True)`

**`StopNearbyParams(BaseModel)`** — query params for proximity search:
- `latitude: float` — `Field(..., ge=-90, le=90)`
- `longitude: float` — `Field(..., ge=-180, le=180)`
- `radius_meters: int = Field(default=500, ge=1, le=5000, description="Search radius in meters")`

**Per-task validation:**
- `uv run ruff format app/stops/schemas.py`
- `uv run ruff check --fix app/stops/schemas.py`
- `uv run mypy app/stops/schemas.py`
- `uv run pyright app/stops/schemas.py`

---

### Task 3: Create database model
**File:** `app/stops/models.py` (create new)
**Action:** CREATE

Define the `Stop` SQLAlchemy model following the pattern in `reference/vsa-patterns.md` (Model Pattern section). Inherit from `Base` and `TimestampMixin`.

```python
from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.shared.models import TimestampMixin
```

**`Stop(Base, TimestampMixin)`** with `__tablename__ = "stops"`:
- `id: Mapped[int]` — `mapped_column(primary_key=True, index=True)`
- `gtfs_stop_id: Mapped[str]` — `mapped_column(String(50), unique=True, nullable=False, index=True)`
- `stop_name: Mapped[str]` — `mapped_column(String(200), nullable=False, index=True)`
- `stop_lat: Mapped[float | None]` — `mapped_column(Float, nullable=True)`
- `stop_lon: Mapped[float | None]` — `mapped_column(Float, nullable=True)`
- `stop_desc: Mapped[str | None]` — `mapped_column(Text, nullable=True)`
- `location_type: Mapped[int]` — `mapped_column(Integer, default=0, nullable=False)`
- `parent_station_id: Mapped[int | None]` — `mapped_column(Integer, ForeignKey("stops.id"), nullable=True)`
- `wheelchair_boarding: Mapped[int]` — `mapped_column(Integer, default=0, nullable=False)`
- `is_active: Mapped[bool]` — `mapped_column(Boolean, default=True, nullable=False)`

Include a Google-style class docstring explaining the model and its GTFS alignment.

**Per-task validation:**
- `uv run ruff format app/stops/models.py`
- `uv run ruff check --fix app/stops/models.py`
- `uv run mypy app/stops/models.py`
- `uv run pyright app/stops/models.py`

---

### Task 4: Create exceptions
**File:** `app/stops/exceptions.py` (create new)
**Action:** CREATE

Define feature-specific exceptions following `reference/vsa-patterns.md` (Feature Exceptions Pattern section) and `app/core/exceptions.py`.

```python
from app.core.exceptions import DatabaseError, NotFoundError, ValidationError


class StopError(DatabaseError):
    """Base exception for stop-related errors."""
    pass


class StopNotFoundError(NotFoundError):
    """Raised when a stop is not found by ID."""
    pass


class StopAlreadyExistsError(ValidationError):
    """Raised when creating a stop with a duplicate gtfs_stop_id."""
    pass
```

**Per-task validation:**
- `uv run ruff format app/stops/exceptions.py`
- `uv run ruff check --fix app/stops/exceptions.py`
- `uv run mypy app/stops/exceptions.py`
- `uv run pyright app/stops/exceptions.py`

---

### Task 5: Create repository
**File:** `app/stops/repository.py` (create new)
**Action:** CREATE

Implement `StopRepository` following `reference/vsa-patterns.md` (Async Repository Pattern section).

```python
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
```

**`StopRepository`** class:
- `__init__(self, db: AsyncSession) -> None` — store `self.db`
- `async def get(self, stop_id: int) -> Stop | None` — `select(Stop).where(Stop.id == stop_id)`, use `scalar_one_or_none()`
- `async def get_by_gtfs_id(self, gtfs_stop_id: str) -> Stop | None` — lookup by GTFS ID
- `async def list(self, *, offset: int = 0, limit: int = 100, active_only: bool = True, search: str | None = None) -> list[Stop]`:
  - Build query with optional `Stop.is_active.is_(True)` filter
  - If `search` is provided, add case-insensitive `Stop.stop_name.ilike(f"%{search}%")` filter
  - Apply `.offset(offset).limit(limit)` and order by `Stop.stop_name`
  - Return `list(result.scalars().all())`
- `async def count(self, *, active_only: bool = True, search: str | None = None) -> int`:
  - Same filters as `list` but use `select(func.count()).select_from(Stop)`
  - Return `result.scalar_one()`
- `async def create(self, data: StopCreate) -> Stop`:
  - `stop = Stop(**data.model_dump())`
  - `self.db.add(stop)`, `await self.db.commit()`, `await self.db.refresh(stop)`
  - Return `stop`
- `async def update(self, stop: Stop, data: StopUpdate) -> Stop`:
  - `for field, value in data.model_dump(exclude_unset=True).items(): setattr(stop, field, value)`
  - `await self.db.commit()`, `await self.db.refresh(stop)`
  - Return `stop`
- `async def delete(self, stop: Stop) -> None`:
  - `await self.db.delete(stop)`, `await self.db.commit()`

Import `Stop` from `app.stops.models` and `StopCreate, StopUpdate` from `app.stops.schemas`.

**Per-task validation:**
- `uv run ruff format app/stops/repository.py`
- `uv run ruff check --fix app/stops/repository.py`
- `uv run mypy app/stops/repository.py`
- `uv run pyright app/stops/repository.py`

---

### Task 6: Create service
**File:** `app/stops/service.py` (create new)
**Action:** CREATE

Implement `StopService` following `reference/vsa-patterns.md` (Async Service Pattern section).

```python
import math

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.stops.exceptions import StopAlreadyExistsError, StopNotFoundError
from app.stops.models import Stop
from app.stops.repository import StopRepository
from app.stops.schemas import (
    StopCreate,
    StopNearbyParams,
    StopResponse,
    StopUpdate,
)
from app.shared.schemas import PaginatedResponse, PaginationParams

logger = get_logger(__name__)
```

**Constants** at module level:
- `_EARTH_RADIUS_METERS = 6_371_000`

**`_haversine_distance(lat1, lon1, lat2, lon2) -> float`** — Copy the Haversine function from `app/core/agents/tools/transit/search_stops.py` (lines 33-53). This is the second use, so add `# NOTE: duplicated from app/core/agents/tools/transit/search_stops.py` per the three-feature rule.

**`StopService`** class:
- `__init__(self, db: AsyncSession) -> None` — create `self.repository = StopRepository(db)` and store `self.db = db`
- `async def get_stop(self, stop_id: int) -> StopResponse`:
  - Log `stops.fetch_started` with `stop_id`
  - Call `self.repository.get(stop_id)`
  - If `None`, log `stops.fetch_failed` with reason `not_found`, raise `StopNotFoundError`
  - Return `StopResponse.model_validate(stop)`
- `async def list_stops(self, pagination: PaginationParams, *, search: str | None = None, active_only: bool = True) -> PaginatedResponse[StopResponse]`:
  - Log `stops.list_started` with page, page_size, search, active_only
  - Call `self.repository.list(offset=pagination.offset, limit=pagination.page_size, active_only=active_only, search=search)`
  - Call `self.repository.count(active_only=active_only, search=search)` for total
  - Map items through `StopResponse.model_validate`
  - Log `stops.list_completed` with result count and total
  - Return `PaginatedResponse[StopResponse](items=items, total=total, page=pagination.page, page_size=pagination.page_size)`
- `async def create_stop(self, data: StopCreate) -> StopResponse`:
  - Log `stops.create_started` with `gtfs_stop_id`
  - Check for duplicate: `self.repository.get_by_gtfs_id(data.gtfs_stop_id)`
  - If exists, log and raise `StopAlreadyExistsError`
  - Call `self.repository.create(data)`
  - Log `stops.create_completed` with `stop_id` and `gtfs_stop_id`
  - Return `StopResponse.model_validate(stop)`
- `async def update_stop(self, stop_id: int, data: StopUpdate) -> StopResponse`:
  - Log `stops.update_started`
  - Get stop or raise `StopNotFoundError`
  - If `data.model_dump(exclude_unset=True)` has `gtfs_stop_id`, check for duplicate (excluding current stop)
  - Call `self.repository.update(stop, data)`
  - Log `stops.update_completed`
  - Return `StopResponse.model_validate(stop)`
- `async def delete_stop(self, stop_id: int) -> None`:
  - Log `stops.delete_started`
  - Get stop or raise `StopNotFoundError`
  - Call `self.repository.delete(stop)`
  - Log `stops.delete_completed`
- `async def search_nearby(self, params: StopNearbyParams, limit: int = 20) -> list[StopResponse]`:
  - Log `stops.nearby_started` with lat, lon, radius
  - Fetch ALL active stops from repository (no pagination — filter in Python): `self.repository.list(offset=0, limit=10000, active_only=True)`
  - Filter by Haversine distance <= `params.radius_meters`, collecting `(distance, stop)` pairs
  - Sort by distance ascending, take first `limit` results
  - Log `stops.nearby_completed` with result count
  - Return list of `StopResponse.model_validate(stop)` (note: `StopResponse` does not include `distance_meters` — this is a CMS API, not the agent API)

**Per-task validation:**
- `uv run ruff format app/stops/service.py`
- `uv run ruff check --fix app/stops/service.py`
- `uv run mypy app/stops/service.py`
- `uv run pyright app/stops/service.py`

---

### Task 7: Create routes
**File:** `app/stops/routes.py` (create new)
**Action:** CREATE

Implement FastAPI routes following `reference/vsa-patterns.md` (Async Routes Pattern section) and the pattern in `app/transit/routes.py`.

Add pyright directives at the top of file (same as `app/transit/routes.py`):
```python
# pyright: reportUnknownMemberType=false, reportUntypedFunctionDecorator=false
```

```python
from fastapi import APIRouter, Depends, Query, status
from fastapi.requests import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.rate_limit import limiter
from app.shared.schemas import PaginatedResponse, PaginationParams
from app.stops.schemas import (
    StopCreate,
    StopNearbyParams,
    StopResponse,
    StopUpdate,
)
from app.stops.service import StopService

router = APIRouter(prefix="/api/v1/stops", tags=["stops"])
```

**Dependency:**
```python
def get_service(db: AsyncSession = Depends(get_db)) -> StopService:
    return StopService(db)
```

**Endpoints (6 total):**

1. `GET /api/v1/stops/` — List stops (paginated, with optional search)
   - Rate limit: `30/minute`
   - Params: `request: Request`, `pagination: PaginationParams = Depends()`, `search: str | None = Query(None, max_length=200)`, `active_only: bool = Query(True)`, `service: StopService = Depends(get_service)`
   - Returns: `PaginatedResponse[StopResponse]`
   - Call `service.list_stops(pagination, search=search, active_only=active_only)`

2. `GET /api/v1/stops/nearby` — Proximity search (MUST be defined BEFORE `/{stop_id}` to avoid path collision)
   - Rate limit: `30/minute`
   - Params: `request: Request`, `latitude: float = Query(..., ge=-90, le=90)`, `longitude: float = Query(..., ge=-180, le=180)`, `radius_meters: int = Query(500, ge=1, le=5000)`, `limit: int = Query(20, ge=1, le=100)`, `service: StopService = Depends(get_service)`
   - Returns: `list[StopResponse]`
   - Construct `StopNearbyParams(latitude=latitude, longitude=longitude, radius_meters=radius_meters)`
   - Call `service.search_nearby(params, limit=limit)`

3. `GET /api/v1/stops/{stop_id}` — Get stop by ID
   - Rate limit: `30/minute`
   - Params: `request: Request`, `stop_id: int`, `service: StopService = Depends(get_service)`
   - Returns: `StopResponse`
   - Call `service.get_stop(stop_id)`

4. `POST /api/v1/stops/` — Create stop
   - Rate limit: `10/minute`
   - Status code: `201`
   - Params: `request: Request`, `data: StopCreate`, `service: StopService = Depends(get_service)`
   - Returns: `StopResponse`
   - Call `service.create_stop(data)`

5. `PATCH /api/v1/stops/{stop_id}` — Update stop
   - Rate limit: `10/minute`
   - Params: `request: Request`, `stop_id: int`, `data: StopUpdate`, `service: StopService = Depends(get_service)`
   - Returns: `StopResponse`
   - Call `service.update_stop(stop_id, data)`

6. `DELETE /api/v1/stops/{stop_id}` — Delete stop
   - Rate limit: `10/minute`
   - Status code: `204`
   - Params: `request: Request`, `stop_id: int`, `service: StopService = Depends(get_service)`
   - Returns: `None`
   - Call `service.delete_stop(stop_id)`

**IMPORTANT:** The `request: Request` parameter is required by slowapi for rate limiting but is unused in the function body. The file-level pyright directive handles the type warning. The `ARG001` suppression is handled via `pyproject.toml` per-file-ignores (Task 9).

**IMPORTANT:** Define the `/nearby` endpoint BEFORE `/{stop_id}` — otherwise FastAPI will match "nearby" as a stop_id and return a 422 validation error.

**Per-task validation:**
- `uv run ruff format app/stops/routes.py`
- `uv run ruff check --fix app/stops/routes.py`
- `uv run mypy app/stops/routes.py`
- `uv run pyright app/stops/routes.py`

---

### Task 8: Register router and update config
**File:** `app/main.py` (modify existing)
**Action:** UPDATE

Add the stops router import and registration. Read the file first, then add:

1. Add import (after the existing transit import):
   ```python
   from app.stops.routes import router as stops_router
   ```

2. Add router inclusion (after `app.include_router(transit_router)`):
   ```python
   app.include_router(stops_router)
   ```

**File:** `pyproject.toml` (modify existing)
**Action:** UPDATE

Add per-file-ignores for the stops routes file. In `[tool.ruff.lint.per-file-ignores]` section, add:
```toml
"app/stops/routes.py" = ["ARG001"]  # slowapi requires Request param for rate limiting
```

**File:** `alembic/env.py` (modify existing)
**Action:** UPDATE

Add import of the stops model so Alembic autogenerate can discover it. After the existing imports (line 12), add:
```python
import app.stops.models  # noqa: F401 — register Stop model for autogenerate
```

**Per-task validation:**
- `uv run ruff format app/main.py app/stops/routes.py`
- `uv run ruff check --fix app/main.py alembic/env.py pyproject.toml`
- `uv run mypy app/main.py`

---

### Task 9: Create test conftest and init
**File:** `app/stops/tests/__init__.py` (create new)
**Action:** CREATE

Empty init file.

**File:** `app/stops/tests/conftest.py` (create new)
**Action:** CREATE

Create shared test fixtures for the stops feature:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.stops.models import Stop
from app.shared.models import utcnow
```

**Fixtures:**

- `def make_stop(**overrides) -> Stop` — Factory function that creates a `Stop` model instance with sensible defaults:
  - `id=1`, `gtfs_stop_id="1001"`, `stop_name="Centrala stacija"`, `stop_lat=56.9496`, `stop_lon=24.1052`, `stop_desc=None`, `location_type=0`, `parent_station_id=None`, `wheelchair_boarding=0`, `is_active=True`, `created_at=utcnow()`, `updated_at=utcnow()`
  - Apply `**overrides` on top of defaults
  - Construct `Stop` instance by setting attributes manually (not via `__init__` since SQLAlchemy models use mapped columns)
  - Return type annotation: `-> Stop`

- `def mock_db() -> AsyncMock` — Returns an `AsyncMock` for `AsyncSession`:
  - Return type annotation: `-> AsyncMock`

**Per-task validation:**
- `uv run ruff format app/stops/tests/conftest.py app/stops/tests/__init__.py`
- `uv run ruff check --fix app/stops/tests/conftest.py`

---

### Task 10: Create service tests
**File:** `app/stops/tests/test_service.py` (create new)
**Action:** CREATE

Write unit tests for `StopService`. Use `unittest.mock.AsyncMock` to mock the repository. Follow the test patterns in `app/transit/tests/test_service.py`.

**Test cases (minimum 12 tests):**

1. `test_get_stop_success` — Service returns `StopResponse` for valid ID
2. `test_get_stop_not_found` — Service raises `StopNotFoundError` for missing ID
3. `test_list_stops_success` — Service returns `PaginatedResponse` with items
4. `test_list_stops_empty` — Service returns empty `PaginatedResponse` when no stops
5. `test_list_stops_with_search` — Service passes search filter to repository
6. `test_create_stop_success` — Service creates stop and returns response
7. `test_create_stop_duplicate` — Service raises `StopAlreadyExistsError` for duplicate gtfs_stop_id
8. `test_update_stop_success` — Service updates and returns modified stop
9. `test_update_stop_not_found` — Service raises `StopNotFoundError`
10. `test_delete_stop_success` — Service deletes stop
11. `test_delete_stop_not_found` — Service raises `StopNotFoundError`
12. `test_search_nearby_success` — Service returns stops sorted by distance
13. `test_search_nearby_no_results` — Service returns empty list when no stops in radius

**Test pattern for each:**
```python
async def test_get_stop_success(make_stop, mock_db):
    stop = make_stop(id=1, stop_name="Centrala stacija")
    mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=stop)))

    service = StopService(mock_db)
    # Patch repository method directly
    service.repository.get = AsyncMock(return_value=stop)

    result = await service.get_stop(1)
    assert result.id == 1
    assert result.stop_name == "Centrala stacija"
```

**Approach:** Mock the repository methods directly on the service instance rather than mocking the database session internals. This keeps tests focused on service logic.

**Per-task validation:**
- `uv run ruff format app/stops/tests/test_service.py`
- `uv run ruff check --fix app/stops/tests/test_service.py`
- `uv run pytest app/stops/tests/test_service.py -v`

---

### Task 11: Create repository tests
**File:** `app/stops/tests/test_repository.py` (create new)
**Action:** CREATE

Write unit tests for `StopRepository` using mocked `AsyncSession`. Test the SQL query construction, not actual database execution.

**Test cases (minimum 8 tests):**

1. `test_get_by_id` — Repository executes correct select query
2. `test_get_by_gtfs_id` — Repository looks up by gtfs_stop_id
3. `test_list_default` — Repository applies active_only filter and pagination
4. `test_list_with_search` — Repository adds ilike filter
5. `test_count_active` — Repository counts with active filter
6. `test_create` — Repository adds to session and commits
7. `test_update` — Repository sets attributes and commits
8. `test_delete` — Repository deletes from session and commits

**Mock pattern:** Use `AsyncMock` for the session. For `execute`, mock the return value to have `.scalars().all()` or `.scalar_one_or_none()` chains.

**Per-task validation:**
- `uv run ruff format app/stops/tests/test_repository.py`
- `uv run ruff check --fix app/stops/tests/test_repository.py`
- `uv run pytest app/stops/tests/test_repository.py -v`

---

### Task 12: Create route tests
**File:** `app/stops/tests/test_routes.py` (create new)
**Action:** CREATE

Write unit tests for the API routes using FastAPI's TestClient pattern. Mock the `StopService` dependency.

**Setup:** Override the `get_service` dependency in the router:
```python
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch

from app.main import app
from app.stops.routes import get_service
from app.stops.service import StopService
from app.core.rate_limit import limiter

# Disable rate limiting for tests
limiter.enabled = False
```

**Test cases (minimum 10 tests):**

1. `test_list_stops` — GET `/api/v1/stops/` returns 200 with paginated data
2. `test_list_stops_with_search` — GET `/api/v1/stops/?search=Centrs` passes search param
3. `test_get_stop` — GET `/api/v1/stops/1` returns 200 with stop data
4. `test_get_stop_not_found` — GET `/api/v1/stops/999` returns 404
5. `test_create_stop` — POST `/api/v1/stops/` returns 201 with created stop
6. `test_create_stop_duplicate` — POST returns 422 for duplicate gtfs_stop_id
7. `test_update_stop` — PATCH `/api/v1/stops/1` returns 200 with updated stop
8. `test_delete_stop` — DELETE `/api/v1/stops/1` returns 204
9. `test_nearby_stops` — GET `/api/v1/stops/nearby?latitude=56.9496&longitude=24.1052` returns list
10. `test_nearby_missing_params` — GET `/api/v1/stops/nearby` without lat/lon returns 422

**IMPORTANT:** The `limiter.enabled = False` line MUST come AFTER all imports (Ruff E402 rule). Place all `from ... import ...` lines first, then `limiter.enabled = False`.

**Mock pattern:** Use `app.dependency_overrides[get_service]` to inject a mock service. The mock service should return `StopResponse` instances for success cases and raise the appropriate exceptions for error cases.

**Per-task validation:**
- `uv run ruff format app/stops/tests/test_routes.py`
- `uv run ruff check --fix app/stops/tests/test_routes.py`
- `uv run pytest app/stops/tests/test_routes.py -v`

---

## Migration

After all code is written and tests pass:

```bash
uv run alembic revision --autogenerate -m "add stops table"
```

Review the generated migration in `alembic/versions/`. Verify it creates:
- `stops` table with all columns
- Indexes on `id`, `gtfs_stop_id` (unique), `stop_name`
- Foreign key on `parent_station_id` → `stops.id`

Then apply:
```bash
uv run alembic upgrade head
```

**Note:** This requires a running PostgreSQL instance. If Docker is not running, the migration generation still works (it just compares metadata). Application of the migration requires the database.

## Logging Events

- `stops.fetch_started` — When retrieving a single stop by ID
- `stops.fetch_failed` — When stop not found (includes `reason="not_found"`)
- `stops.list_started` — When listing stops (includes search, pagination params)
- `stops.list_completed` — When list returns (includes `result_count`, `total`)
- `stops.create_started` — When creating a stop (includes `gtfs_stop_id`)
- `stops.create_completed` — When stop created (includes `stop_id`, `gtfs_stop_id`)
- `stops.create_failed` — When creation fails (duplicate gtfs_stop_id)
- `stops.update_started` — When updating a stop (includes `stop_id`)
- `stops.update_completed` — When stop updated (includes `stop_id`)
- `stops.delete_started` — When deleting a stop (includes `stop_id`)
- `stops.delete_completed` — When stop deleted (includes `stop_id`)
- `stops.nearby_started` — When proximity search starts (includes lat, lon, radius)
- `stops.nearby_completed` — When proximity search completes (includes `result_count`)

## Testing Strategy

### Unit Tests
**Location:** `app/stops/tests/`
- `test_service.py` — StopService business logic (13 tests)
- `test_repository.py` — StopRepository query construction (8 tests)
- `test_routes.py` — HTTP endpoint behavior (10 tests)

### Integration Tests
**Mark with:** `@pytest.mark.integration`
Not included in this plan — would test actual database operations. Can be added after the feature is stable.

### Edge Cases
- Empty search string — returns all stops (no filter)
- Very long search string — truncated by schema validation (`max_length=200`)
- Nearby with `radius_meters=1` — likely returns no results
- Nearby with no coordinates on stops — stops without lat/lon are skipped
- Delete stop with children (parent_station_id FK) — database will reject with FK constraint error
- Create stop with `parent_station_id` pointing to non-existent stop — FK constraint error
- PATCH with empty body — no-op, returns unchanged stop
- Pagination beyond total — returns empty items list with correct total

## Acceptance Criteria

This feature is complete when:
- [ ] `Stop` model exists with all GTFS-aligned fields
- [ ] CRUD endpoints work: GET (list + single), POST, PATCH, DELETE
- [ ] Proximity search (`/nearby`) returns stops sorted by distance
- [ ] Pagination works with `PaginatedResponse[StopResponse]`
- [ ] Search filter on `stop_name` is case-insensitive
- [ ] Duplicate `gtfs_stop_id` is rejected with 422
- [ ] Rate limiting applied to all endpoints
- [ ] All type checkers pass (mypy + pyright)
- [ ] All tests pass (31+ tests)
- [ ] Structured logging follows `stops.action_state` pattern
- [ ] No type suppressions added
- [ ] Router registered in `app/main.py`
- [ ] Alembic migration generated
- [ ] No regressions in existing tests

## Completion Checklist

Before marking this plan as fully executed:
- [ ] All 12 tasks completed in order
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
uv run pytest app/stops/tests/ -v
```

**Level 4: Full Test Suite (unit)**
```bash
uv run pytest -v -m "not integration"
```

**Level 5: Server Validation (if Docker running)**
```bash
curl -s http://localhost:8123/health
curl -s http://localhost:8123/api/v1/stops/ | python -m json.tool
```

**Success definition:** Levels 1-4 exit code 0, all tests pass, zero errors or warnings. Level 5 optional.

## Dependencies

- **Shared utilities used:** `PaginationParams`, `PaginatedResponse[T]`, `ErrorResponse`, `TimestampMixin`, `utcnow()`, `get_db()`, `get_logger()`, `Base`
- **Core modules used:** `app.core.database`, `app.core.exceptions`, `app.core.logging`, `app.core.rate_limit`
- **New dependencies:** None — plain float columns, no GeoAlchemy2 needed
- **New env vars:** None

## Known Pitfalls

The executing agent MUST follow these rules to avoid common errors:

1. **No `assert` in production code** — Ruff S101 forbids assert outside test files. Use conditional checks instead.
2. **No `object` type hints** — Import and use actual types directly. Never write `def f(data: object)` then isinstance-check.
3. **Untyped third-party libraries** — When adding a dependency without `py.typed`:
   - mypy: Add `[[tool.mypy.overrides]]` with `ignore_missing_imports = true`
   - pyright: Add file-level `# pyright: reportUnknown...=false` directives to the ONE file interfacing with the library
   - **NEVER** use pyright `[[executionEnvironments]]` with a scoped `root` — it breaks `app.*` import resolution
4. **Mock exceptions must match catch blocks** — If production code catches `httpx.HTTPError`, tests must mock `httpx.ConnectError` (or another subclass), not bare `Exception`.
5. **No unused imports or variables** — Ruff F401 catches unused imports, Ruff F841 catches unused local variables. Don't write speculative code — only import/assign what you actually use.
6. **No unnecessary noqa/type-ignore** — Ruff RUF100 flags unused suppression comments.
7. **Test helper functions need return type annotations** — mypy `disallow_untyped_defs=false` for tests only relaxes *defining* untyped functions, but `disallow_untyped_call` is still globally true. When `async def test_foo()` (implicitly typed via coroutine return) calls an untyped helper, mypy raises `no-untyped-call`. Fix: always add `-> ReturnType` to test helpers (e.g., `def make_stop(**overrides) -> Stop:`).
8. **No EN DASH in strings** — Ruff RUF001 forbids ambiguous Unicode characters like `–` (EN DASH, U+2013). Always use `-` (HYPHEN-MINUS, U+002D).
9. **`/nearby` route MUST be defined before `/{stop_id}`** — FastAPI matches routes in order. "nearby" would match as a `stop_id` path parameter if the parameterized route comes first.
10. **`limiter.enabled = False` in tests MUST come after all imports** — Ruff E402 flags imports after non-import statements.
11. **Schema field additions break ALL consumers** — When adding a required field to a Pydantic `BaseModel`, update every file that constructs that model (test helpers, mock factories, route tests).
12. **Dict literal types must match function param types exactly (invariance)** — In tests, `{"key": "value"}` is inferred as `dict[str, str]` which is NOT compatible with broader union types. Add explicit type annotations.
13. **`from_attributes = True` is required on response models** — Since `StopResponse` is constructed from SQLAlchemy model instances via `model_validate(stop)`, the `ConfigDict(from_attributes=True)` is essential.
14. **Rate limiting pyright directives** — `app/stops/routes.py` needs `# pyright: reportUnknownMemberType=false, reportUntypedFunctionDecorator=false` at the top of the file because slowapi lacks type stubs (same as `app/transit/routes.py`).
15. **SQLAlchemy `ilike` for case-insensitive search** — Use `Stop.stop_name.ilike(f"%{search}%")` not `.like()`. The `ilike` method generates `ILIKE` on PostgreSQL which is case-insensitive.
16. **Self-referential FK on `parent_station_id`** — SQLAlchemy handles `ForeignKey("stops.id")` using the table name string, not the model class. This is correct for self-referential relationships.

## Notes

- **Future consideration:** If stop count grows beyond ~10,000, consider adding GeoAlchemy2 with a spatial index (`GIST`) for proximity queries. The current Haversine approach loads all stops into memory.
- **GTFS sync:** A future task will add a GTFS import endpoint that bulk-creates/updates stops from `stops.txt`. The `gtfs_stop_id` unique constraint enables upsert logic.
- **Agent tool interaction:** The existing `search_stops` agent tool reads from the GTFS static cache (ephemeral, read-only). This feature manages the persistent database table. They are independent systems. A future enhancement could have the agent query the database instead of the cache.
- **Security:** No authentication is enforced at the API level for MVP — auth is handled by the CMS frontend layer and nginx. Rate limiting provides basic abuse protection.

## Pre-Implementation Checklist

The executing agent MUST verify before writing any code:
- [ ] Read all files listed in "Relevant Files" section
- [ ] Reviewed `reference/vsa-patterns.md` for exact code patterns
- [ ] Understood the solution approach (plain floats, no PostGIS)
- [ ] Clear on task execution order (1-12)
- [ ] Validation commands are executable in this environment
