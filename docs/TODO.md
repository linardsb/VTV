# VTV TODO

Planned features and improvements. Each item links to its detailed planning document where available.

## Progress Overview

```
Backend API       ██████████████████████░░  99%  (12/12 features + analytics + compliance exports + multi-feed GTFS-RT + WebSocket live streaming + alerts + fleet + geofences)
CMS Frontend      ███████████████████████░  99%  (13 pages live, real API on all, WebSocket real-time, multi-feed support, EU compliance exports, analytics dashboard)
Testing           ████████████████████░░░░  90%  (927 unit tests, 106 security tests, 81 e2e tests, CI pipeline live with security gates)
Infrastructure    ██████████████████████░░  97%  (Docker, nginx+Brotli, Gunicorn multi-worker, Redis rate limiting, Makefile, 25 slash commands, CI/CD, 6 security audits, SDLC security framework, context-triggered security SDC)
Latvia Platform   ████████░░░░░░░░░░░░░░░  35%  (Riga GTFS + PostGIS + WebSocket + multi-feed GTFS-RT + TimescaleDB historical storage, no multi-city yet)
Intelligence/ML   ░░░░░░░░░░░░░░░░░░░░░░░   0%  (Phase 4 — not started)
```

## In Progress

### E2E Testing Maturity

- [ ] **CRUD E2E Tests** - Tests that create/edit/delete records and verify persistence. Current 81 tests cover page loads, filters, navigation, and UI interactions but don't test full write operations (require seeded test data).

## Planned Features

### Knowledge Base

- [ ] **RAG Knowledge Base Improvements** - Expand document type support (HTML, PPTX — Excel/CSV done), add Latvian lemmatizer, parent-child chunking, temporal metadata, auto-domain tagging, cross-lingual search, document versioning, search feedback loop, and knowledge graph overlay. ~12-14 days remaining effort, ~$0.65/month added cost.
  - Plan: [docs/PLANNING/rag-improvements.md](PLANNING/rag-improvements.md)

- [ ] **SOP & File Automation** - Automated document ingestion (folder watcher, email monitor, web scraper, GTFS sync) and LLM-powered SOP generation (incident-to-SOP pipeline, regulation change detection, shift handover notes, template scaffolding). ~13 days total effort, ~$4.50/month LLM cost, saves ~47 hrs/month human time.
  - Plan: [docs/PLANNING/sop-file-automation.md](PLANNING/sop-file-automation.md)

### CMS Features

- [ ] **Route Shape Polylines** - Display route geometry on map from GTFS `shapes.txt`. Requires polyline layer in react-leaflet, shape import during GTFS ZIP processing, and route-shape association. Enhances route visualization significantly.

- [x] ~~**NeTEx/SIRI Compliance Exports**~~ — Moved to Completed (2026-03-07)

### Fleet Management & Vehicle Tracking (LocTracker-inspired)

- [x] **Phase 1A: Device Management + Telemetry Ingestion** — `app/fleet/` vertical slice: TrackedDevice CRUD (5 endpoints + RBAC), Traccar webhook bridge with OBD-II parsing, `vehicle_positions` hypertable extended with `source` + `obd_data` columns, Traccar Docker sidecar (`--profile fleet`). 17 unit tests. (commit 10ff86c, 2026-03-08)
  - Plan: [.agents/plans/fleet-core-1a.md](../.agents/plans/fleet-core-1a.md)

- [x] **Phase 1B: Geofencing (Backend)** — `app/geofences/` vertical slice: PostGIS POLYGON zones with GIST indexing, 8 REST endpoints (CRUD + event queries + dwell reports), background evaluator (30s cycle, Redis state, ST_Contains), entry/exit/dwell detection with alerts integration, 2 tables (geofences + geofence_events), 23 unit tests. CMS fleet pages still pending. (2026-03-08)
  - Plan: [.agents/plans/geofences-phase-1b.md](../.agents/plans/geofences-phase-1b.md)

- [ ] **Phase 2: Fuel + Analytics + LocShare** — Fuel monitoring (refueling/drain detection from OBD), fuel consumption analytics, fleet distance/drive time reports, idle time detection, LocPoints dwell time, LocShare (JWT expiring public tracking links), PDF/CSV report export, speed/device-offline alerts. CMS: fuel dashboard, analytics pages, LocShare management. ~27 days effort.
  - Plan: [docs/PLANNING/fleet-management-tracking.md](PLANNING/fleet-management-tracking.md) (Phase 2)

- [ ] **Phase 3: Tachograph + Driving Hours Compliance** — `app/tachograph/` vertical slice: remote DDD file download (Teltonika Web Tacho + flespi), DDD binary parser, EU 561/2006 driving hours calculator (daily 9/10h, weekly 56h, biweekly 90h, monthly 160h), compliance status endpoints, infringement detection, driving hours alerts. CMS: compliance dashboard, activity timeline, DDD management, violation reports. ~36 days effort.
  - Plan: [docs/PLANNING/fleet-management-tracking.md](PLANNING/fleet-management-tracking.md) (Phase 3)

- [ ] **Phase 4: Routing + Maps Fallback** — OSRM self-hosted (Latvia OSM extract) as Docker sidecar, HERE Fleet Telematics API fallback, route optimization for service vehicles. CMS: route planning UI with map waypoints. ~15 days effort.
  - Plan: [docs/PLANNING/fleet-management-tracking.md](PLANNING/fleet-management-tracking.md) (Phase 4)

- [ ] **Phase 5: Driver Mobile App + Messaging** — `app/messaging/` vertical slice (dispatcher↔driver messaging, task assignment), React Native mobile app (live map, alerts, messaging, tasks), push notifications (FCM/APNs). ~28 days effort.
  - Plan: [docs/PLANNING/fleet-management-tracking.md](PLANNING/fleet-management-tracking.md) (Phase 5)

### Full Latvia Transit Platform

- [ ] **Phase 1: Foundation** - Database extensions (TimescaleDB), GTFS static importer for all Latvia, CKAN data.gov.lv bridge for immediate ATD data, full-screen transit map in CMS. ~3 weeks remaining effort. *Largely done: GTFS import, Redis cache, REST endpoints, GTFS-RT poller, PostGIS spatial queries (GeoAlchemy2 + GIST index), WebSocket live streaming (backend Pub/Sub + frontend real-time push with HTTP fallback), persistent GTFS storage (DB-backed static data for agent tools), and TimescaleDB historical position storage (hypertable, compression, 90-day retention, vehicle history + delay trend endpoints) are complete. Remaining: multi-city GTFS, CKAN bridge, full-screen map.*
  - Plan: [docs/PLANNING/Implementation-Plan.md](PLANNING/Implementation-Plan.md) (Phase 1)

- [ ] **Phase 2: Full Latvia Coverage** - Additional city feeds (Daugavpils, Jurmala, Pieriga), train positions via WebSocket, Valhalla route matching, ETA calculator, adaptive polling, circuit breakers, TimescaleDB compression, GTFS-RT publisher. ~4 weeks effort.
  - Plan: [docs/PLANNING/Implementation-Plan.md](PLANNING/Implementation-Plan.md) (Phase 2)

- [ ] **Phase 3: Intercity Gap-Fill** - OwnTracks integration for phone-based tracking, Traccar integration for hardware GPS (Teltonika FMB920), OpenTripPlanner for journey planning, shareable tracking links, historical analytics. ~8 weeks effort.
  - Plan: [docs/PLANNING/Implementation-Plan.md](PLANNING/Implementation-Plan.md) (Phase 3)

- [ ] **Phase 4: Intelligence** - ML-based ETA prediction (TimescaleDB history), weather-adjusted delays, passenger load prediction (e-ticket data), congestion factors, anomaly detection, public developer API. Ongoing.
  - Plan: [docs/PLANNING/Implementation-Plan.md](PLANNING/Implementation-Plan.md) (Phase 4)

## Completed

### Backend Features

- [x] **Schedule Management** - 23 endpoints: agencies, routes, calendars, trips CRUD. GTFS ZIP import with merge/upsert strategy, validation, stop times. Full vertical slice with async SQLAlchemy, Pydantic schemas, structured logging. (commit 37d5c70)
  - Plan: [.agents/plans/schedule-management.md](../.agents/plans/schedule-management.md)

- [x] **Multi-Feed GTFS-RT** - Background poller for multiple transit feeds, Redis caching for sub-ms reads, vehicle position enrichment with static GTFS data. Configurable via `TRANSIT_FEEDS_JSON`. (commit 37d5c70)

- [x] **DMS Backend** - Document management system: file persistence at `data/documents/{id}/`, metadata editing (PATCH), file download, content preview, domain listing, Excel/CSV extraction via openpyxl. 4 new API endpoints, 3 new Document model columns (title, description, file_path). 10 new unit tests.
  - Plan: [.agents/plans/dms-backend.md](../.agents/plans/dms-backend.md)

- [x] **Agent Document Citations** - Agent system prompt includes CITATION RULES for clickable document links (`[title](/{locale}/documents/{id})`), knowledge search tool passes `document_id` through results. 7 unit tests. (commit bf0889f)
  - Plan: [.agents/plans/agent-document-citations.md](../.agents/plans/agent-document-citations.md)

- [x] **RAG Knowledge Base** - Hybrid search (pgvector + fulltext + RRF), multi-format ingestion (PDF, DOCX, email, image OCR, text), configurable embeddings (OpenAI/Jina/local), cross-encoder reranking, agent tool integration. 20 unit tests. (commit 8544237)

- [x] **Latvian Language Support** - Rewritten agent system prompt with Latvian language rules, 30+ transit term glossary, diacriticless input understanding. LLM upgraded to Claude Sonnet 4.5, embeddings switched to Jina v3 for explicit Latvian support. Frontend i18n diacritics fixed. (commit 17ce1a9)
  - Research: [docs/PLANNING/latvian-language-and-model-research.md](PLANNING/latvian-language-and-model-research.md)

- [x] **Stop Management CRUD** - Backend vertical slice with SQLAlchemy models, Haversine proximity search (plain Float columns), Pydantic schemas, async repository, 6 REST endpoints. (commit f88efc5)

- [x] **AI Chat Page** - CMS chat page with real LLM integration via agent service /v1/chat/completions endpoint, streaming SSE responses, bilingual i18n. (commit 3dad10b)

- [x] **Obsidian Vault Tools (4)** - query_vault (5 actions), manage_notes (5 actions), manage_folders (4 actions), bulk_operations (5 actions with dry_run). 68 unit tests. (commit 0bc02c3)

- [x] **Transit Tools (5)** - query_bus_status, get_route_schedule, search_stops, get_adherence_report, check_driver_availability. 104 unit tests. (commits 3472688-b25885f)

- [x] **Transit REST API** - GET /api/v1/transit/vehicles for frontend map polling, enriches GTFS-RT with static data. 9 unit tests. (commit 032e617)

- [x] **DDoS Defense** - nginx rate limiting, connection limits, security headers, slowapi per-IP limits, body size middleware, query quota tracker. (commit 643b23e)

- [x] **JWT Auth + RBAC** - 7 endpoints: login, logout, refresh, seed, reset-password, delete-user. bcrypt with timing attack prevention, Redis brute-force tracking (5 attempts = 15min lockout), token revocation denylist, refresh token single-use, 4-role RBAC (admin/editor/dispatcher/viewer). 52 unit tests. (commit 4c34c33)

- [x] **Driver Management** - 5 endpoints: CRUD + availability. HR profiles, shift/availability tracking, agent tool integration. 27 unit tests.

- [x] **Event Management** - 5 endpoints: CRUD + date range filter. Dashboard calendar integration, operational event tracking. 18 unit tests.

- [x] **Agent Skills System** - 7 endpoints: CRUD + activation/deactivation + agent context injection. Reusable knowledge packages that dynamically extend agent capabilities. 11th agent tool. 23 unit tests. (commit ed9662f)

- [x] **PostGIS Migration** - Migrated stop proximity search from Haversine formula to PostGIS `ST_DWithin` with GeoAlchemy2, GIST-indexed Geometry(Point, 4326) column, database trigger for lat/lon→geom sync. Sub-ms spatial queries. (commit f7070b7, 2026-02-26)
  - Plan: [.agents/plans/postgis-migration.md](../.agents/plans/postgis-migration.md)

- [x] **DMS Enhancements** - Scanned PDF OCR detection, LLM auto-tagging on upload, tag CRUD endpoints (create/list/delete tags, bulk tag documents). (commit 65697a8, 2026-02-26)
  - Plan: [.agents/plans/dms-enhancements.md](../.agents/plans/dms-enhancements.md)

- [x] **WebSocket Live Streaming (Backend)** - Real-time vehicle position push via WebSocket (`/ws/transit/vehicles`). Redis Pub/Sub fan-out from GTFS-RT pollers to per-client connections. Per-client feed/route filtering via subscribe messages. JWT auth via query parameter. ConnectionManager singleton, background subscriber task. nginx WebSocket proxy with 3600s timeouts and 10/IP connection limit. 30 new unit tests (ws_manager, ws_routes, ws_subscriber, poller). (commit cdb80ca, 2026-02-27)
  - Plan: [.agents/plans/be-websocket-live-streaming.md](../.agents/plans/be-websocket-live-streaming.md)

- [x] **WebSocket Live Streaming (Frontend)** - Replaced HTTP polling with WebSocket real-time push (~100ms latency) for vehicle positions. Automatic fallback to SWR HTTP polling (10s) after 3 failed reconnects. Periodic 60s retry to switch back to WebSocket. Route filtering via subscribe message. Connection status badge (Live/Polling/Connecting) on map. JWT auth via query parameter with 60s cached token. (commit 5bf06ca, 2026-02-27)
  - Plan: [.agents/plans/fe-websocket-vehicle-positions.md](../.agents/plans/fe-websocket-vehicle-positions.md)

- [x] **Vehicle Management** - Fleet CRUD (8 endpoints), maintenance tracking with mileage/date side-effects, driver assignment with cross-feature conflict detection, database CHECK constraints, fleet_number→GTFS-RT vehicle_id linking. 30 unit tests, code review with 6/10 issues fixed. (2026-02-27)
  - Plan: [.agents/plans/vehicle-management.md](../.agents/plans/vehicle-management.md)
  - Review: [.agents/code-reviews/vehicles-review.md](../.agents/code-reviews/vehicles-review.md)

### CMS Frontend Pages

- [x] **Dashboard** - 4 metric cards (real API via SWR: vehicles + routes, 30s polling), multi-view calendar (week/month/3-month/year, real events via `useCalendarEvents` SWR hook), drag-and-drop driver scheduling (driver roster + 5 action types), live timeline, resizable panels. (commit 852ee95, updated 2026-02-25)

- [x] **Routes Page** - Real API CRUD against backend `/api/v1/schedules/routes`, server pagination, search, type/agency/status filters, route detail sheet, route form, Leaflet map with live GTFS-RT vehicle positions (WebSocket real-time push with HTTP polling fallback), connection status badge, resizable split panels, mobile tab layout. 142 i18n keys per locale.

- [x] **Stops Page** - Real API CRUD against backend `/api/v1/stops`, Leaflet map with draggable markers and terminus icons, direction display, location_type filtering, GTFS ID copy-to-clipboard, proximity search, mobile tab layout.

- [x] **Schedules Page** - Real API CRUD against backend `/api/v1/schedules` (22 endpoints). Three tabs: Calendars (service ID, operating days, date ranges, exceptions), Trips (route/calendar/direction filters, stop times), Import (GTFS ZIP drag-and-drop upload, merge/upsert, validation with error/warning display).

- [x] **Documents Page** - Real API against backend `/api/v1/knowledge`. Upload form (drag-and-drop, react-dropzone, 10 file types), filterable table (search, type, domain, status, language), document detail with lazy-loaded chunk viewer, download/delete. ~70 i18n keys per locale.
  - Plan: [.agents/plans/dms-frontend.md](../.agents/plans/dms-frontend.md)

- [x] **Login Page** - Auth.js v5 credentials provider, DB-backed via `POST /api/v1/auth/login`, brute-force protection (5 attempts = 15min lockout).

- [x] **Drivers Page** - Real API CRUD against backend `/api/v1/drivers`. Driver profiles, shift management, availability tracking, search and filters. 10 e2e tests.

- [x] **GTFS Page** - Dedicated GTFS data management page at `/[locale]/gtfs` with 3 tabs: Data Overview (5 stat cards — agencies, routes, calendars, trips, stops + GTFS-RT feed status), Import (reuses GTFSImport from Schedules), Export (agency filter + download). Semantic tokens, full i18n (30 keys per locale). Backend data from `/api/v1/schedules` + `/api/v1/transit/feeds`.

- [x] **Mobile Responsive** - All pages: tab-based Table/Map switching, collapsible filter Sheet, hamburger sidebar. (commit 032e617)

- [x] **Design Tokens** - Three-tier tokens (primitive, semantic, component), active state styling. (commit 801640d)

- [x] **Performance Fixes** - Self-hosted fonts, dashboard converted to RSC, build optimizations. (commit fcfea8a)

### Infrastructure & Tooling

- [x] **Playwright E2E Testing** - 81 tests across 10 files (dashboard, routes, stops, schedules, documents, drivers, navigation, login, smoke). Auto-detection of changed features via `detect-changed.sh`. Auth setup with session reuse. `make e2e` / `/e2e` slash command.

- [x] **Slash Commands (25)** - 8 backend + 7 frontend + 9 cross-cutting + 1 testing. Full pipeline: prime -> planning -> execute -> validate -> commit.

- [x] **Makefile** - Unified workflow: `make dev` (full stack), `make check` (lint+types+tests), `make e2e` (auto-detect), `make docker` (full deploy). 18 targets.

- [x] **Docker Compose** - PostgreSQL (pgvector/pgvector:pg18), Redis, auto-migration, FastAPI app, Next.js CMS, nginx reverse proxy. Production overlay with security headers. `make docker` / `make docker-prod`.

- [x] **Codebase Audit** - 120 findings documented in `.agents/code-reviews/AUDIT-SUMMARY.md`. (2026-02-21)

- [x] **Documentation Cleanup** - 74 redundant CLAUDE.md files removed, 5 substantive files retained. (2026-02-21)

- [x] **Security Audit Remediation** - 13 findings from third-party security audit fixed. Streaming upload with 50MB limit, regex filename sanitization, path traversal prevention, ILIKE wildcard escaping, X-Real-IP rate limiting, Redis URL redaction, Docker env var interpolation, transit input validation, nginx HTTPS template, environment-controlled demo credentials. 33 security regression tests. (commit 85bf32d, 2026-02-22)
  - Audit: [docs/security_audit.txt](security_audit.txt)

- [x] **Security Audit 2 Remediation** - Second audit addressing code quality, data integrity, and testing gaps. `ValidationError` → `DomainValidationError` rename (Pydantic clash), Content-Length header hardening, transit tool deduplication (6 functions → `utils.py`), GTFS time validation (min/sec range), unique constraints on `(trip_id, stop_sequence)` and `(calendar_id, date)` + 2 migrations, knowledge empty update rejection, unknown file type rejection, exception handling improvements, cookie SameSite, locale-aware auth redirects, schedule edge case tests, knowledge repository + route layer tests. 34 new tests (520 → 554). (2026-02-23)
  - Audit: [docs/security_audit_2.txt](security_audit_2.txt)

- [x] **Security Hardening v3** - 19-task, 4-phase hardening: bcrypt timing normalization, password complexity on reset, CORS method/header allowlists, health endpoint redaction, convention enforcement tests (auto-discover all endpoints for auth). 84 security tests. (2026-02-24)
  - Plan: [.agents/plans/security-hardening-v3.md](../.agents/plans/security-hardening-v3.md)

- [x] **Security Hardening v4** - 15-task, 4-phase hardening: CI/CD security gates (dedicated Ruff Bandit step, pip-audit), container hardening (non-root, cap_drop ALL, no-new-privileges), automated backups with GDPR retention, GDPR right-to-erasure endpoint, pre-commit hook (Bandit + sensitive file check). (2026-02-24)
  - Plan: [.agents/plans/security-hardening-v4.md](../.agents/plans/security-hardening-v4.md)
  - Audit: [docs/security_audit_4.txt](security_audit_4.txt)

- [x] **Security Hardening v5** - 16 findings (4 CRIT, 5 HIGH, 7 MED): quota IP bypass fix, logout endpoint, refresh token single-use, ZIP bomb protection, streaming GTFS upload, SSRF localhost validation, request ID sanitization, file path redaction. 94 security tests. (commit 6eb1ed0, 2026-02-25)
  - Plan: [.agents/plans/security-hardening-v5.md](../.agents/plans/security-hardening-v5.md)
  - Audit: [docs/security_audit_5.txt](security_audit_5.txt)

- [x] **SDLC Security Audit Framework** - Three-tiered security scanning (quick/standard/full) integrated into development lifecycle. `scripts/security-audit.sh` runner with Docker/nginx validators (`scripts/check-docker-security.py`, `scripts/check-nginx-security.py`). GitHub Actions scheduled workflow (`.github/workflows/security.yml`, weekly cron + manual dispatch). Audit tracking registry (`.agents/audits/tracking.md`). 11 new convention tests (TestSDLCSecurityGates + TestAuditCoverageCompleteness). Security checks integrated into 7 slash commands. `make security-audit-quick/standard/full` targets. 690 total unit tests, 105 security tests. (2026-02-25)
  - Plan: [.agents/plans/sdlc-security-audits.md](../.agents/plans/sdlc-security-audits.md)

- [x] **CI Pipeline** - GitHub Actions workflow (`.github/workflows/ci.yml`): backend checks (ruff lint + dedicated security audit via `ruff --select=S` + mypy + pyright + pytest with PostgreSQL + Redis), frontend checks (TypeScript + ESLint + build), e2e tests (docker-compose + Playwright). Dependency scanning via pip-audit. (2026-02-24)

- [x] **Performance Optimization (5 phases)** - Phase 1: Redis-backed rate limiting (cross-worker), poller leader election (Redis SETNX), Gunicorn multi-worker (4 UvicornWorkers), configurable connection pool. Phase 2: Auth user cache (TTLCache, 30s TTL, invalidate on update). Phase 3: Nginx upstream keepalive, Brotli compression (multi-stage Docker build), HTTP cache headers (GET-only on semi-static endpoints). Phase 4: SWR data fetching (request dedup, stale-while-revalidate, focus revalidation), session token caching (60s). Phase 5: Font weight reduction, react-leaflet tree-shaking. 12 code review findings fixed. 693 unit tests. (2026-02-25)
  - Plan: plan mode session
  - Review: [.agents/code-reviews/perf-optimization-review.md](../.agents/code-reviews/perf-optimization-review.md)
  - Report: [.agents/execution-reports/perf-optimization.md](../.agents/execution-reports/perf-optimization.md)

- [x] **Dashboard Drag-and-Drop Scheduling** - Driver roster sidebar with draggable cards (HTML5 DnD API), calendar drop zones on week/month views with precise time calculation. 5 action types: assign shift, mark leave, mark sick day, schedule training, custom event. RBAC-enforced (admin/editor only). SWR-based `useDriversSummary` hook (120s refresh). `DriverDropDialog` with i18n-templated event titles. 46 new i18n keys per locale. (2026-02-25)
  - Plan: [.agents/plans/fe-dashboard-dnd.md](../.agents/plans/fe-dashboard-dnd.md)
  - Review: [.agents/code-reviews/fe-dashboard-dnd-review.md](../.agents/code-reviews/fe-dashboard-dnd-review.md)

- [x] **Users Page** - Admin-only user management page at `/[locale]/users`. CRUD with search, role/status filters, reset-password dialog. Backend: `/api/v1/auth/users` (5 endpoints). (commit b2d5e1d, 2026-02-25)
  - Plan: [.agents/plans/fe-users-page.md](../.agents/plans/fe-users-page.md)

- [x] **@vtv/sdk Generation + Full Migration** - Auto-generated TypeScript client from FastAPI OpenAPI schema. 66 endpoints, 95+ types (as of 2026-03-08). Auth via request interceptor (JWT, dual server/client context). All 13 API domains migrated from hand-written `authFetch` to thin SDK wrappers, eliminating ~1,200 lines of boilerplate. (commits b2d5e1d, b9e34f0, 2026-02-25/26)
  - Plan: [.agents/plans/fe-sdk-generation.md](../.agents/plans/fe-sdk-generation.md)
  - Migration plan: [.agents/plans/fe-sdk-migration.md](../.agents/plans/fe-sdk-migration.md)

- [x] **Calendar Event Hover Cards** - Tooltip hover cards on calendar events (week/month/3-month views) showing event details, goals, and driver info. shadcn/ui HoverCard component with semantic tokens. (commit 15d39d2, 2026-02-27)
  - Plan: [.agents/plans/fe-calendar-event-hover-card.md](../.agents/plans/fe-calendar-event-hover-card.md)

- [x] **Scoped CLAUDE.md Context Files** - Added path-scoped CLAUDE.md files across the codebase for AI-assisted development context. Cleaned up duplicate `cms/cms/` directory. (commit 4329731, 2026-02-27)

- [x] **Vehicles Page** - Fleet management page at `/[locale]/vehicles`. Vehicle CRUD, maintenance tracking, driver assignment, search/filter by type/status. Backend: `/api/v1/vehicles` (8 endpoints). (commit f75988c, 2026-03-07)

- [x] **Analytics Dashboard** - Analytics page at `/[locale]/analytics` with 3 tabs: Fleet (vehicle utilization, maintenance stats), Drivers (shift coverage, availability), Performance (on-time metrics, delay analysis). Read-only aggregation over existing data. Backend: `/api/v1/analytics` (4 endpoints). (commit 7bbeece, 2026-03-07)

- [x] **Multi-Feed GTFS-RT Frontend** - Routes page multi-feed support: feed selector filter (ToggleGroup), per-feed marker border colors, feed health overlay with vehicle counts per feed, auto-fit bounds on feed change. WebSocket subscription filtering by feed. (commit d65a151, 2026-03-07)

- [x] **EU Compliance Exports Tab** - GTFS page 4th tab "Compliance" for EU-mandated export formats: NeTEx EPIP 1.2 XML download, SIRI Vehicle Monitoring 2.0 XML download, SIRI Stop Monitoring 2.0 XML download. Agency/route/stop filters per format, export status display. Backend: `/api/v1/compliance` (4 endpoints). (commit 9aed21e, 2026-03-07)

- [x] **Persistent GTFS Storage** - Migrated agent transit tools from in-memory HTTP/ZIP-based GTFSStaticCache to DB-backed GTFSStaticStore. Reads from existing schedules + stops PostgreSQL tables via ScheduleRepository. Same dataclass interface (RouteInfo, StopInfo, TripInfo, etc.), same TTL-based refresh. FK resolution maps translate integer PKs to GTFS string IDs. Updated 8 consumer files (5 agent tools + poller + transit service + analytics service) and 7 test files. 822 unit tests pass. (2026-03-07)
  - Plan: [.agents/plans/persistent-gtfs-storage.md](../.agents/plans/persistent-gtfs-storage.md)

- [x] **Security Audit 6 Remediation** - 8 vulnerability categories addressed: fail-closed token revocation (Redis down = deny), RBAC hardening on drivers/events/knowledge endpoints (require_role), magic bytes file upload validation, prompt injection detection, brute force logging upgrade, JWT secret startup validation, CORS wildcard prevention, configurable SSL verification. 9 test fixes for updated security behavior. (commit 08c0aec, 2026-03-07)
  - Audit: [documents/PLANNING/audit_6.txt](../documents/PLANNING/audit_6.txt)
  - Plan: [.agents/plans/security-audit-6.md](../.agents/plans/security-audit-6.md)

- [x] **Historical Position Storage (TimescaleDB)** - Time-series vehicle position storage with TimescaleDB hypertable. Dual-write from poller (Redis + TimescaleDB, non-blocking). `vehicle_positions` table with compression (7d) and retention (90d) policies. Vehicle history and route delay trend REST endpoints with RBAC. `VehicleStopStatus` Literal type, `EnrichedVehicle` TypedDict, `DelayTrendBucket` TypedDict. 838 unit tests. (2026-03-07)
  - Plan: [.agents/plans/historical-position-storage.md](../.agents/plans/historical-position-storage.md)
  - Review: [.agents/code-reviews/transit-history-review.md](../.agents/code-reviews/transit-history-review.md)

- [x] **OpenAPI Spec Completions + SDK Regeneration** - Added OpenAPI response schemas to compliance XML endpoints (`responses` parameter with `application/xml` content type), typed transit `/feeds` endpoint with `TransitFeedsResponse` model, and regenerated `@vtv/sdk` from live spec. SDK now covers all 66 endpoints (was 48) across 13 API domains with 95+ TypeScript types. (commit aa9d9f3, 2026-03-08)
  - Plan: [.agents/plans/openapi-spec-completions.md](../.agents/plans/openapi-spec-completions.md)

- [x] **Notification/Alerts System** - Proactive alerting with configurable rules and background evaluator. 11 REST endpoints under `/api/v1/alerts` (rule CRUD + instance lifecycle + dashboard summary). Background evaluator checks 3 rule types: `maintenance_due`, `registration_expiry`, `delay_threshold`. Partial unique index for active alert deduplication. RBAC: admin-only rules, admin+dispatcher instances, all-auth summary. 2 tables (`alert_rules`, `alert_instances`), 40 unit tests. (2026-03-08)
  - Plan: [.agents/plans/notification-alerts-system.md](../.agents/plans/notification-alerts-system.md)

- [x] **Geofence Zone Monitoring (Phase 1B Backend)** - PostGIS POLYGON zones with GIST indexing and ST_Contains containment queries. 8 REST endpoints (CRUD + event history + dwell reports). Background evaluator (30s cycle) detects vehicle entry/exit/dwell via Redis state tracking, creates alert instances. 2 tables (geofences, geofence_events), 3 new alert types (geofence_enter/exit/dwell). 23 unit tests. (2026-03-08)
  - Plan: [.agents/plans/geofences-phase-1b.md](../.agents/plans/geofences-phase-1b.md)

- [x] **Context-Triggered Security SDC** - Integrated security into the development cycle based on audit_6 findings. New `_shared/security-contexts.md` defines 6 context categories (CTX-AUTH, CTX-RBAC, CTX-FILE, CTX-AGENT, CTX-INFRA, CTX-INPUT) with trigger keywords, specific requirements, and plan task templates. Updated 7 commands: `/be-planning` and `/fe-planning` now detect and inject security contexts into plans, `/review` and `/fe-review` apply context-aware deeper checks, `/be-prime` and `/fe-prime` surface the security context system. (2026-03-07)

## Planning Documents

| Document | Path | Description |
|----------|------|-------------|
| Implementation Plan | [docs/PLANNING/Implementation-Plan.md](PLANNING/Implementation-Plan.md) | Full Latvia transit platform (4 phases, 16+ weeks) |
| RAG Improvements | [docs/PLANNING/rag-improvements.md](PLANNING/rag-improvements.md) | Knowledge base enhancements (10 improvements) |
| SOP Automation | [docs/PLANNING/sop-file-automation.md](PLANNING/sop-file-automation.md) | Automated ingestion + SOP generation |
| Latvian Language Research | [docs/PLANNING/latvian-language-and-model-research.md](PLANNING/latvian-language-and-model-research.md) | Model benchmarks, embedding selection, DMS architecture |
| Command Architecture | [docs/PLANNING/command-planning.md](PLANNING/command-planning.md) | Slash command design decisions and audit |
| Schedule Management | [.agents/plans/schedule-management.md](../.agents/plans/schedule-management.md) | GTFS schedule management backend implementation |
