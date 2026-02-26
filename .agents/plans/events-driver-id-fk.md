# Plan: Add driver_id Foreign Key to Operational Events + Driver Filter Endpoint

## Feature Metadata
**Feature Type**: Enhancement
**Estimated Complexity**: Medium
**Primary Systems Affected**: events (primary), drivers (read-only cross-feature reference)

## Feature Description

The `operational_events` table currently stores driver references only implicitly via the event title string (e.g., "Uldis Grīnbergs - Apmācība"). This makes it impossible to efficiently query events by driver using database joins or indexes.

This enhancement adds a nullable `driver_id` integer foreign key column to `operational_events` that references `drivers.id`. It also adds a `driver_id` query parameter to the existing `GET /api/v1/events/` list endpoint so the frontend can fetch all events for a specific driver on a given date range. A dedicated convenience endpoint `GET /api/v1/events/by-driver/{driver_id}` is also added for direct driver-event lookups.

The FK is nullable because not all events are driver-specific — maintenance events, service alerts, and route changes may have no associated driver. Existing events with no driver_id will retain `NULL` and remain queryable as before.

## User Story

As a dispatcher using the dashboard calendar
I want to see all operational events assigned to a specific driver
So that I can review their schedule, shift assignments, training sessions, and goal progress for any date range

## Solution Approach

Add `driver_id` as a nullable FK column on `operational_events` referencing `drivers.id`. Use `SET NULL` on delete so that if a driver record is removed, associated events are preserved (they lose the driver reference but retain their content). Add an index on `driver_id` for fast lookups.

Extend the existing list endpoint with an optional `driver_id` query parameter. This leverages the existing pagination, date range filtering, and response format — no new response schema needed. Add a convenience endpoint for direct driver-event queries that returns the same paginated response.

**Approach Decision:**
We chose to add a nullable FK + filter parameter on the existing list endpoint because:
- It follows VTV's existing filter pattern (see `start_date`/`end_date` on the same endpoint)
- It's backward-compatible — existing clients without `driver_id` parameter get the same results
- The dedicated by-driver endpoint provides a clean URL for frontend driver-action panels

**Alternatives Considered:**
- Junction table (many-to-many): Rejected because each event is assigned to at most one driver. A simple FK is sufficient and avoids unnecessary complexity.
- Storing driver_id only in JSONB goals: Rejected because it cannot be indexed or used in efficient SQL JOINs.

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, logging patterns, type checking requirements
- `app/events/models.py` — Current OperationalEvent model (7 columns + TimestampMixin)
- `app/events/schemas.py` — EventBase, EventCreate, EventUpdate, EventResponse, GoalItem, EventGoals
- `app/events/repository.py` — EventRepository with list/count/get/create/update/delete
- `app/events/service.py` — EventService business logic layer
- `app/events/routes.py` — 5 REST endpoints (list, get, create, update, delete)
- `app/events/exceptions.py` — EventNotFoundError
- `app/drivers/models.py` — Driver model with `id` primary key on `drivers` table

### Similar Features (Examples to Follow)
- `app/events/routes.py` (lines 30-45) — Pattern for optional Query parameters on list endpoint
- `app/events/repository.py` (lines 26-41) — Pattern for optional filter in list query
- `app/schedules/routes.py` — Example of FK-based filtering across features (uses `calendar.created_by_id`)
- `alembic/versions/37de45842dd3_add_goals_jsonb_to_events.py` — Latest migration in chain (revision `37de45842dd3`, parent `6aed7d0b568d`)

### Files to Modify
- `app/events/models.py` — Add `driver_id` FK column
- `app/events/schemas.py` — Add `driver_id` to EventBase, EventCreate, EventUpdate, EventResponse
- `app/events/repository.py` — Add `driver_id` filter to list/count, add `list_by_driver` method
- `app/events/service.py` — Thread `driver_id` through list_events, add `list_events_by_driver`
- `app/events/routes.py` — Add `driver_id` query param to list, add by-driver endpoint
- `app/events/tests/conftest.py` — Update `make_event` defaults to include `driver_id`
- `app/events/tests/test_service.py` — Add tests for driver_id filtering
- `app/events/tests/test_routes.py` — Add tests for driver_id query param and by-driver endpoint

### Files NOT to Modify
- `app/main.py` — Events router is already registered; no new router needed
- `app/drivers/` — No changes to the drivers feature; we only read-reference `drivers.id`

## Research Documentation

- SQLAlchemy FK with SET NULL: https://docs.sqlalchemy.org/en/20/core/constraints.html#on-update-and-on-delete
  - Section: "ON UPDATE and ON DELETE"
  - Summary: Use `ForeignKey("drivers.id", ondelete="SET NULL")` for nullable FK that NULLs on parent delete
  - Use for: Task 1 (model definition)

## Implementation Plan

### Phase 1: Foundation (Schema + Model)
Add the FK column to the model and extend all Pydantic schemas with the new optional field. Create the database migration.

### Phase 2: Core Implementation (Repository + Service + Routes)
Thread `driver_id` through the data access layer, business logic layer, and HTTP layer. Add the new by-driver endpoint.

### Phase 3: Testing & Validation
Update existing test fixtures and tests for backward compatibility. Add new tests for driver-id filtering and the by-driver endpoint.

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.

---

### Task 1: Add driver_id FK column to OperationalEvent model
**File:** `app/events/models.py` (modify existing)
**Action:** UPDATE

Add the `driver_id` nullable FK column to the `OperationalEvent` model:

1. Add `ForeignKey` and `Integer` to the SQLAlchemy imports:
   ```python
   from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
   ```

2. Add the `driver_id` column after the existing `goals` column:
   ```python
   driver_id: Mapped[int | None] = mapped_column(
       Integer,
       ForeignKey("drivers.id", ondelete="SET NULL"),
       nullable=True,
       index=True,
   )
   ```

Key details:
- `ondelete="SET NULL"` — if the referenced driver is deleted, events keep their data but lose the driver reference
- `nullable=True` — not all events have a driver (maintenance, service alerts)
- `index=True` — fast lookups when filtering by driver

**Per-task validation:**
- `uv run ruff format app/events/models.py`
- `uv run ruff check --fix app/events/models.py`
- `uv run mypy app/events/models.py`
- `uv run pyright app/events/models.py`

---

### Task 2: Add driver_id to Pydantic schemas
**File:** `app/events/schemas.py` (modify existing)
**Action:** UPDATE

Add `driver_id` as an optional integer field to the relevant schemas.

1. Add `driver_id` to `EventBase` (after the `goals` field):
   ```python
   driver_id: int | None = Field(None, description="Associated driver ID from drivers table")
   ```

2. Add `driver_id` to `EventUpdate` (after the `goals` field):
   ```python
   driver_id: int | None = None
   ```

3. `EventCreate` inherits from `EventBase` so it gets `driver_id` automatically.
4. `EventResponse` inherits from `EventBase` so it gets `driver_id` automatically.

**Schema Impact Tracing:** Grep for `EventCreate(`, `EventUpdate(`, `EventBase(`, `EventResponse(` across the codebase to identify all constructors that may need updating. Since `driver_id` has a default of `None`, existing constructors will NOT break — this is backward-compatible.

**Per-task validation:**
- `uv run ruff format app/events/schemas.py`
- `uv run ruff check --fix app/events/schemas.py`
- `uv run mypy app/events/schemas.py`
- `uv run pyright app/events/schemas.py`

---

### Task 3: Create Alembic migration
**Action:** CREATE migration

**If database is running (preferred):**
```bash
uv run alembic revision --autogenerate -m "add_driver_id_fk_to_events"
uv run alembic upgrade head
```

**If database is NOT running (manual fallback):**
Create a new migration file at `alembic/versions/<auto_id>_add_driver_id_fk_to_events.py`:

```python
"""add_driver_id_fk_to_events

Revision ID: <auto-generated>
Revises: 37de45842dd3
Create Date: <auto-generated>
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "<auto-generated>"
down_revision: str | Sequence[str] | None = "37de45842dd3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add driver_id FK column to operational_events table."""
    op.add_column(
        "operational_events",
        sa.Column("driver_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        op.f("ix_operational_events_driver_id"),
        "operational_events",
        ["driver_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_operational_events_driver_id_drivers",
        "operational_events",
        "drivers",
        ["driver_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Remove driver_id FK column from operational_events table."""
    op.drop_constraint(
        "fk_operational_events_driver_id_drivers",
        "operational_events",
        type_="foreignkey",
    )
    op.drop_index(
        op.f("ix_operational_events_driver_id"),
        table_name="operational_events",
    )
    op.drop_column("operational_events", "driver_id")
```

Column specification:
- `driver_id`: Integer, nullable=True, FK to `drivers.id`, ondelete="SET NULL", indexed

**Per-task validation:**
- `uv run ruff format alembic/versions/*.py`
- `uv run ruff check --fix alembic/versions/*.py`
- If DB is running: `uv run alembic upgrade head` succeeds without errors

---

### Task 4: Add driver_id filter to EventRepository
**File:** `app/events/repository.py` (modify existing)
**Action:** UPDATE

1. Add `driver_id: int | None = None` parameter to the `list` method:

   Update the method signature:
   ```python
   async def list(
       self,
       *,
       offset: int = 0,
       limit: int = 100,
       start_date: datetime.datetime | None = None,
       end_date: datetime.datetime | None = None,
       driver_id: int | None = None,
   ) -> list[OperationalEvent]:
   ```

   Add the filter clause after the existing `end_date` filter:
   ```python
   if driver_id is not None:
       query = query.where(OperationalEvent.driver_id == driver_id)
   ```

2. Add `driver_id: int | None = None` parameter to the `count` method:

   Update the method signature:
   ```python
   async def count(
       self,
       *,
       start_date: datetime.datetime | None = None,
       end_date: datetime.datetime | None = None,
       driver_id: int | None = None,
   ) -> int:
   ```

   Add the filter clause after the existing `end_date` filter:
   ```python
   if driver_id is not None:
       query = query.where(OperationalEvent.driver_id == driver_id)
   ```

The same filter pattern is used for `start_date`/`end_date` — follow the exact same style.

**Per-task validation:**
- `uv run ruff format app/events/repository.py`
- `uv run ruff check --fix app/events/repository.py`
- `uv run mypy app/events/repository.py`
- `uv run pyright app/events/repository.py`

---

### Task 5: Thread driver_id through EventService
**File:** `app/events/service.py` (modify existing)
**Action:** UPDATE

1. Add `driver_id` parameter to `list_events`:

   Update the method signature:
   ```python
   async def list_events(
       self,
       pagination: PaginationParams,
       *,
       start_date: datetime.datetime | None = None,
       end_date: datetime.datetime | None = None,
       driver_id: int | None = None,
   ) -> PaginatedResponse[EventResponse]:
   ```

   Pass `driver_id` to repository calls:
   ```python
   events = await self.repository.list(
       offset=pagination.offset,
       limit=pagination.page_size,
       start_date=start_date,
       end_date=end_date,
       driver_id=driver_id,
   )
   total = await self.repository.count(
       start_date=start_date,
       end_date=end_date,
       driver_id=driver_id,
   )
   ```

   Add `driver_id` to the started log:
   ```python
   logger.info(
       "events.list_started",
       page=pagination.page,
       page_size=pagination.page_size,
       driver_id=driver_id,
   )
   ```

2. Add `list_events_by_driver` convenience method:

   ```python
   async def list_events_by_driver(
       self,
       driver_id: int,
       pagination: PaginationParams,
       *,
       start_date: datetime.datetime | None = None,
       end_date: datetime.datetime | None = None,
   ) -> PaginatedResponse[EventResponse]:
       """List events for a specific driver with pagination and date filters."""
       logger.info("events.list_by_driver_started", driver_id=driver_id, page=pagination.page)
       return await self.list_events(
           pagination, start_date=start_date, end_date=end_date, driver_id=driver_id
       )
   ```

**Per-task validation:**
- `uv run ruff format app/events/service.py`
- `uv run ruff check --fix app/events/service.py`
- `uv run mypy app/events/service.py`
- `uv run pyright app/events/service.py`

---

### Task 6: Add driver_id query param and by-driver endpoint to routes
**File:** `app/events/routes.py` (modify existing)
**Action:** UPDATE

1. Add `driver_id` query parameter to the existing `list_events` endpoint:

   Add after the `end_date` parameter:
   ```python
   driver_id: int | None = Query(None, description="Filter events by driver ID"),  # noqa: B008
   ```

   Pass to service:
   ```python
   return await service.list_events(
       pagination, start_date=start_date, end_date=end_date, driver_id=driver_id
   )
   ```

2. Add the new `by-driver` endpoint BEFORE the `/{event_id}` GET route (to avoid path conflicts where FastAPI would try to parse "by-driver" as an event_id integer):

   ```python
   @router.get("/by-driver/{driver_id}", response_model=PaginatedResponse[EventResponse])
   @limiter.limit("30/minute")
   async def list_events_by_driver(
       request: Request,
       driver_id: int,
       pagination: PaginationParams = Depends(),  # noqa: B008
       start_date: datetime.datetime | None = Query(None),  # noqa: B008
       end_date: datetime.datetime | None = Query(None),  # noqa: B008
       service: EventService = Depends(get_service),  # noqa: B008
       _current_user: User = Depends(get_current_user),  # noqa: B008
   ) -> PaginatedResponse[EventResponse]:
       """List operational events for a specific driver.

       Requires authentication. Supports pagination and date range filters.
       """
       _ = request
       return await service.list_events_by_driver(
           driver_id, pagination, start_date=start_date, end_date=end_date
       )
   ```

**IMPORTANT:** The `by-driver` route MUST be placed BEFORE the `/{event_id}` route in the file. FastAPI routes are matched in registration order. If `/{event_id}` comes first, a request to `/by-driver/5` would try to parse "by-driver" as an integer and return 422.

**Per-task validation:**
- `uv run ruff format app/events/routes.py`
- `uv run ruff check --fix app/events/routes.py`
- `uv run mypy app/events/routes.py`
- `uv run pyright app/events/routes.py`

---

### Task 7: Update test fixtures to include driver_id
**File:** `app/events/tests/conftest.py` (modify existing)
**Action:** UPDATE

1. Update the `make_event` factory defaults dict to include `driver_id`:

   Add `"driver_id": None` to the `defaults` dict (after `"goals": None`):
   ```python
   defaults: dict[str, object] = {
       "id": 1,
       "title": "Bus Fleet Inspection",
       "description": "Quarterly inspection of bus fleet at Depot A",
       "start_datetime": now,
       "end_datetime": now + datetime.timedelta(hours=2),
       "priority": "high",
       "category": "maintenance",
       "goals": None,
       "driver_id": None,
       "created_at": now,
       "updated_at": now,
   }
   ```

This ensures all existing tests continue to work (they don't pass `driver_id` so it defaults to `None`). Tests that need a driver_id can pass `driver_id=5` via overrides.

**Per-task validation:**
- `uv run ruff format app/events/tests/conftest.py`
- `uv run ruff check --fix app/events/tests/conftest.py`
- `uv run pytest app/events/tests/ -v` — all existing tests still pass

---

### Task 8: Add service-level tests for driver_id filtering
**File:** `app/events/tests/test_service.py` (modify existing)
**Action:** UPDATE

Add the following tests at the end of the file (before any closing block):

```python
async def test_list_events_with_driver_filter(service):
    """List events filtered by driver_id."""
    events = [make_event(id=1, driver_id=5)]
    service.repository.list = AsyncMock(return_value=events)
    service.repository.count = AsyncMock(return_value=1)

    pagination = PaginationParams(page=1, page_size=20)
    result = await service.list_events(pagination, driver_id=5)

    assert len(result.items) == 1
    service.repository.list.assert_awaited_once()
    call_kwargs = service.repository.list.call_args.kwargs
    assert call_kwargs["driver_id"] == 5


async def test_list_events_by_driver(service):
    """list_events_by_driver delegates to list_events with driver_id."""
    events = [make_event(id=1, driver_id=10)]
    service.repository.list = AsyncMock(return_value=events)
    service.repository.count = AsyncMock(return_value=1)

    pagination = PaginationParams(page=1, page_size=20)
    result = await service.list_events_by_driver(10, pagination)

    assert len(result.items) == 1
    call_kwargs = service.repository.list.call_args.kwargs
    assert call_kwargs["driver_id"] == 10


async def test_create_event_with_driver_id(service):
    """Create event with driver_id assigned."""
    now = utcnow()
    data = EventCreate(
        title="Driver Shift",
        start_datetime=now,
        end_datetime=now + datetime.timedelta(hours=8),
        category="driver-shift",
        driver_id=7,
    )
    created = make_event(id=20, title="Driver Shift", driver_id=7)
    service.repository.create = AsyncMock(return_value=created)

    result = await service.create_event(data)
    assert result.id == 20
    assert result.driver_id == 7


async def test_create_event_without_driver_id(service):
    """Create event without driver_id (backward compat)."""
    now = utcnow()
    data = EventCreate(
        title="Maintenance",
        start_datetime=now,
        end_datetime=now + datetime.timedelta(hours=2),
    )
    created = make_event(id=21, title="Maintenance", driver_id=None)
    service.repository.create = AsyncMock(return_value=created)

    result = await service.create_event(data)
    assert result.id == 21
    assert result.driver_id is None
```

**Per-task validation:**
- `uv run ruff format app/events/tests/test_service.py`
- `uv run ruff check --fix app/events/tests/test_service.py`
- `uv run pytest app/events/tests/test_service.py -v` — all tests pass

---

### Task 9: Add route-level tests for driver_id
**File:** `app/events/tests/test_routes.py` (modify existing)
**Action:** UPDATE

Add the following tests at the end of the file:

```python
def test_list_events_with_driver_id_filter():
    """GET /api/v1/events/?driver_id=5 filters by driver."""
    mock_svc = _mock_service()
    resp = _make_response(1, title="Driver Shift", driver_id=5)

    mock_svc.list_events = AsyncMock(
        return_value=PaginatedResponse[EventResponse](
            items=[resp], total=1, page=1, page_size=20
        )
    )
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.get("/api/v1/events/?driver_id=5")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["driver_id"] == 5
        # Verify driver_id was passed to service
        mock_svc.list_events.assert_awaited_once()
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_list_events_without_driver_id():
    """GET /api/v1/events/ without driver_id returns all events."""
    mock_svc = _mock_service()
    resp1 = _make_response(1, driver_id=5)
    resp2 = _make_response(2, driver_id=None)

    mock_svc.list_events = AsyncMock(
        return_value=PaginatedResponse[EventResponse](
            items=[resp1, resp2], total=2, page=1, page_size=20
        )
    )
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.get("/api/v1/events/")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_list_events_by_driver_endpoint():
    """GET /api/v1/events/by-driver/5 returns events for driver 5."""
    mock_svc = _mock_service()
    resp = _make_response(1, title="Shift", driver_id=5)

    mock_svc.list_events_by_driver = AsyncMock(
        return_value=PaginatedResponse[EventResponse](
            items=[resp], total=1, page=1, page_size=20
        )
    )
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.get("/api/v1/events/by-driver/5")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["driver_id"] == 5
        mock_svc.list_events_by_driver.assert_awaited_once()
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_list_events_by_driver_with_date_range():
    """GET /api/v1/events/by-driver/5?start_date=...&end_date=... applies both filters."""
    mock_svc = _mock_service()
    resp = _make_response(1, driver_id=5)

    mock_svc.list_events_by_driver = AsyncMock(
        return_value=PaginatedResponse[EventResponse](
            items=[resp], total=1, page=1, page_size=20
        )
    )
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.get(
            "/api/v1/events/by-driver/5"
            "?start_date=2026-03-01T00:00:00Z&end_date=2026-03-31T23:59:59Z"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_create_event_with_driver_id():
    """POST /api/v1/events/ with driver_id creates event linked to driver."""
    mock_svc = _mock_service()
    resp = _make_response(30, title="Driver Shift", driver_id=7, category="driver-shift")
    mock_svc.create_event = AsyncMock(return_value=resp)
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/events/",
            json={
                "title": "Driver Shift",
                "start_datetime": "2026-03-01T06:00:00Z",
                "end_datetime": "2026-03-01T14:00:00Z",
                "category": "driver-shift",
                "driver_id": 7,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["driver_id"] == 7
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_create_event_without_driver_id_backward_compat():
    """POST /api/v1/events/ without driver_id still works (backward compat)."""
    mock_svc = _mock_service()
    resp = _make_response(31, title="Maintenance", driver_id=None)
    mock_svc.create_event = AsyncMock(return_value=resp)
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/events/",
            json={
                "title": "Maintenance",
                "start_datetime": "2026-03-01T08:00:00Z",
                "end_datetime": "2026-03-01T10:00:00Z",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["driver_id"] is None
    finally:
        app.dependency_overrides.pop(get_service, None)
```

Also add the `EventResponse` import check — the existing import `from app.events.schemas import EventResponse` is already present, and `PaginatedResponse` is already imported. No new imports needed for these tests.

**Per-task validation:**
- `uv run ruff format app/events/tests/test_routes.py`
- `uv run ruff check --fix app/events/tests/test_routes.py`
- `uv run pytest app/events/tests/test_routes.py -v` — all tests pass

---

## Migration

**Prefer autogenerate when database is running:**
```bash
uv run alembic revision --autogenerate -m "add_driver_id_fk_to_events"
uv run alembic upgrade head
```

**When database may not be running:** Manual migration creation is an acceptable fallback. The column specification:
- `driver_id`: `Integer`, nullable=True, FK to `drivers.id`, ondelete="SET NULL"
- Index: `ix_operational_events_driver_id` on `driver_id` column
- FK constraint name: `fk_operational_events_driver_id_drivers`
- Parent revision: `37de45842dd3` (add_goals_jsonb_to_events)

## Logging Events

- `events.list_started` — now includes `driver_id` parameter in log context
- `events.list_by_driver_started` — emitted when the by-driver convenience method is called

No new error logging events — the existing `events.list_completed` and `events.fetch_failed` patterns remain unchanged.

## Testing Strategy

### Unit Tests
**Location:** `app/events/tests/test_service.py`
- `test_list_events_with_driver_filter` — verifies driver_id is passed to repository
- `test_list_events_by_driver` — verifies convenience method delegates correctly
- `test_create_event_with_driver_id` — verifies creation with driver_id
- `test_create_event_without_driver_id` — backward compatibility

### Route Tests
**Location:** `app/events/tests/test_routes.py`
- `test_list_events_with_driver_id_filter` — query param parsing
- `test_list_events_without_driver_id` — backward compatibility
- `test_list_events_by_driver_endpoint` — new endpoint
- `test_list_events_by_driver_with_date_range` — combined filters
- `test_create_event_with_driver_id` — POST with driver_id
- `test_create_event_without_driver_id_backward_compat` — POST without driver_id

### Edge Cases
- Event with `driver_id=None` — should be returned when no driver filter is applied
- Event with `driver_id=5` when filtering for `driver_id=10` — should NOT be returned
- Existing events without driver_id — should continue to work after migration
- `by-driver` endpoint with date range — both filters applied simultaneously

## Acceptance Criteria

This feature is complete when:
- [ ] `operational_events` table has a nullable `driver_id` FK to `drivers.id` with SET NULL on delete
- [ ] `GET /api/v1/events/?driver_id=5` filters events by driver
- [ ] `GET /api/v1/events/by-driver/5` returns paginated events for driver 5
- [ ] `POST /api/v1/events/` accepts optional `driver_id` field
- [ ] `PATCH /api/v1/events/{id}` can update `driver_id`
- [ ] EventResponse includes `driver_id` field
- [ ] Existing events without driver_id continue to work (backward compatible)
- [ ] All type checkers pass (mypy + pyright)
- [ ] All tests pass (unit + route)
- [ ] Structured logging follows `domain.component.action_state` pattern
- [ ] No type suppressions added
- [ ] No regressions in existing tests
- [ ] Alembic migration applied successfully

## Completion Checklist

Before marking this plan as fully executed:
- [ ] All tasks completed in order (Tasks 1-9)
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
uv run pytest app/events/tests/ -v
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

- Shared utilities used: `PaginatedResponse`, `PaginationParams` from `app/shared/schemas`, `TimestampMixin`/`utcnow` from `app/shared/models`
- Core modules used: `get_db` from `app/core/database`, `get_logger` from `app/core/logging`, `limiter` from `app/core/rate_limit`
- Cross-feature read: `drivers` table referenced by FK only — no imports from `app/drivers/`
- New dependencies: None
- New env vars: None

## Known Pitfalls

The executing agent MUST follow these rules to avoid common errors:

1. **Route ordering matters** — The `by-driver/{driver_id}` endpoint MUST be placed BEFORE `/{event_id}` in the routes file. FastAPI matches routes in order; `/{event_id}` would capture "by-driver" as a path parameter and return 422.
2. **Nullable FK = Optional field everywhere** — `driver_id` is `int | None` in the model, schemas, and all method signatures. Never make it required.
3. **SET NULL semantics** — When a driver is deleted, `driver_id` becomes NULL on linked events. The events are preserved. Do NOT use CASCADE.
4. **Backward compatibility** — All existing tests construct events without `driver_id`. The conftest `make_event` factory MUST default `driver_id` to `None` so existing tests pass unchanged.
5. **No `assert` in production code** — Ruff S101 forbids assert outside test files. Use conditional checks instead.
6. **No EN DASH in strings** — Ruff RUF001 forbids `–` (U+2013). Use `-` (U+002D).
7. **B008 on Query()** — FastAPI `Query(None)` in function defaults needs `# noqa: B008`.
8. **`app.dependency_overrides` is global** — Test fixtures must save/restore overrides (existing pattern in test_routes.py uses try/finally — follow the same pattern).
9. **Migration parent must be `37de45842dd3`** — This is the latest migration (add_goals_jsonb_to_events). The new migration's `down_revision` must point to it.

## Notes

- **Frontend impact:** After this backend change, the `@vtv/sdk` TypeScript client should be regenerated (`pnpm --filter @vtv/sdk refresh`) to pick up the new `driver_id` field on event types and the `driver_id` query parameter. The `fetchEvents` function in `cms/apps/web/src/lib/events-sdk.ts` can then accept `driver_id` as a filter. This is a separate frontend task.
- **Existing events:** The migration adds a nullable column — all existing events get `driver_id = NULL`. No data backfill is needed for MVP. A future task could parse driver names from event titles and populate `driver_id` retrospectively.
- **OpenAPI schema:** The new query parameter and endpoint will automatically appear in the OpenAPI spec at `/openapi.json`, making them available to the SDK generator and Swagger docs.

## Pre-Implementation Checklist

The executing agent MUST verify before writing any code:
- [ ] Read all files listed in "Relevant Files" section
- [ ] Understood the solution approach and why alternatives were rejected
- [ ] Clear on task execution order (Tasks 1-9)
- [ ] Validation commands are executable in this environment
- [ ] Database is running (check `docker compose ps` for db service)
