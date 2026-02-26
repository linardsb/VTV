# Plan: Dashboard Goals Model — JSONB Goals Field on Events

## Feature Metadata
**Feature Type**: Enhancement
**Estimated Complexity**: Medium
**Primary Systems Affected**: `app/events/` (models, schemas, repository, service, routes, tests)
**Session**: 2 of 4 (depends on Session 1 drag-and-drop fix — completed)

## Feature Description

Add a `goals` JSONB column to the `operational_events` table so the frontend can store structured driver scheduling goals alongside calendar events. When a dispatcher drags a driver card onto a calendar day, the resulting event can include: a route assignment (from the driver's qualified routes), a transport type assignment (bus/trolleybus/tram with optional vehicle number), training objectives, performance notes, and a completable checklist of goal items.

This is the backend data model that Sessions 3 and 4 (frontend dialog and goal visualization) depend on. The design is backward-compatible — existing events without goals return `goals: null`. No new endpoints are added; the existing 5 CRUD endpoints (`GET /`, `GET /{id}`, `POST /`, `PATCH /{id}`, `DELETE /{id}`) are extended to accept and return the goals field.

After this session completes, the TypeScript SDK must be regenerated (`cd cms && pnpm --filter @vtv/sdk refresh`) to expose the new `EventGoals` type to the frontend.

## User Story

As a dispatcher
I want to attach structured goals (route assignment, training objectives, checklist items) to driver scheduling events
So that driver shifts have clear, trackable objectives visible on the dashboard calendar

## Solution Approach

Add a nullable JSONB column `goals` to the existing `operational_events` table. The JSONB value conforms to a `EventGoals` Pydantic schema containing a list of `GoalItem` objects (each with text, completion status, and type classification) plus optional route/transport/vehicle assignment fields.

**Approach Decision:**
We chose a single JSONB column on the existing events table because:
- The goals data is always accessed alongside the event (no independent queries needed)
- JSONB provides schema flexibility for future goal types without migrations
- Backward-compatible: NULL default means existing events work unchanged
- PostgreSQL JSONB supports GIN indexing if query needs arise later

**Alternatives Considered:**
- **Separate `goals` table with FK to events**: Rejected because goals are always fetched with their event (1:1 relationship), separate table adds JOIN overhead and complexity without benefit
- **Storing goals in the `description` text field**: Rejected because it lacks structure, prevents typed frontend rendering, and makes completion tracking impossible

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, logging patterns, type checking requirements
- `app/events/models.py` (lines 1-33) — Current OperationalEvent model, learn column definition pattern
- `app/events/schemas.py` (lines 1-61) — Current schemas with Literal types and model_validator pattern
- `app/events/repository.py` (lines 1-74) — CRUD operations, learn `model_dump()` and `exclude_unset` patterns
- `app/events/service.py` (lines 1-93) — Business logic layer, learn logging pattern
- `app/events/routes.py` (lines 1-102) — Route definitions with auth, rate limiting
- `app/events/exceptions.py` (lines 1-16) — Feature exceptions

### Similar Features (Examples to Follow)
- `app/events/schemas.py` (lines 12-13) — Literal type alias pattern: `PriorityType = Literal[...]`
- `app/events/schemas.py` (lines 34-51) — EventUpdate with `model_validator(mode="before")` for empty body rejection
- `app/events/tests/conftest.py` (lines 1-58) — `make_event()` factory pattern with `**overrides`
- `app/events/tests/test_service.py` (lines 1-155) — Service unit tests with mocked repository
- `app/events/tests/test_routes.py` (lines 1-168) — Route tests with TestClient and dependency overrides

### Files to Modify
- `app/events/schemas.py` — Add GoalItem, EventGoals, TransportType; update EventBase, EventUpdate
- `app/events/models.py` — Add JSONB goals column
- `app/events/repository.py` — No changes needed (model_dump/exclude_unset handles JSONB transparently)
- `app/events/service.py` — No changes needed (passes through schemas unchanged)
- `app/events/routes.py` — No changes needed (schemas handle serialization)
- `app/events/tests/conftest.py` — Update make_event factory
- `app/events/tests/test_service.py` — Add goals-related test cases
- `app/events/tests/test_routes.py` — Add goals-related route tests
- `alembic/versions/` — New migration adding goals column

## Implementation Plan

### Phase 1: Foundation (Tasks 1-2)
Add the Pydantic schemas (`GoalItem`, `EventGoals`) and update existing event schemas to include the `goals` field. This establishes the data contract before touching the database.

### Phase 2: Database (Tasks 3-4)
Add the JSONB column to the SQLAlchemy model and create the Alembic migration. The repository and service layers require NO changes — `model_dump()` serializes Pydantic models to dicts (which JSONB stores natively), and `model_validate()` deserializes JSONB dicts back to Pydantic models.

### Phase 3: Tests (Tasks 5-7)
Update the test factory, add service-level tests for goals CRUD, and add route-level tests for goals in HTTP requests/responses.

### Phase 4: Validation (Task 8)
Run the full validation pyramid to confirm zero regressions.

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.

---

### Task 1: Add GoalItem and EventGoals Schemas
**File:** `app/events/schemas.py` (modify existing)
**Action:** UPDATE

Add the new schemas and type alias BEFORE the existing `EventBase` class. Insert after the existing `CategoryType` definition (line 13):

1. Add a `TransportType` Literal type alias:
   ```python
   TransportType = Literal["bus", "trolleybus", "tram"]
   ```

2. Add `GoalItemType` Literal type alias:
   ```python
   GoalItemType = Literal["route", "training", "note", "checklist"]
   ```

3. Create `GoalItem` schema:
   ```python
   class GoalItem(BaseModel):
       """A single goal or checklist item within an event's goals."""

       text: str = Field(..., min_length=1, max_length=500, description="Goal description text")
       completed: bool = Field(default=False, description="Whether this goal item is completed")
       item_type: GoalItemType = Field(..., description="Goal type: route/training/note/checklist")
   ```
   NOTE: Use `item_type` not `type` — `type` is a Python builtin and causes lint issues in some contexts.

4. Create `EventGoals` schema:
   ```python
   class EventGoals(BaseModel):
       """Structured goals attached to a driver scheduling event."""

       items: list[GoalItem] = Field(default_factory=list, description="List of goal/checklist items")
       route_id: int | None = Field(None, description="Assigned route ID from driver's qualified routes")
       transport_type: TransportType | None = Field(None, description="Assigned transport: bus/trolleybus/tram")
       vehicle_id: str | None = Field(None, max_length=50, description="Optional specific vehicle number")
   ```

**Per-task validation:**
- `uv run ruff format app/events/schemas.py`
- `uv run ruff check --fix app/events/schemas.py` passes
- `uv run mypy app/events/schemas.py` passes with 0 errors
- `uv run pyright app/events/schemas.py` passes with 0 errors

---

### Task 2: Update EventBase, EventUpdate, and EventResponse with Goals Field
**File:** `app/events/schemas.py` (modify existing — same file as Task 1)
**Action:** UPDATE

1. Add `goals` field to `EventBase` (after the `category` field):
   ```python
   goals: EventGoals | None = Field(None, description="Structured goals for driver scheduling")
   ```
   This makes goals available in both `EventCreate` (inherits EventBase) and `EventResponse` (inherits EventBase).

2. Add `goals` field to `EventUpdate` (after the `category` field, before the `model_validator`):
   ```python
   goals: EventGoals | None = None
   ```
   This is optional in PATCH — when not sent, `exclude_unset=True` in the repository skips it. When explicitly sent as `null`, it clears goals.

3. `EventResponse` inherits `EventBase` and already has `model_config = ConfigDict(from_attributes=True)`. When SQLAlchemy returns the JSONB column as a Python dict, Pydantic's `model_validate()` with `from_attributes=True` automatically validates the dict against the `EventGoals` schema. No changes needed to EventResponse beyond what the EventBase inheritance provides.

4. Verify that the existing `reject_empty_body` validator in `EventUpdate` still works. It checks `any(v is not None for v in data.values())`. Sending `{"goals": {...}}` has a non-None value, so it passes. Sending `{"goals": null}` has a None value, but if other fields are also None/missing, it correctly rejects. This is the desired behavior.

**Per-task validation:**
- `uv run ruff format app/events/schemas.py`
- `uv run ruff check --fix app/events/schemas.py` passes
- `uv run mypy app/events/schemas.py` passes with 0 errors
- `uv run pyright app/events/schemas.py` passes with 0 errors

---

### Task 3: Add JSONB Goals Column to OperationalEvent Model
**File:** `app/events/models.py` (modify existing)
**Action:** UPDATE

1. Add the JSONB import. The project uses PostgreSQL 18 via pgvector image. Use the dialect-specific import:
   ```python
   from sqlalchemy.dialects.postgresql import JSONB
   ```

2. Add the `goals` column to the `OperationalEvent` class, after the `category` column:
   ```python
   goals: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True, default=None)
   ```

3. Add the `Any` import:
   ```python
   from typing import Any
   ```

The type annotation uses `dict[str, Any] | None` because SQLAlchemy represents JSONB columns as plain dicts. The Pydantic layer handles the dict → `EventGoals` conversion.

**Per-task validation:**
- `uv run ruff format app/events/models.py`
- `uv run ruff check --fix app/events/models.py` passes
- `uv run mypy app/events/models.py` passes with 0 errors
- `uv run pyright app/events/models.py` passes with 0 errors

---

### Task 4: Create Alembic Migration for Goals Column
**Action:** CREATE migration

**If database is running (preferred):**
```bash
uv run alembic revision --autogenerate -m "add_goals_jsonb_to_events"
uv run alembic upgrade head
```

**If database is NOT running (manual fallback):**
Create a new migration file at `alembic/versions/<hash>_add_goals_jsonb_to_events.py`.

The migration chain head is `6aed7d0b568d` (add_created_by_id_to_calendars). The new migration must set:
```python
down_revision = "6aed7d0b568d"
```

Manual migration body:
```python
def upgrade() -> None:
    """Add goals JSONB column to operational_events table."""
    op.add_column(
        "operational_events",
        sa.Column("goals", sa.dialects.postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    """Remove goals column from operational_events table."""
    op.drop_column("operational_events", "goals")
```

Import requirements for manual migration:
```python
from collections.abc import Sequence
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op
```

If using the dialect import approach in manual mode, the column type should be `postgresql.JSONB()`.

**Per-task validation:**
- `uv run alembic upgrade head` completes without errors (if DB running)
- `uv run alembic check` confirms head is at the latest revision (if DB running)
- If DB not running, verify the migration file has correct `down_revision` and valid `upgrade()`/`downgrade()` functions

---

### Task 5: Update Test Factory and Conftest
**File:** `app/events/tests/conftest.py` (modify existing)
**Action:** UPDATE

1. Update the `make_event()` factory to include a `goals` default of `None`:
   Add `"goals": None` to the `defaults` dict:
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
       "created_at": now,
       "updated_at": now,
   }
   ```
   This ensures all existing tests that call `make_event()` continue to work — they get `goals=None` by default.

2. Add a helper function to create sample goals data for tests:
   ```python
   def make_goals_dict(**overrides: object) -> dict[str, object]:
       """Factory to create a goals dict matching EventGoals schema."""
       defaults: dict[str, object] = {
           "items": [
               {"text": "Complete route familiarization", "completed": False, "item_type": "route"},
               {"text": "Review safety procedures", "completed": True, "item_type": "training"},
           ],
           "route_id": 22,
           "transport_type": "bus",
           "vehicle_id": "RS-1047",
       }
       defaults.update(overrides)
       return defaults
   ```

**Per-task validation:**
- `uv run ruff format app/events/tests/conftest.py`
- `uv run ruff check --fix app/events/tests/conftest.py` passes
- `uv run pytest app/events/tests/ -v` — existing tests still pass

---

### Task 6: Add Service-Level Tests for Goals
**File:** `app/events/tests/test_service.py` (modify existing)
**Action:** UPDATE

Add the following test functions to the end of the file. Import `make_goals_dict` from conftest:

```python
from app.events.tests.conftest import make_event, make_goals_dict
```
Update the existing import line that imports `make_event` to also import `make_goals_dict`.

**Test 1: Create event with goals**
```python
async def test_create_event_with_goals(service):
    now = utcnow()
    goals_data = make_goals_dict()
    data = EventCreate(
        title="Driver Shift - Route 22",
        start_datetime=now,
        end_datetime=now + datetime.timedelta(hours=8),
        priority="medium",
        category="driver-shift",
        goals=goals_data,
    )
    created = make_event(
        id=11,
        title="Driver Shift - Route 22",
        category="driver-shift",
        goals=goals_data,
    )
    service.repository.create = AsyncMock(return_value=created)

    result = await service.create_event(data)
    assert result.id == 11
    assert result.goals is not None
    assert result.goals.route_id == 22
    assert result.goals.transport_type == "bus"
    assert len(result.goals.items) == 2
    assert result.goals.items[0].item_type == "route"
    assert result.goals.items[1].completed is True
```

**Test 2: Create event without goals (backward compat)**
```python
async def test_create_event_without_goals(service):
    now = utcnow()
    data = EventCreate(
        title="Regular Maintenance",
        start_datetime=now,
        end_datetime=now + datetime.timedelta(hours=2),
    )
    created = make_event(id=12, title="Regular Maintenance")
    service.repository.create = AsyncMock(return_value=created)

    result = await service.create_event(data)
    assert result.id == 12
    assert result.goals is None
```

**Test 3: Update event goals**
```python
async def test_update_event_goals(service):
    event = make_event(id=1, goals=None)
    goals_data = make_goals_dict(route_id=7, transport_type="trolleybus")
    updated = make_event(id=1, goals=goals_data)
    data = EventUpdate(goals=goals_data)

    service.repository.get = AsyncMock(return_value=event)
    service.repository.update = AsyncMock(return_value=updated)

    result = await service.update_event(1, data)
    assert result.goals is not None
    assert result.goals.route_id == 7
    assert result.goals.transport_type == "trolleybus"
```

**Test 4: Clear event goals by setting to null**
```python
async def test_clear_event_goals(service):
    goals_data = make_goals_dict()
    event = make_event(id=1, goals=goals_data)
    cleared = make_event(id=1, goals=None)
    data = EventUpdate(goals=None, title="Updated Title")

    service.repository.get = AsyncMock(return_value=event)
    service.repository.update = AsyncMock(return_value=cleared)

    result = await service.update_event(1, data)
    assert result.goals is None
```

**Test 5: GoalItem schema validation**
```python
def test_goal_item_valid():
    from app.events.schemas import GoalItem

    item = GoalItem(text="Complete route review", item_type="route")
    assert item.completed is False
    assert item.item_type == "route"


def test_goal_item_invalid_type():
    from pydantic import ValidationError
    from app.events.schemas import GoalItem

    with pytest.raises(ValidationError):
        GoalItem(text="Test", item_type="invalid")
```

**Test 6: EventGoals schema validation**
```python
def test_event_goals_defaults():
    from app.events.schemas import EventGoals

    goals = EventGoals()
    assert goals.items == []
    assert goals.route_id is None
    assert goals.transport_type is None
    assert goals.vehicle_id is None


def test_event_goals_invalid_transport():
    from pydantic import ValidationError
    from app.events.schemas import EventGoals

    with pytest.raises(ValidationError):
        EventGoals(transport_type="airplane")
```

**Per-task validation:**
- `uv run ruff format app/events/tests/test_service.py`
- `uv run ruff check --fix app/events/tests/test_service.py` passes
- `uv run pytest app/events/tests/test_service.py -v` — all tests pass

---

### Task 7: Add Route-Level Tests for Goals
**File:** `app/events/tests/test_routes.py` (modify existing)
**Action:** UPDATE

Add the following test functions to the end of the file. Import `make_goals_dict` from conftest:

Update the import line to include `make_goals_dict`:
```python
from app.events.tests.conftest import make_event, make_goals_dict
```

**Test 1: Create event with goals via POST**
```python
def test_create_event_with_goals():
    mock_svc = _mock_service()
    goals_data = make_goals_dict()
    resp = _make_response(20, title="Driver Shift", category="driver-shift", goals=goals_data)
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
                "priority": "medium",
                "category": "driver-shift",
                "goals": {
                    "items": [
                        {"text": "Route familiarization", "completed": False, "item_type": "route"},
                    ],
                    "route_id": 22,
                    "transport_type": "bus",
                    "vehicle_id": "RS-1047",
                },
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["goals"] is not None
        assert data["goals"]["route_id"] == 22
        assert data["goals"]["transport_type"] == "bus"
        assert len(data["goals"]["items"]) == 2
    finally:
        app.dependency_overrides.pop(get_service, None)
```

**Test 2: Get event with goals returns goals in response**
```python
def test_get_event_with_goals():
    mock_svc = _mock_service()
    goals_data = make_goals_dict()
    resp = _make_response(1, title="Shift", goals=goals_data)
    mock_svc.get_event = AsyncMock(return_value=resp)
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.get("/api/v1/events/1")
        assert response.status_code == 200
        data = response.json()
        assert data["goals"] is not None
        assert data["goals"]["vehicle_id"] == "RS-1047"
    finally:
        app.dependency_overrides.pop(get_service, None)
```

**Test 3: Create event without goals (backward compat)**
```python
def test_create_event_without_goals_field():
    mock_svc = _mock_service()
    resp = _make_response(21, title="Maintenance")
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
        assert data["goals"] is None
    finally:
        app.dependency_overrides.pop(get_service, None)
```

**Test 4: Update event to add goals via PATCH**
```python
def test_update_event_with_goals():
    mock_svc = _mock_service()
    goals_data = make_goals_dict(route_id=15)
    resp = _make_response(1, title="Inspection", goals=goals_data)
    mock_svc.update_event = AsyncMock(return_value=resp)
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.patch(
            "/api/v1/events/1",
            json={
                "goals": {
                    "items": [],
                    "route_id": 15,
                    "transport_type": "tram",
                },
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["goals"]["route_id"] == 15
    finally:
        app.dependency_overrides.pop(get_service, None)
```

**Test 5: List events includes goals in response**
```python
def test_list_events_includes_goals():
    mock_svc = _mock_service()
    goals_data = make_goals_dict()
    resp1 = _make_response(1, title="With Goals", goals=goals_data)
    resp2 = _make_response(2, title="Without Goals")

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
        assert data["items"][0]["goals"] is not None
        assert data["items"][0]["goals"]["route_id"] == 22
        assert data["items"][1]["goals"] is None
    finally:
        app.dependency_overrides.pop(get_service, None)
```

**Per-task validation:**
- `uv run ruff format app/events/tests/test_routes.py`
- `uv run ruff check --fix app/events/tests/test_routes.py` passes
- `uv run pytest app/events/tests/test_routes.py -v` — all tests pass

---

### Task 8: Full Validation Pyramid
**Action:** Validate the complete implementation.

No router registration changes needed — the events router is already registered in `app/main.py` (line 147). No new dependencies needed. No `.env.example` changes needed.

**Per-task validation:**
Run the full pyramid — all must pass with 0 errors.

## Logging Events

No new logging events are needed. The existing event lifecycle logging in `app/events/service.py` already covers:
- `events.create_started` / `events.create_completed` — goals data flows through transparently
- `events.update_started` / `events.update_completed` — goals updates logged as part of event update
- `events.fetch_started` / `events.fetch_completed` — goals returned in response
- `events.delete_started` / `events.delete_completed` — event with goals deleted

The goals field is stored as JSONB and passed through the service layer without special handling, so no additional logging points are warranted.

## Testing Strategy

### Unit Tests
**Location:** `app/events/tests/test_service.py`
- Create event with goals — verify goals round-trip through service
- Create event without goals — backward compatibility
- Update event to add goals — verify PATCH behavior
- Clear event goals — set goals to null
- GoalItem schema validation — valid types, rejected invalid types
- EventGoals schema defaults — empty items list, null optional fields
- EventGoals invalid transport type — rejected by Literal validation

### Route Tests
**Location:** `app/events/tests/test_routes.py`
- POST with goals — 201, goals in response
- POST without goals — 201, goals is null (backward compat)
- GET single event with goals — goals in response
- PATCH to add goals — 200, goals updated
- GET list with mixed goals — some events have goals, some null

### Edge Cases
- Empty goals object `{}` — valid, all defaults apply (items=[], nulls)
- Goals with empty items list — valid
- Goals with only route_id, no items — valid
- Missing `item_type` on GoalItem — rejected by Pydantic (required field)
- Invalid transport_type — rejected by Literal validation
- GoalItem text exceeding 500 chars — rejected by max_length
- Existing events with NULL goals column — returned as `goals: null` in response

## Acceptance Criteria

This feature is complete when:
- [ ] `EventGoals` and `GoalItem` Pydantic schemas defined with proper validation
- [ ] `TransportType` and `GoalItemType` use `Literal` type aliases
- [ ] `goals` JSONB column added to `OperationalEvent` model (nullable, default None)
- [ ] Alembic migration created and applied
- [ ] `EventCreate` accepts optional `goals` field
- [ ] `EventUpdate` accepts optional `goals` field (PATCH partial update works)
- [ ] `EventResponse` returns `goals` field (null or structured object)
- [ ] Existing events without goals return `goals: null` (backward compatible)
- [ ] All type checkers pass (mypy + pyright)
- [ ] All tests pass (existing + new goals tests)
- [ ] Structured logging follows `domain.component.action_state` pattern
- [ ] No type suppressions added
- [ ] No regressions in existing tests

## Completion Checklist

Before marking this plan as fully executed:
- [ ] All tasks completed in order (Tasks 1-8)
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

- **Shared utilities used**: `TimestampMixin` from `app.shared.models`, `PaginatedResponse`/`PaginationParams` from `app.shared.schemas`
- **Core modules used**: `Base` from `app.core.database`, `get_logger` from `app.core.logging`, `get_db` from `app.core.database`
- **New dependencies**: None — SQLAlchemy already supports JSONB via `sqlalchemy.dialects.postgresql`
- **New env vars**: None

## SDK Regeneration (Post-Implementation)

After backend changes are committed, regenerate the TypeScript SDK so Sessions 3-4 can use the new types:
```bash
cd cms && pnpm --filter @vtv/sdk refresh
```

This will add `EventGoals`, `GoalItem`, `TransportType`, and `GoalItemType` types to `cms/packages/sdk/src/client/types.gen.ts`.

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
7. **Test helper functions need return type annotations** — mypy `disallow_untyped_defs=false` for tests only relaxes *defining* untyped functions, but `disallow_untyped_call` is still globally true. When `async def test_foo()` (implicitly typed via coroutine return) calls an untyped helper, mypy raises `no-untyped-call`. Fix: always add `-> ReturnType` to test helpers (e.g., `def _make_ctx() -> MagicMock:`).
8. **No EN DASH in strings** — Ruff RUF001 forbids ambiguous Unicode characters like `\u2013` (EN DASH). Always use `-` (HYPHEN-MINUS, U+002D).
9. **JSONB column type annotation** — Use `Mapped[dict[str, Any] | None]` for the SQLAlchemy model column. Pydantic handles the dict-to-model conversion in the schema layer via `model_validate()` with `from_attributes=True`.
10. **`model_dump()` serializes nested Pydantic models to dicts** — `EventCreate.model_dump()` converts `goals: EventGoals(...)` to `goals: {"items": [...], "route_id": 22, ...}` which JSONB stores directly. No manual serialization needed.
11. **`exclude_unset=True` preserves PATCH semantics** — `EventUpdate.model_dump(exclude_unset=True)` only includes fields the client actually sent. Not sending `goals` means it won't be touched. Sending `goals: null` explicitly sets it to None.
12. **Schema field additions break ALL consumers** — When adding `goals` to EventBase, verify all constructors of EventCreate, EventUpdate, EventResponse still work. The `goals` field has a default (`None`), so existing constructors that don't pass `goals` will get `None` — no breaking change.
13. **Don't guess `# type: ignore` codes** — Write code WITHOUT ignores, run mypy, read the exact error code, THEN add the precise ignore if needed.
14. **Constrained string fields must use `Literal[...]`** — `TransportType` and `GoalItemType` use Literal for free Pydantic validation and TypeScript union generation.
15. **Partially annotated test functions need `-> None`** — Adding a type annotation to a pytest fixture parameter without a return type triggers mypy `no-untyped-def`. Always specify both param type AND `-> None` return type when any test function parameter is annotated.
16. **`dict.get()` returns the full union type** — When working with JSONB dict data, use proper type narrowing.
17. **JSONB migration uses `postgresql.JSONB()`** — In Alembic migrations, import from `sqlalchemy.dialects.postgresql` not the generic `sa.JSON`.
18. **The `make_event()` factory must include `goals: None`** — Without this default, the factory would not pass the new `goals` attribute to `OperationalEvent(...)`, and existing tests could break when the model expects the field.

## Notes

- **No new endpoints**: The existing 5 CRUD endpoints handle goals transparently through the schema layer
- **No service/repository changes**: The `model_dump()`/`model_validate()` pattern handles JSONB serialization automatically
- **No route changes**: FastAPI's request body parsing handles nested Pydantic models in JSON payloads
- **Future indexing**: If we need to query events by `goals->>'route_id'`, we can add a GIN index on the JSONB column in a future migration without schema changes
- **Session 3 dependency**: The frontend goal dialog (Session 3) requires the TypeScript SDK to be regenerated after this backend work is committed. Run `cd cms && pnpm --filter @vtv/sdk refresh` before starting Session 3
- **Session 4 dependency**: The goal visualization layer (Session 4) reads the `goals` field from the response — no additional backend work needed beyond this session

## Pre-Implementation Checklist

The executing agent MUST verify before writing any code:
- [ ] Read all files listed in "Relevant Files" section
- [ ] Understood the solution approach (JSONB column, schema-level validation, no endpoint changes)
- [ ] Clear on task execution order (schemas first, then model, then migration, then tests)
- [ ] Validation commands are executable in this environment
- [ ] Database is running (check `docker-compose ps` for db service)
