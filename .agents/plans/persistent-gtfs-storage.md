# Plan: Persistent GTFS Storage — Migrate Agent Transit Tools from In-Memory Cache to DB

## Feature Metadata
**Feature Type**: Refactor / Enhancement
**Estimated Complexity**: High
**Primary Systems Affected**: `app/core/agents/tools/transit/` (5 tools + static_cache + utils), `app/transit/` (poller, service), `app/analytics/` (service), `app/schedules/` (repository — read-only consumer), `app/stops/` (repository — read-only consumer)

## Feature Description

The agent's 5 transit tools (`query_bus_status`, `get_route_schedule`, `search_stops`, `get_adherence_report`, `check_driver_availability`) currently resolve GTFS static data (route names, stop names, trip info, stop times, calendars) through `GTFSStaticCache` — a module-level singleton that downloads and parses a remote GTFS ZIP file into Python dicts on first access, then refreshes when stale (TTL-based).

This approach has critical limitations: data is lost on restart, each worker maintains its own copy, cross-feed queries are impossible, and the data cannot be joined with other DB entities. The `app/schedules/` feature already has full GTFS tables (`agencies`, `routes`, `calendars`, `calendar_dates`, `trips`, `stop_times`) and the `app/stops/` feature has a `stops` table — the exact same data the cache holds.

This refactor replaces `GTFSStaticCache` with a new **`GTFSStaticStore`** that reads from the existing PostgreSQL tables via `ScheduleRepository` and `StopRepository`, keeping the same public interface so all 5 transit tools, the transit poller/service, and the analytics service continue working with minimal changes.

## User Story

As a **system operator**
I want agent transit tools to read GTFS data from the database instead of downloading and parsing ZIP files
So that data survives restarts, is consistent across workers, and can leverage existing GTFS import/management workflows.

## Solution Approach

**Create a DB-backed `GTFSStaticStore` that presents the same interface as `GTFSStaticCache`.**

The store class will:
1. Accept a `db_session_factory` (already available in `UnifiedDeps`) instead of `httpx.AsyncClient`
2. Load data from existing `schedules` and `stops` DB tables into the same dataclass structures (`RouteInfo`, `StopInfo`, `TripInfo`, `StopTimeEntry`, `CalendarEntry`, `CalendarDateException`)
3. Build the same indexes (`route_trips`, `trip_stop_times`, `stop_routes`)
4. Expose identical lookup methods (`get_route_name`, `get_stop_name`, `get_trip_route_id`, `get_trip_headsign`, `get_active_service_ids`)
5. Use the same TTL-based staleness check so data refreshes periodically from DB
6. Replace the module-level `get_static_cache()` function with `get_static_store()` that uses DB

**Approach Decision:**
We chose a drop-in replacement approach because:
- All 5 agent tools + transit service + analytics service reference `GTFSStaticCache` and `get_static_cache` — changing the interface would require modifying 8+ files
- The dataclass structures (`RouteInfo`, `StopInfo`, etc.) are used extensively in tool logic and tests — keeping them avoids cascading changes
- The existing `ScheduleRepository` already has all needed query methods (`list_all_routes`, `list_all_trips`, `list_all_stop_times`, etc.)

**Alternatives Considered:**
- **Direct SQL in each tool**: Rejected — would require rewriting all 5 tools, break the shared index structures, and lose the caching benefit
- **Remove caching entirely (query DB per-request)**: Rejected — agent tools often make multiple lookups in a single call; per-query DB access would add latency. The in-memory cache pattern is sound, just the data source needs to change from HTTP ZIP to DB
- **ORM model objects directly**: Rejected — tool logic uses lightweight dataclasses with GTFS string IDs, while DB models use integer PKs with FK relationships. Translating would add complexity

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, logging patterns, type checking requirements
- `app/core/agents/tools/transit/static_cache.py` (lines 1-429) — Current implementation to replace. Contains 6 dataclasses, `GTFSStaticCache` class, and `get_static_cache()` singleton
- `app/core/agents/tools/transit/deps.py` (lines 1-87) — `UnifiedDeps` dataclass with `db_session_factory` field already present
- `app/core/database.py` (lines 46-59) — `get_db_context()` async context manager

### DB Tables to Query
- `app/schedules/models.py` (lines 1-138) — `Agency`, `Route`, `Calendar`, `CalendarDate`, `Trip`, `StopTime` models
- `app/schedules/repository.py` (lines 629-670) — `list_all_routes()`, `list_all_calendars()`, `list_all_calendar_dates()`, `list_all_trips()`, `list_all_stop_times()` — the exact methods we need
- `app/stops/models.py` (lines 1-43) — `Stop` model with `gtfs_stop_id`, `stop_name`, `stop_lat`, `stop_lon`

### Consumer Files (must update imports)
- `app/core/agents/tools/transit/get_route_schedule.py` (line 20-24) — imports `StopTimeEntry`, `TripInfo`, `get_static_cache`
- `app/core/agents/tools/transit/search_stops.py` (line 19) — imports `StopInfo`, `get_static_cache`
- `app/core/agents/tools/transit/get_adherence_report.py` (lines 21-25) — imports `StopTimeEntry`, `TripInfo`, `get_static_cache`
- `app/core/agents/tools/transit/query_bus_status.py` (line 31) — imports `GTFSStaticCache`, `get_static_cache`
- `app/core/agents/tools/transit/utils.py` (line 12) — imports `StopTimeEntry`, `TripInfo`
- `app/transit/service.py` (lines 19-21) — imports `GTFSStaticCache`, `get_static_cache`
- `app/transit/poller.py` (line 17) — imports `GTFSStaticCache`, `get_static_cache`
- `app/analytics/service.py` (line 29) — imports `get_static_cache`

### Similar Features (Examples to Follow)
- `app/core/agents/tools/transit/check_driver_availability.py` (lines 100-103) — Example of a tool using `ctx.deps.db_session_factory` for DB access
- `app/core/agents/tools/transit/driver_data.py` — Example of tool data layer using `db_session_factory`

### Test Files (must update)
- `app/core/agents/tools/transit/tests/test_static_cache.py` — Direct cache tests
- `app/core/agents/tools/transit/tests/test_get_route_schedule.py` — Mocks `get_static_cache`
- `app/core/agents/tools/transit/tests/test_search_stops.py` — Mocks cache data
- `app/core/agents/tools/transit/tests/test_get_adherence_report.py` — Mocks `get_static_cache`
- `app/core/agents/tools/transit/tests/test_query_bus_status.py` — Mocks `get_static_cache`
- `app/transit/tests/test_poller.py` — Mocks `get_static_cache`
- `app/transit/tests/test_service.py` — Mocks `get_static_cache`
- `app/analytics/tests/test_service.py` — Mocks `get_static_cache`

## Implementation Plan

### Phase 1: Create DB-Backed Store (drop-in replacement)
Create `GTFSStaticStore` that loads from DB tables into the same dataclass structures, exposing the same interface. Keep `static_cache.py` intact during development — the new store lives in a new file.

### Phase 2: Replace Singleton Factory
Replace `get_static_cache(http_client, settings)` with `get_static_store(db_session_factory, settings)`. The new function signature drops `http_client` and adds `db_session_factory`. Update all 8 consumer files to call the new function.

### Phase 3: Update Tests
Update all test files that mock `get_static_cache` to mock `get_static_store` instead. Test assertions remain the same since the data structures are unchanged.

### Phase 4: Cleanup
Remove the old `GTFSStaticCache.load()` HTTP/ZIP parsing code. Keep dataclass definitions in place (they're shared). Deprecate/remove the old `get_static_cache` function.

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.

---

### Task 1: Create GTFSStaticStore — DB-Backed Cache
**File:** `app/core/agents/tools/transit/static_store.py` (create new)
**Action:** CREATE

Create a new module that provides a DB-backed replacement for `GTFSStaticCache`. The class loads data from existing PostgreSQL tables into the same dataclass structures.

**Implementation details:**

1. Import the same dataclass types from `static_cache.py`: `RouteInfo`, `StopInfo`, `TripInfo`, `StopTimeEntry`, `CalendarEntry`, `CalendarDateException`
2. Import `ScheduleRepository` from `app.schedules.repository`
3. Define `GTFSStaticStore` class with the SAME public interface as `GTFSStaticCache`:
   - Same `__init__` (same dict/list attributes: `routes`, `stops`, `trips`, `calendar`, `calendar_dates`, `route_trips`, `trip_stop_times`, `stop_routes`, `_loaded_at`)
   - New `async def load_from_db(self, db_session_factory)` method that:
     a. Opens a session via `async with db_session_factory() as db:`
     b. Creates `ScheduleRepository(db)`
     c. Calls `list_all_routes()` → convert each `Route` model to `RouteInfo(route_id=r.gtfs_route_id, route_short_name=r.route_short_name, route_long_name=r.route_long_name, route_type=r.route_type)`
     d. Loads stops via raw SQL query on stops table: `select(Stop)` → convert each to `StopInfo(stop_id=s.gtfs_stop_id, stop_name=s.stop_name, stop_lat=s.stop_lat, stop_lon=s.stop_lon)`
     e. Calls `list_all_calendars()` → convert each `Calendar` model to `CalendarEntry` (note: DB stores `start_date`/`end_date` as `datetime.date`, cache uses `YYYYMMDD` strings — must format with `strftime("%Y%m%d")`)
     f. Calls `list_all_calendar_dates()` → convert each `CalendarDate` model to `CalendarDateException` (must look up `gtfs_service_id` from the calendar's FK, AND format date as `YYYYMMDD`)
     g. Calls `list_all_trips()` → for each trip, look up `gtfs_route_id` and `gtfs_service_id` via the FK relationships. Convert to `TripInfo(trip_id=t.gtfs_trip_id, route_id=<gtfs_route_id>, service_id=<gtfs_service_id>, direction_id=t.direction_id, trip_headsign=t.trip_headsign)`
     h. Calls `list_all_stop_times()` → group by trip, convert to `StopTimeEntry`. Must resolve `trip_id` FK to `gtfs_trip_id` and `stop_id` FK to `gtfs_stop_id`
     i. Calls `_build_route_trips_index()` and `_build_stop_routes_index()` (reuse from `GTFSStaticCache`)
     j. Sets `self._loaded_at = datetime.now(tz=UTC)`
   - Same `is_stale()`, `get_route_name()`, `get_stop_name()`, `get_trip_route_id()`, `get_trip_headsign()`, `get_active_service_ids()` methods — **inherit from GTFSStaticCache** or copy them
   - Same `_build_route_trips_index()` and `_build_stop_routes_index()` — **inherit from GTFSStaticCache**

4. **Design decision: Use inheritance.** `GTFSStaticStore` extends `GTFSStaticCache` and overrides only the `load_from_db` method. The parent's `load()` (HTTP) still exists but won't be called. All lookup methods and index builders are inherited. This avoids code duplication.

5. For FK resolution (trips need gtfs_route_id, stop_times need gtfs_trip_id and gtfs_stop_id), pre-build lookup maps ONCE during load:
   - `route_pk_to_gtfs: dict[int, str]` — from `list_all_routes()`
   - `calendar_pk_to_gtfs: dict[int, str]` — from `list_all_calendars()`
   - `trip_pk_to_gtfs: dict[int, str]` — from trips
   - `stop_pk_to_gtfs: dict[int, str]` — from stops
   These maps are local variables in `load_from_db`, NOT stored on the instance.

6. Define module-level singleton:
```python
_static_store: GTFSStaticStore | None = None

async def get_static_store(
    db_session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]],
    settings: Settings,
) -> GTFSStaticStore:
    """Get or create the DB-backed GTFS static store singleton."""
    global _static_store
    if _static_store is None or _static_store.is_stale(settings.gtfs_static_cache_ttl_hours):
        _static_store = GTFSStaticStore()
        await _static_store.load_from_db(db_session_factory)
    return _static_store
```

7. Add structured logging:
   - `transit.static_store.load_started`
   - `transit.static_store.load_completed` — with counts matching the old cache log
   - `transit.static_store.load_failed` — with exc_info

8. Import `from app.stops.models import Stop` and use `select(Stop)` for loading stops directly (not via repository, since StopRepository doesn't have a `list_all_stops()` for GTFS export — it's pagination-based).

9. For stops query, use the raw SQLAlchemy select:
```python
from sqlalchemy import select
from app.stops.models import Stop
result = await db.execute(select(Stop))
all_stops = result.scalars().all()
```

10. For calendar_dates FK resolution: each `CalendarDate` has `calendar_id` (int FK). Need to map that to `gtfs_service_id`. Use the `calendar_pk_to_gtfs` map built from calendars.

**Per-task validation:**
- `uv run ruff format app/core/agents/tools/transit/static_store.py`
- `uv run ruff check --fix app/core/agents/tools/transit/static_store.py`
- `uv run mypy app/core/agents/tools/transit/static_store.py`
- `uv run pyright app/core/agents/tools/transit/static_store.py`

---

### Task 2: Update get_route_schedule to use DB store
**File:** `app/core/agents/tools/transit/get_route_schedule.py` (modify existing)
**Action:** UPDATE

1. Change import from:
   ```python
   from app.core.agents.tools.transit.static_cache import (
       StopTimeEntry,
       TripInfo,
       get_static_cache,
   )
   ```
   to:
   ```python
   from app.core.agents.tools.transit.static_cache import (
       StopTimeEntry,
       TripInfo,
   )
   from app.core.agents.tools.transit.static_store import get_static_store
   ```

2. In `get_route_schedule()` function, change line ~193:
   ```python
   # OLD:
   static = await get_static_cache(ctx.deps.transit_http_client, ctx.deps.settings)
   # NEW:
   static = await get_static_store(ctx.deps.db_session_factory, ctx.deps.settings)
   ```

3. The `db_session_factory` is already available on `ctx.deps` (`UnifiedDeps.db_session_factory`). However, it's typed as `Callable[..] | None`. We need to handle the None case. Add a guard:
   ```python
   if ctx.deps.db_session_factory is None:
       return "Database session not available. Transit schedule data requires database access."
   static = await get_static_store(ctx.deps.db_session_factory, ctx.deps.settings)
   ```

**Per-task validation:**
- `uv run ruff format app/core/agents/tools/transit/get_route_schedule.py`
- `uv run ruff check --fix app/core/agents/tools/transit/get_route_schedule.py`
- `uv run mypy app/core/agents/tools/transit/get_route_schedule.py`

---

### Task 3: Update search_stops to use DB store
**File:** `app/core/agents/tools/transit/search_stops.py` (modify existing)
**Action:** UPDATE

1. Change import:
   ```python
   # OLD:
   from app.core.agents.tools.transit.static_cache import StopInfo, get_static_cache
   # NEW:
   from app.core.agents.tools.transit.static_cache import StopInfo
   from app.core.agents.tools.transit.static_store import get_static_store
   ```

2. In `search_stops()` function, change line ~216:
   ```python
   # OLD:
   static = await get_static_cache(ctx.deps.transit_http_client, ctx.deps.settings)
   # NEW:
   if ctx.deps.db_session_factory is None:
       return "Database session not available. Stop search requires database access."
   static = await get_static_store(ctx.deps.db_session_factory, ctx.deps.settings)
   ```

**Per-task validation:**
- `uv run ruff format app/core/agents/tools/transit/search_stops.py`
- `uv run ruff check --fix app/core/agents/tools/transit/search_stops.py`
- `uv run mypy app/core/agents/tools/transit/search_stops.py`

---

### Task 4: Update get_adherence_report to use DB store
**File:** `app/core/agents/tools/transit/get_adherence_report.py` (modify existing)
**Action:** UPDATE

1. Change import:
   ```python
   # OLD:
   from app.core.agents.tools.transit.static_cache import (
       StopTimeEntry,
       TripInfo,
       get_static_cache,
   )
   # NEW:
   from app.core.agents.tools.transit.static_cache import (
       StopTimeEntry,
       TripInfo,
   )
   from app.core.agents.tools.transit.static_store import get_static_store
   ```

2. In `get_adherence_report()` function, change line ~224:
   ```python
   # OLD:
   static = await get_static_cache(ctx.deps.transit_http_client, ctx.deps.settings)
   # NEW:
   if ctx.deps.db_session_factory is None:
       return "Database session not available. Adherence report requires database access."
   static = await get_static_store(ctx.deps.db_session_factory, ctx.deps.settings)
   ```

**Per-task validation:**
- `uv run ruff format app/core/agents/tools/transit/get_adherence_report.py`
- `uv run ruff check --fix app/core/agents/tools/transit/get_adherence_report.py`
- `uv run mypy app/core/agents/tools/transit/get_adherence_report.py`

---

### Task 5: Update query_bus_status to use DB store
**File:** `app/core/agents/tools/transit/query_bus_status.py` (modify existing)
**Action:** UPDATE

1. Change import:
   ```python
   # OLD:
   from app.core.agents.tools.transit.static_cache import GTFSStaticCache, get_static_cache
   # NEW:
   from app.core.agents.tools.transit.static_cache import GTFSStaticCache
   from app.core.agents.tools.transit.static_store import get_static_store
   ```
   Note: `GTFSStaticCache` is still used as a type annotation for `_handle_status`, `_handle_route_overview`, `_handle_stop_departures`, and `_build_bus_statuses`. Since `GTFSStaticStore` inherits from `GTFSStaticCache`, the type annotation remains valid. Keep importing `GTFSStaticCache` for the type.

2. In `query_bus_status()` function, change line ~119:
   ```python
   # OLD:
   static = await get_static_cache(ctx.deps.transit_http_client, ctx.deps.settings)
   # NEW:
   if ctx.deps.db_session_factory is None:
       return "Database session not available. Bus status requires database access."
   static = await get_static_store(ctx.deps.db_session_factory, ctx.deps.settings)
   ```

**Per-task validation:**
- `uv run ruff format app/core/agents/tools/transit/query_bus_status.py`
- `uv run ruff check --fix app/core/agents/tools/transit/query_bus_status.py`
- `uv run mypy app/core/agents/tools/transit/query_bus_status.py`

---

### Task 6: Update transit poller to use DB store
**File:** `app/transit/poller.py` (modify existing)
**Action:** UPDATE

1. Read the file first to understand current usage.
2. Change import:
   ```python
   # OLD:
   from app.core.agents.tools.transit.static_cache import GTFSStaticCache, get_static_cache
   # NEW:
   from app.core.agents.tools.transit.static_cache import GTFSStaticCache
   from app.core.agents.tools.transit.static_store import get_static_store
   ```

3. The poller's `_poll_once` method currently calls `get_static_cache(self._http_client, self._settings)`. Change to `get_static_store(db_session_factory, self._settings)`. The poller needs access to `db_session_factory`. Check how the poller is instantiated — it likely receives settings and an http_client. Add `db_session_factory` as a constructor parameter.

4. If the poller doesn't have `db_session_factory`, add it:
   - Add `db_session_factory` parameter to `__init__`
   - Update the poller's instantiation site (likely in `app/transit/service.py` or `app/main.py` lifespan)

**Per-task validation:**
- `uv run ruff format app/transit/poller.py`
- `uv run ruff check --fix app/transit/poller.py`
- `uv run mypy app/transit/poller.py`

---

### Task 7: Update transit service to use DB store
**File:** `app/transit/service.py` (modify existing)
**Action:** UPDATE

1. Read the file first.
2. Change import:
   ```python
   # OLD:
   from app.core.agents.tools.transit.static_cache import GTFSStaticCache, get_static_cache
   # NEW:
   from app.core.agents.tools.transit.static_cache import GTFSStaticCache
   from app.core.agents.tools.transit.static_store import get_static_store
   ```

3. Update the call to `get_static_cache` → `get_static_store` with `db_session_factory` parameter.

4. Ensure `db_session_factory` is available — may need to import `get_db_context` from `app.core.database` and pass it.

**Per-task validation:**
- `uv run ruff format app/transit/service.py`
- `uv run ruff check --fix app/transit/service.py`
- `uv run mypy app/transit/service.py`

---

### Task 8: Update analytics service to use DB store
**File:** `app/analytics/service.py` (modify existing)
**Action:** UPDATE

1. Read the file first.
2. Change import:
   ```python
   # OLD:
   from app.core.agents.tools.transit.static_cache import get_static_cache
   # NEW:
   from app.core.agents.tools.transit.static_store import get_static_store
   ```

3. Update the call to `get_static_cache` → `get_static_store`. The analytics service already creates an `httpx.AsyncClient` internally. Replace that with `get_db_context` from `app.core.database`.

**Per-task validation:**
- `uv run ruff format app/analytics/service.py`
- `uv run ruff check --fix app/analytics/service.py`
- `uv run mypy app/analytics/service.py`

---

### Task 9: Write unit tests for GTFSStaticStore
**File:** `app/core/agents/tools/transit/tests/test_static_store.py` (create new)
**Action:** CREATE

Write tests that verify `GTFSStaticStore.load_from_db` correctly transforms DB model objects into the expected dataclass structures.

**Test strategy:** Mock the `db_session_factory` and `ScheduleRepository` methods. Don't hit a real DB — these are unit tests.

**Test 1: Happy path — load_from_db populates all structures**
```python
async def test_load_from_db_populates_routes():
    # Mock db_session_factory to return a session
    # Mock ScheduleRepository.list_all_routes() to return Route objects
    # Assert store.routes dict has correct RouteInfo entries
```

**Test 2: Calendar date format conversion**
```python
async def test_load_from_db_formats_calendar_dates():
    # Mock calendars with datetime.date objects
    # Assert CalendarEntry.start_date is YYYYMMDD string format
```

**Test 3: FK resolution for trips**
```python
async def test_load_from_db_resolves_trip_fks():
    # Mock trips with integer route_id and calendar_id FKs
    # Assert TripInfo.route_id is the gtfs_route_id string, not integer PK
```

**Test 4: FK resolution for stop_times**
```python
async def test_load_from_db_resolves_stop_time_fks():
    # Mock stop_times with integer trip_id and stop_id FKs
    # Assert StopTimeEntry uses gtfs_trip_id and gtfs_stop_id strings
```

**Test 5: Index building**
```python
async def test_load_from_db_builds_indexes():
    # After load, assert route_trips, trip_stop_times, stop_routes are populated
```

**Test 6: get_static_store singleton with TTL**
```python
async def test_get_static_store_caches_and_refreshes():
    # First call creates store
    # Second call returns cached
    # After TTL expires, reloads
```

**Test 7: Empty DB**
```python
async def test_load_from_db_empty_database():
    # All repository methods return empty lists
    # Store should have empty dicts/lists, no errors
```

**Per-task validation:**
- `uv run ruff format app/core/agents/tools/transit/tests/test_static_store.py`
- `uv run ruff check --fix app/core/agents/tools/transit/tests/test_static_store.py`
- `uv run pytest app/core/agents/tools/transit/tests/test_static_store.py -v`

---

### Task 10: Update existing transit tool tests
**File:** `app/core/agents/tools/transit/tests/test_get_route_schedule.py` (modify existing)
**Action:** UPDATE

1. Read the file first.
2. Change all `@patch("app.core.agents.tools.transit.get_route_schedule.get_static_cache")` to `@patch("app.core.agents.tools.transit.get_route_schedule.get_static_store")`
3. Mock deps must have `db_session_factory` set (not None). Add `db_session_factory=MagicMock()` to the mock deps.
4. The mock return values remain the same (they return GTFSStaticCache-like objects with the same attributes).

**Per-task validation:**
- `uv run ruff format app/core/agents/tools/transit/tests/test_get_route_schedule.py`
- `uv run ruff check --fix app/core/agents/tools/transit/tests/test_get_route_schedule.py`
- `uv run pytest app/core/agents/tools/transit/tests/test_get_route_schedule.py -v`

---

### Task 11: Update search_stops tests
**File:** `app/core/agents/tools/transit/tests/test_search_stops.py` (modify existing)
**Action:** UPDATE

1. Read the file first.
2. Change all `@patch(...)` targets from `get_static_cache` to `get_static_store`.
3. Ensure mock deps have `db_session_factory=MagicMock()`.

**Per-task validation:**
- `uv run ruff format app/core/agents/tools/transit/tests/test_search_stops.py`
- `uv run ruff check --fix app/core/agents/tools/transit/tests/test_search_stops.py`
- `uv run pytest app/core/agents/tools/transit/tests/test_search_stops.py -v`

---

### Task 12: Update get_adherence_report tests
**File:** `app/core/agents/tools/transit/tests/test_get_adherence_report.py` (modify existing)
**Action:** UPDATE

1. Read the file first.
2. Change all `@patch(...)` targets from `get_static_cache` to `get_static_store`.
3. Ensure mock deps have `db_session_factory=MagicMock()`.

**Per-task validation:**
- `uv run ruff format app/core/agents/tools/transit/tests/test_get_adherence_report.py`
- `uv run ruff check --fix app/core/agents/tools/transit/tests/test_get_adherence_report.py`
- `uv run pytest app/core/agents/tools/transit/tests/test_get_adherence_report.py -v`

---

### Task 13: Update query_bus_status tests
**File:** `app/core/agents/tools/transit/tests/test_query_bus_status.py` (modify existing)
**Action:** UPDATE

1. Read the file first.
2. Change all `@patch(...)` targets from `get_static_cache` to `get_static_store`.
3. Ensure mock deps have `db_session_factory=MagicMock()`.

**Per-task validation:**
- `uv run ruff format app/core/agents/tools/transit/tests/test_query_bus_status.py`
- `uv run ruff check --fix app/core/agents/tools/transit/tests/test_query_bus_status.py`
- `uv run pytest app/core/agents/tools/transit/tests/test_query_bus_status.py -v`

---

### Task 14: Update transit poller tests
**File:** `app/transit/tests/test_poller.py` (modify existing)
**Action:** UPDATE

1. Read the file first.
2. Change all `@patch("app.transit.poller.get_static_cache")` to `@patch("app.transit.poller.get_static_store")`.
3. Update mock poller construction if `db_session_factory` was added as parameter.

**Per-task validation:**
- `uv run ruff format app/transit/tests/test_poller.py`
- `uv run ruff check --fix app/transit/tests/test_poller.py`
- `uv run pytest app/transit/tests/test_poller.py -v`

---

### Task 15: Update transit service tests
**File:** `app/transit/tests/test_service.py` (modify existing)
**Action:** UPDATE

1. Read the file first.
2. Change all `@patch("app.transit.service.get_static_cache")` to `@patch("app.transit.service.get_static_store")`.
3. Update mock construction if needed.

**Per-task validation:**
- `uv run ruff format app/transit/tests/test_service.py`
- `uv run ruff check --fix app/transit/tests/test_service.py`
- `uv run pytest app/transit/tests/test_service.py -v`

---

### Task 16: Update analytics service tests
**File:** `app/analytics/tests/test_service.py` (modify existing)
**Action:** UPDATE

1. Read the file first.
2. Change all `@patch("app.analytics.service.get_static_cache")` to `@patch("app.analytics.service.get_static_store")`.

**Per-task validation:**
- `uv run ruff format app/analytics/tests/test_service.py`
- `uv run ruff check --fix app/analytics/tests/test_service.py`
- `uv run pytest app/analytics/tests/test_service.py -v`

---

### Task 17: Clean up static_cache.py
**File:** `app/core/agents/tools/transit/static_cache.py` (modify existing)
**Action:** UPDATE

1. Keep ALL dataclass definitions (`RouteInfo`, `StopInfo`, `TripInfo`, `StopTimeEntry`, `CalendarEntry`, `CalendarDateException`) — they're imported everywhere
2. Keep `GTFSStaticCache` class since `GTFSStaticStore` inherits from it
3. Remove or deprecate the module-level `_static_cache` singleton and `get_static_cache()` function. Since the HTTP-based loading is no longer the primary path:
   - Remove the `_static_cache` global variable
   - Remove `get_static_cache()` function
   - Keep `GTFSStaticCache.load()` method (it's the HTTP loader — may still be useful for testing or fallback)
4. Verify no remaining imports of `get_static_cache` exist (Grep for it)

**Per-task validation:**
- `uv run ruff format app/core/agents/tools/transit/static_cache.py`
- `uv run ruff check --fix app/core/agents/tools/transit/static_cache.py`
- `uv run mypy app/core/agents/tools/transit/static_cache.py`
- Grep: `grep -r "get_static_cache" app/` should return 0 results (only test mock references should remain — and those were updated in Tasks 10-16)

---

### Task 18: Update static_cache tests
**File:** `app/core/agents/tools/transit/tests/test_static_cache.py` (modify existing)
**Action:** UPDATE

The existing tests test `GTFSStaticCache` directly (calendar logic, index building). These tests are still valid since `GTFSStaticStore` inherits from `GTFSStaticCache`. No changes needed to the test logic. Only update if imports changed.

If `get_static_cache` was removed from static_cache.py, verify none of the tests import it. Current tests don't import `get_static_cache` — they construct `GTFSStaticCache()` directly. No changes expected.

**Per-task validation:**
- `uv run pytest app/core/agents/tools/transit/tests/test_static_cache.py -v`

---

## Logging Events

- `transit.static_store.load_started` — when DB load begins
- `transit.static_store.load_completed` — when DB load finishes (include route_count, stop_count, trip_count, stop_time_trips, calendar_entries, calendar_exceptions, stop_routes_count)
- `transit.static_store.load_failed` — when DB load fails (include exc_info, error, error_type)

## Testing Strategy

### Unit Tests
**Location:** `app/core/agents/tools/transit/tests/test_static_store.py`
- `GTFSStaticStore.load_from_db` — correct transformation from DB models to dataclasses
- FK resolution — integer PKs correctly mapped to GTFS string IDs
- Date formatting — `datetime.date` → `YYYYMMDD` strings
- Index building — `route_trips`, `trip_stop_times`, `stop_routes` populated correctly
- `get_static_store` singleton — caching and TTL refresh behavior
- Empty database — no errors, empty structures

### Existing Tests (updated mocks)
**Location:** Various test files (Tasks 10-16)
- All existing tool tests continue to pass with `get_static_store` mock in place of `get_static_cache`
- Mock return values unchanged — same dataclass structures

### Edge Cases
- Empty database (no GTFS data imported yet) — tools should return helpful error messages
- Stops with null lat/lon — `StopInfo` allows None, search_stops handles it
- Overnight trips (stop_times > 24:00:00) — unchanged, same string format
- Calendar with no matching service on query date — `get_active_service_ids` logic unchanged (inherited)

## Acceptance Criteria

This feature is complete when:
- [ ] `GTFSStaticStore` class loads from DB and produces identical data structures to `GTFSStaticCache`
- [ ] All 5 agent tools use `get_static_store` instead of `get_static_cache`
- [ ] Transit poller and service use `get_static_store`
- [ ] Analytics service uses `get_static_store`
- [ ] All type checkers pass (mypy + pyright)
- [ ] All tests pass (unit + existing tool tests with updated mocks)
- [ ] Structured logging follows `domain.component.action_state` pattern
- [ ] No type suppressions added (beyond existing ones)
- [ ] `get_static_cache` function removed from `static_cache.py`
- [ ] No HTTP calls for GTFS static data in agent tools (only GTFS-RT remains HTTP-based)
- [ ] No regressions in existing tests

## Completion Checklist

Before marking this plan as fully executed:
- [ ] All 18 tasks completed in order
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
uv run pytest app/core/agents/tools/transit/tests/ -v
uv run pytest app/transit/tests/ -v
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

- Shared utilities used: `TimestampMixin` (inherited via models), `get_db_context()` from `app.core.database`
- Core modules used: `app.core.config.Settings`, `app.core.logging.get_logger`
- Cross-feature reads: `app.schedules.repository.ScheduleRepository`, `app.stops.models.Stop`
- New dependencies: None — all packages already installed
- New env vars: None

## Known Pitfalls

The executing agent MUST follow all 59 Python anti-pattern rules from `_shared/python-anti-patterns.md`.

**Specific risks for this refactor:**

1. **FK resolution mapping** — DB models use integer PKs (`Route.id`, `Trip.id`) while GTFS uses string IDs (`gtfs_route_id`, `gtfs_trip_id`). Every FK reference must be resolved to the GTFS string ID. Missing a resolution will cause silent data corruption (integer IDs where strings are expected).

2. **Date format conversion** — `Calendar.start_date` is `datetime.date` in the DB but `CalendarEntry.start_date` is a `YYYYMMDD` string. Must call `.strftime("%Y%m%d")`. Missing this breaks `get_active_service_ids()` which does string comparison.

3. **Stop table is in `app/stops/`, not `app/schedules/`** — Stop data lives in a different feature's table. This is fine per VTV rules (cross-feature read access is allowed). Use direct SQLAlchemy `select(Stop)` since `StopRepository` is pagination-oriented.

4. **`db_session_factory` is Optional** — `UnifiedDeps.db_session_factory` is typed as `Callable[...] | None`. Every tool must guard against `None` before calling `get_static_store()`. In practice it's always set by `create_unified_deps()`, but the type system requires the check.

5. **Singleton reset in tests** — The `_static_store` global must be resettable for tests. Either expose a `_reset_store()` function or ensure tests mock at the `get_static_store` level (which they do via `@patch`).

6. **Calendar FK for calendar_dates** — `CalendarDate.calendar_id` is an integer FK to `Calendar.id`. To get the `service_id` for `CalendarDateException`, need the `calendar_pk_to_gtfs` lookup map. Don't try to use a joined query — build the map from the calendars list and look up.

7. **StopTime FK double resolution** — `StopTime.trip_id` → need `gtfs_trip_id` string. `StopTime.stop_id` → need `gtfs_stop_id` string. Both need lookup maps built before processing stop_times.

8. **Large dataset performance** — Riga's GTFS has ~2000 stops, ~80 routes, ~thousands of trips, ~tens of thousands of stop_times. Loading all into memory via `list_all_*()` is fine — same data was previously loaded from a ZIP. The DB queries should use the existing repository methods which already handle this scale.

## Notes

- **Fallback strategy**: The old `GTFSStaticCache.load()` HTTP method is preserved on the parent class. If the DB has no GTFS data (e.g., fresh install before first import), tools will return empty results. A future enhancement could add a fallback to HTTP loading if DB is empty.
- **GTFS-RT remains HTTP-based**: Only the static GTFS data (routes, stops, trips, calendars, stop_times) moves to DB. Real-time data (vehicle positions, trip updates, alerts) continues to be fetched via HTTP from GTFS-RT feeds — this is correct since RT data is ephemeral.
- **Multi-feed support**: The current `static_cache.py` loads from a single GTFS URL. The DB already supports data from multiple feeds (via GTFS import). This migration automatically enables cross-feed queries since all data is in the same tables.
- **The `transit` feature's poller** also depends on static cache for resolving route/trip names when processing RT data. It needs the same migration.

## Pre-Implementation Checklist

The executing agent MUST verify before writing any code:
- [ ] Read all files listed in "Relevant Files" section
- [ ] Understood FK resolution strategy (integer PK → GTFS string ID)
- [ ] Understood date format conversion (datetime.date → YYYYMMDD string)
- [ ] Understood inheritance approach (GTFSStaticStore extends GTFSStaticCache)
- [ ] Confirmed `db_session_factory` is already on `UnifiedDeps` (deps.py line 35-37)
- [ ] Confirmed `ScheduleRepository` has `list_all_*()` methods (repository.py lines 629-670)
- [ ] Clear on task execution order (store → tools → external consumers → tests → cleanup)
- [ ] Validation commands are executable in this environment
