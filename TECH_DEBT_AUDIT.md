# Tech-Debt Audit — `app/transit/` (Stage 1.1 pilot)

> Status: **Phase 1 + Phase 2 dimension sweep complete. 3 quick wins shipped (T-001/T-002/T-003). 39 new entries (T-004…T-042) appended; Task 27 spot-check reclassified T-016/T-023/T-024/T-042 as NOT MATERIAL, leaving 35 net findings.**
> Audit scope: `app/transit/` (32 `.py` files, 6646 LOC, 27 test modules).
> Excluded: `app/core/agents/` (Stage 5), `cms/` (frontend), agent surface dim 10, frontend dims 12–13.
> Plan: `.agents/plans/td-1.1-transit-pilot-audit.md`. Protocol: `docs/PLANNING/Tech-Debt-Audit-Plan.md` §A.

## Shipped (Stage 1.3 quick wins)

| ID | Title | Severity | Effort | Status |
|----|-------|----------|--------|--------|
| T-001 | `routes.py` 8× raw `HTTPException` → `AppError` subclasses | Medium | M | RESOLVED |
| T-002 | `phone_identifier` unique constraint vs soft-delete (latent 500) | High | S | RESOLVED |
| T-003 | CKAN intercity placeholder resource IDs gated behind off-by-default flag | Critical | S | RESOLVED |

See Section 3 below for the full finding entries.

---

## 1. Executive Summary

Ranked by impact, each bullet references a finding ID. Three RESOLVED quick wins
are excluded from the active list.

- **High: `vehicle_positions.latitude/longitude` are plain `Float` columns with
  no PostGIS Geometry type and no GIST index** (T-035, `models.py:69-70`). Every
  spatial query against the realtime hypertable falls back to seq scan; blocks
  proximity-filtered history queries that don't exist yet *because* the column
  shape would make them unusable. Effort: M.
- **High: `traffic_counts` and `traffic_accidents` are not hypertables, no
  retention, no compression** (T-036,
  `alembic/versions/k4l5m6n7o8p9_weather_traffic_tables.py:109-170`). Both
  tables are time-series (`period_start/period_end`, `detected_at`) but only
  `weather_observations` got hypertable + policies in the same migration. Both
  grow unbounded. Effort: S.
- **High: file-level `pyright: reportUnknownArgumentType=false,
  reportUnknownVariableType=false` on `feed_client.py:1`** (T-008). The widest
  type-debt suppression in the slice sits on the boundary parser that is *the*
  trust boundary for non-GTFS-RT feeds. Real type errors are invisible.
  Effort: S (tighten to per-line ignores; catalogue remaining errors).
- **High: `poller.py:235-243` publishes the entire `enriched_vehicles` list as
  a single Redis Pub/Sub message every poll** (T-017). For Riga (~250 vehicles
  on a 10s tick) that's a multi-hundred-KB broadcast on every tick, fanned out
  to every connected WebSocket client. Bandwidth + parse cost scale with
  product of feeds × vehicles × clients. Effort: M.
- **High: WebSocket auth via `?token=JWT` query parameter at
  `ws_routes.py:60-87`** (T-028). Tokens land in nginx + uvicorn access logs by
  default; URL is also visible to browser history, referer, and shared link
  copy-paste. Either accept tokens via `Sec-WebSocket-Protocol` or scrub from
  access logs. Effort: S.
- **Medium: 14 sites in `app/transit/` use `datetime.now(tz=UTC)` instead of
  `app.shared.models.utcnow()`** (T-006). Convention exists, isn't enforced;
  drifts every PR. Effort: S, mechanical.
- **Medium: README API table lists 5 endpoints; actual is 12 REST + 1 WS = 13**
  (T-031, `app/transit/README.md:158-167`; same miscount in `CLAUDE.md`).
  Public-facing doc + repo-root architecture doc both stale. Effort: S.
- **Medium: `journey_planner.py` parses raw OTP JSON as `dict[str, Any]` 8+
  sites with no Pydantic schema** (T-009). Trust-boundary parser silently
  accepts shape drift from the upstream OTP server. Effort: M.
- **Medium: 5 disjoint subsystems co-tenant under `app/transit/`** (see
  Section 2 mental model + T-004). VSA boundary blurred; share/phone/plan/ETL
  writes bypass service+repository split. Tagged `→ DEEPEN` for
  Architecture-Deepening (Stage 1.2). Effort: L.

---

## 2. Architectural Mental Model

`app/transit/` is presented in `CLAUDE.md` as a single vertical slice for "Multi-feed GTFS-RT tracking," but in practice it is the load-bearing spine for **five distinct subsystems** sharing one directory: (a) the **GTFS-RT realtime spine** — `poller.py` (leader-elected per-feed asyncio pollers with `CircuitBreaker`), `feed_client.py` (pluggable `FeedClient` Protocol with `DaugavpilsScraper` JSON + `GpsTextClient` semicolon-delimited variants), `redis_reader.py` (batch MGET), `gtfs_rt_publisher.py` (combined protobuf re-export at `/gtfs-rt/vehicle_positions.pb`, public no-auth), `ws_subscriber.py` + `ws_manager.py` + `ws_routes.py` + `ws_schemas.py` (Redis Pub/Sub → ConnectionManager fan-out → JWT-via-querystring WebSocket clients), `repository.py` + `models.py` (`VehiclePositionRecord` TimescaleDB hypertable, 7-day compression / 90-day retention); (b) **journey planning** — `journey_planner.py` + `otp_client.py` calling a self-hosted OpenTripPlanner with circuit breaker, enriching OTP itineraries with GTFS-RT delays parsed back from the Redis cache; (c) **share links** — `locshare.py` (signed JWT in URL → SHA-256 hash in DB) + `ShareLink` model + the public `/share/{token}` resolver that intentionally bypasses `get_current_user`; (d) **phone-based tracking** — `owntracks_listener.py` (MQTT subscriber to OwnTracks topics) + `VehiclePhoneAssignment` admin CRUD; (e) **historical / ML-training ETLs** — `historical_gtfs_importer.py`, `eticket_importer.py`, `weather_etl.py`, `traffic_etl.py`, `snapshot_*.py`, `weather_models.py`, `traffic_models.py` — independent leader-elected hourly/daily cron jobs writing into their own PostGIS- and TimescaleDB-enabled tables purely for ML feature engineering, with no REST surface and no relationship to the realtime path other than co-tenancy in the directory.

**Data-flow shape.** Realtime: `feed_client.fetch_*` → `poller.poll_once` (per-feed asyncio task, `CircuitBreaker` wrapping fetch, adaptive interval keyed on hour-of-day) → `redis pipeline.set vehicle:{feed}:{vehicle}` (60s TTL) + `sadd feed:{feed}:vehicles` + `redis.publish transit:vehicles:{feed}` + `batch_insert_positions(vehicle_positions hypertable)` (best-effort, never blocks poller); read paths are `redis_reader.get_vehicles_from_redis` (batch MGET) for REST and `ws_subscriber._subscribe_loop` (Redis psubscribe → `ConnectionManager.broadcast` with per-client feed/route filtering) for WebSocket. Cold paths: `historical_gtfs_importer` / `eticket_importer` are CLI-driven (`scripts/*backfill*`); `weather_etl` / `traffic_etl` are background asyncio tasks with their own Redis leader locks. Journey-plan and share endpoints synchronously call out to OTP and Redis respectively from request handlers. **What is *not* here that you'd expect:** there is no slice-wide `service.py` — the existing `service.py` (376 LOC) is a *realtime-read* service only; share-link creation, phone-assignment duplicate-check (routes.py:301-309), and OTP planning all sit in route handlers or in modules that bypass the service/repository split that CLAUDE.md mandates. There is also no `repository.py` for any of the five non-realtime subsystems — each writes to its own tables directly through the same `AsyncSession`.

**Drift vs. README and CLAUDE.md (auto-flagged for dim 9):**
- **Drift:** README §API Endpoints (`app/transit/README.md:158-167`) claims "10 REST + 1 WebSocket"; actual is 12 REST + 1 WebSocket = 13 (`rg "@router\." app/transit/routes.py app/transit/ws_routes.py | wc -l` = 13). The undocumented endpoints are `/share` (POST), `/share/{token}` (GET), `/plan`, `/vehicles/{id}/eta`, `/gtfs-rt/vehicle_positions.pb`, `/phone-assignments` (3).
- **Drift:** README §Business Rules has duplicated numbering — `10`, `11`, `12` each appear twice across `app/transit/README.md:134-141`. Suggests two sets of business rules were merged without renumbering.
- **Drift:** CLAUDE.md project-structure line for `app/transit/` claims "10 REST + 1 WebSocket endpoint" — same miscount as README.
- **Drift:** README claims `Pub/Sub publishes enriched vehicles` but does not document that the *entire* `enriched_vehicles` list is published in a single message per poll cycle (`poller.py:235-243`); for high-vehicle-count feeds (Riga ~250 vehicles) this is a multi-hundred-KB message broadcast over Redis on every 10s cycle.

Five-subsystem co-tenancy is the dominant architectural fact and the lens for everything that follows.

---

## 3. Findings Table

T-001/T-002/T-003 are the Stage 1.3 quick wins shipped during Phase 1
orientation. T-004…T-042 are the Phase 2 sweep across §A dimensions 1–9, 11.
Dim 10 (agent surface) and dims 12–13 (frontend) are excluded scope.

| ID | Category | File:Line | Severity | Effort | Description | Recommendation | Status |
|----|----------|-----------|----------|--------|-------------|----------------|--------|
| T-001 | dim 7 (error handling) | `app/transit/routes.py:59,309,364,396,487,497,499` | Medium | M | 7 raw `raise HTTPException(...)` calls in route handlers contradict the CLAUDE.md rule "Inherit from `AppError` in `core.exceptions` for automatic HTTP status mapping." Pattern is codebase-wide (knowledge 5, analytics 5, fleet 2, etc.) — transit just has the most. | Add `ConflictError` (409) and `GoneError` (410) AppError subclasses; migrate transit raises in this PR; tag remaining slices `→ DEEPEN` for Architecture-Deepening. **The L414 `HTTPException(503)` bridging `TransitDataError` is intentional and stays — it's a different drift category (agent-exception → HTTP), not the same pattern.** | RESOLVED — alembic migration `y9z0a1b2c3d4`, `ConflictError`/`GoneError` added to `app/core/exceptions.py`, all 7 raises migrated, test suite green. |
| T-002 | dim 1 (architectural decay) + dim 4 (untested edge) | `app/transit/models.py:137`, `alembic/versions/t4u5v6w7x8y9_add_vehicle_phone_assignments.py:47`, `app/transit/routes.py:301-309,366` | High | S | `VehiclePhoneAssignment.phone_identifier` has DB-level `UniqueConstraint`, but the application implements soft-delete via `active=False`. The duplicate-check at `routes.py:301-309` filters `active.is_(True)` (correct), so a deactivated row holds the unique slot and any re-assignment with the same phone identifier 500s on the unique constraint. Untested path: `test_phone_assignment_routes.py:163-170` covers create→duplicate-active=409 but not create→deactivate→recreate=500. | Replace the full `UniqueConstraint("phone_identifier")` with a **partial** unique index `WHERE active = true` so deactivated rows don't block re-assignment. Add a regression test that exercises create → deactivate → recreate → 201. | RESOLVED — alembic migration `y9z0a1b2c3d4_phone_assignment_partial_unique.py` drops the full unique constraint and adds the partial index `uq_phone_assignments_active_phone_identifier`; model `__table_args__` updated; new `test_create_after_deactivate_allows_reuse` regression test. |
| T-003 | dim 5 (config) + dim 8 (input/contract) | `app/transit/ckan_client.py:30-39`, `app/core/agents/tools/transit/search_intercity.py:101,231,249-251` | Critical | S (gate) / L (real fix) | `CKAN_RESOURCES` ships placeholder UUIDs (`d4e5f6a7-…`, `e5f6a7b8-…`, sequentially incremented hex) used as live resource IDs in `search_intercity_*` agent tools. Worse, verification against data.gov.lv shows the actual ATD dataset (`atd-gtfs`) publishes a single zipped GTFS file (`b0a020e4-1ee6-4e1a-9a94-63b1f8defd6d`), not Datastore-enabled per-table resources — the entire `query_sql` architecture mismatches the data source. | Short-term: gate the feature behind `intercity_search_enabled=False` (default off); document the design mismatch in `ckan_client.py`. Long-term (DEEPEN): redesign the pipeline to import the ZIP into local tables (similar to `historical_gtfs_importer.py`) or find a different data source that exposes per-table SQL. | RESOLVED (gate) — `Settings.intercity_search_enabled` defaults False; `create_unified_deps()` skips the CKAN HTTP client when off, so the existing `_get_ckan_client` raises a clear `TransitDataError`. Real fix tagged `→ DEEPEN`. |
| T-004 | dim 1 (architectural decay) | `app/transit/service.py:1-376`, `app/transit/routes.py:280-471`, `app/transit/locshare.py:1-84`, `app/transit/journey_planner.py:1-347` | Medium | L | `service.py` is the *realtime-read* service only. Share-link creation/resolution (`routes.py:418-471`), phone-assignment duplicate-check (`routes.py:301-309`), and OTP planning (`routes.py:381-415` calls `journey_planner` directly) all bypass the service+repository split CLAUDE.md mandates. Five subsystems share one slice: realtime spine, journey planning, share links, phone tracking, ML-training ETLs. | Tagged `→ DEEPEN`: split into `app/transit/` (realtime), `app/sharelinks/`, `app/journey/` (or fold into transit but with its own service+repo), `app/ml_etl/`. Each gets its own `service.py` + `repository.py`. | OPEN — DEEPEN |
| T-005 | dim 1 | `app/transit/poller.py:132-258 poll_once` (126 LOC), `app/transit/poller.py:329-518 run` (189 LOC) | Medium | M | `FeedPoller.poll_once` is a 126-LOC method that fetches, enriches, publishes to Redis, and best-effort persists to Postgres in a single body. `FeedPoller.run` is a 189-LOC method that interleaves leader-lock acquire/refresh/release, adaptive polling interval computation, circuit-breaker transition logging, and `poll_once` dispatch. Both are over the §A 100-LOC threshold. | Extract `_fetch_and_enrich`, `_publish_to_redis`, `_persist_history` from `poll_once`. Extract `_lifecycle_loop` (lock+breaker) and `_poll_loop` (interval+dispatch) from `run`. Code stays in `poller.py`; coupling becomes intra-class instead of one mega-method. | OPEN |
| T-006 | dim 2 (consistency rot) | `app/transit/routes.py:440,496`, `app/transit/poller.py:240,342`, `app/transit/service.py:244`, `app/transit/journey_planner.py:85,129,203`, `app/transit/locshare.py:41`, `app/transit/owntracks_listener.py:160`, `app/transit/train_ws_listener.py:69`, `app/transit/redis_reader.py:52`, `app/transit/gtfs_rt_publisher.py:66`, `app/transit/historical_gtfs_importer.py:408`, `app/transit/eticket_importer.py:313`, `app/transit/traffic_etl.py:369` | Low | S | 14 sites use `datetime.now(tz=UTC)` (or `datetime.datetime.now(datetime.UTC)`) inline. `app.shared.models.utcnow()` exists for exactly this purpose and is used in `app/memory/repository.py`, `app/public_api/repository.py`. Convention drift only — no behavior bug. | Mechanical replace across all 14 sites. Add `from app.shared.models import utcnow`. Either ship as a single PR or tag `→ DEEPEN` for slice-wide cleanup if the convention is decided to be repo-wide. | OPEN |
| T-007 | dim 2 | `app/transit/feed_client.py:15`, `otp_client.py:6`, `journey_planner.py:12`, `service.py:13`, `poller.py:13`, `historical_gtfs_importer.py:15`, `ckan_client.py:16`, `traffic_etl.py:19`, `eticket_importer.py:18`, `weather_etl.py:19` | Low | M | 10 modules instantiate their own `httpx.AsyncClient` with overlapping lifetimes — service has its own, journey_planner has its own, each poller has its own, each ETL has its own. No shared connection pool. Each one needs its own close-on-shutdown wiring (some have it, some don't — ETLs use `async with`, OK). | Tagged `→ DEEPEN` for slice-wide HTTP-client lifecycle audit. Either reuse a single bounded-pool client per upstream host, or accept the per-module split and add a convention test enforcing close-on-shutdown wiring. | OPEN — DEEPEN |
| T-008 | dim 3 (type & contract debt) | `app/transit/feed_client.py:1` | High | S | `# pyright: reportUnknownArgumentType=false, reportUnknownVariableType=false` is a *file-level* suppression on the parser for non-GTFS-RT feed payloads (Daugavpils JSON, GpsTextClient CSV-like). The slice's primary trust boundary has its strictest type-checker disabled wholesale. | Replace with per-line `# pyright: ignore[<rule>]` for the specific lines that need it. Catalogue what shows up. The `_LAT_MIN/MAX/_LON_MIN/MAX` validation is good, but typing on the parsed shape is what catches drift. | OPEN |
| T-009 | dim 3 + dim 8 | `app/transit/journey_planner.py:114-119,163,207,211,227,234-235,248` | Medium | M | OTP response is parsed as `dict[str, Any]` at 8+ sites — `plan_data`, `itineraries_raw`, `from_place`, `to_place`, `legs_raw`, `leg`, `polyline_data`. No Pydantic model for the OTP response shape. OTP is an external HTTP service whose JSON shape can drift between versions. | Define `OTPPlanResponse`, `OTPItinerary`, `OTPLeg`, `OTPPlace` Pydantic models. Validate at `OTPClient.plan()` boundary. Internal call sites stop using `.get(...)` defaults. | OPEN |
| T-010 | dim 3 + dim 8 | `app/transit/ckan_client.py:165-283 query_sql` | Medium | M | Returns `list[dict[str, Any]]`. Downstream `search_intercity_*` agent tools (currently gated off, T-003) iterate raw dicts, do their own field reads. No schema validation at the CKAN boundary. | Tagged `→ DEEPEN` jointly with T-003 real fix — when the CKAN-or-ZIP-import pipeline gets redesigned, define `CKANStop`, `CKANRoute`, etc. Pydantic models with field validation. | OPEN — DEEPEN |
| T-011 | dim 3 | `app/transit/redis_reader.py:78` | Low | S | `results.append(VehiclePosition(**data))  # type: ignore[arg-type]` — explicit ignore on the Pydantic constructor splat. Indicates the dict shape isn't typed strongly enough for the model. | Replace with `VehiclePosition.model_validate(data)`. The model_validate path is the one that gives a proper validation error if shape drifts. | OPEN |
| T-012 | dim 3 | `app/transit/journey_planner.py:152`, `app/transit/redis_reader.py:63` | Low | S | `await redis_client.smembers(feed_key)  # type: ignore[misc]` repeated. The `redis-py` async stubs are weak around `smembers`. | Add a typed wrapper in `app/core/redis.py` (`async def smembers_str(key) -> set[str]`) and use it. Removes the duplicated ignore. | OPEN |
| T-013 | dim 4 (test debt) | `app/transit/tests/` (no `@pytest.mark.skip` / `xfail` found) | — | — | Audit dim 4 found zero skipped/xfailed tests in transit. No finding. | — | NOT MATERIAL |
| T-014 | dim 4 | `app/transit/tests/test_phone_assignment_routes.py:163-170` (pre-T-002), `app/transit/tests/test_journey_planner.py:69-310` | Low | S | Phone-assignment tests pre-T-002 covered create→duplicate but not create→deactivate→recreate (the soft-delete path that 500s); T-002 added the missing case. Journey planner tests construct fixtures from int timestamps but don't cover OTP-side enum drift (e.g. unknown `mode`, missing `legGeometry`). | Add 2-3 fixtures with malformed/partial OTP responses → assert graceful degradation, not exception leak through to handler. | OPEN |
| T-015 | dim 5 (config) | `app/core/config.py` (CKAN/data.gov.lv settings); `app/transit/ckan_client.py` | Low | S | `intercity_search_enabled=False` (T-003) means `ckan_datastore_sql_url`, `ckan_cache_ttl_s`, `ckan_rate_limit_delay_s`, `data_gov_lv_base_url`, `data_gov_lv_dataset_id`, `eticket_archive_base_url`, `eticket_max_archive_size_mb`, `gtfs_backfill_rate_limit_seconds` settings are unused-in-prod surface. Risk of bit-rot. | Either flip the flag soon (DEEPEN T-003 real fix) or annotate the settings with `# T-003: unused while intercity_search_enabled=False — keep wired for redesign`. | OPEN |
| T-016 | dim 5 | Phase 2 §A Stack tooling | — | — | `pip-audit`, `vulture`, `pydeps` runs were deferred during Phase 2 (CKAN-pivot consumed time). Not a finding under §B (no observed defect, just unrun tools); kept here as a deferred-tasks pointer, not a counted row. | Run `uvx pip-audit`, `uvx vulture app/transit/`, `uvx pydeps app/transit --show-cycles --noshow` in a follow-up; new findings append as T-043+. | NOT MATERIAL — DEFERRED TASK |
| T-017 | dim 6 (performance) | `app/transit/poller.py:235-243` | High | M | Every poll cycle (10s for Riga) publishes the *entire* `enriched_vehicles` list as one Redis Pub/Sub message via `transit:vehicles:{feed}`. For high-vehicle-count feeds (Riga ~250 vehicles, ~1KB each enriched), the broadcast is multi-hundred-KB on each tick, fanned out to every WebSocket client per-feed subscriber. WS subscriber then re-broadcasts via `ConnectionManager.broadcast` filtered per-client (`ws_subscriber._subscribe_loop`). Exact per-tick size has not been measured — `redis-cli MONITOR` against the running poller would confirm. | Either chunk per-route (publish per-route batches) or per-vehicle (one message per vehicle, smaller messages, more messages). Per-route preserves batch read efficiency on the WS side. | OPEN |
| T-018 | dim 6 | `app/transit/journey_planner.py:144-167 _build_delay_map` | Medium | S | For each feed in `feed_ids`, the method does sequential `redis.smembers(...)` then `redis.mget(...)`. Two round-trips per feed. With 4 feeds this is 8 sequential Redis calls before any OTP planning happens. | Wrap the per-feed loop in `asyncio.gather(*[_one_feed(fid) for fid in feed_ids])`. Single `redis_client` is async-safe. | OPEN |
| T-019 | dim 6 | `app/transit/poller.py:110`, `service.py:357`, `journey_planner.py:329` | Low | — | Three module-level singletons each own an `httpx.AsyncClient`. All three have explicit `close_*()` calls in `app/main.py` lifespan. | NOT MATERIAL — flagged for visibility; the close-on-shutdown wiring is correct in each case. | NOT MATERIAL |
| T-020 | dim 6 | `app/transit/poller.py:329-518 run` | Low | S | The leader-lock-refresh inside the run loop fires every iteration (effectively every poll interval). For an idle feed at a low-poll hour (60-300s interval), that's fine; for a fast feed (10s) every tick refreshes the lock. Slight Redis pressure. | Tagged `→ DEEPEN`. Decouple lock refresh from poll interval — refresh at `ttl/3` cadence regardless of poll interval. | OPEN — DEEPEN |
| T-021 | dim 7 (error handling) | `app/transit/routes.py:412` | Low | S | `raise HTTPException(status_code=503, detail=str(exc)) from exc` for `TransitDataError`. T-001 disposition kept this intentionally — but the rest of the slice now uses `AppError` subclasses with the global handler. | Add `ServiceUnavailableError(AppError)` (status 503) to `app/core/exceptions.py`, wire into `setup_exception_handlers`, replace the L412 raise. Closes T-001 follow-up. | OPEN |
| T-022 | dim 8 (input/SQL) | `app/transit/traffic_etl.py:175-194 upsert_traffic_counts`, `:230-249 upsert_traffic_accidents` | Medium | S | f-string interpolation of `lat`/`lon` floats into raw `text(...)` SQL with `# noqa: S608` suppressing the Bandit warning. The values come from `_safe_float()` which returns `float \| None`, so the runtime values are always floats or the literal `"NULL"` — *currently safe*. But the pattern is fragile: if `_safe_float` ever changes return type or a refactor inlines a different parser, the `noqa` masks the regression. | Replace the f-string with a parameter (`:location_lat`, `:location_lon` bindparams) and build the geography expression server-side with `ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography` — keeps the SQL static, removes the `noqa`. | OPEN |
| T-023 | dim 7 | `app/transit/gtfs_rt_publisher.py:122-124` | — | — | Initial sweep claimed `except Exception:` swallows protobuf-build errors and returns empty bytes silently. **Verification (lines 122-124) shows the block is `except Exception: logger.exception("transit.publisher.build_failed", feed_id=feed_id); raise`** — exception IS re-raised, log event IS emitted via `logger.exception`. Behaviour is correct: caller (`/gtfs-rt/vehicle_positions.pb` route) gets a 5xx, ops sees a structured log with traceback. | NOT MATERIAL — bad finding caught during Task 27 spot-check. | NOT MATERIAL |
| T-024 | dim 7 | `docs/logging-standard.md`; `app/transit/gtfs_rt_publisher.py:123` | — | — | Initial sweep claimed `transit.publisher.build_failed` is stale (declared in standard, not emitted). **Verification (`grep -n transit.publisher app/transit/gtfs_rt_publisher.py`) shows it IS emitted at line 123** via `logger.exception`. Audit-log-taxonomy stale-check finding was a false positive against my prior assumption, not the script. | NOT MATERIAL — bad finding caught during Task 27 spot-check. | NOT MATERIAL |
| T-025 | dim 7 | `app/transit/journey_planner.py:170,181,194`, `app/transit/ws_routes.py:55`, `app/transit/owntracks_listener.py:364`, `app/transit/train_ws_listener.py:312`, `app/transit/historical_gtfs_importer.py:249,342`, `app/transit/eticket_importer.py:275,286` | Low | — | 11 `except Exception` blocks. Each is a deliberate fail-open at a non-critical boundary (Redis cache miss, listener shutdown, importer per-row resilience, WS heartbeat error) and each logs. | NOT MATERIAL — covered by Section 6 entry. The pattern is correct here. | NOT MATERIAL — see §6 |
| T-026 | dim 7 | `app/transit/poller.py:402` | Low | S | `except Exception:` in `_release_leader_lock` swallows Redis errors during shutdown. Acceptable but should at least log at warning level. | Add `logger.warning("transit.poller.lock_release_failed", exc_info=True)`. | OPEN |
| T-027 | dim 8 (security) | `app/transit/routes.py:63-471`, `app/transit/ws_routes.py:60-87` | — | — | All 13 endpoint auth: `/vehicles` (any role), `/feeds` (any role), `/vehicles/{id}/history` (admin/disp/editor), `/vehicles/{id}/eta` (any role), `/routes/{id}/delay-trend` (admin/disp/editor), `/gtfs-rt/vehicle_positions.pb` (PUBLIC — by design), `/phone-assignments` POST (admin/disp), GET (admin/disp), DELETE (admin only), `/plan` (any role), `/share` POST (admin/disp), `/share/{token}` GET (PUBLIC — by design), WS (JWT). Two intentional public endpoints documented. | NOT MATERIAL — auth coverage is complete. Public endpoints are by design, see Section 6. | NOT MATERIAL |
| T-028 | dim 8 | `app/transit/ws_routes.py:60-87` | High | S | JWT in `?token=` query parameter is the standard browser-WS auth pattern, but the URL ends up in nginx access log + uvicorn access log + browser history + any error log. Token revocation (`is_token_revoked`) helps but doesn't fix log retention. | (a) Move token to `Sec-WebSocket-Protocol` subprotocol header (some browsers support this); or (b) configure nginx + uvicorn access logs to scrub `?token=` query string for the `/ws/` prefix. (b) is the smaller change. | OPEN |
| T-029 | dim 8 | `app/transit/routes.py:418-471 create_share_link`, `app/transit/locshare.py` | — | — | Share token issued in body. Stored as SHA-256 hash in DB. Token loss = no recovery. By design — share links are revocable per-instance via DB delete. | NOT MATERIAL — see Section 6. | NOT MATERIAL |
| T-030 | dim 8 | `app/transit/routes.py:165-201 get_vehicle_eta` | Low | M | ETA endpoint requires `get_current_user` (any authenticated role), but the underlying ETA model exposes per-vehicle schedule deviations that downstream operators may consider operationally sensitive. Public-data feed (`/gtfs-rt/...`) exposes raw positions, which is more public, so role parity is reasonable. | Tagged `→ DEEPEN` with the broader public-API question (Q2 below). Consider role-tightening only if the ML-derived ETA is decided to be operator-only data. | OPEN — DEEPEN |
| T-031 | dim 9 (doc drift) | `app/transit/README.md:158-167` | Medium | S | API Endpoints table lists 5 endpoints. Actual: 12 REST + 1 WS = 13. Missing: `/vehicles/{id}/eta`, `/gtfs-rt/vehicle_positions.pb`, `/phone-assignments` (POST/GET), `/phone-assignments/{id}` DELETE, `/plan`, `/share` POST, `/share/{token}` GET. | Add 8 missing rows with method/path/auth/description columns. Add a convention test that compares `@router.*` count to README row count. | OPEN |
| T-032 | dim 9 | `app/transit/README.md:134-141` | Low | S | Business rules use `10`, `11`, `12` twice each (lines 132-138 and again 137-138). Two sets of rules merged without renumbering. | Renumber the second set as 13/14/15. | OPEN |
| T-033 | dim 9 | `CLAUDE.md` repo-root `## Project Structure` line for `app/transit/` | Low | S | Same miscount as T-031: claims "10 REST + 1 WebSocket endpoint". | Update to "12 REST + 1 WebSocket". Or replace with auto-derived count from a convention test. | OPEN |
| T-034 | dim 9 | Public-facing docstrings: `app/transit/service.py`, `app/transit/locshare.py`, `app/transit/journey_planner.py` | Low | S | Module docstrings exist but several public functions miss Google-style param docs. `service.py:_enrich_vehicles` is a private one but `journey_planner.JourneyPlannerService.plan` lacks Returns/Raises. | Add missing Google-style docs on public methods. The 5-principle agent-tool docstring pattern doesn't apply here (REST surface). | OPEN |
| T-035 | dim 11 (GTFS/PostGIS/Timescale) | `app/transit/models.py:69-70`, `alembic/versions/b7c8d9e0f1a2_add_vehicle_positions_hypertable.py` | High | M | `VehiclePositionRecord.latitude` and `longitude` are `Float` columns. No `geography(POINT, 4326)` column. No GIST index on a derived expression. Indexes are on `(vehicle_id, recorded_at)`, `(route_id, recorded_at)`, `(feed_id, recorded_at)`. Any future "vehicles near a stop" history query has no spatial path. | Migration: `ALTER TABLE vehicle_positions ADD COLUMN location geography(POINT, 4326) GENERATED ALWAYS AS (ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography) STORED`. Then `CREATE INDEX ix_vehicle_positions_location ON vehicle_positions USING GIST (location)`. Use `STORED` so it indexes; the model gets a read-only `Mapped[WKBElement]` column. Hypertable + chunk re-build = backfill cost on an existing volume; check chunk count before merging. | OPEN |
| T-036 | dim 11 | `alembic/versions/k4l5m6n7o8p9_weather_traffic_tables.py:109-170` | High | S | `traffic_counts` and `traffic_accidents` are *not* hypertables. The same migration adds hypertable + 7-day compression + 365-day retention to `weather_observations` but skips both traffic tables. Both have time-series columns (`period_start/period_end` for counts, `detected_at` for accidents). Without hypertables they grow as one chunk; without retention they grow forever. | New migration: `SELECT create_hypertable('traffic_counts', 'period_start', chunk_time_interval => INTERVAL '7 days', if_not_exists => true)`; same for `traffic_accidents` on `detected_at`. Add `add_compression_policy` (e.g. 30 days) and `add_retention_policy` (e.g. 730 days) — exact policy is an open question (T-037). | OPEN |
| T-037 | dim 11 | `alembic/versions/b7c8d9e0f1a2_*` (90d), `alembic/versions/k4l5m6n7o8p9_*` (365d weather), `alembic/versions/i2j3k4l5m6n7_*` (1825d eticket) | Low | S | `vehicle_positions` retention 90d, `weather_observations` 365d, `eticket_validations` 1825d. Disparate policies, no documented rationale (each migration has its own opaque comment). | Add `docs/data-retention.md` documenting the rationale per table. Cross-link from each migration's docstring. | OPEN |
| T-038 | dim 11 | `app/transit/gtfs_rt_publisher.py:66` | Low | S | Publisher rebuilds `feed.header.timestamp = int(datetime.now(tz=UTC).timestamp())` — overwrites whatever upstream timestamp the source feed had. Downstream consumers can't tell when *we* serialized vs when the source observed. | Optionally preserve the highest upstream `vehicle.timestamp` when present; document the choice in the response header docstring. | OPEN |
| T-039 | dim 11 | `app/transit/feed_client.py` (no `from google.transit.gtfs_realtime_pb2 import` for stubs) | Medium | M | `feed_client.py` uses raw protobuf parsing without leveraging the type stubs in `typings/google.transit.gtfs_realtime_pb2.pyi` — the file-level pyright suppression (T-008) hides exactly the kind of GTFS-RT enum-drift the stubs would catch. | After T-008 tighten, add explicit imports + use the typed enum. The repo already has the stub. | OPEN — paired with T-008 |
| T-040 | dim 11 | `app/transit/repository.py:108-128 get_route_delay_trend` | — | — | Raw `text("...")` SQL using TimescaleDB `time_bucket()`. Uses `bindparams` so it's parameterized. SQLAlchemy ORM has no equivalent for `time_bucket`. | NOT MATERIAL — see Section 6. | NOT MATERIAL |
| T-041 | dim 11 | `app/transit/snapshot_models.py:55-` | Low | S | `GtfsSnapshotTrip`, `GtfsSnapshotStopTime` etc. use string GTFS IDs (intentional per docstring). They are NOT hypertables, but are append-only archive tables. No retention policy. Grow indefinitely. | Document the policy explicitly: archive data has no retention by design (training requires the full history). Add the rationale to the model docstring. Or — if storage becomes an issue — partition by `snapshot_date` later. | OPEN |
| T-042 | dim 11 | `app/transit/models.py:73`, `app/transit/repository.py:135-137` | — | — | Initial sweep claimed `delay_seconds` is `Float` and the repository casts it to `int`. **Verification (`grep -n delay_seconds app/transit/models.py`) shows it is already `Mapped[int] = mapped_column(SmallInteger, ...)` at line 73.** The `::int` casts in `repository.py:135-137` defensively coerce SQLAlchemy `Row` cells (not Float→int conversion). | NOT MATERIAL — bad finding caught during Task 27 spot-check. | NOT MATERIAL |

---

## 4. Top 5 Priorities

Five highest-impact open findings, with concrete diff sketches per §A Phase 3.

### Priority 1: T-036 — Hypertable + retention for `traffic_counts` / `traffic_accidents`

```python
# New migration: alembic/versions/zXXXX_traffic_hypertable.py

def upgrade() -> None:
    if _is_timescale_available():
        op.execute(
            "SELECT create_hypertable('traffic_counts', 'period_start', "
            "chunk_time_interval => INTERVAL '7 days', "
            "if_not_exists => true, migrate_data => true)"
        )
        op.execute(
            "SELECT create_hypertable('traffic_accidents', 'detected_at', "
            "chunk_time_interval => INTERVAL '7 days', "
            "if_not_exists => true, migrate_data => true)"
        )
        op.execute(
            "ALTER TABLE traffic_counts SET (timescaledb.compress, "
            "timescaledb.compress_segmentby = 'point_id, vehicle_class')"
        )
        op.execute("SELECT add_compression_policy('traffic_counts', INTERVAL '30 days')")
        op.execute("SELECT add_retention_policy('traffic_counts', INTERVAL '730 days')")
        # Same for traffic_accidents (different segmentby — accident severity)
```

Effort: S. Severity: High. Lowest-risk high-impact change in the audit —
it's a single migration with no application-code change required. Open
question on the exact retention horizon → see §7 Q1.

### Priority 2: T-035 — `vehicle_positions` PostGIS Geometry + GIST index

```python
# New migration: alembic/versions/zYYYY_vehicle_positions_geom.py

def upgrade() -> None:
    # Generated stored column — read-only, indexable, derives from lat/lon
    op.execute(
        "ALTER TABLE vehicle_positions ADD COLUMN location geography(POINT, 4326) "
        "GENERATED ALWAYS AS "
        "(ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography) STORED"
    )
    op.execute(
        "CREATE INDEX ix_vehicle_positions_location "
        "ON vehicle_positions USING GIST (location)"
    )

# app/transit/models.py:
class VehiclePositionRecord(Base, TimestampMixin):
    ...
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    location: Mapped[WKBElement] = mapped_column(
        Geography("POINT", srid=4326),
        Computed(
            "ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography",
            persisted=True,
        ),
        nullable=False,
    )
```

Effort: M (verify chunk count + backfill cost on existing hypertable before
merging — `SELECT count(*) FROM timescaledb_information.chunks WHERE
hypertable_name = 'vehicle_positions'`). Severity: High. Unlocks proximity
queries the slice would otherwise grow without.

### Priority 3: T-008 + T-039 — Tighten `feed_client.py` type suppression

```python
# Before: app/transit/feed_client.py:1
# pyright: reportUnknownArgumentType=false, reportUnknownVariableType=false
"""Pluggable feed clients..."""

# After:
"""Pluggable feed clients..."""

# At the specific call sites that needed it:
parsed_records = json.loads(text)  # pyright: ignore[reportUnknownVariableType]
# (etc — narrow per-line, audit what shows up)
```

Effort: S to remove file-level + S to triage the new pyright errors. Severity:
High. The file-level suppression is the single biggest type-debt blanket in
the slice and it sits exactly on the boundary parser. Pair with T-039 once
the per-line ignores are catalogued.

### Priority 4: T-017 — Per-route Redis Pub/Sub batching in `poller.py`

```python
# Before: app/transit/poller.py:235-243
await redis_client.publish(
    f"transit:vehicles:{feed_id}",
    json.dumps([v.model_dump(mode="json") for v in enriched_vehicles]),
)

# After:
by_route: dict[str, list[VehiclePosition]] = defaultdict(list)
for v in enriched_vehicles:
    by_route[v.route_id or "_no_route_"].append(v)
async with redis_client.pipeline(transaction=False) as pipe:
    for route_id, vehicles in by_route.items():
        pipe.publish(
            f"transit:vehicles:{feed_id}:{route_id}",
            json.dumps([v.model_dump(mode="json") for v in vehicles]),
        )
    await pipe.execute()

# WS subscriber: psubscribe to transit:vehicles:{feed}:* (already glob), then
# ConnectionManager filters per-client by route_id. For a Riga-sized feed
# (~250 vehicles spread across ~50 routes), per-message size drops
# proportionally — exact ratio depends on vehicle distribution and should be
# verified post-rollout via `redis-cli MONITOR`.
```

Effort: M (poller change + WS subscriber pattern adjustment + test that
broadcast still reaches every connected client). Severity: High. Bandwidth and
WS-client parse cost both scale linearly with feed size today.

### Priority 5: T-028 — Scrub WebSocket `?token=` from access logs

```nginx
# nginx/nginx.conf — add to /ws/ location block
location /ws/ {
    set $clean_args $args;
    if ($args ~ "(.*)token=[^&]*(.*)") {
        set $clean_args "$1token=REDACTED$2";
    }
    access_log /var/log/nginx/access.log main_with_clean_args;
    proxy_pass ...;
}

# nginx/nginx.conf — log_format
log_format main_with_clean_args '$remote_addr - "$request_method $uri?$clean_args" ...';
```

Effort: S. Severity: High. Smaller change than moving to subprotocol auth and
addresses the immediate token-leak-in-logs risk. The subprotocol upgrade can
follow later as the proper fix.

---

## 5. Quick Wins

Each item below is `Effort=S` AND `Severity ≥ Medium` per §B; all three shipped.

- [x] **T-002** — Replace `phone_identifier` full unique constraint with partial `WHERE active = true` index (Effort=S, Severity=High). Migration `y9z0a1b2c3d4`.
- [x] **T-003** — Gate `intercity_search_*` agent tools behind off-by-default `intercity_search_enabled` flag until ATD GTFS ZIP ingestion is redesigned (Effort=S for the gate, Severity=Critical).
- [x] **T-001** *(transit slice only)* — Replace `routes.py` raw `HTTPException` raises with `AppError` subclasses; add `ConflictError`/`GoneError`. Effort was M (8 sites + handler + test), tracked here for visibility. Codebase-wide migration of remaining 23 raises across 7 other slices is tagged `→ DEEPEN`.

### Phase 2 sweep — open quick wins (`Effort=S` AND `Severity ≥ Medium`)

- [ ] **T-036** — Add hypertable + retention/compression policies for
  `traffic_counts` and `traffic_accidents` (Effort=S, Severity=High). Single
  migration. Open question on retention horizon → §7 Q1.
- [ ] **T-008** — Replace file-level `pyright: reportUnknown*=false` in
  `feed_client.py:1` with per-line ignores (Effort=S, Severity=High).
- [ ] **T-028** — Scrub `?token=` from nginx + uvicorn access logs for `/ws/`
  prefix (Effort=S, Severity=High). Smaller than subprotocol upgrade.
- [ ] **T-022** — Add per-batch failure counter + end-of-batch log to
  `traffic_etl.py:399-411` triple-nested except blocks (Effort=S,
  Severity=Medium).
- [ ] **T-031** — Add 8 missing endpoint rows to `app/transit/README.md`
  (Effort=S, Severity=Medium). Pair with T-032 (renumber business rules) and
  T-033 (CLAUDE.md miscount) for one PR.
- [ ] **T-018** — `asyncio.gather` per-feed in
  `journey_planner._build_delay_map` (Effort=S, Severity=Medium).
- [ ] **T-021** — Add `ServiceUnavailableError(AppError)` and migrate
  `routes.py:412` (Effort=S, Severity=Low/Medium — closes T-001 follow-up).
- [ ] **T-006** — Replace 14 `datetime.now(tz=UTC)` sites with `utcnow()`
  (Effort=S, Severity=Low). Listed for batching with other slice-wide
  cleanups; weak convention so not a hard ship blocker.

---

## 6. Looks Bad But Actually Fine

Each entry is something that surfaced as a candidate finding and was
deliberately not flagged. The reasoning that closed the call is recorded so
the next reviewer doesn't re-walk it.

- **`poller.py:run` is 189 LOC and `poll_once` is 126 LOC.** Both are over
  the §A 100-LOC threshold and `T-005` does flag them with a scoped
  refactor. But: `run` is a single state-machine loop (leader-lock acquire →
  poll dispatch → breaker check → adaptive interval → release), not a god
  function pretending to be one method. Splitting it into helpers fixes the
  metric without making the control flow easier to follow — the helpers
  end up sharing 5+ pieces of mutable state. T-005 stays open as Medium/M
  but is *not* a Top-5 priority precisely because the cure is not clearly
  better than the disease.

- **`routes.py:412` raw `HTTPException(503)` after T-001 migration.** The
  T-001 disposition kept this one site as a bridge from `TransitDataError`
  (an agent-domain exception) to HTTP 503. Rest of the slice migrated to
  `AppError` subclasses. T-021 proposes a `ServiceUnavailableError(AppError)`
  to close the gap properly, but the current raw raise is *not* a regression
  — it's a deliberately-different bridge for an exception that doesn't
  inherit `AppError` and shouldn't (`TransitDataError` is reused by agent
  tools that don't speak HTTP).

- **`repository.py:108-128 get_route_delay_trend` is raw `text()` SQL.**
  Looks like a SQLAlchemy-best-practices miss. It uses TimescaleDB's
  `time_bucket()` function which has no SQLAlchemy ORM equivalent.
  `bindparams(...)` keeps it parameterized; the alternative (manually-
  generated bucket boundaries with `case/when`) is strictly worse. Leave it.

- **`/gtfs-rt/vehicle_positions.pb` is unauthenticated** (`routes.py:256`).
  Looks like a missing `get_current_user`. It's intentional — the endpoint
  serves the standard public GTFS-Realtime protobuf feed that downstream
  open-data consumers (transit apps, mapping tools, university research)
  expect to be public. The README documents it correctly. CLAUDE.md
  miscount (T-033) hides the endpoint from the project-structure summary
  but the intent is correct.

- **`/share/{token}` is unauthenticated** (`routes.py:474`). Looks like a
  CTX-AUTH violation. It's the entire point of share links — the *token*
  is the authentication. Token is signed JWT, stored as SHA-256 hash, has
  expiry, and is revocable per-instance. (T-029 records this disposition.)

- **The 11 `except Exception` blocks at T-025 (journey planner cache reads,
  WS heartbeat send, listener shutdown, importer per-row resilience).**
  `rg "except Exception:" app/transit/` finds 16 sites. Eleven of them are
  *deliberate* fail-open at non-critical boundaries — Redis cache write
  failures shouldn't fail the request, MQTT listener cleanup shouldn't
  fail shutdown, an importer's per-row failure shouldn't fail the
  10,000-row batch. Each one logs. T-022 (traffic_etl f-string SQL with
  `# noqa: S608`) is the one that surfaced an actual concern; T-023 was
  initially flagged here but Task 27 verification showed the publisher
  re-raises and emits `transit.publisher.build_failed`, so it is no
  longer a finding.

- **14 `datetime.now(tz=UTC)` sites instead of `utcnow()`** (T-006). Looks
  like clear convention violation. But: the convention itself
  (`app.shared.models.utcnow()`) is a one-line wrapper around exactly
  `datetime.now(tz=UTC)` — there's no behavioral difference. It's used in
  2 other slices (memory, public_api). The transit drift is real but
  load-bearing-ness is low; T-006 is the *lowest priority* finding for a
  reason. Flagged for batching with other slice-wide cleanups, not as a
  ship blocker.

---

## 7. Open Questions for the Maintainer

Debt-vs-intentional uncertainties that aren't resolvable from code alone.

**Q1: Are `weather_observations` 365d, `vehicle_positions` 90d, and
`eticket_validations` 1825d retention policies the result of explicit
data-engineering choices, or migration drift?**
Three migrations set wildly different retention horizons with no documented
rationale. T-036 needs a retention policy for the new traffic tables but
there's no precedent to anchor on — should accidents follow the 5-year
e-ticket horizon (because they're rare events with research value)?
Counts follow the 1-year weather horizon (because they're daily aggregates)?
Files: `alembic/versions/b7c8d9e0f1a2_add_vehicle_positions_hypertable.py:84`,
`alembic/versions/k4l5m6n7o8p9_weather_traffic_tables.py:107`,
`alembic/versions/i2j3k4l5m6n7_add_eticket_validations.py:103`.

**Q2: Should `/api/v1/transit/vehicles` and `/api/v1/transit/feeds` move from
`get_current_user` (any role) to public, since `/gtfs-rt/vehicle_positions.pb`
exposes the same data already?**
The protobuf endpoint exists *because* downstream consumers want unauthenticated
access. The JSON variant is locked behind any-role auth. If the data is
public-by-protocol, the role check on the JSON variant is theatre — it just
forces consumers to the protobuf path. Alternative: move both to a `Public
Developer API` slice (the OPS-2.x public API key infrastructure already
exists at `app/public_api/`).
Files: `app/transit/routes.py:63-110`, `app/transit/routes.py:256-283`.

**Q3: With LV-3.2 fleet bridge writing to `transit:vehicles:fleet` and
OwnTracks writing to `transit:vehicles:owntracks` (or similar), is the
intentional contract that they share the `vehicle_id` namespace — and if
yes, is one of them meant to win, or both meant to coexist?**
Both pipelines can write the same `vehicle_id` into different feeds; no
de-dup logic exists. If a phone-tracked driver also has a Traccar device
on the same vehicle, the WebSocket subscriber broadcasts both. The README
documents *that* this happens but not *why* (intent vs accident).
Files: `app/transit/owntracks_listener.py:184`, `app/fleet/service.py:62`,
`app/transit/poller.py:235-243`.

**Q4: Is `intercity_search_enabled=False` (T-003 disposition) a holding
pattern for weeks/months, or does the LV-1.1 plan have a target sprint to
flip it back on with the redesigned ZIP-import pipeline?**
The longer the flag stays default-off, the more likely the surrounding CKAN
config (T-015: 8 settings) bit-rots. If there's no concrete target, T-015
should add `# T-003: keep wired` markers; if there is, the markers are
unnecessary and the redesign should be the next planning round.
Files: `app/transit/ckan_client.py:42-51`, `app/core/config.py` (CKAN
section), `.agents/plans/td-1.1-transit-pilot-audit.md`.
