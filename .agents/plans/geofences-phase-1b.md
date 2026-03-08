# Plan: Geofences — Phase 1B

## Feature Metadata
**Feature Type**: New Capability
**Estimated Complexity**: High
**Primary Systems Affected**: `app/geofences/` (new), `app/alerts/` (extension), `app/core/config.py`, `app/main.py`, `app/tests/test_security.py`

## Feature Description

Geofences are geographic zones (polygons) used to detect when fleet vehicles enter, exit, or dwell inside defined areas. This is Phase 1B of the fleet management extension — it depends on Phase 1A (device CRUD + Traccar telemetry ingestion) which is already implemented and flowing vehicle positions into Redis and the `vehicle_positions` hypertable.

The feature introduces a new `app/geofences/` vertical slice with PostGIS Polygon geometry storage, full CRUD for zone management, a background evaluator that periodically checks vehicle positions against active geofences using `ST_Contains`, event logging for enter/exit/dwell transitions, and integration with the existing alerts system to fire alerts on geofence violations.

The evaluator reads live vehicle positions from Redis (the same cache populated by both GTFS-RT pollers and the Traccar webhook bridge), checks each position against all active geofences using PostGIS spatial containment, detects state transitions (enter/exit), calculates dwell time, and creates alert instances via the existing alerts infrastructure when thresholds are exceeded.

## User Story

As a fleet dispatcher
I want to define geographic zones and receive alerts when vehicles enter, exit, or stay too long in those zones
So that I can monitor depot arrivals, detect unauthorized route deviations, and track dwell time at customer sites

## Security Contexts

**Active contexts:**
- **CTX-RBAC**: Feature adds 8 new REST endpoints with role-based access control
- **CTX-INPUT**: Endpoints accept GeoJSON polygon coordinates, search queries, and filter parameters

**Not applicable:**
- CTX-AUTH: No changes to auth/login flow
- CTX-FILE: No file uploads
- CTX-AGENT: No agent tools in this feature
- CTX-INFRA: No Docker/nginx/config changes (PostGIS already available)

## Solution Approach

We implement a full vertical slice following VTV's established patterns, mirroring `app/fleet/` for CRUD and `app/alerts/evaluator.py` for the background evaluation loop.

**Approach Decision:**
We chose PostGIS `ST_Contains` with `Geometry(Polygon, 4326)` because:
- PostGIS is already available (used by `app/stops/` for spatial queries with GeoAlchemy2)
- Server-side spatial containment is more efficient than application-side point-in-polygon
- GIST index on the geometry column enables sub-ms containment checks even with hundreds of zones

**Alternatives Considered:**
- **Application-side Shapely**: Rejected because it requires loading all polygons into memory and doesn't leverage existing PostGIS infrastructure
- **H3 hexagonal indexing**: Rejected as over-engineered for <1000 geofences; PostGIS is simpler and already available

**Background evaluator design:**
We mirror the `app/alerts/evaluator.py` pattern — a background asyncio task started/stopped via the application lifespan. The evaluator reads vehicle positions from Redis (not DB) for low-latency access, then uses PostGIS to check containment. State tracking (which vehicle is in which zone) is maintained in Redis to survive evaluator restarts and enable stateless containment checks.

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, logging patterns, type checking requirements
- `app/core/config.py` (lines 188-205) — Settings pattern for fleet/alerts, add geofence settings here
- `app/core/exceptions.py` — AppError hierarchy (NotFoundError, DomainValidationError)
- `app/core/database.py` — Base class, get_db(), get_db_context()
- `app/shared/schemas.py` — PaginationParams, PaginatedResponse[T], ErrorResponse
- `app/shared/models.py` — TimestampMixin, utcnow()
- `app/shared/utils.py` — escape_like()

### Similar Features (Examples to Follow)
- `app/fleet/models.py` — TrackedDevice model with CheckConstraint pattern (lines 21-30)
- `app/fleet/schemas.py` — Base/Create/Update/Response schema hierarchy (lines 14-95)
- `app/fleet/repository.py` — Repository with CRUD, count, list with filters (lines 15-206)
- `app/fleet/service.py` — Service with structured logging, cross-feature validation (lines 25-235)
- `app/fleet/routes.py` — Router with rate limiting, require_role, get_current_user (lines 26-155)
- `app/fleet/exceptions.py` — Feature exception hierarchy (lines 1-44)
- `app/alerts/evaluator.py` — Background task loop pattern with start/stop lifecycle (lines 179-227)
- `app/alerts/models.py` — AlertRule/AlertInstance models for integration (lines 14-82)
- `app/alerts/repository.py` — AlertInstanceRepository.create() and find_active_duplicate() (lines 141-177)
- `app/alerts/schemas.py` — AlertInstanceCreate schema (lines 71-76)
- `app/stops/models.py` — PostGIS Geometry column with GeoAlchemy2, pyright ignore pattern (lines 8, 32-35)

### Files to Modify
- `app/main.py` — Register geofences_router, start/stop geofence evaluator in lifespan
- `app/core/config.py` — Add geofence evaluator settings
- `app/tests/test_security.py` — No changes needed (all endpoints use JWT auth)

## Implementation Plan

### Phase 1: Foundation
Define schemas, models, and exceptions for the geofence vertical slice. Create the Alembic migration for the `geofences` and `geofence_events` tables with PostGIS geometry columns and GIST indexes.

### Phase 2: Core Implementation
Build the repository, service, and routes layers. Implement CRUD for geofences with GeoJSON input/output, event queries with time range filtering, and dwell time reporting.

### Phase 3: Background Evaluator & Alerts Integration
Create the geofence evaluator background task that reads vehicle positions from Redis, checks containment against active geofences via PostGIS, tracks enter/exit state transitions in Redis, and creates alert instances via the existing alerts system.

### Phase 4: Integration & Validation
Register the router, wire the evaluator lifecycle, update security tests, and run the full validation pyramid.

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.

### Task 1: Create Geofence Schemas
**File:** `app/geofences/schemas.py` (create new)
**Action:** CREATE

Create Pydantic schemas:

- `GeofenceBase(BaseModel)`:
  - `name: str` — Field(max_length=200)
  - `zone_type: Literal["depot", "terminal", "restricted", "customer", "custom"]`
  - `color: str | None` — Field(None, max_length=7, pattern=r"^#[0-9A-Fa-f]{6}$")
  - `alert_on_enter: bool` — default True
  - `alert_on_exit: bool` — default True
  - `alert_on_dwell: bool` — default False
  - `dwell_threshold_minutes: int | None` — Field(None, ge=1, le=1440)
  - `alert_severity: Literal["critical", "high", "medium", "low", "info"]` — default "medium"
  - `description: str | None` — Field(None, max_length=1000)

- `GeofenceCreate(GeofenceBase)`:
  - `coordinates: list[list[float]]` — GeoJSON polygon coordinates (list of [lon, lat] pairs, first=last). Add `@field_validator("coordinates")` to validate: min 4 points, first==last (closed ring), valid lat/lon ranges.

- `GeofenceUpdate(BaseModel)`:
  - All GeofenceBase fields as optional + `coordinates: list[list[float]] | None`
  - `is_active: bool | None`
  - `@model_validator(mode="before")` with `@classmethod` to reject empty PATCH body (anti-pattern #52)

- `GeofenceResponse(GeofenceBase)`:
  - `id: int`
  - `coordinates: list[list[float]]`
  - `is_active: bool`
  - `created_at: datetime`
  - `updated_at: datetime`
  - `model_config = ConfigDict(from_attributes=True)`

- `GeofenceEventResponse(BaseModel)`:
  - `id: int`
  - `geofence_id: int`
  - `geofence_name: str`
  - `vehicle_id: str`
  - `event_type: Literal["enter", "exit", "dwell_exceeded"]`
  - `entered_at: datetime`
  - `exited_at: datetime | None`
  - `dwell_seconds: int | None`
  - `latitude: float`
  - `longitude: float`
  - `created_at: datetime`
  - `model_config = ConfigDict(from_attributes=True)`

- `DwellTimeReport(BaseModel)`:
  - `geofence_id: int`
  - `geofence_name: str`
  - `total_events: int`
  - `avg_dwell_seconds: float`
  - `max_dwell_seconds: int`
  - `vehicles_inside: int`

**Per-task validation:**
- `uv run ruff format app/geofences/schemas.py`
- `uv run ruff check --fix app/geofences/schemas.py`
- `uv run mypy app/geofences/schemas.py`

---

### Task 2: Create Geofence Models
**File:** `app/geofences/models.py` (create new)
**Action:** CREATE

Create SQLAlchemy models:

- `Geofence(Base, TimestampMixin)`:
  - `__tablename__ = "geofences"`
  - `id: Mapped[int]` — primary_key, index
  - `name: Mapped[str]` — String(200), nullable=False, index=True
  - `zone_type: Mapped[str]` — String(20), nullable=False
  - `geometry` — `mapped_column(Geometry("POLYGON", srid=4326), nullable=False)` with `# pyright: ignore[reportUnknownArgumentType]`
  - `color: Mapped[str | None]` — String(7), nullable=True
  - `description: Mapped[str | None]` — Text, nullable=True
  - `alert_on_enter: Mapped[bool]` — default=True, nullable=False
  - `alert_on_exit: Mapped[bool]` — default=True, nullable=False
  - `alert_on_dwell: Mapped[bool]` — default=False, nullable=False
  - `dwell_threshold_minutes: Mapped[int | None]` — Integer, nullable=True
  - `alert_severity: Mapped[str]` — String(20), nullable=False, default="medium"
  - `is_active: Mapped[bool]` — default=True, nullable=False
  - `__table_args__`: CheckConstraint for zone_type IN (...), CheckConstraint for alert_severity IN (...), Index with `postgresql_where=text("is_active = true")` on geometry for spatial queries

- `GeofenceEvent(Base, TimestampMixin)`:
  - `__tablename__ = "geofence_events"`
  - `id: Mapped[int]` — primary_key, index
  - `geofence_id: Mapped[int]` — ForeignKey("geofences.id", ondelete="CASCADE"), index
  - `vehicle_id: Mapped[str]` — String(100), nullable=False, index (string to match Redis vehicle keys)
  - `event_type: Mapped[str]` — String(20), nullable=False
  - `entered_at: Mapped[datetime.datetime]` — DateTime(timezone=True), nullable=False
  - `exited_at: Mapped[datetime.datetime | None]` — DateTime(timezone=True), nullable=True
  - `dwell_seconds: Mapped[int | None]` — Integer, nullable=True
  - `latitude: Mapped[float]` — Float, nullable=False
  - `longitude: Mapped[float]` — Float, nullable=False
  - `__table_args__`: CheckConstraint for event_type IN ('enter', 'exit', 'dwell_exceeded'), Index on (geofence_id, entered_at)

Import `Geometry` from `geoalchemy2` with `# pyright: ignore[reportMissingTypeStubs]` (same pattern as `app/stops/models.py` line 8).

**Per-task validation:**
- `uv run ruff format app/geofences/models.py`
- `uv run ruff check --fix app/geofences/models.py`
- `uv run mypy app/geofences/models.py`

---

### Task 3: Create `__init__.py`
**File:** `app/geofences/__init__.py` (create new)
**Action:** CREATE

Empty `__init__.py` file.

**Per-task validation:**
- File exists

---

### Task 4: Create Geofence Exceptions
**File:** `app/geofences/exceptions.py` (create new)
**Action:** CREATE

Create exception hierarchy mirroring `app/fleet/exceptions.py`:

- `GeofenceError(AppError)` — base
- `GeofenceNotFoundError(NotFoundError)` — `__init__(self, geofence_id: int)`, message: `"Geofence '{geofence_id}' not found"`
- `GeofenceEventNotFoundError(NotFoundError)` — `__init__(self, event_id: int)`
- `GeofenceValidationError(DomainValidationError)` — `__init__(self, message: str)`

Import from `app.core.exceptions`.

**Per-task validation:**
- `uv run ruff format app/geofences/exceptions.py`
- `uv run ruff check --fix app/geofences/exceptions.py`
- `uv run mypy app/geofences/exceptions.py`

---

### Task 5: Create Geofence Repository
**File:** `app/geofences/repository.py` (create new)
**Action:** CREATE

Create `GeofenceRepository` and `GeofenceEventRepository` following `app/fleet/repository.py` patterns.

**`GeofenceRepository`:**
- `__init__(self, db: AsyncSession)` — stores `self.db`
- `async def get(self, geofence_id: int) -> Geofence | None`
- `async def list(self, *, offset, limit, search, zone_type, is_active) -> list[Geofence]` — search on `name` with `escape_like()`, filter by zone_type and is_active
- `async def count(self, *, search, zone_type, is_active) -> int`
- `async def create(self, data: GeofenceCreate, wkt_geometry: str) -> Geofence` — construct Geofence with `geometry=func.ST_GeomFromText(wkt_geometry, 4326)`, add, commit, refresh. Use `from sqlalchemy import func`.
- `async def update(self, geofence: Geofence, data: GeofenceUpdate, wkt_geometry: str | None) -> Geofence` — apply fields from `model_dump(exclude_unset=True, exclude={"coordinates"})`, if wkt_geometry provided set `geofence.geometry = func.ST_GeomFromText(wkt_geometry, 4326)`, commit, refresh
- `async def delete(self, geofence: Geofence) -> None`
- `async def get_active_geofences(self) -> list[Geofence]` — filter is_active=True
- `async def check_containment(self, lat: float, lon: float) -> list[Geofence]` — use `func.ST_Contains(Geofence.geometry, func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326))` with `Geofence.is_active.is_(True)`
- `async def get_coordinates(self, geofence: Geofence) -> list[list[float]]` — use `func.ST_AsGeoJSON(geofence.geometry)` to extract coordinates, parse JSON, return coordinate list

**`GeofenceEventRepository`:**
- `__init__(self, db: AsyncSession)`
- `async def create(self, geofence_id, vehicle_id, event_type, entered_at, latitude, longitude) -> GeofenceEvent`
- `async def get_open_entry(self, geofence_id: int, vehicle_id: str) -> GeofenceEvent | None` — find event with event_type="enter" and exited_at IS NULL
- `async def close_entry(self, event: GeofenceEvent, exited_at: datetime) -> GeofenceEvent` — set exited_at, calculate dwell_seconds, commit
- `async def list_by_geofence(self, geofence_id, *, offset, limit, event_type, start_time, end_time) -> list[GeofenceEvent]`
- `async def count_by_geofence(self, geofence_id, *, event_type, start_time, end_time) -> int`
- `async def list_all(self, *, offset, limit, vehicle_id, event_type, geofence_id, start_time, end_time) -> list[GeofenceEvent]`
- `async def count_all(self, *, vehicle_id, event_type, geofence_id, start_time, end_time) -> int`
- `async def get_dwell_report(self, geofence_id: int, start_time, end_time) -> DwellTimeReport` — use `func.avg`, `func.max`, `func.count` on dwell_seconds for completed events

For spatial functions, add `# pyright: ignore[reportUnknownMemberType]` on GeoAlchemy2 function calls as needed.

**Per-task validation:**
- `uv run ruff format app/geofences/repository.py`
- `uv run ruff check --fix app/geofences/repository.py`
- `uv run mypy app/geofences/repository.py`

---

### Task 6: Create Geofence Service
**File:** `app/geofences/service.py` (create new)
**Action:** CREATE

Create `GeofenceService` following `app/fleet/service.py` patterns:

- `__init__(self, db: AsyncSession)` — init `self.db`, `self.geofence_repo`, `self.event_repo`
- `logger = get_logger(__name__)`

**Helper method:**
- `_coordinates_to_wkt(self, coordinates: list[list[float]]) -> str` — convert `[[lon, lat], ...]` to WKT `POLYGON((lon lat, lon lat, ...))` string

**CRUD methods (all with structured logging):**
- `async def get_geofence(self, geofence_id: int) -> GeofenceResponse` — fetch, raise GeofenceNotFoundError if None, convert geometry to coordinates for response
- `async def list_geofences(self, pagination, *, search, zone_type, is_active) -> PaginatedResponse[GeofenceResponse]` — list+count, convert geometry for each
- `async def create_geofence(self, data: GeofenceCreate) -> GeofenceResponse` — convert coordinates to WKT, create via repo
- `async def update_geofence(self, geofence_id, data: GeofenceUpdate) -> GeofenceResponse` — fetch, validate exists, update
- `async def delete_geofence(self, geofence_id: int) -> None` — fetch, validate, delete

**Event query methods:**
- `async def list_events_by_geofence(self, geofence_id, pagination, *, event_type, start_time, end_time) -> PaginatedResponse[GeofenceEventResponse]` — validate geofence exists, query events
- `async def list_all_events(self, pagination, *, vehicle_id, event_type, geofence_id, start_time, end_time) -> PaginatedResponse[GeofenceEventResponse]`
- `async def get_dwell_report(self, geofence_id, start_time, end_time) -> DwellTimeReport` — validate geofence exists, delegate to repo

For the response conversion, read coordinates from PostGIS via `repo.get_coordinates()` and inject into the response. Use `GeofenceResponse.model_validate(geofence)` — but since `geometry` is a PostGIS binary, you need to manually construct the response dict with coordinates extracted separately.

Logging pattern: `geofences.{action}_started`, `geofences.{action}_completed`, `geofences.{action}_failed`.

**Per-task validation:**
- `uv run ruff format app/geofences/service.py`
- `uv run ruff check --fix app/geofences/service.py`
- `uv run mypy app/geofences/service.py`

---

### Task 7: Create Geofence Routes
**File:** `app/geofences/routes.py` (create new)
**Action:** CREATE

Create FastAPI router at `prefix="/api/v1/geofences"`, tags=`["geofences"]`.

Follow `app/fleet/routes.py` patterns exactly — rate limiter, `Request` param, `_ = request` for ARG001, `Depends(get_service)` with `# noqa: B008`.

**Endpoints (8):**

1. `GET /` — `list_geofences` — `@limiter.limit("30/minute")`, `Depends(get_current_user)`, params: PaginationParams, search (Query, max_length=200), zone_type (Query), is_active (Query)
2. `POST /` — `create_geofence` — `@limiter.limit("10/minute")`, `Depends(require_role("admin", "editor"))`, body: GeofenceCreate, status_code=201
3. `GET /{geofence_id}` — `get_geofence` — `@limiter.limit("30/minute")`, `Depends(get_current_user)`
4. `PATCH /{geofence_id}` — `update_geofence` — `@limiter.limit("10/minute")`, `Depends(require_role("admin", "editor"))`, body: GeofenceUpdate
5. `DELETE /{geofence_id}` — `delete_geofence` — `@limiter.limit("10/minute")`, `Depends(require_role("admin"))`, status_code=204
6. `GET /{geofence_id}/events` — `list_geofence_events` — `@limiter.limit("30/minute")`, `Depends(get_current_user)`, params: PaginationParams, event_type (Query), start_time (Query, datetime), end_time (Query, datetime)
7. `GET /events` — `list_all_events` — `@limiter.limit("30/minute")`, `Depends(get_current_user)`, params: PaginationParams, vehicle_id (Query), event_type (Query), geofence_id (Query), start_time, end_time
8. `GET /{geofence_id}/dwell-report` — `get_dwell_report` — `@limiter.limit("30/minute")`, `Depends(get_current_user)`, params: start_time (Query, datetime), end_time (Query, datetime)

**IMPORTANT:** Route `/events` (list all events) MUST be defined BEFORE `/{geofence_id}` routes to avoid FastAPI treating "events" as a geofence_id path parameter. Place it after the POST but before GET by ID.

Add pyright directives at top: `# pyright: reportUnknownMemberType=false, reportUntypedFunctionDecorator=false`

**Per-task validation:**
- `uv run ruff format app/geofences/routes.py`
- `uv run ruff check --fix app/geofences/routes.py`
- `uv run mypy app/geofences/routes.py`

---

### Task 8: Create Geofence Evaluator
**File:** `app/geofences/evaluator.py` (create new)
**Action:** CREATE

Create background evaluator following `app/alerts/evaluator.py` pattern (lines 179-227).

Add pyright directive: `# pyright: reportUnknownMemberType=false, reportMissingTypeStubs=false, reportArgumentType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false`

**Module-level:**
- `_evaluator_task: asyncio.Task[None] | None = None`
- `logger = get_logger(__name__)`
- `REDIS_VEHICLE_PREFIX = "vehicle:"`
- `REDIS_GEOFENCE_STATE_PREFIX = "geofence_state:"` — tracks which vehicles are inside which zones

**Core function:**
- `async def evaluate_geofences_once() -> int` — returns number of new events created
  1. Get Redis client via `get_redis()`
  2. Scan all `vehicle:*` keys, parse JSON for lat/lon
  3. For each vehicle with valid coordinates, open a DB context (`get_db_context()`)
  4. Use `GeofenceRepository.check_containment(lat, lon)` to get list of geofences containing this point
  5. Get previous state from Redis: `geofence_state:{vehicle_id}` — a JSON set of geofence IDs the vehicle was previously inside
  6. Compare current vs previous:
     - **New entries** (in current, not in previous): create `GeofenceEvent(event_type="enter")`, fire alert if `alert_on_enter`
     - **Exits** (in previous, not in current): close open entry event (set exited_at, dwell_seconds), create exit event, fire alert if `alert_on_exit`
     - **Still inside**: check dwell time — if `alert_on_dwell` and dwell exceeds `dwell_threshold_minutes`, create dwell_exceeded event+alert (once, dedup via alert system)
  7. Update Redis state: `geofence_state:{vehicle_id}` = JSON list of current geofence IDs
  8. Return total new events

**Alert integration:**
- When creating alerts, use `AlertInstanceRepository.find_active_duplicate()` to deduplicate
- Use `AlertInstanceCreate` with:
  - `alert_type="geofence_enter"` / `"geofence_exit"` / `"geofence_dwell"`
  - `source_entity_type="vehicle"`
  - `source_entity_id=vehicle_id`
  - `title=f"Vehicle {vehicle_id} entered zone {geofence.name}"` (or exited/dwell)
  - `severity=geofence.alert_severity`
  - `details={"geofence_id": geofence.id, "geofence_name": geofence.name, "zone_type": geofence.zone_type}`

**Lifecycle functions:**
- `async def _evaluator_loop(interval: int) -> None` — mirror alerts evaluator pattern
- `async def start_geofence_evaluator(settings: Settings) -> None` — check `settings.geofence_evaluator_enabled`, create task
- `async def stop_geofence_evaluator() -> None` — cancel task, handle CancelledError + Exception separately

**Per-task validation:**
- `uv run ruff format app/geofences/evaluator.py`
- `uv run ruff check --fix app/geofences/evaluator.py`
- `uv run mypy app/geofences/evaluator.py`

---

### Task 9: Add Geofence Settings to Config
**File:** `app/core/config.py` (modify existing)
**Action:** UPDATE

Add after the fleet management settings block (after line 205):

```python
    # Geofence evaluator
    geofence_evaluator_enabled: bool = True
    geofence_check_interval_seconds: int = 30
```

**Per-task validation:**
- `uv run ruff format app/core/config.py`
- `uv run ruff check --fix app/core/config.py`
- `uv run mypy app/core/config.py`

---

### Task 10: Create Alembic Migration
**File:** `alembic/versions/e2f3a4b5c6d7_add_geofences_tables.py` (create new)
**Action:** CREATE

**If database is running**, use: `uv run alembic revision --autogenerate -m "add geofences and geofence_events tables"`

**If database is NOT running**, create manually with these specifications:

Revision depends on: `d1e2f3a4b5c6` (the fleet tracking columns migration — latest head).

**upgrade():**
1. Create `geofences` table:
   - `id` INTEGER PRIMARY KEY AUTOINCREMENT
   - `name` VARCHAR(200) NOT NULL
   - `zone_type` VARCHAR(20) NOT NULL
   - `geometry` GEOMETRY(POLYGON, 4326) NOT NULL
   - `color` VARCHAR(7) NULLABLE
   - `description` TEXT NULLABLE
   - `alert_on_enter` BOOLEAN NOT NULL DEFAULT TRUE
   - `alert_on_exit` BOOLEAN NOT NULL DEFAULT TRUE
   - `alert_on_dwell` BOOLEAN NOT NULL DEFAULT FALSE
   - `dwell_threshold_minutes` INTEGER NULLABLE
   - `alert_severity` VARCHAR(20) NOT NULL DEFAULT 'medium'
   - `is_active` BOOLEAN NOT NULL DEFAULT TRUE
   - `created_at` TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
   - `updated_at` TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
   - CHECK constraint: `zone_type IN ('depot', 'terminal', 'restricted', 'customer', 'custom')`
   - CHECK constraint: `alert_severity IN ('critical', 'high', 'medium', 'low', 'info')`
   - INDEX on `name`
   - GIST INDEX on `geometry` WHERE `is_active = true`

2. Create `geofence_events` table:
   - `id` INTEGER PRIMARY KEY AUTOINCREMENT
   - `geofence_id` INTEGER NOT NULL FK -> geofences.id ON DELETE CASCADE
   - `vehicle_id` VARCHAR(100) NOT NULL
   - `event_type` VARCHAR(20) NOT NULL
   - `entered_at` TIMESTAMP WITH TIME ZONE NOT NULL
   - `exited_at` TIMESTAMP WITH TIME ZONE NULLABLE
   - `dwell_seconds` INTEGER NULLABLE
   - `latitude` FLOAT NOT NULL
   - `longitude` FLOAT NOT NULL
   - `created_at` TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
   - `updated_at` TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
   - CHECK constraint: `event_type IN ('enter', 'exit', 'dwell_exceeded')`
   - INDEX on `geofence_id`
   - INDEX on `vehicle_id`
   - INDEX on `(geofence_id, entered_at)`

3. Add new alert rule types to `ck_alert_rules_rule_type` CHECK constraint on `alert_rules` table:
   - ALTER TABLE to drop old constraint, re-create with: `'delay_threshold', 'maintenance_due', 'registration_expiry', 'manual', 'geofence_enter', 'geofence_exit', 'geofence_dwell'`

**downgrade():**
1. Drop `geofence_events` table
2. Drop `geofences` table
3. Restore original alert_rules CHECK constraint (without geofence types)

**Per-task validation:**
- `uv run ruff format alembic/versions/e2f3a4b5c6d7_add_geofences_tables.py`
- `uv run ruff check --fix alembic/versions/e2f3a4b5c6d7_add_geofences_tables.py`
- If DB running: `uv run alembic upgrade head`

---

### Task 11: Create Test Fixtures
**File:** `app/geofences/tests/__init__.py` (create new)
**Action:** CREATE

Empty `__init__.py`.

---

### Task 12: Create Test conftest
**File:** `app/geofences/tests/conftest.py` (create new)
**Action:** CREATE

Create shared fixtures:

- `sample_geofence_create() -> GeofenceCreate` — a polygon around central Riga (approximate: `[[24.10, 56.94], [24.12, 56.94], [24.12, 56.96], [24.10, 56.96], [24.10, 56.94]]`)
- `sample_geofence_update() -> GeofenceUpdate` — partial update (name change)
- `mock_db()` — `AsyncMock(spec=AsyncSession)`
- `geofence_service(mock_db)` — `GeofenceService(mock_db)`

**Per-task validation:**
- `uv run ruff format app/geofences/tests/conftest.py`
- `uv run ruff check --fix app/geofences/tests/conftest.py`

---

### Task 13: Create Service Tests
**File:** `app/geofences/tests/test_service.py` (create new)
**Action:** CREATE

Add pyright directives: `# pyright: reportCallIssue=false, reportUnknownMemberType=false`

Test cases (unit tests, mock DB):

1. `test_create_geofence_success` — happy path, verify repo.create called with WKT
2. `test_get_geofence_not_found` — raises GeofenceNotFoundError
3. `test_list_geofences_empty` — returns empty PaginatedResponse
4. `test_update_geofence_not_found` — raises GeofenceNotFoundError
5. `test_delete_geofence_success` — verify repo.delete called
6. `test_delete_geofence_not_found` — raises GeofenceNotFoundError
7. `test_coordinates_to_wkt` — verify coordinate conversion to WKT POLYGON string
8. `test_create_geofence_with_all_options` — zone_type, color, dwell threshold, severity

**Per-task validation:**
- `uv run ruff format app/geofences/tests/test_service.py`
- `uv run ruff check --fix app/geofences/tests/test_service.py`
- `uv run pytest app/geofences/tests/test_service.py -v`

---

### Task 14: Create Evaluator Tests
**File:** `app/geofences/tests/test_evaluator.py` (create new)
**Action:** CREATE

Add pyright directives: `# pyright: reportCallIssue=false, reportUnknownMemberType=false, reportUnknownVariableType=false`

Test cases (mock Redis + DB):

1. `test_evaluate_no_vehicles` — empty Redis scan, returns 0
2. `test_evaluate_vehicle_enters_geofence` — vehicle at lat/lon inside a zone, no previous state -> creates enter event
3. `test_evaluate_vehicle_exits_geofence` — vehicle was inside (Redis state), now outside -> creates exit event, closes open entry
4. `test_evaluate_dwell_exceeded` — vehicle inside zone, dwell exceeds threshold -> creates dwell_exceeded event
5. `test_evaluate_no_alert_when_disabled` — geofence has alert_on_enter=False, no alert created
6. `test_evaluate_deduplicates_alerts` — active duplicate found, no new alert
7. `test_start_stop_lifecycle` — evaluator starts/stops cleanly
8. `test_evaluate_handles_redis_error` — Redis connection error logged, returns 0

Mock `get_redis()`, `get_db_context()`, and patch repositories.

**Per-task validation:**
- `uv run ruff format app/geofences/tests/test_evaluator.py`
- `uv run ruff check --fix app/geofences/tests/test_evaluator.py`
- `uv run pytest app/geofences/tests/test_evaluator.py -v`

---

### Task 15: Create Route Tests
**File:** `app/geofences/tests/test_routes.py` (create new)
**Action:** CREATE

Add pyright directives: `# pyright: reportCallIssue=false, reportUnknownMemberType=false`

Test cases (mock service):

1. `test_list_geofences_requires_auth` — no token -> 401/403
2. `test_create_geofence_requires_editor` — viewer role -> forbidden
3. `test_create_geofence_success` — editor role, valid payload -> 201
4. `test_delete_geofence_requires_admin` — editor role -> forbidden
5. `test_get_geofence_success` — any authenticated user
6. `test_list_events_success` — with time range filters
7. `test_create_geofence_invalid_coordinates` — unclosed ring -> 422

**Per-task validation:**
- `uv run ruff format app/geofences/tests/test_routes.py`
- `uv run ruff check --fix app/geofences/tests/test_routes.py`
- `uv run pytest app/geofences/tests/test_routes.py -v`

---

### Task 16: Register Router & Wire Evaluator in Lifespan
**File:** `app/main.py` (modify existing)
**Action:** UPDATE

1. Add import at top (among the existing router imports):
   ```python
   from app.geofences.evaluator import start_geofence_evaluator, stop_geofence_evaluator
   from app.geofences.routes import router as geofences_router
   ```

2. In the `lifespan()` function, after `await start_evaluator(settings)` (line 109), add:
   ```python
   await start_geofence_evaluator(settings)
   ```

3. In the shutdown section, after `await stop_evaluator()` (line 120), add:
   ```python
   await stop_geofence_evaluator()
   ```

4. In the router registration section, after `app.include_router(fleet_router)` (line 175), add:
   ```python
   app.include_router(geofences_router)
   ```

**Per-task validation:**
- `uv run ruff format app/main.py`
- `uv run ruff check --fix app/main.py`
- `uv run mypy app/main.py`

---

## Migration

**Prefer autogenerate when database is running:**
```bash
uv run alembic revision --autogenerate -m "add geofences and geofence_events tables"
uv run alembic upgrade head
```

**When database is NOT running:** Manual creation is acceptable. See Task 10 for exact column specifications. Revision must chain from `d1e2f3a4b5c6` (fleet migration head).

## Logging Events

- `geofences.geofence.create_started` / `_completed` / `_failed` — zone CRUD
- `geofences.geofence.fetch_started` / `_completed` / `_failed` — zone lookup
- `geofences.geofence.list_started` / `_completed` — zone listing
- `geofences.geofence.update_started` / `_completed` / `_failed`
- `geofences.geofence.delete_started` / `_completed` / `_failed`
- `geofences.evaluator.cycle_started` / `_completed` / `_failed` — evaluation loop
- `geofences.evaluator.vehicle_entered` — entry detection
- `geofences.evaluator.vehicle_exited` — exit detection
- `geofences.evaluator.dwell_exceeded` — dwell threshold breach
- `geofences.evaluator.lifecycle_started` / `_stopped` / `_skipped`

## Testing Strategy

### Unit Tests
**Location:** `app/geofences/tests/test_service.py`
- GeofenceService CRUD operations (8 tests)
- WKT coordinate conversion

**Location:** `app/geofences/tests/test_evaluator.py`
- Evaluator enter/exit/dwell logic (8 tests)
- Redis state management
- Alert deduplication
- Error handling

**Location:** `app/geofences/tests/test_routes.py`
- Auth/RBAC enforcement (7 tests)
- Input validation

### Edge Cases
- Polygon with exactly 4 points (minimum triangle + closing point) — accepted
- Polygon with 3 points (unclosed) — rejected by schema validator
- Vehicle outside all geofences — no events created
- Multiple vehicles in same geofence — independent tracking
- Geofence deactivated while vehicles inside — next cycle creates exit events
- Redis unavailable — evaluator logs warning, returns 0
- Empty geofence table — evaluator runs but creates no events

## Acceptance Criteria

This feature is complete when:
- [ ] 8 REST endpoints operational with proper RBAC (admin/editor for mutations, authenticated for reads)
- [ ] PostGIS Polygon storage with GIST index for spatial containment queries
- [ ] Background evaluator detects enter/exit/dwell transitions from Redis vehicle positions
- [ ] Alerts integration creates AlertInstance entries for geofence violations via existing alert system
- [ ] ~23 unit tests passing (8 service + 8 evaluator + 7 routes)
- [ ] All type checkers pass (mypy + pyright)
- [ ] Structured logging follows `geofences.component.action_state` pattern
- [ ] No type suppressions added (except GeoAlchemy2 pyright ignores matching stops pattern)
- [ ] Router registered in `app/main.py`
- [ ] Evaluator lifecycle wired in app lifespan (start on startup, stop on shutdown)
- [ ] No regressions in existing 904+ tests
- [ ] Security: all endpoints require auth, RBAC enforced per role matrix

## Completion Checklist

Before marking this plan as fully executed:
- [ ] All 16 tasks completed in order
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
uv run pytest app/geofences/tests/ -v
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

- **Shared utilities used:** PaginationParams, PaginatedResponse[T] (app/shared/schemas), TimestampMixin, utcnow() (app/shared/models), escape_like() (app/shared/utils), get_logger (app/core/logging), get_db, get_db_context (app/core/database), get_redis (app/core/redis), AppError, NotFoundError, DomainValidationError (app/core/exceptions)
- **Core modules used:** Settings (app/core/config), limiter (app/core/rate_limit)
- **Cross-feature reads:** AlertInstanceRepository, AlertInstanceCreate (app/alerts/) for alert creation in evaluator
- **New dependencies:** None — GeoAlchemy2 already installed (used by app/stops/)
- **New env vars:** `GEOFENCE_EVALUATOR_ENABLED` (bool, default True), `GEOFENCE_CHECK_INTERVAL_SECONDS` (int, default 30)

## Known Pitfalls

The executing agent MUST follow all 59 Python anti-pattern rules from `_shared/python-anti-patterns.md`. Key ones for this feature:

- **#8**: No EN DASH in strings — use regular hyphen
- **#18**: ARG001 — `_ = request` in every route handler, `_ = param` for unused params
- **#40**: FastAPI `Query(None)` needs `# noqa: B008`
- **#41**: ILIKE search must use `escape_like()`
- **#52**: Empty PATCH body rejection via `@model_validator(mode="before")` with `@classmethod`
- **#54**: Constrained strings use `Literal[...]` types
- **GeoAlchemy2**: Use same pyright ignore patterns as `app/stops/models.py` — `# pyright: ignore[reportMissingTypeStubs]` on import, `# pyright: ignore[reportUnknownArgumentType]` on Geometry() constructor
- **PostGIS functions**: `func.ST_Contains`, `func.ST_GeomFromText`, `func.ST_AsGeoJSON`, `func.ST_SetSRID`, `func.ST_MakePoint` — all accessed via `sqlalchemy.func`
- **Redis state keys**: Use `geofence_state:{vehicle_id}` pattern, store as JSON string of geofence ID list, set TTL matching vehicle TTL

## Notes

- The evaluator runs on a 30-second default interval. For real-time detection, this could be replaced with a Redis Pub/Sub subscriber (like the WebSocket subscriber) in a future iteration. The polling approach is simpler and consistent with the alerts evaluator pattern.
- GeoJSON coordinates use `[longitude, latitude]` order (RFC 7946). PostGIS WKT also uses `lon lat` order. The schema validator should enforce this.
- The `vehicle_id` in geofence_events is a string matching the Redis vehicle key format (e.g., "4521"), not a database integer FK. This allows tracking both GTFS-RT and hardware vehicles without requiring a vehicles table FK.
- Future enhancement: add GeoJSON MultiPolygon support for complex zone shapes. Current implementation supports Polygon only.

## Pre-Implementation Checklist

The executing agent MUST verify before writing any code:
- [ ] Read all files listed in "Relevant Files" section
- [ ] Understood the solution approach and PostGIS spatial query pattern from stops
- [ ] Clear on evaluator pattern from alerts/evaluator.py
- [ ] Clear on CRUD pattern from fleet/ vertical slice
- [ ] Validation commands are executable in this environment
