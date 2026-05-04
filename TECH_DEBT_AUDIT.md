# Tech-Debt Audit — `app/transit/` (Stage 1.1 pilot)

> Status: **Phase 1 mental model complete + 3 quick wins shipped (T-001/T-002/T-003). Phase 2 dimension sweep deferred.**
> Audit scope: `app/transit/` (32 `.py` files, 6612 LOC, 27 test modules).
> Excluded: `app/core/agents/` (Stage 5), `cms/` (frontend), agent surface dim 10.
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

_TBD — populated in Task 20 after the dimension sweep._

---

## 2. Architectural Mental Model

`app/transit/` is presented in `CLAUDE.md` as a single vertical slice for "Multi-feed GTFS-RT tracking," but in practice it is the load-bearing spine for **five distinct subsystems** sharing one directory: (a) the **GTFS-RT realtime spine** — `poller.py` (leader-elected per-feed asyncio pollers with `CircuitBreaker`), `feed_client.py` (pluggable `FeedClient` Protocol with `DaugavpilsScraper` JSON + `GpsTextClient` semicolon-delimited variants), `redis_reader.py` (batch MGET), `gtfs_rt_publisher.py` (combined protobuf re-export at `/gtfs-rt/vehicle_positions.pb`, public no-auth), `ws_subscriber.py` + `ws_manager.py` + `ws_routes.py` + `ws_schemas.py` (Redis Pub/Sub → ConnectionManager fan-out → JWT-via-querystring WebSocket clients), `repository.py` + `models.py` (`VehiclePositionRecord` TimescaleDB hypertable, 7-day compression / 90-day retention); (b) **journey planning** — `journey_planner.py` + `otp_client.py` calling a self-hosted OpenTripPlanner with circuit breaker, enriching OTP itineraries with GTFS-RT delays parsed back from the Redis cache; (c) **share links** — `locshare.py` (signed JWT in URL → SHA-256 hash in DB) + `ShareLink` model + the public `/share/{token}` resolver that intentionally bypasses `get_current_user`; (d) **phone-based tracking** — `owntracks_listener.py` (MQTT subscriber to OwnTracks topics) + `VehiclePhoneAssignment` admin CRUD; (e) **historical / ML-training ETLs** — `historical_gtfs_importer.py`, `eticket_importer.py`, `weather_etl.py`, `traffic_etl.py`, `snapshot_*.py`, `weather_models.py`, `traffic_models.py` — independent leader-elected hourly/daily cron jobs writing into their own PostGIS- and TimescaleDB-enabled tables purely for ML feature engineering, with no REST surface and no relationship to the realtime path other than co-tenancy in the directory.

**Data-flow shape.** Realtime: `feed_client.fetch_*` → `poller.poll_once` (per-feed asyncio task, `CircuitBreaker` wrapping fetch, adaptive interval keyed on hour-of-day) → `redis pipeline.set vehicle:{feed}:{vehicle}` (60s TTL) + `sadd feed:{feed}:vehicles` + `redis.publish transit:vehicles:{feed}` + `batch_insert_positions(vehicle_positions hypertable)` (best-effort, never blocks poller); read paths are `redis_reader.get_vehicles_from_redis` (batch MGET) for REST and `ws_subscriber._subscribe_loop` (Redis psubscribe → `ConnectionManager.broadcast` with per-client feed/route filtering) for WebSocket. Cold paths: `historical_gtfs_importer` / `eticket_importer` are CLI-driven (`scripts/*backfill*`); `weather_etl` / `traffic_etl` are background asyncio tasks with their own Redis leader locks. Journey-plan and share endpoints synchronously call out to OTP and Redis respectively from request handlers. **What is *not* here that you'd expect:** there is no slice-wide `service.py` — the existing `service.py` (376 LOC) is a *realtime-read* service only; share-link creation, phone-assignment duplicate-check (routes.py:301-309), and OTP planning all sit in route handlers or in modules that bypass the service/repository split that CLAUDE.md mandates. There is also no `repository.py` for any of the five non-realtime subsystems — each writes to its own tables directly through the same `AsyncSession`.

**Drift vs. README and CLAUDE.md (auto-flagged for dim 9):**
- **Drift:** README §API Endpoints (`app/transit/README.md:158-167`) claims "10 REST + 1 WebSocket"; actual is 12 REST + 1 WebSocket = 13 (`rg "@router\." app/transit/routes.py app/transit/ws_routes.py | wc -l` = 13). The undocumented endpoints are `/share` (POST), `/share/{token}` (GET), `/plan`, `/vehicles/{id}/eta`, `/gtfs-rt/vehicle_positions.pb`, `/phone-assignments` (3).
- **Drift:** README §Business Rules has duplicated numbering — `10`, `11`, `12` each appear twice across `app/transit/README.md:134-141`. Suggests two sets of business rules were merged without renumbering.
- **Drift:** Logging-taxonomy audit (`scripts/audit_log_taxonomy.py`) reports `transit.publisher.build_failed` as **stale** — declared in `docs/logging-standard.md` but no longer emitted from `app/transit/gtfs_rt_publisher.py`.
- **Drift:** CLAUDE.md project-structure line for `app/transit/` claims "10 REST + 1 WebSocket endpoint" — same miscount as README.
- **Drift:** README claims `Pub/Sub publishes enriched vehicles` but does not document that the *entire* `enriched_vehicles` list is published in a single message per poll cycle (`poller.py:235-243`); for high-vehicle-count feeds (Riga ~250 vehicles) this is a multi-hundred-KB message broadcast over Redis on every 10s cycle.

Five-subsystem co-tenancy is the dominant architectural fact and the lens for everything that follows.

---

## 3. Findings Table

Three findings surfaced during Phase 1 orientation and shipped immediately as
Stage 1.3 quick wins. The full Phase 2 sweep across §A dimensions 1–9, 11 is
paused — when resumed, additional findings will append below as `T-004+`.

| ID | Category | File:Line | Severity | Effort | Description | Recommendation | Status |
|----|----------|-----------|----------|--------|-------------|----------------|--------|
| T-001 | dim 7 (error handling) | `app/transit/routes.py:59,309,364,396,487,497,499` | Medium | M | 7 raw `raise HTTPException(...)` calls in route handlers contradict the CLAUDE.md rule "Inherit from `AppError` in `core.exceptions` for automatic HTTP status mapping." Pattern is codebase-wide (knowledge 5, analytics 5, fleet 2, etc.) — transit just has the most. | Add `ConflictError` (409) and `GoneError` (410) AppError subclasses; migrate transit raises in this PR; tag remaining slices `→ DEEPEN` for Architecture-Deepening. **The L414 `HTTPException(503)` bridging `TransitDataError` is intentional and stays — it's a different drift category (agent-exception → HTTP), not the same pattern.** | RESOLVED — alembic migration `y9z0a1b2c3d4`, `ConflictError`/`GoneError` added to `app/core/exceptions.py`, all 7 raises migrated, test suite green. |
| T-002 | dim 1 (architectural decay) + dim 4 (untested edge) | `app/transit/models.py:137`, `alembic/versions/t4u5v6w7x8y9_add_vehicle_phone_assignments.py:47`, `app/transit/routes.py:301-309,366` | High | S | `VehiclePhoneAssignment.phone_identifier` has DB-level `UniqueConstraint`, but the application implements soft-delete via `active=False`. The duplicate-check at `routes.py:301-309` filters `active.is_(True)` (correct), so a deactivated row holds the unique slot and any re-assignment with the same phone identifier 500s on the unique constraint. Untested path: `test_phone_assignment_routes.py:163-170` covers create→duplicate-active=409 but not create→deactivate→recreate=500. | Replace the full `UniqueConstraint("phone_identifier")` with a **partial** unique index `WHERE active = true` so deactivated rows don't block re-assignment. Add a regression test that exercises create → deactivate → recreate → 201. | RESOLVED — alembic migration `y9z0a1b2c3d4_phone_assignment_partial_unique.py` drops the full unique constraint and adds the partial index `uq_phone_assignments_active_phone_identifier`; model `__table_args__` updated; new `test_create_after_deactivate_allows_reuse` regression test. |
| T-003 | dim 5 (config) + dim 8 (input/contract) | `app/transit/ckan_client.py:30-39`, `app/core/agents/tools/transit/search_intercity.py:101,231,249-251` | Critical | S (gate) / L (real fix) | `CKAN_RESOURCES` ships placeholder UUIDs (`d4e5f6a7-…`, `e5f6a7b8-…`, sequentially incremented hex) used as live resource IDs in `search_intercity_*` agent tools. Worse, verification against data.gov.lv shows the actual ATD dataset (`atd-gtfs`) publishes a single zipped GTFS file (`b0a020e4-1ee6-4e1a-9a94-63b1f8defd6d`), not Datastore-enabled per-table resources — the entire `query_sql` architecture mismatches the data source. | Short-term: gate the feature behind `intercity_search_enabled=False` (default off); document the design mismatch in `ckan_client.py`. Long-term (DEEPEN): redesign the pipeline to import the ZIP into local tables (similar to `historical_gtfs_importer.py`) or find a different data source that exposes per-table SQL. | RESOLVED (gate) — `Settings.intercity_search_enabled` defaults False; `create_unified_deps()` skips the CKAN HTTP client when off, so the existing `_get_ckan_client` raises a clear `TransitDataError`. Real fix tagged `→ DEEPEN`. |

---

## 4. Top 5 Priorities

_TBD — populated in Task 22._

---

## 5. Quick Wins

Each item below is `Effort=S` AND `Severity ≥ Medium` per §B; all three shipped.

- [x] **T-002** — Replace `phone_identifier` full unique constraint with partial `WHERE active = true` index (Effort=S, Severity=High). Migration `y9z0a1b2c3d4`.
- [x] **T-003** — Gate `intercity_search_*` agent tools behind off-by-default `intercity_search_enabled` flag until ATD GTFS ZIP ingestion is redesigned (Effort=S for the gate, Severity=Critical).
- [x] **T-001** *(transit slice only)* — Replace `routes.py` raw `HTTPException` raises with `AppError` subclasses; add `ConflictError`/`GoneError`. Effort was M (8 sites + handler + test), tracked here for visibility. Codebase-wide migration of remaining 23 raises across 7 other slices is tagged `→ DEEPEN`.

---

## 6. Looks Bad But Actually Fine

_TBD — populated in Task 24 (≥3 entries required by §A; empty = audit didn't look hard enough)._

---

## 7. Open Questions for the Maintainer

_TBD — populated in Task 25 (≥2 entries required)._
