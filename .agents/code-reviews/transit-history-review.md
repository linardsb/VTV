# Review: `app/transit/` (Historical Position Storage)

**Summary:** Solid implementation of TimescaleDB-backed historical position storage with proper non-blocking poller integration, RBAC-protected endpoints, and parameterized queries. A few medium-priority issues around missing `TimestampMixin`, `Literal` types for constrained fields, and `type: ignore` proliferation in the poller dict-to-record conversion.

## Active Security Contexts

- **CTX-RBAC**: New REST endpoints — verified `require_role()` with explicit roles
- **CTX-INPUT**: New Query parameters — verified `max_length`, `pattern`, `ge`/`le` constraints
- **CTX-INFRA**: Docker modification (TimescaleDB) — verified no hardcoded credentials

## Findings

| File:Line | Issue | Suggestion | Priority |
|-----------|-------|------------|----------|
| `models.py:16` | Model does not inherit `TimestampMixin` — VTV convention requires all models inherit it. `VehiclePositionRecord` uses its own `recorded_at` but lacks `created_at`/`updated_at` audit columns. | Add `TimestampMixin` as a mixin. The `recorded_at` column serves a different purpose (GTFS-RT measurement time) than `created_at` (DB insert time), so both are valid. However, if the hypertable partitioning relies on `recorded_at` as the sole time column, adding `created_at`/`updated_at` may increase row size without benefit. **Decision needed**: either add `TimestampMixin` for convention compliance or document the exception. | Medium |
| `schemas.py:42,82` | `current_status` is `str` but should be `Literal["IN_TRANSIT_TO", "STOPPED_AT", "INCOMING_AT"]` per VTV convention for constrained fields. | Define `VehicleStopStatus = Literal["IN_TRANSIT_TO", "STOPPED_AT", "INCOMING_AT"]` and use it in both `VehiclePosition` and `HistoricalPosition`. | Medium |
| `poller.py:139-151` | 6 `type: ignore` comments for `float()`/`int()` conversions from `dict[str, object]`. This is a code smell — the enriched vehicle dict is untyped. | Consider defining a `TypedDict` (e.g., `EnrichedVehicle`) for the return type of `_enrich_vehicle()` to eliminate all type ignore comments. This would also make the dict-to-record conversion self-documenting. | Medium |
| `service.py:168-171` | 4 `type: ignore` comments in `get_delay_trend()` for the same `dict[str, object]` conversion. | The repository's `get_route_delay_trend()` returns `list[dict[str, object]]`. Consider returning a `TypedDict` or `NamedTuple` from the repository to avoid type ignores at the service layer. | Medium |
| `repository.py:35` | `batch_insert_positions` calls `db.commit()` directly. In VTV, the caller typically controls commit scope. If this function is called within a larger transaction, the explicit commit could cause issues. | For the current use case (poller writes), this is fine since each batch is an independent unit. Add a docstring note: "Commits immediately — not suitable for use within a larger transaction." | Low |
| `routes.py:85,137` | `vehicle_id` and `route_id` path parameters lack `max_length` or `pattern` constraints. [CTX-INPUT] | Add `Path(max_length=100, pattern=r"^[\w\-.:]+$")` to both parameters for input validation consistency with the `route_id` Query param on line 38. | Medium |
| `routes.py:126-127` | `fromisoformat()` can raise `ValueError` on malformed input. The regex pattern validates format but not semantic correctness (e.g., month 13). | The regex + `fromisoformat()` combination is actually robust — `fromisoformat` will reject invalid dates. The `ValueError` would bubble up as a 500. Consider wrapping in try/except to return a 422 with a descriptive message. | Low |
| `poller.py:157` | History write success logged at `logger.debug()` — this is useful operational data that may be lost in production (typically set to INFO+). | Consider `logger.info()` for production visibility, or leave as `debug` if write frequency (every 10s per feed) would be too noisy. | Low |
| `migration:87` | `remove_compression_policy` uses `if_not_exists` but should be `if_exists` for symmetry with the retention policy removal on line 86. | Change to `if_exists => true` to match. The current parameter name is actually valid TimescaleDB syntax but reads confusingly. | Low |
| `test_history_routes.py` | Tests override `get_current_user` but don't test unauthorized access (no role, wrong role). [CTX-RBAC] | Add a test verifying that a user without admin/dispatcher/editor role gets 403. This validates the RBAC configuration. | Medium |
| `service.py:160` | Lazy import `from app.core.database import get_db_context` inside `get_delay_trend()`. This is already imported at the top of `_fetch_direct()` (line 192). | Move the import to module level since it's used in two places. Lazy imports are for breaking circular deps — both call sites suggest no circular dep exists. | Low |
| `poller.py:117-120` | Redundant null check for `_db_session_factory` — already checked and assigned at line 67-70 in the same `poll_once()` call. | Remove the duplicate check (lines 117-120). The factory is guaranteed non-None after the initial fetch block. | Low |

## Stats

- **Files reviewed:** 10 (models, schemas, repository, service, routes, poller, migration, 3 test files)
- **Issues:** 12 total — 0 Critical, 0 High, 6 Medium, 6 Low

## Context-Specific Assessment

### CTX-RBAC
- Both new endpoints use `require_role("admin", "dispatcher", "editor")` — appropriate restriction for historical data access
- Existing `/vehicles` and `/feeds` endpoints use `get_current_user` (any authenticated user) — consistent with read-only real-time data
- Missing: test for unauthorized role rejection on new endpoints

### CTX-INPUT
- Time parameters have `max_length=30` and ISO 8601 regex patterns
- `limit` has `ge=1, le=10000` bounds
- `interval_minutes` has `ge=5, le=1440` bounds
- Gap: `vehicle_id` and `route_id` path params lack constraints

### CTX-INFRA
- TimescaleDB added via apt in Dockerfile — no hardcoded credentials
- `shared_preload_libraries` configured correctly
- Compression and retention policies use configurable intervals from settings

## Verdict

The implementation is production-ready with no critical or high-priority issues. The 6 medium items are all quality improvements (TypedDict for type safety, Literal types, path param validation, RBAC test coverage) that would strengthen the code but don't represent functional risks. The non-blocking poller pattern is correctly implemented — history write failures are caught and logged without disrupting the Redis write path.

**Next step:** `/code-review-fix .agents/code-reviews/transit-history-review.md`
