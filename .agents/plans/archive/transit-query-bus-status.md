# Plan: Transit Tool — `query_bus_status`

## Feature Metadata
**Feature Type**: New Capability (First AI Agent Tool)
**Estimated Complexity**: High
**Primary Systems Affected**: `app/core/agents/` (agent factory, deps, tool registration), new `app/core/agents/tools/transit/` package

## Feature Description

This is the first of 5 transit tools for VTV's Pydantic AI agent. `query_bus_status` enables dispatchers to ask natural language questions about bus delays, positions, and operational status — and get real-time answers from Rigas Satiksme's publicly available GTFS-Realtime feeds.

The tool fetches live protobuf data from `saraksti.rigassatiksme.lv`, merges vehicle positions with trip updates and static GTFS route/stop names, and returns structured, dispatcher-friendly results. It supports three query modes: single vehicle/route status, route-wide overview with headway analysis, and upcoming departures at a stop.

This implementation also introduces the **agent dependency injection pattern** (`Agent[TransitDeps, str]` replacing `Agent[None, str]`), which all future tools (transit + Obsidian) will use. The deps pattern provides an `httpx.AsyncClient` for GTFS-RT fetching and is designed for testability via Pydantic AI's `override` mechanism.

### What Differentiates VTV

**Industry context (from research):**
- **Swiftly** charges $50K+/year, focuses on large US agencies. VTV targets EU municipal operators below procurement thresholds.
- **Optibus** is planning-focused. VTV is operations-focused with AI-first dispatch.
- **No competitor** offers a natural language interface to GTFS-RT data. Dispatchers currently switch between 3-4 tools.

**VTV's novel approach:**
1. **Natural language → structured transit data**: Dispatcher asks "Is route 22 running on time?" and gets delay seconds, vehicle positions, headway gaps — all from a single conversational query.
2. **Agent-optimized responses**: Tool output includes both structured data (for agent reasoning) and a `summary` field (pre-formatted text for direct relay to the user).
3. **Severity tagging**: Every result includes severity level (normal/warning/critical) so the agent can prioritize what to surface first.
4. **Forward-compatible schema**: Includes nullable `predicted_delay_seconds` field for future ML-based delay prediction without schema changes.
5. **Free, open data**: Rigas Satiksme publishes unauthenticated GTFS-RT feeds — zero data acquisition cost.

## User Story

As a **dispatcher** at Rigas Satiksme,
I want to ask the AI assistant about current bus status in plain language,
So that I can quickly identify delays, assess route performance, and make informed operational decisions without switching between multiple monitoring tools.

## Solution Approach

We build a Pydantic AI tool function that fetches and merges two GTFS-RT protobuf feeds (vehicle positions + trip updates) from Rigas Satiksme's public endpoints, cross-references with cached static GTFS data (route names, stop names), and returns dispatcher-friendly structured results.

**Architecture:**
```
query_bus_status(ctx, action, route_id?, vehicle_id?, stop_id?)
     │
     ├── GTFSRealtimeClient (async httpx, connection-pooled)
     │   ├── fetch_vehicle_positions()  →  vehicle_positions.pb
     │   ├── fetch_trip_updates()       →  trip_updates.pb
     │   └── fetch_alerts()             →  gtfs_realtime.pb (ServiceAlert entities)
     │
     ├── GTFSStaticCache (in-memory, loaded at startup, daily refresh)
     │   ├── routes: dict[str, RouteInfo]
     │   ├── stops: dict[str, StopInfo]
     │   └── trips: dict[str, TripInfo]
     │
     └── Merger: joins RT + static → structured BusStatus / RouteOverview / StopDepartures
```

**Approach Decision:**
We chose live GTFS-RT feeds with in-memory caching because:
- Rigas Satiksme endpoints are free, unauthenticated, and refresh every 15-30 seconds
- Protobuf parsing is lightweight (<10ms for ~1000 vehicles)
- In-memory cache with 20-second TTL avoids hammering the feed while ensuring fresh data
- The `httpx.AsyncClient` in deps enables connection pooling and easy test mocking

**Alternatives Considered:**
- **Database-backed feed storage**: Rejected — adds complexity for real-time data that's stale in 30 seconds. Archival for ML training is a future concern.
- **Direct REST API (departures2.php)**: Rejected — only supports stop-centric queries, not vehicle/route queries. The protobuf feeds are more complete and standardized.
- **Mock data only**: Rejected — real feeds are freely available, and testing against live data validates the tool's real-world behavior.

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, logging patterns, type checking requirements
- `reference/mvp-tool-designs.md` — Agent tool design principles (token efficiency, dry_run, actionable errors)
- `reference/PRD.md` (Section 6) — Agent architecture, tool list, safety constraints

### Agent Module (Patterns to Follow)
- `app/core/agents/agent.py` (lines 1-50) — Agent factory, singleton pattern, system prompt. **MUST be modified** to add deps type and tool registration.
- `app/core/agents/config.py` (lines 1-68) — Model resolution pattern. No changes needed.
- `app/core/agents/service.py` (lines 1-103) — Service orchestration, `agent.run()` call at line 59. **MUST be modified** to pass deps to `agent.run()`.
- `app/core/agents/schemas.py` (lines 1-89) — OpenAI-compatible schemas. No changes needed.
- `app/core/agents/exceptions.py` (lines 1-82) — Exception hierarchy. May need new `TransitDataError` subclass.
- `app/core/agents/tests/test_service.py` (lines 1-63) — Test patterns: `agent.override(model=TestModel())`, `patch("...logger")`. **MUST be updated** for new deps signature.

### Configuration
- `app/core/config.py` (lines 1-67) — Settings class. **MUST be modified** to add GTFS-RT URLs and transit config.
- `.env.example` (lines 1-23) — Environment variables. **MUST be updated** with transit settings.

### Files to Modify
- `app/core/agents/agent.py` — Change `Agent[None, str]` → `Agent[TransitDeps, str]`, register tool
- `app/core/agents/service.py` — Pass deps to `agent.run()`
- `app/core/agents/exceptions.py` — Add `TransitDataError`
- `app/core/config.py` — Add transit feed URLs
- `.env.example` — Add transit env vars
- `pyproject.toml` — Add `gtfs-realtime-bindings` and `httpx` dependencies
- `app/core/agents/tests/test_service.py` — Update for deps pattern

## Research Documentation

Use these resources for implementation guidance:

- [GTFS-Realtime Reference](https://gtfs.org/documentation/realtime/reference/)
  - Section: VehiclePosition, TripUpdate, ServiceAlert entity definitions
  - Summary: Defines the protobuf schema for real-time transit data
  - Use for: Understanding feed structure when implementing `GTFSRealtimeClient`

- [Python GTFS-RT Bindings](https://pypi.org/project/gtfs-realtime-bindings/)
  - Summary: `from google.transit import gtfs_realtime_pb2` — parse protobuf feeds
  - Use for: Task 5 (GTFSRealtimeClient implementation)

- [Pydantic AI Tool Registration](https://ai.pydantic.dev/tools/)
  - Section: `@agent.tool` decorator, `RunContext[DepsType]`
  - Summary: Tools receive `RunContext` as first arg, deps accessible via `ctx.deps`
  - Use for: Task 8 (tool function implementation)

- [Rigas Satiksme GTFS-RT Feeds](https://saraksti.rigassatiksme.lv/)
  - Endpoints: `vehicle_positions.pb`, `trip_updates.pb`, `gtfs_realtime.pb`
  - No authentication required
  - Use for: Configuration values in Task 2

## Tool Interface

### Function Signature
```python
@agent.tool
async def query_bus_status(
    ctx: RunContext[TransitDeps],
    action: str,
    route_id: str | None = None,
    vehicle_id: str | None = None,
    stop_id: str | None = None,
) -> str:
```

### Actions

| Action | Required Params | Returns |
|--------|----------------|---------|
| `status` | `vehicle_id` OR `route_id` | Current position, delay, next stop, alerts for one or more vehicles |
| `route_overview` | `route_id` | All active vehicles on route with delays, headway analysis, aggregate stats |
| `stop_departures` | `stop_id` | Upcoming departures at a stop with real-time predictions |

### Agent-Optimized Docstring (must be included verbatim)
```
"""Query real-time bus status, delays, and positions for Riga's transit network.

WHEN TO USE: Dispatcher asks about bus delays, vehicle locations, route performance,
or upcoming departures at a stop. This is the primary tool for real-time operations.

WHEN NOT TO USE: For historical performance analysis (use get_adherence_report),
for timetable/schedule lookups (use get_route_schedule), or for finding stops by
name or location (use search_stops).

ACTIONS:
- "status": Get current status of a specific vehicle or all vehicles on a route.
  Requires vehicle_id OR route_id. Returns position, delay, next stop.
- "route_overview": Aggregate view of all vehicles on a route with headway analysis.
  Requires route_id. Best for "how is route X performing?" questions.
- "stop_departures": Upcoming departures at a specific stop with real-time predictions.
  Requires stop_id. Best for "when is the next bus at stop Y?" questions.

EFFICIENCY: Use "status" with vehicle_id for single-vehicle queries (fastest).
Use "route_overview" only when the dispatcher asks about overall route performance.

COMPOSITION: After this tool, consider get_route_schedule to compare against planned
timetable, or get_adherence_report for historical context.
"""
```

### Example Calls
```python
# Single vehicle status
query_bus_status(action="status", vehicle_id="4521")

# All vehicles on route 22
query_bus_status(action="status", route_id="22")

# Route overview with headway analysis
query_bus_status(action="route_overview", route_id="22")

# Upcoming departures at a stop
query_bus_status(action="stop_departures", stop_id="a0072")
```

## Composition

### Multi-Tool Workflows
```
Dispatcher: "Why is route 22 always late?"
Agent workflow:
  1. query_bus_status(action="route_overview", route_id="22")  →  current status
  2. get_adherence_report(route_id="22", period="week")        →  historical pattern
  3. Agent synthesizes: "Route 22 is currently 4 min late. This week, OTP is 72%..."

Dispatcher: "When is the next 15 at Brīvības iela?"
Agent workflow:
  1. search_stops(query="Brīvības iela")                      →  stop_id
  2. query_bus_status(action="stop_departures", stop_id="...")  →  upcoming buses
```

## Implementation Plan

### Phase 1: Foundation (Tasks 1-4)
Dependencies, configuration, schemas, and exception types.

### Phase 2: Core Implementation (Tasks 5-8)
GTFS-RT client, deps injection, tool function, agent rewiring.

### Phase 3: Integration & Validation (Tasks 9-12)
Tests, service layer update, env example, final validation.

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.

### Task 1: Add Dependencies
**File:** `pyproject.toml` (modify existing)
**Action:** UPDATE

Add two new dependencies to the `[project.dependencies]` array:
- `"gtfs-realtime-bindings>=1.0.0"` — protobuf bindings for GTFS-RT feeds
- `"httpx>=0.28.1"` — async HTTP client (already in dev deps, promote to production)

After editing, run:
```bash
uv sync
```

Note: `httpx` is already in `[dependency-groups] dev` at line 21. Move it to production `dependencies` AND keep it in dev (it's fine to have it in both — dev group adds test utilities like `TestClient`).

**Per-task validation:**
- `uv sync` completes without errors
- `uv run python -c "from google.transit import gtfs_realtime_pb2; print('OK')"` succeeds
- `uv run python -c "import httpx; print('OK')"` succeeds

---

### Task 2: Add Transit Configuration
**File:** `app/core/config.py` (modify existing)
**Action:** UPDATE

Add transit feed configuration to the `Settings` class after the LLM settings block (after line 48):

```python
# Transit GTFS-RT feeds (Rigas Satiksme public endpoints)
gtfs_rt_vehicle_positions_url: str = "https://saraksti.rigassatiksme.lv/vehicle_positions.pb"
gtfs_rt_trip_updates_url: str = "https://saraksti.rigassatiksme.lv/trip_updates.pb"
gtfs_rt_alerts_url: str = "https://saraksti.rigassatiksme.lv/gtfs_realtime.pb"
gtfs_static_url: str = "https://saraksti.rigassatiksme.lv/gtfs.zip"
gtfs_rt_cache_ttl_seconds: int = 20
gtfs_static_cache_ttl_hours: int = 24
```

All have sensible defaults — no required env vars added. URLs point to Rigas Satiksme's unauthenticated public endpoints.

**Per-task validation:**
- `uv run ruff format app/core/config.py`
- `uv run ruff check app/core/config.py` passes
- `uv run mypy app/core/config.py` passes with 0 errors

---

### Task 3: Add Transit Exception
**File:** `app/core/agents/exceptions.py` (modify existing)
**Action:** UPDATE

Add a new exception class after `AgentExecutionError` (after line 34):

```python
class TransitDataError(AgentError):
    """Transit data fetch or parse failed (feed unavailable, invalid protobuf)."""

    pass
```

Update `setup_agent_exception_handlers` to register the new handler (add after line 81):
```python
app.add_exception_handler(TransitDataError, handler)
```

Also update the `agent_exception_handler` function to map `TransitDataError` → HTTP 503 Service Unavailable (add elif before the final status_code assignment):
```python
if isinstance(exc, AgentExecutionError):
    status_code = status.HTTP_502_BAD_GATEWAY
elif isinstance(exc, TransitDataError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
```

**Per-task validation:**
- `uv run ruff format app/core/agents/exceptions.py`
- `uv run ruff check app/core/agents/exceptions.py` passes
- `uv run mypy app/core/agents/exceptions.py` passes with 0 errors

---

### Task 4: Create Transit Tool Schemas
**File:** `app/core/agents/tools/__init__.py` (create new)
**Action:** CREATE

Create the package init file:
```python
"""Agent tools package — transit and obsidian tool modules."""
```

**File:** `app/core/agents/tools/transit/__init__.py` (create new)
**Action:** CREATE

Create the package init file:
```python
"""Transit tools for real-time bus operations data."""
```

**File:** `app/core/agents/tools/transit/schemas.py` (create new)
**Action:** CREATE

Define all Pydantic models for the tool's input and output. Models needed:

**`Position`**:
- `latitude: float`
- `longitude: float`
- `bearing: float | None = None`
- `speed_kmh: float | None = None`

**`Alert`**:
- `header: str`
- `description: str | None = None`
- `cause: str | None = None`
- `effect: str | None = None`

**`BusStatus`**:
- `vehicle_id: str`
- `route_id: str`
- `route_short_name: str` — human-readable (e.g., "22")
- `trip_id: str | None = None`
- `direction: str | None = None`
- `current_status: str` — "IN_TRANSIT_TO", "STOPPED_AT", "INCOMING_AT"
- `current_stop_name: str | None = None`
- `next_stop_name: str | None = None`
- `position: Position | None = None`
- `delay_seconds: int` — positive = late, negative = early, 0 = on time
- `delay_description: str` — human-readable: "3 min late", "on time", "1 min early"
- `predicted_arrival: str | None = None` — ISO 8601 datetime at next stop
- `timestamp: str` — ISO 8601 when data was measured
- `severity: str` — "normal" | "warning" | "critical" (based on delay thresholds)
- `alerts: list[Alert]`

**`HeadwayInfo`**:
- `average_headway_minutes: float`
- `expected_headway_minutes: float | None = None`
- `headway_deviation_minutes: float | None = None`
- `is_bunched: bool` — True if two vehicles are within 2 minutes of each other

**`RouteOverview`**:
- `route_id: str`
- `route_short_name: str`
- `active_vehicles: int`
- `vehicles: list[BusStatus]`
- `average_delay_seconds: float`
- `on_time_count: int` — vehicles within +/- 300 seconds (5 min)
- `late_count: int`
- `early_count: int`
- `headway: HeadwayInfo | None = None`
- `summary: str` — pre-formatted text for agent to relay

**`StopDeparture`**:
- `route_id: str`
- `route_short_name: str`
- `vehicle_id: str | None = None`
- `trip_id: str | None = None`
- `predicted_arrival: str | None = None` — ISO 8601
- `scheduled_arrival: str | None = None` — ISO 8601
- `delay_seconds: int`
- `delay_description: str`

**`StopDepartures`**:
- `stop_id: str`
- `stop_name: str`
- `departures: list[StopDeparture]`
- `summary: str`

All models use `model_config = ConfigDict(strict=True)`. Include Google-style docstrings.
Follow schema pattern from `app/core/agents/schemas.py`.

**Per-task validation:**
- `uv run ruff format app/core/agents/tools/transit/schemas.py`
- `uv run ruff check app/core/agents/tools/transit/schemas.py` passes
- `uv run mypy app/core/agents/tools/transit/schemas.py` passes with 0 errors

---

### Task 5: Create Transit Dependencies
**File:** `app/core/agents/tools/transit/deps.py` (create new)
**Action:** CREATE

Define the dependency injection types for transit tools:

**`TransitDeps`** (dataclass):
- `http_client: httpx.AsyncClient` — connection-pooled async HTTP client for GTFS-RT fetching
- `settings: Settings` — application settings (for feed URLs, cache TTL)

This is a simple dataclass (not Pydantic model) following Pydantic AI's deps convention:
```python
from dataclasses import dataclass
import httpx
from app.core.config import Settings

@dataclass
class TransitDeps:
    """Dependencies injected into transit tools via RunContext."""
    http_client: httpx.AsyncClient
    settings: Settings
```

Include a factory function:
```python
def create_transit_deps(settings: Settings | None = None) -> TransitDeps:
    """Create TransitDeps with a configured httpx client."""
    if settings is None:
        settings = get_settings()
    client = httpx.AsyncClient(
        timeout=httpx.Timeout(10.0, connect=5.0),
        limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
    )
    return TransitDeps(http_client=client, settings=settings)
```

**Per-task validation:**
- `uv run ruff format app/core/agents/tools/transit/deps.py`
- `uv run ruff check app/core/agents/tools/transit/deps.py` passes
- `uv run mypy app/core/agents/tools/transit/deps.py` passes with 0 errors

---

### Task 6: Create GTFS-RT Client
**File:** `app/core/agents/tools/transit/client.py` (create new)
**Action:** CREATE

Implement the `GTFSRealtimeClient` class that fetches and parses protobuf feeds.

**Class: `GTFSRealtimeClient`**

Constructor:
- `http_client: httpx.AsyncClient`
- `settings: Settings`
- `_vehicle_cache: dict` — in-memory cache with timestamp
- `_trip_update_cache: dict` — in-memory cache with timestamp
- `_alerts_cache: dict` — in-memory cache with timestamp

Methods:

**`async def fetch_vehicle_positions(self) -> list[VehiclePositionData]`**:
- Check cache: if `_vehicle_cache` age < `settings.gtfs_rt_cache_ttl_seconds`, return cached
- Fetch `settings.gtfs_rt_vehicle_positions_url` via `http_client.get()`
- Parse with `gtfs_realtime_pb2.FeedMessage().ParseFromString(response.content)`
- Extract `entity.vehicle` for each entity with `HasField('vehicle')`
- Convert to typed dataclass `VehiclePositionData` (not raw protobuf — typed for mypy)
- Log `"transit.vehicle_positions.fetch_completed"` with `count` and `feed_timestamp`
- On error: log `"transit.vehicle_positions.fetch_failed"`, raise `TransitDataError` with actionable message

**`async def fetch_trip_updates(self) -> list[TripUpdateData]`**:
- Same pattern as vehicle positions but parses `entity.trip_update`
- Extract `stop_time_update` array for delay information
- Log `"transit.trip_updates.fetch_completed"`

**`async def fetch_alerts(self) -> list[AlertData]`**:
- Fetch alerts feed, extract `entity.alert` entities
- Log `"transit.alerts.fetch_completed"`

**Internal dataclasses** (not Pydantic — these are intermediate, not API-facing):

```python
@dataclass
class VehiclePositionData:
    vehicle_id: str
    trip_id: str | None
    route_id: str | None
    latitude: float
    longitude: float
    bearing: float | None
    speed: float | None  # m/s from feed
    current_stop_sequence: int | None
    current_status: str  # "IN_TRANSIT_TO", "STOPPED_AT", "INCOMING_AT"
    stop_id: str | None
    timestamp: int  # POSIX

@dataclass
class StopTimeUpdateData:
    stop_sequence: int
    stop_id: str | None
    arrival_delay: int | None  # seconds
    departure_delay: int | None  # seconds
    arrival_time: int | None  # POSIX timestamp
    departure_time: int | None  # POSIX timestamp

@dataclass
class TripUpdateData:
    trip_id: str
    route_id: str | None
    vehicle_id: str | None
    stop_time_updates: list[StopTimeUpdateData]
    timestamp: int

@dataclass
class AlertData:
    header_text: str
    description_text: str | None
    cause: str | None
    effect: str | None
    route_ids: list[str]
    stop_ids: list[str]
```

**Important implementation notes:**
- Use `try/except` around protobuf parsing — feeds can occasionally be malformed
- Convert protobuf enums to strings (e.g., `VehicleStopStatus.IN_TRANSIT_TO` → `"IN_TRANSIT_TO"`)
- Handle missing fields gracefully — not all vehicles have all fields populated
- Speed from feed is in m/s — do NOT convert here, convert in the tool output layer

**Per-task validation:**
- `uv run ruff format app/core/agents/tools/transit/client.py`
- `uv run ruff check app/core/agents/tools/transit/client.py` passes
- `uv run mypy app/core/agents/tools/transit/client.py` passes with 0 errors
- `uv run pyright app/core/agents/tools/transit/client.py` passes

---

### Task 7: Create Static GTFS Cache
**File:** `app/core/agents/tools/transit/static_cache.py` (create new)
**Action:** CREATE

Implement a lightweight cache for static GTFS data (route names, stop names, trip-to-route mappings).

**Class: `GTFSStaticCache`**

This is NOT a full GTFS parser. It loads only the fields needed for enriching real-time data:

```python
@dataclass
class RouteInfo:
    route_id: str
    route_short_name: str
    route_long_name: str
    route_type: int  # 0=tram, 3=bus, 11=trolleybus

@dataclass
class StopInfo:
    stop_id: str
    stop_name: str
    stop_lat: float | None
    stop_lon: float | None

@dataclass
class TripInfo:
    trip_id: str
    route_id: str
    direction_id: int | None
    trip_headsign: str | None
```

**Methods:**

**`async def load(self, http_client: httpx.AsyncClient, gtfs_url: str) -> None`**:
- Download GTFS ZIP
- Parse `routes.txt` → `self.routes: dict[str, RouteInfo]`
- Parse `stops.txt` → `self.stops: dict[str, StopInfo]`
- Parse `trips.txt` → `self.trips: dict[str, TripInfo]`
- Use Python's `zipfile` and `csv` modules (stdlib, no new deps)
- Store `self._loaded_at: datetime` for staleness check
- Log `"transit.static_cache.load_completed"` with route_count, stop_count, trip_count

**`def is_stale(self, ttl_hours: int) -> bool`**:
- Return True if `_loaded_at` is older than `ttl_hours`

**`def get_route_name(self, route_id: str) -> str`**:
- Return `route_short_name` or `route_id` if not found

**`def get_stop_name(self, stop_id: str) -> str`**:
- Return `stop_name` or `stop_id` if not found

**`def get_trip_route_id(self, trip_id: str) -> str | None`**:
- Lookup trip → route_id mapping

**Module-level singleton:**
```python
_static_cache: GTFSStaticCache | None = None

async def get_static_cache(http_client: httpx.AsyncClient, settings: Settings) -> GTFSStaticCache:
    global _static_cache
    if _static_cache is None or _static_cache.is_stale(settings.gtfs_static_cache_ttl_hours):
        _static_cache = GTFSStaticCache()
        await _static_cache.load(http_client, settings.gtfs_static_url)
    return _static_cache
```

**Important:** Use `io.BytesIO` to process the ZIP in memory — do NOT write to disk.

**Per-task validation:**
- `uv run ruff format app/core/agents/tools/transit/static_cache.py`
- `uv run ruff check app/core/agents/tools/transit/static_cache.py` passes
- `uv run mypy app/core/agents/tools/transit/static_cache.py` passes with 0 errors

---

### Task 8: Implement query_bus_status Tool
**File:** `app/core/agents/tools/transit/query_bus_status.py` (create new)
**Action:** CREATE

This is the main tool function that the agent calls. It orchestrates the client, cache, and schema layers.

**Function signature:**
```python
from pydantic_ai import RunContext
from app.core.agents.tools.transit.deps import TransitDeps

async def query_bus_status(
    ctx: RunContext[TransitDeps],
    action: str,
    route_id: str | None = None,
    vehicle_id: str | None = None,
    stop_id: str | None = None,
) -> str:
```

**IMPORTANT:** The function is NOT decorated with `@agent.tool` here. It is registered in `agent.py` (Task 9). This avoids circular imports.

**The return type is `str`** (JSON-serialized). Pydantic AI tools return strings that the LLM processes.

**Include the full agent-optimized docstring** from the "Tool Interface" section above. This docstring is critical — the LLM reads it to decide when to use this tool.

**Implementation logic:**

1. **Validate action**: Must be one of `"status"`, `"route_overview"`, `"stop_departures"`. If invalid, return actionable error string: `"Invalid action '{action}'. Use 'status', 'route_overview', or 'stop_departures'."`

2. **Validate required params per action**:
   - `status`: requires `vehicle_id` OR `route_id`
   - `route_overview`: requires `route_id`
   - `stop_departures`: requires `stop_id`
   - Return actionable error if missing: `"Action 'status' requires vehicle_id or route_id. Example: query_bus_status(action='status', route_id='22')"`

3. **Fetch data:**
   ```python
   client = GTFSRealtimeClient(ctx.deps.http_client, ctx.deps.settings)
   static = await get_static_cache(ctx.deps.http_client, ctx.deps.settings)
   ```

4. **Action: `status`**:
   - Fetch vehicle positions + trip updates
   - Filter by `vehicle_id` or `route_id`
   - Merge: match vehicles to trip updates by `trip_id`
   - Enrich: add route names, stop names from static cache
   - Calculate `delay_description` from `delay_seconds`:
     - `abs(delay) < 60` → "on time"
     - `delay > 0` → f"{delay // 60} min late"
     - `delay < 0` → f"{abs(delay) // 60} min early"
   - Calculate `severity`:
     - `abs(delay) < 180` → "normal"
     - `abs(delay) < 600` → "warning"
     - else → "critical"
   - Convert speed from m/s to km/h: `speed * 3.6`
   - Build `list[BusStatus]` and serialize to JSON

5. **Action: `route_overview`**:
   - Same data fetch as `status`, filtered by `route_id`
   - Calculate aggregate stats: average delay, on-time count, late count, early count
   - Calculate headway: sort vehicles by `current_stop_sequence`, compute gaps
   - Detect bunching: vehicles within 2 minutes headway
   - Build `summary` string: "Route {name}: {n} active vehicles, avg delay {x}s. {late_count} late, {early_count} early. {bunching_note}"
   - Build `RouteOverview` and serialize to JSON

6. **Action: `stop_departures`**:
   - Fetch trip updates
   - Filter `stop_time_updates` where `stop_id` matches
   - Enrich with route names from static cache
   - Sort by predicted arrival time (ascending)
   - Limit to next 10 departures
   - Build `summary`: "Next departures at {stop_name}: Route {x} in {y} min, Route {z} in {w} min..."
   - Build `StopDepartures` and serialize to JSON

**Error handling:**
- Wrap all feed fetches in try/except
- On `TransitDataError`: return actionable error string (don't raise — tools should return errors as strings so the LLM can reason about them)
- On `httpx.TimeoutException`: return "Transit feed timed out. The Rigas Satiksme data service may be temporarily unavailable. Try again in 30 seconds."

**Structured logging:**
- `"transit.query_bus_status.started"` with `action`, `route_id`, `vehicle_id`, `stop_id`
- `"transit.query_bus_status.completed"` with `action`, `result_count`, `duration_ms`
- `"transit.query_bus_status.failed"` with `exc_info=True`, `error`, `error_type`

**Per-task validation:**
- `uv run ruff format app/core/agents/tools/transit/query_bus_status.py`
- `uv run ruff check app/core/agents/tools/transit/query_bus_status.py` passes
- `uv run mypy app/core/agents/tools/transit/query_bus_status.py` passes with 0 errors
- `uv run pyright app/core/agents/tools/transit/query_bus_status.py` passes

---

### Task 9: Rewire Agent with Deps and Tool
**File:** `app/core/agents/agent.py` (modify existing)
**Action:** UPDATE

This is the most critical modification. The agent must change from `Agent[None, str]` to `Agent[TransitDeps, str]`.

**Changes:**

1. Add imports:
```python
from app.core.agents.tools.transit.deps import TransitDeps
from app.core.agents.tools.transit.query_bus_status import query_bus_status
```

2. Update `create_agent` signature and body:
```python
def create_agent(model: str | Model | None = None) -> Agent[TransitDeps, str]:
    if model is None:
        model = get_agent_model()
    logger.info("agent.create_completed", model=str(model))
    return Agent(
        model,
        deps_type=TransitDeps,
        output_type=str,
        system_prompt=SYSTEM_PROMPT,
        tools=[query_bus_status],
    )
```

3. Update module-level singleton type:
```python
agent: Agent[TransitDeps, str] = create_agent()
```

**Per-task validation:**
- `uv run ruff format app/core/agents/agent.py`
- `uv run ruff check app/core/agents/agent.py` passes
- `uv run mypy app/core/agents/agent.py` passes with 0 errors

---

### Task 10: Update Service to Pass Deps
**File:** `app/core/agents/service.py` (modify existing)
**Action:** UPDATE

The `agent.run()` call at line 59 must now pass `TransitDeps`:

1. Add imports:
```python
from app.core.agents.tools.transit.deps import TransitDeps, create_transit_deps
```

2. Add deps creation in `AgentService.__init__`:
```python
class AgentService:
    def __init__(self) -> None:
        self._deps: TransitDeps = create_transit_deps()
```

3. Update `agent.run()` call (line 59):
```python
result = await agent.run(user_prompt, deps=self._deps)
```

4. Add cleanup method (for graceful shutdown):
```python
async def close(self) -> None:
    """Close the HTTP client."""
    await self._deps.http_client.aclose()
```

**Per-task validation:**
- `uv run ruff format app/core/agents/service.py`
- `uv run ruff check app/core/agents/service.py` passes
- `uv run mypy app/core/agents/service.py` passes with 0 errors

---

### Task 11: Update Existing Tests
**File:** `app/core/agents/tests/test_service.py` (modify existing)
**Action:** UPDATE

Existing tests must be updated because `AgentService.__init__` now creates `TransitDeps`.

1. Add mock for `create_transit_deps`:
```python
from unittest.mock import AsyncMock, MagicMock, patch

@pytest.fixture
def mock_transit_deps():
    """Create mock TransitDeps for testing."""
    deps = MagicMock()
    deps.http_client = AsyncMock()
    deps.settings = MagicMock()
    return deps
```

2. Patch `create_transit_deps` in each test:
```python
with patch("app.core.agents.service.create_transit_deps", return_value=mock_transit_deps):
    service = AgentService()
```

3. Update the `agent.override()` calls — `TestModel` still works, but now the agent expects `TransitDeps`:
```python
with agent.override(model=TestModel()):
    with patch("app.core.agents.service.create_transit_deps", return_value=mock_deps):
        with patch("app.core.agents.service.logger"):
            response = await service.chat(request)
```

Ensure all 3 existing tests still pass with the new deps pattern.

**Per-task validation:**
- `uv run ruff format app/core/agents/tests/test_service.py`
- `uv run ruff check app/core/agents/tests/test_service.py` passes
- `uv run pytest app/core/agents/tests/test_service.py -v` — all 3 tests pass

---

### Task 12: Create Tool Unit Tests
**File:** `app/core/agents/tools/transit/tests/__init__.py` (create new)
**Action:** CREATE

```python
"""Tests for transit tools."""
```

**File:** `app/core/agents/tools/transit/tests/test_query_bus_status.py` (create new)
**Action:** CREATE

Test the tool function directly (not through the agent). Mock the GTFS-RT client.

**Test 1: Status action with route_id**
```python
async def test_status_by_route_returns_vehicles():
    # Mock GTFSRealtimeClient to return 2 test vehicles on route "22"
    # Mock static cache with route name "22" → "Centrs — Jugla"
    # Call query_bus_status with action="status", route_id="22"
    # Assert JSON output contains 2 vehicles with correct route_short_name
    # Assert delay_description is human-readable
    # Assert severity is calculated correctly
```

**Test 2: Status action with vehicle_id**
```python
async def test_status_by_vehicle_returns_single():
    # Mock client with 1 vehicle matching vehicle_id="4521"
    # Assert JSON output contains exactly 1 vehicle
```

**Test 3: Route overview with headway**
```python
async def test_route_overview_calculates_stats():
    # Mock 3 vehicles: 1 on-time, 1 late (400s), 1 early (-200s)
    # Call action="route_overview", route_id="22"
    # Assert average_delay_seconds is correct
    # Assert on_time_count, late_count, early_count are correct
    # Assert summary string is non-empty
```

**Test 4: Stop departures**
```python
async def test_stop_departures_returns_sorted():
    # Mock trip updates with 3 stop_time_updates matching stop_id
    # Assert departures are sorted by predicted arrival (ascending)
    # Assert limit of 10 is applied
```

**Test 5: Invalid action**
```python
async def test_invalid_action_returns_error_message():
    # Call with action="invalid"
    # Assert result contains "Invalid action" error message
    # Assert result suggests valid actions
```

**Test 6: Missing required params**
```python
async def test_status_without_ids_returns_error():
    # Call action="status" without route_id or vehicle_id
    # Assert result contains actionable error with example usage
```

**Test 7: Feed timeout graceful handling**
```python
async def test_feed_timeout_returns_helpful_error():
    # Mock http_client.get to raise httpx.TimeoutException
    # Assert result contains "Transit feed timed out" message
    # Assert no exception is raised (tool returns error as string)
```

Use `RunContext` mock pattern:
```python
from unittest.mock import AsyncMock, MagicMock
from pydantic_ai import RunContext

def make_ctx(deps):
    ctx = MagicMock(spec=RunContext)
    ctx.deps = deps
    return ctx
```

**Per-task validation:**
- `uv run ruff format app/core/agents/tools/transit/tests/test_query_bus_status.py`
- `uv run ruff check app/core/agents/tools/transit/tests/test_query_bus_status.py` passes
- `uv run pytest app/core/agents/tools/transit/tests/ -v` — all 7 tests pass

---

### Task 13: Create Client Unit Tests
**File:** `app/core/agents/tools/transit/tests/test_client.py` (create new)
**Action:** CREATE

Test the GTFSRealtimeClient in isolation.

**Test 1: Parse vehicle positions from real-like protobuf**
```python
async def test_fetch_vehicle_positions_parses_protobuf():
    # Create a valid FeedMessage protobuf with 2 vehicle entities
    # Mock httpx response with serialized protobuf bytes
    # Assert 2 VehiclePositionData returned with correct fields
```

**Test 2: Cache respects TTL**
```python
async def test_vehicle_cache_returns_cached_within_ttl():
    # First call: fetch from mock
    # Second call within TTL: should NOT call http_client again
    # Assert http_client.get called only once
```

**Test 3: Cache refreshes after TTL**
```python
async def test_vehicle_cache_refreshes_after_ttl():
    # First call: fetch
    # Advance time past TTL
    # Second call: should fetch again
```

**Test 4: Malformed protobuf raises TransitDataError**
```python
async def test_malformed_protobuf_raises_transit_data_error():
    # Mock response with random bytes (not valid protobuf)
    # Assert TransitDataError is raised with actionable message
```

**Test 5: HTTP error raises TransitDataError**
```python
async def test_http_error_raises_transit_data_error():
    # Mock httpx to raise httpx.HTTPStatusError (e.g., 500)
    # Assert TransitDataError is raised
```

**Per-task validation:**
- `uv run ruff format app/core/agents/tools/transit/tests/test_client.py`
- `uv run ruff check app/core/agents/tools/transit/tests/test_client.py` passes
- `uv run pytest app/core/agents/tools/transit/tests/ -v` — all tests pass

---

### Task 14: Update .env.example
**File:** `.env.example` (modify existing)
**Action:** UPDATE

Add transit configuration section after the Obsidian section (after line 23):

```bash
# Transit GTFS-RT feeds (Rigas Satiksme — no auth required)
# GTFS_RT_VEHICLE_POSITIONS_URL=https://saraksti.rigassatiksme.lv/vehicle_positions.pb
# GTFS_RT_TRIP_UPDATES_URL=https://saraksti.rigassatiksme.lv/trip_updates.pb
# GTFS_RT_ALERTS_URL=https://saraksti.rigassatiksme.lv/gtfs_realtime.pb
# GTFS_STATIC_URL=https://saraksti.rigassatiksme.lv/gtfs.zip
# GTFS_RT_CACHE_TTL_SECONDS=20
# GTFS_STATIC_CACHE_TTL_HOURS=24
```

All commented out since defaults are baked into `Settings`.

**Per-task validation:**
- File is valid bash syntax (comments only)

---

## Logging Events

| Event | When Emitted | Context Fields |
|-------|-------------|----------------|
| `transit.query_bus_status.started` | Tool invoked | `action`, `route_id`, `vehicle_id`, `stop_id` |
| `transit.query_bus_status.completed` | Tool returned result | `action`, `result_count`, `duration_ms` |
| `transit.query_bus_status.failed` | Tool caught error | `error`, `error_type`, `exc_info=True` |
| `transit.vehicle_positions.fetch_completed` | Protobuf parsed | `count`, `feed_timestamp` |
| `transit.vehicle_positions.fetch_failed` | Feed fetch error | `error`, `error_type`, `exc_info=True` |
| `transit.trip_updates.fetch_completed` | Trip updates parsed | `count`, `feed_timestamp` |
| `transit.trip_updates.fetch_failed` | Feed fetch error | `error`, `error_type`, `exc_info=True` |
| `transit.alerts.fetch_completed` | Alerts parsed | `count` |
| `transit.static_cache.load_completed` | Static GTFS loaded | `route_count`, `stop_count`, `trip_count` |

## Testing Strategy

### Unit Tests
**Location:** `app/core/agents/tools/transit/tests/`
- `test_query_bus_status.py` — 7 tests covering all 3 actions, validation, error handling
- `test_client.py` — 5 tests covering protobuf parsing, caching, error cases

### Integration Tests
Not needed for MVP — the feeds are external and unauthenticated. Unit tests with mocked HTTP responses provide sufficient coverage. Integration tests against live feeds can be added later with `@pytest.mark.integration`.

### Edge Cases
- Empty feed (0 vehicles) — should return empty list, not error
- Vehicle with no trip_id — should still appear in results with `trip_id: null`
- Route with no active vehicles — `route_overview` should return `active_vehicles: 0`
- Stop with no upcoming departures — should return empty departures list
- Feed returns HTTP 500 — tool returns error string, not exception

## Acceptance Criteria

This feature is complete when:
- [ ] `query_bus_status` tool registered with Pydantic AI agent
- [ ] Agent type changed from `Agent[None, str]` to `Agent[TransitDeps, str]`
- [ ] Three actions work: `status`, `route_overview`, `stop_departures`
- [ ] Live GTFS-RT feeds from Rigas Satiksme are fetched and parsed
- [ ] Static GTFS cache loads route/stop/trip names
- [ ] Results include `delay_description`, `severity`, `summary` for agent consumption
- [ ] All type checkers pass (mypy + pyright)
- [ ] All tests pass (12+ new tests + 3 existing updated)
- [ ] Structured logging follows `domain.component.action_state` pattern
- [ ] No type suppressions added
- [ ] Agent-optimized docstring guides LLM tool selection

## Completion Checklist

Before marking this plan as fully executed:
- [ ] All 14 tasks completed in order
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
uv run pytest app/core/agents/tools/transit/tests/ -v
```

**Level 4: Full Test Suite (unit)**
```bash
uv run pytest -v -m "not integration"
```

**Level 5: Server Validation (if Docker running)**
```bash
curl -s http://localhost:8123/health
curl -s -X POST http://localhost:8123/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"What is the status of route 22?"}]}'
```

**Success definition:** Levels 1-4 exit code 0, all tests pass, zero errors or warnings.

## Dependencies

- **Shared utilities used:** `get_logger()` from `app.core.logging`, `get_settings()` from `app.core.config`
- **Core modules used:** `app.core.agents.agent`, `app.core.agents.exceptions`
- **New dependencies:**
  ```bash
  uv add gtfs-realtime-bindings
  # httpx already in dev deps — promote to production
  ```
- **New env vars:** All optional with defaults (see Task 2 and Task 14)

## New Files Created

| File | Purpose |
|------|---------|
| `app/core/agents/tools/__init__.py` | Package init |
| `app/core/agents/tools/transit/__init__.py` | Package init |
| `app/core/agents/tools/transit/schemas.py` | Pydantic response models (BusStatus, RouteOverview, etc.) |
| `app/core/agents/tools/transit/deps.py` | TransitDeps dataclass and factory |
| `app/core/agents/tools/transit/client.py` | GTFSRealtimeClient (protobuf fetch + cache) |
| `app/core/agents/tools/transit/static_cache.py` | Static GTFS name resolver |
| `app/core/agents/tools/transit/query_bus_status.py` | Main tool function |
| `app/core/agents/tools/transit/tests/__init__.py` | Test package init |
| `app/core/agents/tools/transit/tests/test_query_bus_status.py` | Tool tests (7) |
| `app/core/agents/tools/transit/tests/test_client.py` | Client tests (5) |

## Files Modified

| File | Change |
|------|--------|
| `pyproject.toml` | Add `gtfs-realtime-bindings`, promote `httpx` |
| `app/core/config.py` | Add 7 transit settings |
| `app/core/agents/exceptions.py` | Add `TransitDataError`, register handler |
| `app/core/agents/agent.py` | Change to `Agent[TransitDeps, str]`, register tool |
| `app/core/agents/service.py` | Pass `TransitDeps` to `agent.run()` |
| `app/core/agents/tests/test_service.py` | Update for deps pattern |
| `.env.example` | Add transit config comments |

## Notes

### Future Considerations
- **Delay prediction ML**: Schema includes nullable `predicted_delay_seconds` — populate when ML model is trained on archived GTFS-RT data
- **Feed archival**: Consider storing raw protobuf responses for training data (out of MVP scope)
- **GTFS-RT feed monitoring**: A future background task could detect feed staleness and alert dispatchers
- **Other transit tools**: `get_route_schedule`, `search_stops`, `get_adherence_report`, `check_driver_availability` will reuse `GTFSRealtimeClient` and `GTFSStaticCache`

### Performance
- Protobuf parsing: <10ms for ~1000 vehicle entities
- Cache hit: <1ms (in-memory dict lookup)
- Static GTFS load: ~2-5 seconds on first load (downloads ~5MB ZIP, parses 3 CSV files)
- Total tool latency (cache hit): <50ms
- Total tool latency (cache miss): <2 seconds

### Security
- All GTFS-RT feeds are public, unauthenticated, read-only
- No user input reaches database queries (no SQL injection risk)
- No PII in transit data (vehicle IDs are fleet numbers, not driver IDs)
- Tool is read-only — cannot modify any transit data

## Pre-Implementation Checklist

The executing agent MUST verify before writing any code:
- [ ] Read all files listed in "Relevant Files" section
- [ ] Reviewed research documentation
- [ ] Understood the solution approach and why alternatives were rejected
- [ ] Clear on task execution order
- [ ] Validation commands are executable in this environment
- [ ] `uv sync` works (Python environment is set up)
