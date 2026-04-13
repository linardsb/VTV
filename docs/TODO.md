# VTV TODO

Planned features and improvements. Each item links to its detailed planning document where available.

> Architecture: Vertical Slice, security-first, async-first, Latvian-first
> Pattern: Each task = one planning + implementation session
> Agent Intelligence Plan: [docs/PLANNING/agent-intelligence-plan.md](PLANNING/agent-intelligence-plan.md)

---

## Progress Overview

```
Backend API       ██████████████████████░░  99%  (12/12 features + analytics + compliance exports + multi-feed GTFS-RT + WebSocket live streaming + alerts + fleet + geofences)
CMS Frontend      ███████████████████████░  99%  (18 pages live, real API on all, WebSocket real-time, multi-feed support, EU compliance exports, analytics dashboard, fleet devices/map/telemetry, geofences, full-screen map)
Testing           ████████████████████░░░░  90%  (2258 unit tests, 115 security tests, 81 e2e tests, CI pipeline live with security gates)
Infrastructure    ██████████████████████░░  97%  (Docker, nginx+Brotli, Gunicorn multi-worker, Redis rate limiting, Makefile, 25 slash commands, CI/CD, 6 security audits, SDLC security framework, context-triggered security SDC, pre-commit framework + detect-secrets, graceful shutdown coordinator)
Latvia Platform   ████████████░░░░░░░░░░░  55%  (Riga GTFS + PostGIS + WebSocket + multi-feed GTFS-RT + TimescaleDB historical storage + pluggable feed clients + PV train WebSocket + adaptive polling + per-feed circuit breakers + GTFS-RT publisher)
Agent Intelligence ████████████████████████ 100%  (Phases AI-1 through AI-11 complete — see docs/TODO-archive.md. AI-8 complete: circuit-breaker + provider health + chain integration. AI-9 complete: injection detection + blocking + output validation. AI-10 complete: heading-breadcrumb citations + regression tests. AI-11 complete: AI-11.1 synthetic QA generation + AI-11.2 retrieval metrics + AI-11.3 eval runner + faithfulness judge + AI-11.4 regression baselines + CI gate.)
Intelligence/ML   ████████████████████████ 100%  (17/17 subtasks done. ML-1 complete. ML-2 complete. ML-3 complete. ML-4 complete. ML-5 complete.)
```

## In Progress

### E2E Testing Maturity

- [ ] **CRUD E2E Tests** - Tests that create/edit/delete records and verify persistence. Current 81 tests cover page loads, filters, navigation, and UI interactions but don't test full write operations (require seeded test data).

---

## Completed Tracks — Archived

**Agent Intelligence** (AI-1 through AI-11) — all 40 subtasks complete. See [TODO-archive.md](TODO-archive.md).
**Operations & Platform Hardening** (OPS-1 through OPS-5) — all 16 subtasks complete. See [TODO-archive.md](TODO-archive.md).
**Intelligence/ML** (ML-1 through ML-5) — all 17 subtasks complete. See [TODO-archive.md](TODO-archive.md).

---

## Planned Features

> Plan: [docs/PLANNING/Implementation-Plan.md](PLANNING/Implementation-Plan.md) | [docs/PLANNING/fleet-management-tracking.md](PLANNING/fleet-management-tracking.md) | [docs/PLANNING/rag-improvements.md](PLANNING/rag-improvements.md) | [docs/PLANNING/sop-file-automation.md](PLANNING/sop-file-automation.md)

### Master Summary — 31 subtasks remaining

| Track | Subtasks | BE | FE | Mobile | Infra | Realistic Total |
|-------|----------|----|----|--------|-------|-----------------|
| Latvia Phase 1 | 2 | 2 | 0 | — | — | ~3h |
| ~~Latvia Phase 2~~ | ~~0~~ | — | — | — | — | ✅ Done |
| Latvia Phase 3 | 4 | 3 | 1 | — | 2 | ~2 days |
| Knowledge Base | 5 | 5 | 0.5 | — | — | ~6h |
| SOP Automation | 5 | 5 | 0.5 | — | — | ~1 day |
| Fleet Phase 2 | 3 | 2 | 1 | — | — | ~2 days |
| Fleet Phase 3 | 3 | 2 | 1 | — | — | ~2.5 days |
| Fleet Phase 4 | 2 | 1 | 1 | — | 1 | ~1 day |
| Fleet Phase 5 | 2 | 1 | — | 1 | — | ~2 days |
| CMS Features | 1 | 0.5 | 0.5 | — | — | ~30min |
| **Totals** | **31** | **22.5** | **5.5** | **1** | **3** | **~11.5 days serial** |

### Max Parallel Schedule (~5 days with 3 sessions)

```
Day 1:  Session A: LV-1.1 + LV-1.2 (BE)    | Session B: CMS-1 (FE)               | Session C: KB-1..KB-5 (BE)
Day 2:  Session A: ~~LV-2.1 + LV-2.2~~ ✅   | Session B: SOP-1..SOP-3 + SOP-5 (BE)| Session C: FLEET-2.1 + FLEET-2.2 (BE)
Day 3:  Session A: LV-2.3 + LV-2.4 (BE)     | Session B: LV-3.1 + LV-3.2 (BE)    | Session C: TACHO-1 (BE)
Day 4:  Session A: LV-3.3 (BE+FE)            | Session B: LV-3.4 + FLEET-2.3 (BE) | Session C: TACHO-2 + TACHO-3 (BE+FE)
Day 5:  Session A: ROUTE-1 + ROUTE-2 (BE+FE) | Session B: MSG-1 (BE)               | Session C: SOP-4 + MSG-2 (BE+Mobile)
```

### Cross-Track Dependencies

```
~~LV-1.2 (multi-city GTFS)~~ ✅ ──→ SOP-4 (GTFS schedule sync) — unblocked
LV-3.4 (LocShare) ──────────→ FLEET-2.3 (fleet LocShare)
TACHO-1 (DDD parser) ───────→ TACHO-2 (driving hours) ──→ TACHO-3 (dashboard)
ROUTE-1 (OSRM backend) ────→ ROUTE-2 (planning UI)
MSG-1 (messaging API) ──────→ MSG-2 (mobile app)
Everything else is independent and can run in any order.
```

---

### Latvia Transit — Phase 1 Remaining (~3 hours)

> **Sprint deliverable:** Extend Riga-only coverage to all Latvia via CKAN bridge (day-zero intercity data) + multi-city GTFS import. Full-screen `/map` CMS page is done (LV-1.3). Architecture is already multi-feed (TRANSIT_FEEDS_JSON, per-feed pollers, namespaced Redis keys, pattern-subscribe WS) — this phase fills in the data.

| Subtask | Type | Realistic | Parallel? |
|---------|------|-----------|-----------|
| ~~LV-1.1 CKAN bridge~~ | BE | ✅ Done | Implemented 2026-04-13 — plan: `.agents/plans/lv-1-1-ckan-bridge-client.md` |
| ~~LV-1.2 Multi-city GTFS~~ | BE | ✅ Done | Implemented 2026-04-13 — plan: `.agents/plans/lv-1-2-multi-city-gtfs-import.md` |
| ~~LV-1.3 Full-screen `/map`~~ | FE | ✅ Done | Implemented 2026-04-13 — plan: `.agents/plans/fe-full-screen-map.md` |

#### ~~LV-1.1 CKAN data.gov.lv Bridge Client~~ ✅ Implemented 2026-04-13
**What:** `app/transit/ckan_client.py` — async CKAN Datastore SQL API client with Redis caching (5 min TTL), rate limiting (1 req/s), automatic pagination (>32K rows, capped at 100 pages), and SQL input sanitization. Two agent tools registered: `search_intercity_stops` (name/proximity), `search_intercity_routes` (name/stop filter). 31 tests across 2 files.
**Plan:** `.agents/plans/lv-1-1-ckan-bridge-client.md`
**Files:** `app/transit/ckan_client.py`, `app/core/agents/tools/transit/search_intercity.py`, config + deps + agent.py updates, 15 new log events in `docs/logging-standard.md`
**Config:** `CKAN_DATASTORE_SQL_URL`, `CKAN_CACHE_TTL_S`, `CKAN_RATE_LIMIT_DELAY_S`
**Note:** CKAN resource IDs are placeholder UUIDs — replace with actual data.gov.lv IDs before production use.

#### ~~LV-1.2 Multi-City GTFS Static Import~~ ✅ Done (2026-04-13)
**What:** Extend `app/schedules/gtfs_import.py` to support multiple GTFS feeds by namespacing all parsed entities with `feed_id`. Add GTFS feed management endpoints and a scheduled background task that re-imports each feed daily.
**Why:** Current importer overwrites all data on each run — fine for single-feed Riga, breaks with multiple cities. Feed-scoped imports let Riga, Jurmala, Pieriga, and ATD coexist in the same DB tables. The `Shape` model already carries `feed_id`; other models need the same treatment.
**Implementation:**
- `alembic/versions/xxx_add_feed_id_to_gtfs_tables.py` — add `feed_id` column (default `"riga"`) + composite unique constraints to `routes`, `trips`, `stop_times`, `calendar`, `calendar_dates`, `agencies`. Backfill existing rows with `"riga"`.
- `app/schedules/gtfs_import.py` — `GTFSImporter.__init__(feed_id: str)` propagates `feed_id` to all parsed entities. `GTFSParseResult` includes `feed_id`.
- `app/schedules/service.py` — `import_feed(feed_id, url)` downloads ZIP, delegates to importer, upserts (delete old feed rows + insert new in a transaction)
- `app/schedules/routes.py` — `POST /v1/schedules/feeds/{feed_id}/import` (admin-only), `GET /v1/schedules/feeds` (list configured feeds + last import timestamp)
- `app/main.py` — background task: daily at 03:00 UTC, loop `settings.transit_feeds`, re-import static GTFS for each feed with a valid `static_url`
- `TRANSIT_FEEDS_JSON` — add entries for ATD (`https://atd.lv/sites/default/files/GTFS/gtfs-latvia-lv.zip`), Jurmala, Pieriga
- 15+ unit tests: feed-scoped parsing (3), upsert idempotency (2), composite unique constraints (2), multi-feed coexistence (2), background task scheduling (2), endpoint auth (2), migration rollback (2)
**Verify:** Import Riga + ATD feeds. `SELECT feed_id, COUNT(*) FROM routes GROUP BY 1` shows two rows. Re-import Riga — ATD routes untouched. Agent tools query routes across feeds. GTFS export still works for single-feed download.

#### ~~LV-1.3 Full-Screen `/map` CMS Page~~ ✅ Implemented 2026-04-13
**What:** New CMS page at `/map` — full-viewport Leaflet map showing all live vehicles from all feeds, with operator/route/vehicle-type filters, click-to-inspect panel, and WebSocket real-time updates. Builds on existing `RouteMap` component which already supports multi-feed markers and feed health overlay.
**Verify:** `/map` loads full-screen. Feed chips toggle Riga/ATD markers. Clicking a vehicle opens the detail drawer. WebSocket pushes update markers in real-time. Zoom out to all-Latvia → markercluster groups dense areas. Performance: 500+ markers render at 60fps.

---

### Latvia Transit — Phase 2: Full Latvia Coverage ✅ COMPLETE

> **Sprint deliverable:** All available Latvian real-time feeds live on the map, trains visible alongside buses, circuit breakers per feed, and a published GTFS-RT combined feed for third parties. All 4 subtasks complete.

| Subtask | Type | Realistic | Parallel? |
|---------|------|-----------|-----------|
| ~~LV-2.1 Additional city feeds~~ | BE | ✅ Done | ✅ Implemented — pluggable feed client architecture |
| ~~LV-2.2 Train WebSocket~~ | BE+FE | ✅ Done | ✅ Implemented 2026-04-13 — PV train WS listener + CMS train filter |
| ~~LV-2.3 Adaptive polling + breakers~~ | BE | ✅ Done | ✅ Implemented — adaptive intervals + per-feed circuit breakers |
| ~~LV-2.4 GTFS-RT publisher~~ | BE | ✅ Done | ✅ Implemented — combined GTFS-RT VehiclePositions publisher |

#### LV-2.1 Additional City GTFS-RT Feeds ✅ DONE
**Implemented:** Pluggable feed client architecture extending VTV from Riga-only to 4+ cities. Instead of separate scraper/poller files per source type, a single `FeedClient` Protocol + factory pattern dispatches on `TransitFeedConfig.feed_type` discriminator (`"gtfs_rt"` | `"scraper"` | `"gps_text"`). All clients normalize to `VehiclePositionData` — downstream pipeline (enrich -> Redis -> TimescaleDB -> Pub/Sub) is unchanged.
**Files created:** `app/transit/feed_client.py` (Protocol + DaugavpilsScraper + GpsTextClient + factory), `app/transit/tests/test_feed_client.py` (15 tests)
**Files modified:** `app/core/config.py` (FeedType Literal + feed_type field), `app/transit/poller.py` (pluggable _feed_client), `docs/logging-standard.md` (5 new events)
**Input validation (CTX-INPUT):** Latvia bounding box (55.5-58.1 N, 20.5-28.3 E), vehicle_id regex `^[\w\-.:]{1,64}$`, timestamp staleness (24h) / future (5min) bounds. Invalid vehicles skipped with warning log.
**Plan:** `.agents/plans/lv-2-1-additional-city-feeds.md`

#### ~~LV-2.2 Train Positions via WebSocket~~ ✅ Implemented 2026-04-13
**What:** `app/transit/train_ws_listener.py` — WebSocket client connecting to `wss://trainmap.pv.lv/ws` (configurable via `TRAIN_WS_URL`), parses train position messages with defensive field extraction, normalizes to `EnrichedVehicle` dicts with `feed_id="pv_trains"` and `route_type=2` (Rail), writes to Redis + TimescaleDB + Pub/Sub via the same pipeline as the GTFS-RT poller. Exponential backoff reconnection (1s -> 2s -> 4s -> ... -> 60s max, configurable via `TRAIN_WS_RECONNECT_MAX_SECONDS`). CMS frontend adds green rail color (#43A047), "Train" filter option on `/map`, and route_type=2 filtering in vehicle map + full-screen map. 12 unit tests + 12 new log events in taxonomy.
**Plan:** `.agents/plans/lv-2-2-train-ws-listener.md`
**Files created:** `app/transit/train_ws_listener.py`, `app/transit/tests/test_train_ws_listener.py`
**Files modified:** `app/core/config.py` (3 settings), `app/main.py` (lifespan startup/shutdown), `cms/apps/web/src/hooks/use-vehicle-positions.ts` (rail color), `cms/apps/web/src/components/map/map-filters.tsx` (train option), `cms/apps/web/src/components/map/vehicle-map.tsx` (route_type=2 filter), `cms/apps/web/src/app/[locale]/(dashboard)/map/page.tsx` (route_type=2 filter), `cms/apps/web/messages/en.json` + `lv.json` (i18n keys), `docs/logging-standard.md` (12 new events)
**Config:** `TRAIN_WS_ENABLED` (default true), `TRAIN_WS_URL`, `TRAIN_WS_RECONNECT_MAX_SECONDS` (default 60)

#### LV-2.3 Adaptive Polling + Per-Feed Circuit Breakers ✅ DONE
**Implemented:** Hour-of-day adaptive polling intervals (1x peak, 2x off-peak, 4x night) and per-feed `CircuitBreaker` from `app/core/resilience.py` wired into each `FeedPoller` instance. Failing feeds trip independently without affecting healthy feeds. Health probes updated for per-feed staleness thresholds with adaptive-aware ceilings.
**Files created:** `app/transit/tests/test_adaptive_polling.py` (12 tests)
**Files modified:** `app/core/config.py` (3 settings: `transit_adaptive_polling_enabled`, `transit_peak_hours`, `transit_night_hours`), `app/transit/poller.py` (`_parse_hour_ranges()`, `_adaptive_interval()`, per-feed `CircuitBreaker` in `FeedPoller.__init__`, adaptive `run()` loop, per-feed metric labels), `app/core/health.py` (per-feed staleness thresholds, per-feed GTFS-RT freshness probe), `docs/logging-standard.md` (`transit.feed.circuit_open` event)
**Plan:** `.agents/plans/lv-2-3-adaptive-polling-circuit-breakers.md`

#### LV-2.4 GTFS-RT Publisher (Combined Feed) ✅ DONE
**Implemented:** `app/transit/gtfs_rt_publisher.py` — reads live positions from all feeds in Redis, assembles a combined GTFS-RT `FeedMessage` protobuf, and serves it at `GET /api/v1/transit/gtfs-rt/vehicle_positions.pb`. Enables third-party apps to consume VTV's combined Latvia feed.
**Files created:** `app/transit/gtfs_rt_publisher.py` (`build_combined_feed()`, `_read_all_vehicles()`, `_status_to_enum()`), `app/transit/tests/test_gtfs_rt_publisher.py` (10 tests)
**Files modified:** `app/transit/routes.py` (new endpoint), `typings/google/transit/gtfs_realtime_pb2.pyi` (`gtfs_realtime_version` on `FeedHeader`, `id` on `FeedEntity`), `docs/logging-standard.md` (4 new `transit.publisher.*` events)
**Security:** Public endpoint in `PUBLIC_ALLOWLIST`, `feed_id` param validated with `max_length=50, pattern=r"^[\w\-]+$"`, no ILIKE queries.
**Plan:** `.agents/plans/lv-2-4-gtfs-rt-publisher.md`

---

### Latvia Transit — Phase 3: Intercity Gap-Fill (~2 days)

> **Sprint deliverable:** Intercity buses tracked via phone-based (OwnTracks) and hardware (Traccar) GPS, multi-modal journey planning via OpenTripPlanner, and shareable public tracking links.

| Subtask | Type | Realistic | Parallel? |
|---------|------|-----------|-----------|
| LV-3.1 OwnTracks MQTT | BE + infra | ~3h | ✅ Yes — independent |
| LV-3.2 Traccar bridge extension | BE | ~1.5h | ✅ Yes — independent |
| LV-3.3 OpenTripPlanner | BE + FE + infra | ~6h | ✅ Yes — independent |
| LV-3.4 LocShare tracking links | BE + FE | ~3h | ✅ Yes — independent |

#### LV-3.1 OwnTracks MQTT Integration
**What:** Deploy Mosquitto MQTT broker (Docker sidecar), create `app/transit/owntracks_listener.py` — subscribes to OwnTracks position topics, normalizes to `VehiclePositionData`, writes to Redis + TimescaleDB. Admin UI to assign phone → driver → vehicle → route.
**Why:** Fastest path to intercity tracking — drivers install OwnTracks on their phone, zero hardware cost. Gets real positions for routes with no GTFS-RT feed. Proves the concept before investing in Teltonika hardware.
**Implementation:**
- `docker-compose.yml` — add `mosquitto` service (Eclipse Mosquitto, port 1883/8883, password auth)
- `app/transit/owntracks_listener.py`:
  - `OwnTracksListener` class — `asyncio-mqtt` subscribe to `owntracks/+/+`, parse JSON, normalize lat/lon/speed/bearing/timestamp
  - Lookup: `phone_id → vehicle_assignment` from new `vehicle_phone_assignments` table
  - Write pipeline: same as `FeedPoller` (Redis + TimescaleDB + Pub/Sub)
- `alembic/versions/xxx_vehicle_phone_assignments.py` — `vehicle_phone_assignments(id, phone_identifier, vehicle_id FK, route_id FK, driver_id FK, assigned_by, assigned_at, active)`
- `app/transit/routes.py` — 3 new admin endpoints: `POST /v1/transit/phone-assignments`, `GET /v1/transit/phone-assignments`, `DELETE /v1/transit/phone-assignments/{id}`
- `app/core/config.py` — `mqtt_broker_url: str | None = None`, `mqtt_username`, `mqtt_password`, `owntracks_enabled: bool = False`
- 12+ unit tests: MQTT message parsing (3), vehicle assignment lookup (2), normalization (2), Redis write (2), missing assignment handling (1), endpoint auth (2)
**Verify:** Start Mosquitto + app. Publish OwnTracks test message via `mosquitto_pub`. Vehicle appears on `/map` with `source="owntracks"`. Assign phone to vehicle+route via admin API → marker shows route label.

#### LV-3.2 Traccar Hardware GPS Bridge Extension
**What:** Extend existing `app/fleet/bridge.py` Traccar webhook integration to also write transit-compatible positions for fleet devices assigned to transit routes. This bridges hardware GPS (Teltonika FMB920) into the transit map alongside GTFS-RT and OwnTracks sources.
**Why:** Traccar integration already exists for fleet telemetry (Phase 1A). This phase extends it so fleet-tracked intercity buses appear on the transit map — same vehicle, dual purpose. No new infrastructure needed.
**Implementation:**
- `app/fleet/bridge.py` — after writing to `vehicle_positions` with `source="traccar"`, also publish to Redis Pub/Sub channel `transit:vehicles:fleet` if the device's vehicle has an active route assignment
- `vehicle_phone_assignments` table reused (or new `vehicle_transit_assignments` if semantics differ)
- CMS `/map` — fleet-sourced vehicles appear alongside GTFS-RT vehicles, distinguished by source icon
- 6+ unit tests: transit publish for route-assigned devices (2), no publish for non-transit devices (1), dual-write consistency (2), map rendering (1)
**Verify:** Assign a Traccar device to a transit route. Simulated webhook → vehicle appears on `/map` with fleet icon + route label. GTFS-RT vehicles from same route show alongside.

#### LV-3.3 OpenTripPlanner Journey Planning
**What:** Deploy OpenTripPlanner (Docker sidecar) with Latvia GTFS + OSM data. Create `app/transit/journey_planner.py` — proxies OTP's `/plan` API, enriches with VTV's real-time delay data (GTFS-RT trip updates), and exposes as `GET /api/v1/transit/plan`. CMS journey planner UI.
**Why:** Multi-modal journey planning ("walk → bus → train → walk") is the killer feature for a unified transit platform. OTP is the industry standard — self-hosted, open-source, handles GTFS natively.
**Implementation:**
- `docker-compose.yml` — add `otp` service (OpenTripPlanner 2.x, Java 17, Latvia GTFS + OSM extract, port 8080)
- `scripts/build_otp_graph.sh` — downloads Latvia OSM extract + all GTFS ZIPs, builds OTP graph
- `app/transit/journey_planner.py`:
  - `plan_journey(from_lat, from_lon, to_lat, to_lon, depart_at, arrive_by, modes) -> JourneyPlan`
  - Proxies to OTP `/otp/routers/default/plan`, maps response to VTV schema
  - Enriches legs with VTV delay data: for each transit leg, look up current delay from Redis
  - Caches plan results for 60s (same origin/dest/time)
- `app/transit/routes.py` — `GET /api/v1/transit/plan?from=56.95,24.11&to=56.85,24.30&depart=...`
- `app/transit/schemas.py` — `JourneyPlan`, `JourneyLeg`, `JourneyStep` Pydantic models
- CMS: `cms/apps/web/src/app/[locale]/(dashboard)/planner/page.tsx` — origin/destination inputs (geocoded), time picker, results list with map polylines per leg
- 15+ unit tests: OTP proxy (3), delay enrichment (3), caching (2), schema mapping (2), error handling (2), CMS component tests (3)
**Verify:** `GET /api/v1/transit/plan?from=56.9496,24.1052&to=56.5047,21.0109` (Riga→Liepāja) returns multi-modal plan with bus + possible train legs. Delay enrichment shows actual vs scheduled times. CMS planner page renders route on map with colored legs per transport mode.

#### LV-3.4 Shareable Tracking Links (LocShare)
**What:** Create `app/transit/locshare.py` — generates signed JWT tracking links that show a single vehicle's live position on a public page. No auth required to view. Configurable expiry (1h-24h). QR code generation for physical posting at stops.
**Why:** Passengers and operations staff need to share "where is my bus?" without VTV accounts. LocShare links are the public-facing equivalent of the internal `/map` — lightweight, embeddable, expiring.
**Implementation:**
- `app/transit/locshare.py`:
  - `create_share_link(vehicle_id, route_id, expires_in_hours) -> ShareLink` — signs JWT with `vehicle_id` + expiry, stores in `share_links` table
  - `resolve_share_link(token) -> ShareLinkData | None` — validates JWT, returns vehicle_id + route_id
- `alembic/versions/xxx_share_links.py` — `share_links(id, token_hash, vehicle_id, route_id, created_by, expires_at, view_count)`
- `app/transit/routes.py`:
  - `POST /v1/transit/share` (auth required) — create link
  - `GET /v1/transit/share/{token}` (public, no auth) — returns vehicle position JSON
- CMS: `/share/{token}` public page — minimal Leaflet map showing single vehicle, auto-refreshing
- QR code: `qrcode` library, generated on share creation, returned as base64 PNG
- 10+ unit tests: JWT signing/validation (3), expiry enforcement (2), view count increment (1), public access (2), QR generation (2)
**Verify:** Create share link via API. Open `/share/{token}` in incognito — vehicle visible on minimal map, updating live. Wait past expiry — returns 410 Gone. QR code scans to the same URL.

---

### Knowledge Base Improvements (~6 hours)

> **Sprint deliverable:** PPTX extraction, Latvian-aware BM25 stemming, document versioning, search feedback loop, and knowledge graph overlay. Completes the RAG pipeline with full document format coverage and language-aware retrieval.
> Plan: [docs/PLANNING/rag-improvements.md](PLANNING/rag-improvements.md)

| Subtask | Type | Realistic | Parallel? |
|---------|------|-----------|-----------|
| KB-1 PPTX extractor | BE | ~30min | ✅ Yes — independent |
| KB-2 Latvian lemmatizer | BE | ~1.5h | ✅ Yes — independent |
| KB-3 Document versioning | BE | ~1.5h | ✅ Yes — independent |
| KB-4 Search feedback loop | BE + FE | ~1.5h | ✅ Yes — independent |
| KB-5 Entity/knowledge graph | BE | ~1.5h | ✅ Yes — independent |

#### KB-1 PPTX Extractor
**What:** Add PowerPoint support to `app/knowledge/processing.py` — extract text from slides (titles, body, notes, tables, grouped shapes) preserving slide order and heading structure for the semantic chunker.
**Why:** Operations teams share SOPs and training materials as PPTX. Currently these must be manually converted to PDF/DOCX before upload. PPTX is the last major office format missing (PDF, DOCX, XLSX, CSV, email, images already supported).
**Implementation:**
- `pyproject.toml` — add `python-pptx ^1.0`
- `app/knowledge/processing.py`:
  - New `_extract_pptx(file_path) -> str` function — iterates slides, extracts `slide.shapes` text (title + body + table cells + notes), formats as markdown with `# Slide N: {title}` headings
  - Register `"pptx"` in `SUPPORTED_TYPES` and MIME type mapping
  - `asyncio.to_thread()` wrapper (same pattern as other extractors)
- `app/knowledge/routes.py` — add `application/vnd.openxmlformats-officedocument.presentationml.presentation` to allowed MIME types
- 8+ unit tests: basic extraction (1), tables in slides (1), notes extraction (1), grouped shapes (1), empty slides (1), heading structure (1), MIME type acceptance (1), round-trip with chunker (1)
**Verify:** Upload a 20-slide PPTX with mixed content (titles, bullet lists, tables, speaker notes). Extracted text preserves slide order with markdown headings. Chunks have `heading_path` like "Slide 3: Safety Procedures > Evacuation Protocol". Search finds content from slide body text.

#### KB-2 Latvian UDPipe Lemmatizer for BM25
**What:** Integrate UDPipe Latvian model into fulltext search to enable proper BM25 stemming. Current `to_tsvector('simple', ...)` treats Latvian as unstemmed tokens — "autobuss", "autobusam", "autobusu" are 3 separate terms. Lemmatization collapses them to "autobuss".
**Why:** Latvian is a highly inflected language (7 noun cases, 6 verb conjugations). Without lemmatization, BM25 recall is ~40% lower than English on equivalent queries. This is the single highest-impact retrieval improvement remaining after HyDE.
**Implementation:**
- `pyproject.toml` — add `ufal.udpipe ^1.3` (C++ bindings, ~50MB model)
- `app/knowledge/lemmatizer.py` (new):
  - `LemmaTokenizer` class — loads UDPipe Latvian model on init, exposes `lemmatize(text: str) -> list[str]`
  - Language detection: if text is Latvian (from document `language` field), use UDPipe; else fall back to `simple` tsvector
  - Singleton with lazy model loading (same pattern as reranker warm-up)
- `app/knowledge/repository.py`:
  - `_build_tsvector()` — for Latvian documents, pre-lemmatize the text and use the lemmatized tokens with `to_tsvector('simple', lemmatized_text)` instead of raw text
  - `_build_tsquery()` — lemmatize the query terms before building `plainto_tsquery`
- `alembic/versions/xxx_add_lemmatized_tsvector.py` — add `lemmatized_content` column on `document_chunks` (populated during chunking, updated on re-chunk)
- `app/knowledge/chunking.py` — compute `lemmatized_content` during chunk creation
- `app/core/config.py` — `latvian_lemmatizer_enabled: bool = True`, `udpipe_model_path: str = "models/latvian-ud-2.5.udpipe"`
- 12+ unit tests: lemmatization accuracy (4 — noun cases, verb conjugations, compound words, mixed LV/EN), tsvector generation (2), search recall improvement (2), fallback for non-Latvian (2), model loading (2)
**Verify:** Index a Latvian SOP document. Search "autobusu apkope" (bus maintenance) — matches document containing "autobuss" and "apkopē". Compare recall@3 with/without lemmatizer on 20 Latvian QA pairs — expect 15-20% improvement.

#### KB-3 Document Versioning with Diff-Aware Search
**What:** Add version tracking to documents — re-uploading a document with the same title creates a new version rather than overwriting. Search results annotate which version matched. Diff view shows what changed between versions.
**Why:** SOPs and regulations are updated periodically. Currently re-upload overwrites — the old version is lost. Dispatchers need to know "was this procedure updated recently?" and "what changed?".
**Implementation:**
- `alembic/versions/xxx_document_versions.py` — add `version: int = 1` and `parent_document_id: int | None` (FK to self) to `documents` table. New index on `(title, version DESC)`.
- `app/knowledge/service.py`:
  - `ingest_document()` — detect same-title document, increment version, set `parent_document_id`, re-chunk new version, mark old version as `superseded` (keep chunks for historical search)
  - `get_document_versions(document_id) -> list[DocumentVersion]` — version history
  - `get_document_diff(doc_id, version_a, version_b) -> DocumentDiff` — difflib unified diff of extracted text
- `app/knowledge/routes.py` — `GET /v1/documents/{id}/versions`, `GET /v1/documents/{id}/diff?v1=1&v2=2`
- Search results: annotate with `version` and `is_latest` flag. By default search only latest versions; `include_superseded=true` param for historical search.
- 10+ unit tests: version creation (2), superseded marking (1), diff generation (2), search latest-only (2), search with superseded (1), version history endpoint (2)
**Verify:** Upload "SOP-001.pdf" v1. Upload updated "SOP-001.pdf" — creates v2, v1 marked superseded. Search returns v2 by default. `GET /v1/documents/{id}/diff?v1=1&v2=2` shows unified diff. `GET /v1/documents/{id}/versions` lists both.

#### KB-4 Search Feedback Loop
**What:** Add thumbs-up/down feedback on search results. Aggregate feedback to auto-tune RRF weights per query type (keyword/semantic/mixed) — queries where users consistently prefer vector results shift weight toward vector, and vice versa.
**Why:** RRF weights are currently static (configured in AI-1.3). Real usage patterns differ from assumptions — keyword-heavy queries may need more fulltext weight than the default. Feedback-driven tuning closes the loop without manual A/B testing.
**Implementation:**
- `alembic/versions/xxx_search_feedback.py` — `search_feedback(id, query_hash, chunk_id, relevant: bool, query_type, created_at)`
- `app/knowledge/routes.py` — `POST /v1/knowledge/search/{query_hash}/feedback` with `{chunk_id, relevant: bool}`
- `app/knowledge/feedback.py` (new):
  - `record_feedback(query_hash, chunk_id, relevant)` — store + aggregate
  - `get_tuned_weights(query_type) -> RRFWeights` — compute from last 30 days of feedback: if vector results get more thumbs-up for `keyword` queries, shift `fulltext_weight` down and `vector_weight` up
  - Background task: recompute weights daily, store in Redis `rrf:weights:{query_type}`
- `app/knowledge/service.py` — read tuned weights from Redis before each search (fallback to config defaults)
- CMS chat UI: add small 👍/👎 buttons next to cited sources in agent responses
- 10+ unit tests: feedback storage (2), weight computation (3), fallback to defaults (1), daily recompute (2), CMS feedback submission (2)
**Verify:** Submit 20 feedback signals (mostly thumbs-up on vector results for keyword queries). Run weight recompute → `vector_weight` for keyword queries increases. Next search uses tuned weights. Reset feedback → falls back to config defaults.

#### KB-5 Entity/Knowledge-Graph Overlay
**What:** Extract named entities (routes, stops, people, regulations) from documents during chunking, store as a lightweight knowledge graph (`entities` + `entity_mentions` tables), and use entity co-occurrence to boost search results that share entities with the query.
**Why:** Transit documents heavily reference shared entities — "Route 22", "Brīvības iela", "EU Regulation 561/2006". When a dispatcher asks about Route 22, chunks mentioning Route 22 should rank higher even if the embedding similarity is moderate. Entity-aware retrieval bridges the semantic gap.
**Implementation:**
- `alembic/versions/xxx_entities.py` — `entities(id, name, entity_type, normalized_name)`, `entity_mentions(id, entity_id FK, chunk_id FK, mention_count)`. Index on `(entity_type, normalized_name)`.
- `app/knowledge/entity_extractor.py` (new):
  - `extract_entities(text: str, language: str) -> list[EntityMention]` — regex-based for routes (`maršrut\w*\s+\d+`), stops (known stop names from GTFS), regulations (`EU\s+\d+/\d+`), plus spaCy NER for people/organizations if `spacy` available (optional dependency)
  - Normalize: "Route 22" = "route_22", "maršruts 22" = "route_22"
- `app/knowledge/chunking.py` — call entity extractor during chunk creation, store mentions
- `app/knowledge/repository.py` — entity co-occurrence boost in hybrid search: if query mentions entity X, chunks with `entity_mentions` for X get a score boost (configurable multiplier)
- `app/core/config.py` — `entity_boost_enabled: bool = True`, `entity_boost_multiplier: float = 1.3`
- 12+ unit tests: route extraction (3), stop name extraction (2), regulation extraction (2), normalization (2), search boost (2), no-entity fallback (1)
**Verify:** Index a document mentioning "Route 22" and "Brīvības iela". Search "Route 22 delays" → chunks mentioning Route 22 boosted above generic delay chunks. Entity table shows extracted entities with mention counts. Disable boost → ranking reverts to pure RRF.

---

### SOP & File Automation (~1 day)

> **Sprint deliverable:** Automated document ingestion from folders, email, and web sources. LLM-powered SOP generation from operational data. Saves ~47 hrs/month human time.
> Plan: [docs/PLANNING/sop-file-automation.md](PLANNING/sop-file-automation.md)

| Subtask | Type | Realistic | Parallel? |
|---------|------|-----------|-----------|
| SOP-1 Folder watcher | BE | ~1.5h | ✅ Yes — independent |
| SOP-2 Email monitor | BE | ~1.5h | ✅ Yes — independent |
| SOP-3 Web scraper | BE | ~1.5h | ✅ Yes — independent |
| SOP-4 GTFS schedule sync | BE | ~1.5h | ✅ Yes — LV-1.2 done, unblocked |
| SOP-5 LLM SOP generation | BE + FE | ~2h | ✅ Yes — independent |

#### SOP-1 Folder Watcher (Auto-Ingest)
**What:** Background task that monitors `/data/knowledge-inbox/{domain}/` directories. New files are auto-ingested into the knowledge base with domain inferred from folder name, language auto-detected, and duplicate detection via file hash.
**Why:** Current ingestion requires manual upload via CMS or API. Operations staff drop files into shared folders — a watcher bridges the gap with zero workflow change.
**Implementation:**
- `app/knowledge/watcher.py` (new):
  - `FolderWatcher` class — polls configured inbox paths every 60s via `pathlib.Path.iterdir()`
  - On new file: compute SHA-256, check against `documents.file_hash` to skip duplicates, call `KnowledgeService.ingest_document()`, move file to `processed/` subfolder
  - Domain: derived from folder name (`/data/knowledge-inbox/operations/` → `domain="operations"`)
  - Language: auto-detect via existing `langdetect` or simple heuristic (Latvian diacritics → `lv`, else `en`)
- `app/core/config.py` — `knowledge_inbox_path: str = "/data/knowledge-inbox"`, `knowledge_watcher_enabled: bool = False`, `knowledge_watcher_interval_s: int = 60`
- `app/main.py` — register `start_folder_watcher()` in lifespan, gated by config
- `docker-compose.yml` — mount `document_data` volume to include inbox path
- 10+ unit tests: file detection (2), domain inference (2), duplicate skip (2), move to processed (1), language detection (1), error handling (2)
**Verify:** Drop a PDF into `/data/knowledge-inbox/operations/`. Within 60s, document appears in knowledge base with `domain="operations"`. Drop same file again — skipped (duplicate hash). File moved to `processed/` subfolder.

#### SOP-2 Email Inbox Monitor
**What:** Background task that polls `documents@vtv.lv` via IMAP, downloads attachments, and auto-ingests them into the knowledge base. Subject line parsed for domain tags (`[operations]`, `[maintenance]`).
**Why:** Staff forward documents via email. An inbox monitor captures these without requiring them to learn the CMS upload workflow.
**Implementation:**
- `app/knowledge/email_monitor.py` (new):
  - `EmailMonitor` class — `aioimaplib` IMAP connection, polls every 5 min, fetches UNSEEN messages
  - For each message: extract attachments, parse subject for `[domain]` tag, call `KnowledgeService.ingest_document()` per attachment
  - Mark processed messages as SEEN; on failure, mark as FLAGGED for manual review
  - Structured logging: `knowledge.email.ingested`, `knowledge.email.failed`, `knowledge.email.skipped_no_attachment`
- `app/core/config.py` — `knowledge_email_enabled: bool = False`, `knowledge_email_imap_host`, `knowledge_email_imap_user`, `knowledge_email_imap_password`, `knowledge_email_poll_interval_s: int = 300`
- 8+ unit tests: IMAP message parsing (2), attachment extraction (2), domain tag parsing (2), duplicate handling (1), error recovery (1)
**Verify:** Send email with PDF attachment to `documents@vtv.lv` with subject `[operations] New SOP`. Within 5 min, document appears in knowledge base with `domain="operations"`. Send email without attachment — logged as skipped.

#### SOP-3 Web Scraper for Transit Regulations
**What:** Scheduled scraper that monitors key transit regulation pages (ATD, MK noteikumi, EU regulations) for changes. On change, downloads updated content, extracts text, and ingests as a new document version (using KB-3 versioning).
**Why:** Transit regulations change without notification. Dispatchers need current versions in the knowledge base without manually checking government websites.
**Implementation:**
- `app/knowledge/web_scraper.py` (new):
  - `RegulationScraper` class — configured list of `(url, selector, domain, title)` tuples
  - Fetches page, extracts text via CSS selector, computes content hash, compares with last ingested version
  - On change: create new document version via `KnowledgeService.ingest_document()`
- `app/core/config.py` — `knowledge_scraper_enabled: bool = False`, `knowledge_scraper_targets_json: str = "[]"`
- Background task: daily at 06:00 UTC
- 8+ unit tests: content extraction (2), change detection (2), version creation (2), no-change skip (1), HTTP error handling (1)
**Verify:** Configure scraper target for a test URL. Change page content → next run creates new document version. No change → skip logged. Version history shows both versions.

#### SOP-4 GTFS Schedule Sync
**What:** Auto-ingest GTFS schedule changes as knowledge base documents when the daily GTFS import detects route/stop changes. Generates a human-readable changelog ("Route 22: 3 new stops added, frequency increased weekdays 7-9") that dispatchers can search.
**Why:** Schedule changes are the #1 source of dispatcher questions. Currently they must manually read GTFS diffs. Auto-generated changelogs make schedule updates searchable via the agent.
**Implementation:**
- `app/knowledge/gtfs_sync.py` (new):
  - `generate_schedule_changelog(old_feed, new_feed) -> str` — diffs routes, stops, frequencies between GTFS versions
  - Produces markdown with sections per changed route
  - Calls `KnowledgeService.ingest_document(title=f"Schedule Update {date}", domain="schedules")`
- Wire into `app/schedules/service.py::import_feed()` — after successful import, generate changelog if changes detected
- 8+ unit tests: route addition detection (2), stop removal detection (2), frequency change detection (2), no-change skip (1), markdown format (1)
**Verify:** Import a GTFS feed. Modify a route's stop list in the feed. Re-import → changelog document created. Agent query "What changed in the schedule today?" → returns the changelog.

#### SOP-5 LLM-Powered SOP Generation
**What:** Pipeline that takes operational incident reports (from alerts) and generates draft SOPs. Dispatcher reviews and approves before publishing to the knowledge base. Uses fast-tier LLM with transit-domain prompting.
**Why:** After each incident, operations staff should write an SOP to prevent recurrence. In practice, 80% of incidents never get an SOP because writing them takes 30-60 minutes. LLM generation reduces this to 5 minutes of review.
**Implementation:**
- `app/knowledge/sop_generator.py` (new):
  - `generate_sop_draft(incident_description: str, alert_data: dict | None) -> SOPDraft` — LLM generates structured SOP (title, scope, procedure steps, responsible roles, related routes/stops)
  - Uses `resolve_tier_model("fast")` — cheap, 500-800 tokens per SOP
  - Returns `SOPDraft(title, content_markdown, domain, suggested_tags)` for human review
- `app/knowledge/routes.py` — `POST /v1/knowledge/generate-sop` (admin/dispatcher), `POST /v1/knowledge/publish-sop` (admin, publishes draft to KB)
- CMS: "Generate SOP" button in alerts detail view → opens editor with pre-filled draft → "Publish" saves to KB
- 8+ unit tests: generation with alert context (2), generation without alert (1), structured output validation (2), publish flow (2), LLM error fallback (1)
**Verify:** Trigger a test alert. Click "Generate SOP" in CMS → LLM generates draft SOP with procedure steps. Edit title → click Publish → document appears in knowledge base. Agent query about the procedure → returns the SOP.

---

### Fleet Management — Phase 2: Fuel + Analytics (~2 days)

> **Sprint deliverable:** Fuel monitoring with refueling/drain detection from OBD-II, fleet analytics (distance, drive time, idle time), LocShare public tracking links, and PDF/CSV report export. CMS: fuel dashboard + analytics pages.
> Plan: [docs/PLANNING/fleet-management-tracking.md](PLANNING/fleet-management-tracking.md) (Phase 2)

| Subtask | Type | Realistic | Parallel? |
|---------|------|-----------|-----------|
| FLEET-2.1 Fuel monitoring | BE | ~4h | ✅ Yes — independent |
| FLEET-2.2 Fleet analytics | BE + FE | ~5h | ✅ Yes — independent |
| FLEET-2.3 LocShare fleet | BE + FE | ~3h | ⚠️ After LV-3.4 (reuses LocShare infra) |

#### FLEET-2.1 Fuel Monitoring + Refueling/Drain Detection
**What:** Create `app/fleet/fuel.py` — processes `fuel_level_pct` from OBD-II telemetry (already parsed in `bridge.py`), detects refueling events (>10% jump in 5 min), fuel drain events (>5% drop without engine running), and stores fuel log entries. Threshold-based alerts via existing alerts system.
**Why:** Fuel is the #1 fleet operating cost. Detecting unauthorized drains saves money; tracking consumption per vehicle identifies maintenance issues. The OBD data already flows through `bridge.py` — this phase adds interpretation.
**Implementation:**
- `alembic/versions/xxx_fuel_logs.py` — `fuel_logs(id, vehicle_id FK, recorded_at, fuel_level_pct, event_type ["reading","refuel","drain","consumption"], delta_pct, odometer_km, location GEOGRAPHY(POINT))`
- `app/fleet/fuel.py`:
  - `FuelMonitor` class — maintains per-vehicle fuel state in Redis (`fleet:fuel:{vehicle_id}`)
  - `process_fuel_reading(vehicle_id, fuel_pct, speed, odometer, lat, lon)` — called from `bridge.py` on each Traccar webhook
  - Refuel detection: `delta > 10%` within 5 min window + vehicle stopped
  - Drain detection: `delta < -5%` + engine off (speed=0, RPM=0)
  - Consumption tracking: `delta < 0` + engine on → normal consumption entry
- `app/fleet/routes.py` — `GET /v1/fleet/vehicles/{id}/fuel-log?from=&to=`, `GET /v1/fleet/vehicles/{id}/fuel-summary` (total consumed, avg consumption L/100km, refuel count, drain alerts)
- Alert integration: `"fuel_drain"` alert type registered with existing `AlertRuleType`
- 15+ unit tests: refuel detection (3), drain detection (3), consumption tracking (2), Redis state management (2), alert integration (2), edge cases (no prior reading, stale data) (3)
**Verify:** Simulate Traccar webhook sequence: 50% → 50% → 48% → 45% → 90% (refuel) → 88% → 30% (drain). Fuel log shows consumption entries, 1 refuel event, 1 drain alert fired. `GET /v1/fleet/vehicles/{id}/fuel-summary` returns accurate totals.

#### FLEET-2.2 Fleet Analytics (Distance, Drive Time, Idle Time)
**What:** Create `app/fleet/analytics.py` — computes per-vehicle and fleet-wide metrics from `vehicle_positions` TimescaleDB data: total distance (Haversine sum), drive time (speed > 3 km/h), idle time (engine on + speed < 3), trip count, and country mileage (PostGIS country polygon intersection for cross-border tracking).
**Why:** Fleet managers need daily/weekly/monthly KPIs per vehicle and fleet-wide. These metrics drive maintenance scheduling (high-mileage vehicles), driver performance review (excessive idle time), and billing (country mileage for international routes).
**Implementation:**
- `app/fleet/analytics.py`:
  - `compute_vehicle_analytics(vehicle_id, from_ts, to_ts) -> VehicleAnalytics` — TimescaleDB window queries over `vehicle_positions`
  - `compute_fleet_analytics(from_ts, to_ts) -> FleetAnalytics` — aggregate across all fleet vehicles
  - Distance: `SUM(ST_Distance(lag(pos), pos))` window function
  - Drive time: `SUM(CASE WHEN speed_kmh > 3 THEN interval ELSE 0 END)`
  - Idle time: `SUM(CASE WHEN speed_kmh < 3 AND obd_data->>'rpm' > '0' THEN interval ELSE 0 END)`
- `app/fleet/routes.py` — `GET /v1/fleet/analytics?from=&to=&vehicle_id=` (admin/dispatcher)
- CMS: `cms/apps/web/src/app/[locale]/(dashboard)/fleet/analytics/page.tsx` — fleet KPI cards + per-vehicle table + Recharts time series
- PDF/CSV export: `GET /v1/fleet/analytics/export?format=pdf|csv&from=&to=` — generates report via `reportlab` (PDF) or stdlib `csv`
- 15+ unit tests: distance calculation (3), drive/idle time (3), fleet aggregation (2), export format (2), TimescaleDB query (2), CMS component tests (3)
**Verify:** With 7 days of test position data, `GET /v1/fleet/analytics` returns per-vehicle distance, drive time, idle time. Export as PDF — opens with correct tables and charts. Fleet summary matches sum of individual vehicles.

#### FLEET-2.3 LocShare Public Tracking Links
**What:** Extend LV-3.4 LocShare pattern for fleet vehicles — create time-limited public tracking links for fleet devices. Adds fleet-specific metadata (device IMEI, OBD telemetry overlay) and dwell time tracking at LocPoints (geofence-based).
**Why:** Fleet operators need to share vehicle tracking with clients ("your delivery vehicle is here") without giving them VTV access. Reuses the LV-3.4 LocShare infrastructure but adds fleet-specific OBD overlay and dwell tracking.
**Implementation:**
- Extend `app/transit/locshare.py` with `source="fleet"` variant
- Fleet share links include OBD telemetry overlay (speed, fuel level, engine status) if `include_telemetry=true`
- `app/fleet/routes.py` — `POST /v1/fleet/vehicles/{id}/share` (creates fleet LocShare link)
- Dwell tracking: when a shared vehicle enters a geofence (LocPoint), record `dwell_start` time; display dwell duration on the public share page
- CMS: share link management page under `/fleet` with copy-to-clipboard and QR code
- 8+ unit tests: fleet share creation (2), telemetry overlay (2), dwell tracking (2), expiry (1), QR code (1)
**Verify:** Create fleet share link. Public page shows vehicle + OBD gauges (speed, fuel). Vehicle enters a geofence → dwell timer starts on share page. Link expires → 410 Gone.

---

### Fleet Management — Phase 3: Tachograph + Driving Hours (~2.5 days)

> **Sprint deliverable:** `app/tachograph/` vertical slice with remote DDD file download, binary parser, EU 561/2006 driving hours calculator, infringement detection, and compliance dashboard.
> Plan: [docs/PLANNING/fleet-management-tracking.md](PLANNING/fleet-management-tracking.md) (Phase 3)

| Subtask | Type | Realistic | Parallel? |
|---------|------|-----------|-----------|
| TACHO-1 DDD download + parser | BE | ~6h | ✅ Yes — independent |
| TACHO-2 EU 561 driving hours | BE | ~5h | ⚠️ After TACHO-1 (needs parsed activities) |
| TACHO-3 Compliance dashboard | FE | ~4h | ⚠️ After TACHO-2 (needs compliance API) |

#### TACHO-1 DDD File Download + Parser
**What:** Create `app/tachograph/` vertical slice. `ddd_downloader.py` fetches DDD files from Teltonika Web Tacho or flespi API. `ddd_parser.py` parses the binary DDD format (EU regulation 3821/85 Annex 1B) into structured activity records (driving, rest, work, availability) with driver card data.
**Why:** EU regulation requires digital tachograph data download every 28 days (driver card) and 90 days (vehicle unit). Manual download requires physical presence at each vehicle. Remote download via Teltonika Web Tacho automates this.
**Implementation:**
- `app/tachograph/` — full VSA: `models.py`, `schemas.py`, `repository.py`, `service.py`, `routes.py`, `tests/`
- `app/tachograph/ddd_downloader.py` — `download_ddd(device_imei, period) -> bytes` via Teltonika Web Tacho REST API or flespi DDD API
- `app/tachograph/ddd_parser.py` — binary parser for DDD format: `parse_ddd(raw: bytes) -> TachographData` with `driver_activities: list[Activity]`, `driver_card: DriverCardData`, `vehicle_data: VehicleData`
- `alembic/versions/xxx_tachograph.py` — `tachograph_downloads(id, device_id FK, driver_id FK, downloaded_at, period_start, period_end, file_hash, file_path)`, `driver_activities(id, download_id FK, activity_type, started_at, ended_at, duration_minutes, location)`
- `app/tachograph/routes.py` — `POST /v1/tachograph/download/{device_id}` (trigger download), `GET /v1/tachograph/downloads` (list), `GET /v1/tachograph/downloads/{id}/activities` (parsed activities)
- `app/core/config.py` — `tachograph_enabled: bool = False`, `tachograph_provider: Literal["teltonika_web_tacho", "flespi"]`, API credentials
- 20+ unit tests: DDD binary parsing (8), API download mock (3), activity extraction (4), schema validation (3), endpoint auth (2)
**Verify:** Mock DDD file from Teltonika. `POST /v1/tachograph/download/{device_id}` triggers download, parses binary, stores activities. `GET /v1/tachograph/downloads/{id}/activities` returns structured driving/rest periods with timestamps.

#### TACHO-2 EU 561/2006 Driving Hours Calculator
**What:** Create `app/tachograph/compliance.py` — implements the EU 561/2006 driving hours rules: daily driving max 9h (extendable to 10h twice/week), weekly max 56h, biweekly max 90h, daily rest min 11h (reducible to 9h three times between rests), weekly rest min 45h. Detects infringements with severity classification.
**Why:** Non-compliance results in fines (€500-€5000 per infringement in Latvia) and insurance invalidation. Automated calculation replaces manual spreadsheet tracking and catches violations before they happen.
**Implementation:**
- `app/tachograph/compliance.py`:
  - `DrivingHoursCalculator` class — takes `list[Activity]`, computes running totals against EU 561/2006 thresholds
  - `check_compliance(driver_id, date_range) -> ComplianceReport` — returns current status + list of infringements + remaining allowances
  - `Infringement(frozen=True)` — `type` (daily_driving_exceeded, weekly_exceeded, biweekly_exceeded, insufficient_daily_rest, insufficient_weekly_rest), `severity` (minor/serious/very_serious per EU classification), `actual_value`, `limit_value`, `occurred_at`
  - `RemainingAllowance(frozen=True)` — `daily_driving_remaining_minutes`, `weekly_driving_remaining_minutes`, `next_required_rest_at`
- `app/tachograph/routes.py` — `GET /v1/tachograph/compliance/{driver_id}` (current status), `GET /v1/tachograph/compliance/{driver_id}/infringements?from=&to=`
- Alert integration: `"driving_hours_exceeded"` alert type, fires when remaining allowance < 30 min
- 25+ unit tests: each EU rule (8), edge cases (split rest, reduced daily rest counting) (5), infringement severity classification (4), remaining allowance calculation (3), multi-week rolling window (3), alert trigger (2)
**Verify:** Create driver activities: 9h driving + 11h rest + 9h driving + 11h rest + 10h driving (3rd day exceeds without extension). Calculator detects `daily_driving_exceeded` infringement. Check weekly totals after 56h → `weekly_exceeded` detected. Remaining allowance shows correct minutes.

#### TACHO-3 Compliance Dashboard (CMS)
**What:** CMS page at `/tachograph` — driver compliance overview (traffic light status per driver), activity timeline (Gantt-style per day), DDD download management, and infringement report with severity badges.
**Why:** Fleet managers need at-a-glance compliance visibility. Current process is per-driver manual checking. A dashboard with red/amber/green status per driver and drill-down to activities replaces this.
**Implementation:**
- `cms/apps/web/src/app/[locale]/(dashboard)/tachograph/page.tsx`:
  - Driver compliance table: name, today's driving hours, weekly total, status (green/amber/red), next required rest
  - Click driver → activity timeline (Recharts Gantt: driving=blue, rest=green, work=orange, availability=grey)
  - DDD downloads tab: list downloads, trigger new download, view parsed activities
  - Infringement report: filterable by driver/date/severity, exportable as PDF
- SDK: `@vtv/sdk` wrappers for tachograph endpoints
- `cms/apps/web/messages/lv.json` + `en.json` — ~60 new i18n keys
- RBAC: admin + dispatcher roles
- 10+ component tests
**Verify:** `/tachograph` loads with driver list showing compliance status. Click a driver → activity timeline renders correctly. Trigger DDD download → progress indicator → activities appear. Export infringement report as PDF.

---

### Fleet Management — Phase 4: Routing (~1 day)

> **Sprint deliverable:** Self-hosted OSRM with Latvia OSM data for fast routing, HERE Maps API fallback for truck-specific routing, and a CMS route planning UI.
> Plan: [docs/PLANNING/fleet-management-tracking.md](PLANNING/fleet-management-tracking.md) (Phase 4)

| Subtask | Type | Realistic | Parallel? |
|---------|------|-----------|-----------|
| ROUTE-1 OSRM + HERE fallback | BE + infra | ~4h | ✅ Yes — independent |
| ROUTE-2 Route planning UI | FE | ~3h | ⚠️ After ROUTE-1 (needs routing API) |

#### ROUTE-1 OSRM Self-Hosted + HERE Fallback
**What:** Deploy OSRM (Open Source Routing Machine) as Docker sidecar with pre-built Latvia OSM graph. Create `app/fleet/routing.py` — routing service that tries OSRM first, falls back to HERE Fleet Telematics API for truck-specific routing (height/weight restrictions, toll costs).
**Why:** Routing is needed for fleet analytics (actual vs shortest distance), trip optimization, and ETA calculation. OSRM is fast (sub-10ms) and free for car routing; HERE adds truck restrictions and toll data at API cost.
**Implementation:**
- `docker-compose.yml` — add `osrm` service (osrm/osrm-backend, port 5000, pre-built Latvia graph)
- `scripts/build_osrm_graph.sh` — downloads Latvia OSM extract from Geofabrik, runs `osrm-extract` + `osrm-contract`
- `app/fleet/routing.py`:
  - `RoutingService` class — `route(origin, destination, vehicle_type) -> RouteResult`
  - OSRM path: `GET /route/v1/driving/{lon1},{lat1};{lon2},{lat2}` → parse distance, duration, polyline
  - HERE fallback: `GET /v8/routes?origin=...&destination=...&transportMode=truck` with `truck[height/weight/length]` params
  - `RouteResult(frozen=True)` — `distance_km`, `duration_minutes`, `polyline`, `toll_cost_eur` (HERE only), `source: "osrm"|"here"`
- `app/fleet/routes.py` — `POST /v1/fleet/route` with origin/destination/vehicle_type
- `app/core/config.py` — `osrm_url: str = "http://osrm:5000"`, `here_api_key: str | None = None`, `routing_fallback_to_here: bool = True`
- 12+ unit tests: OSRM routing (3), HERE fallback (2), polyline parsing (2), toll cost (1), vehicle type selection (2), error handling (2)
**Verify:** `POST /v1/fleet/route` with Riga→Liepāja → returns OSRM route with distance + polyline. Set `vehicle_type=truck` with HERE key configured → returns truck route with toll cost. Kill OSRM → falls back to HERE seamlessly.

#### ROUTE-2 CMS Route Planning UI
**What:** CMS page at `/fleet/planner` — map-based route planner with drag-and-drop waypoints, vehicle type selector, and optimization toggle (shortest vs fastest). Renders route polyline on Leaflet map with distance/time/toll summary.
**Why:** Dispatchers plan service vehicle routes daily. Currently done via Google Maps or paper. An integrated planner with fleet-specific truck routing saves time and accounts for vehicle restrictions.
**Implementation:**
- `cms/apps/web/src/app/[locale]/(dashboard)/fleet/planner/page.tsx`:
  - Leaflet map with click-to-add waypoints (origin, destination, intermediate stops)
  - Drag-and-drop waypoint reordering
  - Vehicle type selector (car/truck/bus) — truck shows height/weight inputs
  - "Optimize" button calls routing API, renders polyline + summary card
  - Save route for later use (optional)
- SDK: wrapper for `POST /v1/fleet/route`
- ~30 i18n keys
- 6+ component tests
**Verify:** Click two points on map → route polyline renders with distance/time. Add intermediate waypoint → route recalculates. Select truck type → route avoids low bridges (if HERE is configured). Summary shows total distance + duration.

---

### Fleet Management — Phase 5: Mobile App + Messaging (~2 days)

> **Sprint deliverable:** Dispatcher↔driver messaging system and React Native mobile app for drivers with live map, alerts, messaging, and task management.
> Plan: [docs/PLANNING/fleet-management-tracking.md](PLANNING/fleet-management-tracking.md) (Phase 5)

| Subtask | Type | Realistic | Parallel? |
|---------|------|-----------|-----------|
| MSG-1 Messaging vertical slice | BE | ~5h | ✅ Yes — independent |
| MSG-2 React Native mobile app | Mobile | ~8h | ⚠️ After MSG-1 (needs messaging API) |

#### MSG-1 Messaging Vertical Slice
**What:** Create `app/messaging/` vertical slice — real-time dispatcher↔driver messaging with message persistence, read receipts, and task assignment. WebSocket delivery with offline queue for drivers with intermittent connectivity.
**Why:** Dispatchers currently communicate with drivers via phone calls or personal WhatsApp — no audit trail, no task tracking, no integration with the fleet system. Structured messaging enables task assignment with acknowledgment.
**Implementation:**
- `app/messaging/` — full VSA: `models.py`, `schemas.py`, `repository.py`, `service.py`, `routes.py`, `tests/`
- `alembic/versions/xxx_messaging.py`:
  - `conversations(id, type ["direct","group","broadcast"], title, created_by FK, created_at)`
  - `conversation_members(conversation_id FK, user_id FK, role ["admin","member"], joined_at)`
  - `messages(id, conversation_id FK, sender_id FK, content, message_type ["text","task","alert","system"], task_data JSONB, sent_at, edited_at)`
  - `message_read_receipts(message_id FK, user_id FK, read_at)`
- `app/messaging/ws_handler.py` — WebSocket endpoint `WS /v1/messaging/ws` with JWT auth, delivers new messages in real-time, handles typing indicators
- `app/messaging/routes.py` — 8 REST endpoints: list conversations, create conversation, send message, get messages (paginated), mark read, create task message, get unread count, search messages
- `app/messaging/task_service.py` — task messages with status tracking (assigned → acknowledged → in_progress → completed)
- Push queue: messages to offline users stored in `message_queue` table, delivered on next WS connect
- 20+ unit tests: CRUD (5), WebSocket delivery (3), read receipts (2), task lifecycle (4), offline queue (2), auth (2), pagination (2)
**Verify:** Dispatcher sends message to driver via CMS. Driver (on mobile/test WS client) receives in real-time. Driver reads → read receipt appears for dispatcher. Dispatcher creates task → driver acknowledges → status updates to "acknowledged". Driver goes offline → message queued → delivered on reconnect.

#### MSG-2 React Native Mobile App
**What:** React Native mobile app for drivers — live fleet map, alerts feed, messaging inbox, task list, and OwnTracks-compatible position reporting. Authentication via VTV JWT (same as CMS).
**Why:** Drivers need a mobile interface for messaging, alerts, and tasks. The mobile app also replaces OwnTracks for position reporting — one app for communication and tracking instead of two separate apps.
**Implementation:**
- `mobile/` — new directory at repo root, React Native (Expo) project
- Screens: Login, Map (live vehicle positions), Alerts (push notifications feed), Messages (conversation list + chat), Tasks (assigned tasks with status), Settings
- GPS reporting: background location service publishing to VTV API (replaces OwnTracks for drivers who install the app)
- Push notifications: Firebase Cloud Messaging (FCM) for Android, APNs for iOS
- `app/messaging/push.py` — `PushService` class — sends FCM/APNs push for new messages and alerts
- `app/core/config.py` — `fcm_server_key`, `apns_key_path`, `push_enabled: bool = False`
- Auth: reuse VTV JWT — `POST /v1/auth/login` from mobile, token stored in secure storage
- Offline support: SQLite local cache for messages, sync on reconnect
- 15+ unit tests (backend push service): FCM send (3), APNs send (2), token management (2), offline queue integration (3), GPS position ingestion (3), auth (2)
**Verify:** Install app on test device. Login with driver credentials. Map shows fleet vehicles. Dispatcher sends message → push notification + in-app message. Driver taps task → acknowledges. GPS position appears on dispatcher's `/map`. Kill app → message arrives as push notification.

---

### CMS Features

| Subtask | Type | Realistic | Parallel? |
|---------|------|-----------|-----------|
| CMS-1 Route shape polylines | BE + FE | ~30min | ✅ Yes — anytime |

#### CMS-1 Route Shape Polylines
**What:** Render GTFS route geometries (`shapes.txt`) as colored polylines on the route map and full-screen `/map` page. Shapes are already imported in `app/schedules/models.py::Shape` — this task adds the API endpoint and frontend rendering layer.
**Why:** Currently the map shows only vehicle markers with no route context. Polylines show where routes run, helping dispatchers visually identify coverage gaps and route deviations.
**Implementation:**
- `app/schedules/routes.py` — `GET /v1/schedules/routes/{route_id}/shape` — returns GeoJSON `LineString` assembled from `Shape` points ordered by `shape_pt_sequence`
- `app/schedules/service.py` — `get_route_shape(route_id, feed_id) -> GeoJSON` — query `Shape` table, group by `gtfs_shape_id`, build coordinate array
- CMS `route-map.tsx`:
  - Add `Polyline` layer from `react-leaflet` — renders route shape behind vehicle markers
  - Color: per-feed color from `feedColors` prop, with 50% opacity
  - Toggle: "Show routes" checkbox in map controls
  - Selected route: full opacity + thicker line when `selectedRouteId` is set
- SDK: `getRouteShape(routeId)` wrapper
- 6+ unit tests: GeoJSON assembly (2), multi-shape routes (1), empty shape handling (1), CMS rendering (2)
**Verify:** Open routes page → toggle "Show routes" → polylines appear for all routes. Click a route → its polyline highlights. `/map` page shows polylines for all visible feeds. Zoom out → polylines visible across all Latvia.

---

_Completed work archived to [docs/TODO-archive.md](TODO-archive.md)._
