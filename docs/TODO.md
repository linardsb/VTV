# VTV TODO

Planned features and improvements. Each item links to its detailed planning document where available.

## Planned Features

### Document Management System (DMS)

- [ ] **DMS Backend** - Scanned PDF OCR detection, Excel/CSV extraction, LLM auto-tagging on upload, tag CRUD endpoints, document download endpoint, document content endpoint. ~4 days effort.
  - Plan: [docs/PLANNING/latvian-language-and-model-research.md](PLANNING/latvian-language-and-model-research.md) (see "Unified DMS" section)

- [ ] **DMS Frontend Pages** - Three new CMS pages: document list with filters/search/pagination, document upload with drag-and-drop and auto-tag preview, document viewer with rendered content and metadata sidebar. ~6 days effort.
  - Plan: [docs/PLANNING/latvian-language-and-model-research.md](PLANNING/latvian-language-and-model-research.md) (see "Frontend CMS pages" section)

- [ ] **Agent Document Citations** - Update agent prompt to include clickable document links (`[title](/lv/documents/{id})`) when citing knowledge base results. ~0.5 days effort.
  - Plan: [docs/PLANNING/latvian-language-and-model-research.md](PLANNING/latvian-language-and-model-research.md) (see "Document Viewer UX Decision" section)

### Knowledge Base

- [ ] **RAG Knowledge Base Improvements** - Expand document type support (Excel/CSV, HTML, PPTX), add Latvian lemmatizer, parent-child chunking, temporal metadata, auto-domain tagging, cross-lingual search, document versioning, search feedback loop, and knowledge graph overlay. ~14-16 days total effort, ~$0.65/month added cost.
  - Plan: [docs/PLANNING/rag-improvements.md](PLANNING/rag-improvements.md)

- [ ] **SOP & File Automation** - Automated document ingestion (folder watcher, email monitor, web scraper, GTFS sync) and LLM-powered SOP generation (incident-to-SOP pipeline, regulation change detection, shift handover notes, template scaffolding). ~13 days total effort, ~$4.50/month LLM cost, saves ~47 hrs/month human time.
  - Plan: [docs/PLANNING/sop-file-automation.md](PLANNING/sop-file-automation.md)

### Full Latvia Transit Platform

- [ ] **Phase 1: Foundation** - Database extensions (PostGIS, TimescaleDB), GTFS static importer for all Latvia, CKAN data.gov.lv bridge for immediate ATD data, GTFS-RT poller for Riga vehicle positions, Redis for real-time cache, REST API endpoints for vehicles/departures/history, WebSocket for live streaming, full-screen transit map in CMS. ~4 weeks effort.
  - Plan: [docs/PLANNING/Implementation-Plan.md](PLANNING/Implementation-Plan.md) (Phase 1)

- [ ] **Phase 2: Full Latvia Coverage** - Additional city feeds (Daugavpils, Jurmala, Pieriga), train positions via WebSocket, Valhalla route matching, ETA calculator, adaptive polling, circuit breakers, TimescaleDB compression, GTFS-RT publisher. ~4 weeks effort.
  - Plan: [docs/PLANNING/Implementation-Plan.md](PLANNING/Implementation-Plan.md) (Phase 2)

- [ ] **Phase 3: Intercity Gap-Fill** - OwnTracks integration for phone-based tracking, Traccar integration for hardware GPS (Teltonika FMB920), OpenTripPlanner for journey planning, shareable tracking links, historical analytics. ~8 weeks effort.
  - Plan: [docs/PLANNING/Implementation-Plan.md](PLANNING/Implementation-Plan.md) (Phase 3)

- [ ] **Phase 4: Intelligence** - ML-based ETA prediction (TimescaleDB history), weather-adjusted delays, passenger load prediction (e-ticket data), congestion factors, anomaly detection, public developer API. Ongoing.
  - Plan: [docs/PLANNING/Implementation-Plan.md](PLANNING/Implementation-Plan.md) (Phase 4)

### CMS Pages (from PRD MVP scope)

- [ ] **Stop Management Page** - CMS page for stops with map-based placement, proximity filter (currently Haversine, PostGIS after Phase 1 infra), bulk import from GTFS stops.txt. Backend CRUD exists, frontend page needed.
- [ ] **Schedule Management Page** - Timetable grid view, service calendar, trip CRUD, schedule validation against GTFS spec.
- [ ] **GTFS Import/Export Page** - Upload GTFS ZIP, parse/validate, bulk insert. Export GTFS-compliant ZIP from database.

## Completed

### Backend Features

- [x] **RAG Knowledge Base** - Hybrid search (pgvector + fulltext + RRF), multi-format ingestion (PDF, DOCX, email, image OCR, text), configurable embeddings (OpenAI/Jina/local), cross-encoder reranking, agent tool integration. 20 unit tests. (commit 8544237)

- [x] **Latvian Language Support** - Rewritten agent system prompt with Latvian language rules, 30+ transit term glossary, diacriticless input understanding. LLM upgraded to Claude Sonnet 4.5, embeddings switched to Jina v3 for explicit Latvian support. Frontend i18n diacritics fixed. (commit 17ce1a9)
  - Research: [docs/PLANNING/latvian-language-and-model-research.md](PLANNING/latvian-language-and-model-research.md)

- [x] **Stop Management CRUD** - Backend vertical slice with SQLAlchemy models, Haversine proximity search (plain Float columns), Pydantic schemas, async repository, 6 REST endpoints. (commit f88efc5)

- [x] **AI Chat Page** - CMS chat page with real LLM integration via agent service /v1/chat/completions endpoint, streaming SSE responses, bilingual i18n. (commit 3dad10b)

- [x] **Obsidian Vault Tools (4)** - query_vault (5 actions), manage_notes (5 actions), manage_folders (4 actions), bulk_operations (5 actions with dry_run). 68 unit tests. (commit 0bc02c3)

- [x] **Transit Tools (5)** - query_bus_status, get_route_schedule, search_stops, get_adherence_report, check_driver_availability. 104 unit tests. (commits 3472688-b25885f)

- [x] **Transit REST API** - GET /api/v1/transit/vehicles for frontend map polling, enriches GTFS-RT with static data. 9 unit tests. (commit 032e617)

- [x] **DDoS Defense** - nginx rate limiting, connection limits, security headers, slowapi per-IP limits, body size middleware, query quota tracker. (commit 643b23e)

### Frontend Features

- [x] **Dashboard** - Calendar, metric cards, compact spacing system. (commit 852ee95)

- [x] **Routes Page** - Filterable route list, detail view, live bus map (Leaflet + OSM), resizable split panels, CRUD, 26 mock routes, 142 i18n keys per locale. (commit 3d20139)

- [x] **Mobile Responsive Routes** - Tab-based Table/Map switching, collapsible filter Sheet, hamburger sidebar. (commit 032e617)

- [x] **Route Type Filtering** - Bus/trolleybus/tram filter for live map vehicles. (commit 42a3154)

- [x] **Design Tokens** - Three-tier tokens (primitive, semantic, component), active state styling. (commit 801640d)

- [x] **Performance Fixes** - Self-hosted fonts, dashboard converted to RSC, build optimizations. (commit fcfea8a)

### Infrastructure & Tooling

- [x] **Slash Commands (23)** - 16 backend + 7 frontend AI-assisted development commands. Full pipeline: prime -> planning -> execute -> validate -> commit.

- [x] **Docker Compose** - PostgreSQL (pgvector/pgvector:pg18), FastAPI app, Next.js CMS, nginx reverse proxy with resource limits.

## Planning Documents

| Document | Path | Description |
|----------|------|-------------|
| Implementation Plan | [docs/PLANNING/Implementation-Plan.md](PLANNING/Implementation-Plan.md) | Full Latvia transit platform (4 phases, 16+ weeks) |
| RAG Improvements | [docs/PLANNING/rag-improvements.md](PLANNING/rag-improvements.md) | Knowledge base enhancements (10 improvements) |
| SOP Automation | [docs/PLANNING/sop-file-automation.md](PLANNING/sop-file-automation.md) | Automated ingestion + SOP generation |
| Latvian Language Research | [docs/PLANNING/latvian-language-and-model-research.md](PLANNING/latvian-language-and-model-research.md) | Model benchmarks, embedding selection, DMS architecture |
| Command Architecture | [docs/PLANNING/command-planning.md](PLANNING/command-planning.md) | Slash command design decisions and audit |
