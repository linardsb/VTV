# VTV TODO

Planned features and improvements. Each item links to its detailed planning document where available.

## Progress Overview

```
Backend API       ██████████████████████░░  95%  (8/8 features: auth, knowledge, drivers, events, stops, schedules, transit, skills)
CMS Frontend      ██████████████████████░░  93%  (9/9 pages live, real API on 8/9, mock calendar on dashboard only)
Testing           ████████████████████░░░░  80%  (690 unit tests, 81 e2e tests, CI pipeline live with security gates)
Infrastructure    ██████████████████████░░  95%  (Docker, nginx, Makefile, 24 slash commands, CI/CD, 6 security audits, SDLC security framework)
Latvia Platform   ████░░░░░░░░░░░░░░░░░░░  15%  (Riga GTFS only, no PostGIS/TimescaleDB/multi-city yet)
Intelligence/ML   ░░░░░░░░░░░░░░░░░░░░░░░   0%  (Phase 4 — not started)
```

## In Progress

### E2E Testing Maturity

- [ ] **CRUD E2E Tests** - Tests that create/edit/delete records and verify persistence. Current 81 tests cover page loads, filters, navigation, and UI interactions but don't test full write operations (require seeded test data).

### Dashboard Real Data

- [ ] **Dashboard Calendar Integration** - Replace mock calendar events with real backend data. Dashboard metrics now use real API data (vehicle positions + route counts, 30s polling via `useDashboardMetrics` hook). Calendar events still use `mock-dashboard-data.ts`.

## Planned Features

### Document Management System (DMS)

- [ ] **DMS Enhancements** - Scanned PDF OCR detection, LLM auto-tagging on upload, tag CRUD endpoints. ~2 days remaining effort.
  - Plan: [docs/PLANNING/latvian-language-and-model-research.md](PLANNING/latvian-language-and-model-research.md) (see "Unified DMS" section)

### Knowledge Base

- [ ] **RAG Knowledge Base Improvements** - Expand document type support (HTML, PPTX — Excel/CSV done), add Latvian lemmatizer, parent-child chunking, temporal metadata, auto-domain tagging, cross-lingual search, document versioning, search feedback loop, and knowledge graph overlay. ~12-14 days remaining effort, ~$0.65/month added cost.
  - Plan: [docs/PLANNING/rag-improvements.md](PLANNING/rag-improvements.md)

- [ ] **SOP & File Automation** - Automated document ingestion (folder watcher, email monitor, web scraper, GTFS sync) and LLM-powered SOP generation (incident-to-SOP pipeline, regulation change detection, shift handover notes, template scaffolding). ~13 days total effort, ~$4.50/month LLM cost, saves ~47 hrs/month human time.
  - Plan: [docs/PLANNING/sop-file-automation.md](PLANNING/sop-file-automation.md)

### Full Latvia Transit Platform

- [ ] **Phase 1: Foundation** - Database extensions (PostGIS, TimescaleDB), GTFS static importer for all Latvia, CKAN data.gov.lv bridge for immediate ATD data, WebSocket for live streaming, full-screen transit map in CMS. ~4 weeks effort. *Partially done: GTFS import, Redis cache, REST endpoints, and GTFS-RT poller for Riga are complete.*
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

### CMS Frontend Pages

- [x] **Dashboard** - 4 metric cards (real API: vehicles + routes, 30s polling), multi-view calendar (week/month/3-month/year, mock events), live timeline, resizable panels. (commit 852ee95, updated 2026-02-23)

- [x] **Routes Page** - Real API CRUD against backend `/api/v1/schedules/routes`, server pagination, search, type/agency/status filters, route detail sheet, route form, Leaflet map with live GTFS-RT vehicle positions (15s polling), resizable split panels, mobile tab layout. 142 i18n keys per locale.

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

- [x] **Slash Commands (24)** - 16 backend + 7 frontend + 1 e2e. Full pipeline: prime -> planning -> execute -> validate -> commit.

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

## Planning Documents

| Document | Path | Description |
|----------|------|-------------|
| Implementation Plan | [docs/PLANNING/Implementation-Plan.md](PLANNING/Implementation-Plan.md) | Full Latvia transit platform (4 phases, 16+ weeks) |
| RAG Improvements | [docs/PLANNING/rag-improvements.md](PLANNING/rag-improvements.md) | Knowledge base enhancements (10 improvements) |
| SOP Automation | [docs/PLANNING/sop-file-automation.md](PLANNING/sop-file-automation.md) | Automated ingestion + SOP generation |
| Latvian Language Research | [docs/PLANNING/latvian-language-and-model-research.md](PLANNING/latvian-language-and-model-research.md) | Model benchmarks, embedding selection, DMS architecture |
| Command Architecture | [docs/PLANNING/command-planning.md](PLANNING/command-planning.md) | Slash command design decisions and audit |
| Schedule Management | [.agents/plans/schedule-management.md](../.agents/plans/schedule-management.md) | GTFS schedule management backend implementation |
