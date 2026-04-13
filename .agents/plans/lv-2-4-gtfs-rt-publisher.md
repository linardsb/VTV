# Plan: LV-2.4 GTFS-RT Publisher (Combined Feed)

## Context

VTV aggregates 5+ GTFS-RT feeds into a unified view. Publishing a combined GTFS-RT feed at `GET /api/v1/transit/gtfs-rt/vehicle_positions.pb` turns VTV into a data provider — registrable on the Mobility Database and usable by any GTFS-RT consumer (Google Maps, Transit app, etc.).

## Security Context Assessment

**Active:** CTX-RBAC (new endpoint), CTX-INPUT (query params)
**Not active:** CTX-AUTH (public endpoint, no auth), CTX-FILE, CTX-AGENT, CTX-INFRA

- Public endpoint — no auth required, rate limited 60/min (anonymous tier handles abuse)
- Optional `feed_id` query param needs max_length + pattern validation
- No ILIKE queries, no file handling, no agent tools

## Research Summary

### Redis Vehicle Storage Pattern
- Individual keys: `vehicle:{feed_id}:{vehicle_id}` → JSON `EnrichedVehicle` (TTL 120s)
- Feed set: `feed:{feed_id}:vehicles` → set of vehicle IDs
- Reader: `app/transit/redis_reader.py:15-80` — `get_vehicles_from_redis()` + `_read_feed_vehicles()`

### Protobuf Infrastructure
- Type stubs: `typings/google/transit/gtfs_realtime_pb2.pyi` — `FeedMessage`, `FeedEntity`, `VehiclePosition`, etc.
- Existing parsing: `app/core/agents/tools/transit/client.py:192-210` — `feed.ParseFromString(raw)`
- **No existing serialization** — `SerializeToString()` is new for LV-2.4
- Stubs need `id` field on `FeedEntity` and `gtfs_rt_version` on `FeedHeader` for building feeds

### Key Patterns to Follow
- Binary response: `app/compliance/routes.py:39-73` — `Response(content=bytes, media_type=...)`
- Transit routes: `app/transit/routes.py:34` — `APIRouter(prefix="/api/v1/transit")`
- Rate limiting: `@limiter.limit("60/minute")` + `request: Request` param
- Redis access: `await get_redis()` singleton, `smembers()`, `mget()`, `set(key, val, ex=ttl)`
- Structured logging: `get_logger(__name__)`, `transit.publisher.action_state` pattern

### VehicleStopStatus Mapping
`schemas.py:13` defines `Literal["IN_TRANSIT_TO", "STOPPED_AT", "INCOMING_AT"]`.
Protobuf enum values: `IN_TRANSIT_TO=2`, `STOPPED_AT=1`, `INCOMING_AT=0`.

## Test Landscape

- Transit has 15 test files, 3833 lines total
- Redis mock pattern: `_make_mock_redis()` with `AsyncMock` + `MagicMock` pipeline (`test_poller_history.py:23-34`)
- Rate limit disabled in tests: `limiter.enabled = False` (`test_routes.py:17`)
- Root conftest provides `client` (TestClient) and `mock_settings` fixtures
- No existing protobuf serialization tests — this will be the first
- Public endpoint test pattern: `app/public_api/tests/test_routes.py`

## Type Check Baseline

- **Pyright: 0 errors** on `app/transit/`
- **Mypy: 0 errors** (40 source files)
- Target: 0 errors after implementation

## Files to Create/Modify

| Action | File | Purpose |
|--------|------|---------|
| CREATE | `app/transit/gtfs_rt_publisher.py` | `build_combined_feed()` — reads Redis, builds protobuf FeedMessage, caches result |
| UPDATE | `app/transit/routes.py` | Add `GET /gtfs-rt/vehicle_positions.pb` endpoint |
| UPDATE | `typings/google/transit/gtfs_realtime_pb2.pyi` | Add `id` field to `FeedEntity`, `gtfs_rt_version` to `FeedHeader` |
| CREATE | `app/transit/tests/test_gtfs_rt_publisher.py` | 8+ unit tests for publisher + endpoint |

## Implementation Steps

### Step 1: Update protobuf type stubs

**File:** `typings/google/transit/gtfs_realtime_pb2.pyi`

Add missing fields needed for building (not just parsing) FeedMessage:
- `FeedEntity.id: str` — required entity identifier
- `FeedHeader.gtfs_rt_version: str` — spec requires "2.0"

**Validation:** `uv run pyright typings/google/transit/gtfs_realtime_pb2.pyi`

### Step 2: Create GTFS-RT publisher module

**File:** `app/transit/gtfs_rt_publisher.py`

```python
# pyright: reportUnknownMemberType=false, reportMissingTypeStubs=false
```

**Functions:**

1. `_status_to_enum(status: str) -> int` — maps `"IN_TRANSIT_TO"` → 2, `"STOPPED_AT"` → 1, `"INCOMING_AT"` → 0

2. `async def build_combined_feed(*, feed_id: str | None = None) -> bytes`:
   - Check Redis cache key `gtfs_rt:combined:vehicle_positions` (or `gtfs_rt:combined:vehicle_positions:{feed_id}` if filtered)
   - If cache hit, return cached bytes
   - Call `_read_all_vehicles(feed_id=feed_id)` to get vehicle data from Redis (reuse `_read_feed_vehicles` from `redis_reader.py`)
   - Build `gtfs_realtime_pb2.FeedMessage`:
     - `header.gtfs_rt_version = "2.0"`
     - `header.timestamp = int(datetime.now(tz=UTC).timestamp())`
     - For each vehicle: `entity = feed.entity.add()`, set `entity.id = f"{feed_id}_{vehicle_id}"`, populate `entity.vehicle` fields
   - Serialize: `result = feed.SerializeToString()`
   - Cache in Redis with 5s TTL
   - Log `transit.publisher.build_completed` with vehicle count
   - Return bytes

3. `async def _read_all_vehicles(*, feed_id: str | None = None) -> list[dict[str, object]]`:
   - Get enabled feed IDs from settings (or single feed_id if specified)
   - For each feed: `smembers(f"feed:{fid}:vehicles")` → `mget([f"vehicle:{fid}:{vid}" ...])` → parse JSON
   - Return list of dicts (raw EnrichedVehicle data)

**Logging events:**
- `transit.publisher.build_started` (info)
- `transit.publisher.build_completed` (info, vehicle_count=N, feed_id=...)
- `transit.publisher.cache_hit` (debug)
- `transit.publisher.build_failed` (error)

**Validation:** `uv run ruff format app/transit/gtfs_rt_publisher.py && uv run ruff check --fix app/transit/gtfs_rt_publisher.py && uv run pyright app/transit/gtfs_rt_publisher.py && uv run mypy app/transit/gtfs_rt_publisher.py`

### Step 3: Add endpoint to transit routes

**File:** `app/transit/routes.py`

Add at end of file:

```python
@router.get("/gtfs-rt/vehicle_positions.pb")
@limiter.limit("60/minute")
async def get_gtfs_rt_vehicle_positions(
    request: Request,
    feed_id: str | None = Query(None, max_length=50, pattern=r"^[\w\-]+$"),  # noqa: B008
) -> Response:
    """Serve combined GTFS-RT VehiclePositions feed as protobuf.

    Public endpoint — no authentication required. Rate limited to 60 requests/minute.
    Returns binary protobuf (application/x-protobuf).
    """
    from app.transit.gtfs_rt_publisher import build_combined_feed

    pb_bytes = await build_combined_feed(feed_id=feed_id)
    return Response(
        content=pb_bytes,
        media_type="application/x-protobuf",
    )
```

**Key decisions:**
- No auth dependency — public endpoint
- `Response` return type for binary content (not a Pydantic model)
- Lazy import to avoid circular imports
- `feed_id` query param with same validation pattern as existing `/vehicles` endpoint
- 60/min rate limit (higher than authenticated /vehicles 30/min — public consumers need headroom)

**Imports to add:** `from fastapi.responses import Response`

**Validation:** `uv run ruff format app/transit/routes.py && uv run ruff check --fix app/transit/routes.py && uv run pyright app/transit/routes.py && uv run mypy app/transit/routes.py`

### Step 4: Write unit tests

**File:** `app/transit/tests/test_gtfs_rt_publisher.py`

```python
# pyright: reportCallIssue=false, reportUnknownMemberType=false
```

**Test structure:**

```
class TestBuildCombinedFeed:
    test_single_feed_serialization          — 1 vehicle, verify protobuf round-trip
    test_multi_feed_assembly                — 2 feeds × 2 vehicles, verify 4 entities with correct IDs
    test_empty_feeds_returns_valid_feed     — no vehicles, verify valid FeedMessage with 0 entities
    test_cache_hit_returns_cached_bytes     — pre-populate cache key, verify no Redis vehicle reads
    test_cache_miss_populates_cache         — verify cache SET after build
    test_feed_id_filter                     — only vehicles from specified feed

class TestGtfsRtEndpoint:
    test_returns_protobuf_content_type      — response Content-Type is application/x-protobuf
    test_returns_valid_protobuf             — parse response bytes with FeedMessage.ParseFromString
    test_feed_id_query_param                — filter by feed_id query param
```

**Mock strategy:**
- Patch `app.transit.gtfs_rt_publisher.get_redis` → `AsyncMock`
- Mock `smembers()` → set of vehicle IDs
- Mock `mget()` → list of JSON vehicle dicts
- Mock `get()` (cache read) → `None` for miss, bytes for hit
- Mock `set()` (cache write) → verify called with correct key + TTL
- For endpoint tests: patch `build_combined_feed` → return pre-built bytes
- `limiter.enabled = False` at module level
- Use `client` fixture from root conftest

**Validation:** `uv run pytest app/transit/tests/test_gtfs_rt_publisher.py -v && uv run pyright app/transit/tests/test_gtfs_rt_publisher.py`

## Preflight Fixes Applied

| File | Line | Pattern | What Changed |
|------|------|---------|--------------|
| `app/tests/test_security.py` | 718 | `PUBLIC_ALLOWLIST` | Added `"get_gtfs_rt_vehicle_positions"` — public endpoint needs allowlist entry |

## Preflight Warnings

- `redis_reader.py:63` uses `# type: ignore[misc]` on `smembers()` — same pattern needed in publisher
- `redis_reader.py:78` uses `# type: ignore[arg-type]` on VehiclePosition construction — publisher uses raw dicts instead
- Type stubs for protobuf `entity.add()` returns unknown type — may need `# type: ignore` on `.add()` calls
- `pipeline()` in Redis is sync (returns `MagicMock` not `AsyncMock`) — only `execute()` is async (anti-pattern #35)

## Security Checklist

- [x] Public endpoint — no auth required (intentional, documented)
- [x] `@limiter.limit("60/minute")` rate limiting
- [x] `feed_id` param: `max_length=50`, `pattern=r"^[\w\-]+$"` (matches existing pattern)
- [x] No ILIKE queries (Redis-only reads)
- [x] No user input in Redis keys beyond validated `feed_id`
- [x] Error responses use structured logging, no internal type leakage

## Verification

- [ ] `uv run ruff format app/transit/gtfs_rt_publisher.py app/transit/routes.py`
- [ ] `uv run ruff check app/transit/ --fix`
- [ ] `uv run pyright app/transit/` — 0 errors (baseline: 0)
- [ ] `uv run mypy app/transit/` — 0 errors (baseline: 0)
- [ ] `uv run pytest app/transit/tests/test_gtfs_rt_publisher.py -v` — all pass
- [ ] `uv run pytest app/transit/tests/ -v` — no regressions
- [ ] `make security-audit-quick` passes
