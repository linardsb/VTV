# Code Review: app/core/

**Reviewer:** Senior Backend Engineer
**Date:** 2026-02-21
**Scope:** All files in `app/core/` (infrastructure + agents submodule)
**Files reviewed:** 65 Python files across core infrastructure, agent service, 10 agent tools, and ~201 tests

---

## Summary

The `app/core/` module provides the infrastructure foundation for the VTV transit operations platform: configuration, database, logging, middleware, rate limiting, Redis, health checks, exception handling, and the AI agent subsystem (10 tools across transit, Obsidian vault, and knowledge base domains).

**Overall assessment:** Solid infrastructure with good architectural decisions. The codebase demonstrates consistent patterns, thorough input validation, structured logging, and defensive error handling. The vertical slice architecture is well-implemented. Most issues are Medium/Low severity; there are no show-stopping Critical bugs, but there are a few High-severity items related to security, data integrity, and code duplication that should be addressed.

**Strengths:**
- Consistent structured logging with `domain.component.action_state` pattern throughout
- Excellent input validation and actionable error messages in all 10 agent tools
- Safety constraints well-enforced: confirm for deletes, dry_run for bulk, path traversal prevention
- Clean separation between tool functions, schemas, client wrappers, and dependencies
- Health check caching prevents connection pool exhaustion
- Comprehensive test coverage across all modules

---

## Findings

### Critical

No critical issues found.

### High

**H1. Database session lacks commit on success path**
- **File:** `/Users/Berzins/Desktop/VTV/app/core/database.py`, lines 42-58
- **Standard:** Error Handling
- **Details:** The `get_db()` dependency yields a session but never calls `await session.commit()`. While individual features may handle commits in their service/repository layers, the lack of any commit in the session lifecycle means that if any endpoint forgets to commit, changes are silently lost. The `finally` block only closes the session. Consider adding `await session.commit()` before the `finally` block (or at least document that consumers must commit explicitly).

**H2. Health check leaks Redis URL (potentially with password) to logs**
- **File:** `/Users/Berzins/Desktop/VTV/app/core/redis.py`, line 26
- **Standard:** Security
- **Details:** `logger.info("redis.connection_initialized", redis_url=settings.redis_url)` logs the full Redis URL, which may contain credentials (e.g., `redis://:password@host:6379/0`). The URL should be sanitized before logging, or only the host/port should be logged.

**H3. Redis health check detail leaks internal error information**
- **File:** `/Users/Berzins/Desktop/VTV/app/core/health.py`, line 127
- **Standard:** Security
- **Details:** `raise HTTPException(status_code=503, detail=f"Redis unavailable: {e}")` exposes internal exception messages to the client. In production, this could leak Redis connection details, hostnames, or configuration. The DB health check correctly uses a generic message ("Database is not accessible") but the Redis check does not.

**H4. `X-Forwarded-For` header spoofing in rate limiter**
- **File:** `/Users/Berzins/Desktop/VTV/app/core/rate_limit.py`, lines 24-26
- **Standard:** Security
- **Details:** `_get_client_ip()` trusts `X-Forwarded-For` unconditionally. An attacker can rotate this header value on every request to bypass rate limiting entirely. This should be mitigated by either: (a) only trusting `X-Forwarded-For` when behind a known reverse proxy (nginx is configured, so this is partially mitigated at the infrastructure level), or (b) using a configurable trusted proxy list. Since the project uses nginx as a reverse proxy, the actual risk is reduced, but the application-level code has no protection if accessed directly.

**H5. Significant code duplication across transit tools**
- **File:** `/Users/Berzins/Desktop/VTV/app/core/agents/tools/transit/get_route_schedule.py`, lines 35-66, 69-83, 86-102
- **File:** `/Users/Berzins/Desktop/VTV/app/core/agents/tools/transit/get_adherence_report.py`, lines 38-54, 57-71, 74-88, 91-106, 108-123
- **File:** `/Users/Berzins/Desktop/VTV/app/core/agents/tools/transit/check_driver_availability.py`, lines 34-50, 53-67
- **File:** `/Users/Berzins/Desktop/VTV/app/core/agents/tools/transit/query_bus_status.py`, lines 44-51
- **Standard:** Code Quality (DRY)
- **Details:** The following functions are duplicated across 3-4 files:
  - `_validate_date()` -- identical in `get_route_schedule.py`, `get_adherence_report.py`, `check_driver_availability.py`
  - `_classify_service_type()` -- identical in `get_route_schedule.py`, `get_adherence_report.py`, `check_driver_availability.py`
  - `_gtfs_time_to_minutes()` -- identical in `get_route_schedule.py`, `get_adherence_report.py`
  - `_gtfs_time_to_display()` -- identical in `get_route_schedule.py`, `get_adherence_report.py`
  - `_delay_description()` -- identical in `query_bus_status.py`, `get_adherence_report.py`
  - `_get_first_departure_minutes()` -- identical in `get_route_schedule.py`, `get_adherence_report.py`

  Per the project's three-feature rule, any utility used by 3+ features should be extracted to `app/shared/`. These 6 functions are used across 2-4 tool files and should be consolidated into a shared transit utilities module (e.g., `app/core/agents/tools/transit/utils.py`).

**H6. Module-level singletons use mutable globals without thread safety**
- **File:** `/Users/Berzins/Desktop/VTV/app/core/redis.py`, lines 11, 16-17 (`global _redis_client`)
- **File:** `/Users/Berzins/Desktop/VTV/app/core/agents/service.py`, lines 150, 161-162 (`global _agent_service`)
- **File:** `/Users/Berzins/Desktop/VTV/app/core/agents/quota.py`, lines 88, 97-98 (`global _quota_tracker`)
- **File:** `/Users/Berzins/Desktop/VTV/app/core/agents/tools/transit/static_cache.py`, lines 408, 424 (`global _static_cache`)
- **File:** `/Users/Berzins/Desktop/VTV/app/core/health.py`, lines 19-26 (`global _db_health_cache, ...`)
- **Standard:** Performance / Architecture
- **Details:** Multiple module-level singletons use `global` with `None` initialization. While this is safe in single-process async (uvicorn with one worker), it becomes a race condition with multiple workers or if `--workers > 1`. The quota tracker comment acknowledges "no cross-process sharing" which is correct, but the in-memory quota tracker means quotas reset on restart and are not shared across workers. This should be documented as a known limitation, and a Redis-backed quota tracker should be considered for production multi-worker deployments.

### Medium

**M1. `database.py` evaluates settings at module import time**
- **File:** `/Users/Berzins/Desktop/VTV/app/core/database.py`, lines 14-22
- **Standard:** Architecture
- **Details:** `settings = get_settings()` and `engine = create_async_engine(...)` execute at import time. This means importing `database.py` requires a valid `DATABASE_URL` environment variable, which can break test isolation and makes it harder to test without a database. The engine creation should be deferred (e.g., a factory function or lazy property).

**M2. `echo=True` in development leaks SQL statements to logs**
- **File:** `/Users/Berzins/Desktop/VTV/app/core/database.py`, line 22
- **Standard:** Security / Logging
- **Details:** `echo=settings.environment == "development"` logs all SQL statements including potentially sensitive query parameters when running in development mode. While this is useful for debugging, it should be a separate explicit setting (e.g., `DATABASE_ECHO=false`) rather than tied to the environment name, to prevent accidental production logging if someone sets `environment=development`.

**M3. `BodySizeLimitMiddleware` path matching is fragile**
- **File:** `/Users/Berzins/Desktop/VTV/app/core/middleware.py`, lines 55-57
- **Standard:** Security
- **Details:** `if path.endswith("/import") or "/knowledge" in path:` uses simple string matching which could be bypassed (e.g., `/api/not-real/knowledge-bypass` would match). The path checks should use more precise matching, such as checking for specific route prefixes like `path.startswith("/api/schedules/") and path.endswith("/import")`.

**M4. Exception handler logs errors then raises HTTPException (double-logging)**
- **File:** `/Users/Berzins/Desktop/VTV/app/core/health.py`, lines 85-91
- **Standard:** Logging
- **Details:** In `database_health_check()`, `logger.error(...)` is called, then `HTTPException` is raised. The `RequestLoggingMiddleware` will also log the error response. This results in the same error being logged twice -- once by the endpoint and once by the middleware. This is a minor noise issue in log aggregation.

**M5. Health check global state not reset between tests**
- **File:** `/Users/Berzins/Desktop/VTV/app/core/health.py`, lines 19-26
- **Standard:** Testing
- **Details:** The `_redis_health_cache` and `_redis_health_cache_time` globals are not reset in the test fixture `_clear_db_health_cache`. The fixture only clears `_db_health_cache` and `_db_health_cache_time`. The `health_redis` endpoint has its own cache that could leak between tests.

**M6. `config.py` `transit_feeds` computed field calls `json.loads` on every access**
- **File:** `/Users/Berzins/Desktop/VTV/app/core/config.py`, lines 87-104
- **Standard:** Performance
- **Details:** `transit_feeds` is a `@computed_field @property` that calls `json.loads(self.transit_feeds_json)` and constructs `TransitFeedConfig` objects on every access. While `Settings` is cached via `@lru_cache`, each access to `settings.transit_feeds` recomputes the property. Consider caching the result in a private attribute or using `@functools.cached_property`.

**M7. `_VALID_ACTIONS` validation pattern is not type-safe**
- **File:** Multiple tool files (all 10 tools)
- **Standard:** Type Safety
- **Details:** Every tool uses `action: str` and validates at runtime against a tuple of valid strings. Using `Literal["status", "route_overview", "stop_departures"]` would provide compile-time type safety. However, since these are LLM-facing tool parameters, the current approach with helpful error messages is arguably more practical for agent interaction. Still, the internal validation could benefit from an enum or Literal type.

**M8. `ObsidianClient.search()` constructs `params` dict but never uses it**
- **File:** `/Users/Berzins/Desktop/VTV/app/core/agents/tools/obsidian/client.py`, lines 71-77
- **Standard:** Code Quality
- **Details:** The `params` dict is populated with `contextLength` when `path` is provided, but is never passed to the HTTP request (`self._http_client.post(url, content=query, ...)`). The `params` parameter is missing from the `post()` call. This means the `path` parameter to the `search()` method has no effect on the search scope.

**M9. Obsidian `_handle_recent` and `_handle_glob` only search top-level directory**
- **File:** `/Users/Berzins/Desktop/VTV/app/core/agents/tools/obsidian/query_vault.py`, lines 335-381
- **Standard:** Code Quality
- **Details:** Both `_handle_recent()` and `_handle_glob()` call `client.list_directory("/")` which only returns top-level entries. Notes in subfolders will not be found. This is a functional limitation that should be documented or addressed with recursive listing.

**M10. `_handle_move` in `manage_notes.py` is not atomic**
- **File:** `/Users/Berzins/Desktop/VTV/app/core/agents/tools/obsidian/manage_notes.py`, lines 411-427
- **Standard:** Error Handling
- **Details:** The move operation reads the note, creates it at the new path, then deletes the original. If the delete fails after the create succeeds, the note exists in both locations. If the create fails, no data is lost. This is acceptable given the Obsidian API limitations, but the non-atomic nature should be documented.

**M11. `search_knowledge_base` creates a new `AsyncSessionLocal` outside DI**
- **File:** `/Users/Berzins/Desktop/VTV/app/core/agents/tools/knowledge/search_knowledge.py`, lines 87-88
- **Standard:** Architecture
- **Details:** The knowledge base tool creates its own database session via `async with AsyncSessionLocal() as db:` rather than using the FastAPI dependency injection system (`get_db()`). This bypasses the standard session lifecycle and any middleware that wraps the DI-provided session. Since tool functions run inside the agent (not as direct route handlers), this is somewhat justified, but it introduces a second session management pattern.

### Low

**L1. `TransitDeps` alias retained for backward compatibility**
- **File:** `/Users/Berzins/Desktop/VTV/app/core/agents/tools/transit/deps.py`, lines 31, 63
- **Standard:** Code Quality
- **Details:** `TransitDeps = UnifiedDeps` and `create_transit_deps = create_unified_deps` are retained as backward-compatibility aliases. Multiple tool files still import `TransitDeps` instead of `UnifiedDeps`. The migration should be completed and the aliases removed.

**L2. `_RIGA_TZ` constant duplicated across 3 files**
- **File:** `/Users/Berzins/Desktop/VTV/app/core/agents/tools/transit/get_route_schedule.py`, line 32
- **File:** `/Users/Berzins/Desktop/VTV/app/core/agents/tools/transit/get_adherence_report.py`, line 32
- **File:** `/Users/Berzins/Desktop/VTV/app/core/agents/tools/transit/check_driver_availability.py`, line 30
- **Standard:** Code Quality (DRY)
- **Details:** The timezone constant `_RIGA_TZ = ZoneInfo("Europe/Riga")` is defined in 3 separate files. Should be extracted to a shared location.

**L3. `_ON_TIME_THRESHOLD` defined in two files with same value**
- **File:** `/Users/Berzins/Desktop/VTV/app/core/agents/tools/transit/query_bus_status.py`, line 37
- **File:** `/Users/Berzins/Desktop/VTV/app/core/agents/tools/transit/get_adherence_report.py`, line 33
- **Standard:** Code Quality (DRY)
- **Details:** Both files define `_ON_TIME_THRESHOLD = 300`. Should be a shared constant.

**L4. `ValidationError` name conflicts with Pydantic's `ValidationError`**
- **File:** `/Users/Berzins/Desktop/VTV/app/core/exceptions.py`, line 26
- **Standard:** Code Quality (naming)
- **Details:** The custom `ValidationError` class shares its name with `pydantic.ValidationError`, which is used throughout the codebase for request validation. This can cause confusion when reading error logs or when both are needed in the same module. Consider renaming to `DomainValidationError` or `BusinessValidationError`.

**L5. `get_logger` return type is `WrappedLogger` which lacks specific method signatures**
- **File:** `/Users/Berzins/Desktop/VTV/app/core/logging.py`, line 109
- **Standard:** Type Safety
- **Details:** `WrappedLogger` from structlog does not provide typed method signatures for `.info()`, `.error()`, etc. This means all log calls are untyped. This is a known structlog limitation and not directly fixable, but worth noting.

**L6. Test file `test_health.py` does not test Redis health endpoint**
- **File:** `/Users/Berzins/Desktop/VTV/app/core/tests/test_health.py`
- **Standard:** Testing
- **Details:** The `health_redis` endpoint is not covered by any test in the health test file. The Redis health check with caching behavior should have dedicated tests.

**L7. `driver_data.py` mock data hardcoded for Riga-specific bus routes**
- **File:** `/Users/Berzins/Desktop/VTV/app/core/agents/tools/transit/driver_data.py`
- **Standard:** Architecture
- **Details:** Mock driver data is hardcoded with Riga-specific route IDs (`bus_1`, `bus_22`, etc.). The file is clearly documented as a Phase 1 placeholder to be replaced by a CMS API client. The async interface matches the planned real client. No action needed, but the TODO should be tracked.

**L8. `Content-Length` header parsing does not handle malformed values**
- **File:** `/Users/Berzins/Desktop/VTV/app/core/middleware.py`, line 62
- **Standard:** Error Handling
- **Details:** `int(content_length)` will raise `ValueError` if the header contains a non-numeric value. While this would be caught by the framework, wrapping it in a `try/except ValueError` would be more defensive.

**L9. `FallbackModel` logic in `get_agent_model` is unreachable for anthropic/ollama**
- **File:** `/Users/Berzins/Desktop/VTV/app/core/agents/config.py`, lines 67-82
- **Standard:** Code Quality
- **Details:** When `provider` is `"anthropic"` or `"ollama"`, the function returns early before reaching the `FallbackModel` logic. This means fallback is only available for generic string-based providers. The test `test_get_agent_model_with_fallback` documents this behavior, but it may not be the intended design. If anthropic+ollama fallback is desired, the logic needs restructuring.

**L10. `close_redis()` silently swallows `RuntimeError` with bare pass**
- **File:** `/Users/Berzins/Desktop/VTV/app/core/redis.py`, lines 36-37
- **Standard:** Logging
- **Details:** `except RuntimeError: pass` follows the project's documented pattern (rule 16), but a `logger.debug("redis.close_skipped_closed_loop")` would improve observability without adding noise.

---

## Recommendations

### Priority 1 (High-value, low-effort)
1. **Sanitize Redis URL in logs** (H2): Replace `redis_url=settings.redis_url` with `redis_host=parsed_url.host` to avoid credential leakage.
2. **Fix Redis health check error detail** (H3): Use a generic error message like the DB health check does.
3. **Fix `ObsidianClient.search()` unused `params`** (M8): Pass `params=params` to the POST request or remove the dead code.
4. **Reset Redis health cache in test fixture** (M5): Add `health_mod._redis_health_cache = None` and `health_mod._redis_health_cache_time = 0.0` to `_clear_db_health_cache`.

### Priority 2 (Important, moderate effort)
5. **Extract duplicated transit utility functions** (H5): Create `app/core/agents/tools/transit/utils.py` with `_validate_date()`, `_classify_service_type()`, `_gtfs_time_to_minutes()`, `_gtfs_time_to_display()`, `_delay_description()`, `_get_first_departure_minutes()`, `_RIGA_TZ`, and `_ON_TIME_THRESHOLD`.
6. **Complete `TransitDeps` to `UnifiedDeps` migration** (L1): Update all tool imports and remove aliases.
7. **Add `health_redis` test coverage** (L6): Test both success and failure paths with cache behavior.

### Priority 3 (Good to have, higher effort)
8. **Defer database engine creation** (M1): Move `engine` creation to a lazy factory to improve test isolation.
9. **Add `Content-Length` parsing safety** (L8): Wrap `int(content_length)` in try/except.
10. **Document singleton limitations** (H6): Add a note about multi-worker behavior and consider Redis-backed quota for production.
11. **Tighten body size path matching** (M3): Use route-prefix-based checks instead of substring matching.

### Architecture Notes
- The vertical slice architecture is well-maintained. Each tool owns its full vertical: schemas, client, business logic, and tests.
- The dependency injection via `UnifiedDeps` dataclass is clean and testable.
- The OpenAI-compatible API format is a good design choice for client interoperability.
- The system prompt in `agent.py` is comprehensive and well-structured for Latvian/English bilingual support.
- The three-tier safety model (confirm for deletes, dry_run for bulk, path sandboxing) is consistently applied across all Obsidian tools.
