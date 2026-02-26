# Plan: search_stops Transit Tool

## Feature Metadata
**Feature Type**: New Capability (Agent Tool)
**Estimated Complexity**: Medium
**Primary Systems Affected**: `app/core/agents/tools/transit/`, `app/core/agents/agent.py`

## Feature Description

`search_stops` is the third transit tool for the VTV AI agent. It enables dispatchers to find bus stops by name (fuzzy text search) or by geographic proximity (lat/lon radius search). The tool reads from the GTFS static cache — the same `GTFSStaticCache` singleton already used by `query_bus_status` and `get_route_schedule`.

The PRD lists the data source as "VTV tRPC API", but since that API does not exist yet, this tool will source data from the GTFS static feed (identical approach to `get_route_schedule`). The same Rigas Satiksme GTFS ZIP already contains `stops.txt` with stop names, IDs, and coordinates, which is already parsed into `GTFSStaticCache.stops` as `StopInfo` dataclasses with `stop_lat`/`stop_lon` fields.

This tool serves as the entry point for stop-related workflows. Other tools reference stop IDs (e.g., `query_bus_status(action="stop_departures", stop_id="a0072")`), so dispatchers need a way to discover valid stop IDs from names or locations.

## User Story

As a dispatcher
I want to search for bus stops by name or proximity to a location
So that I can find the correct stop_id to use with other transit tools

## Tool Interface

```python
async def search_stops(
    ctx: RunContext[TransitDeps],
    action: str,                    # "search" | "nearby"
    query: str | None = None,       # Text search term (for "search")
    latitude: float | None = None,  # Center lat (for "nearby")
    longitude: float | None = None, # Center lon (for "nearby")
    radius_meters: int | None = None, # Search radius (for "nearby", default 500)
    limit: int | None = None,       # Max results (default 10, max 25)
) -> str:
```

**Actions:**
- `"search"` — Case-insensitive substring match on stop names. Returns matching stops sorted by name. Requires `query`.
- `"nearby"` — Find stops within a radius of a lat/lon point, sorted by distance. Requires `latitude` and `longitude`. Uses the Haversine formula for distance calculation.

## Composition

- **Before search_stops**: Dispatcher says "where is the nearest stop to X?" or "find stop Brivibas"
- **After search_stops**: Use the returned `stop_id` with `query_bus_status(action="stop_departures", stop_id=...)` for real-time departures, or `get_route_schedule` to check if a specific route serves a stop.

## Solution Approach

Use the existing `GTFSStaticCache.stops` dictionary (already loaded with lat/lon from `stops.txt`). For text search, do case-insensitive substring matching. For proximity search, compute Haversine distances against all stops and return the closest within the radius.

**Approach Decision:**
We chose in-memory search over the GTFS static cache because:
- Stop data is already loaded and cached (24h TTL) by the existing `GTFSStaticCache`
- ~2000 stops for Riga is trivially fast to iterate in-memory
- No new dependencies or external services needed
- Consistent with `get_route_schedule` which also uses static cache instead of the planned tRPC API

**Alternatives Considered:**
- PostGIS spatial queries: Rejected because the database schema doesn't exist yet and this is read-only GTFS data
- VTV tRPC API: Rejected because the CMS backend API is not yet implemented
- External geocoding API: Rejected because stop coordinates are already in the GTFS feed

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, logging patterns, type checking requirements
- `app/core/agents/tools/transit/static_cache.py` (lines 36-43) — `StopInfo` dataclass with `stop_lat`/`stop_lon` fields
- `app/core/agents/tools/transit/static_cache.py` (lines 117-133) — `GTFSStaticCache.__init__` with `self.stops` dict
- `app/core/agents/tools/transit/static_cache.py` (lines 389-411) — `get_static_cache` singleton pattern

### Similar Features (Examples to Follow)
- `app/core/agents/tools/transit/query_bus_status.py` (lines 63-161) — Tool function pattern: docstring, validation, try/except, structured logging
- `app/core/agents/tools/transit/get_route_schedule.py` (lines 210-417) — Tool function with static cache, validation, JSON response
- `app/core/agents/tools/transit/schemas.py` — Response model patterns with `ConfigDict(strict=True)`
- `app/core/agents/tools/transit/tests/test_get_route_schedule.py` — Test patterns: `_make_ctx()`, `_make_mock_static()`, patch `get_static_cache`

### Files to Modify
- `app/core/agents/tools/transit/schemas.py` — Add `StopResult` and `StopSearchResults` response models
- `app/core/agents/agent.py` — Register `search_stops` in tools array

## Research Documentation

- [Haversine formula](https://en.wikipedia.org/wiki/Haversine_formula)
  - Section: Formula
  - Summary: Calculate great-circle distance between two lat/lon points on Earth
  - Use for: Implementing the `nearby` action's distance calculation

## Implementation Plan

### Phase 1: Foundation
Add response schemas (`StopResult`, `StopSearchResults`) to the existing `schemas.py`. Add a `stop_trips` index to `GTFSStaticCache` so we can report which routes serve each stop.

### Phase 2: Core Implementation
Create `search_stops.py` with the tool function, Haversine distance helper, text matching logic, and parameter validation. Follow exact patterns from `query_bus_status.py`.

### Phase 3: Integration & Validation
Register tool with agent, create tests, run full validation pyramid.

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.

### Task 1: Add response schemas for search_stops
**File:** `app/core/agents/tools/transit/schemas.py` (modify existing)
**Action:** UPDATE

Add two new Pydantic models at the end of the file (after the `RouteSchedule` class):

```python
# --- Stop search schemas (search_stops) ---


class StopResult(BaseModel):
    """A single stop returned from a search.

    Attributes:
        stop_id: GTFS stop identifier (use with query_bus_status stop_departures).
        stop_name: Human-readable stop name.
        stop_lat: WGS84 latitude, if available.
        stop_lon: WGS84 longitude, if available.
        distance_meters: Distance from search point in meters (nearby action only).
        routes: List of route short names serving this stop, if available.
    """

    model_config = ConfigDict(strict=True)

    stop_id: str
    stop_name: str
    stop_lat: float | None = None
    stop_lon: float | None = None
    distance_meters: int | None = None
    routes: list[str] | None = None


class StopSearchResults(BaseModel):
    """Results from a stop search operation.

    Attributes:
        action: The search action that was performed.
        query: The search text (for search action).
        result_count: Number of stops returned.
        total_matches: Total matches before limit was applied.
        stops: List of matching stops.
        summary: Pre-formatted text summary for agent to relay to user.
    """

    model_config = ConfigDict(strict=True)

    action: str
    query: str | None = None
    result_count: int
    total_matches: int
    stops: list[StopResult]
    summary: str
```

Also update the module docstring (line 1-5) to mention `search_stops`:
```python
"""Pydantic response schemas for transit tool outputs.

These models define the structured data returned by transit tools
(query_bus_status, get_route_schedule, search_stops). The agent receives
JSON-serialized versions of these models.
"""
```

**Per-task validation:**
- `uv run ruff format app/core/agents/tools/transit/schemas.py`
- `uv run ruff check app/core/agents/tools/transit/schemas.py` passes
- `uv run mypy app/core/agents/tools/transit/schemas.py` passes with 0 errors

---

### Task 2: Add stop-to-routes index to GTFSStaticCache
**File:** `app/core/agents/tools/transit/static_cache.py` (modify existing)
**Action:** UPDATE

Add a new index `stop_routes: dict[str, list[str]]` to `GTFSStaticCache` that maps `stop_id → list of route short names`. This enables reporting which routes serve a stop in search results.

1. Add to `__init__` (after `self.trip_stop_times` line):
   ```python
   self.stop_routes: dict[str, list[str]] = {}
   ```

2. Add a new method `_build_stop_routes_index` after `_build_route_trips_index`:
   ```python
   def _build_stop_routes_index(self) -> None:
       """Build stop_id → list[route_short_name] index from parsed data."""
       stop_route_sets: dict[str, set[str]] = {}
       for trip_id, stop_times in self.trip_stop_times.items():
           trip_info = self.trips.get(trip_id)
           if trip_info is None:
               continue
           route_name = self.get_route_name(trip_info.route_id)
           for st in stop_times:
               if st.stop_id not in stop_route_sets:
                   stop_route_sets[st.stop_id] = set()
               stop_route_sets[st.stop_id].add(route_name)
       self.stop_routes = {
           sid: sorted(routes) for sid, routes in stop_route_sets.items()
       }
   ```

3. Call `self._build_stop_routes_index()` at the end of the `load` method, after `self._build_route_trips_index()` (line 161).

4. Add `stop_routes_count=len(self.stop_routes)` to the logger.info call in `load` (line 168-176).

**Per-task validation:**
- `uv run ruff format app/core/agents/tools/transit/static_cache.py`
- `uv run ruff check app/core/agents/tools/transit/static_cache.py` passes
- `uv run mypy app/core/agents/tools/transit/static_cache.py` passes with 0 errors
- `uv run pyright app/core/agents/tools/transit/static_cache.py` passes

---

### Task 3: Create search_stops tool implementation
**File:** `app/core/agents/tools/transit/search_stops.py` (create new)
**Action:** CREATE

Create the tool module following the exact pattern of `query_bus_status.py` and `get_route_schedule.py`.

Structure:
1. Module docstring
2. Imports: `json`, `time`, `math`, `RunContext`, `TransitDeps`, schemas, `get_static_cache`, `StopInfo`, `get_logger`
3. Constants: `_VALID_ACTIONS`, `_DEFAULT_RADIUS_METERS = 500`, `_MAX_RADIUS_METERS = 2000`, `_DEFAULT_LIMIT = 10`, `_MAX_LIMIT = 25`, `_EARTH_RADIUS_METERS = 6_371_000`
4. Helper: `_haversine_distance(lat1, lon1, lat2, lon2) -> float` — returns meters
5. Helper: `_validate_search_params(action, query, latitude, longitude) -> str | None`
6. Helper: `_search_by_name(stops, stop_routes, query, limit) -> tuple[list, int]`
7. Helper: `_search_nearby(stops, stop_routes, lat, lon, radius, limit) -> tuple[list, int]`
8. Tool function: `search_stops(ctx, action, query, latitude, longitude, radius_meters, limit) -> str`

**Haversine formula implementation:**
```python
def _haversine_distance(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """Calculate great-circle distance between two points in meters."""
    lat1_r = math.radians(lat1)
    lat2_r = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return _EARTH_RADIUS_METERS * c
```

**Tool function agent-optimized docstring must include:**
- WHEN TO USE: Finding stops by name or location for use with other transit tools
- WHEN NOT TO USE: For real-time departures (use query_bus_status), for schedules (use get_route_schedule)
- ACTIONS: "search" (text) and "nearby" (lat/lon)
- EFFICIENCY: Use "search" for name lookups, "nearby" only when location is known
- COMPOSITION: After finding stop_id, chain with query_bus_status(action="stop_departures", stop_id=...)

**search_by_name logic:**
- Case-insensitive substring match on `stop_name`
- Sort results alphabetically by stop name
- Return tuple of (list of StopResult, total_matches count)

**search_nearby logic:**
- Require both lat and lon to be non-None (validated earlier)
- Compute Haversine distance for each stop that has lat/lon
- Filter by radius_meters
- Sort by distance ascending
- Return tuple of (list of StopResult, total_matches count)

**Both helpers** should populate `StopResult.routes` from `stop_routes` index.

**Parameter validation:**
- If `action not in _VALID_ACTIONS`: return actionable error
- If `action == "search"` and not query: return error with example
- If `action == "nearby"` and (latitude is None or longitude is None): return error with example
- Clamp limit to [1, _MAX_LIMIT] range
- Clamp radius_meters to [1, _MAX_RADIUS_METERS] range

**Error handling:** Wrap the main logic in try/except like existing tools. Log start/complete/failed.

**Per-task validation:**
- `uv run ruff format app/core/agents/tools/transit/search_stops.py`
- `uv run ruff check app/core/agents/tools/transit/search_stops.py` passes
- `uv run mypy app/core/agents/tools/transit/search_stops.py` passes with 0 errors
- `uv run pyright app/core/agents/tools/transit/search_stops.py` passes

---

### Task 4: Register search_stops with the agent
**File:** `app/core/agents/agent.py` (modify existing)
**Action:** UPDATE

1. Add import (after the existing tool imports):
   ```python
   from app.core.agents.tools.transit.search_stops import search_stops
   ```

2. Add `search_stops` to the `tools=` list in `create_agent()`:
   ```python
   tools=[query_bus_status, get_route_schedule, search_stops],
   ```

**Per-task validation:**
- `uv run ruff format app/core/agents/agent.py`
- `uv run ruff check app/core/agents/agent.py` passes
- `uv run mypy app/core/agents/agent.py` passes with 0 errors

---

### Task 5: Create unit tests for search_stops
**File:** `app/core/agents/tools/transit/tests/test_search_stops.py` (create new)
**Action:** CREATE

Follow the test patterns from `test_get_route_schedule.py` and `test_query_bus_status.py`.

**Helper functions (with return type annotations!):**

```python
def _make_ctx() -> MagicMock:
    """Create a mock RunContext with TransitDeps."""
    ctx = MagicMock()
    ctx.deps.http_client = AsyncMock()
    ctx.deps.settings = MagicMock()
    return ctx


def _make_mock_static() -> MagicMock:
    """Create a mock GTFSStaticCache with sample stop data."""
    mock = MagicMock()
    mock.stops = {
        "s1": StopInfo(stop_id="s1", stop_name="Brīvības iela", stop_lat=56.9496, stop_lon=24.1052),
        "s2": StopInfo(stop_id="s2", stop_name="Centrālā stacija", stop_lat=56.9440, stop_lon=24.1134),
        "s3": StopInfo(stop_id="s3", stop_name="Brīvības bulvāris", stop_lat=56.9550, stop_lon=24.1100),
        "s4": StopInfo(stop_id="s4", stop_name="Jugla", stop_lat=56.9800, stop_lon=24.1900),
        "s5": StopInfo(stop_id="s5", stop_name="Ziepniekkalns", stop_lat=56.9200, stop_lon=24.0500),
    }
    mock.stop_routes = {
        "s1": ["22", "3"],
        "s2": ["1", "22"],
        "s3": ["22"],
        "s4": ["15"],
        "s5": ["7"],
    }
    return mock
```

**Unit tests for helpers:**

1. `test_haversine_distance_same_point` — distance is 0
2. `test_haversine_distance_known_pair` — verify against a known distance (e.g., Riga center to Jugla ~4km)
3. `test_validate_search_params_invalid_action` — returns error string
4. `test_validate_search_params_search_missing_query` — returns error
5. `test_validate_search_params_search_valid` — returns None
6. `test_validate_search_params_nearby_missing_coords` — returns error
7. `test_validate_search_params_nearby_valid` — returns None

**Tool function tests (patch `get_static_cache`):**

8. `test_search_stops_invalid_action` — returns actionable error
9. `test_search_stops_search_by_name` — query="Brīvības", expect 2 results (Brīvības iela + Brīvības bulvāris)
10. `test_search_stops_search_no_matches` — query="Nonexistent", expect 0 results with helpful message
11. `test_search_stops_search_case_insensitive` — query="brīvības" (lowercase) matches
12. `test_search_stops_nearby_finds_close_stops` — search near s1 coordinates, radius 1000, expect s1 and nearby stops
13. `test_search_stops_nearby_no_results` — search far from all stops with small radius
14. `test_search_stops_nearby_sorted_by_distance` — verify closest stop comes first
15. `test_search_stops_limit_respected` — set limit=1, get exactly 1 result
16. `test_search_stops_routes_populated` — verify `routes` field is populated in results
17. `test_search_stops_feed_error` — patch `get_static_cache` to raise, verify error message

All test function helpers must have return type annotations.

**Per-task validation:**
- `uv run ruff format app/core/agents/tools/transit/tests/test_search_stops.py`
- `uv run ruff check app/core/agents/tools/transit/tests/test_search_stops.py` passes
- `uv run pytest app/core/agents/tools/transit/tests/test_search_stops.py -v` — all tests pass

---

### Task 6: Add stop_routes index test to existing static cache tests
**File:** `app/core/agents/tools/transit/tests/test_static_cache.py` (modify existing)
**Action:** UPDATE

Add one test to verify the `_build_stop_routes_index` method works correctly. This test should:
- Create a `GTFSStaticCache` instance
- Populate `trips`, `trip_stop_times`, and `routes` manually
- Call `_build_stop_routes_index()`
- Assert the `stop_routes` dict has correct mappings

**Per-task validation:**
- `uv run ruff format app/core/agents/tools/transit/tests/test_static_cache.py`
- `uv run ruff check app/core/agents/tools/transit/tests/test_static_cache.py` passes
- `uv run pytest app/core/agents/tools/transit/tests/test_static_cache.py -v` — all tests pass

---

## Logging Events

- `transit.search_stops.started` — when tool function begins (includes action, query/coords)
- `transit.search_stops.completed` — when tool returns results (includes action, result_count, duration_ms)
- `transit.search_stops.failed` — when an exception occurs (includes error, error_type, duration_ms)

## Testing Strategy

### Unit Tests
**Location:** `app/core/agents/tools/transit/tests/test_search_stops.py`
- Haversine distance calculation — correctness for known distances and edge cases
- Parameter validation — all invalid combinations produce actionable errors
- Name search — case insensitivity, substring matching, alphabetical sort
- Nearby search — distance filtering, distance sort, radius clamping
- Result limiting — limit parameter respected
- Routes populated — stop_routes index data appears in results

### Unit Tests (Static Cache)
**Location:** `app/core/agents/tools/transit/tests/test_static_cache.py`
- stop_routes index — correct route name mapping from trip→stop relationships

### Edge Cases
- Empty query string for search — should return validation error
- Query matches all stops — limited to `_MAX_LIMIT`
- Stop without lat/lon — skipped in nearby search, included in name search
- Radius 0 — only exact position matches (unlikely but handled)
- Latvian diacritics in stop names — case-insensitive search handles Unicode via `.lower()`

## Acceptance Criteria

This feature is complete when:
- [ ] `search_stops(action="search", query="Brīvības")` returns matching stops with names, IDs, coordinates, and routes
- [ ] `search_stops(action="nearby", latitude=56.95, longitude=24.11, radius_meters=500)` returns nearby stops sorted by distance
- [ ] Invalid parameters return actionable error messages with examples
- [ ] Response includes `routes` field showing which routes serve each stop
- [ ] All type checkers pass (mypy + pyright)
- [ ] All tests pass (17+ new tests + existing tests unbroken)
- [ ] Structured logging follows `transit.search_stops.{started,completed,failed}` pattern
- [ ] No type suppressions added
- [ ] Tool registered in `app/core/agents/agent.py`
- [ ] No regressions in existing 134 unit tests

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
uv run ruff check .
```

**Level 2: Type Safety**
```bash
uv run mypy app/
uv run pyright app/
```

**Level 3: Unit Tests (feature-specific)**
```bash
uv run pytest app/core/agents/tools/transit/tests/test_search_stops.py -v
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

- Shared utilities used: `app.core.logging.get_logger`
- Core modules used: `app.core.config.Settings`, `app.core.agents.exceptions.TransitDataError`
- New dependencies: None (math module is stdlib)
- New env vars: None

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

## Notes

- The Haversine formula is sufficient for Riga-scale distances (~30km city area). For a global transit system, a faster approximation (equirectangular) could be used, but accuracy matters more here.
- The `stop_routes` index adds a small amount of processing during cache load but provides significant value — dispatchers can see which routes serve a stop without a separate query.
- Future enhancement: add a `stop_id` action to look up a single stop by exact ID (useful when the agent already has a stop_id and needs the name/location). This is deferred per YAGNI.
- Unicode `.lower()` handles Latvian diacritics (ā, ē, ī, ū, ģ, ķ, ļ, ņ, š, ž) correctly in Python 3.12+.

## Pre-Implementation Checklist

The executing agent MUST verify before writing any code:
- [ ] Read all files listed in "Relevant Files" section
- [ ] Reviewed research documentation
- [ ] Understood the solution approach and why alternatives were rejected
- [ ] Clear on task execution order
- [ ] Validation commands are executable in this environment
