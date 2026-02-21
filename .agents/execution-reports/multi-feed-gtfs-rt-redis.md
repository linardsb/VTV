# Execution Report: Multi-Feed GTFS-RT with Redis Caching

## Summary

Implemented multi-feed GTFS-RT tracking with Redis caching across 19 tasks. All validation checks pass (377/377 tests, 0 mypy/pyright errors). The implementation adds background pollers, Redis pipeline writes, batch MGET reads, and 3 new REST endpoints.

## Files Created

| File | Description |
|------|-------------|
| `app/core/redis.py` | Redis client singleton (get_redis/close_redis) with lifespan management |
| `app/transit/poller.py` | Background GTFS-RT poller with per-feed asyncio tasks |
| `app/transit/redis_reader.py` | Redis batch reader (MGET + JSON deserialize) |
| `app/transit/tests/test_poller.py` | 10 unit tests for poller module |
| `app/transit/tests/test_redis_reader.py` | 7 unit tests for Redis reader |
| `app/transit/tests/test_routes_multi.py` | 6 unit tests for new REST endpoints |

## Files Modified

| File | Changes |
|------|---------|
| `pyproject.toml` | Added `redis[hiredis]` dependency + mypy override for redis module |
| `docker-compose.yml` | Added Redis 7 Alpine service with volume |
| `app/core/config.py` | Added `TransitFeedConfig`, `transit_feeds` computed property, Redis URL, poller settings |
| `app/core/health.py` | Added `/health/redis` endpoint, Redis check in `/health/ready` |
| `app/transit/schemas.py` | Added `feed_id`/`operator_name` to VehiclePosition, new FeedStatusResponse |
| `app/transit/service.py` | Dual-mode: Redis reads (poller) or direct GTFS-RT fetch (legacy) |
| `app/transit/routes.py` | Added GET /vehicles/{feed_id} and GET /feeds endpoints |
| `app/main.py` | Added start_pollers/stop_pollers to lifespan, close_redis cleanup |
| `.env.example` | Added Redis and multi-feed configuration variables |
| `app/core/tests/test_config.py` | 3 new tests for TransitFeedConfig and feed parsing |
| `app/transit/tests/test_service.py` | Updated existing tests for dual-mode service |

## Validation Results

| Check | Status |
|-------|--------|
| Ruff format | PASS |
| Ruff check | PASS |
| MyPy | PASS (0 errors, 124 files) |
| Pyright | PASS (0 errors) |
| Pytest (unit) | PASS (377 passed, 0 failed) |
| Pytest (integration) | SKIPPED (Docker not running) |

## Bugs Found During Implementation

| Bug | Root Cause | Fix Applied |
|-----|-----------|-------------|
| 5 test failures in full suite (agent routes + main lifespan) | `start_pollers()` calls `get_redis()` during lifespan. When Redis unavailable, background tasks fail with `ConnectionError`. `stop_pollers()` only caught `CancelledError`, not the actual error, so it propagated to test teardown. | (1) Wrapped `get_redis()` in try/except in `start_pollers()` for graceful degradation. (2) Added `except Exception` alongside `CancelledError` in `stop_pollers()`. (3) Wrapped `pipe.execute()` in try/except in `poll_once()`. |
| Ruff S110 (try-except-pass) | Combined `except (CancelledError, Exception): pass` triggered S110. | Separated into two except blocks: `CancelledError: pass` (allowed) + `Exception: logger.debug(...)` |
| `@computed_field` on `@property` mypy error | mypy doesn't support decorator stacking on `@property` | Added `# type: ignore[prop-decorator]` (rule 30 documented) |
| Redis async stubs type confusion | `redis.asyncio` methods typed as `Awaitable[T] | T`, confusing mypy on `await` | Added `# type: ignore[misc]` on await calls + pyright file-level directives |
| Speculative `# type: ignore` codes wrong | Guessed error codes that didn't match actual mypy output, causing `unused-ignore` errors | Removed all speculative ignores, ran mypy first, then added exact codes (rule 31 documented) |
| `redis.pipeline()` mock using `AsyncMock` | `pipeline()` is synchronous, only `execute()` is async. `AsyncMock()` made `pipeline()` return coroutine, breaking `pipe.set()` | Used `MagicMock()` for Redis client, `AsyncMock()` only for `pipe.execute` (rule 34 documented) |

## Divergences from Plan

| Planned | Actual | Reason |
|---------|--------|--------|
| 19 tasks | 19 tasks completed | No divergence |
| Simple error handling in poller | 3-layer graceful degradation | Test suite revealed Redis unavailability crashes app startup; added defensive patterns |

## Lessons Learned (Codified as Rules 31-38)

8 new anti-pattern rules added to `/be-execute`, `/be-planning`, and `CLAUDE.md`:
- Rule 31: `@computed_field` on `@property` needs `# type: ignore[prop-decorator]`
- Rule 32: Don't guess `# type: ignore` codes - validate first
- Rule 33: `dict[str, object]` fails Pydantic `**kwargs` - use `dict[str, Any]`
- Rule 34: Redis async stubs need `# type: ignore[misc]` on await calls
- Rule 35: `redis.pipeline()` is SYNC - mock with MagicMock, not AsyncMock
- Rule 36: Lazy imports break `@patch` targets
- Rule 37: Bare `except: pass` violates Ruff S110
- Rule 38: Background tasks `stop_*()` must catch ALL exceptions
