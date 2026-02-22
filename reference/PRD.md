# VTV — Product Requirements Document

> Unified CMS and AI Agent Service for Riga City Bus Operations

---

## 1. Executive Summary

VTV is a unified web portal for managing Riga's public transit operations — routes, schedules, fleet, drivers, and real-time tracking — with an embedded AI assistant for dispatchers and a personal knowledge management integration via Obsidian.

The system targets Rigas Satiksme (RS), a municipal transit operator running 1,097 vehicles across ~80 routes. The platform replaces fragmented manual workflows with a GTFS-compliant CMS backed by an AI agent capable of querying transit data and managing an Obsidian knowledge vault through a single unified interface.

**Key differentiator:** Compliance-first integration layer priced below EU procurement thresholds, with AI-assisted dispatch operations built on Pydantic AI.

---

## 2. Mission

Provide RS dispatchers and administrators with a single platform to manage transit operations, maintain regulatory compliance (GTFS, NeTEx, SIRI, GDPR), and access AI-powered operational insights — while keeping the technology stack minimal, the deployment self-contained, and the LLM provider fully swappable (cloud API or 100% local with zero recurring AI costs).

---

## 3. Target Users

| Role | Count | Primary Use |
|------|-------|-------------|
| **Dispatchers** | ~10-15 | Real-time operations, schedule queries, AI assistant |
| **Administrators** | ~10-20 | Route/schedule CRUD, GTFS import/export, fleet management |
| **Planners** | ~3-5 | Schedule optimization, reporting, analytics |
| **System Admin** | 1-2 | User management, configuration, deployment |

---

## 4. MVP Scope

### 4.1 What's In (MVP)

**CMS (Next.js 16 Turborepo Monorepo)**
- Route management — CRUD with map visualization (react-leaflet v5 + OpenStreetMap) ✅ (full-stack: real API with server pagination, all GTFS route types 0-12, route color mapping for live vehicle markers)
- Stop management — CRUD with geolocation, Haversine proximity search, Leaflet map with click-to-place and terminus markers ✅ (PostGIS planned for Phase 1 completion)
- Schedule management — service calendar, trip CRUD, GTFS import ✅ (full-stack: backend 22 endpoints + frontend CMS page with 3 tabs)
- GTFS import/export — parse and generate GTFS ZIP files ✅ (import via POST + export via GET, 7 CSV files each)
- Authentication — Auth.js v5 with 4-role RBAC (admin, dispatcher, editor, viewer) ✅ (DB-backed via `POST /api/v1/auth/login`, bcrypt, brute-force lockout)
- Internationalization — Latvian (primary) + English ✅ (proper diacritics, 142+ i18n keys per locale)
- Responsive dashboard layout (✅ dashboard + routes + chat pages are mobile responsive)

**AI Agent Service (FastAPI + Pydantic AI)**
- Single unified agent with transit + vault + knowledge tools
- OpenAI-compatible `/v1/chat/completions` endpoint
- Streaming (SSE) and non-streaming support
- 4 Obsidian vault tools (query, notes, folders, bulk)
- 5 read-only transit tools (bus status, schedules, stops, adherence, drivers)
- 1 knowledge base tool (RAG search over uploaded documents via pgvector) ✅
- Document management system (upload, metadata edit, download, content preview, Excel/CSV support) ✅
- Chat UI embedded in CMS ✅ (dedicated `/chat` page with streaming SSE, bilingual LV/EN)

**Infrastructure**
- Local Docker Compose deployment (agent service + Ollama + PostgreSQL)
- GTFS data seeded from RS public feed

### 4.2 What's Out (Post-MVP)

- ~~Live GPS tracking and real-time map~~ ✅ **Implemented** — Multi-feed GTFS-RT tracking with Redis caching, background pollers, 3 REST endpoints. Live map with react-leaflet v5, HTTP polling. Supports Riga + configurable additional feeds (Jurmala, Pieriga, ATD)
- ~~Vehicle and driver management (Phase 2)~~ **Driver management implemented** — Full CRUD backend (5 endpoints), CMS page with table/filters/forms, agent tool integration (DB-backed `check_driver_availability`). Vehicle management remains Phase 2
- NeTEx/SIRI compliance exports (Phase 3)
- Public-facing passenger information (out of scope)
- Fare management (handled by e-talons system)
- Mobile app

---

## 5. Architecture

### 5.1 System Overview

```
┌─────────────────────────────────────────────────┐
│       Next.js 16 CMS (Turborepo Monorepo)       │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │
│  │  Routes   │  │ Schedules│  │   AI Chat    │  │
│  │  Stops    │  │ Calendar │  │   Sidebar    │  │
│  │  GTFS     │  │ Trips    │  │              │  │
│  └────┬─────┘  └────┬─────┘  └──────┬───────┘  │
│       │              │               │          │
│       └── REST API + @vtv/sdk ───────┘          │
│              │                       │          │
│     Next.js API routes       POST /v1/chat/     │
│              │               completions        │
│     PostgreSQL (self-hosted + pgvector)  │      │
└──────────────────────────────────────┼──────────┘
                                       │
                          ┌────────────▼──────────┐
                          │  FastAPI Agent Service │
                          │                       │
                          │  Unified Pydantic AI   │
                          │  Agent with all tools  │
                          │                       │
                          │  Transit  Obsidian  KB │
                          │  Tools    Tools    Tool │
                          │  (5)      (4)     (1)  │
                          │     │        │     │   │
                          │  GTFS-RT  Obsidian  pg │
                          │  + GTFS   REST API  vector│
                          │  feeds    via httpx    │
                          └────────────────────────┘
```

### 5.2 Technology Stack (12 Technologies, 1 Primary Language)

| Layer | Technology | Justification |
|-------|-----------|---------------|
| Language | TypeScript 5.x | Single language for CMS monolith |
| CMS Framework | Next.js 16 (App Router) | Full-stack, production-ready, enterprise patterns via implementation |
| UI | Shadcn/ui + Tailwind v4 | No framework lock-in, CSS variable theming |
| Data Tables | TanStack Table v8 | Server-side filtering/pagination |
| API | REST + @vtv/sdk (OpenAPI-generated) | Type-safe client from FastAPI spec; tRPC v11 planned for CMS-native routes |
| ORM | SQLAlchemy 2.0 (async) | Backend ORM with pgvector; Drizzle planned for CMS PostGIS layer |
| Database | PostgreSQL 18 + pgvector | Vector search for RAG; PostGIS planned for spatial queries |
| Maps | react-leaflet v5 + Leaflet 1.9 | OpenStreetMap tiles, marker clustering planned |
| Auth | Auth.js v5 | Self-hosted RBAC, data sovereignty |
| Agent Framework | Pydantic AI 1.58+ | Strongest Python agent framework |
| Agent API | FastAPI | OpenAI-compatible endpoints |
| Agent LLM | Swappable (Ollama / Anthropic / OpenAI / any) | Single env var switch; zero-cost local or cloud API |

### 5.3 Deployment (Current)

```yaml
# docker-compose.yml (actual)
services:
  db:           # pgvector/pgvector:pg18 (PostgreSQL 18 + pgvector) — port 5433, healthcheck
  redis:        # redis:7-alpine — real-time vehicle position cache, healthcheck
  migrate:      # Alembic auto-migration (runs once, service_completed_successfully)
  app:          # FastAPI + Pydantic AI (non-root) — internal only, healthcheck
  cms:          # Next.js 16 — internal only, healthcheck
  nginx:        # Reverse proxy — port 80 (rate limiting, granular body size limits, security headers)

# All services have healthchecks and dependency ordering via depends_on conditions.
# Planned additions (see docs/PLANNING/Implementation-Plan.md):
  # PostGIS extension — spatial queries (switch db image)
  # Ollama — local LLM (fallback/dev)
```

All services run locally via Docker Compose with resource limits. LLM is fully configurable — currently using cloud Anthropic (Claude Sonnet 4.5), switchable to Ollama for zero API cost or any provider via env vars. See Section 6.4 for LLM provider strategy.

---

## 6. Unified AI Agent

### 6.1 Design Philosophy

One agent, all tools. The LLM decides which tools to use based on the user's query. No routing logic, no agent registry — the agent has access to 10 tools and selects the appropriate ones per request.

```python
agent = Agent(
    'anthropic:claude-sonnet-4-5',
    deps_type=UnifiedDeps,
    output_type=str,
    instructions="You are a transit operations and knowledge management assistant...",
    tools=[
        # Transit (5 read-only)
        query_bus_status,
        get_route_schedule,
        search_stops,
        get_adherence_report,
        check_driver_availability,
        # Obsidian (4 vault tools)
        obsidian_query_vault,
        obsidian_manage_notes,
        obsidian_manage_folders,
        obsidian_bulk_operations,
        # Knowledge base (1 RAG search)
        search_knowledge_base,
    ]
)
```

### 6.2 Transit Tools (Read-Only)

| Tool | Purpose | Data Source |
|------|---------|------------|
| `query_bus_status` ✅ | Current delay/position status for a route or vehicle | GTFS-RT feeds (Rigas Satiksme) |
| `get_route_schedule` ✅ | Timetable for a specific route and service date | GTFS static ZIP (stop_times, calendar, calendar_dates) |
| `search_stops` ✅ | Search stops by name or proximity (lat/lon) | GTFS static ZIP (stops.txt, stop_times.txt) |
| `get_adherence_report` ✅ | On-time performance metrics for routes/periods | GTFS-RT trip updates + GTFS static ZIP |
| `check_driver_availability` ✅ | Available drivers for a shift/date | DB-backed via `app/drivers/` (fallback: mock data for tests) |

All transit tools are read-only. The agent cannot create, update, or delete any transit data. This is a safety constraint — AI advises, humans decide.

### 6.3 Obsidian Vault Tools

| Tool | Purpose | Actions |
|------|---------|---------|
| `obsidian_query_vault` | Search and discover vault content | search, find_by_tags, list, recent, glob |
| `obsidian_manage_notes` | Individual note operations | create, read, update, delete, move |
| `obsidian_manage_folders` | Folder operations | create, delete, list, move |
| `obsidian_bulk_operations` | Batch operations with dry_run | move, tag, delete, update_frontmatter, create |

Full tool specifications in [mvp-tool-designs.md](./mvp-tool-designs.md).

### 6.4 LLM Provider Strategy

The agent service treats the LLM as a swappable dependency. RS can run entirely on local models with zero API costs, use cloud APIs for better reasoning, or mix both with automatic failover.

#### Provider Configuration

A single environment variable controls which LLM powers the agent:

```bash
# Option 1: Cloud API (best reasoning, ~EUR 60-90/month)
LLM_PROVIDER=anthropic
LLM_MODEL=claude-sonnet-4-5

# Option 2: Fully local (zero cost, good reasoning)
LLM_PROVIDER=ollama
LLM_MODEL=llama3.1:70b

# Option 3: Local with cloud fallback (cost-optimized)
LLM_PROVIDER=ollama
LLM_MODEL=llama3.1:70b
LLM_FALLBACK_PROVIDER=anthropic
LLM_FALLBACK_MODEL=claude-sonnet-4-5
```

#### How It Works

Pydantic AI supports 15+ providers via `"provider:model"` syntax and `FallbackModel` for automatic failover:

```python
from pydantic_ai import Agent
from pydantic_ai.models.fallback import FallbackModel

def build_model(settings: LLMSettings):
    primary = f"{settings.provider}:{settings.model}"

    if settings.fallback_provider:
        fallback = f"{settings.fallback_provider}:{settings.fallback_model}"
        return FallbackModel(primary, fallback)

    return primary

agent = Agent(
    build_model(settings.llm),
    deps_type=UnifiedDeps,
    output_type=str,
    instructions="...",
    tools=[...],
)
```

If the primary model fails (timeout, rate limit, error), `FallbackModel` automatically tries the fallback — no code changes, no restarts.

#### Supported Providers

| Provider | Config Value | Example Models | Cost | Notes |
|----------|-------------|----------------|------|-------|
| **Ollama** (local) | `ollama` | `llama3.1:70b`, `qwen2.5:32b`, `mistral-large` | EUR 0/month | Requires GPU; 70B models need ~40GB VRAM |
| **Anthropic** | `anthropic` | `claude-sonnet-4-5`, `claude-haiku-4-5` | ~EUR 60-90/month | Best tool-use reasoning |
| **OpenAI** | `openai` | `gpt-4o`, `gpt-4o-mini` | ~EUR 40-80/month | Strong alternative |
| **Groq** (cloud, fast) | `groq` | `llama-3.3-70b-versatile` | Free tier available | Fast inference, open models |
| **OpenRouter** | `openrouter` | Any model | Pay-per-use | Gateway to 100+ models |
| **Any OpenAI-compatible** | `openai` + custom `base_url` | Any | Varies | LM Studio, vLLM, TGI, etc. |

#### Deployment Profiles

| Profile | LLM Config | Monthly Cost | Use Case |
|---------|-----------|-------------|----------|
| **Zero-cost local** | Ollama `llama3.1:70b` | EUR 0 | RS wants no API costs; has GPU server |
| **Budget local** | Ollama `qwen2.5:32b` | EUR 0 | Smaller GPU; acceptable quality |
| **Cloud optimized** | Haiku for routing + Sonnet for reasoning | ~EUR 30-50 | Best cost/quality ratio |
| **Cloud premium** | Claude Sonnet for everything | ~EUR 60-90 | Best quality, simplest config |
| **Hybrid** | Ollama primary + Claude fallback | ~EUR 10-20 | Local handles most queries; cloud for complex ones |

#### Local Model Requirements

For running locally without any cloud API dependency:

| Model | VRAM Required | Quality | Speed |
|-------|--------------|---------|-------|
| `llama3.1:8b` | ~6 GB | Adequate for simple queries | Fast |
| `llama3.1:70b` | ~40 GB | Strong tool use, good reasoning | Moderate |
| `qwen2.5:32b` | ~20 GB | Good balance of quality and resources | Moderate |
| `mistral-large` | ~40 GB | Strong multilingual (Latvian) | Moderate |

**Recommendation for RS:** Start with `llama3.1:70b` on a local GPU server. If tool selection accuracy drops below 85%, switch to Claude Sonnet or use the hybrid profile. The switch is a single env var change — no code changes, no redeployment needed.

#### Architecture Guarantee

The agent service is designed so that **no code path depends on a specific LLM provider**:

- Tools define their own JSON Schema — works identically across all providers
- Pydantic AI normalizes all provider APIs into a single interface
- Streaming SSE format is provider-agnostic (agent service encodes it)
- Tool descriptions are written for broad LLM compatibility, not Claude-specific
- Tests use `TestModel` / `FunctionModel` — no real LLM needed for CI

Switching providers is always a configuration change, never a code change.

### 6.5 LLM Recommendation for Transit Operations

Municipal transit companies have specific requirements that shape LLM selection:

**Why transit is a strong fit for local LLMs:**
- Queries are **domain-specific and repetitive** — "which routes are delayed?", "show schedule for route 22" — not open-ended creative tasks
- Tool selection is the hard part, not prose generation — local 70B models handle structured tool calls well
- **Data sovereignty matters** — transit operational data shouldn't leave RS infrastructure
- **Predictable costs** — municipal budgets are fixed; variable API costs are harder to justify in procurement
- **Latvian language** — local models like Mistral-Large and Qwen2.5 have strong multilingual support

**Recommended LLM strategy for RS:**

| Phase | Strategy | Rationale |
|-------|----------|-----------|
| **Development** | Claude Sonnet (cloud) | Fastest iteration, best tool-use accuracy for building/testing tools |
| **MVP pilot** | Ollama `llama3.1:70b` (local) | Prove the system works with zero API cost; validate tool accuracy |
| **Production** | Ollama local + Claude fallback | Local handles 80-90% of queries; cloud fallback for complex reasoning |
| **Scale (5+ agencies)** | Dedicated GPU server + fine-tuned model | Train on accumulated transit query data for domain-specific accuracy |

**Hardware for local deployment:**
- **Minimum:** 1x NVIDIA RTX 4090 (24GB VRAM) — runs `qwen2.5:32b` comfortably
- **Recommended:** 1x NVIDIA A100 40GB or 2x RTX 4090 — runs `llama3.1:70b` at production speed
- **Budget option:** AMD MI60/MI100 or used NVIDIA A6000 — available in EU secondary market
- **Cloud GPU fallback:** Hetzner dedicated GPU servers from ~EUR 150/month (still cheaper than API costs at scale)

A one-time EUR 2,000-4,000 GPU investment eliminates all recurring LLM costs permanently. At 50 queries/day across 15 dispatchers, this pays for itself within 2-3 months versus cloud API pricing.

### 6.6 Safety Constraints

- Transit tools: read-only, no write operations
- Knowledge base tool: read-only search, no document management via agent
- Vault delete operations: require `confirm: true`
- Bulk operations: support `dry_run` for preview
- Path sandboxing: prevents directory traversal (`../`)
- No vault file access outside configured vault path
- Monthly spending cap on Claude API (EUR 100 hard limit)
- Token budget per user per day (50 queries)

---

## 7. CMS Core Features (MVP)

### 7.1 Route Management ✅ (Full-stack — Backend API + Frontend CMS page)

- ✅ Filterable route list with search, type filter, agency filter — real API with server-side pagination
- ✅ Route detail view (Sheet panel) with GTFS route ID, sort order, agency lookup
- ✅ Live bus map panel (Leaflet/OSM, live vehicle positions from backend, resizable 60/40 split, bidirectional route selection sync, route color map from API)
- ✅ Mobile responsive layout (tab-based Table/Map switching, collapsible filter Sheet, hamburger sidebar)
- ✅ CRUD operations (create, edit, delete) with role-based visibility — real API via `/api/v1/schedules/routes`
- ⬜ Route shape display on map from GTFS shapes.txt (deferred — requires polyline layer)
- ✅ Route type support: all GTFS types 0-12 (tram, subway, rail, bus, ferry, cable tram, gondola, funicular, trolleybus, monorail) with selectable filter
- ✅ Color utility: backend hex conversion ("FF7043" ↔ "#FF7043") for route color dots and vehicle markers
- ✅ Bilingual i18n (LV/EN) — expanded with all transport types and schedule-related keys

### 7.2 Stop Management ✅ (Full-stack — Backend CRUD + Frontend CMS page)

- ✅ Stop list with search, status filter, and Haversine proximity search (plain Float columns, PostGIS planned)
- ✅ Backend CRUD endpoints (create, read, update, delete, list, nearby) — 6 endpoints with server-side `location_type` filtering
- ✅ Map-based stop placement with click-to-place and drag-to-reposition (Leaflet + CARTO Voyager tiles)
- ✅ Terminus stop visualization — green markers for `location_type=1` (galapunkts), blue for regular stops
- ✅ Direction display — `stop_desc` shown in table rows and map popups (e.g., "Uz centru")
- ✅ Copyable GTFS stop IDs with clipboard feedback
- ✅ Resilient batch map loading (sequential batches of 5 with `Promise.allSettled` to handle rate limits)
- ✅ Bilingual i18n (332 keys each for LV/EN) — Galapunkts (LV) / Terminus (EN)
- ⬜ Stop hierarchy support (station > stop)
- ⬜ Bulk import from GTFS stops.txt
- ⬜ Migrate to PostGIS `ST_DWithin` for sub-ms spatial queries (see [Implementation-Plan.md](../docs/PLANNING/Implementation-Plan.md))

### 7.3 Schedule Management ✅ (Full-stack — Backend API + Frontend CMS page)

- ✅ Service calendar CRUD with weekday/weekend/holiday patterns (7 day flags + date range)
- ✅ Calendar exception management (calendar_dates: add/remove service on specific dates)
- ✅ Trip CRUD with stop_times bulk replace (atomic PUT operation)
- ✅ Schedule validation against GTFS spec (date ranges, references, time format, sequence ordering)
- ✅ GTFS ZIP import (parse 6 CSV files, bulk insert with FK resolution, skip unknown stops)
- ✅ Frontend CMS page with 3 tabs: Calendars (table, form, detail with exceptions), Trips (filterable table, form, detail with stop times), Import (ZIP upload + validation)
- ✅ Frontend API client (22 endpoints: agencies, routes, calendars, trips, import, validate)
- ⬜ Timetable grid view (frontend — rows = trips, columns = stops)
- ✅ GTFS export (generate ZIP from database — `GET /api/v1/schedules/export`)

### 7.4 GTFS Import/Export

- ✅ Import: upload GTFS ZIP, parse 6 core CSV files, validate references, bulk insert (via `/api/v1/schedules/import`)
- ✅ Export: generate GTFS-compliant ZIP from database (7 CSV files: agency, routes, calendar, calendar_dates, trips, stop_times, stops — via `GET /api/v1/schedules/export`)
- ✅ Validation: check referential integrity, time consistency, required fields (via `/api/v1/schedules/validate`)
- ⬜ Seed database from RS public feed (`https://saraksti.rigassatiksme.lv/gtfs.zip`)

### 7.5 Authentication & Authorization

| Role | Routes | Schedules | GTFS | Users | AI Chat |
|------|--------|-----------|------|-------|---------|
| Admin | CRUD | CRUD | Import/Export | CRUD | Yes |
| Dispatcher | Read | Read | Export | — | Yes |
| Editor | CRUD | CRUD | Import/Export | — | Yes |
| Viewer | Read | Read | — | — | No |

### 7.6 Dashboard Layout

```
┌─────────────────────────────────────────────────┐
│  [Logo]  Riga Transit CMS     Search   Alerts   │
├──────┬──────────────────────────┬───────────────┤
│      │                          │               │
│ Nav  │   Main Content           │ AI Chat       │
│      │   (Map / Table / Form)   │ Sidebar       │
│ Routes│                         │               │
│ Stops │                         │ "What routes  │
│ Sched │                         │  are delayed?"│
│ GTFS  │                         │               │
│      │                          │               │
├──────┴──────────────────────────┴───────────────┤
│ Status: 42 active  ·  3 delayed  ·  1 alert    │
└─────────────────────────────────────────────────┘
```

---

## 8. Data Model (GTFS-Aligned)

### Core Tables

```
agencies        → Transit operators (RS)
routes          → Bus/tram/trolleybus lines
stops           → Stops with lat/lon floats (PostGIS geometry planned)
calendar        → Weekly service patterns
calendar_dates  → Holiday/exception overrides
trips           → Individual journeys on routes
stop_times      → Arrival/departure times per trip per stop
shapes          → Route geometry (linestring + encoded polyline)
```

### Auth Tables

```
users           → Email, bcrypt hashed password, role (admin/dispatcher/editor/viewer), brute-force lockout ✅
sessions        → Auth.js session management (JWT-based, no server sessions table needed)
```

---

## 9. API Design

### CMS API (tRPC v11)

```
routes.list / getById / create / update / delete / getShape
stops.list / nearby / getById / create / update / search
schedules.getByRoute / getTrips / createTrip / updateStopTimes / getCalendar
gtfs.import / export / validate / status
```

### REST Endpoints

```
POST   /api/gtfs/import       — Upload GTFS ZIP
GET    /api/gtfs/export        — Download GTFS ZIP
GET    /api/gtfs/feed.zip      — Public GTFS feed
```

### Agent API (FastAPI, OpenAI-Compatible)

```
POST   /v1/chat/completions   — Chat (streaming + non-streaming)
GET    /v1/models              — List available models
GET    /health                 — Health check
```

---

## 10. Compliance

### GDPR

- Driver data pseudonymized in database
- GPS tracking data retained max 90 days (Phase 2)
- DPIA required before Phase 2 driver tracking
- No tracking during driver rest periods
- Public GTFS-RT feeds use fleet numbers, not driver IDs
- Data export and deletion on request

### EU Transit Regulations

- GTFS static export compliant with MMTIS Delegated Regulation
- NeTEx/SIRI exports planned for Phase 3
- Data published to Latvian National Access Point (data.gov.lv)

### Data Sovereignty

- All data stored in EU (PostgreSQL on Supabase EU region or self-hosted)
- Auth.js self-hosted (no third-party auth provider)
- Obsidian vault data stays local (never uploaded)

---

## 11. Success Criteria (MVP)

| Criteria | Target |
|----------|--------|
| GTFS import | Parse RS feed (80 routes, 2000+ stops) in < 30 seconds |
| Route CRUD | Create, edit, delete routes with map visualization |
| Schedule editing | Edit timetable grid, save, export as valid GTFS |
| AI response time | < 5 seconds for transit queries, < 3 seconds for vault queries |
| AI accuracy | Correct tool selection on > 90% of dispatcher queries |
| Concurrent users | Support 20 simultaneous users |
| Uptime | 99% (local deployment) |
| Cost (cloud LLM) | < EUR 120/month total (infrastructure + LLM API) |
| Cost (local LLM) | < EUR 30/month total (infrastructure only, EUR 0 LLM cost) |

---

## 12. Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Drizzle + PostGIS integration issues | Medium | High | Week 1 spike; fallback to Kysely + raw SQL |
| LLM API costs exceed budget | Medium | Medium | Swappable provider: run Ollama locally for EUR 0, or hard cap EUR 100/month on cloud APIs |
| RS GTFS feed format changes | Low | High | Validate on import, alert on schema mismatch |
| Obsidian Local REST API limitations | Low | Medium | Extend via Dataview DQL, fallback to direct filesystem |
| GDPR violation from GPS tracking | High | Critical | Defer to Phase 2, engage Latvian DPA lawyer first |
| Scope creep beyond MVP | High | High | Strict phase gates, this PRD defines the boundary |

---


## 13. References

- [Implementation Plan](../docs/PLANNING/Implementation-Plan.md) — Full Latvia transit platform roadmap (4 phases: foundation, full Latvia coverage, intercity gap-fill, ML intelligence)
- [Master Plan](./PLANNING/plan.md) — Full 71KB planning document
- [MVP Tool Designs](./mvp-tool-designs.md) — Detailed Obsidian tool specifications
- [Architecture Diagrams](./diagrams/architecture-diagrams.md) — C4 model and data flows
- [RS GTFS Feed](https://saraksti.rigassatiksme.lv/gtfs.zip) — Live static GTFS data
- [RS GTFS-RT Feed](https://saraksti.rigassatiksme.lv/gtfs_realtime.pb) — Live real-time data
- [Anthropic Tool Design Guide](https://www.anthropic.com/engineering/writing-tools-for-agents) — Tool architecture principles
- [mcp-obsidian](https://github.com/MarkusPfundstein/mcp-obsidian) — MCP server architecture reference
