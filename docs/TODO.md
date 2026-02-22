# VTV TODO

Planned features and improvements. Each item links to its detailed planning document where available.

## Progress Overview

```
Backend API       ████████████████████░░░░  85%  (6/7 features, schedules + stops + transit + knowledge + DMS + auth done)
CMS Frontend      ████████████████████░░░░  83%  (7/7 pages live, real API on 5/7, mock data on dashboard)
Testing           ██████████████░░░░░░░░░░  60%  (450 unit tests, 69 e2e tests, no CI pipeline yet)
Infrastructure    ████████████████████░░░░  80%  (Docker, nginx, Makefile, 24 slash commands, e2e framework)
Latvia Platform   ████░░░░░░░░░░░░░░░░░░░  15%  (Riga GTFS only, no PostGIS/TimescaleDB/multi-city yet)
Intelligence/ML   ░░░░░░░░░░░░░░░░░░░░░░░   0%  (Phase 4 — not started)
```

## In Progress

### E2E Testing Maturity

- [ ] **CI Pipeline** - GitHub Actions workflow for e2e tests on PR. Currently runs locally only via `make e2e`.
- [ ] **CRUD E2E Tests** - Tests that create/edit/delete records and verify persistence. Current 69 tests cover page loads, filters, navigation, and UI interactions but don't test full write operations (require seeded test data).

### Dashboard Real Data

- [ ] **Dashboard API Integration** - Replace mock metrics and calendar events with real backend data. Dashboard currently uses `mock-dashboard-data.ts` — the only page still on mock data.

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

### CMS Frontend Pages

- [x] **Dashboard** - 4 metric cards, multi-view calendar (week/month/3-month/year), live timeline, resizable panels. Mock data. (commit 852ee95)

- [x] **Routes Page** - Real API CRUD against backend `/api/v1/schedules/routes`, server pagination, search, type/agency/status filters, route detail sheet, route form, Leaflet map with live GTFS-RT vehicle positions (15s polling), resizable split panels, mobile tab layout. 142 i18n keys per locale.

- [x] **Stops Page** - Real API CRUD against backend `/api/v1/stops`, Leaflet map with draggable markers and terminus icons, direction display, location_type filtering, GTFS ID copy-to-clipboard, proximity search, mobile tab layout.

- [x] **Schedules Page** - Real API CRUD against backend `/api/v1/schedules` (22 endpoints). Three tabs: Calendars (service ID, operating days, date ranges, exceptions), Trips (route/calendar/direction filters, stop times), Import (GTFS ZIP drag-and-drop upload, merge/upsert, validation with error/warning display).

- [x] **Documents Page** - Real API against backend `/api/v1/knowledge`. Upload form (drag-and-drop, react-dropzone, 10 file types), filterable table (search, type, domain, status, language), document detail with lazy-loaded chunk viewer, download/delete. ~70 i18n keys per locale.
  - Plan: [.agents/plans/dms-frontend.md](../.agents/plans/dms-frontend.md)

- [x] **Login Page** - Auth.js v5 credentials provider, DB-backed via `POST /api/v1/auth/login`, brute-force protection (5 attempts = 15min lockout).

- [x] **Mobile Responsive** - All pages: tab-based Table/Map switching, collapsible filter Sheet, hamburger sidebar. (commit 032e617)

- [x] **Design Tokens** - Three-tier tokens (primitive, semantic, component), active state styling. (commit 801640d)

- [x] **Performance Fixes** - Self-hosted fonts, dashboard converted to RSC, build optimizations. (commit fcfea8a)

### Infrastructure & Tooling

- [x] **Playwright E2E Testing** - 69 tests across 9 files (dashboard, routes, stops, schedules, documents, navigation, login, smoke). Auto-detection of changed features via `detect-changed.sh`. Auth setup with session reuse. `make e2e` / `/e2e` slash command.

- [x] **Slash Commands (24)** - 16 backend + 7 frontend + 1 e2e. Full pipeline: prime -> planning -> execute -> validate -> commit.

- [x] **Makefile** - Unified workflow: `make dev` (full stack), `make check` (lint+types+tests), `make e2e` (auto-detect), `make docker` (full deploy). 18 targets.

- [x] **Docker Compose** - PostgreSQL (pgvector/pgvector:pg18), Redis, auto-migration, FastAPI app, Next.js CMS, nginx reverse proxy. Production overlay with security headers. `make docker` / `make docker-prod`.

- [x] **Codebase Audit** - 120 findings documented in `.agents/code-reviews/AUDIT-SUMMARY.md`. (2026-02-21)

- [x] **Documentation Cleanup** - 74 redundant CLAUDE.md files removed, 5 substantive files retained. (2026-02-21)

## Planning Documents

| Document | Path | Description |
|----------|------|-------------|
| Implementation Plan | [docs/PLANNING/Implementation-Plan.md](PLANNING/Implementation-Plan.md) | Full Latvia transit platform (4 phases, 16+ weeks) |
| RAG Improvements | [docs/PLANNING/rag-improvements.md](PLANNING/rag-improvements.md) | Knowledge base enhancements (10 improvements) |
| SOP Automation | [docs/PLANNING/sop-file-automation.md](PLANNING/sop-file-automation.md) | Automated ingestion + SOP generation |
| Latvian Language Research | [docs/PLANNING/latvian-language-and-model-research.md](PLANNING/latvian-language-and-model-research.md) | Model benchmarks, embedding selection, DMS architecture |
| Command Architecture | [docs/PLANNING/command-planning.md](PLANNING/command-planning.md) | Slash command design decisions and audit |
| Schedule Management | [.agents/plans/schedule-management.md](../.agents/plans/schedule-management.md) | GTFS schedule management backend implementation |
