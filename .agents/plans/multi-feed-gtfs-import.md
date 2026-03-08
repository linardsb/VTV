# Plan: Multi-Feed GTFS Static Import

## Feature Metadata
**Feature Type**: Enhancement
**Estimated Complexity**: High
**Primary Systems Affected**: schedules, stops, core/config

## Feature Description

The VTV backend already supports multi-feed GTFS-RT polling (vehicle positions, trip updates) via `TransitFeedConfig` with per-feed `feed_id` identifiers, Redis-based caching, and Pub/Sub fan-out. However, the static GTFS data (routes, schedules, calendars, trips, stop times) is currently Riga-only — the database schema uses single-column unique constraints on GTFS IDs (`gtfs_route_id`, `gtfs_trip_id`, `gtfs_service_id`, `gtfs_agency_id`) which means importing a second feed would cause ID collisions (e.g., both Riga and ATD could have `route_id="1"`).

This feature adds `feed_id` scoping to all schedule entities (Agency, Route, Calendar, Trip) so multiple GTFS static feeds can coexist in the same database. The import endpoint gains a required `feed_id` parameter, unique constraints become composite `(feed_id, gtfs_xxx_id)`, and all upsert/lookup operations are scoped by feed. Stops remain globally unique by `gtfs_stop_id` since they represent physical locations shared across operators.

After this change, operators can import GTFS ZIPs from ATD (intercity), Jurmala, and Pieriga alongside the existing Riga data. Each feed's data is isolated by `feed_id`, enabling per-feed export, per-feed queries, and proper GTFS-RT enrichment matching.

## User Story

As a system administrator
I want to import GTFS static data from multiple transit operators (ATD, Jurmala, Pieriga)
So that the schedule tables contain comprehensive Latvia-wide transit data for cross-feed queries and AI agent tools

## Solution Approach

Add a `feed_id` column (`String(50)`, non-nullable) to Agency, Route, Calendar, and Trip models. Change unique constraints from single-column GTFS IDs to composite `(feed_id, gtfs_xxx_id)`. Update all repository bulk_upsert methods to use the new composite constraint names, and scope all GTFS ID lookup maps by `feed_id`. The import endpoint gains a required `feed_id` query parameter that flows through service → repository.

**Approach Decision:**
We chose feed_id column + composite unique constraints because:
- Clean separation: GTFS IDs remain unmodified in the database (no prefixing)
- Correct semantics: feed_id is a first-class attribute, not a string hack
- Query efficiency: composite indexes support both scoped and unscoped queries
- Aligns with existing `TransitFeedConfig.feed_id` used by the RT poller

**Alternatives Considered:**
- **Prefix GTFS IDs** (e.g., "atd:R1"): Rejected because it breaks GTFS-RT matching (RT feeds use unprefixed IDs), pollutes GTFS export, and makes queries awkward
- **Separate databases per feed**: Rejected because it prevents cross-feed queries and complicates the agent tools that need unified data access

**Design Decisions:**
- Stops remain globally unique by `gtfs_stop_id` — stops are physical locations shared across operators. If two feeds reference the same stop, they merge. If they use different IDs for the same location, separate records are created (can be merged later via admin tools)
- `feed_id` defaults to `"riga"` in migration for existing data — zero-downtime for current deployment
- CalendarDate and StopTime do NOT need `feed_id` — they're transitively scoped through their parent Calendar/Trip foreign keys
- Export gains optional `feed_id` filter for per-feed GTFS ZIP generation

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, logging patterns, type checking requirements
- `app/schedules/models.py` (lines 1-138) — All 6 schedule models with current unique constraints
- `app/stops/models.py` (lines 1-43) — Stop model with `gtfs_stop_id` unique constraint (NOT changed)
- `app/core/config.py` (lines 18-28) — `TransitFeedConfig` with `feed_id` field

### Similar Features (Examples to Follow)
- `app/schedules/repository.py` (lines 732-862) — Existing `bulk_upsert_*` methods using `pg_insert` + `on_conflict_do_update` with `index_elements`
- `app/schedules/repository.py` (lines 890-947) — Existing `get_*_gtfs_map` methods and `_existing_gtfs_ids`
- `app/schedules/service.py` (lines 547-766) — Current `import_gtfs` flow with 7-step upsert
- `app/schedules/routes.py` (lines 362-384) — Current import endpoint with streaming upload
- `app/schedules/gtfs_import.py` (lines 30-164) — GTFSParseResult and GTFSImporter.parse()

### Files to Modify
- `app/schedules/models.py` — Add `feed_id` to Agency, Route, Calendar, Trip
- `app/schedules/repository.py` — Scope bulk_upsert and gtfs_map methods by feed_id
- `app/schedules/service.py` — Pass feed_id through import_gtfs and export_gtfs
- `app/schedules/routes.py` — Add feed_id param to import and export endpoints
- `app/schedules/schemas.py` — Add feed_id to GTFSImportResponse and entity responses
- `app/schedules/gtfs_import.py` — Pass feed_id to parsed model instances
- `app/main.py` — No change (router already registered)

## Implementation Plan

### Phase 1: Foundation (Schema + Models + Migration)
Add `feed_id` column to 4 schedule models, update unique constraints from single-column to composite, create Alembic migration with default value for existing data.

### Phase 2: Repository & Import Pipeline
Update all bulk_upsert methods to use composite constraint names, scope all GTFS ID lookup maps by feed_id, thread feed_id through the import service and endpoint.

### Phase 3: Export & Response Schemas
Add feed_id filtering to GTFS export, add feed_id to API response schemas.

### Phase 4: Tests
Update existing tests for feed_id parameter, add multi-feed import test proving two feeds coexist.

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.

---

### Task 1: Update Schedule Models — Add feed_id Column
**File:** `app/schedules/models.py` (modify existing)
**Action:** UPDATE

Add `feed_id` column and update unique constraints for Agency, Route, Calendar, and Trip:

1. Add to **Agency** model (after line 29, the `gtfs_agency_id` field):
   ```python
   feed_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True, default="riga")
   ```
   Change `__table_args__` to replace the single-column unique on `gtfs_agency_id` with a composite:
   ```python
   __table_args__ = (UniqueConstraint("feed_id", "gtfs_agency_id", name="uq_agency_feed_gtfs_id"),)
   ```
   Remove `unique=True` from the `gtfs_agency_id` column definition (keep `index=True`).

2. Add to **Route** model (after line 42, the `gtfs_route_id` field):
   ```python
   feed_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True, default="riga")
   ```
   Add `__table_args__`:
   ```python
   __table_args__ = (UniqueConstraint("feed_id", "gtfs_route_id", name="uq_route_feed_gtfs_id"),)
   ```
   Remove `unique=True` from `gtfs_route_id`.

3. Add to **Calendar** model (after line 62, the `gtfs_service_id` field):
   ```python
   feed_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True, default="riga")
   ```
   Add `__table_args__` (note: Calendar already has none, so add it):
   ```python
   __table_args__ = (UniqueConstraint("feed_id", "gtfs_service_id", name="uq_calendar_feed_gtfs_id"),)
   ```
   Remove `unique=True` from `gtfs_service_id`.

4. Add to **Trip** model (after line 104, the `gtfs_trip_id` field):
   ```python
   feed_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True, default="riga")
   ```
   Add `__table_args__`:
   ```python
   __table_args__ = (UniqueConstraint("feed_id", "gtfs_trip_id", name="uq_trip_feed_gtfs_id"),)
   ```
   Remove `unique=True` from `gtfs_trip_id`.

**IMPORTANT:** The `String` import is already present. `UniqueConstraint` is already imported. Make sure NOT to disturb any existing `__table_args__` on CalendarDate or StopTime — those keep their current constraints.

**Per-task validation:**
- `uv run ruff format app/schedules/models.py`
- `uv run ruff check --fix app/schedules/models.py`
- `uv run mypy app/schedules/models.py`

---

### Task 2: Create Alembic Migration
**File:** `alembic/versions/XXXX_add_feed_id_to_schedule_models.py` (create new)
**Action:** CREATE

Create a migration manually (do NOT use `--autogenerate` as it may not be running against a live DB). The migration must:

1. Add `feed_id` column with server default to each table:
   ```python
   op.add_column("agencies", sa.Column("feed_id", sa.String(50), nullable=False, server_default="riga"))
   op.add_column("routes", sa.Column("feed_id", sa.String(50), nullable=False, server_default="riga"))
   op.add_column("calendars", sa.Column("feed_id", sa.String(50), nullable=False, server_default="riga"))
   op.add_column("trips", sa.Column("feed_id", sa.String(50), nullable=False, server_default="riga"))
   ```

2. Drop old single-column unique constraints/indexes. Use `batch_alter_table` for safety:
   - agencies: drop unique index on `gtfs_agency_id` (index name likely `ix_agencies_gtfs_agency_id` or constraint name from SA)
   - routes: drop unique index on `gtfs_route_id`
   - calendars: drop unique index on `gtfs_service_id`
   - trips: drop unique index on `gtfs_trip_id`

   **IMPORTANT:** To find exact constraint/index names, the executing agent MUST inspect the database or read the initial migration file at `alembic/versions/16befcf37286_initial_schema.py`. Look for `unique=True` on the relevant columns to find the auto-generated index names. SQLAlchemy auto-names unique constraints as `uq_{table}_{column}` or creates unique indexes as `ix_{table}_{column}`.

3. Create new composite unique constraints:
   ```python
   op.create_unique_constraint("uq_agency_feed_gtfs_id", "agencies", ["feed_id", "gtfs_agency_id"])
   op.create_unique_constraint("uq_route_feed_gtfs_id", "routes", ["feed_id", "gtfs_route_id"])
   op.create_unique_constraint("uq_calendar_feed_gtfs_id", "calendars", ["feed_id", "gtfs_service_id"])
   op.create_unique_constraint("uq_trip_feed_gtfs_id", "trips", ["feed_id", "gtfs_trip_id"])
   ```

4. Create indexes on `feed_id` for each table:
   ```python
   op.create_index("ix_agencies_feed_id", "agencies", ["feed_id"])
   op.create_index("ix_routes_feed_id", "routes", ["feed_id"])
   op.create_index("ix_calendars_feed_id", "calendars", ["feed_id"])
   op.create_index("ix_trips_feed_id", "trips", ["feed_id"])
   ```

5. Remove server defaults after backfill (existing rows already have "riga"):
   ```python
   op.alter_column("agencies", "feed_id", server_default=None)
   op.alter_column("routes", "feed_id", server_default=None)
   op.alter_column("calendars", "feed_id", server_default=None)
   op.alter_column("trips", "feed_id", server_default=None)
   ```

6. Write a proper `downgrade()` that reverses all changes.

Use the latest migration revision hash from `alembic/versions/` as the `down_revision`. The most recent is `4f10502b5ce8`. Set `revision` to a new unique hash using `alembic.util.rev_id()` pattern, or hardcode a descriptive one. Use message `"add_feed_id_to_schedule_models"`.

**Per-task validation:**
- `uv run ruff format alembic/versions/*feed_id*.py`
- `uv run ruff check --fix alembic/versions/*feed_id*.py`

---

### Task 3: Update Schemas — Add feed_id to Responses and Import
**File:** `app/schedules/schemas.py` (modify existing)
**Action:** UPDATE

1. Add `feed_id: str` field to **AgencyResponse** (after `gtfs_agency_id`):
   ```python
   feed_id: str
   ```

2. Add `feed_id: str` field to **RouteResponse** (after `gtfs_route_id`):
   ```python
   feed_id: str
   ```

3. Add `feed_id: str` field to **CalendarResponse** (after `gtfs_service_id`):
   ```python
   feed_id: str
   ```

4. Add `feed_id: str` field to **TripResponse** (after `gtfs_trip_id`):
   ```python
   feed_id: str
   ```

5. Add `feed_id: str` field to **GTFSImportResponse** (as the first field):
   ```python
   feed_id: str
   ```

6. **Schema Impact Tracing:** Grep for `GTFSImportResponse(` across the codebase. The only constructor is in `app/schedules/service.py` line ~738 — update it in Task 6. Grep for `AgencyResponse(`, `RouteResponse(`, `CalendarResponse(`, `TripResponse(` — these use `from_attributes=True` so they auto-populate from ORM models (no constructor changes needed, since the models will have `feed_id`).

**Per-task validation:**
- `uv run ruff format app/schedules/schemas.py`
- `uv run ruff check --fix app/schedules/schemas.py`
- `uv run mypy app/schedules/schemas.py`

---

### Task 4: Update GTFSImporter — Accept and Apply feed_id
**File:** `app/schedules/gtfs_import.py` (modify existing)
**Action:** UPDATE

1. Update `GTFSImporter.__init__` to accept `feed_id`:
   ```python
   def __init__(self, zip_data: bytes, feed_id: str) -> None:
       self.zip_data = zip_data
       self.feed_id = feed_id
       self.warnings: list[str] = []
   ```

2. In `_parse_agencies` method: after creating each `Agency` object, set `agency.feed_id = self.feed_id`. The Agency constructor is called around line 200-210. Add `feed_id=self.feed_id` to the Agency() constructor call.

3. In `_parse_routes` method: set `route.feed_id = self.feed_id` on each parsed Route object (around line 250-260).

4. In `_parse_calendars` method: set `calendar.feed_id = self.feed_id` on each parsed Calendar object (around line 300-310).

5. In `_parse_trips` method: set `trip.feed_id = self.feed_id` on each parsed Trip object (around line 390-400).

**Read the actual parse methods** to find the exact lines where model objects are constructed. Add `feed_id=self.feed_id` to each constructor call.

**Per-task validation:**
- `uv run ruff format app/schedules/gtfs_import.py`
- `uv run ruff check --fix app/schedules/gtfs_import.py`
- `uv run mypy app/schedules/gtfs_import.py`

---

### Task 5: Update Repository — Feed-Scoped Upserts and Maps
**File:** `app/schedules/repository.py` (modify existing)
**Action:** UPDATE

This is the most critical task. ALL bulk_upsert methods and GTFS map methods must be updated.

#### 5a. Update `bulk_upsert_agencies` (line ~732)

Change `index_elements=["gtfs_agency_id"]` to `constraint="uq_agency_feed_gtfs_id"`:
```python
stmt = stmt.on_conflict_do_update(
    constraint="uq_agency_feed_gtfs_id",
    set_={c: stmt.excluded[c] for c in update_cols},
)
```

Update `_existing_gtfs_ids` call to also filter by feed_id. Change the method to accept the values list and extract feed_id:
```python
existing_ids = await self._existing_gtfs_ids_for_feed(
    Agency.gtfs_agency_id, Agency.feed_id,
    [v["gtfs_agency_id"] for v in values],
    values[0]["feed_id"],
)
```

Each `values` dict must include `"feed_id"` — this is set by the service layer (Task 6).

#### 5b. Update `bulk_upsert_routes` (line ~760)

Change `index_elements=["gtfs_route_id"]` to `constraint="uq_route_feed_gtfs_id"`.
Update `_existing_gtfs_ids` call similarly.

#### 5c. Update `bulk_upsert_calendars` (line ~796)

Change `index_elements=["gtfs_service_id"]` to `constraint="uq_calendar_feed_gtfs_id"`.
Update `_existing_gtfs_ids` call similarly.

#### 5d. Update `bulk_upsert_trips` (line ~834)

Change `index_elements=["gtfs_trip_id"]` to `constraint="uq_trip_feed_gtfs_id"`.
Update `_existing_gtfs_ids` call similarly. Note this method already loops in batches — update the constraint in the inner loop.

#### 5e. Add `_existing_gtfs_ids_for_feed` method

Add a new method that filters by both GTFS ID and feed_id:
```python
async def _existing_gtfs_ids_for_feed(
    self,
    gtfs_column: InstrumentedAttribute[str],
    feed_column: InstrumentedAttribute[str],
    gtfs_ids: list[str],
    feed_id: str,
) -> set[str]:
    """Find which GTFS IDs already exist for a specific feed."""
    if not gtfs_ids:
        return set()
    ids: set[str] = set()
    for i in range(0, len(gtfs_ids), _BATCH_SIZE):
        batch = gtfs_ids[i : i + _BATCH_SIZE]
        result = await self.db.execute(
            select(gtfs_column).where(
                gtfs_column.in_(batch),
                feed_column == feed_id,
            )
        )
        ids.update(result.scalars().all())
    return ids
```

Keep the old `_existing_gtfs_ids` method — it may still be useful for global lookups.

#### 5f. Update `get_agency_gtfs_map` (line ~890)

Add optional `feed_id` parameter:
```python
async def get_agency_gtfs_map(self, feed_id: str | None = None) -> dict[str, int]:
    query = select(Agency.gtfs_agency_id, Agency.id)
    if feed_id is not None:
        query = query.where(Agency.feed_id == feed_id)
    result = await self.db.execute(query)
    return {row[0]: row[1] for row in result.all()}
```

#### 5g. Update `get_route_gtfs_map` (line ~899)

Same pattern — add optional `feed_id` parameter with `.where(Route.feed_id == feed_id)`.

#### 5h. Update `get_calendar_gtfs_map` (line ~908)

Same pattern — add optional `feed_id` parameter with `.where(Calendar.feed_id == feed_id)`.

#### 5i. Update `get_trip_gtfs_map` (line ~917)

Same pattern — add optional `feed_id` parameter with `.where(Trip.feed_id == feed_id)`.

#### 5j. Update `list_all_*` export methods (optional feed_id filter)

Update `list_all_agencies`, `list_all_routes`, `list_all_calendars`, `list_all_calendar_dates`, `list_all_trips` to accept optional `feed_id: str | None = None` and filter when provided. For `list_all_calendar_dates`, filter via a join or subquery on Calendar.feed_id. For `list_all_trips`, filter via Trip.feed_id.

**Per-task validation:**
- `uv run ruff format app/schedules/repository.py`
- `uv run ruff check --fix app/schedules/repository.py`
- `uv run mypy app/schedules/repository.py`

---

### Task 6: Update Service — Thread feed_id Through Import
**File:** `app/schedules/service.py` (modify existing)
**Action:** UPDATE

#### 6a. Update `import_gtfs` signature (line ~547)

Add `feed_id` parameter:
```python
async def import_gtfs(self, zip_data: bytes, feed_id: str) -> GTFSImportResponse:
```

#### 6b. Pass feed_id to GTFSImporter (line ~574)

```python
importer = GTFSImporter(zip_data, feed_id=feed_id)
```

#### 6c. Add feed_id to all upsert value dicts

For agencies (line ~602-613), add `"feed_id": feed_id` to each dict in `agency_values`.
For routes (line ~623-636), add `"feed_id": feed_id` to each dict in `route_values`.
For calendars (line ~645-658), add `"feed_id": feed_id` to each dict in `calendar_values`.
For trips (line ~689-700), add `"feed_id": feed_id` to each dict in `trip_values`.

#### 6d. Scope GTFS map reloads by feed_id

Change map reload calls to pass feed_id:
```python
agency_map = await self.repository.get_agency_gtfs_map(feed_id=feed_id)
# ... later ...
calendar_map = await self.repository.get_calendar_gtfs_map(feed_id=feed_id)
# ... later ...
route_map = await self.repository.get_route_gtfs_map(feed_id=feed_id)
# ... later ...
trip_map = await self.repository.get_trip_gtfs_map(feed_id=feed_id)
```

#### 6e. Add feed_id to GTFSImportResponse constructor (line ~738)

Add `feed_id=feed_id` as first kwarg:
```python
return GTFSImportResponse(
    feed_id=feed_id,
    agencies_count=len(result.agencies),
    ...
)
```

#### 6f. Add feed_id to logging context

Update the `schedules.import_started` and `schedules.import_completed` log events:
```python
logger.info("schedules.import_started", feed_id=feed_id)
# ... and in import_completed:
logger.info("schedules.import_completed", feed_id=feed_id, ...)
```

#### 6g. Update `export_gtfs` signature (line ~835)

Add optional `feed_id` parameter:
```python
async def export_gtfs(self, agency_id: int | None = None, feed_id: str | None = None) -> bytes:
```

Pass `feed_id` to the repository's `list_all_*` methods:
```python
agencies = await self.repository.list_all_agencies(feed_id=feed_id)
routes = await self.repository.list_all_routes(agency_id=agency_id, feed_id=feed_id)
calendars = await self.repository.list_all_calendars(feed_id=feed_id)
calendar_dates = await self.repository.list_all_calendar_dates(feed_id=feed_id)
# trips and stop_times are already filtered through route_ids
trips = await self.repository.list_all_trips(route_ids=route_ids, feed_id=feed_id)
```

**Per-task validation:**
- `uv run ruff format app/schedules/service.py`
- `uv run ruff check --fix app/schedules/service.py`
- `uv run mypy app/schedules/service.py`

---

### Task 7: Update Routes — Add feed_id to Import and Export Endpoints
**File:** `app/schedules/routes.py` (modify existing)
**Action:** UPDATE

#### 7a. Update import endpoint (line ~362)

Add `feed_id` as a required query parameter:
```python
@router.post("/import", response_model=GTFSImportResponse)
@limiter.limit("5/minute")
async def import_gtfs(
    request: Request,
    file: UploadFile,
    feed_id: str = Query(..., min_length=1, max_length=50, pattern=r"^[\w\-]+$"),  # noqa: B008
    service: ScheduleService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(require_role("admin", "editor")),  # noqa: B008
) -> GTFSImportResponse:
```

Pass to service:
```python
return await service.import_gtfs(zip_data, feed_id=feed_id)
```

#### 7b. Update export endpoint (line ~344)

Add optional `feed_id` query parameter:
```python
@router.get("/export")
@limiter.limit("5/minute")
async def export_gtfs(
    request: Request,
    agency_id: int | None = Query(None),
    feed_id: str | None = Query(None, min_length=1, max_length=50, pattern=r"^[\w\-]+$"),  # noqa: B008
    service: ScheduleService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(get_current_user),  # noqa: B008
) -> Response:
```

Pass to service:
```python
zip_bytes = await service.export_gtfs(agency_id=agency_id, feed_id=feed_id)
```

#### 7c. Update list_agencies endpoint

Add optional `feed_id` query filter to `list_agencies`:
```python
async def list_agencies(
    request: Request,
    feed_id: str | None = Query(None, max_length=50),  # noqa: B008
    service: ScheduleService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(get_current_user),  # noqa: B008
) -> list[AgencyResponse]:
```

This requires updating `ScheduleService.list_agencies` and `ScheduleRepository.list_agencies` to accept optional `feed_id`. Add `.where(Agency.feed_id == feed_id)` filter when provided.

#### 7d. Update list_routes endpoint

Add optional `feed_id` query parameter to `list_routes`. Thread through service → repository. Add `.where(Route.feed_id == feed_id)` when provided.

**Per-task validation:**
- `uv run ruff format app/schedules/routes.py`
- `uv run ruff check --fix app/schedules/routes.py`
- `uv run mypy app/schedules/routes.py`

---

### Task 8: Update Service List Methods — Feed Filtering
**File:** `app/schedules/service.py` (modify existing)
**Action:** UPDATE

Add optional `feed_id: str | None = None` parameter to:
- `list_agencies(self, feed_id: str | None = None)` — pass to repository
- `list_routes(self, pagination, ..., feed_id: str | None = None)` — pass to repository

**Per-task validation:**
- `uv run ruff format app/schedules/service.py`
- `uv run ruff check --fix app/schedules/service.py`
- `uv run mypy app/schedules/service.py`

---

### Task 9: Update Repository List Methods — Feed Filtering
**File:** `app/schedules/repository.py` (modify existing)
**Action:** UPDATE

Add optional `feed_id: str | None = None` parameter to:
- `list_agencies(self, feed_id: str | None = None)` — add `.where(Agency.feed_id == feed_id)` when not None
- `list_routes(self, ..., feed_id: str | None = None)` — add filter
- `count_routes(self, ..., feed_id: str | None = None)` — add filter

**Per-task validation:**
- `uv run ruff format app/schedules/repository.py`
- `uv run ruff check --fix app/schedules/repository.py`
- `uv run mypy app/schedules/repository.py`

---

### Task 10: Update Existing Tests — Add feed_id
**File:** `app/schedules/tests/test_gtfs_import.py` (modify existing)
**Action:** UPDATE

Read this file first. Update all `GTFSImporter(zip_data)` calls to `GTFSImporter(zip_data, feed_id="test")`.

**Per-task validation:**
- `uv run ruff format app/schedules/tests/test_gtfs_import.py`
- `uv run ruff check --fix app/schedules/tests/test_gtfs_import.py`
- `uv run pytest app/schedules/tests/test_gtfs_import.py -v`

---

### Task 11: Update Service Tests — Add feed_id
**File:** `app/schedules/tests/test_service.py` (modify existing)
**Action:** UPDATE

Read this file first. Update:
1. All `service.import_gtfs(zip_data)` calls to `service.import_gtfs(zip_data, feed_id="test")`
2. All mock/fixture Agency, Route, Calendar, Trip objects to include `feed_id="test"`
3. All `GTFSImportResponse(...)` assertions to include `feed_id="test"`
4. All `AgencyResponse(...)`, `RouteResponse(...)`, `CalendarResponse(...)`, `TripResponse(...)` assertions to include `feed_id`

**Per-task validation:**
- `uv run ruff format app/schedules/tests/test_service.py`
- `uv run ruff check --fix app/schedules/tests/test_service.py`
- `uv run pytest app/schedules/tests/test_service.py -v`

---

### Task 12: Update Route Tests — Add feed_id
**File:** `app/schedules/tests/test_routes.py` (modify existing)
**Action:** UPDATE

Read this file first. Update:
1. Import test calls to include `feed_id` query param: `?feed_id=test`
2. Mock service responses to include `feed_id`
3. Assertion checks for `feed_id` in responses

**Per-task validation:**
- `uv run ruff format app/schedules/tests/test_routes.py`
- `uv run ruff check --fix app/schedules/tests/test_routes.py`
- `uv run pytest app/schedules/tests/test_routes.py -v`

---

### Task 13: Update GTFS Export Tests — Add feed_id
**File:** `app/schedules/tests/test_gtfs_export.py` (modify existing)
**Action:** UPDATE

Read this file first. Update mock model objects to include `feed_id="test"` attribute.

**Per-task validation:**
- `uv run ruff format app/schedules/tests/test_gtfs_export.py`
- `uv run ruff check --fix app/schedules/tests/test_gtfs_export.py`
- `uv run pytest app/schedules/tests/test_gtfs_export.py -v`

---

### Task 14: Update Conftest Fixtures — Add feed_id
**File:** `app/schedules/tests/conftest.py` (modify existing)
**Action:** UPDATE

Read this file first. Add `feed_id="test"` to all Agency, Route, Calendar, Trip fixtures and factory functions.

**Per-task validation:**
- `uv run ruff format app/schedules/tests/conftest.py`
- `uv run ruff check --fix app/schedules/tests/conftest.py`

---

### Task 15: Add Multi-Feed Import Test
**File:** `app/schedules/tests/test_multi_feed_import.py` (create new)
**Action:** CREATE

Create a focused test file proving multi-feed isolation:

```python
"""Tests for multi-feed GTFS import — verifying feed isolation."""
import pytest

from app.schedules.gtfs_import import GTFSImporter


class TestMultiFeedParsing:
    """Verify GTFSImporter applies feed_id to all parsed entities."""

    def test_importer_sets_feed_id_on_agencies(self, sample_gtfs_zip: bytes) -> None:
        """Agencies parsed from ZIP have the specified feed_id."""
        importer = GTFSImporter(sample_gtfs_zip, feed_id="atd")
        result = importer.parse(stop_map={})
        for agency in result.agencies:
            assert agency.feed_id == "atd"

    def test_importer_sets_feed_id_on_routes(self, sample_gtfs_zip: bytes) -> None:
        """Routes parsed from ZIP have the specified feed_id."""
        importer = GTFSImporter(sample_gtfs_zip, feed_id="jurmala")
        result = importer.parse(stop_map={})
        for route in result.routes:
            assert route.feed_id == "jurmala"

    def test_importer_sets_feed_id_on_calendars(self, sample_gtfs_zip: bytes) -> None:
        """Calendars parsed from ZIP have the specified feed_id."""
        importer = GTFSImporter(sample_gtfs_zip, feed_id="pieriga")
        result = importer.parse(stop_map={})
        for calendar in result.calendars:
            assert calendar.feed_id == "pieriga"

    def test_importer_sets_feed_id_on_trips(self, sample_gtfs_zip: bytes) -> None:
        """Trips parsed from ZIP have the specified feed_id."""
        importer = GTFSImporter(sample_gtfs_zip, feed_id="atd")
        result = importer.parse(stop_map={})
        for trip in result.trips:
            assert trip.feed_id == "atd"

    def test_different_feeds_same_gtfs_ids(self, sample_gtfs_zip: bytes) -> None:
        """Two feeds can produce entities with identical GTFS IDs but different feed_ids."""
        result_riga = GTFSImporter(sample_gtfs_zip, feed_id="riga").parse(stop_map={})
        result_atd = GTFSImporter(sample_gtfs_zip, feed_id="atd").parse(stop_map={})

        # Same GTFS IDs, different feed_ids
        assert result_riga.agencies[0].gtfs_agency_id == result_atd.agencies[0].gtfs_agency_id
        assert result_riga.agencies[0].feed_id == "riga"
        assert result_atd.agencies[0].feed_id == "atd"
```

The test uses `sample_gtfs_zip` fixture from conftest — read `conftest.py` to find or create it. If it doesn't exist, create a minimal GTFS ZIP fixture with agency.txt, routes.txt, calendar.txt, trips.txt, stop_times.txt.

**Per-task validation:**
- `uv run ruff format app/schedules/tests/test_multi_feed_import.py`
- `uv run ruff check --fix app/schedules/tests/test_multi_feed_import.py`
- `uv run pytest app/schedules/tests/test_multi_feed_import.py -v`

---

### Task 16: Update Cross-Feature Consumers — Security Tests and Others
**File:** Multiple files (modify existing)
**Action:** UPDATE

Grep across the codebase for breaking references:

1. `Grep for "AgencyResponse(" in app/` — update any manual constructors to include `feed_id`
2. `Grep for "RouteResponse(" in app/` — update any manual constructors
3. `Grep for "CalendarResponse(" in app/` — update any manual constructors
4. `Grep for "TripResponse(" in app/` — update any manual constructors
5. `Grep for "GTFSImportResponse(" in app/` — update constructors (main one is in service.py, handled in Task 6)
6. Check `app/tests/test_security.py` for schedule-related assertions
7. Check `app/compliance/` for any schedule model usage
8. Check `app/analytics/` for any schedule model usage
9. Check `app/core/agents/tools/transit/static_store.py` for schedule model queries — if it queries Agency, Route, Calendar, or Trip models, it may need feed_id awareness. For now, do NOT change the static_store — it loads all feeds' data into a single cache, which is the correct behavior for agent tools that query across feeds.

**Per-task validation:**
- `uv run ruff format .`
- `uv run ruff check --fix .`
- `uv run mypy app/`

---

### Task 17: Update .env.example
**File:** `.env.example` (modify existing)
**Action:** UPDATE

Add a comment near the TRANSIT_FEEDS_JSON section documenting the feed_id requirement for static import:

```bash
# Multi-feed GTFS static import: POST /api/v1/schedules/import?feed_id=riga
# Each feed_id should match the TransitFeedConfig.feed_id for GTFS-RT correlation
# Available feeds: riga, atd, jurmala, pieriga
```

**Per-task validation:**
- No linting needed for .env files

---

## Migration Details

**Column additions (all tables):**
- `feed_id`: `String(50)`, nullable=False, server_default="riga" (removed after backfill)

**Constraint changes:**
| Table | Drop | Create |
|-------|------|--------|
| agencies | unique on `gtfs_agency_id` | `uq_agency_feed_gtfs_id (feed_id, gtfs_agency_id)` |
| routes | unique on `gtfs_route_id` | `uq_route_feed_gtfs_id (feed_id, gtfs_route_id)` |
| calendars | unique on `gtfs_service_id` | `uq_calendar_feed_gtfs_id (feed_id, gtfs_service_id)` |
| trips | unique on `gtfs_trip_id` | `uq_trip_feed_gtfs_id (feed_id, gtfs_trip_id)` |

**Index additions:**
- `ix_agencies_feed_id`, `ix_routes_feed_id`, `ix_calendars_feed_id`, `ix_trips_feed_id`

## Logging Events

- `schedules.import_started` — now includes `feed_id` context
- `schedules.import_completed` — now includes `feed_id` context
- `schedules.import_failed` — now includes `feed_id` context (if available)

## Testing Strategy

### Unit Tests
**Location:** `app/schedules/tests/`
- GTFSImporter — verify `feed_id` propagated to all parsed models
- Repository bulk_upsert — verify composite constraint used (mocked DB)
- Service import_gtfs — verify `feed_id` threaded through all steps
- Route import endpoint — verify `feed_id` query param required and validated

### Integration Tests
**Location:** `app/schedules/tests/test_multi_feed_import.py`
**Mark with:** `@pytest.mark.integration`
- Import two feeds with overlapping GTFS IDs — both coexist
- Export filtered by feed_id — only that feed's data exported
- List routes/agencies filtered by feed_id — correct scoping

### Edge Cases
- Import with `feed_id=""` — rejected by `min_length=1` validation
- Import with `feed_id` containing special chars — rejected by `pattern=r"^[\w\-]+$"`
- Import same feed_id twice — upserts (updates existing, creates new)
- Export with invalid feed_id — returns empty ZIP (no data matches)
- Existing data without feed_id — migration sets "riga" default

## Acceptance Criteria

This feature is complete when:
- [ ] `POST /api/v1/schedules/import?feed_id=riga` works as before (backward compatible)
- [ ] `POST /api/v1/schedules/import?feed_id=atd` imports ATD data alongside Riga
- [ ] Two feeds with overlapping GTFS IDs coexist without constraint violations
- [ ] `GET /api/v1/schedules/export?feed_id=riga` exports only Riga data
- [ ] `GET /api/v1/schedules/agencies?feed_id=atd` returns only ATD agencies
- [ ] `GET /api/v1/schedules/routes?feed_id=atd` returns only ATD routes
- [ ] All type checkers pass (mypy + pyright)
- [ ] All tests pass (unit + integration)
- [ ] Structured logging includes feed_id context
- [ ] No type suppressions added
- [ ] No regressions in existing tests

## Completion Checklist

Before marking this plan as fully executed:
- [ ] All tasks completed in order
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
uv run pytest app/schedules/tests/ -v
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

- Shared utilities used: `PaginationParams`, `PaginatedResponse`, `TimestampMixin`, `escape_like`
- Core modules used: `get_db`, `get_logger`, `get_settings`, `limiter`
- New dependencies: None
- New env vars: None (feed_id is a per-request parameter, not a config var)

## Known Pitfalls

The executing agent MUST follow all 59 Python anti-pattern rules from `@_shared/python-anti-patterns.md`.

**Specific risks for this task:**

1. **Schema field additions break ALL consumers (rule #11):** Adding `feed_id` to response schemas means ALL places that construct those schemas must be updated. Grep for `SchemaName(` before editing. The ORM `from_attributes=True` auto-populates from models, but any manual constructors in tests or service code need updating.

2. **Migration constraint names must match model `__table_args__`:** The `name="uq_agency_feed_gtfs_id"` in the model must exactly match the constraint name in the migration. A mismatch causes `on_conflict_do_update(constraint=...)` to fail at runtime.

3. **Import order matters for `on_conflict_do_update`:** The `constraint` parameter uses the constraint NAME (string), not `index_elements`. This is because composite unique constraints can't be specified as `index_elements` in PostgreSQL's `INSERT ... ON CONFLICT`.

4. **Stop model is NOT changed:** Stops remain globally unique by `gtfs_stop_id`. Do NOT add `feed_id` to the Stop model or its repository. Cross-feed stop sharing is by design.

5. **`feed_id` query parameter validation:** Use `pattern=r"^[\w\-]+$"` to prevent injection. Match the pattern used by the transit routes endpoint (see `app/transit/routes.py` line 28).

6. **Test fixtures must include `feed_id`:** After adding `feed_id` to models with `nullable=False`, ALL test fixtures creating Agency/Route/Calendar/Trip objects must include `feed_id="test"` or the DB will reject them.

7. **CalendarDate and StopTime do NOT get `feed_id`:** These are transitively scoped through their parent FK. Adding `feed_id` to them would be redundant and violate normalization.

## Notes

- **Future work — static_store:** The `GTFSStaticStore` (`app/core/agents/tools/transit/static_store.py`) loads GTFS data from DB into memory for agent tools. Currently it loads all data regardless of feed. After this migration, it will automatically include multi-feed data, which is correct for cross-feed agent queries. If per-feed agent scoping is needed later, that's a separate enhancement.

- **Future work — auto-import:** This plan covers manual ZIP upload per feed. A future enhancement could add scheduled auto-import from feed URLs (using `TransitFeedConfig.static_url`) via a background task, similar to how the RT poller works.

- **Future work — feed management:** Feed definitions live in `TransitFeedConfig` (config.py). A future CRUD API for feed management could be added, but is out of scope here.

- **GTFS-RT correlation:** The `feed_id` used in static import SHOULD match the `TransitFeedConfig.feed_id` used for RT polling. This enables the RT poller's enrichment logic to look up the correct feed's static data. However, this correlation is not enforced — it's the admin's responsibility to use matching feed_ids.

## Pre-Implementation Checklist

The executing agent MUST verify before writing any code:
- [ ] Read all files listed in "Relevant Files" section
- [ ] Reviewed the migration section and understand constraint naming
- [ ] Understood that Stop model is NOT changed
- [ ] Clear on task execution order (models → migration → schemas → importer → repository → service → routes → tests)
- [ ] Validation commands are executable in this environment
