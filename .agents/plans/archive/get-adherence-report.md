# Plan: get_adherence_report — On-Time Performance Metrics Tool

## Feature Metadata
**Feature Type**: New Capability (Transit Tool #4)
**Estimated Complexity**: Medium
**Primary Systems Affected**: `app/core/agents/tools/transit/`, `app/core/agents/agent.py`

## Feature Description

`get_adherence_report` is the fourth transit tool for VTV's AI agent. It computes on-time performance metrics for bus routes by comparing real-time GTFS-RT delay data against the planned GTFS static schedule. This gives dispatchers a snapshot-based adherence analysis — how well is a route (or the entire network) performing right now compared to what was planned?

The tool is read-only (safety constraint) and returns structured metrics: on-time percentage, average delay, delay distribution, and per-trip breakdowns. It bridges the gap between `query_bus_status` (individual vehicle status) and aggregate operational intelligence that dispatchers need for shift reporting and performance monitoring.

The PRD lists the data source as "VTV tRPC API," but since the CMS tRPC API is not yet implemented, this tool uses the existing GTFS-RT feeds (real-time delays) cross-referenced with GTFS static data (scheduled times) — the same data sources already proven in `query_bus_status` and `get_route_schedule`. This produces a real-time snapshot report rather than historical analysis, which is the practical MVP approach.

## User Story

As a **dispatcher or planner**
I want to **see on-time performance metrics for a route or the entire network over today's service**
So that **I can identify underperforming routes, prepare shift reports, and make informed operational decisions**

## Solution Approach

Cross-reference real-time GTFS-RT trip updates (delay data per trip) with the GTFS static schedule (planned trips for today). For each active trip, calculate whether it's on-time, late, or early based on configurable thresholds. Aggregate these into route-level and optionally network-level metrics.

**Approach Decision:**
We chose snapshot-based analysis from GTFS-RT + static GTFS because:
- Both data sources are already integrated and cached (`GTFSRealtimeClient`, `GTFSStaticCache`)
- No database or historical storage needed — keeps the tool stateless and read-only
- Matches the existing tool architecture pattern (fetch, compute, return structured JSON)

**Alternatives Considered:**
- **Database-backed historical analysis**: Rejected because VTV has no historical delay storage yet — that's a future feature requiring migrations, a write pipeline, and retention policies
- **VTV tRPC API integration**: Rejected because the CMS tRPC endpoints don't exist yet — the PRD lists this as the future data source but it's not available for MVP

## Tool Interface

```python
async def get_adherence_report(
    ctx: RunContext[TransitDeps],
    route_id: str | None = None,
    date: str | None = None,
    time_from: str | None = None,
    time_until: str | None = None,
) -> str:
```

**Parameters:**
- `route_id`: Optional. GTFS route ID to analyze. If omitted, returns network-wide summary of all routes with active vehicles.
- `date`: Optional. Service date as YYYY-MM-DD. Defaults to today (Riga timezone). Used to determine which scheduled trips to compare against.
- `time_from`: Optional. Start of analysis window (HH:MM). Filters scheduled trips.
- `time_until`: Optional. End of analysis window (HH:MM). Filters scheduled trips.

**Example calls:**
```python
# Single route adherence
get_adherence_report(route_id="bus_22")

# Network-wide summary
get_adherence_report()

# Route adherence for morning peak
get_adherence_report(route_id="bus_22", time_from="07:00", time_until="09:00")
```

## Composition

**Before this tool:**
- `search_stops` → find stop_id → `query_bus_status(action="stop_departures")` → user asks "is the whole route like this?" → `get_adherence_report(route_id=...)`

**After this tool:**
- Agent identifies underperforming route → `get_route_schedule(route_id=...)` to show planned times → `query_bus_status(action="route_overview")` for current vehicle positions

**Workflow chain:**
`get_adherence_report` → identifies problem routes → `query_bus_status(action="route_overview")` for details → `get_route_schedule` for planned schedule comparison

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, logging patterns, type checking requirements
- `app/core/agents/tools/transit/schemas.py` (lines 1-316) — All existing Pydantic schemas; new adherence schemas go here
- `app/core/agents/tools/transit/deps.py` (lines 1-43) — TransitDeps dataclass injected via RunContext
- `app/core/agents/tools/transit/client.py` (lines 1-367) — GTFSRealtimeClient with `fetch_trip_updates()` and `fetch_vehicle_positions()`
- `app/core/agents/tools/transit/static_cache.py` (lines 1-429) — GTFSStaticCache with `get_active_service_ids()`, `route_trips`, `trip_stop_times`
- `app/core/agents/agent.py` (lines 1-57) — Agent creation and tool registration

### Similar Features (Examples to Follow)
- `app/core/agents/tools/transit/get_route_schedule.py` (lines 1-418) — CLOSEST pattern to follow: uses static cache + date validation + time window filtering + direction grouping. Mirror this file's structure almost exactly.
- `app/core/agents/tools/transit/query_bus_status.py` (lines 1-462) — Shows GTFSRealtimeClient usage pattern and delay calculation from trip updates
- `app/core/agents/tools/transit/search_stops.py` (lines 1-326) — Shows action validation, parameter clamping, and summary building pattern

### Test Files (Patterns to Follow)
- `app/core/agents/tools/transit/tests/test_get_route_schedule.py` (lines 1-284) — CLOSEST test pattern: `_make_ctx()` and `_make_mock_static()` helpers, mock patching, JSON response assertions
- `app/core/agents/tools/transit/tests/test_query_bus_status.py` (lines 1-154) — Shows helper function unit tests and error case patterns

### Files to Modify
- `app/core/agents/tools/transit/schemas.py` — Add adherence report schemas
- `app/core/agents/agent.py` — Import and register `get_adherence_report`

## Implementation Plan

### Phase 1: Foundation (Schemas)
Add Pydantic response schemas for the adherence report output.

### Phase 2: Core Implementation (Tool)
Implement the `get_adherence_report` tool function with GTFS-RT + static cross-referencing.

### Phase 3: Integration & Validation (Agent + Tests)
Register tool with agent, write comprehensive tests, validate full pyramid.

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.

---

### Task 1: Add adherence report schemas to schemas.py
**File:** `app/core/agents/tools/transit/schemas.py` (modify existing)
**Action:** UPDATE

Add the following schemas at the end of the file (after the `StopSearchResults` class, around line 316):

**Update the module docstring** (line 1-5) to include `get_adherence_report` in the list of tools.

**Add these classes:**

1. `TripAdherence` — Per-trip on-time status:
   - `trip_id: str` — GTFS trip identifier
   - `direction_id: int | None = None` — Direction (0=outbound, 1=inbound)
   - `headsign: str | None = None` — Trip destination label
   - `scheduled_departure: str` — HH:MM planned first stop departure
   - `delay_seconds: int = 0` — Current schedule deviation (positive=late, negative=early)
   - `delay_description: str = "on time"` — Human-readable delay text
   - `status: str = "on_time"` — One of "on_time", "late", "early", "no_data"
   - `vehicle_id: str | None = None` — Fleet vehicle on this trip, if known

2. `RouteAdherence` — Per-route aggregated metrics:
   - `route_id: str` — GTFS route identifier
   - `route_short_name: str` — Human-readable route number
   - `scheduled_trips: int` — Total trips scheduled for the period
   - `tracked_trips: int` — Trips with real-time data available
   - `on_time_count: int` — Trips within +/- 300 seconds of schedule
   - `late_count: int` — Trips more than 300 seconds late
   - `early_count: int` — Trips more than 300 seconds early
   - `no_data_count: int` — Scheduled trips without real-time data
   - `on_time_percentage: float` — Percentage of tracked trips that are on time
   - `average_delay_seconds: float` — Mean delay across tracked trips
   - `worst_trip: TripAdherence | None = None` — Trip with highest absolute delay
   - `trips: list[TripAdherence] = []` — Individual trip details (may be truncated)

3. `AdherenceReport` — Top-level report:
   - `report_type: str` — "route" or "network"
   - `route_id: str | None = None` — Route ID if single-route report
   - `service_date: str` — ISO date (YYYY-MM-DD)
   - `service_type: str` — "weekday", "saturday", "sunday"
   - `time_from: str | None = None` — Start of analysis window, if filtered
   - `time_until: str | None = None` — End of analysis window, if filtered
   - `routes: list[RouteAdherence]` — Per-route metrics (one item for route report, many for network)
   - `network_on_time_percentage: float | None = None` — Overall network on-time % (network report only)
   - `network_average_delay_seconds: float | None = None` — Overall network avg delay (network report only)
   - `summary: str` — Pre-formatted text summary

All models use `model_config = ConfigDict(strict=True)` and Google-style docstrings with Attributes section, matching existing schemas.

**Per-task validation:**
- `uv run ruff format app/core/agents/tools/transit/schemas.py`
- `uv run ruff check app/core/agents/tools/transit/schemas.py`
- `uv run mypy app/core/agents/tools/transit/schemas.py`

---

### Task 2: Create get_adherence_report tool implementation
**File:** `app/core/agents/tools/transit/get_adherence_report.py` (create new)
**Action:** CREATE

**Module docstring:**
```python
"""Transit tool: get_adherence_report.

Computes on-time performance metrics by cross-referencing real-time
GTFS-RT delay data with the planned GTFS static schedule.
"""
```

**Imports to use:**
```python
from __future__ import annotations

import json
import time
from datetime import date, datetime
from zoneinfo import ZoneInfo

from pydantic_ai import RunContext

from app.core.agents.tools.transit.client import GTFSRealtimeClient, TripUpdateData
from app.core.agents.tools.transit.deps import TransitDeps
from app.core.agents.tools.transit.schemas import (
    AdherenceReport,
    RouteAdherence,
    TripAdherence,
)
from app.core.agents.tools.transit.static_cache import (
    TripInfo,
    StopTimeEntry,
    get_static_cache,
)
from app.core.logging import get_logger
```

**Constants:**
```python
_RIGA_TZ = ZoneInfo("Europe/Riga")
_ON_TIME_THRESHOLD = 300  # +/- 5 minutes
_MAX_TRIPS_PER_ROUTE = 30  # Token efficiency cap
_MAX_ROUTES_NETWORK = 15  # Cap for network-wide report
```

**Helper functions to implement:**

1. `_validate_date(date_str: str | None) -> tuple[date, str] | str` — Reuse the exact same logic from `get_route_schedule.py`. Copy it here (don't import, to keep tools independent per VTV's vertical slice pattern — each tool is self-contained). Parse YYYY-MM-DD or default to today in Riga timezone.

2. `_classify_service_type(query_date: date) -> str` — Same as `get_route_schedule.py`. Returns "weekday", "saturday", or "sunday".

3. `_gtfs_time_to_minutes(gtfs_time: str) -> int` — Same as `get_route_schedule.py`. Convert "HH:MM:SS" to minutes since midnight.

4. `_gtfs_time_to_display(gtfs_time: str) -> str` — Same as `get_route_schedule.py`. Convert to HH:MM, normalizing >24h.

5. `_delay_description(delay_seconds: int) -> str` — Same as `query_bus_status.py`. Convert delay to "on time", "3 min late", etc.

6. `_classify_trip_status(delay_seconds: int) -> str` — New. Returns "on_time" if `abs(delay) <= _ON_TIME_THRESHOLD`, "late" if `delay > _ON_TIME_THRESHOLD`, "early" if `delay < -_ON_TIME_THRESHOLD`.

7. `_compute_route_adherence(route_id: str, route_name: str, scheduled_trips: list[TripInfo], trip_update_map: dict[str, TripUpdateData], trip_stop_times: dict[str, list[StopTimeEntry]], time_from_minutes: int | None, time_until_minutes: int | None) -> RouteAdherence` — Core computation function. For each scheduled trip:
   - Check if it falls within the time window (using first departure time from stop_times)
   - Look up the trip in `trip_update_map` to get delay data
   - If found: use the first stop_time_update's arrival_delay or departure_delay
   - If not found: mark as "no_data"
   - Aggregate into counts and percentages
   - Find worst trip (highest absolute delay)
   - Truncate trip list to `_MAX_TRIPS_PER_ROUTE`

**Main tool function:**

```python
async def get_adherence_report(
    ctx: RunContext[TransitDeps],
    route_id: str | None = None,
    date: str | None = None,
    time_from: str | None = None,
    time_until: str | None = None,
) -> str:
```

**Agent-optimized docstring (CRITICAL — follow this exactly):**

```
"""Analyze on-time performance for a route or the entire transit network.

WHEN TO USE: Dispatcher asks about punctuality, on-time performance,
service reliability, delay patterns, or "how is route X performing today?"
questions. Returns aggregate metrics comparing real-time data vs schedule.

WHEN NOT TO USE: For current vehicle positions or delays (use query_bus_status).
For the planned timetable without real-time comparison (use get_route_schedule).
For finding stops (use search_stops).

PARAMETERS:
- route_id: GTFS route ID for single-route analysis. Omit for network-wide
  summary of all routes with active vehicles. Network reports are capped at
  15 routes sorted by worst on-time percentage.
- date: Service date as YYYY-MM-DD. Defaults to today (Riga timezone).
  Determines which scheduled trips to compare against.
- time_from: Start of analysis window (HH:MM). Filters to trips departing
  after this time. Example: "07:00" for morning peak analysis.
- time_until: End of analysis window (HH:MM). Filters to trips departing
  before this time.

EFFICIENCY: For quick network health checks, omit route_id.
For detailed single-route analysis, always provide route_id.
Use time_from/time_until to focus on peak periods.

COMPOSITION: After identifying underperforming routes, use
query_bus_status(action="route_overview") for live vehicle details, or
get_route_schedule for the planned timetable comparison.

Args:
    ctx: Pydantic AI run context with TransitDeps.
    route_id: GTFS route identifier for single-route report, or None for network.
    date: Service date (YYYY-MM-DD). Defaults to today.
    time_from: Start of time window filter (HH:MM).
    time_until: End of time window filter (HH:MM).

Returns:
    JSON string with AdherenceReport data or actionable error message.
"""
```

**Implementation logic:**

1. Log `transit.get_adherence_report.started` with all parameters
2. Validate date using `_validate_date()`
3. Fetch static cache and GTFS-RT trip updates:
   ```python
   client = GTFSRealtimeClient(ctx.deps.http_client, ctx.deps.settings)
   static = await get_static_cache(ctx.deps.http_client, ctx.deps.settings)
   trip_updates = await client.fetch_trip_updates()
   ```
4. Build `trip_update_map: dict[str, TripUpdateData]` from trip updates (keyed by trip_id)
5. Get active service IDs for the date: `static.get_active_service_ids(query_date)`
6. Compute time window bounds if `time_from`/`time_until` provided
7. **If route_id provided:**
   - Validate route exists in `static.routes`
   - Get route's scheduled trips filtered by active service IDs
   - Call `_compute_route_adherence()`
   - Set `report_type = "route"`
8. **If route_id is None (network report):**
   - Iterate all routes that have at least one trip update in `trip_update_map`
   - Call `_compute_route_adherence()` for each
   - Sort by `on_time_percentage` ascending (worst first)
   - Truncate to `_MAX_ROUTES_NETWORK`
   - Compute network-level averages
   - Set `report_type = "network"`
9. Build summary string
10. Return JSON-serialized `AdherenceReport`
11. Log `transit.get_adherence_report.completed` with duration_ms and key metrics
12. Wrap in try/except for `TransitDataError` and general exceptions — return actionable error message on failure

**Error handling pattern** (match existing tools exactly):
```python
except Exception as e:
    duration_ms = int((time.monotonic() - start_time) * 1000)
    logger.error(
        "transit.get_adherence_report.failed",
        exc_info=True,
        error=str(e),
        error_type=type(e).__name__,
        duration_ms=duration_ms,
    )
    return (
        f"Transit data error: {e}. "
        "The GTFS data service may be temporarily unavailable. "
        "Try again in 30 seconds."
    )
```

**Per-task validation:**
- `uv run ruff format app/core/agents/tools/transit/get_adherence_report.py`
- `uv run ruff check app/core/agents/tools/transit/get_adherence_report.py`
- `uv run mypy app/core/agents/tools/transit/get_adherence_report.py`
- `uv run pyright app/core/agents/tools/transit/get_adherence_report.py`

---

### Task 3: Register tool with the agent
**File:** `app/core/agents/agent.py` (modify existing)
**Action:** UPDATE

Add import (after the search_stops import on line 15):
```python
from app.core.agents.tools.transit.get_adherence_report import get_adherence_report
```

Add tool to the tools list in `create_agent()` (line 50, after `search_stops`):
```python
tools=[query_bus_status, get_route_schedule, search_stops, get_adherence_report],
```

**Per-task validation:**
- `uv run ruff format app/core/agents/agent.py`
- `uv run ruff check app/core/agents/agent.py`
- `uv run mypy app/core/agents/agent.py`

---

### Task 4: Create comprehensive test suite
**File:** `app/core/agents/tools/transit/tests/test_get_adherence_report.py` (create new)
**Action:** CREATE

**Test file structure** — follow the pattern from `test_get_route_schedule.py`:

**Imports:**
```python
"""Tests for get_adherence_report transit tool."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.agents.tools.transit.get_adherence_report import (
    _classify_trip_status,
    _delay_description,
    _gtfs_time_to_display,
    _gtfs_time_to_minutes,
    _validate_date,
    get_adherence_report,
)
from app.core.agents.tools.transit.client import TripUpdateData, StopTimeUpdateData
from app.core.agents.tools.transit.static_cache import (
    RouteInfo,
    StopTimeEntry,
    TripInfo,
)
```

**Helper functions** (with return type annotations — CRITICAL for mypy):
```python
def _make_ctx() -> MagicMock:
    ctx = MagicMock()
    ctx.deps.http_client = AsyncMock()
    ctx.deps.settings = MagicMock()
    return ctx

def _make_mock_static() -> MagicMock:
    # Create mock with bus_22 route, 3 trips (t1, t2, t3) with service_id "WD"
    # t1: direction 0, departs 06:00, t2: direction 0, departs 08:00
    # t3: direction 1, departs 07:00
    # Include trip_stop_times for all three
    ...

def _make_trip_update(trip_id: str, delay_seconds: int, vehicle_id: str | None = None) -> TripUpdateData:
    # Build a TripUpdateData with one StopTimeUpdateData having the given delay
    ...
```

**Unit tests for helper functions (8 tests):**

1. `test_gtfs_time_to_minutes_normal` — "06:30:00" → 390
2. `test_gtfs_time_to_minutes_overnight` — "25:30:00" → 1530
3. `test_gtfs_time_to_display_normal` — "06:30:00" → "06:30"
4. `test_gtfs_time_to_display_overnight` — "25:30:00" → "01:30"
5. `test_validate_date_none_returns_today` — None → (date, str) tuple for today
6. `test_validate_date_invalid` — "bad-date" → error string with "Invalid date"
7. `test_classify_trip_status_on_time` — 120 → "on_time", -120 → "on_time"
8. `test_classify_trip_status_late_and_early` — 400 → "late", -400 → "early"
9. `test_delay_description_values` — 0 → "on time", 300 → "5 min late", -180 → "3 min early"

**Tool function tests with mocks (10 tests):**

10. `test_get_adherence_report_invalid_date` — Pass bad date → "Invalid date" in result
11. `test_get_adherence_report_route_not_found` — Pass nonexistent route → "not found" in result
12. `test_get_adherence_report_no_service` — No active service IDs → "no scheduled service" in result
13. `test_get_adherence_report_single_route_success` — Route with 3 scheduled trips, 2 with real-time data (one on-time, one late), 1 no-data → verify JSON output:
    - `report_type == "route"`
    - `routes[0].scheduled_trips == 3`
    - `routes[0].tracked_trips == 2`
    - `routes[0].on_time_count == 1`
    - `routes[0].late_count == 1`
    - `routes[0].no_data_count == 1`
    - `on_time_percentage == 50.0`
    - `summary` contains route name
14. `test_get_adherence_report_all_on_time` — All trips with delays < 300s → `on_time_percentage == 100.0`
15. `test_get_adherence_report_network_report` — No route_id → `report_type == "network"`, multiple routes in result, `network_on_time_percentage` present
16. `test_get_adherence_report_time_window_filter` — time_from="07:00" → only trips departing after 07:00 included
17. `test_get_adherence_report_worst_trip_identified` — Verify `worst_trip` has the highest absolute delay
18. `test_get_adherence_report_feed_error` — Mock `get_static_cache` to raise RuntimeError → "Transit data error" in result
19. `test_get_adherence_report_no_realtime_data` — Empty trip updates → all trips marked "no_data", on_time_percentage = 0.0

**Mocking pattern** (follow existing tests exactly):
```python
@pytest.mark.asyncio
async def test_example():
    ctx = _make_ctx()
    mock_static = _make_mock_static()
    mock_client = AsyncMock()
    mock_client.fetch_trip_updates.return_value = [...]

    with (
        patch(
            "app.core.agents.tools.transit.get_adherence_report.GTFSRealtimeClient",
            return_value=mock_client,
        ),
        patch(
            "app.core.agents.tools.transit.get_adherence_report.get_static_cache",
            return_value=mock_static,
        ),
    ):
        result = await get_adherence_report(ctx, route_id="bus_22", date="2026-02-17")

    import json
    data = json.loads(result)
    assert data["report_type"] == "route"
```

**Per-task validation:**
- `uv run ruff format app/core/agents/tools/transit/tests/test_get_adherence_report.py`
- `uv run ruff check app/core/agents/tools/transit/tests/test_get_adherence_report.py`
- `uv run pytest app/core/agents/tools/transit/tests/test_get_adherence_report.py -v` — all tests pass

---

## Migration

No database migrations needed. This tool is stateless — it reads from GTFS-RT feeds and static GTFS data only.

## Logging Events

- `transit.get_adherence_report.started` — When tool function is entered. Includes: route_id, date, time_from, time_until.
- `transit.get_adherence_report.completed` — When result is successfully computed. Includes: duration_ms, report_type, route_count (number of routes analyzed), total_tracked_trips.
- `transit.get_adherence_report.failed` — When an exception occurs. Includes: exc_info=True, error, error_type, duration_ms.

## Testing Strategy

### Unit Tests
**Location:** `app/core/agents/tools/transit/tests/test_get_adherence_report.py`
- Helper functions: `_validate_date`, `_gtfs_time_to_minutes`, `_gtfs_time_to_display`, `_classify_trip_status`, `_delay_description`
- Core computation: `_compute_route_adherence` via tool function tests with mock data

### Integration-Style Tests (via mocking)
**Location:** Same file
- Single-route report with mixed adherence data
- Network-wide report with multiple routes
- Time window filtering
- Error handling (feed errors, no data)
- Edge cases (all on-time, no real-time data, route not found)

### Edge Cases
- Route exists but no real-time data → all trips "no_data", 0% on-time
- Route exists but no scheduled service on date → actionable error message
- Network report with no active vehicles → empty routes list with summary
- Time window filter excludes all trips → actionable error with actual service hours
- Empty trip update delay (delay=0) → counted as on-time

## Acceptance Criteria

This feature is complete when:
- [ ] `AdherenceReport`, `RouteAdherence`, and `TripAdherence` schemas defined in `schemas.py`
- [ ] `get_adherence_report` tool function implemented with agent-optimized docstring
- [ ] Tool registered in `agent.py` tools list
- [ ] 19+ unit tests pass covering helpers, happy paths, error cases, and edge cases
- [ ] All type checkers pass (mypy + pyright) with zero errors
- [ ] Structured logging follows `transit.get_adherence_report.{started|completed|failed}` pattern
- [ ] No type suppressions added
- [ ] No regressions in existing 154 tests

## Completion Checklist

Before marking this plan as fully executed:
- [ ] All tasks completed in order (1 → 2 → 3 → 4)
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
uv run pytest app/core/agents/tools/transit/tests/test_get_adherence_report.py -v
```

**Level 4: Full Test Suite (unit)**
```bash
uv run pytest -v -m "not integration"
```

**Level 5: Server Validation (if Docker running)**
```bash
uv run uvicorn app.main:app --port 8123 &
sleep 3
curl -s http://localhost:8123/health
kill %1
```

**Success definition:** Levels 1-4 exit code 0, all tests pass, zero errors or warnings. Level 5 optional.

## Dependencies

- **Shared utilities used:** `app.core.logging.get_logger`
- **Core modules used:** `app.core.config.Settings`, `app.core.agents.exceptions.TransitDataError`
- **Transit modules used:** `GTFSRealtimeClient`, `GTFSStaticCache`, `TransitDeps`, all from existing transit tools
- **New dependencies:** None (all data sources already integrated)
- **New env vars:** None

## Known Pitfalls

The executing agent MUST follow these rules to avoid common errors:

1. **No `assert` in production code** — Ruff S101 forbids assert outside test files. Use conditional checks instead.
   - BAD: `assert cache is not None`
   - GOOD: `if cache is not None:`
2. **No `object` type hints** — Import and use actual types directly. Never write `def f(data: object)` then isinstance-check.
3. **Untyped third-party libraries** — Not applicable here (all deps are typed).
4. **Mock exceptions must match catch blocks** — If production code catches a general `Exception`, mocking with `RuntimeError` is fine (it's a subclass). But don't mock with a different exception hierarchy.
5. **No unused imports or variables** — Ruff F401 catches unused imports, Ruff F841 catches unused local variables. Don't write speculative code — only import/assign what you actually use.
6. **No unnecessary noqa/type-ignore** — Ruff RUF100 flags unused suppression comments.
7. **Test helper functions need return type annotations** — Always add `-> ReturnType` to test helpers (e.g., `def _make_ctx() -> MagicMock:`). Without this, mypy `no-untyped-call` will fail when tests call these helpers.
8. **Copy helper functions, don't import from other tools** — `_validate_date`, `_gtfs_time_to_minutes`, etc. exist in `get_route_schedule.py`. Copy them into the new file. VTV's tool pattern keeps each tool self-contained — tools don't import from each other (check all 3 existing tools: none import from sibling tools).
9. **Use `from __future__ import annotations`** — Required at top of every production Python file for forward reference support.
10. **Division by zero** — When computing `on_time_percentage`, guard against `tracked_trips == 0`. Return 0.0 in that case.

## Notes

- **Future evolution:** When VTV's CMS tRPC API is implemented with historical delay storage, this tool can be extended to query historical data for multi-day trend analysis. The schema is designed to accommodate this — `service_date` already supports arbitrary dates.
- **Performance:** The tool makes 1 HTTP call (trip_updates feed, ~20s cache TTL) + uses the static cache (24h TTL). Computation is O(trips × stops) which is fast for Riga's ~80 routes.
- **Token efficiency:** Network reports are capped at 15 routes and 30 trips per route. Summaries are pre-formatted so the agent can relay them directly without reformatting.
- **Data freshness:** Real-time data reflects the current state of the GTFS-RT feed. The report is a "point in time" snapshot, not a historical analysis. The summary should make this clear.

## Pre-Implementation Checklist

The executing agent MUST verify before writing any code:
- [ ] Read all files listed in "Relevant Files" section
- [ ] Understood the solution approach: GTFS-RT delays cross-referenced with GTFS static schedule
- [ ] Clear on task execution order: schemas → tool → agent registration → tests
- [ ] Validation commands are executable in this environment (`uv run ruff`, `uv run mypy`, `uv run pytest`)
