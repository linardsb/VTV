# Plan: LV-3.3 OpenTripPlanner Journey Planning

## Context

Multi-modal journey planning ("walk -> bus -> train -> walk") is the killer feature for a unified transit platform. OTP is the industry standard — self-hosted, open-source, handles GTFS natively. This feature deploys OTP 2.x as a Docker sidecar, proxies its `/plan` API, enriches results with VTV's real-time GTFS-RT delay data from Redis, and exposes as `GET /api/v1/transit/plan`.

## Security Context Assessment

| Context | Active? | Rationale |
|---------|---------|-----------|
| CTX-RBAC | **Yes** | New REST endpoint needs auth + rate limiting |
| CTX-INPUT | **Yes** | Lat/lon query params, datetime strings need validation |
| CTX-INFRA | **Yes** | Docker compose changes, new service networking |
| CTX-AUTH | No | No auth flow changes |
| CTX-FILE | No | No file uploads |
| CTX-AGENT | No | No agent tool changes (future: agent tool wrapper) |

## Research Summary

### Existing Transit Architecture

- **Router**: `app/transit/routes.py:39` — prefix `/api/v1/transit`, 6 existing endpoints
- **Service singleton**: `app/transit/service.py:336-377` — `get_transit_service()` pattern with module-level `_transit_service`
- **HTTP client**: `httpx.AsyncClient` with timeout/keepalive tuning (service.py:340-345)
- **Circuit breaker**: `app.core.resilience.CircuitBreaker` (failure_threshold, reset_timeout)
- **Redis access**: `app.core.redis.get_redis()` async factory
- **Error handling**: `TransitDataError` -> HTTP 503 via global exception handler (no route-level catch needed)
- **Config**: `app/core/config.py` — OwnTracks settings at line 124-130, insert OTP after

### Delay Enrichment Strategy

OTP legs reference GTFS `trip_id` and `route_id`. Redis stores enriched vehicle JSON at `vehicle:{feed_id}:{vehicle_id}` with `trip_id` and `delay_seconds` fields. Strategy: read all vehicles from Redis via `redis_reader.get_vehicles_from_redis()`, build `trip_id -> delay_seconds` map, match against each transit leg's `tripId`. No poller changes needed — journey plans have <=10 transit legs so O(n) scan is fine.

### Key Dependencies (already installed)

`httpx`, `redis[hiredis]`, `pydantic`, `structlog`, `slowapi`, `fastapi`

## Test Landscape

- 21 transit test files, 165 test functions, all passing
- HTTP mock pattern: `AsyncMock(spec=httpx.AsyncClient)` + `MagicMock` responses
- Redis mock pattern: `patch("module.get_redis")` with AsyncMock
- Auth override: `app.dependency_overrides[get_current_user] = _mock_admin_user` (autouse fixture)
- Rate limiter: `limiter.enabled = False` at module level
- REST endpoint tests: `AsyncClient(transport=ASGITransport(app=app))`
- Error mapping: `TransitDataError` -> 503 (global handler, no route-level catch)

## Type Check Baseline

- **Pyright**: 0 errors on `app/transit/`
- **Mypy**: 0 errors on `app/transit/`
- 11 justified inline suppressions (geoalchemy2, redis-py stubs)

## Files to Create/Modify

| Action | File | Purpose |
|--------|------|---------|
| CREATE | `scripts/build_otp_graph.sh` | Download Latvia OSM + GTFS, build OTP graph |
| CREATE | `otp/` directory | OTP config + graph volume mount |
| UPDATE | `docker-compose.yml` | Add OTP 2.x service with `journey_planner` profile |
| UPDATE | `app/core/config.py:130` | Add OTP settings (url, timeout, cache TTL, feature flag) |
| UPDATE | `.env.example` | Add OTP env vars |
| CREATE | `app/transit/otp_client.py` | HTTP client for OTP `/plan` API with circuit breaker |
| CREATE | `app/transit/journey_planner.py` | Service: proxy OTP, enrich delays, cache results |
| UPDATE | `app/transit/schemas.py:185` | Add JourneyPlan/Leg/Step response schemas |
| UPDATE | `app/transit/routes.py:39` | Add `GET /plan` endpoint |
| CREATE | `app/transit/tests/test_otp_client.py` | OTP client unit tests |
| CREATE | `app/transit/tests/test_journey_planner.py` | Journey planner service + route tests |
| UPDATE | `docs/logging-standard.md` | Add journey_planner log events |

## Implementation Steps

### Step 1: OTP Graph Build Script + Docker Config

**CREATE** `scripts/build_otp_graph.sh` — bash script (`set -euo pipefail`):
1. `mkdir -p otp/graphs`
2. Download Latvia OSM from `https://download.geofabrik.de/europe/latvia-latest.osm.pbf` -> `otp/graphs/`
3. Download Riga GTFS from `https://data.gov.lv/dati/dataset/marsrutu-saraksti-rigas-satiksme/resource/gtfs.zip` -> `otp/graphs/`
4. Run `docker run --rm -v otp/graphs:/var/otp/graphs opentripplanner/opentripplanner:2.6.0 --build --save /var/otp/graphs`
5. Make executable (`chmod +x`)

**CREATE** `otp/router-config.json` — OTP routing defaults: walkSpeed 1.3, maxWalkDistance 2000, numItineraries 5, empty updaters array.

**UPDATE** `docker-compose.yml` — add `otp` service after mosquitto block. Follow existing profile pattern (traccar/mosquitto):
- Image: `docker.io/opentripplanner/opentripplanner:2.6.0`
- Profile: `journey_planner`
- Command: `["--load", "--serve", "/var/otp/graphs"]`
- Expose: 8080, port `${OTP_PORT:-8080}:8080`
- Volumes: `./otp/graphs:/var/otp/graphs:ro`, `./otp/router-config.json:/var/otp/graphs/router-config.json:ro`
- Env: `JAVA_OPTS: "${OTP_JAVA_OPTS:--Xmx1g}"`
- Healthcheck: `curl -sf http://localhost:8080/otp/routers/default` (30s interval, 60s start_period)
- Memory limit: 1536M

**Validation:** `docker compose config --profiles journey_planner` parses without error.

### Step 2: Config Settings

**UPDATE** `app/core/config.py` — insert after line 130 (owntracks section), before line 132 (computed_field). Add 7 settings: `otp_enabled: bool = False`, `otp_base_url: str = "http://otp:8080"`, `otp_router_id: str = "default"`, `otp_timeout_seconds: float = 10.0`, `otp_cache_ttl_seconds: int = 300`, `otp_max_itineraries: int = 5`, `otp_max_walk_distance_m: int = 2000`.

**UPDATE** `.env.example` — add `OTP_ENABLED`, `OTP_BASE_URL`, `OTP_TIMEOUT_SECONDS` with comment.

**Validation:** `uv run python -c "from app.core.config import get_settings; s = get_settings(); print(s.otp_enabled, s.otp_base_url)"`

### Step 3: Journey Plan Schemas

**UPDATE** `app/transit/schemas.py` — append after line 185. Add 4 schemas:

1. `TransportMode = Literal["WALK", "BUS", "TRAM", "RAIL", "SUBWAY", "FERRY", "TROLLEYBUS", "BICYCLE", "CAR"]`
2. `JourneyLeg(BaseModel)` — `mode: TransportMode`, `from_name/lat/lon`, `to_name/lat/lon`, `start_time/end_time: datetime.datetime`, `duration_seconds: int`, `distance_m: float`, transit-specific optionals (`route_id`, `route_short_name`, `route_long_name`, `trip_id`, `agency_name`, `num_stops`), enrichment fields (`realtime_delay_seconds: int | None`, `scheduled_start_time: datetime.datetime | None`, `polyline: str | None`). All with `ConfigDict(strict=True)`.
3. `JourneyItinerary(BaseModel)` — `start_time/end_time: datetime.datetime`, `duration_seconds`, `walk_distance_m`, `transit_time_seconds`, `waiting_time_seconds`, `transfers: int`, `legs: list[JourneyLeg]`.
4. `JourneyPlanResponse(BaseModel)` — `from_name/lat/lon`, `to_name/lat/lon`, `itineraries: list[JourneyItinerary]`, `requested_at: datetime.datetime`, `otp_enriched: bool = False`.

**Validation:** `uv run ruff format app/transit/schemas.py && uv run ruff check --fix app/transit/schemas.py && uv run pyright app/transit/schemas.py`

### Step 4: OTP Client

**CREATE** `app/transit/otp_client.py` — pyright directive: `reportUnknownMemberType=false`

Class `OTPClient`:
- Constructor: `http_client: httpx.AsyncClient`, `settings: Settings`. Store `_base_url` (strip trailing `/`), `_router_id`, `_breaker = CircuitBreaker(name="otp-planner", failure_threshold=5, reset_timeout=60.0)`.
- Method `async def plan(self, params: dict[str, str]) -> dict[str, Any]`:
  - URL: `{base_url}/otp/routers/{router_id}/plan`
  - Wrap in `async with self._breaker:` context manager
  - `await self._http.get(url, params=params)` -> `.raise_for_status()` -> `.json()`
  - Catch `httpx.HTTPStatusError` -> log `transit.otp_client.plan_http_error` -> raise `TransitDataError`
  - Catch `httpx.ConnectError | httpx.TimeoutException` -> log `transit.otp_client.plan_connection_failed` -> raise `TransitDataError`
  - Catch `Exception` (CircuitOpenError etc.) -> log `transit.otp_client.plan_failed` -> raise `TransitDataError`
- Import `TransitDataError` from `app.core.agents.exceptions` (lazy import inside method to avoid circular)

**Validation:** `uv run ruff format app/transit/otp_client.py && uv run ruff check --fix app/transit/otp_client.py && uv run pyright app/transit/otp_client.py`

### Step 5: Journey Planner Service

**CREATE** `app/transit/journey_planner.py` — pyright directive: `reportUnknownMemberType=false`

Constants: `_LAT_MIN, _LAT_MAX = 55.5, 58.1` / `_LON_MIN, _LON_MAX = 20.5, 28.3` (Latvia bbox).

Class `JourneyPlannerService`:
- Constructor: `otp_client: OTPClient`, `settings: Settings`
- **`async def plan_journey(from_lat, from_lon, to_lat, to_lon, depart_at=None, arrive_by=None, modes="TRANSIT,WALK") -> JourneyPlanResponse`**:
  1. Validate coords within Latvia bounds -> `TransitDataError` if outside
  2. Check Redis cache (key = `_cache_key(...)`) -> return if hit, log `transit.journey_planner.cache_hit`
  3. Build OTP params: `fromPlace`, `toPlace`, `date`, `time`, `mode`, `numItineraries`, `maxWalkDistance`. If `arrive_by`: add `arriveBy=true`
  4. Log `transit.journey_planner.plan_requested`
  5. Call `self._otp.plan(params)` -> raw OTP response
  6. Map `raw["plan"]["itineraries"]` -> `list[JourneyItinerary]` via `_map_itinerary()`
  7. Enrich: `_build_delay_map()` -> `dict[str, int]` (trip_id -> delay_seconds)
  8. Build `JourneyPlanResponse` from OTP `plan.from/to` + mapped itineraries
  9. Cache result, log `transit.journey_planner.plan_completed`

- **`_map_itinerary(itin: dict, delay_map: dict) -> JourneyItinerary`**: Extract OTP 2.x fields (timestamps in ms -> `_ms_to_dt()`). Fields: `startTime`, `endTime`, `duration`, `walkDistance`, `transitTime`, `waitingTime`, `transfers`, `legs`.

- **`_map_leg(leg: dict, delay_map: dict) -> JourneyLeg`**: Map OTP leg. Mode validation against `TransportMode` Literal (fallback `WALK`). Extract `from/to` place name/lat/lon. Transit fields: `routeId`, `routeShortName`, `route`, `tripId`, `agencyName`, `numIntermediateStops`. Enrichment: if `trip_id in delay_map`, set `realtime_delay_seconds` and `scheduled_start_time`. Polyline from `legGeometry.points`.

- **`async def _build_delay_map() -> dict[str, int] | None`**: If `otp_enabled=False`, return None. SCAN Redis for `feed:*:vehicles` sets. For each feed, SMEMBERS -> MGET vehicle JSONs -> extract `trip_id`/`delay_seconds`. Wrapped in try/except — log warning on failure, return None (graceful degradation). Redis type ignores: `# type: ignore[misc]`.

- **`_cache_key(from_lat, ...) -> str`**: Round lat/lon to 4 decimals (~11m). MD5 hash (first 12 chars, `usedforsecurity=False`, `# noqa: S324`). Prefix: `journey_plan:`.

- **`_get_cached(key) -> JourneyPlanResponse | None`**: Redis GET -> `model_validate_json()`. Try/except with debug log.

- **`_set_cached(key, plan)`**: Redis SET with `ex=otp_cache_ttl_seconds`. `# type: ignore[misc]`. Try/except with debug log.

Module functions:
- **`_ms_to_dt(ms) -> datetime`**: OTP millisecond timestamp -> `datetime.fromtimestamp(ms/1000, tz=UTC)`. Fallback: `now(UTC)`.
- **`get_journey_planner(settings=None) -> JourneyPlannerService`**: Singleton pattern (like `get_transit_service`). Creates `httpx.AsyncClient` with `otp_timeout_seconds`, `OTPClient`, `JourneyPlannerService`.
- **`async def close_journey_planner()`**: `aclose()` the HTTP client. Wrap in `try/except RuntimeError: pass` (event loop may be closed). Reset singleton to None.

**Validation:** `uv run ruff format app/transit/journey_planner.py && uv run ruff check --fix app/transit/journey_planner.py && uv run pyright app/transit/journey_planner.py`

### Step 6: REST Endpoint

**UPDATE** `app/transit/routes.py` — add import at top (after existing schema imports):

```python
from app.transit.schemas import JourneyPlanResponse  # add to existing import block
from app.transit.journey_planner import get_journey_planner
```

Add `GET /plan` endpoint before the phone assignment section (`# -- Phone Assignment` comment). Pattern follows existing `get_vehicles` endpoint:

- `@router.get("/plan", response_model=JourneyPlanResponse)`
- `@limiter.limit("10/minute")` (lower than vehicles — OTP is slower)
- Query params with `# noqa: B008`: `from_lat: float = Query(..., ge=55.5, le=58.1)`, `from_lon: float = Query(..., ge=20.5, le=28.3)`, same for `to_lat/to_lon`. `depart_at: str | None = Query(None, max_length=30)`, `arrive_by: str | None = Query(None, max_length=30)`, `modes: str = Query("TRANSIT,WALK", max_length=100, pattern=r"^[A-Z,]+$")`
- Auth: `_current_user: User = Depends(get_current_user)`
- `_ = request` for rate limiter
- Parse `depart_at`/`arrive_by` via existing `_parse_iso_time()` helper (returns 422 on bad format)
- Reject both `depart_at` AND `arrive_by` -> HTTPException 422
- Call `get_journey_planner().plan_journey(...)` and return
- Log `transit.api.plan_requested`
- Docstring notes `TransitDataError` -> 503 via global handler

**Validation:** `uv run ruff format app/transit/routes.py && uv run ruff check --fix app/transit/routes.py && uv run pyright app/transit/routes.py`

### Step 7: Shutdown Registration

**UPDATE** `app/main.py` — in the lifespan function, add OTP shutdown registration alongside existing transit service shutdown. Add import:

```python
from app.transit.journey_planner import close_journey_planner
```

Register in shutdown coordinator (after existing transit registrations):

```python
coordinator.register(ShutdownTask(
    name="journey_planner",
    drain_timeout_s=2.0,
    drain=close_journey_planner,
))
```

**Validation:** `uv run ruff check app/main.py && uv run pyright app/main.py`

### Step 8: Unit Tests — OTP Client

**CREATE** `app/transit/tests/test_otp_client.py`:

Test structure:
- `test_plan_success` — mock httpx.get returns OTP JSON, verify params passed correctly
- `test_plan_http_error` — mock raises `httpx.HTTPStatusError`, verify `TransitDataError`
- `test_plan_connection_error` — mock raises `httpx.ConnectError`, verify `TransitDataError`
- `test_plan_timeout` — mock raises `httpx.TimeoutException`, verify `TransitDataError`
- `test_circuit_breaker_trips` — 5 failures open circuit, next call raises `TransitDataError`

Mock pattern: `AsyncMock(spec=httpx.AsyncClient)`, `MagicMock` for response with `.json()` and `.raise_for_status()`.

**Validation:** `uv run pytest app/transit/tests/test_otp_client.py -v`

### Step 9: Unit Tests — Journey Planner Service + Route

**CREATE** `app/transit/tests/test_journey_planner.py`:

Test structure:

**Service tests (mock OTPClient + Redis):**
- `test_plan_journey_success` — OTP returns 2 itineraries, verify schema mapping
- `test_plan_journey_cache_hit` — Redis returns cached plan, OTP not called
- `test_plan_journey_cache_miss` — Redis empty, OTP called, result cached
- `test_delay_enrichment` — vehicle in Redis with trip_id+delay, verify leg enriched
- `test_delay_enrichment_redis_down` — Redis error returns plan without enrichment (otp_enriched=False)
- `test_coordinates_outside_latvia` — raises TransitDataError
- `test_cache_key_rounding` — coordinates differing by < 11m produce same cache key

**Route tests (AsyncClient + ASGITransport):**
- `test_plan_endpoint_200` — valid params return JourneyPlanResponse
- `test_plan_endpoint_422_both_times` — depart_at AND arrive_by returns 422
- `test_plan_endpoint_422_invalid_coords` — lat outside Latvia bounds returns 422
- `test_plan_endpoint_503_otp_down` — TransitDataError maps to 503
- `test_plan_endpoint_401_no_auth` — no auth returns 401/403

Auth override pattern: autouse fixture with `app.dependency_overrides[get_current_user]`.
Rate limiter: `limiter.enabled = False` at module level.

**Validation:** `uv run pytest app/transit/tests/test_journey_planner.py -v`

### Step 10: CMS Journey Planner Page (outline)

**CREATE** `cms/apps/web/src/app/[locale]/(dashboard)/planner/page.tsx`:

Structure:
- Server component wrapper with `useTranslations("planner")`
- Client component `JourneyPlannerForm` — two location inputs (lat/lon or address search), datetime picker, mode selector
- `JourneyResults` — list of itineraries with duration, transfers, walk distance
- `JourneyMap` — Leaflet map with colored polylines per leg mode (walk=gray, bus=blue, tram=red, rail=green)
- SDK call: `GET /api/v1/transit/plan` via `@vtv/sdk`

**i18n keys** (both `lv.json` and `en.json`):
- `planner.title`, `planner.from`, `planner.to`, `planner.departAt`, `planner.arriveBy`
- `planner.search`, `planner.noResults`, `planner.itineraries`, `planner.transfers`
- `planner.walk`, `planner.bus`, `planner.tram`, `planner.rail`, `planner.delay`

**Sidebar nav**: Add entry after "Map" in dashboard layout.

**RBAC**: All authenticated roles (viewer+).

> CMS implementation is a follow-up task — backend is the priority.

## Preflight Warnings

- `app/transit/routes.py` uses `# noqa: B008` on all `Query()` defaults — follow same pattern
- `app/transit/routes.py:1` has pyright file-level directives — preserve them
- Transit test files use `limiter.enabled = False` AFTER all imports (Ruff E402)
- `TransitDataError` is in `app.core.agents.exceptions`, not `app.transit.exceptions`
- Redis `smembers`/`set` calls need `# type: ignore[misc]` (redis-py async stubs)

## Security Checklist

- [x] `get_current_user` dependency on `/plan` endpoint
- [x] `@limiter.limit("10/minute")` rate limiting (lower than vehicle endpoint — OTP is slower)
- [x] Input validation via `Query(ge=, le=)` for lat/lon bounds
- [x] `max_length` on string query params (depart_at, arrive_by, modes)
- [x] `pattern=r"^[A-Z,]+$"` regex on modes param
- [x] Error responses use `TransitDataError` (global handler -> 503)
- [x] No credential exposure in logs (OTP is internal network, no auth)
- [x] Docker service: internal port only, `profiles` gate

## Verification

- [ ] `make lint` passes (ruff format + check)
- [ ] `make types` passes (mypy + pyright)
- [ ] `make test` passes (all unit tests including new)
- [ ] `make security-audit-quick` passes
- [ ] New `/plan` endpoint has auth + rate limiting
- [ ] Pyright errors <= baseline (0 errors before)
- [ ] `docker compose config --profiles journey_planner` validates
- [ ] Security convention tests pass: `uv run pytest app/tests/test_security.py -v`
