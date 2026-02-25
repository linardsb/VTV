# Review: Performance Optimization Implementation

**Summary:** Solid implementation across all 5 phases. Architecture decisions are sound — Redis fallbacks, leader election, SWR migration, and nginx caching are all well-executed. Two critical security findings (cache headers on mutating endpoints, hardcoded API URL), two high-priority reliability issues, and several medium improvements.

## Findings

| File:Line | Standard | Issue | Suggestion | Priority |
|-----------|----------|-------|------------|----------|
| `nginx/nginx.conf:189-201` | Security | Cache-Control on `/api/v1/stops` caches POST/PATCH/DELETE responses too — nginx `location` matches all methods, so `max-age=300` applies to mutating requests | Add `if ($request_method != GET) { add_header Cache-Control "no-store" always; }` or split into `location = /api/v1/stops` (GET list) vs catch-all. Same applies to `/api/v1/schedules/routes` and `/api/v1/schedules/agencies` | Critical |
| `cms/apps/web/src/hooks/use-vehicle-positions.ts:92` | Security | Hardcoded `apiBase = "http://localhost:8123"` as default — should use env var | Use `process.env.NEXT_PUBLIC_AGENT_URL ?? "http://localhost:8123"` consistent with `use-dashboard-metrics.ts:42` | Critical |
| `app/transit/poller.py:296-300` | Architecture | `stop_pollers()` only catches `CancelledError` on `_leader_refresh_task`, but if the task already failed (e.g., Redis disconnect), `await task` re-raises the original exception, not `CancelledError` | Add `except Exception:` handler after `except asyncio.CancelledError:` (CLAUDE.md pitfall #38) | High |
| `app/auth/dependencies.py:26` | Architecture | `TTLCache[int, User]` caches the SQLAlchemy ORM `User` object. If the ORM session that loaded it is closed/expired, accessing lazy-loaded attributes on the cached instance could raise `DetachedInstanceError` | Safe only because `expire_on_commit=False` is set in `database.py:33` and all accessed fields (`is_active`, `id`, `role`) are eagerly loaded columns. Add a code comment noting this dependency so future relationship additions don't break | High |
| `nginx/nginx.conf:189-246` | Architecture | Semi-static cache locations duplicate the full proxy directive block (7 lines each x 4 locations). DRY violation makes maintenance error-prone | Consider extracting common proxy directives into an `include` file or using nginx `map` for Cache-Control per path | Medium |
| `app/core/rate_limit.py:45-58` | Structured Logging | `_get_storage_uri()` exception handler catches bare `Exception` without logging the actual error details (no `error=str(e)`, no `error_type`) | Add `error=str(e), error_type=type(e).__name__` to the warning log for debuggability | Medium |
| `app/transit/poller.py:274` | Structured Logging | Leader refresh setup failure logged at `debug` level — should be `warning` since it affects operational reliability | Change `logger.debug` to `logger.warning` at line 275 | Medium |
| `cms/apps/web/src/hooks/use-dashboard-metrics.ts:46-47` | Architecture | `routesFetchedRef` + `setRouteData` pattern — `setRouteData` is called inside `fetchRouteCountsOnce` which runs in SWR's `onSuccess` callback. If `onSuccess` fires on every revalidation (every 30s), the ref check prevents re-fetching, but a stale route count is never refreshed | Consider fetching route counts with a separate SWR key (long `refreshInterval` like 300s) instead of the ref+callback pattern | Medium |
| `cms/apps/web/src/lib/auth-fetch.ts:19-21` | Security | Token cache uses module-level `let` variables — in SSR, these persist across all users on the server process. The `typeof window === "undefined"` guard at line 29 skips the cache server-side, so this is safe. But the cache variables exist in SSR scope | Add a comment noting the server-side safety of the `typeof window` guard to prevent future regressions | Low |
| `app/core/database.py:19-26` | Docstrings | Engine creation comment explains the math but the `pool_recycle` reason could be more specific | Minor — comment says "Prevent stale connections", could say "Recycle connections after 1h to avoid PostgreSQL idle timeouts" | Low |
| `nginx/Dockerfile:24-25` | Architecture | `brotli.conf` echo lines duplicate what's already in `nginx.conf` lines 5-6. Both the Dockerfile `RUN echo` and the config file `load_module` directives load the modules | Remove the `RUN echo` in Dockerfile (lines 24-25) since `nginx.conf` already has the `load_module` directives. Or remove from `nginx.conf` and rely on Dockerfile's `/etc/nginx/modules/brotli.conf` | Low |
| `cms/apps/web/src/components/swr-provider.tsx:6` | TypeScript | Props interface missing — uses inline `{ children: React.ReactNode }` | Extract to `interface SWRProviderProps { children: React.ReactNode }` for consistency with project patterns | Low |

## Security Checklist

- [x] Rate limiting enforced across all workers (Phase 1A — Redis storage with in-memory fallback)
- [x] No duplicate GTFS-RT polling (Phase 1B — Redis leader election with single-worker fallback)
- [x] Auth token revocation still immediate via Redis (Phase 2A — cache only bypasses DB, not Redis revocation check)
- [x] User deactivation cached max 30s (acceptable, matches JWT model)
- [x] Cache headers use `private` not `public` (Phase 3B — no shared cache leaks)
- [x] Auth endpoints keep `no-store` (Phase 3B — `/api/v1/auth/*` falls through to general `/api/` block)
- [x] SWR fetcher uses existing authFetch with JWT injection (Phase 4A)
- [x] Session token cache has TTL, never persisted to disk/localStorage (Phase 4B)
- [ ] **Semi-static cache locations also cache mutating requests** (Critical finding above)

## Stats
- Files reviewed: 20 (backend: 8, frontend: 7, infrastructure: 5)
- Issues: 12 total — 2 Critical, 2 High, 3 Medium, 5 Low

## Next step

To fix issues: `/code-review-fix .agents/code-reviews/perf-optimization-review.md`
