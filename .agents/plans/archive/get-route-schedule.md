# Plan: get_route_schedule Transit Tool

## Feature Metadata
**Feature Type**: New Capability (Agent Tool)
**Estimated Complexity**: High
**Primary Systems Affected**: `app/core/agents/tools/transit/`, `app/core/agents/agent.py`

## Feature Description

The `get_route_schedule` tool enables the VTV AI agent to look up planned timetables for any bus route on a given service date. This is the second transit tool (after `query_bus_status`) and unlocks a critical agent workflow: comparing real-time status against the planned schedule.

The tool reads static GTFS data (stop_times.txt, calendar.txt, calendar_dates.txt) to resolve which trips run on a given date, what stops they serve, and at what times. It handles GTFS time quirks (times exceeding 24:00:00 for overnight trips), service calendar logic (weekday/weekend/holiday exceptions), and produces token-efficient responses for the LLM agent.

The PRD (Section 6.2) defines this as: "Timetable for a specific route and service date" sourced from the VTV tRPC API. Since the CMS backend doesn't exist yet, we source data directly from the Riga GTFS static feed (same source as `query_bus_status` uses for enrichment), making this tool fully functional today without waiting for backend CRUD.

## User Story

As a **dispatcher**
I want to ask the AI agent "what is the schedule for route 22 today?"
So that I can verify service coverage, answer passenger queries, and compare planned vs actual operations.

## Solution Approach

We extend the existing `GTFSStaticCache` to parse three additional GTFS files (`stop_times.txt`, `calendar.txt`, `calendar_dates.txt`) and build two new indexes (`route_trips` for route→trip lookups, `trip_stop_times` for trip→ordered stops). The tool function follows the exact same pattern as `query_bus_status`: accepts parameters, validates, delegates to handler functions, returns JSON or error string.

**Approach Decision:**
We chose to extend `GTFSStaticCache` (eager loading) because:
- The cache already downloads the full GTFS ZIP — parsing 3 more CSV files from the same ZIP is trivial overhead
- All transit tools share the same singleton cache, so schedule data is available to future tools too
- Riga's GTFS feed is ~200K stop_time rows = ~20-30MB in memory, well within acceptable bounds

**Alternatives Considered:**
- Separate lazy-loading cache for schedule data: Rejected because it would require re-downloading the same ZIP or storing raw bytes, adding complexity for negligible memory savings
- Using gtfs-kit or pygtfs library: Rejected because they add heavy dependencies (Pandas, SQLite), are alpha-quality, and our CSV parsing is simpler and already proven in the codebase
- On-demand per-route parsing: Rejected because it re-parses the ZIP on every query (~500ms latency vs <10ms for pre-built indexes)

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, logging patterns, type checking requirements
- `reference/PRD.md` (lines 166-176) — Transit tool specs, data sources
- `reference/mvp-tool-designs.md` — Tool design principles (token efficiency, errors, dry-run)

### Similar Features (Examples to Follow)
- `app/core/agents/tools/transit/query_bus_status.py` (all 461 lines) — **PRIMARY PATTERN**: function signature, logging, error handling, return format, parameter validation
- `app/core/agents/tools/transit/static_cache.py` (all 237 lines) — Cache structure, `_parse_*` methods, singleton pattern, `is_stale()` check
- `app/core/agents/tools/transit/schemas.py` (all 175 lines) — Pydantic `BaseModel` with `ConfigDict(strict=True)` pattern
- `app/core/agents/tools/transit/tests/test_query_bus_status.py` (all 153 lines) — Test patterns: MagicMock ctx, patch at consumer module path
- `app/core/agents/agent.py` (all 54 lines) — Tool registration in `tools=[...]` list

### Files to Modify
- `app/core/agents/tools/transit/static_cache.py` — Add `StopTimeEntry`, `CalendarEntry`, `CalendarDateException` dataclasses; add `_parse_stop_times`, `_parse_calendar`, `_parse_calendar_dates` methods; add `route_trips` and `trip_stop_times` indexes; add `service_id` to `TripInfo`
- `app/core/agents/tools/transit/schemas.py` — Add `ScheduleStop`, `TripSchedule`, `DirectionSchedule`, `RouteSchedule` response models
- `app/core/agents/agent.py` — Add `get_route_schedule` to `tools=[...]` list

### Files to Create
- `app/core/agents/tools/transit/get_route_schedule.py` — Tool function
- `app/core/agents/tools/transit/tests/test_get_route_schedule.py` — Unit tests

## Research Documentation

- [GTFS Schedule Reference](https://gtfs.org/documentation/schedule/reference/)
  - Section: stop_times.txt, calendar.txt, calendar_dates.txt field definitions
  - Summary: Defines exact CSV column names, data types, and constraints
  - Use for: Tasks 1-2 (parsing logic)

- [GTFS Schedule Best Practices](https://gtfs.org/documentation/schedule/schedule-best-practices/)
  - Section: Service calendars, time handling
  - Summary: Times can exceed 24:00:00 for overnight trips; calendar_dates can ADD or REMOVE service
  - Use for: Task 4 (time utilities, service resolution)

- [Pydantic AI Documentation — Tools](https://ai.pydantic.dev/tools/)
  - Section: Function tools, RunContext
  - Summary: Tools are plain async functions passed via `tools=[...]`; first param is `RunContext[DepsType]`
  - Use for: Task 5 (tool function signature)

## Implementation Plan

### Phase 1: Foundation (Tasks 1-3)
Extend the static GTFS cache with new data structures and parsing for `stop_times.txt`, `calendar.txt`, and `calendar_dates.txt`. Add `service_id` to `TripInfo`. Build route→trips and trip→stop_times indexes.

### Phase 2: Tool Implementation (Tasks 4-6)
Add schedule response schemas. Create GTFS time utilities. Implement the `get_route_schedule` tool function with full validation, logging, and token-efficient response formatting.

### Phase 3: Integration & Validation (Tasks 7-9)
Register the tool with the agent. Write comprehensive unit tests. Run full validation pyramid.

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.

---

### Task 1: Add schedule dataclasses and service_id to TripInfo
**File:** `app/core/agents/tools/transit/static_cache.py` (modify existing)
**Action:** UPDATE

Add three new dataclasses AFTER the existing `TripInfo` class (before `class GTFSStaticCache`):

1. Add `service_id: str` field to the existing `TripInfo` dataclass:
   - `service_id: str = ""` — GTFS service_id linking to calendar, used for schedule resolution

2. Create `StopTimeEntry` dataclass:
   - `stop_id: str` — GTFS stop identifier
   - `stop_sequence: int` — Order of stop within trip (1-indexed)
   - `arrival_time: str` — GTFS HH:MM:SS format (may exceed 24:00:00 for overnight)
   - `departure_time: str` — GTFS HH:MM:SS format

3. Create `CalendarEntry` dataclass:
   - `service_id: str` — Links to trips
   - `monday: bool` through `sunday: bool` — Day-of-week bitmask
   - `start_date: str` — YYYYMMDD format, inclusive start
   - `end_date: str` — YYYYMMDD format, inclusive end

4. Create `CalendarDateException` dataclass:
   - `service_id: str` — Links to calendar entry
   - `date: str` — YYYYMMDD format
   - `exception_type: int` — 1=service added, 2=service removed

Update the `_parse_trips` method to also extract `service_id`:
```python
service_id=row.get("service_id", ""),
```

**Per-task validation:**
- `uv run ruff format app/core/agents/tools/transit/static_cache.py`
- `uv run ruff check app/core/agents/tools/transit/static_cache.py` passes
- `uv run mypy app/core/agents/tools/transit/static_cache.py` passes with 0 errors
- `uv run pyright app/core/agents/tools/transit/static_cache.py` passes with 0 errors

---

### Task 2: Add parse methods and indexes to GTFSStaticCache
**File:** `app/core/agents/tools/transit/static_cache.py` (modify existing)
**Action:** UPDATE

Extend `GTFSStaticCache.__init__` with new fields:
```python
self.calendar: list[CalendarEntry] = []
self.calendar_dates: list[CalendarDateException] = []
self.route_trips: dict[str, list[TripInfo]] = {}
self.trip_stop_times: dict[str, list[StopTimeEntry]] = {}
```

Add to `load()` method — call new parse methods AFTER existing ones (inside the `with zipfile.ZipFile` block):
```python
self._parse_stop_times(zf)
self._parse_calendar(zf)
self._parse_calendar_dates(zf)
self._build_route_trips_index()
```

Update the load completed log to include new counts:
```python
logger.info(
    "transit.static_cache.load_completed",
    route_count=len(self.routes),
    stop_count=len(self.stops),
    trip_count=len(self.trips),
    stop_time_trips=len(self.trip_stop_times),
    calendar_entries=len(self.calendar),
    calendar_exceptions=len(self.calendar_dates),
)
```

Implement `_parse_stop_times(self, zf: zipfile.ZipFile) -> None`:
- Guard: `if "stop_times.txt" not in zf.namelist(): return`
- Parse CSV, build `self.trip_stop_times` dict keyed by `trip_id`
- After parsing, sort each trip's entries by `stop_sequence`
- Follow the exact same csv.DictReader + io.TextIOWrapper pattern from `_parse_routes`

Implement `_parse_calendar(self, zf: zipfile.ZipFile) -> None`:
- Guard: `if "calendar.txt" not in zf.namelist(): return`
- Parse CSV into `self.calendar` list
- Day columns: read `row.get("monday", "0")` etc., convert to `bool` via `== "1"`

Implement `_parse_calendar_dates(self, zf: zipfile.ZipFile) -> None`:
- Guard: `if "calendar_dates.txt" not in zf.namelist(): return`
- Parse CSV into `self.calendar_dates` list

Implement `_build_route_trips_index(self) -> None`:
- Iterate `self.trips.values()`, group by `route_id` into `self.route_trips`

Add a convenience method `get_active_service_ids(self, query_date: date) -> set[str]`:
- Import `date` from `datetime` at top of file
- Step 1: Check `self.calendar` — for each entry where `start_date <= date_str <= end_date`, check if the weekday flag is True. Use `query_date.strftime("%A").lower()` to get day name, then `getattr(entry, day_name)` to check the boolean.
- Step 2: Apply `self.calendar_dates` — add service_ids with `exception_type == 1`, remove with `exception_type == 2`
- Return the active `set[str]`

IMPORTANT: The `query_date` parameter must use `datetime.date` type (from stdlib). Import as: `from datetime import UTC, date, datetime` (extending the existing import).

**Per-task validation:**
- `uv run ruff format app/core/agents/tools/transit/static_cache.py`
- `uv run ruff check app/core/agents/tools/transit/static_cache.py` passes
- `uv run mypy app/core/agents/tools/transit/static_cache.py` passes with 0 errors
- `uv run pyright app/core/agents/tools/transit/static_cache.py` passes with 0 errors
- `uv run pytest app/core/agents/tools/transit/tests/ -v` — existing tests still pass

---

### Task 3: Add schedule response schemas
**File:** `app/core/agents/tools/transit/schemas.py` (modify existing)
**Action:** UPDATE

Add these new models AFTER the existing `StopDepartures` class:

1. `ScheduleStop(BaseModel)` — A stop within a scheduled trip:
   - `stop_sequence: int`
   - `stop_id: str`
   - `stop_name: str`
   - `arrival_time: str` — HH:MM display format
   - `departure_time: str` — HH:MM display format

2. `TripSchedule(BaseModel)` — A single scheduled trip:
   - `trip_id: str`
   - `direction_id: int | None = None`
   - `headsign: str | None = None`
   - `first_departure: str` — HH:MM of first stop
   - `last_arrival: str` — HH:MM of last stop
   - `stop_count: int`

3. `DirectionSchedule(BaseModel)` — Schedule for one direction:
   - `direction_id: int | None = None`
   - `headsign: str | None = None`
   - `trip_count: int`
   - `first_departure: str` — HH:MM of earliest trip
   - `last_departure: str` — HH:MM of latest trip
   - `trips: list[TripSchedule]`

4. `RouteSchedule(BaseModel)` — Full schedule response:
   - `route_id: str`
   - `route_short_name: str`
   - `route_long_name: str`
   - `service_date: str` — YYYY-MM-DD
   - `service_type: str` — "weekday", "saturday", "sunday"
   - `trip_count: int`
   - `directions: list[DirectionSchedule]`
   - `summary: str`

All models must have `model_config = ConfigDict(strict=True)` and Google-style docstrings.

**Per-task validation:**
- `uv run ruff format app/core/agents/tools/transit/schemas.py`
- `uv run ruff check app/core/agents/tools/transit/schemas.py` passes
- `uv run mypy app/core/agents/tools/transit/schemas.py` passes with 0 errors
- `uv run pyright app/core/agents/tools/transit/schemas.py` passes with 0 errors

---

### Task 4: Create GTFS time utility functions
**File:** `app/core/agents/tools/transit/get_route_schedule.py` (create new)
**Action:** CREATE

Create the module file with these module-level helper functions (these will be tested via the test file):

1. `_gtfs_time_to_minutes(gtfs_time: str) -> int`:
   - Convert GTFS "HH:MM:SS" or "HH:MM" to minutes since midnight
   - Must handle times > 24:00:00 (e.g., "25:30:00" → 1530)
   - Split on ":", take hours * 60 + minutes

2. `_gtfs_time_to_display(gtfs_time: str) -> str`:
   - Convert GTFS time to "HH:MM" display format
   - Normalize hours > 24 using `% 24` (e.g., "25:30:00" → "01:30")
   - Return `f"{hours:02d}:{minutes:02d}"`

3. `_classify_service_type(query_date: date) -> str`:
   - Return `"saturday"` if Saturday, `"sunday"` if Sunday, else `"weekday"`
   - Import `date` from `datetime`

4. `_validate_date(date_str: str | None) -> tuple[date, str] | str`:
   - If None, return `(today_riga, today_str)` using `Europe/Riga` timezone (use `datetime.now(tz=ZoneInfo("Europe/Riga")).date()`)
   - If provided, parse as `YYYY-MM-DD`, return `(parsed_date, date_str)`
   - On parse error, return actionable error string: `"Invalid date format '{date_str}'. Use YYYY-MM-DD format, e.g., '2026-02-17'."`
   - Import `ZoneInfo` from `zoneinfo` (stdlib, no new dependency needed)

Include all necessary imports:
```python
from __future__ import annotations
import json
import time
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo
from pydantic_ai import RunContext
from app.core.agents.tools.transit.deps import TransitDeps
from app.core.agents.tools.transit.schemas import (
    DirectionSchedule,
    RouteSchedule,
    ScheduleStop,
    TripSchedule,
)
from app.core.agents.tools.transit.static_cache import get_static_cache
from app.core.logging import get_logger
```

Add module docstring and logger:
```python
"""Transit tool: get_route_schedule.

Provides planned timetable data for bus routes by querying static
GTFS data (stop_times, calendar, calendar_dates).
"""
logger = get_logger(__name__)
```

Also define constants:
```python
_MAX_TRIPS_PER_DIRECTION = 30  # Token efficiency cap
```

**Per-task validation:**
- `uv run ruff format app/core/agents/tools/transit/get_route_schedule.py`
- `uv run ruff check app/core/agents/tools/transit/get_route_schedule.py` passes
- `uv run mypy app/core/agents/tools/transit/get_route_schedule.py` passes with 0 errors

---

### Task 5: Implement get_route_schedule tool function
**File:** `app/core/agents/tools/transit/get_route_schedule.py` (modify — add to file from Task 4)
**Action:** UPDATE

Add the main tool function with this exact signature:
```python
async def get_route_schedule(
    ctx: RunContext[TransitDeps],
    route_id: str,
    date: str | None = None,
    direction_id: int | None = None,
    time_from: str | None = None,
    time_until: str | None = None,
) -> str:
```

**Agent-optimized docstring** (CRITICAL — this is read by the LLM for tool selection):
```
"""Look up the planned timetable for a bus route on a specific service date.

WHEN TO USE: Dispatcher asks about scheduled departure times, service hours,
trip frequency, timetable, or "when does route X run?" questions. Returns
the PLANNED schedule from GTFS static data.

WHEN NOT TO USE: For current delays or vehicle positions (use query_bus_status
instead). For historical on-time performance (use get_adherence_report).
For finding stops by name or location (use search_stops).

PARAMETERS:
- route_id: GTFS route ID (e.g., "bus_22"). Required. If unsure, check
  query_bus_status(action="route_overview") output for valid route IDs.
- date: Service date as YYYY-MM-DD. Defaults to today (Riga timezone).
  Use this to check future or past schedules.
- direction_id: 0 or 1 to filter by direction. Omit for both directions.
  Direction 0 is typically outbound, 1 is inbound.
- time_from: Filter trips departing after this time (HH:MM).
  Example: time_from="08:00" to see only morning trips.
- time_until: Filter trips departing before this time (HH:MM).
  Example: time_until="12:00" combined with time_from="08:00".

EFFICIENCY: Always provide direction_id and time_from/time_until when
the question targets a specific period. Without filters, response may
be truncated to 30 trips per direction.

COMPOSITION: Compare with query_bus_status to see if real-time service
matches the planned schedule. Chain: get_route_schedule → query_bus_status
for "is route X running on schedule?" analysis.

Args:
    ctx: Pydantic AI run context with TransitDeps.
    route_id: GTFS route identifier.
    date: Service date (YYYY-MM-DD). Defaults to today.
    direction_id: Direction filter (0 or 1).
    time_from: Start of time window filter (HH:MM).
    time_until: End of time window filter (HH:MM).

Returns:
    JSON string with RouteSchedule data or actionable error message.
"""
```

**Implementation structure** (follow the `query_bus_status` pattern exactly):

1. `start_time = time.monotonic()`
2. Log `transit.get_route_schedule.started` with all params
3. Validate date using `_validate_date(date)` — return error string if invalid
4. Load static cache: `static = await get_static_cache(ctx.deps.http_client, ctx.deps.settings)`
5. Validate route exists: `if route_id not in static.routes:` → return actionable error listing some available routes
6. Get active service IDs: `service_ids = static.get_active_service_ids(query_date)`
7. Get trips for this route+service: filter `static.route_trips.get(route_id, [])` where `trip.service_id in service_ids`
8. If `direction_id is not None`, filter further by `trip.direction_id == direction_id`
9. For each matching trip, get stop times from `static.trip_stop_times.get(trip.trip_id, [])`
10. Apply time_from/time_until filters (compare first stop's departure_time using `_gtfs_time_to_minutes`)
11. Group trips by `direction_id`, build `DirectionSchedule` objects
12. Truncate to `_MAX_TRIPS_PER_DIRECTION` trips per direction
13. Build `RouteSchedule` with summary text
14. Return `json.dumps(result.model_dump(), ensure_ascii=False)`
15. Wrap everything in try/except, log failure, return error string

Add a helper function `_build_direction_schedules(...)` that groups trips by direction and builds the response structure. Each trip becomes a `TripSchedule` with `first_departure` and `last_arrival` from the first and last stop times. Do NOT include individual stops in the default response (token efficiency) — only `stop_count`.

Handle edge cases with actionable error messages:
- Route not found: `"Route '{route_id}' not found in GTFS data. Available routes include: {first_10_route_names}. Check route ID format."`
- No service on date: `"Route {name} exists but has no scheduled service on {date} ({day_name}). Try an adjacent date or check if this is a holiday."`
- No trips in time window: `"Route {name} has {total} trips on {date}, but none between {time_from}-{time_until}. First departure: {first}, last: {last}."`

**Per-task validation:**
- `uv run ruff format app/core/agents/tools/transit/get_route_schedule.py`
- `uv run ruff check app/core/agents/tools/transit/get_route_schedule.py` passes
- `uv run mypy app/core/agents/tools/transit/get_route_schedule.py` passes with 0 errors
- `uv run pyright app/core/agents/tools/transit/get_route_schedule.py` passes with 0 errors

---

### Task 6: Register tool with agent
**File:** `app/core/agents/agent.py` (modify existing)
**Action:** UPDATE

Add import:
```python
from app.core.agents.tools.transit.get_route_schedule import get_route_schedule
```

Update the `tools` list in `create_agent()`:
```python
tools=[query_bus_status, get_route_schedule],
```

That's it — no other changes to this file.

**Per-task validation:**
- `uv run ruff format app/core/agents/agent.py`
- `uv run ruff check app/core/agents/agent.py` passes
- `uv run mypy app/core/agents/agent.py` passes with 0 errors

---

### Task 7: Create unit tests for helper functions
**File:** `app/core/agents/tools/transit/tests/test_get_route_schedule.py` (create new)
**Action:** CREATE

Add `__init__.py` to test directory if missing: `app/core/agents/tools/transit/tests/__init__.py`

Import the helper functions directly:
```python
from app.core.agents.tools.transit.get_route_schedule import (
    _classify_service_type,
    _gtfs_time_to_display,
    _gtfs_time_to_minutes,
    _validate_date,
    get_route_schedule,
)
```

**Test helper functions (pure unit tests, no mocks):**

1. `test_gtfs_time_to_minutes_normal()` — "06:30:00" → 390
2. `test_gtfs_time_to_minutes_midnight()` — "00:00:00" → 0
3. `test_gtfs_time_to_minutes_overnight()` — "25:30:00" → 1530
4. `test_gtfs_time_to_minutes_short_format()` — "06:30" → 390
5. `test_gtfs_time_to_display_normal()` — "06:30:00" → "06:30"
6. `test_gtfs_time_to_display_overnight()` — "25:30:00" → "01:30"
7. `test_classify_service_type_weekday()` — Monday → "weekday"
8. `test_classify_service_type_saturday()` — Saturday → "saturday"
9. `test_classify_service_type_sunday()` — Sunday → "sunday"
10. `test_validate_date_none_returns_today()` — None → (today, str)
11. `test_validate_date_valid()` — "2026-02-17" → (date(2026,2,17), "2026-02-17")
12. `test_validate_date_invalid()` — "not-a-date" → error string containing "Invalid date"

Use `from datetime import date` for creating test dates.

**Per-task validation:**
- `uv run ruff format app/core/agents/tools/transit/tests/test_get_route_schedule.py`
- `uv run ruff check app/core/agents/tools/transit/tests/test_get_route_schedule.py` passes
- `uv run pytest app/core/agents/tools/transit/tests/test_get_route_schedule.py -v` — all pass

---

### Task 8: Create unit tests for tool function
**File:** `app/core/agents/tools/transit/tests/test_get_route_schedule.py` (modify — append to file from Task 7)
**Action:** UPDATE

Add imports:
```python
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
```

**Test the tool function with mocks** (follow `test_query_bus_status.py` pattern exactly):

1. `test_get_route_schedule_route_not_found()`:
   - Mock `get_static_cache` returning a cache with `routes = {}` (empty)
   - Call `get_route_schedule(ctx, route_id="nonexistent")`
   - Assert "not found" in result

2. `test_get_route_schedule_no_service()`:
   - Mock `get_static_cache` returning a cache with:
     - `routes = {"bus_22": RouteInfo(route_id="bus_22", route_short_name="22", route_long_name="Test", route_type=3)}`
     - `route_trips = {"bus_22": [TripInfo(trip_id="t1", route_id="bus_22", service_id="WD")]}`
     - `get_active_service_ids()` returning empty `set()` (no service that day)
   - Call `get_route_schedule(ctx, route_id="bus_22", date="2026-12-25")`
   - Assert "no scheduled service" in result

3. `test_get_route_schedule_success()`:
   - Mock `get_static_cache` with populated data:
     - Routes, trips (2 trips with different directions), stop times (2-3 stops each), calendar returning active service_id
   - Call `get_route_schedule(ctx, route_id="bus_22")`
   - Parse returned JSON, verify `RouteSchedule` structure: `route_id`, `trip_count`, `directions`, `summary`

4. `test_get_route_schedule_invalid_date()`:
   - Call `get_route_schedule(ctx, route_id="bus_22", date="not-a-date")`
   - Assert "Invalid date" in result (no mocks needed — validation fires before cache access)

5. `test_get_route_schedule_direction_filter()`:
   - Mock cache with trips in both directions
   - Call with `direction_id=0`
   - Parse JSON, verify only direction 0 trips returned

6. `test_get_route_schedule_feed_error()`:
   - Mock `get_static_cache` to raise `RuntimeError("Connection refused")`
   - Patch logger to suppress output
   - Assert "Transit data error" in result

**Mock patterns:**
- `ctx = MagicMock()` with `ctx.deps.http_client = AsyncMock()` and `ctx.deps.settings = MagicMock()`
- Patch at: `"app.core.agents.tools.transit.get_route_schedule.get_static_cache"`
- For cache mock: use `MagicMock()` and set attributes directly (`.routes`, `.route_trips`, `.trip_stop_times`)
- For `get_active_service_ids`: set `mock_static.get_active_service_ids.return_value = {"WD"}`
- Import dataclasses from `static_cache` to build realistic mock data: `from app.core.agents.tools.transit.static_cache import RouteInfo, TripInfo, StopTimeEntry`

**Per-task validation:**
- `uv run ruff format app/core/agents/tools/transit/tests/test_get_route_schedule.py`
- `uv run ruff check app/core/agents/tools/transit/tests/test_get_route_schedule.py` passes
- `uv run pytest app/core/agents/tools/transit/tests/test_get_route_schedule.py -v` — all pass

---

### Task 9: Create unit tests for static_cache extensions
**File:** `app/core/agents/tools/transit/tests/test_static_cache.py` (create new)
**Action:** CREATE

Test the new `get_active_service_ids` method and parse methods:

1. `test_get_active_service_ids_weekday()`:
   - Create a `GTFSStaticCache` instance manually
   - Set `cache.calendar` with a `CalendarEntry` that has `monday=True`
   - Call `cache.get_active_service_ids(date(2026, 2, 16))` (Monday)
   - Assert the service_id is in the result

2. `test_get_active_service_ids_exception_removes()`:
   - Set `calendar_dates` with `exception_type=2` for a specific date
   - Assert the service_id is NOT in the result

3. `test_get_active_service_ids_exception_adds()`:
   - Set `calendar_dates` with `exception_type=1` for a date not in calendar
   - Assert the added service_id IS in the result

4. `test_get_active_service_ids_outside_date_range()`:
   - Set `calendar` with `start_date` and `end_date` that don't contain the query date
   - Assert empty result

Import `CalendarEntry`, `CalendarDateException`, `GTFSStaticCache` from static_cache.
Import `date` from `datetime`.

**Per-task validation:**
- `uv run ruff format app/core/agents/tools/transit/tests/test_static_cache.py`
- `uv run ruff check app/core/agents/tools/transit/tests/test_static_cache.py` passes
- `uv run pytest app/core/agents/tools/transit/tests/test_static_cache.py -v` — all pass

---

## Tool Interface

```python
async def get_route_schedule(
    ctx: RunContext[TransitDeps],
    route_id: str,                      # Required: GTFS route ID
    date: str | None = None,            # Optional: YYYY-MM-DD, defaults to today (Riga TZ)
    direction_id: int | None = None,    # Optional: 0 or 1
    time_from: str | None = None,       # Optional: HH:MM filter start
    time_until: str | None = None,      # Optional: HH:MM filter end
) -> str:                               # JSON string or error message
```

**Example calls:**
```python
# Full schedule for route 22 today
get_route_schedule(ctx, route_id="bus_22")

# Sunday schedule, outbound only
get_route_schedule(ctx, route_id="bus_22", date="2026-02-22", direction_id=0)

# Morning trips only
get_route_schedule(ctx, route_id="bus_22", time_from="06:00", time_until="09:00")
```

## Composition

| Workflow | Tool Chain |
|----------|-----------|
| "Is route 22 on schedule?" | `get_route_schedule` → `query_bus_status(action="route_overview")` → compare planned vs actual |
| "When is the last bus today?" | `get_route_schedule` → read `last_departure` from response |
| "Does route 22 run on Sunday?" | `get_route_schedule(date="2026-02-22")` → check if `trip_count > 0` |
| "What stops does route 22 serve?" | Use `search_stops` (future tool) instead — `get_route_schedule` shows times, not stop discovery |

## Logging Events

- `transit.get_route_schedule.started` — Tool invoked (includes route_id, date, direction_id, time_from, time_until)
- `transit.get_route_schedule.completed` — Success (includes duration_ms, trip_count)
- `transit.get_route_schedule.failed` — Error (includes exc_info, error, error_type, duration_ms)

## Testing Strategy

### Unit Tests
**Location:** `app/core/agents/tools/transit/tests/test_get_route_schedule.py`
- Helper functions: time conversion, date validation, service type classification
- Tool function: route not found, no service, success, invalid date, direction filter, feed error

**Location:** `app/core/agents/tools/transit/tests/test_static_cache.py`
- `get_active_service_ids`: weekday match, exception add, exception remove, outside date range

### Edge Cases
- GTFS time > 24:00:00 (overnight trips) — handled by `_gtfs_time_to_minutes` / `_gtfs_time_to_display`
- Route with no trips in the GTFS feed — returns "no scheduled service" message
- Calendar with no entries (some GTFS feeds use only `calendar_dates.txt`) — `get_active_service_ids` handles this
- Empty `stop_times.txt` — tool returns trips with `stop_count=0`
- Missing GTFS files (e.g., no `calendar.txt`) — parse methods guard with `if X not in zf.namelist()`
- Very large route (100+ trips) — truncated to `_MAX_TRIPS_PER_DIRECTION` with truncation message in summary

## Acceptance Criteria

This feature is complete when:
- [ ] Static cache parses `stop_times.txt`, `calendar.txt`, `calendar_dates.txt` from GTFS ZIP
- [ ] `TripInfo` includes `service_id` field
- [ ] `get_active_service_ids()` correctly resolves active services for any date
- [ ] Tool returns valid `RouteSchedule` JSON for existing routes with service
- [ ] Tool returns actionable error messages for: invalid route, no service, invalid date, no trips in window
- [ ] Responses are token-efficient: max 30 trips per direction, no individual stop times in default mode
- [ ] All type checkers pass (mypy + pyright) with 0 errors
- [ ] All tests pass (18+ new tests + existing tests unbroken)
- [ ] Structured logging follows `transit.get_route_schedule.{started|completed|failed}` pattern
- [ ] No type suppressions added
- [ ] Tool registered in `agent.py` tools list
- [ ] No regressions in existing `query_bus_status` tests

## Completion Checklist

Before marking this plan as fully executed:
- [ ] All 9 tasks completed in order
- [ ] Per-task validations passed
- [ ] Full validation pyramid passed (Levels 1-5)
- [ ] No deviations from plan (or deviations documented with reasons)
- [ ] Ready for `/commit`

## Final Validation (5-Level Pyramid)

Run each level in order — every one must pass with 0 errors:

**Level 1: Syntax & Style**
```bash
uv run ruff format .
uv run ruff check .
```

**Level 2: Type Safety**
```bash
uv run mypy app/
uv run pyright app/
```

**Level 3: Unit Tests (feature-specific)**
```bash
uv run pytest app/core/agents/tools/transit/tests/test_get_route_schedule.py app/core/agents/tools/transit/tests/test_static_cache.py -v
```

**Level 4: Full Test Suite (unit)**
```bash
uv run pytest -v -m "not integration"
```

**Level 5: Server Validation (optional)**
```bash
curl -s http://localhost:8123/health
```

**Success definition:** Levels 1-4 exit code 0, all tests pass, zero errors or warnings.

## Dependencies

- **Shared utilities used:** `get_logger` from `app.core.logging`, `TransitDataError` from `app.core.agents.exceptions`
- **Core modules used:** `Settings` from `app.core.config`, `TransitDeps` from deps
- **New dependencies:** None — uses Python stdlib `zoneinfo.ZoneInfo` for timezone, `csv`/`zipfile`/`io` already used
- **New env vars:** None — uses existing `gtfs_static_url` and `gtfs_static_cache_ttl_hours`

## Known Pitfalls

The executing agent MUST follow these rules to avoid common errors:

1. **No `assert` in production code** — Ruff S101 forbids assert outside test files. Use conditional checks: `if route_id not in static.routes:` then return error string.
2. **No `object` type hints** — Import actual types (`date`, `RouteInfo`, etc.). Never use `object` or untyped parameters.
3. **GTFS times exceed 24:00:00** — "25:30:00" is valid GTFS (1:30 AM next day). Do NOT use `datetime.strptime` on these. Parse manually by splitting on ":".
4. **GTFS date format is YYYYMMDD** (no dashes) — `calendar.txt` uses `20260217`, not `2026-02-17`. Convert with `query_date.strftime("%Y%m%d")`.
5. **Mock at consumer path** — Patch `"app.core.agents.tools.transit.get_route_schedule.get_static_cache"`, not the definition path.
6. **`get_active_service_ids` uses `getattr(entry, day_name)`** — The `CalendarEntry` dataclass must have `monday`, `tuesday`, etc. as separate `bool` fields (not a dict) so `getattr` works.
7. **Sort stop times by `stop_sequence`** — GTFS stop_times.txt may not be ordered. Always sort after parsing.
8. **`from __future__ import annotations`** — Include at top of all new files (existing pattern in codebase).
9. **Only import what you use** — Ruff F401 catches unused imports. Don't import `ScheduleStop` in the tool file if you don't use it in the default response mode.

## Notes

- **Future enhancement:** Add `stop_id` parameter to show schedule at a specific stop only (most token-efficient mode). Deferred to keep initial scope manageable.
- **Data freshness:** Schedule data refreshes every 24h (same TTL as existing static cache). Riga updates their GTFS feed roughly weekly.
- **Memory impact:** Adding `stop_times.txt` parsing increases cache memory from ~5MB to ~25-30MB. Acceptable for a server process.
- **No new dependencies:** This tool uses only Python stdlib + existing project dependencies. Zero additional packages.

## Pre-Implementation Checklist

The executing agent MUST verify before writing any code:
- [ ] Read all files listed in "Relevant Files" section
- [ ] Reviewed GTFS documentation for calendar/stop_times field names
- [ ] Understood the `query_bus_status` pattern (function signature, logging, error handling)
- [ ] Clear on task execution order (cache extension → schemas → tool → agent registration → tests)
- [ ] Validation commands are executable: `uv run ruff`, `uv run mypy`, `uv run pyright`, `uv run pytest`
