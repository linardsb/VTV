# Plan: Schedule Management

## Feature Metadata
**Feature Type**: New Capability
**Estimated Complexity**: High
**Primary Systems Affected**: `app/schedules/` (new), `app/main.py`, `app/stops/` (cross-feature read)

## Feature Description

Schedule management adds GTFS-compliant database tables and REST API for managing transit agencies, routes, service calendars, trips, and stop times. This is the foundational data layer for VTV's transit operations — everything from timetable grids to GTFS import/export depends on these tables.

The feature includes a GTFS ZIP import endpoint that parses Riga Satiksme's public feed (80 routes, 2000+ stops, thousands of trips) and bulk-inserts into the database. After import, all entities support manual CRUD for fine-grained editing. Stop times reference the existing `stops` table via foreign key for referential integrity.

The schedule data follows the GTFS specification: agencies own routes, routes contain trips, trips belong to service calendars (weekly patterns with date exceptions), and each trip has an ordered sequence of stop times with arrival/departure values.

## User Story

As a transit administrator,
I want to import schedules from GTFS feeds and edit them via the CMS,
so that I can manage timetables, service calendars, and trip data for all routes.

## Solution Approach

We create a new `app/schedules/` vertical slice with 6 SQLAlchemy models (Agency, Route, Calendar, CalendarDate, Trip, StopTime), a GTFS ZIP import module, and ~20 REST endpoints covering full CRUD for all entities.

**Approach Decision:**
We chose a single `schedules` feature owning all 6 tables because:
- These entities are tightly coupled (trips require routes + calendars, stop_times require trips + stops)
- GTFS import must orchestrate creation across all tables in one transaction
- A single service layer can enforce cross-entity validation (e.g., trips reference valid calendars)

**Alternatives Considered:**
- Separate `routes` and `schedules` features: Rejected because routes and trips are too tightly coupled for GTFS import. Would require complex cross-feature writes.
- String IDs instead of FK integers: Rejected because the user explicitly requested FK to stops.id for referential integrity.

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, anti-patterns, logging patterns
- `app/shared/schemas.py` — `PaginationParams`, `PaginatedResponse[T]`, `ErrorResponse`
- `app/shared/models.py` — `TimestampMixin`, `utcnow()`
- `app/core/database.py` — `Base`, `get_db()`, `AsyncSessionLocal`
- `app/core/exceptions.py` — `NotFoundError`, `ValidationError`, `DatabaseError`

### Similar Features (Examples to Follow)
- `app/stops/schemas.py` — Pydantic schema pattern (Base/Create/Update/Response)
- `app/stops/models.py` — SQLAlchemy model with `Mapped[]`, FK, index
- `app/stops/repository.py` — Async CRUD, pagination, filtering, count
- `app/stops/service.py` — Structured logging, error handling, PaginatedResponse
- `app/stops/exceptions.py` — Feature exception hierarchy
- `app/stops/routes.py` — Thin routes, `get_service()`, rate limiting, `_ = request`
- `app/stops/tests/conftest.py` — Factory fixtures, `make_stop()`, `mock_db`
- `app/core/agents/tools/transit/static_cache.py` — GTFS ZIP parsing (CSV reader, data structures, field mapping). Reuse the same parsing approach.

### Files to Modify
- `app/main.py` — Register `schedules_router`

## Implementation Plan

### Phase 1: Foundation
Create schemas, models, and exceptions. These define the data structures and error types used by all subsequent code.

### Phase 2: Core Implementation
Build repository (CRUD), GTFS import (ZIP parsing + bulk insert), service (business logic + validation), and routes (REST API).

### Phase 3: Testing & Integration
Create test fixtures, unit tests for service/routes/import, register router in main.py, and generate database migration.

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.

---

### Task 1: Create Pydantic Schemas
**File:** `app/schedules/schemas.py` (create new)
**Action:** CREATE

Create all request/response schemas for the 6 GTFS entities. Follow the pattern in `app/stops/schemas.py`.

**Agency schemas:**
- `AgencyCreate`: `gtfs_agency_id: str` (min 1, max 50), `agency_name: str` (min 1, max 200), `agency_url: str | None`, `agency_timezone: str` (default `"Europe/Riga"`), `agency_lang: str | None`
- `AgencyResponse`: All fields + `id: int`, `created_at`, `updated_at`. Set `model_config = ConfigDict(from_attributes=True)`

**Route schemas:**
- `RouteCreate`: `gtfs_route_id: str`, `agency_id: int`, `route_short_name: str` (max 50), `route_long_name: str` (max 200), `route_type: int` (ge=0, le=12), `route_color: str | None` (max 6), `route_text_color: str | None`, `route_sort_order: int | None`
- `RouteUpdate`: All fields optional with `Field(None, ...)`
- `RouteResponse`: All fields + `id`, timestamps. Include `model_config = ConfigDict(from_attributes=True)`

**Calendar schemas:**
- `CalendarCreate`: `gtfs_service_id: str`, 7 day booleans (`monday` through `sunday`), `start_date: date`, `end_date: date`
- `CalendarUpdate`: All fields optional
- `CalendarResponse`: All fields + `id`, timestamps, `exceptions: list[CalendarDateResponse]`

**CalendarDate schemas:**
- `CalendarDateCreate`: `date: date`, `exception_type: int` (ge=1, le=2)
- `CalendarDateResponse`: `id`, `calendar_id`, `date`, `exception_type`, timestamps

**Trip schemas:**
- `TripCreate`: `gtfs_trip_id: str` (max 100), `route_id: int`, `calendar_id: int`, `direction_id: int | None` (ge=0, le=1), `trip_headsign: str | None`, `block_id: str | None`
- `TripUpdate`: All fields optional except `gtfs_trip_id`
- `TripResponse`: All fields + `id`, timestamps
- `TripDetailResponse(TripResponse)`: Adds `stop_times: list[StopTimeResponse]`

**StopTime schemas:**
- `StopTimeCreate`: `stop_id: int`, `stop_sequence: int` (ge=1), `arrival_time: str` (pattern `^\d{2}:\d{2}:\d{2}$`), `departure_time: str` (same pattern), `pickup_type: int` (default 0), `drop_off_type: int` (default 0)
- `StopTimeResponse`: All fields + `id`, `trip_id`, timestamps
- `StopTimesBulkUpdate`: `stop_times: list[StopTimeCreate]`

**Import schemas:**
- `GTFSImportResponse`: `agencies_count: int`, `routes_count: int`, `calendars_count: int`, `calendar_dates_count: int`, `trips_count: int`, `stop_times_count: int`, `skipped_stop_times: int`, `warnings: list[str]`

**Validation schemas:**
- `ValidationResult`: `valid: bool`, `errors: list[str]`, `warnings: list[str]`

Also create `app/schedules/__init__.py` as an empty file.

**Per-task validation:**
- `uv run ruff format app/schedules/schemas.py`
- `uv run ruff check --fix app/schedules/schemas.py`
- `uv run mypy app/schedules/schemas.py`

---

### Task 2: Create SQLAlchemy Models
**File:** `app/schedules/models.py` (create new)
**Action:** CREATE

Create 6 models following the pattern in `app/stops/models.py`. All inherit `Base` and `TimestampMixin`.

**Imports:**
```python
from datetime import date
from sqlalchemy import Boolean, Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base
from app.shared.models import TimestampMixin
```

**Agency model** (`__tablename__ = "agencies"`):
- `id: Mapped[int]` — primary_key, index
- `gtfs_agency_id: Mapped[str]` — String(50), unique, nullable=False, index
- `agency_name: Mapped[str]` — String(200), nullable=False
- `agency_url: Mapped[str | None]` — String(500), nullable=True
- `agency_timezone: Mapped[str]` — String(50), nullable=False, default="Europe/Riga"
- `agency_lang: Mapped[str | None]` — String(5), nullable=True

**Route model** (`__tablename__ = "routes"`):
- `id`, `gtfs_route_id` (String(50), unique, index)
- `agency_id: Mapped[int]` — FK to `agencies.id`, ondelete CASCADE, index
- `route_short_name: Mapped[str]` — String(50), index
- `route_long_name: Mapped[str]` — String(200)
- `route_type: Mapped[int]` — Integer (0=tram, 3=bus, 11=trolleybus)
- `route_color: Mapped[str | None]`, `route_text_color: Mapped[str | None]` — String(6)
- `route_sort_order: Mapped[int | None]`
- `is_active: Mapped[bool]` — default True

**Calendar model** (`__tablename__ = "calendars"`):
- `id`, `gtfs_service_id` (String(50), unique, index)
- 7 day booleans: `monday` through `sunday` — Boolean, nullable=False
- `start_date: Mapped[date]` — Date, nullable=False
- `end_date: Mapped[date]` — Date, nullable=False

**CalendarDate model** (`__tablename__ = "calendar_dates"`):
- `id`, `calendar_id: Mapped[int]` — FK to `calendars.id`, ondelete CASCADE, index
- `date: Mapped[date]` — Date, nullable=False
- `exception_type: Mapped[int]` — Integer (1=added, 2=removed)

**Trip model** (`__tablename__ = "trips"`):
- `id`, `gtfs_trip_id: Mapped[str]` — String(100), unique, index
- `route_id: Mapped[int]` — FK to `routes.id`, ondelete CASCADE, index
- `calendar_id: Mapped[int]` — FK to `calendars.id`, ondelete CASCADE, index
- `direction_id: Mapped[int | None]` — Integer, nullable
- `trip_headsign: Mapped[str | None]` — String(200)
- `block_id: Mapped[str | None]` — String(50)

**StopTime model** (`__tablename__ = "stop_times"`):
- `id`, `trip_id: Mapped[int]` — FK to `trips.id`, ondelete CASCADE, index
- `stop_id: Mapped[int]` — FK to `stops.id`, ondelete CASCADE, index
- `stop_sequence: Mapped[int]` — Integer
- `arrival_time: Mapped[str]` — String(8), HH:MM:SS format (can exceed 24:00:00)
- `departure_time: Mapped[str]` — String(8)
- `pickup_type: Mapped[int]` — Integer, default=0
- `drop_off_type: Mapped[int]` — Integer, default=0

**Per-task validation:**
- `uv run ruff format app/schedules/models.py`
- `uv run ruff check --fix app/schedules/models.py`
- `uv run mypy app/schedules/models.py`
- `uv run pyright app/schedules/models.py`

---

### Task 3: Create Feature Exceptions
**File:** `app/schedules/exceptions.py` (create new)
**Action:** CREATE

Follow pattern from `app/stops/exceptions.py`:
```python
from app.core.exceptions import DatabaseError, NotFoundError, ValidationError

class ScheduleError(DatabaseError): pass
class RouteNotFoundError(NotFoundError): pass
class CalendarNotFoundError(NotFoundError): pass
class TripNotFoundError(NotFoundError): pass
class StopTimeNotFoundError(NotFoundError): pass
class RouteAlreadyExistsError(ValidationError): pass
class CalendarAlreadyExistsError(ValidationError): pass
class TripAlreadyExistsError(ValidationError): pass
class ScheduleValidationError(ValidationError): pass
class GTFSImportError(DatabaseError): pass
```

**Per-task validation:**
- `uv run ruff format app/schedules/exceptions.py`
- `uv run ruff check --fix app/schedules/exceptions.py`
- `uv run mypy app/schedules/exceptions.py`

---

### Task 4: Create Repository
**File:** `app/schedules/repository.py` (create new)
**Action:** CREATE

Follow the pattern from `app/stops/repository.py`. All methods async, use `select()` syntax.

**ScheduleRepository class:**
Constructor: `def __init__(self, db: AsyncSession) -> None:` stores `self.db`

**Per entity, implement these method groups (mirror `app/stops/repository.py` patterns):**

**Agency:** `create_agency`, `get_agency`, `get_agency_by_gtfs_id`, `list_agencies`

**Route:** `create_route`, `get_route`, `get_route_by_gtfs_id`, `list_routes(*, offset, limit, search, route_type, agency_id)`, `count_routes(same filters)`, `update_route`, `delete_route`

**Calendar:** `create_calendar`, `get_calendar`, `get_calendar_by_gtfs_id`, `list_calendars(*, offset, limit, active_on: date | None)` (filter `start_date <= active_on <= end_date`), `count_calendars`, `update_calendar`, `delete_calendar`

**CalendarDate:** `create_calendar_date(calendar_id, data)`, `list_calendar_dates(calendar_id)`, `get_calendar_date`, `delete_calendar_date`

**Trip:** `create_trip`, `get_trip`, `get_trip_by_gtfs_id`, `list_trips(*, offset, limit, route_id, calendar_id, direction_id)`, `count_trips(same filters)`, `update_trip`, `delete_trip`

**StopTime:** `list_stop_times(trip_id)` (order by stop_sequence), `replace_stop_times(trip_id, stop_times)` (delete existing + bulk create), `create_stop_time(trip_id, data)`, `get_stop_time`, `delete_stop_time`

**Bulk methods (for GTFS import):**
- `bulk_create_{entity}(items: list[Model]) -> None` — one per entity, uses `self.db.add_all(); await self.db.flush()`
- `clear_all_schedule_data() -> None` — DELETE in reverse FK order: stop_times, trips, calendar_dates, calendars, routes, agencies

IMPORTANT: Bulk methods use `flush()` not `commit()` — the service controls the transaction boundary.

**Per-task validation:**
- `uv run ruff format app/schedules/repository.py`
- `uv run ruff check --fix app/schedules/repository.py`
- `uv run mypy app/schedules/repository.py`
- `uv run pyright app/schedules/repository.py`

---

### Task 5: Create GTFS Import Module
**File:** `app/schedules/gtfs_import.py` (create new)
**Action:** CREATE

Parse GTFS ZIP files and return model instances. Reference `app/core/agents/tools/transit/static_cache.py` for CSV parsing patterns. This module is pure parsing (no database access) — the service handles DB operations.

**Class: `GTFSImporter`**

Constructor: `def __init__(self, zip_data: bytes) -> None:` — stores bytes, initializes warnings list

**Methods (all sync — CSV parsing is CPU-bound, not I/O):**

- `parse() -> GTFSParseResult` — orchestrates all file parsing
- `_parse_agencies(reader)` — parse agencies.txt (create default if missing)
- `_parse_routes(reader, agency_map)` — parse routes.txt, resolve agency_id
- `_parse_calendars(reader)` — parse calendar.txt (YYYYMMDD -> date, "0"/"1" -> bool)
- `_parse_calendar_dates(reader, calendar_map)` — parse calendar_dates.txt
- `_parse_trips(reader, route_map, calendar_map)` — skip trips with unknown route/calendar
- `_parse_stop_times(reader, trip_map, stop_map) -> tuple[list[StopTime], int]` — skip unknown trip/stop with warning

**GTFSParseResult dataclass:** agencies, routes, calendars, calendar_dates, trips, stop_times (lists), skipped_stop_times (int), warnings (list[str]). Use typed lambda for defaults: `field(default_factory=lambda: list[Agency]())`.

**Key patterns:**
- `zipfile.ZipFile(io.BytesIO(zip_data))` to read ZIP from bytes
- `csv.DictReader(io.TextIOWrapper(zf.open(filename)))` for each CSV
- `stop_map` parameter maps GTFS stop_id strings to database stop.id integers (built by service)

**Per-task validation:**
- `uv run ruff format app/schedules/gtfs_import.py`
- `uv run ruff check --fix app/schedules/gtfs_import.py`
- `uv run mypy app/schedules/gtfs_import.py`
- `uv run pyright app/schedules/gtfs_import.py`

---

### Task 6: Create Service
**File:** `app/schedules/service.py` (create new)
**Action:** CREATE

Business logic with structured logging. Follow `app/stops/service.py` pattern.

**Class: `ScheduleService`**

Constructor: `def __init__(self, db: AsyncSession) -> None:` — creates `self.repository = ScheduleRepository(db)`, stores `self.db`

**Agency methods:**
- `list_agencies() -> list[AgencyResponse]`
- `create_agency(data: AgencyCreate) -> AgencyResponse` — check duplicate by gtfs_agency_id

**Route methods:**
- `get_route(route_id: int) -> RouteResponse` — raise RouteNotFoundError if missing
- `list_routes(pagination: PaginationParams, search: str | None, route_type: int | None, agency_id: int | None) -> PaginatedResponse[RouteResponse]`
- `create_route(data: RouteCreate) -> RouteResponse` — check duplicate gtfs_route_id
- `update_route(route_id: int, data: RouteUpdate) -> RouteResponse`
- `delete_route(route_id: int) -> None`

**Calendar methods:**
- `get_calendar(calendar_id: int) -> CalendarResponse` — include exceptions list
- `list_calendars(pagination: PaginationParams, active_on: date | None) -> PaginatedResponse[CalendarResponse]`
- `create_calendar(data: CalendarCreate) -> CalendarResponse`
- `update_calendar(calendar_id: int, data: CalendarUpdate) -> CalendarResponse`
- `delete_calendar(calendar_id: int) -> None`
- `add_calendar_exception(calendar_id: int, data: CalendarDateCreate) -> CalendarDateResponse` — verify calendar exists
- `remove_calendar_exception(exception_id: int) -> None`

**Trip methods:**
- `get_trip(trip_id: int) -> TripDetailResponse` — include stop_times
- `list_trips(pagination: PaginationParams, route_id: int | None, calendar_id: int | None, direction_id: int | None) -> PaginatedResponse[TripResponse]`
- `create_trip(data: TripCreate) -> TripResponse` — verify route and calendar exist
- `update_trip(trip_id: int, data: TripUpdate) -> TripResponse`
- `delete_trip(trip_id: int) -> None`

**StopTime methods:**
- `replace_stop_times(trip_id: int, data: StopTimesBulkUpdate) -> list[StopTimeResponse]` — verify trip exists, replace all stop_times

**GTFS Import method — `import_gtfs(zip_data: bytes) -> GTFSImportResponse`:**
  1. Build stop_map: `StopRepository(self.db)` cross-feature read, map `{stop.gtfs_stop_id: stop.id}`
  2. Clear existing data: `repository.clear_all_schedule_data()`
  3. **Interleaved parse+insert** (CRITICAL — IDs needed for FK resolution):
     - Parse agencies CSV -> bulk create -> flush -> build `{gtfs_agency_id: agency.id}` map
     - Parse routes CSV with agency map -> bulk create -> flush -> build route map
     - Parse calendars -> bulk create -> flush -> build calendar map
     - Parse calendar_dates with calendar map -> bulk create -> flush
     - Parse trips with route+calendar maps -> bulk create -> flush -> build trip map
     - Parse stop_times with trip+stop maps -> bulk create -> flush
  4. Commit transaction, log `schedules.import_completed` with counts

**Validation method:**
- `validate_schedule() -> ValidationResult`
  1. Check all trips reference valid routes (route_id exists)
  2. Check all trips reference valid calendars (calendar_id exists)
  3. Check all stop_times reference valid trips (trip_id exists)
  4. Check all stop_times reference valid stops (stop_id exists in stops table)
  5. Check calendar date ranges (start_date <= end_date)
  6. Check stop_time ordering (stop_sequence is sequential within each trip)
  7. Check time format (HH:MM:SS, arrival <= departure per stop)
  8. Return ValidationResult with errors and warnings

**Logging pattern:** `schedules.{entity}.{action}_{state}` — e.g., `schedules.route.create_completed`, `schedules.import_started`

**Per-task validation:**
- `uv run ruff format app/schedules/service.py`
- `uv run ruff check --fix app/schedules/service.py`
- `uv run mypy app/schedules/service.py`
- `uv run pyright app/schedules/service.py`

---

### Task 7: Create API Routes
**File:** `app/schedules/routes.py` (create new)
**Action:** CREATE

Follow `app/stops/routes.py` pattern. Thin routes, `Depends()` injection, rate limiting.

```python
router = APIRouter(prefix="/api/v1/schedules", tags=["schedules"])

def get_service(db: AsyncSession = Depends(get_db)) -> ScheduleService:  # noqa: B008
    return ScheduleService(db)
```

**Rate limits:** 30/minute for reads, 10/minute for writes, 5/minute for import/validate.

**Agency endpoints (2):**
- `GET /agencies` → `list_agencies` (30/min)
- `POST /agencies` → `create_agency` (10/min, 201)

**Route endpoints (5):**
- `GET /routes` → `list_routes` with pagination, `search: str | None`, `route_type: int | None`, `agency_id: int | None` query params (30/min)
- `POST /routes` → `create_route` (10/min, 201)
- `GET /routes/{route_id}` → `get_route` (30/min)
- `PATCH /routes/{route_id}` → `update_route` (10/min)
- `DELETE /routes/{route_id}` → `delete_route` (10/min, 204)

**Calendar endpoints (5 + 2 exception endpoints):**
- `GET /calendars` → `list_calendars` with pagination, `active_on: date | None` (30/min)
- `POST /calendars` → `create_calendar` (10/min, 201)
- `GET /calendars/{calendar_id}` → `get_calendar` (30/min)
- `PATCH /calendars/{calendar_id}` → `update_calendar` (10/min)
- `DELETE /calendars/{calendar_id}` → `delete_calendar` (10/min, 204)
- `POST /calendars/{calendar_id}/exceptions` → `add_calendar_exception` (10/min, 201)
- `DELETE /calendar-exceptions/{exception_id}` → `remove_calendar_exception` (10/min, 204)

**Trip endpoints (5 + 1 stop_times):**
- `GET /trips` → `list_trips` with pagination, `route_id`, `calendar_id`, `direction_id` filters (30/min)
- `POST /trips` → `create_trip` (10/min, 201)
- `GET /trips/{trip_id}` → `get_trip` returns TripDetailResponse with stop_times (30/min)
- `PATCH /trips/{trip_id}` → `update_trip` (10/min)
- `DELETE /trips/{trip_id}` → `delete_trip` (10/min, 204)
- `PUT /trips/{trip_id}/stop-times` → `replace_stop_times` (10/min)

**Import endpoint (1):**
- `POST /import` → Accept `UploadFile`, read bytes, call `service.import_gtfs(zip_data)` (5/min)
  - Use `from fastapi import UploadFile`
  - Read with `zip_data = await file.read()`
  - Return `GTFSImportResponse`

**Validation endpoint (1):**
- `POST /validate` → `service.validate_schedule()` (5/min)

Every endpoint must:
- Include `request: Request` parameter (for limiter), then `_ = request` in body
- Use `Depends(get_service)` with `# noqa: B008`
- Set appropriate `response_model` and `status_code`

Also add `app/schedules/tests/__init__.py` as empty file.

**Per-task validation:**
- `uv run ruff format app/schedules/routes.py`
- `uv run ruff check --fix app/schedules/routes.py`
- `uv run mypy app/schedules/routes.py`
- `uv run pyright app/schedules/routes.py`

---

### Task 8: Register Router in Main
**File:** `app/main.py` (modify existing)
**Action:** UPDATE

Add import and router registration. Place alongside existing routers:

```python
from app.schedules.routes import router as schedules_router
```

```python
app.include_router(schedules_router)
```

Also add `"app/schedules/routes.py" = ["ARG001"]` to `pyproject.toml` under `[tool.ruff.lint.per-file-ignores]` (slowapi requires unused `Request` param).

**Per-task validation:**
- `uv run ruff format app/main.py`
- `uv run ruff check --fix app/main.py`
- `uv run mypy app/main.py`

---

### Task 9: Create Test Fixtures
**File:** `app/schedules/tests/conftest.py` (create new)
**Action:** CREATE

Follow `app/stops/tests/conftest.py` pattern. Create factory functions and fixtures.

**Helper functions:**
- `make_agency(**overrides) -> Agency` — default: id=1, gtfs_agency_id="RS", agency_name="Rigas Satiksme", agency_timezone="Europe/Riga"
- `make_route(**overrides) -> Route` — default: id=1, gtfs_route_id="bus_22", agency_id=1, route_short_name="22", route_long_name="Centrs - Jugla", route_type=3
- `make_calendar(**overrides) -> Calendar` — default: id=1, gtfs_service_id="weekday_1", monday-friday=True, saturday-sunday=False, start_date=date(2026,1,1), end_date=date(2026,12,31)
- `make_calendar_date(**overrides) -> CalendarDate` — default: id=1, calendar_id=1, date=date(2026,3,15), exception_type=2
- `make_trip(**overrides) -> Trip` — default: id=1, gtfs_trip_id="trip_22_1", route_id=1, calendar_id=1, direction_id=0, trip_headsign="Jugla"
- `make_stop_time(**overrides) -> StopTime` — default: id=1, trip_id=1, stop_id=1, stop_sequence=1, arrival_time="08:00:00", departure_time="08:01:00"

All helpers set `created_at=utcnow()`, `updated_at=utcnow()` from `app.shared.models`.

**Fixtures:**
- `sample_agency`, `sample_route`, `sample_calendar`, `sample_trip` — single instances
- `sample_routes` — list of 3 routes (bus, trolleybus, tram)
- `sample_stop_times` — list of 5 ordered stop_times for a trip
- `mock_db` — `AsyncMock()` for mocking AsyncSession

**Per-task validation:**
- `uv run ruff format app/schedules/tests/conftest.py`
- `uv run ruff check --fix app/schedules/tests/conftest.py`

---

### Task 10: Create Service Tests
**File:** `app/schedules/tests/test_service.py` (create new)
**Action:** CREATE

Test service methods using mocked repository. Follow `app/stops/tests/` patterns.

**Route tests (~8):**
- `test_create_route_success` — verify route created, logging, response fields
- `test_create_route_duplicate_raises` — mock get_route_by_gtfs_id returns existing
- `test_get_route_success` — verify response mapping
- `test_get_route_not_found` — raises RouteNotFoundError
- `test_list_routes_paginated` — verify PaginatedResponse structure
- `test_update_route_success`
- `test_delete_route_success`
- `test_delete_route_not_found`

**Calendar tests (~5):**
- `test_create_calendar_success`
- `test_get_calendar_with_exceptions` — verify exceptions list populated
- `test_add_calendar_exception`
- `test_list_calendars_active_on_filter`
- `test_delete_calendar`

**Trip tests (~5):**
- `test_create_trip_success` — verify route and calendar exist
- `test_get_trip_with_stop_times` — verify TripDetailResponse
- `test_list_trips_filter_by_route`
- `test_replace_stop_times` — verify old removed, new created
- `test_delete_trip`

**Validation tests (~3):**
- `test_validate_valid_schedule` — all checks pass
- `test_validate_orphaned_trips` — trips referencing non-existent routes
- `test_validate_invalid_time_format` — malformed HH:MM:SS

**Import tests (~2):**
- `test_import_gtfs_success` — verify counts
- `test_import_clears_existing_data`

Each test mocks `AsyncSession` and patches repository methods. Use `AsyncMock` for async methods.

**Per-task validation:**
- `uv run ruff format app/schedules/tests/test_service.py`
- `uv run ruff check --fix app/schedules/tests/test_service.py`
- `uv run pytest app/schedules/tests/test_service.py -v`

---

### Task 11: Create Route Tests
**File:** `app/schedules/tests/test_routes.py` (create new)
**Action:** CREATE

Test API endpoints using mocked service. Follow existing route test patterns.

**Setup:** Mock `ScheduleService` and patch `get_service` dependency.

**Route endpoint tests (~6):**
- `test_list_routes_200` — verify pagination response
- `test_create_route_201` — verify status code and response body
- `test_get_route_200`
- `test_get_route_404` — service raises RouteNotFoundError
- `test_update_route_200`
- `test_delete_route_204`

**Calendar endpoint tests (~4):**
- `test_list_calendars_200`
- `test_create_calendar_201`
- `test_add_exception_201`
- `test_remove_exception_204`

**Trip endpoint tests (~4):**
- `test_list_trips_200`
- `test_create_trip_201`
- `test_get_trip_with_stop_times_200`
- `test_replace_stop_times_200`

**Import endpoint test (~1):**
- `test_import_gtfs_200` — mock file upload

**Validation endpoint test (~1):**
- `test_validate_200`

**Per-task validation:**
- `uv run ruff format app/schedules/tests/test_routes.py`
- `uv run ruff check --fix app/schedules/tests/test_routes.py`
- `uv run pytest app/schedules/tests/test_routes.py -v`

---

### Task 12: Create GTFS Import Tests
**File:** `app/schedules/tests/test_gtfs_import.py` (create new)
**Action:** CREATE

Test the GTFSImporter parsing logic with real GTFS CSV data.

**Create a helper** `_make_gtfs_zip(**files: str) -> bytes` that creates an in-memory ZIP with CSV content for each file (agencies.txt, routes.txt, etc.).

**Tests (~6):**
- `test_parse_agencies` — single agency, verify fields
- `test_parse_routes` — 3 routes with different types
- `test_parse_calendars_and_dates` — weekly pattern + exception dates
- `test_parse_trips` — trips linked to routes and calendars
- `test_parse_stop_times_with_stop_map` — verify stop_id resolved from map
- `test_parse_stop_times_missing_stop_skipped` — unknown stop_id skipped with warning
- `test_missing_agencies_file_creates_default` — ZIP without agencies.txt

**Per-task validation:**
- `uv run ruff format app/schedules/tests/test_gtfs_import.py`
- `uv run ruff check --fix app/schedules/tests/test_gtfs_import.py`
- `uv run pytest app/schedules/tests/test_gtfs_import.py -v`

---

### Task 13: Generate Database Migration
**Action:** Run migration commands

If database is running:
```bash
uv run alembic revision --autogenerate -m "add schedule management tables"
uv run alembic upgrade head
```

If database is NOT running, create migration manually. All column types, FKs, and indexes are fully specified in Task 2 (models.py). Create tables in FK dependency order: agencies -> routes -> calendars -> calendar_dates -> trips -> stop_times.

**Per-task validation:**
- `uv run ruff format alembic/versions/` (if generated)
- Migration file compiles without errors

---

## Logging Events

- `schedules.agency.create_completed` — agency created (gtfs_agency_id, agency_name)
- `schedules.route.create_started/completed/failed` — route CRUD
- `schedules.route.list_completed` — route listing (total, filters)
- `schedules.calendar.create_completed` — calendar created (gtfs_service_id)
- `schedules.trip.create_completed` — trip created (gtfs_trip_id, route_id)
- `schedules.stop_times.replace_completed` — stop_times bulk replaced (trip_id, count)
- `schedules.import_started` — GTFS import initiated
- `schedules.import_completed` — import done (all entity counts, duration)
- `schedules.import_failed` — import error (error message, error type)
- `schedules.validate_completed` — validation results (valid, error_count, warning_count)

## Testing Strategy

### Unit Tests
**Location:** `app/schedules/tests/`
- `test_service.py` — ~23 tests: route/calendar/trip CRUD, validation, import
- `test_routes.py` — ~16 tests: endpoint status codes, response formats, error handling
- `test_gtfs_import.py` — ~7 tests: CSV parsing, field mapping, edge cases

**Estimated total:** ~46 unit tests

### Edge Cases
- GTFS ZIP missing optional files (agencies.txt) — create default agency
- Stop times referencing non-existent stops — skip with warning, count skipped
- Calendar with start_date > end_date — validation error
- Time values exceeding 24:00:00 (overnight trips like "25:30:00") — valid per GTFS spec
- Duplicate gtfs_route_id on create — raise RouteAlreadyExistsError
- Import with empty ZIP — raise GTFSImportError
- Pagination with zero results — return empty PaginatedResponse

## Acceptance Criteria

This feature is complete when:
- [ ] 6 SQLAlchemy models created and migrated (agencies, routes, calendars, calendar_dates, trips, stop_times)
- [ ] ~22 REST endpoints functional (CRUD for all entities + import + validate)
- [ ] GTFS ZIP import parses RS feed and bulk-inserts all entities
- [ ] Stop times reference existing stops table via FK (stops.id)
- [ ] Schedule validation checks referential integrity and time formats
- [ ] All type checkers pass (mypy + pyright) with 0 errors
- [ ] All tests pass (~46 unit tests)
- [ ] Structured logging follows `schedules.{entity}.{action}_{state}` pattern
- [ ] Router registered in `app/main.py`
- [ ] No regressions in existing 377 tests

## Completion Checklist

Before marking this plan as fully executed:
- [ ] All 13 tasks completed in order
- [ ] Per-task validations passed
- [ ] Full validation pyramid passed (Levels 1-4)
- [ ] No deviations from plan (or deviations documented)
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
uv run pytest app/schedules/tests/ -v
```

**Level 4: Full Test Suite (unit)**
```bash
uv run pytest -v -m "not integration"
```

**Level 5: Server Validation (if running)**
```bash
curl -s http://localhost:8123/health
curl -s http://localhost:8123/api/v1/schedules/routes | python -m json.tool
```

**Success definition:** Levels 1-4 exit code 0, all tests pass, zero errors.

## Dependencies

- **Shared:** `PaginationParams`, `PaginatedResponse[T]`, `TimestampMixin`, `utcnow()`, `get_db()`, `get_logger()`, `limiter`
- **Core:** `Base`, `NotFoundError`, `ValidationError`, `DatabaseError`
- **Cross-feature:** `StopRepository` (read-only, for stop_map during import)
- **New packages:** None (zipfile, csv, io are stdlib)
- **pyproject.toml:** Add `"app/schedules/routes.py" = ["ARG001"]` to ruff per-file-ignores

## Known Pitfalls

All CLAUDE.md anti-patterns apply (rules 1-37). Feature-specific pitfalls:

1. **GTFS time as String(8)** — NOT Time column. Values can exceed 24:00:00 for overnight trips.
2. **FK resolution order** — flush() after each entity to get IDs. Order: agencies -> routes -> calendars -> calendar_dates -> trips -> stop_times.
3. **Cross-feature stop_map** — Use `StopRepository(self.db)` (same session). Build `{gtfs_stop_id: id}` dict.
4. **flush() not commit() in bulk** — Service controls transaction. Only commit at end of import.
5. **Reverse FK order for DELETE** — stop_times -> trips -> calendar_dates -> calendars -> routes -> agencies.

## Notes

- GTFS import uses replace strategy (clear + reimport). Merge/upsert can be added later.
- This feature does NOT modify `stops` or `transit`. Agent tools continue using `static_cache.py`.
- Frontend timetable grid will be planned separately via `/fe-planning`.
