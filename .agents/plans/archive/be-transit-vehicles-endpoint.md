# Plan: Transit Vehicle Positions REST Endpoint

## Feature Metadata
**Feature Type**: New Capability
**Estimated Complexity**: Medium
**Primary Systems Affected**: `app/core/agents/tools/transit/`, `app/main.py`, `app/core/middleware.py`

## Feature Description

Add a public REST endpoint `GET /api/v1/transit/vehicles` that returns real-time GTFS-RT vehicle positions as JSON. This endpoint reuses the existing `GTFSRealtimeClient` (20-second cache) and `GTFSStaticCache` (24-hour cache) to fetch, parse, and enrich vehicle positions from Rigas Satiksme's public protobuf feeds.

The endpoint is designed for the CMS frontend to poll every 15-30 seconds, replacing the static mock bus positions currently hardcoded in `cms/apps/web/src/lib/mock-bus-positions.ts`. It returns an array of vehicle position objects with route names, delay information, current/next stop names, and geographic coordinates.

This is a read-only, unauthenticated endpoint (the GTFS-RT data is public). It sits alongside the existing agent API (`/v1/chat/completions`) and health checks (`/health`). No database is required. The endpoint follows the existing transit module patterns: structured logging, TransitDataError propagation, and Pydantic response models.

## User Story

As a transit dispatcher viewing the routes page in the CMS
I want to see live bus positions on the Leaflet map
So that I can monitor fleet operations in real time instead of looking at static mock data

## Solution Approach

Create a thin REST layer on top of the existing GTFS-RT infrastructure. The `GTFSRealtimeClient.fetch_vehicle_positions()` method already returns parsed `VehiclePositionData` objects with 20-second caching. The `GTFSStaticCache` resolves route IDs to human-readable names and stop IDs to stop names. We combine these to build enriched vehicle position responses.

**Approach Decision:**
We chose to build a new router module (`app/transit/routes.py`) as a feature slice rather than adding endpoints to the existing agent router because:
- The agent router serves OpenAI-compatible chat endpoints with different concerns (auth, rate limiting, streaming)
- Transit REST endpoints serve structured data to the frontend, a fundamentally different consumer
- Separation follows VTV's vertical slice architecture principle

**Alternatives Considered:**
- **Extend agent routes** (`/v1/chat/completions` + new transit endpoints): Rejected because agent routes have a `/v1` prefix and OpenAI-compatible schema. Transit REST endpoints belong to a different API surface.
- **Frontend-direct GTFS-RT fetch**: Rejected because CORS issues with Rigas Satiksme feeds, protobuf parsing in browser adds ~50KB, and no server-side caching benefit.

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, logging patterns, type checking requirements
- `app/core/config.py` (lines 1-75) — Settings class with GTFS feed URLs and cache TTL values
- `app/core/agents/exceptions.py` (lines 1-42) — TransitDataError exception (reused for feed errors)

### Pattern Files (Examples to Follow)
- `app/core/health.py` (lines 1-106) — Router pattern: APIRouter, tags, endpoint structure, error handling
- `app/core/agents/routes.py` (lines 1-60) — Router with prefix, dependency injection, typed responses
- `app/core/agents/tools/transit/client.py` (lines 127-246) — GTFSRealtimeClient usage, VehiclePositionData dataclass
- `app/core/agents/tools/transit/static_cache.py` (lines 117-429) — GTFSStaticCache singleton, get_static_cache() factory
- `app/core/agents/tools/transit/query_bus_status.py` (lines 347-433) — `_build_bus_statuses()` shows how to enrich vehicle data with delays, stop names, and route names
- `app/core/agents/tools/transit/deps.py` (lines 1-43) — TransitDeps creation with httpx client configuration
- `app/core/agents/tools/transit/schemas.py` (lines 11-84) — Existing Pydantic models: Position, BusStatus (agent schema, NOT for REST)

### Test Patterns
- `app/core/agents/tools/transit/tests/test_query_bus_status.py` (lines 1-80) — Mock patterns for transit tools: AsyncMock for client methods, MagicMock for RunContext, patching get_static_cache

### Files to Modify
- `app/main.py` — Register transit_router
- `app/core/middleware.py` — Ensure CORS allows `http://localhost:3000` (already configured)

### Files to Create
- `app/transit/__init__.py` — Empty package init
- `app/transit/schemas.py` — Pydantic response models for the REST endpoint
- `app/transit/service.py` — Service layer bridging GTFSRealtimeClient + GTFSStaticCache
- `app/transit/routes.py` — FastAPI router with GET /api/v1/transit/vehicles
- `app/transit/tests/__init__.py` — Empty test package init
- `app/transit/tests/test_service.py` — Unit tests for service
- `app/transit/tests/test_routes.py` — Unit tests for route handler

## Implementation Plan

### Phase 1: Foundation
Define Pydantic response schemas for the REST endpoint. These are separate from the agent schemas in `app/core/agents/tools/transit/schemas.py` because the agent schemas are optimized for LLM consumption (text summaries, severity labels) while the REST schemas are optimized for frontend rendering (latitude/longitude, CSS-friendly status codes, route colors).

### Phase 2: Core Implementation
Create the service layer that orchestrates `GTFSRealtimeClient` + `GTFSStaticCache` to produce enriched vehicle positions. Then create the FastAPI router exposing the data.

### Phase 3: Integration & Validation
Register the router in `app/main.py`, write unit tests, and run the full validation pyramid.

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.

---

### Task 1: Create Transit Feature Package
**File:** `app/transit/__init__.py` (create new)
**Action:** CREATE

Create an empty `__init__.py` to establish the `app.transit` package.

```python
"""Transit REST API for real-time vehicle positions."""
```

Also create test package init:
**File:** `app/transit/tests/__init__.py` (create new)
**Action:** CREATE

Empty file.

**Per-task validation:**
- `uv run ruff format app/transit/__init__.py app/transit/tests/__init__.py`
- `uv run ruff check --fix app/transit/__init__.py app/transit/tests/__init__.py` passes

---

### Task 2: Create REST Response Schemas
**File:** `app/transit/schemas.py` (create new)
**Action:** CREATE

Create Pydantic response models optimized for the CMS frontend map component. These are intentionally separate from the agent schemas — the frontend needs flat, simple objects with fields matching the `BusPosition` TypeScript interface in `cms/apps/web/src/types/route.ts`.

Define two models:

**`VehiclePosition`** — a single vehicle on the map:
- `vehicle_id: str` — fleet vehicle identifier (e.g., "4521")
- `route_id: str` — GTFS route identifier
- `route_short_name: str` — human-readable route number (e.g., "22")
- `latitude: float` — WGS84 latitude
- `longitude: float` — WGS84 longitude
- `bearing: float | None = None` — compass heading in degrees (0-360)
- `speed_kmh: float | None = None` — speed in km/h
- `delay_seconds: int = 0` — schedule deviation (positive=late, negative=early)
- `current_status: str` — one of "IN_TRANSIT_TO", "STOPPED_AT", "INCOMING_AT"
- `next_stop_name: str | None = None` — name of next stop (resolved from GTFS static)
- `current_stop_name: str | None = None` — name of current/nearest stop
- `timestamp: str` — ISO 8601 when position was measured

All fields use `ConfigDict(strict=True)`. Include Google-style docstring.

**`VehiclePositionsResponse`** — the top-level response wrapper:
- `count: int` — number of vehicles in response
- `vehicles: list[VehiclePosition]` — vehicle list
- `fetched_at: str` — ISO 8601 server time when data was assembled

Include `model_config = ConfigDict(strict=True)`.

**Per-task validation:**
- `uv run ruff format app/transit/schemas.py`
- `uv run ruff check --fix app/transit/schemas.py` passes
- `uv run mypy app/transit/schemas.py` passes with 0 errors
- `uv run pyright app/transit/schemas.py` passes

---

### Task 3: Create Transit Service
**File:** `app/transit/service.py` (create new)
**Action:** CREATE

Create a service class that fetches and enriches vehicle positions. This bridges the existing `GTFSRealtimeClient` and `GTFSStaticCache` into the REST response schema.

**Class: `TransitService`**

Constructor:
```python
def __init__(self, http_client: httpx.AsyncClient, settings: Settings) -> None:
```
Stores http_client and settings as private fields.

Method: `async def get_vehicle_positions(self, route_id: str | None = None) -> VehiclePositionsResponse:`

Implementation steps:
1. Create `GTFSRealtimeClient(self._http_client, self._settings)`
2. Call `await client.fetch_vehicle_positions()` to get `list[VehiclePositionData]`
3. Call `await client.fetch_trip_updates()` to get `list[TripUpdateData]` for delay data
4. Call `await get_static_cache(self._http_client, self._settings)` to get static data
5. Build trip update lookup: `dict[str, TripUpdateData]` keyed by trip_id
6. For each `VehiclePositionData`:
   - Resolve route_id: use `v.route_id` or look up via `static.get_trip_route_id(v.trip_id)`
   - Resolve route_short_name: `static.get_route_name(route_id)`
   - Get delay from trip updates (same logic as `query_bus_status._build_bus_statuses` lines 347-433)
   - Resolve next_stop_name and current_stop_name from static cache
   - Convert speed from m/s to km/h: `round(v.speed * 3.6, 1) if v.speed else None`
   - Convert timestamp: `datetime.fromtimestamp(v.timestamp, tz=UTC).isoformat()`
   - Build `VehiclePosition` object
7. If `route_id` param is provided, filter vehicles to only that route
8. Return `VehiclePositionsResponse` with `fetched_at=datetime.now(tz=UTC).isoformat()`

**Structured logging:**
- `logger.info("transit.vehicles.fetch_started", route_filter=route_id)`
- `logger.info("transit.vehicles.fetch_completed", count=len(vehicles), duration_ms=...)`
- `logger.error("transit.vehicles.fetch_failed", exc_info=True, error=str(e), error_type=type(e).__name__)`

**Factory function:**
```python
def get_transit_service(settings: Settings | None = None) -> TransitService:
    """Create a TransitService with configured HTTP client."""
    if settings is None:
        settings = get_settings()
    client = httpx.AsyncClient(
        timeout=httpx.Timeout(10.0, connect=5.0),
        limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
    )
    return TransitService(http_client=client, settings=settings)
```

Follow the pattern from `app/core/agents/tools/transit/deps.py` for httpx client configuration.

**Per-task validation:**
- `uv run ruff format app/transit/service.py`
- `uv run ruff check --fix app/transit/service.py` passes
- `uv run mypy app/transit/service.py` passes
- `uv run pyright app/transit/service.py` passes

---

### Task 4: Create Transit Routes
**File:** `app/transit/routes.py` (create new)
**Action:** CREATE

Create a FastAPI router with the vehicle positions endpoint.

**Router configuration:**
```python
router = APIRouter(prefix="/api/v1/transit", tags=["transit"])
```

**Endpoint: `GET /api/v1/transit/vehicles`**

```python
@router.get("/vehicles", response_model=VehiclePositionsResponse)
async def get_vehicles(
    route_id: str | None = None,
) -> VehiclePositionsResponse:
```

- Query parameter `route_id` (optional) — filter to a specific GTFS route
- Creates `TransitService` via `get_transit_service()`
- Calls `service.get_vehicle_positions(route_id=route_id)`
- Returns the response directly
- On `TransitDataError`: the global exception handler in `app/core/agents/exceptions.py` already maps it to HTTP 503 — so do NOT catch it here. Let it propagate.
- Add structured logging: `logger.info("transit.api.vehicles_requested", route_id=route_id)`

**IMPORTANT:** The service creates its own httpx client. In a future optimization, we could use FastAPI dependency injection with a shared client. For now, keep it simple — the client is lightweight and the cache handles repeated calls.

Follow the pattern from `app/core/health.py` (simple router, minimal logic, delegate to service).

**Per-task validation:**
- `uv run ruff format app/transit/routes.py`
- `uv run ruff check --fix app/transit/routes.py` passes
- `uv run mypy app/transit/routes.py` passes
- `uv run pyright app/transit/routes.py` passes

---

### Task 5: Register Router in main.py
**File:** `app/main.py` (modify)
**Action:** UPDATE

Add import and router registration:

```python
from app.transit.routes import router as transit_router
```

Add after the existing `app.include_router(agent_router)` line:

```python
app.include_router(transit_router)
```

**Per-task validation:**
- `uv run ruff format app/main.py`
- `uv run ruff check --fix app/main.py` passes
- `uv run mypy app/main.py` passes

---

### Task 6: Create Service Unit Tests
**File:** `app/transit/tests/test_service.py` (create new)
**Action:** CREATE

Test the `TransitService.get_vehicle_positions()` method with mocked GTFS clients.

**Test fixtures:**
- `_make_vehicle_position(...)` helper returning `VehiclePositionData` — must have `-> VehiclePositionData` return type annotation
- `_make_trip_update(...)` helper returning `TripUpdateData` — must have `-> TripUpdateData` return type annotation
- `_make_static_cache()` helper returning `MagicMock` with `get_route_name`, `get_stop_name`, `get_trip_route_id` — must have `-> MagicMock` return type

**Mock strategy:**
- Patch `app.transit.service.GTFSRealtimeClient` — mock `fetch_vehicle_positions` and `fetch_trip_updates` as `AsyncMock`
- Patch `app.transit.service.get_static_cache` — return a mock `GTFSStaticCache`
- Create `TransitService` with a `MagicMock` httpx client and `MagicMock` settings

**Test 1: `test_get_vehicle_positions_success`**
- Mock 3 vehicles with different routes, delays, statuses
- Assert response has `count=3`
- Assert each vehicle has resolved route_short_name, delay_seconds from trip updates
- Assert `fetched_at` is a valid ISO 8601 string

**Test 2: `test_get_vehicle_positions_with_route_filter`**
- Mock 3 vehicles, 2 on route "22", 1 on route "15"
- Call with `route_id="22"`
- Assert response has `count=2`

**Test 3: `test_get_vehicle_positions_empty`**
- Mock empty vehicle list
- Assert response has `count=0`, `vehicles=[]`

**Test 4: `test_get_vehicle_positions_transit_error`**
- Mock `fetch_vehicle_positions` to raise `TransitDataError`
- Assert `TransitDataError` propagates (not caught by service)

**Test 5: `test_get_vehicle_positions_speed_conversion`**
- Mock a vehicle with `speed=10.0` (m/s)
- Assert response vehicle has `speed_kmh=36.0`

**Test 6: `test_get_vehicle_positions_null_speed_and_bearing`**
- Mock a vehicle with `speed=None`, `bearing=None`
- Assert response vehicle has `speed_kmh=None`, `bearing=None`

All tests use `@pytest.mark.asyncio`. Import `TransitDataError` from `app.core.agents.exceptions`. Import `VehiclePositionData`, `TripUpdateData`, `StopTimeUpdateData` from `app.core.agents.tools.transit.client`.

**Per-task validation:**
- `uv run ruff format app/transit/tests/test_service.py`
- `uv run ruff check --fix app/transit/tests/test_service.py` passes
- `uv run pytest app/transit/tests/test_service.py -v` — all 6 tests pass

---

### Task 7: Create Route Handler Unit Tests
**File:** `app/transit/tests/test_routes.py` (create new)
**Action:** CREATE

Test the FastAPI route handler using `httpx.AsyncClient` with `ASGITransport`.

**Setup:**
```python
from httpx import ASGITransport, AsyncClient
from app.main import app
```

**Test 1: `test_get_vehicles_success`**
- Patch `app.transit.service.get_transit_service` to return a mock service
- Mock `get_vehicle_positions` to return a `VehiclePositionsResponse` with 2 vehicles
- `async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:`
- `response = await client.get("/api/v1/transit/vehicles")`
- Assert `response.status_code == 200`
- Assert `response.json()["count"] == 2`

**Test 2: `test_get_vehicles_with_route_filter`**
- Same as Test 1 but with `?route_id=22`
- Assert the mock service was called with `route_id="22"`

**Test 3: `test_get_vehicles_transit_error`**
- Mock service to raise `TransitDataError("Feed unavailable")`
- Assert `response.status_code == 503`
- Assert `"TransitDataError"` in response JSON

All tests use `@pytest.mark.asyncio`.

**Per-task validation:**
- `uv run ruff format app/transit/tests/test_routes.py`
- `uv run ruff check --fix app/transit/tests/test_routes.py` passes
- `uv run pytest app/transit/tests/test_routes.py -v` — all 3 tests pass

---

## Migration

Not applicable — no database tables. This feature is purely in-memory.

## Logging Events

- `transit.api.vehicles_requested` — when the endpoint is hit (includes route_id filter if present)
- `transit.vehicles.fetch_started` — when the service begins fetching GTFS-RT data
- `transit.vehicles.fetch_completed` — when the service finishes (includes count, duration_ms)
- `transit.vehicles.fetch_failed` — on error (includes error, error_type, duration_ms)

## Testing Strategy

### Unit Tests
**Location:** `app/transit/tests/test_service.py`
- TransitService.get_vehicle_positions — happy path, route filtering, empty results, error propagation, speed conversion, null fields

**Location:** `app/transit/tests/test_routes.py`
- GET /api/v1/transit/vehicles — success, route filter, error handling (503)

### Edge Cases
- All vehicles filtered out by route_id — returns `count=0`, `vehicles=[]`
- Vehicle with no trip_id — route_id resolved from vehicle data directly, delay defaults to 0
- Vehicle with no stop_id — current_stop_name and next_stop_name are None
- Speed is None — speed_kmh is None (no division by zero)
- Timestamp is 0 — produces epoch time ISO string (acceptable)

## Acceptance Criteria

This feature is complete when:
- [ ] `GET /api/v1/transit/vehicles` returns JSON with real-time vehicle positions
- [ ] Optional `?route_id=X` query parameter filters to a single route
- [ ] Response includes enriched fields: route_short_name, next_stop_name, delay_seconds
- [ ] Feed errors return HTTP 503 with TransitDataError details
- [ ] CORS allows requests from `http://localhost:3000` (already configured)
- [ ] All type checkers pass (mypy + pyright)
- [ ] All tests pass (9 new tests: 6 service + 3 route)
- [ ] Structured logging follows `transit.{component}.{action}_{state}` pattern
- [ ] No type suppressions added
- [ ] Router registered in `app/main.py`
- [ ] No regressions in existing tests (189+ tests)

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
uv run pytest app/transit/tests/ -v
```

**Level 4: Full Test Suite (unit)**
```bash
uv run pytest -v -m "not integration"
```

**Level 5: Server Validation (if Docker running)**
```bash
curl -s http://localhost:8123/api/v1/transit/vehicles | python -m json.tool
```

**Success definition:** Levels 1-4 exit code 0, all tests pass, zero errors or warnings. Level 5 optional.

## Dependencies

- **Shared utilities used:** None from `app/shared/` (this feature doesn't need pagination or database)
- **Core modules used:**
  - `app.core.config.Settings`, `app.core.config.get_settings` — feed URLs, cache TTL
  - `app.core.agents.exceptions.TransitDataError` — error propagation
  - `app.core.agents.tools.transit.client.GTFSRealtimeClient` — GTFS-RT fetching
  - `app.core.agents.tools.transit.client.VehiclePositionData` — parsed vehicle data
  - `app.core.agents.tools.transit.client.TripUpdateData` — parsed trip update data
  - `app.core.agents.tools.transit.client.StopTimeUpdateData` — parsed stop time data
  - `app.core.agents.tools.transit.static_cache.get_static_cache` — static GTFS data
  - `app.core.logging.get_logger` — structured logging
- **New dependencies:** None (all packages already installed: httpx, pydantic, fastapi)
- **New env vars:** None (GTFS feed URLs already in Settings)

## Known Pitfalls

The executing agent MUST follow these rules to avoid common errors:

1. **No `assert` in production code** — Ruff S101 forbids assert outside test files. Use conditional checks instead.
2. **No `object` type hints** — Import and use actual types directly. Never write `def f(data: object)` then isinstance-check.
3. **Untyped third-party libraries** — The protobuf library is already handled with pyright directives in `client.py`. The service file does NOT import protobuf directly, so no directives needed.
4. **Mock exceptions must match catch blocks** — If tests need to raise `TransitDataError`, import it from `app.core.agents.exceptions`, not create a generic `Exception`.
5. **No unused imports or variables** — Ruff F401 catches unused imports, Ruff F841 catches unused local variables. Don't write speculative code — only import/assign what you actually use.
6. **No unnecessary noqa/type-ignore** — Ruff RUF100 flags unused suppression comments.
7. **Test helper functions need return type annotations** — Always add `-> ReturnType` to test helpers (e.g., `def _make_vehicle() -> VehiclePositionData:`). mypy's `disallow_untyped_call` is globally true.
8. **No EN DASH in strings** — Ruff RUF001 forbids `\u2013`. Use `-` (HYPHEN-MINUS, U+002D) in all strings.
9. **Do NOT catch TransitDataError in the route handler** — Let it propagate to the global exception handler in `app/core/agents/exceptions.py` which already maps it to HTTP 503.
10. **Import `VehiclePositionData` and `TripUpdateData` from `client.py`** — These are dataclasses, not Pydantic models. They are the internal representation. The REST schema (`app/transit/schemas.py`) is the external representation.

## Notes

- **Frontend integration (follow-up):** After this endpoint is live, the CMS frontend should replace `MOCK_BUS_POSITIONS` with a polling `fetch()` call to `/api/v1/transit/vehicles`. This is a separate frontend task that requires the FastAPI server to be running.
- **Performance:** The 20-second GTFS-RT cache in `GTFSRealtimeClient` means all frontend polling within 20 seconds hits cached data. No concern about hammering the Rigas Satiksme feeds.
- **CORS:** Already configured in `app/core/middleware.py` to allow `http://localhost:3000`. No changes needed.
- **Authentication:** This endpoint is intentionally unauthenticated. The GTFS-RT data is public. If auth is needed later, add it as a separate concern.
- **Rate limiting:** Not implemented in this plan. The 20-second cache provides natural rate limiting. If needed, add per-IP rate limiting as a follow-up.

## Pre-Implementation Checklist

The executing agent MUST verify before writing any code:
- [ ] Read all files listed in "Relevant Files" section
- [ ] Understood how `GTFSRealtimeClient.fetch_vehicle_positions()` returns `list[VehiclePositionData]`
- [ ] Understood how `get_static_cache()` provides route/stop name resolution
- [ ] Understood how `_build_bus_statuses()` in `query_bus_status.py` enriches vehicles with delay data
- [ ] Understood the TransitDataError global exception handler flow
- [ ] Clear on task execution order (schemas -> service -> routes -> main.py -> tests)
- [ ] Validation commands are executable in this environment
