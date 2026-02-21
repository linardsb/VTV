# Code Review: app/transit/

**Reviewer:** Claude Opus 4.6
**Date:** 2026-02-21
**Scope:** All files in `app/transit/` including `tests/` subdirectory

## Summary

The transit module implements multi-feed GTFS-RT vehicle position tracking with dual-mode operation (Redis poller vs. direct fetch). Overall architecture is solid -- clean vertical slice structure, well-separated layers, comprehensive test coverage (25 tests across 4 test files), and proper structured logging. However, the review identified **1 critical bug**, **3 high-severity issues**, **5 medium issues**, and **4 low-severity items** requiring attention.

The most significant finding is a data fidelity bug where the poller path permanently drops `current_stop_name` resolution, meaning production (Redis mode) always returns `null` for this field while direct mode resolves it correctly.

**Files reviewed:**
- `app/transit/__init__.py`
- `app/transit/schemas.py`
- `app/transit/redis_reader.py`
- `app/transit/service.py`
- `app/transit/routes.py`
- `app/transit/poller.py`
- `app/transit/tests/test_poller.py`
- `app/transit/tests/test_redis_reader.py`
- `app/transit/tests/test_service.py`
- `app/transit/tests/test_routes.py`

---

## Findings

### Critical

#### C1. Poller always sets `current_stop_name` to `None` -- data loss in production mode

**File:** `/Users/Berzins/Desktop/VTV/app/transit/poller.py`, line 153
**Standard:** Code Quality (correctness)

In `FeedPoller._enrich_vehicle()`, the `current_stop_name` field is hardcoded to `None`:

```python
# poller.py line 153
"current_stop_name": None,
```

Meanwhile, the direct-fetch path in `service.py` correctly resolves it:

```python
# service.py line 158
current_stop_name = static.get_stop_name(v.stop_id) if v.stop_id else None
```

Since production runs with `TRANSIT_POLLER_ENABLED=true`, **all production responses will have `current_stop_name: null`** for every vehicle, even when the data is available in the static cache. The `vp.stop_id` is available in the poller context (used on line 138 for `next_stop`) but never used for `current_stop_name`.

**Fix:** Replace line 153 with:
```python
"current_stop_name": static.get_stop_name(vp.stop_id) if vp.stop_id else None,
```

---

### High

#### H1. Speed conversion treats `0.0 m/s` as `None` (falsy check on float)

**File:** `/Users/Berzins/Desktop/VTV/app/transit/service.py`, line 161
**File:** `/Users/Berzins/Desktop/VTV/app/transit/poller.py`, line 137
**Standard:** Code Quality (correctness)

Both enrichment paths use a truthiness check on `speed`:

```python
# service.py line 161
speed_kmh = round(v.speed * 3.6, 1) if v.speed else None

# poller.py line 137
speed_kmh = round(vp.speed * 3.6, 1) if vp.speed is not None else None
```

The service.py version (`if v.speed`) evaluates `False` when speed is `0.0`, which is a valid GTFS-RT speed value (vehicle is stationary). This would incorrectly return `speed_kmh: null` instead of `speed_kmh: 0.0` for stopped vehicles in direct-fetch mode.

Note: The poller (line 137) correctly uses `is not None`. Only `service.py` has the bug.

**Fix:** In `service.py` line 161, change to:
```python
speed_kmh = round(v.speed * 3.6, 1) if v.speed is not None else None
```

#### H2. Duplicated vehicle enrichment logic between `service.py` and `poller.py`

**File:** `/Users/Berzins/Desktop/VTV/app/transit/service.py`, lines 112-184
**File:** `/Users/Berzins/Desktop/VTV/app/transit/poller.py`, lines 103-157
**Standard:** Code Quality (DRY)

Vehicle enrichment (route resolution, delay extraction, speed conversion, timestamp formatting) is implemented twice with subtle differences:

| Aspect | `service.py` `_enrich_vehicles()` | `poller.py` `_enrich_vehicle()` |
|--------|-----------------------------------|--------------------------------|
| Returns | `list[VehiclePosition]` | `dict[str, object]` |
| `current_stop_name` | Resolved from static cache | Always `None` (bug C1) |
| Speed check | `if v.speed` (bug H1) | `if vp.speed is not None` (correct) |
| Delay logic | Uses `arrival_delay or departure_delay or 0` | Uses conditional `if arrival_delay != 0` |
| `feed_id`/`operator_name` | Not set (defaults to `""`) | Set from feed config |

This duplication is the root cause of bugs C1 and H1 -- the two implementations have diverged. Extracting a shared enrichment function would prevent future drift.

**Recommendation:** Extract a shared `enrich_vehicle()` function into a new `app/transit/enrichment.py` module, returning a dict that both service and poller consume.

#### H3. No error handling in `redis_reader.py` for Redis failures

**File:** `/Users/Berzins/Desktop/VTV/app/transit/redis_reader.py`, lines 15-80
**Standard:** Error Handling

The Redis reader has zero `try/except` blocks. If Redis becomes unavailable after startup (network partition, OOM eviction, etc.), the `get_vehicles_from_redis()` function will raise an unhandled `redis.ConnectionError` or `redis.TimeoutError`, which would propagate as an HTTP 500 to the frontend.

The poller correctly handles Redis write failures (poller.py lines 91-100), but the read path has no equivalent protection.

**Fix:** Wrap Redis operations in try/except and either:
- Return an empty `VehiclePositionsResponse` with a logged warning, or
- Raise `TransitDataError("Redis unavailable")` for a clean HTTP 503

---

### Medium

#### M1. Unused `redis_client` variable with lint workaround

**File:** `/Users/Berzins/Desktop/VTV/app/transit/redis_reader.py`, lines 29, 47
**Standard:** Code Quality (KISS)

```python
redis_client = await get_redis()  # line 29
# ... 18 lines later ...
_ = redis_client  # Referenced above via get_redis() singleton  # line 47
```

`get_vehicles_from_redis()` calls `get_redis()` on line 29 but never uses the returned client. The actual Redis operations happen inside `_read_feed_vehicles()`, which calls `get_redis()` again on line 61. The `_ = redis_client` assignment on line 47 is a lint suppression workaround for the unused variable.

**Fix:** Remove lines 29 and 47 entirely. The `get_redis()` singleton is correctly called inside `_read_feed_vehicles()`.

#### M2. No input validation on `feed_id` and `route_id` query parameters

**File:** `/Users/Berzins/Desktop/VTV/app/transit/routes.py`, lines 23-26
**Standard:** Security (input validation)

The `feed_id` parameter is used directly in Redis key construction (`f"feed:{feed_id}:vehicles"` and `f"vehicle:{feed_id}:{vid}"`). While Redis key injection is low-risk (read-only operations, no deletion), there is no length limit or character validation. An attacker could send arbitrarily long `feed_id` values.

```python
async def get_vehicles(
    request: Request,
    route_id: str | None = None,    # No validation
    feed_id: str | None = None,     # No validation, used in Redis keys
) -> VehiclePositionsResponse:
```

**Fix:** Add `Query` constraints:
```python
from fastapi import Query

feed_id: str | None = Query(None, max_length=50, pattern=r"^[a-z0-9_-]+$"),  # noqa: B008
route_id: str | None = Query(None, max_length=50),  # noqa: B008
```

#### M3. `get_feeds` endpoint missing rate limiting

**File:** `/Users/Berzins/Desktop/VTV/app/transit/routes.py`, lines 47-59
**Standard:** Security (rate limiting)

The `/feeds` endpoint has no `@limiter.limit()` decorator, unlike `/vehicles` which has `30/minute`. While `/feeds` is lighter (reads from config, not Redis), it should still have rate limiting to prevent abuse.

**Fix:** Add `@limiter.limit("30/minute")` and accept `request: Request` parameter.

#### M4. `get_feeds` endpoint returns untyped `list[dict[str, object]]`

**File:** `/Users/Berzins/Desktop/VTV/app/transit/routes.py`, line 48
**Standard:** Type Safety, Architecture

The `/feeds` endpoint returns a raw dict list instead of a Pydantic response model:

```python
async def get_feeds() -> list[dict[str, object]]:
```

This bypasses schema validation, has no `response_model` for OpenAPI docs, and uses `object` as the value type.

**Fix:** Create a `FeedStatusResponse` Pydantic model in `schemas.py` and set `response_model=list[FeedStatusResponse]`.

#### M5. Module-level mutable state for pollers without thread safety consideration

**File:** `/Users/Berzins/Desktop/VTV/app/transit/poller.py`, lines 179-180
**Standard:** Architecture

```python
_poller_tasks: list[asyncio.Task[None]] = []
_feed_pollers: list[FeedPoller] = []
```

These module-level lists are mutated by `start_pollers()` and `stop_pollers()`. While asyncio is single-threaded, if `start_pollers()` were called twice (e.g., during a hot reload or test), it would append duplicate pollers without clearing. The guard only checks `settings.poller_enabled`, not whether pollers are already running.

**Fix:** Add a guard at the top of `start_pollers()`:
```python
if _poller_tasks:
    logger.warning("transit.poller.already_running")
    return
```

---

### Low

#### L1. README documents incorrect Redis key prefix

**File:** `/Users/Berzins/Desktop/VTV/app/transit/README.md`, line 12
**Standard:** Code Quality (documentation accuracy)

README says:
```
transit:vehicles:{feed_id}:{vehicle_id}
```

Actual code uses:
```
vehicle:{feed_id}:{vehicle_id}
```

The feed set key is `feed:{feed_id}:vehicles` in code but not documented at all.

#### L2. README documents 60s TTL but config default is 120s

**File:** `/Users/Berzins/Desktop/VTV/app/transit/README.md`, lines 12, 41
**File:** `/Users/Berzins/Desktop/VTV/app/core/config.py`, line 81
**Standard:** Code Quality (documentation accuracy)

README states "60s TTL" in two places, but `redis_vehicle_ttl_seconds` defaults to `120` in config.py and tests.

#### L3. Delay extraction logic differs subtly between service and poller

**File:** `/Users/Berzins/Desktop/VTV/app/transit/service.py`, line 153
**File:** `/Users/Berzins/Desktop/VTV/app/transit/poller.py`, lines 131-135
**Standard:** Code Quality (consistency)

Service uses:
```python
delay_seconds = next_stu.arrival_delay or next_stu.departure_delay or 0
```

Poller uses:
```python
delay_seconds = (
    (first.arrival_delay or 0)
    if first.arrival_delay != 0
    else (first.departure_delay or 0)
)
```

The service version would return `departure_delay` when `arrival_delay` is `0` (a valid on-time value). The poller version handles this correctly by checking `!= 0` explicitly. This is another symptom of H2 (duplicated logic diverging).

#### L4. Singleton `TransitService` not resettable for testing

**File:** `/Users/Berzins/Desktop/VTV/app/transit/service.py`, lines 189-213
**Standard:** Testing

`get_transit_service()` creates a module-level singleton with no reset mechanism. Tests work around this by constructing `TransitService` directly, but the singleton's `httpx.AsyncClient` is never cleaned up between test runs. This is acceptable since tests don't call `get_transit_service()`, but a `_reset_transit_service()` helper (test-only) would be cleaner.

---

## Recommendations

### Priority 1 -- Fix immediately (blocks correctness)

1. **Fix C1** -- Resolve `current_stop_name` in poller's `_enrich_vehicle()`. One-line change.
2. **Fix H1** -- Change `if v.speed` to `if v.speed is not None` in `service.py`. One-line change.
3. **Fix H3** -- Add try/except around Redis reads in `redis_reader.py` with graceful degradation.

### Priority 2 -- Fix soon (improves robustness)

4. **Fix H2** -- Extract shared enrichment logic to eliminate divergence. This prevents bugs C1, H1, and L3 from recurring.
5. **Fix M2** -- Add `Query()` constraints on `feed_id` and `route_id` parameters.
6. **Fix M5** -- Add duplicate-start guard to `start_pollers()`.

### Priority 3 -- Fix when convenient (polish)

7. **Fix M1** -- Remove unused `redis_client` variable in `redis_reader.py`.
8. **Fix M3** -- Add rate limiting to `/feeds` endpoint.
9. **Fix M4** -- Create proper Pydantic response model for `/feeds`.
10. **Fix L1, L2** -- Update README with correct Redis key patterns and TTL values.

### Testing gaps to address

- No tests for Redis connection failure in `redis_reader.py` (related to H3)
- No tests for `start_pollers()` when pollers are already running (related to M5)
- No test for `speed=0.0` edge case (would catch H1)
- No test verifying `current_stop_name` is resolved in poller path (would catch C1)
- No tests for malformed JSON in Redis values (deserialization error path)
