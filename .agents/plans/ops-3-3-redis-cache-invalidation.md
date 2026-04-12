# Plan: OPS-3.3 Redis Cache Invalidation Strategy

## Context

Redis caches vehicle positions (120s TTL) and other entities but there is no bulk invalidation when upstream data changes. A stop moving via a GTFS re-import leaves stale lat/lon cached for up to 120s, which breaks geofence detection and proximity search during migration windows. This feature adds explicit cache invalidation hooks wired into the repository layer so mutations auto-invalidate without per-call-site boilerplate.

## Security Context Assessment

**Active contexts:** CTX-INFRA (Redis infrastructure changes), CTX-INPUT (none — no new endpoints)

No new API endpoints are added. The `CacheInvalidator` is an internal utility called from existing repository methods. No auth/RBAC/file handling changes needed.

## Research Summary

### Current Redis Cache Key Patterns

| Entity | Key Pattern | TTL | Location |
|--------|-------------|-----|----------|
| Vehicle position | `vehicle:{feed_id}:{vehicle_id}` | 120s | `app/transit/poller.py:114` |
| Feed vehicle set | `feed:{feed_id}:vehicles` | 120s | `app/transit/poller.py:119` |
| Embedding cache | `emb:{provider}:{hash}` | 3600s | `app/knowledge/embedding.py` |
| Leader locks | `vtv:*_etl:leader` | config | `app/transit/traffic_etl.py` |

**Stops, routes, and geofences have no Redis caches yet.** The invalidation framework creates namespaced hooks so that when caches are added for these entities, invalidation is already wired. For vehicle positions, stale data after a DB mutation (e.g., vehicle reassignment) should be invalidated immediately rather than waiting for the next poller cycle.

### Key Files

| File | Role | Lines of interest |
|------|------|------------------|
| `app/core/redis.py` | Redis singleton (`get_redis()`) | 31-44 |
| `app/core/metrics.py` | `REDIS_CACHE_HITS/MISSES` counters (defined but unwired) | 33-34 |
| `app/core/config.py` | `redis_vehicle_ttl_seconds=120` | 94-95 |
| `app/stops/repository.py` | `create/update/delete/bulk_upsert` | 160-237 |
| `app/geofences/repository.py` | `create/update/delete` | 99-154 |
| `app/vehicles/repository.py` | `create/update/delete` | 133-171 |
| `app/schedules/repository.py` | `bulk_upsert_routes/stops` etc. | 793+ |
| `app/transit/redis_reader.py` | Vehicle position reads from Redis | 15-80 |
| `app/transit/poller.py` | Vehicle position writes to Redis | 84-136 |

### Existing Patterns to Follow

- **Redis access**: `redis = await get_redis()` — singleton, no DI needed
- **Metrics guard**: `if not get_settings().metrics_enabled: return` (see `metrics.py:67`)
- **Logging**: `logger.info("domain.component.action_state", key=value)`
- **Error handling**: `try/except` with warning log, never let cache errors break mutations
- **Pipeline**: `redis.pipeline()` returns sync `MagicMock` in tests (anti-pattern #35)

## Test Landscape

### Existing Fixtures

- `app/stops/tests/conftest.py`: `make_stop()`, `stop_factory`, `mock_db`
- `app/geofences/tests/conftest.py`: `mock_db`, `sample_geofence_create/update`
- `app/vehicles/tests/conftest.py`: `make_vehicle()`, `make_maintenance_record()`
- `app/transit/tests/conftest.py`: `make_eticket_line/txt/zip()`
- `app/core/tests/test_redis.py`: Redis singleton tests

### Redis Mock Patterns

```python
# Simple async operations
mock_redis = AsyncMock()
mock_redis.delete = AsyncMock(return_value=1)
mock_redis.scan = AsyncMock(return_value=(0, ["key1", "key2"]))

# Pipeline (anti-pattern #35)
mock_pipeline = MagicMock()
mock_pipeline.delete = MagicMock()
mock_pipeline.execute = AsyncMock(return_value=[1, 1])
mock_redis.pipeline = MagicMock(return_value=mock_pipeline)
```

## Type Check Baseline

| File | Pyright | Mypy |
|------|---------|------|
| `app/stops/repository.py` | 0 errors | 0 errors |
| `app/geofences/repository.py` | 0 errors | 0 errors |
| `app/vehicles/repository.py` | 0 errors | 0 errors |
| `app/core/redis.py` | 0 errors | 0 errors |
| `app/transit/redis_reader.py` | 0 errors | 0 errors |

All target files clean. Any new type errors = regressions from this feature.

## Files to Create/Modify

| Action | File | Purpose |
|--------|------|---------|
| CREATE | `app/core/cache/__init__.py` | Package init |
| CREATE | `app/core/cache/invalidation.py` | `CacheInvalidator` — namespaced key deletion + pattern scanning |
| UPDATE | `app/core/metrics.py` | Add `REDIS_CACHE_INVALIDATIONS` counter |
| UPDATE | `app/stops/repository.py` | Wire invalidation on create/update/delete/bulk_upsert |
| UPDATE | `app/geofences/repository.py` | Wire invalidation on create/update/delete |
| UPDATE | `app/schedules/service.py` | Wire invalidation after GTFS import completes |
| CREATE | `app/core/cache/tests/__init__.py` | Test package |
| CREATE | `app/core/cache/tests/test_invalidation.py` | 10 unit tests for CacheInvalidator |

## Implementation Steps

### Step 1: Create `app/core/cache/__init__.py`

CREATE `app/core/cache/__init__.py`:
```python
"""Cache management utilities."""
```

**Validation:** `uv run ruff check app/core/cache/__init__.py`

---

### Step 2: Create `CacheInvalidator` in `app/core/cache/invalidation.py`

CREATE `app/core/cache/invalidation.py`:

```python
# pyright: reportUnknownMemberType=false, reportMissingTypeStubs=false
"""Cache invalidation utilities for entity mutations.

Provides namespaced key deletion and pattern-based scanning to invalidate
stale Redis caches when upstream data changes in the database.
"""

from __future__ import annotations

import time

from redis.asyncio import Redis

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.metrics import REDIS_CACHE_INVALIDATIONS
from app.core.redis import get_redis

logger = get_logger(__name__)

# Namespace definitions — central registry of cache key prefixes
NAMESPACES: dict[str, str] = {
    "stops": "stops:*",
    "routes": "routes:*",
    "vehicles:position": "vehicle:*",
    "geofences:spatial": "geofences:spatial:*",
}


class CacheInvalidator:
    """Invalidate Redis cache keys by exact key or namespace pattern.

    Uses SCAN (never KEYS) to find matching keys, deleting in batches
    to avoid blocking Redis. All operations are fire-and-forget safe —
    cache invalidation failures are logged but never raise.
    """

    def __init__(self, redis: Redis | None = None) -> None:
        self._redis = redis

    async def _get_redis(self) -> Redis:
        if self._redis is not None:
            return self._redis
        return await get_redis()

    async def invalidate(self, namespace: str, *keys: str) -> int:
        """Delete exact cache keys within a namespace.

        Args:
            namespace: Cache namespace (e.g., "stops", "vehicles:position").
            *keys: Exact Redis key names to delete.

        Returns:
            Number of keys actually deleted.
        """
        if not keys:
            return 0
        start = time.monotonic()
        deleted = 0
        try:
            redis = await self._get_redis()
            result = await redis.delete(*keys)  # type: ignore[misc]
            deleted = int(result)
            duration_ms = (time.monotonic() - start) * 1000
            logger.info(
                "cache.invalidation.performed",
                namespace=namespace,
                keys_invalidated=deleted,
                key_count=len(keys),
                duration_ms=round(duration_ms, 2),
            )
            _record_metric(namespace, deleted)
        except Exception:
            logger.warning(
                "cache.invalidation.failed",
                namespace=namespace,
                key_count=len(keys),
                exc_info=True,
            )
        return deleted

    async def invalidate_pattern(
        self, pattern: str, *, namespace: str = "", batch_size: int = 100
    ) -> int:
        """Delete all keys matching a glob pattern using SCAN + DEL.

        Scans in batches to avoid blocking Redis for long periods.

        Args:
            pattern: Redis glob pattern (e.g., "stops:*").
            namespace: Namespace label for logging/metrics.
            batch_size: Keys per SCAN iteration.

        Returns:
            Total number of keys deleted.
        """
        start = time.monotonic()
        deleted = 0
        try:
            redis = await self._get_redis()
            cursor: int = 0
            while True:
                cursor, keys = await redis.scan(  # type: ignore[misc]
                    cursor, match=pattern, count=batch_size
                )
                if keys:
                    result = await redis.delete(*keys)  # type: ignore[misc]
                    deleted += int(result)
                if cursor == 0:
                    break
            duration_ms = (time.monotonic() - start) * 1000
            logger.info(
                "cache.invalidation.performed",
                namespace=namespace or pattern,
                keys_invalidated=deleted,
                pattern=pattern,
                duration_ms=round(duration_ms, 2),
            )
            _record_metric(namespace or pattern, deleted)
        except Exception:
            logger.warning(
                "cache.invalidation.failed",
                namespace=namespace or pattern,
                pattern=pattern,
                exc_info=True,
            )
        return deleted


# Module-level convenience functions for repository hooks

async def invalidate_stop_cache(stop_id: int | None = None) -> int:
    """Invalidate stop-related caches after a stop mutation.

    Args:
        stop_id: Specific stop ID, or None to invalidate all stops.

    Returns:
        Number of keys invalidated.
    """
    inv = CacheInvalidator()
    if stop_id is not None:
        return await inv.invalidate("stops", f"stops:{stop_id}")
    return await inv.invalidate_pattern("stops:*", namespace="stops")


async def invalidate_geofence_cache() -> int:
    """Invalidate all geofence spatial caches after a geofence mutation.

    Returns:
        Number of keys invalidated.
    """
    inv = CacheInvalidator()
    return await inv.invalidate_pattern(
        "geofences:spatial:*", namespace="geofences:spatial"
    )


async def invalidate_vehicle_position_cache(
    feed_id: str | None = None, vehicle_id: str | None = None
) -> int:
    """Invalidate vehicle position caches.

    Args:
        feed_id: Feed to invalidate, or None for all feeds.
        vehicle_id: Specific vehicle, or None for all in feed.

    Returns:
        Number of keys invalidated.
    """
    inv = CacheInvalidator()
    if feed_id and vehicle_id:
        return await inv.invalidate(
            "vehicles:position", f"vehicle:{feed_id}:{vehicle_id}"
        )
    if feed_id:
        return await inv.invalidate_pattern(
            f"vehicle:{feed_id}:*", namespace="vehicles:position"
        )
    return await inv.invalidate_pattern("vehicle:*", namespace="vehicles:position")


async def invalidate_route_cache() -> int:
    """Invalidate all route-related caches after a route mutation.

    Returns:
        Number of keys invalidated.
    """
    inv = CacheInvalidator()
    return await inv.invalidate_pattern("routes:*", namespace="routes")


def _record_metric(namespace: str, count: int) -> None:
    """Record cache invalidation in Prometheus counter."""
    if not get_settings().metrics_enabled:
        return
    REDIS_CACHE_INVALIDATIONS.labels(cache_name=namespace).inc(count)
```

**Validation:** `uv run ruff format app/core/cache/invalidation.py && uv run ruff check --fix app/core/cache/invalidation.py && uv run pyright app/core/cache/invalidation.py`

---

### Step 3: Add `REDIS_CACHE_INVALIDATIONS` counter to metrics

UPDATE `app/core/metrics.py` — add after line 34 (after `REDIS_CACHE_MISSES`):

```python
REDIS_CACHE_INVALIDATIONS = Counter(
    "vtv_redis_cache_invalidations_total",
    "Redis cache keys invalidated",
    ["cache_name"],
)
```

**Validation:** `uv run ruff check app/core/metrics.py && uv run pyright app/core/metrics.py`

---

### Step 4: Wire invalidation into `app/stops/repository.py`

UPDATE `app/stops/repository.py`:

Add import at top:
```python
from app.core.cache.invalidation import invalidate_stop_cache
```

After `await self.db.commit()` in `create()` (after line 171), add:
```python
        await invalidate_stop_cache(stop.id)
```

After `await self.db.commit()` in `update()` (after line 187), add:
```python
        await invalidate_stop_cache(stop.id)
```

After `await self.db.commit()` in `delete()` (after line 198), add:
```python
        await invalidate_stop_cache(stop.id)
```

**Do NOT add invalidation to `bulk_upsert()`** — it uses flush-only (no commit), and the caller (`ScheduleService.import_gtfs`) handles invalidation after commit to avoid double-invalidation.

**Validation:** `uv run ruff check app/stops/repository.py && uv run pyright app/stops/repository.py && uv run pytest app/stops/tests/ -x -q`

---

### Step 5: Wire invalidation into `app/geofences/repository.py`

UPDATE `app/geofences/repository.py`:

Add import at top:
```python
from app.core.cache.invalidation import invalidate_geofence_cache
```

After `await self.db.commit()` in `create()` (after line 122), add:
```python
        await invalidate_geofence_cache()
```

After `await self.db.commit()` in `update()` (after line 143), add:
```python
        await invalidate_geofence_cache()
```

After `await self.db.commit()` in `delete()` (after line 154), add:
```python
        await invalidate_geofence_cache()
```

**Validation:** `uv run ruff check app/geofences/repository.py && uv run pyright app/geofences/repository.py && uv run pytest app/geofences/tests/ -x -q`

---

### Step 6: Wire invalidation into `app/schedules/service.py` (GTFS import)

UPDATE `app/schedules/service.py`:

Add import at top:
```python
from app.core.cache.invalidation import invalidate_route_cache, invalidate_stop_cache
```

After `await self.db.commit()` at line 747 (after all bulk operations complete), add:
```python
            await invalidate_stop_cache()  # Clear all stop caches after GTFS import
            await invalidate_route_cache()  # Clear all route caches after GTFS import
```

Insert between line 747 (`await self.db.commit()`) and line 749 (`duration = time.monotonic() - start_time`). Note the 12-space indentation (inside `try` block).

**Validation:** `uv run ruff check app/schedules/service.py && uv run pyright app/schedules/service.py && uv run pytest app/schedules/tests/ -x -q`

---

### Step 7: Create test package and write 10 unit tests

CREATE `app/core/cache/tests/__init__.py`:
```python
"""Cache invalidation tests."""
```

CREATE `app/core/cache/tests/test_invalidation.py`:

10 tests covering:
1. **Exact-key invalidation** — `invalidate("stops", "stops:1")` calls `redis.delete("stops:1")` and returns count
2. **Pattern invalidation with batching (scan returns 2 pages)** — `invalidate_pattern("stops:*")` scans with cursor, deletes in batches, returns total
3. **Pattern invalidation with single page** — scan returns all keys in one page (cursor=0 immediately)
4. **Namespace isolation** — invalidating "stops:*" does NOT touch "geofences:*" keys
5. **Empty-result handling** — `invalidate()` with no keys returns 0; `invalidate_pattern` with no matches returns 0
6. **Repository hook: stop update auto-invalidates** — Mock Redis, call `invalidate_stop_cache(42)`, verify `redis.delete("stops:42")` called
7. **Repository hook: stop bulk invalidates all** — Mock Redis, call `invalidate_stop_cache()` (no ID), verify pattern scan
8. **Repository hook: geofence auto-invalidates** — Mock Redis, call `invalidate_geofence_cache()`, verify pattern scan on `geofences:spatial:*`
9. **Metric emission** — With `metrics_enabled=True`, verify `REDIS_CACHE_INVALIDATIONS` counter incremented
10. **Redis failure is swallowed** — `redis.delete` raises `ConnectionError`, function returns 0 and logs warning (never raises)

Mock patterns:
- `@patch("app.core.cache.invalidation.get_redis", new_callable=AsyncMock)`
- Redis mock: `AsyncMock()` with `.delete = AsyncMock(return_value=N)`, `.scan = AsyncMock(return_value=(0, [keys]))`
- Metrics: `@patch("app.core.cache.invalidation.get_settings")` with `metrics_enabled=True`

**Validation:** `uv run ruff check app/core/cache/tests/test_invalidation.py && uv run pyright app/core/cache/tests/test_invalidation.py && uv run pytest app/core/cache/tests/test_invalidation.py -x -v`

---

## Preflight Warnings

- `app/stops/repository.py`: `bulk_upsert` uses flush-only (no commit) — invalidation should go after the flush loop. The caller (ScheduleService) commits and also calls invalidation separately. To avoid double-invalidation in the GTFS import path, only add invalidation to `create/update/delete` in the repository (not `bulk_upsert`). The service-level hook in `schedules/service.py` handles bulk import.
- `app/schedules/service.py`: Insert invalidation calls after `await self.db.commit()` at line 747, before the duration logging at line 749.
- Redis `SCAN` cursor type: `redis-py` returns `tuple[int, list[str]]` but the async stub types may need `# type: ignore[misc]` (anti-pattern #34).

## Preflight Fixes Applied

| File | Line | Pattern | What Changed |
|------|------|---------|--------------|
| `app/stops/tests/test_repository.py` | 84,101,114 | `test_create/update/delete` call repo directly | Added `@patch("app.stops.repository.invalidate_stop_cache", new_callable=AsyncMock)` to each test — prevents Redis connection in unit tests |
| `app/schedules/tests/test_service.py` | 465 | `test_import_gtfs_success` calls `service.import_gtfs()` | Added `@patch` for both `invalidate_stop_cache` and `invalidate_route_cache` |
| `app/schedules/tests/test_service.py` | 517 | `test_import_merges_existing_data` calls `service.import_gtfs()` | Same patches as above |
| `app/schedules/tests/test_service.py` | 658 | `test_import_gtfs_failure_path` | Safe — exception before commit, invalidation never reached |

## Security Checklist

No new endpoints added. Internal utility only.

- [x] No new API endpoints → no auth/RBAC/rate-limiting needed
- [x] No user input handling → no input validation needed
- [x] Redis operations use `SCAN` (never `KEYS` or `FLUSHDB`)
- [x] Cache errors are caught and logged (never mask DB operation failures)
- [x] No credentials exposed in log events (namespace + key count only)

## Verification

- [ ] `make lint` passes (ruff format + ruff check)
- [ ] `make types` passes (mypy + pyright)
- [ ] `uv run pytest app/core/cache/tests/ -v` — all 10 tests pass
- [ ] `uv run pytest app/stops/tests/ -x -q` — existing stop tests still pass
- [ ] `uv run pytest app/geofences/tests/ -x -q` — existing geofence tests still pass
- [ ] `uv run pytest app/schedules/tests/ -x -q` — existing schedule tests still pass
- [ ] Pyright errors ≤ baseline (0 errors before)
- [ ] `make security-audit-quick` passes
- [ ] Never calls `FLUSHDB` — grep confirms: `rg "FLUSHDB\|flushdb\|flushall\|FLUSHALL" app/`
