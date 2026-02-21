# Plan: Multi-Feed GTFS-RT Tracking with Redis Caching

## Feature Metadata
**Feature Type**: New Capability (Infrastructure + Enhancement)
**Estimated Complexity**: High
**Primary Systems Affected**: `app/transit/`, `app/core/config.py`, `app/core/health.py`, `app/main.py`, `docker-compose.yml`

## Feature Description

VTV currently tracks vehicle positions from a single GTFS-RT feed (Rigas Satiksme) using in-memory caching within the Python process. This plan introduces two foundational capabilities:

1. **Multi-feed support** - A feed registry system allowing VTV to poll vehicle positions from multiple transit operators simultaneously (Riga, Jurmala, Pieriga, and future feeds). Each feed has its own GTFS-RT URLs and poll interval.

2. **Redis caching layer** - Replaces the per-process in-memory vehicle position cache with Redis, enabling shared state across multiple workers, automatic TTL-based expiration of stale vehicles, and sub-millisecond reads for the REST API and agent tools.

The background poller runs as an asyncio task within the FastAPI lifespan, polling each feed at its configured interval and writing normalized vehicle positions to Redis. The REST API and agent tools read from Redis instead of fetching GTFS-RT on every request. The static GTFS cache remains in-memory (24h TTL) since it changes infrequently and is read-heavy.

## User Story

As a transit operations dispatcher
I want to see live vehicle positions from multiple Latvian transit operators on a single map
So that I can monitor cross-operator services and respond to disruptions across the network

## Solution Approach

We introduce a background poller pattern with Redis as the shared cache layer. The poller fetches GTFS-RT feeds at configured intervals and writes normalized vehicle positions to Redis with a 120-second TTL. The REST API reads from Redis, making responses fast and consistent across concurrent requests.

**Approach Decision:**
We chose a background poller + Redis over the current on-demand fetch pattern because:
- On-demand fetch creates latency spikes (100-500ms per feed) on cold cache
- In-memory cache is per-process and cannot be shared across workers
- Multiple feeds polled on-demand would multiply latency linearly
- Redis provides atomic reads, automatic TTL expiry, and horizontal scaling

**Alternatives Considered:**
- **PostgreSQL-only (no Redis)**: Rejected because 500+ vehicle positions updated every 10s = 3000 writes/min. Redis handles this natively; PostgreSQL would need WAL tuning and still be slower for reads.
- **Celery background workers**: Rejected because asyncio tasks in FastAPI lifespan are simpler, avoid an additional dependency (Celery + broker), and are sufficient for single-process deployment.
- **Keep in-memory with multi-feed**: Rejected because cache is per-process and stale on restart. Redis survives app restarts and shares state.

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` - Architecture rules, logging patterns, type checking requirements, Python anti-patterns
- `app/core/config.py` - Current Settings class with single-feed GTFS-RT URLs (lines 56-62)
- `app/core/health.py` - Health check patterns with caching (entire file)
- `app/main.py` - Lifespan management, router registration, singleton cleanup (lines 41-100)

### Similar Features (Examples to Follow)
- `app/transit/service.py` - Singleton pattern with `get_transit_service()` and `close_transit_service()` (lines 167-207)
- `app/core/agents/tools/transit/client.py` - GTFS-RT protobuf parsing in `_parse_vehicle_positions()` (lines 198-246) and `_parse_trip_updates()` (lines 248-311)
- `app/core/agents/tools/transit/static_cache.py` - Static GTFS cache singleton pattern (lines 406-428)
- `app/transit/routes.py` - Thin route handler delegating to service (lines 22-43)
- `app/transit/schemas.py` - VehiclePosition and VehiclePositionsResponse schemas (entire file)

### Files to Modify
- `app/core/config.py` - Add Redis URL, feed registry config, poller settings
- `app/core/health.py` - Add Redis health check endpoint
- `app/transit/service.py` - Refactor to read from Redis instead of direct GTFS-RT fetch
- `app/transit/routes.py` - Add `feed_id` query parameter
- `app/transit/schemas.py` - Add `feed_id` and `operator_name` fields to VehiclePosition
- `app/main.py` - Start/stop poller and Redis in lifespan
- `docker-compose.yml` - Add Redis service
- `.env.example` - Add `REDIS_URL`
- `pyproject.toml` - Add `redis[hiredis]` dependency

## Implementation Plan

### Phase 1: Infrastructure (Tasks 1-5)
Add Redis dependency, Docker service, configuration, and client singleton.

### Phase 2: Feed Registry & Poller (Tasks 6-10)
Create the feed registry model, GTFS-RT poller background task, and Redis write pipeline.

### Phase 3: Service Refactor & API (Tasks 11-14)
Refactor TransitService to read from Redis, update REST API with multi-feed support.

### Phase 4: Testing & Integration (Tasks 15-19)
Unit tests for all new modules, integration wiring, final validation.

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.

---

### Task 1: Add Redis dependency
**File:** `pyproject.toml` (modify existing)
**Action:** UPDATE

Add `redis[hiredis]` to the `[project.dependencies]` section. The `hiredis` extra provides a C-based parser for 10x faster Redis protocol parsing.

Add this line alongside existing dependencies:
```
"redis[hiredis]>=5.2.0",
```

Then install:
```bash
uv add "redis[hiredis]>=5.2.0"
```

Add mypy override for redis (it has partial typing):
```toml
[[tool.mypy.overrides]]
module = "redis.*"
ignore_missing_imports = true
```

**Per-task validation:**
- `uv sync` succeeds
- `uv run python -c "import redis; print(redis.__version__)"` prints version

---

### Task 2: Add Redis service to Docker Compose
**File:** `docker-compose.yml` (modify existing)
**Action:** UPDATE

Add a `redis` service BEFORE the `app` service:

```yaml
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 3
    deploy:
      resources:
        limits:
          cpus: "0.25"
          memory: 128M
    restart: unless-stopped
```

Add `redis_data` to the `volumes` section at the bottom:
```yaml
volumes:
  postgres_data:
  redis_data:
```

Add `redis` to the `app` service `depends_on`:
```yaml
  app:
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
```

**Per-task validation:**
- YAML syntax is valid (no tab characters, proper indentation)

---

### Task 3: Update configuration with Redis and feed settings
**File:** `app/core/config.py` (modify existing)
**Action:** UPDATE

Add a `TransitFeedConfig` Pydantic model ABOVE the `Settings` class. This model defines one GTFS-RT feed source:

```python
class TransitFeedConfig(BaseModel):
    """Configuration for a single GTFS-RT transit feed."""

    feed_id: str
    operator_name: str
    rt_vehicle_positions_url: str
    rt_trip_updates_url: str
    static_url: str
    poll_interval_seconds: int = 10
    enabled: bool = True
```

Add these fields to the `Settings` class:

```python
    # Redis
    redis_url: str = "redis://localhost:6379/0"
    redis_vehicle_ttl_seconds: int = 120

    # Multi-feed GTFS-RT (replaces single-feed URLs)
    transit_feeds_json: str = "[]"
    poller_enabled: bool = True
```

Add a `@computed_field` property to Settings that parses `transit_feeds_json` into a list of `TransitFeedConfig`. If the JSON is empty `"[]"`, fall back to building a single feed from the legacy single-feed URL settings (backward compatibility):

```python
    @computed_field  # type: ignore[prop-decorator]
    @property
    def transit_feeds(self) -> list[TransitFeedConfig]:
        """Parse transit feeds from JSON config, falling back to legacy single-feed URLs."""
        import json

        feeds_raw: list[dict[str, object]] = json.loads(self.transit_feeds_json)
        if feeds_raw:
            return [TransitFeedConfig(**f) for f in feeds_raw]  # type: ignore[arg-type]
        # Backward compatibility: build from legacy single-feed settings
        return [
            TransitFeedConfig(
                feed_id="riga",
                operator_name="Rigas Satiksme",
                rt_vehicle_positions_url=self.gtfs_rt_vehicle_positions_url,
                rt_trip_updates_url=self.gtfs_rt_trip_updates_url,
                static_url=self.gtfs_static_url,
                poll_interval_seconds=self.gtfs_rt_cache_ttl_seconds,
            )
        ]
```

Import `BaseModel` from pydantic (already imported via `BaseSettings`), and `computed_field` from pydantic.

**Per-task validation:**
- `uv run ruff format app/core/config.py`
- `uv run ruff check --fix app/core/config.py` passes
- `uv run mypy app/core/config.py` passes with 0 errors
- `uv run pyright app/core/config.py` passes

---

### Task 4: Create Redis client singleton
**File:** `app/core/redis.py` (create new)
**Action:** CREATE

Create a Redis client singleton module following the pattern from `app/transit/service.py` lines 167-207 (singleton with close function).

```python
"""Redis client singleton for shared state across the application."""

from redis.asyncio import Redis

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_redis_client: Redis | None = None  # type: ignore[type-arg]


async def get_redis() -> Redis:  # type: ignore[type-arg]
    """Get or create the Redis client singleton."""
    global _redis_client  # noqa: PLW0603
    if _redis_client is None:
        settings = get_settings()
        _redis_client = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
        )
        logger.info("redis.connection_initialized", redis_url=settings.redis_url)
    return _redis_client


async def close_redis() -> None:
    """Close the Redis client. Called on app shutdown."""
    global _redis_client  # noqa: PLW0603
    if _redis_client is not None:
        try:
            await _redis_client.aclose()
        except RuntimeError:
            pass  # Event loop already closed
        _redis_client = None
        logger.info("redis.connection_closed")
```

Add pyright directive at top of file:
```python
# pyright: reportUnknownMemberType=false, reportMissingTypeStubs=false
```

**Per-task validation:**
- `uv run ruff format app/core/redis.py`
- `uv run ruff check --fix app/core/redis.py` passes
- `uv run mypy app/core/redis.py` passes
- `uv run pyright app/core/redis.py` passes

---

### Task 5: Add Redis health check
**File:** `app/core/health.py` (modify existing)
**Action:** UPDATE

Add a new `/health/redis` endpoint following the existing `/health/db` pattern. Read the file first to understand the caching pattern (global dict + monotonic time).

Add module-level cache variables:
```python
_redis_health_cache: dict[str, str] | None = None
_redis_health_cache_time: float = 0.0
_REDIS_HEALTH_CACHE_TTL: float = 10.0
```

Add the endpoint:
```python
@router.get("/health/redis")
async def health_redis() -> dict[str, str]:
    """Redis health check with 10s cache."""
    global _redis_health_cache, _redis_health_cache_time  # noqa: PLW0603
    now = time.monotonic()
    if _redis_health_cache is not None and (now - _redis_health_cache_time) < _REDIS_HEALTH_CACHE_TTL:
        return _redis_health_cache
    try:
        redis_client = await get_redis()
        result = await redis_client.ping()
        if not result:
            raise HTTPException(status_code=503, detail="Redis ping failed")
        _redis_health_cache = {"status": "healthy", "service": "redis"}
        _redis_health_cache_time = now
        return _redis_health_cache
    except Exception as e:
        logger.error("redis.health_check_failed", error=str(e), exc_info=True)
        raise HTTPException(status_code=503, detail=f"Redis unavailable: {e}") from e
```

Add import: `from app.core.redis import get_redis`

Also update the `/health/ready` endpoint to include Redis status: call `health_redis()` alongside the existing DB check and include its result.

**Per-task validation:**
- `uv run ruff format app/core/health.py`
- `uv run ruff check --fix app/core/health.py` passes
- `uv run mypy app/core/health.py` passes

---

### Task 6: Update VehiclePosition schema for multi-feed
**File:** `app/transit/schemas.py` (modify existing)
**Action:** UPDATE

Add two new fields to `VehiclePosition`:
```python
    feed_id: str = ""          # Feed source identifier (e.g., "riga", "jurmala")
    operator_name: str = ""    # Human-readable operator name (e.g., "Rigas Satiksme")
```

Add these after the existing `timestamp` field, before `model_config`.

Also add a `feed_id` field to `VehiclePositionsResponse`:
```python
    feed_id: str | None = None  # Filter applied, if any
```

**Per-task validation:**
- `uv run ruff format app/transit/schemas.py`
- `uv run ruff check --fix app/transit/schemas.py` passes
- `uv run mypy app/transit/schemas.py` passes

---

### Task 7: Create the GTFS-RT poller module
**File:** `app/transit/poller.py` (create new)
**Action:** CREATE

This is the core new module. It runs as an asyncio background task, polling GTFS-RT feeds at their configured intervals and writing vehicle positions to Redis.

**Structure:**

```python
"""Background GTFS-RT poller that writes vehicle positions to Redis."""

import asyncio
import json
import time
from datetime import UTC, datetime

import httpx
from redis.asyncio import Redis

from app.core.agents.tools.transit.client import GTFSRealtimeClient
from app.core.agents.tools.transit.static_cache import GTFSStaticCache, get_static_cache
from app.core.config import Settings, TransitFeedConfig, get_settings
from app.core.logging import get_logger
from app.core.redis import get_redis

logger = get_logger(__name__)
```

**Class: `FeedPoller`**

Manages polling for a single feed. Owns its own `GTFSRealtimeClient` instance and HTTP client.

```python
class FeedPoller:
    """Polls a single GTFS-RT feed and writes positions to Redis."""

    def __init__(
        self,
        feed_config: TransitFeedConfig,
        settings: Settings,
    ) -> None:
        self.feed_config = feed_config
        self._settings = settings
        self._http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(10.0, connect=5.0),
            limits=httpx.Limits(max_connections=5, max_keepalive_connections=3),
        )
        self._rt_client = GTFSRealtimeClient(
            http_client=self._http_client, settings=settings
        )
        self._running = False

    async def close(self) -> None:
        self._running = False
        try:
            await self._http_client.aclose()
        except RuntimeError:
            pass
```

**Method: `poll_once()`**

Fetches vehicle positions and trip updates, enriches them using the static cache, and writes each vehicle to Redis as a JSON hash with TTL.

```python
    async def poll_once(self, redis_client: Redis) -> int:
        """Fetch positions from feed, write to Redis. Returns vehicle count."""
        feed_id = self.feed_config.feed_id
        try:
            raw_vehicles = await self._rt_client.fetch_vehicle_positions()
            trip_updates = await self._rt_client.fetch_trip_updates()
            static = await get_static_cache(self._http_client, self._settings)
        except Exception as e:
            logger.error(
                "transit.poller.fetch_failed",
                feed_id=feed_id,
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True,
            )
            return 0

        trip_update_map = {tu.trip_id: tu for tu in trip_updates}
        ttl = self._settings.redis_vehicle_ttl_seconds
        pipe = redis_client.pipeline()
        count = 0

        for vp in raw_vehicles:
            vehicle_data = self._enrich_vehicle(vp, trip_update_map, static)
            key = f"vehicle:{feed_id}:{vp.vehicle_id}"
            pipe.set(key, json.dumps(vehicle_data), ex=ttl)
            count += 1

        # Track which vehicles belong to this feed (set with TTL)
        feed_key = f"feed:{feed_id}:vehicles"
        vehicle_ids = [vp.vehicle_id for vp in raw_vehicles]
        if vehicle_ids:
            pipe.delete(feed_key)
            pipe.sadd(feed_key, *vehicle_ids)
            pipe.expire(feed_key, ttl)

        await pipe.execute()
        return count
```

**Method: `_enrich_vehicle()`**

Mirrors the enrichment logic from `app/transit/service.py` lines 92-164 (`_enrich_vehicles`), but returns a dict suitable for JSON serialization:

```python
    def _enrich_vehicle(
        self,
        vp: VehiclePositionData,
        trip_update_map: dict[str, TripUpdateData],
        static: GTFSStaticCache,
    ) -> dict[str, object]:
        """Enrich a raw vehicle position into a serializable dict."""
        # Resolve route_id (explicit from GTFS-RT, or via trip lookup)
        route_id = vp.route_id or ""
        if not route_id and vp.trip_id:
            resolved = static.get_trip_route_id(vp.trip_id)
            route_id = resolved if resolved else ""

        route_name = static.get_route_name(route_id) if route_id else ""
        route_info = static.routes.get(route_id)
        route_type = route_info.route_type if route_info else 3

        # Extract delay from trip updates
        delay_seconds = 0
        if vp.trip_id and vp.trip_id in trip_update_map:
            tu = trip_update_map[vp.trip_id]
            matching = [
                stu for stu in tu.stop_time_updates
                if stu.stop_sequence >= vp.current_stop_sequence
            ]
            if matching:
                first = matching[0]
                delay_seconds = first.arrival_delay if first.arrival_delay != 0 else first.departure_delay

        speed_kmh = round(vp.speed * 3.6, 1) if vp.speed is not None else None
        next_stop = static.get_stop_name(vp.stop_id) if vp.stop_id else None
        timestamp = datetime.fromtimestamp(vp.timestamp, tz=UTC).isoformat() if vp.timestamp else ""

        return {
            "vehicle_id": vp.vehicle_id,
            "route_id": route_id,
            "route_short_name": route_name,
            "route_type": route_type,
            "latitude": vp.latitude,
            "longitude": vp.longitude,
            "bearing": vp.bearing,
            "speed_kmh": speed_kmh,
            "delay_seconds": delay_seconds,
            "current_status": vp.current_status,
            "next_stop_name": next_stop,
            "current_stop_name": None,
            "timestamp": timestamp,
            "feed_id": self.feed_config.feed_id,
            "operator_name": self.feed_config.operator_name,
        }
```

Import `VehiclePositionData` and `TripUpdateData` from `app.core.agents.tools.transit.client`.

**Method: `run()`**

The main polling loop. Runs until `_running` is set to False:

```python
    async def run(self, redis_client: Redis) -> None:
        """Run the polling loop for this feed."""
        feed_id = self.feed_config.feed_id
        interval = self.feed_config.poll_interval_seconds
        self._running = True
        logger.info("transit.poller.started", feed_id=feed_id, interval_seconds=interval)

        while self._running:
            start = time.monotonic()
            count = await self.poll_once(redis_client)
            duration_ms = round((time.monotonic() - start) * 1000)
            logger.info(
                "transit.poller.cycle_completed",
                feed_id=feed_id,
                vehicle_count=count,
                duration_ms=duration_ms,
            )
            await asyncio.sleep(interval)
```

**Top-level functions for lifecycle management:**

```python
_poller_tasks: list[asyncio.Task[None]] = []
_feed_pollers: list[FeedPoller] = []


async def start_pollers() -> None:
    """Start background poller tasks for all enabled feeds."""
    settings = get_settings()
    if not settings.poller_enabled:
        logger.info("transit.poller.disabled")
        return

    redis_client = await get_redis()
    feeds = [f for f in settings.transit_feeds if f.enabled]

    for feed_config in feeds:
        poller = FeedPoller(feed_config=feed_config, settings=settings)
        _feed_pollers.append(poller)
        task = asyncio.create_task(poller.run(redis_client))
        _poller_tasks.append(task)
        logger.info("transit.poller.feed_registered", feed_id=feed_config.feed_id)

    logger.info("transit.poller.all_started", feed_count=len(feeds))


async def stop_pollers() -> None:
    """Stop all poller tasks and close HTTP clients."""
    for poller in _feed_pollers:
        poller._running = False

    for task in _poller_tasks:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    for poller in _feed_pollers:
        await poller.close()

    _poller_tasks.clear()
    _feed_pollers.clear()
    logger.info("transit.poller.all_stopped")
```

Add pyright directive at top of file:
```python
# pyright: reportUnknownMemberType=false, reportMissingTypeStubs=false
```

**Per-task validation:**
- `uv run ruff format app/transit/poller.py`
- `uv run ruff check --fix app/transit/poller.py` passes
- `uv run mypy app/transit/poller.py` passes
- `uv run pyright app/transit/poller.py` passes

---

### Task 8: Create Redis reader utility
**File:** `app/transit/redis_reader.py` (create new)
**Action:** CREATE

This module provides functions to read vehicle positions from Redis. Used by both TransitService and agent tools.

```python
"""Read vehicle positions from Redis cache."""

import json

from redis.asyncio import Redis

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.redis import get_redis
from app.transit.schemas import VehiclePosition, VehiclePositionsResponse

logger = get_logger(__name__)
```

**Function: `get_vehicles_from_redis()`**

```python
async def get_vehicles_from_redis(
    *,
    feed_id: str | None = None,
    route_id: str | None = None,
) -> VehiclePositionsResponse:
    """Read vehicle positions from Redis, with optional feed and route filters.

    Args:
        feed_id: Filter by feed source (e.g., "riga"). None = all feeds.
        route_id: Filter by route (e.g., "22"). None = all routes.

    Returns:
        VehiclePositionsResponse with matching vehicles.
    """
    redis_client = await get_redis()
    settings = get_settings()
    vehicles: list[VehiclePosition] = []

    # Determine which feeds to read
    if feed_id:
        feed_ids = [feed_id]
    else:
        feed_ids = [f.feed_id for f in settings.transit_feeds if f.enabled]

    for fid in feed_ids:
        feed_vehicles = await _read_feed_vehicles(redis_client, fid)
        vehicles.extend(feed_vehicles)

    # Apply route filter
    if route_id is not None:
        vehicles = [v for v in vehicles if v.route_id == route_id]

    from datetime import UTC, datetime

    return VehiclePositionsResponse(
        count=len(vehicles),
        vehicles=vehicles,
        fetched_at=datetime.now(tz=UTC).isoformat(),
        feed_id=feed_id,
    )


async def _read_feed_vehicles(
    redis_client: Redis,  # type: ignore[type-arg]
    feed_id: str,
) -> list[VehiclePosition]:
    """Read all vehicles for a single feed from Redis."""
    feed_key = f"feed:{feed_id}:vehicles"
    vehicle_ids_raw = await redis_client.smembers(feed_key)
    vehicle_ids: list[str] = sorted(str(vid) for vid in vehicle_ids_raw)

    if not vehicle_ids:
        return []

    # Batch read with MGET
    keys = [f"vehicle:{feed_id}:{vid}" for vid in vehicle_ids]
    values = await redis_client.mget(keys)

    results: list[VehiclePosition] = []
    for val in values:
        if val is None:
            continue
        data: dict[str, object] = json.loads(str(val))
        results.append(VehiclePosition(**data))  # type: ignore[arg-type]

    return results
```

Add pyright directive at top of file:
```python
# pyright: reportUnknownMemberType=false, reportMissingTypeStubs=false
```

**Per-task validation:**
- `uv run ruff format app/transit/redis_reader.py`
- `uv run ruff check --fix app/transit/redis_reader.py` passes
- `uv run mypy app/transit/redis_reader.py` passes
- `uv run pyright app/transit/redis_reader.py` passes

---

### Task 9: Refactor TransitService to read from Redis
**File:** `app/transit/service.py` (modify existing)
**Action:** UPDATE

The TransitService needs two modes:
1. **Redis mode** (default when poller is enabled) - reads from Redis via `get_vehicles_from_redis()`
2. **Direct mode** (fallback when poller is disabled) - uses the existing on-demand GTFS-RT fetch

Read the existing file first. Then modify `get_vehicle_positions()` to check if the poller is enabled. If enabled, delegate to `get_vehicles_from_redis()`. If not, use the existing direct-fetch logic.

Update the method:

```python
async def get_vehicle_positions(
    self,
    route_id: str | None = None,
    feed_id: str | None = None,
) -> VehiclePositionsResponse:
    """Get vehicle positions, from Redis (if poller active) or direct fetch."""
    start = time.monotonic()
    logger.info(
        "transit.vehicles.fetch_started",
        route_filter=route_id,
        feed_filter=feed_id,
        source="redis" if self._settings.poller_enabled else "direct",
    )

    if self._settings.poller_enabled:
        from app.transit.redis_reader import get_vehicles_from_redis

        result = await get_vehicles_from_redis(feed_id=feed_id, route_id=route_id)
    else:
        # Legacy direct-fetch path (existing logic)
        result = await self._fetch_direct(route_id=route_id)

    duration_ms = round((time.monotonic() - start) * 1000)
    logger.info(
        "transit.vehicles.fetch_completed",
        count=result.count,
        duration_ms=duration_ms,
    )
    return result
```

Extract the existing direct-fetch logic into a private method `_fetch_direct()`:

```python
async def _fetch_direct(self, route_id: str | None = None) -> VehiclePositionsResponse:
    """Direct GTFS-RT fetch (legacy mode, used when poller is disabled)."""
    # ... move existing fetch + enrich logic here ...
```

Keep the existing `_enrich_vehicles()` module-level function unchanged (still used by direct mode).

Update `get_transit_service()` to accept the new settings fields gracefully (no changes needed if Settings is passed through).

**Per-task validation:**
- `uv run ruff format app/transit/service.py`
- `uv run ruff check --fix app/transit/service.py` passes
- `uv run mypy app/transit/service.py` passes

---

### Task 10: Update REST API route for multi-feed
**File:** `app/transit/routes.py` (modify existing)
**Action:** UPDATE

Add `feed_id` query parameter to the `get_vehicles` endpoint:

```python
@router.get("/vehicles", response_model=VehiclePositionsResponse)
@limiter.limit("30/minute")
async def get_vehicles(
    request: Request,
    route_id: str | None = None,
    feed_id: str | None = None,
) -> VehiclePositionsResponse:
    """Get live vehicle positions, optionally filtered by feed and/or route."""
    logger.info("transit.api.vehicles_requested", route_id=route_id, feed_id=feed_id)
    service = get_transit_service()
    return await service.get_vehicle_positions(route_id=route_id, feed_id=feed_id)
```

Add a new endpoint to list available feeds:

```python
@router.get("/feeds")
async def get_feeds() -> list[dict[str, object]]:
    """List configured transit feeds and their status."""
    settings = get_settings()
    return [
        {
            "feed_id": f.feed_id,
            "operator_name": f.operator_name,
            "enabled": f.enabled,
            "poll_interval_seconds": f.poll_interval_seconds,
        }
        for f in settings.transit_feeds
    ]
```

Add import: `from app.core.config import get_settings`

**Per-task validation:**
- `uv run ruff format app/transit/routes.py`
- `uv run ruff check --fix app/transit/routes.py` passes
- `uv run mypy app/transit/routes.py` passes

---

### Task 11: Wire poller and Redis into app lifespan
**File:** `app/main.py` (modify existing)
**Action:** UPDATE

Read the existing file first. In the lifespan context manager:

**Startup** (after existing initialization):
```python
from app.transit.poller import start_pollers
await start_pollers()
logger.info("transit.poller.lifecycle_started")
```

**Shutdown** (before existing cleanup):
```python
from app.transit.poller import stop_pollers
await stop_pollers()
logger.info("transit.poller.lifecycle_stopped")
```

Add Redis close to shutdown (after `close_transit_service()`):
```python
from app.core.redis import close_redis
await close_redis()
```

**Per-task validation:**
- `uv run ruff format app/main.py`
- `uv run ruff check --fix app/main.py` passes
- `uv run mypy app/main.py` passes

---

### Task 12: Update .env.example
**File:** `.env.example` (modify existing)
**Action:** UPDATE

Add these new environment variables with documentation comments:

```bash
# Redis (vehicle position cache)
REDIS_URL=redis://localhost:6379/0
REDIS_VEHICLE_TTL_SECONDS=120

# Multi-feed GTFS-RT (JSON array of feed configs)
# Leave empty to use legacy single-feed settings below
# Example: TRANSIT_FEEDS_JSON='[{"feed_id":"riga","operator_name":"Rigas Satiksme","rt_vehicle_positions_url":"https://saraksti.rigassatiksme.lv/vehicle_positions.pb","rt_trip_updates_url":"https://saraksti.rigassatiksme.lv/trip_updates.pb","static_url":"https://saraksti.rigassatiksme.lv/gtfs.zip","poll_interval_seconds":10}]'
TRANSIT_FEEDS_JSON=[]

# Background poller (set to false for testing or when using direct fetch)
POLLER_ENABLED=true
```

**Per-task validation:**
- File has no syntax errors

---

### Task 13: Create poller unit tests
**File:** `app/transit/tests/test_poller.py` (create new)
**Action:** CREATE

Test the `FeedPoller` class and `_enrich_vehicle()` method. Follow patterns from `app/transit/tests/test_service.py`.

```python
"""Tests for the GTFS-RT background poller."""

# pyright: reportUnknownMemberType=false, reportMissingTypeStubs=false, reportArgumentType=false

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.agents.tools.transit.client import (
    StopTimeUpdateData,
    TripUpdateData,
    VehiclePositionData,
)
from app.core.config import TransitFeedConfig
from app.transit.poller import FeedPoller
```

**Test 1: `test_enrich_vehicle_basic`**
Create a `FeedPoller` with a mock feed config and mock settings. Call `_enrich_vehicle()` with a simple `VehiclePositionData` and verify the returned dict has correct `feed_id`, `operator_name`, and resolved fields.

**Test 2: `test_enrich_vehicle_with_delay`**
Create a vehicle with a trip_id, add a matching `TripUpdateData` with `StopTimeUpdateData` containing a delay. Verify `delay_seconds` is extracted correctly.

**Test 3: `test_enrich_vehicle_speed_conversion`**
Pass a vehicle with `speed=10.0` (m/s). Verify result has `speed_kmh=36.0`.

**Test 4: `test_enrich_vehicle_no_route`**
Pass a vehicle with empty `route_id` and no `trip_id`. Verify `route_id=""` and `route_short_name=""`.

**Test 5: `test_poll_once_writes_to_redis`**
Mock the `GTFSRealtimeClient` methods to return test data. Mock the Redis pipeline. Call `poll_once()` and verify:
- `pipe.set()` called for each vehicle with correct key pattern `vehicle:{feed_id}:{vehicle_id}`
- `pipe.sadd()` called to track vehicle IDs
- `pipe.execute()` called once

**Test 6: `test_poll_once_handles_fetch_error`**
Mock `fetch_vehicle_positions()` to raise `TransitDataError`. Call `poll_once()` and verify it returns 0 (no vehicles written) without propagating the exception.

**Test 7: `test_start_stop_pollers`**
Patch `get_settings()` to return settings with one enabled feed and `poller_enabled=True`. Patch `get_redis()`. Call `start_pollers()` and verify task is created. Call `stop_pollers()` and verify cleanup.

All test functions must have `-> None` return annotation.
All helper functions must have return type annotations.

**Per-task validation:**
- `uv run ruff format app/transit/tests/test_poller.py`
- `uv run ruff check --fix app/transit/tests/test_poller.py` passes
- `uv run pytest app/transit/tests/test_poller.py -v` -- all tests pass

---

### Task 14: Create Redis reader unit tests
**File:** `app/transit/tests/test_redis_reader.py` (create new)
**Action:** CREATE

Test the `get_vehicles_from_redis()` function.

```python
"""Tests for Redis vehicle position reader."""

# pyright: reportUnknownMemberType=false, reportMissingTypeStubs=false, reportArgumentType=false

import json
from unittest.mock import AsyncMock, patch

import pytest

from app.transit.redis_reader import get_vehicles_from_redis
```

**Test 1: `test_get_vehicles_all_feeds`**
Mock `get_redis()` to return a mock Redis client. Mock `smembers()` to return vehicle IDs, `mget()` to return JSON vehicle data. Call with no filters. Verify all vehicles returned.

**Test 2: `test_get_vehicles_by_feed`**
Call with `feed_id="riga"`. Verify only the Riga feed's vehicles are read.

**Test 3: `test_get_vehicles_by_route`**
Call with `route_id="22"`. Mock returns vehicles with different route_ids. Verify only route 22 vehicles in response.

**Test 4: `test_get_vehicles_empty_redis`**
Mock `smembers()` to return empty set. Verify count=0 and empty vehicles list.

**Test 5: `test_get_vehicles_expired_keys`**
Mock `smembers()` to return IDs but `mget()` to return `None` for some (expired TTL). Verify those are skipped gracefully.

All test functions must have `-> None` return annotation.

**Per-task validation:**
- `uv run ruff format app/transit/tests/test_redis_reader.py`
- `uv run ruff check --fix app/transit/tests/test_redis_reader.py` passes
- `uv run pytest app/transit/tests/test_redis_reader.py -v` -- all tests pass

---

### Task 15: Create Redis client unit tests
**File:** `app/core/tests/test_redis.py` (create new)
**Action:** CREATE

Test the Redis client singleton lifecycle.

```python
"""Tests for Redis client singleton."""

# pyright: reportUnknownMemberType=false, reportMissingTypeStubs=false

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.redis import close_redis, get_redis
```

**Test 1: `test_get_redis_creates_singleton`**
Patch `Redis.from_url` to return an `AsyncMock`. Call `get_redis()` twice, verify `from_url` called only once. Clean up by calling `close_redis()`.

**Test 2: `test_close_redis_cleans_up`**
Get a Redis client, then close it. Verify `aclose()` was called.

**Test 3: `test_close_redis_handles_runtime_error`**
Get a Redis client where `aclose()` raises `RuntimeError`. Verify `close_redis()` doesn't propagate the error.

All test functions must have `-> None` return annotation.

**Per-task validation:**
- `uv run ruff format app/core/tests/test_redis.py`
- `uv run ruff check --fix app/core/tests/test_redis.py` passes
- `uv run pytest app/core/tests/test_redis.py -v` -- all tests pass

---

### Task 16: Update existing transit service tests
**File:** `app/transit/tests/test_service.py` (modify existing)
**Action:** UPDATE

Read the existing test file first. The service now has two modes (Redis and direct). Existing tests test the direct-fetch path. Update them:

1. Ensure existing tests still pass by setting `poller_enabled=False` on the mock settings object:
   ```python
   mock_settings.poller_enabled = False
   ```

2. Add new tests for the Redis path:

**Test: `test_get_vehicle_positions_redis_mode`**
Mock settings with `poller_enabled=True`. Patch `app.transit.service.get_vehicles_from_redis` to return a response. Call `get_vehicle_positions()` and verify it delegates to the Redis reader (not direct fetch).

**Test: `test_get_vehicle_positions_redis_with_feed_filter`**
Same as above but pass `feed_id="riga"`. Verify it's forwarded to the Redis reader.

All test functions must have `-> None` return annotation.

**Per-task validation:**
- `uv run ruff format app/transit/tests/test_service.py`
- `uv run ruff check --fix app/transit/tests/test_service.py` passes
- `uv run pytest app/transit/tests/test_service.py -v` -- all tests pass

---

### Task 17: Update existing transit route tests
**File:** `app/transit/tests/test_routes.py` (modify existing)
**Action:** UPDATE

Read the existing test file. Add tests for the new `feed_id` parameter and the `/feeds` endpoint:

**Test: `test_get_vehicles_with_feed_id`**
Call `GET /api/v1/transit/vehicles?feed_id=riga`. Verify the service is called with `feed_id="riga"`.

**Test: `test_get_vehicles_with_both_filters`**
Call `GET /api/v1/transit/vehicles?feed_id=riga&route_id=22`. Verify both params forwarded.

**Test: `test_get_feeds`**
Call `GET /api/v1/transit/feeds`. Patch `get_settings()` to return settings with two feeds. Verify response lists both feeds with correct fields.

All test functions must have `-> None` return annotation.

**Per-task validation:**
- `uv run ruff format app/transit/tests/test_routes.py`
- `uv run ruff check --fix app/transit/tests/test_routes.py` passes
- `uv run pytest app/transit/tests/test_routes.py -v` -- all tests pass

---

### Task 18: Update config tests
**File:** `app/core/tests/test_config.py` (modify if exists, create if not)
**Action:** CREATE or UPDATE

Test the new `transit_feeds` computed property:

**Test: `test_transit_feeds_from_json`**
Set `TRANSIT_FEEDS_JSON` env var with a valid JSON array. Verify `settings.transit_feeds` returns parsed `TransitFeedConfig` objects.

**Test: `test_transit_feeds_legacy_fallback`**
Set `TRANSIT_FEEDS_JSON=[]` (empty). Verify `settings.transit_feeds` returns one feed built from legacy single-feed URLs.

**Test: `test_transit_feed_config_defaults`**
Create a `TransitFeedConfig` with minimal fields. Verify `poll_interval_seconds=10` and `enabled=True`.

All test functions must have `-> None` return annotation.

**Per-task validation:**
- `uv run ruff format app/core/tests/test_config.py`
- `uv run ruff check --fix app/core/tests/test_config.py` passes
- `uv run pytest app/core/tests/test_config.py -v` -- all tests pass

---

### Task 19: Final integration — verify no regressions
**Action:** VALIDATE

Run the full validation pyramid:

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

**Level 3: Feature-specific tests**
```bash
uv run pytest app/transit/tests/ -v
uv run pytest app/core/tests/test_redis.py -v
uv run pytest app/core/tests/test_config.py -v
```

**Level 4: Full test suite**
```bash
uv run pytest -v -m "not integration"
```

All levels must pass with 0 errors.

---

## Logging Events

- `redis.connection_initialized` - Redis client created
- `redis.connection_closed` - Redis client shut down
- `redis.health_check_failed` - Redis ping failed (with error context)
- `transit.poller.started` - Feed poller started (feed_id, interval_seconds)
- `transit.poller.feed_registered` - Feed added to poller pool (feed_id)
- `transit.poller.all_started` - All pollers running (feed_count)
- `transit.poller.all_stopped` - All pollers stopped
- `transit.poller.cycle_completed` - One poll cycle finished (feed_id, vehicle_count, duration_ms)
- `transit.poller.fetch_failed` - Feed fetch error (feed_id, error, error_type)
- `transit.poller.disabled` - Poller not started (poller_enabled=False)
- `transit.poller.lifecycle_started` - Poller started in app lifespan
- `transit.poller.lifecycle_stopped` - Poller stopped in app lifespan

## Testing Strategy

### Unit Tests
**Location:** `app/transit/tests/test_poller.py`
- FeedPoller enrichment logic (4 tests)
- FeedPoller.poll_once() Redis write (2 tests)
- start/stop lifecycle (1 test)

**Location:** `app/transit/tests/test_redis_reader.py`
- Multi-feed reads (2 tests)
- Filtering by feed_id and route_id (2 tests)
- Edge cases: empty Redis, expired keys (2 tests)

**Location:** `app/core/tests/test_redis.py`
- Singleton lifecycle (3 tests)

**Location:** `app/core/tests/test_config.py`
- Feed config parsing (3 tests)

### Edge Cases
- Empty `TRANSIT_FEEDS_JSON` defaults to legacy single-feed
- Vehicle TTL expires between `smembers()` and `mget()` - gracefully skipped
- Feed fetch fails - logged, other feeds continue polling
- Redis unavailable at startup - poller logs error, service falls back to direct fetch
- Multiple pollers write to same feed_id concurrently - last write wins (acceptable)

## Acceptance Criteria

This feature is complete when:
- [ ] Redis service starts alongside the app in Docker Compose
- [ ] `/health/redis` returns healthy status
- [ ] Background poller writes vehicle positions to Redis every 10 seconds
- [ ] `GET /api/v1/transit/vehicles` reads from Redis (when poller enabled)
- [ ] `GET /api/v1/transit/vehicles?feed_id=riga` filters by feed
- [ ] `GET /api/v1/transit/feeds` lists configured feeds
- [ ] Legacy direct-fetch mode still works when `POLLER_ENABLED=false`
- [ ] All type checkers pass (mypy + pyright)
- [ ] All tests pass (unit + existing)
- [ ] Structured logging follows `domain.component.action_state` pattern
- [ ] No type suppressions added without justification
- [ ] No regressions in existing 354 unit tests

## Completion Checklist

Before marking this plan as fully executed:
- [ ] All 19 tasks completed in order
- [ ] Per-task validations passed
- [ ] Full validation pyramid passed (Levels 1-4)
- [ ] No deviations from plan (or deviations documented with reasons)
- [ ] Ready for `/commit`

## Final Validation (5-Level Pyramid)

Run each level in order -- every one must pass with 0 errors:

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
uv run pytest app/core/tests/test_redis.py -v
```

**Level 4: Full Test Suite (unit)**
```bash
uv run pytest -v -m "not integration"
```

**Level 5: Server Validation (if Docker running)**
```bash
curl -s http://localhost:8123/health/redis
curl -s http://localhost:8123/api/v1/transit/feeds
```

**Success definition:** Levels 1-4 exit code 0, all tests pass, zero errors or warnings. Level 5 optional.

## Dependencies

- Shared utilities used: `get_logger()`, `get_settings()`, `TimestampMixin` (not needed - no DB models)
- Core modules used: `app.core.config`, `app.core.logging`, `app.core.health`
- New dependencies: `uv add "redis[hiredis]>=5.2.0"`
- New env vars: `REDIS_URL`, `REDIS_VEHICLE_TTL_SECONDS`, `TRANSIT_FEEDS_JSON`, `POLLER_ENABLED`

## Known Pitfalls

The executing agent MUST follow these rules to avoid common errors:

1. **No `assert` in production code** - Ruff S101. Use `if x is not None:` conditionals.
2. **No `object` type hints** - Import actual types. Never `def f(data: object)`.
3. **Redis library typing** - redis-py has partial type stubs. Add `# pyright: reportUnknownMemberType=false, reportMissingTypeStubs=false` to files using Redis directly. Add mypy override for `redis.*`.
4. **Mock exceptions must match catch blocks** - If code catches `Exception`, mock with a specific subclass.
5. **No unused imports or variables** - Ruff F401/F841. Only import what you use.
6. **Test helpers need return types** - `-> MagicMock:`, `-> None:`, etc.
7. **No EN DASH** - Use `-` (HYPHEN-MINUS) not `--` (EN DASH) in strings.
8. **Singleton close must handle `RuntimeError`** - Event loop may be closed. Wrap `aclose()` in `try/except RuntimeError: pass`.
9. **`limiter.enabled = False` after imports** - In test files, all imports first, then module-level setup.
10. **No `type: ignore` in test files** - Use pyright file-level directives instead.
11. **`global` statements need `# noqa: PLW0603`** - Ruff flags global variable mutation.
12. **asyncio.Task type annotation** - Use `list[asyncio.Task[None]]` not `list[asyncio.Task]`.
13. **JSON parsing returns `Any`** - `json.loads()` returns `Any`. Cast appropriately.
14. **Redis `smembers()` returns `set[str]` with `decode_responses=True`** - But type stubs may say `set[bytes]`. Use `str()` wrapping if needed.

## Notes

- **Future: Redis pub/sub** - When WebSocket support is added, the poller should publish to a `transit:vehicle_updates` channel. The architecture supports this but it's out of scope for this plan.
- **Future: Multi-feed static caches** - Currently all feeds share one static cache (Riga). When new feeds are added, each feed will need its own static cache keyed by `static_url`. The `get_static_cache()` function should be updated to accept a URL parameter.
- **Future: Circuit breaker** - If a feed fails N consecutive polls, it should be temporarily disabled. Not implemented here but the `_running` flag supports this pattern.
- **Performance** - Redis MGET for 500 vehicles takes <1ms. The poller writes via pipeline (single round-trip). No performance concerns at current scale.
- **Backward compatibility** - Setting `POLLER_ENABLED=false` reverts to the existing on-demand fetch behavior. All existing tests continue to work.

## Pre-Implementation Checklist

The executing agent MUST verify before writing any code:
- [ ] Read all files listed in "Relevant Files" section
- [ ] Confirmed Redis is accessible (or Docker can start it)
- [ ] Understood the solution approach and why alternatives were rejected
- [ ] Clear on task execution order (infrastructure first, then poller, then service refactor)
- [ ] Validation commands are executable in this environment
