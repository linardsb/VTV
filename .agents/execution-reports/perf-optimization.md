# Execution Report: Performance Optimization (5 Phases)

**Plan:** `.agents/plans/woolly-tumbling-stallman.md` (plan mode)
**Review:** `.agents/code-reviews/perf-optimization-review.md`
**Status:** Complete (all 12 review findings fixed)

## What Was Built

### Phase 1: Backend Parallelism
- **Redis-backed rate limiting** (`app/core/rate_limit.py`) — slowapi storage_uri from Redis with in-memory fallback. Rate limits now enforced across all Gunicorn workers.
- **Poller leader election** (`app/transit/poller.py`) — Redis SETNX lock with TTL refresh ensures only one worker runs GTFS-RT pollers. Fallback to single-worker behavior if Redis unavailable.
- **Multi-worker Gunicorn** (`Dockerfile`) — Production CMD uses `gunicorn -k uvicorn.workers.UvicornWorker -w 4`. Dev override in `docker-compose.yml` keeps single uvicorn with `--reload`.
- **Connection pool tuning** (`app/core/config.py`, `app/core/database.py`) — Configurable `db_pool_size` (default 3), `db_pool_max_overflow` (default 5), `db_pool_recycle` (default 3600). Safe for 4 workers x 8 = 32 max connections under PostgreSQL 100 limit.

### Phase 2: Auth Fast Path
- **Per-worker TTL cache** (`app/auth/dependencies.py`) — `cachetools.TTLCache[int, User]` (max 200 entries, 30s TTL). Skips DB lookup for recently-authenticated users. Redis revocation check always runs (never cached). Cache invalidation on user update/delete/deactivate via `invalidate_user_cache()`.
- **Test isolation** (`conftest.py`) — Autouse `_clear_auth_cache` fixture clears cache between tests.

### Phase 3: Nginx Optimizations
- **Upstream keepalive** (`nginx/nginx.conf`) — `keepalive 32` for FastAPI, `keepalive 16` for Next.js. All proxy locations use `proxy_http_version 1.1; proxy_set_header Connection ""`.
- **HTTP cache headers** — Semi-static endpoints (`/api/v1/stops`, `/api/v1/schedules/agencies`, `/api/v1/schedules/routes`, `/api/v1/transit/feeds`) get `Cache-Control: private, max-age=N` for GET only. POST/PATCH/DELETE get `no-store`. Auth and real-time endpoints remain `no-store`.
- **Brotli compression** (`nginx/Dockerfile`, `nginx/nginx.conf`) — Multi-stage Docker build compiles `ngx_brotli` module. Brotli (level 6) alongside gzip for 15-25% better compression on text. Browser negotiates via Accept-Encoding.

### Phase 4: Frontend SWR
- **SWR adoption** (`cms/apps/web/package.json`) — Added `swr` dependency.
- **SWR provider** (`cms/apps/web/src/components/swr-provider.tsx`) — Global `SWRConfig` with `swrFetcher` (wraps `authFetch`), 5s dedup, focus revalidation, 3 retries.
- **Hook migration** — `use-dashboard-metrics.ts`, `use-calendar-events.ts`, `use-vehicle-positions.ts` migrated from raw useEffect/setInterval to SWR with refreshInterval.
- **Session token caching** (`cms/apps/web/src/lib/auth-fetch.ts`) — Client-side JWT cached for 60s via module-level variables. Shared `getToken()` export used by both authFetch and SDK client.

### Phase 5: Build Optimizations
- **Font weight reduction** (`cms/apps/web/src/app/layout.tsx`) — Removed unused weight `300` from both fonts (~60KB savings).
- **Package import optimization** (`cms/apps/web/next.config.ts`) — Added `react-leaflet` to `optimizePackageImports` for better tree-shaking on map pages.

## Bugs Found During Implementation

| Bug | Root Cause | Fix Applied |
|-----|-----------|-------------|
| `test_list_stops` returning 401 | `app.dependency_overrides.clear()` in other test modules wiped module-level auth override | Converted all 8 test files to autouse pytest fixtures for auth override + replaced `.clear()` with targeted `.pop()` |
| 6 transit test failures | Same `dependency_overrides` test isolation issue | Same autouse fixture pattern |
| 3 events test failures | Events routes require auth (misleading comment said "Public read endpoints") + `.clear()` leaking | Added autouse fixture, removed redundant per-test auth sets |
| 2 GTFS export test failures | Same module-level override without fixture | Same fix pattern |
| nginx cache on mutations | Semi-static location blocks cached POST/PATCH/DELETE responses | Added `set $cache_header "no-store"` + `if ($request_method = GET)` pattern |
| Hardcoded API URL | `use-vehicle-positions.ts` had `apiBase = "http://localhost:8123"` | Changed to `process.env.NEXT_PUBLIC_AGENT_URL ?? "http://localhost:8123"` |
| Poller stop_pollers exception | `await _leader_refresh_task` only caught CancelledError, not prior failures | Added `except Exception:` handler after CancelledError |

## Validation Results

| Check | Result |
|-------|--------|
| Ruff format | PASS |
| Ruff check | PASS (0 issues) |
| MyPy | PASS (0 errors, 193 files) |
| Pyright | PASS (0 errors) |
| Pytest (unit) | PASS (693 passed) |
| Pytest (integration) | PASS (19 passed) |
| Security lint | PASS (0 violations) |
| Security conventions | PASS (105 passed) |
| SDK sync | IN SYNC |
| Server health | PASS |
| Frontend type-check | PASS |

## Files Changed

**Backend (new + modified):**
- `app/core/rate_limit.py` — Redis storage URI with fallback
- `app/core/config.py` — Added `poller_leader_lock_ttl`, `db_pool_size`, `db_pool_max_overflow`, `db_pool_recycle`
- `app/core/database.py` — Configurable pool settings
- `app/auth/dependencies.py` — TTLCache + invalidation
- `app/auth/service.py` — Cache invalidation calls
- `app/auth/tests/test_dependencies.py` — Cache test
- `app/transit/poller.py` — Leader election + exception handling
- `Dockerfile` — Gunicorn CMD
- `docker-compose.yml` — Dev override with single uvicorn
- `pyproject.toml` — Added cachetools, gunicorn
- `conftest.py` — Auth cache clear fixture
- 8 test files — Autouse fixture for test isolation

**Frontend (new + modified):**
- `cms/apps/web/src/lib/swr-fetcher.ts` — NEW
- `cms/apps/web/src/components/swr-provider.tsx` — NEW
- `cms/apps/web/src/lib/auth-fetch.ts` — Token caching
- `cms/apps/web/src/lib/sdk.ts` — Shared getToken()
- `cms/apps/web/src/hooks/use-dashboard-metrics.ts` — SWR migration
- `cms/apps/web/src/hooks/use-calendar-events.ts` — SWR migration
- `cms/apps/web/src/hooks/use-vehicle-positions.ts` — SWR migration + env var fix
- `cms/apps/web/src/app/layout.tsx` — Font weight reduction
- `cms/apps/web/next.config.ts` — react-leaflet optimize
- `cms/apps/web/package.json` — Added swr

**Infrastructure:**
- `nginx/nginx.conf` — Keepalive, cache headers, brotli
- `nginx/Dockerfile` — Brotli module build
