# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

VTV is a unified transit operations platform targeting all of Latvia's public transit, starting with Riga's municipal bus system. This repository contains the **AI Agent Service** — a FastAPI + Pydantic AI application providing a unified agent with 10 tools (5 transit + 4 Obsidian vault + 1 knowledge base). Built with **vertical slice architecture**, optimized for AI-assisted development. Python 3.12+, strict type checking with MyPy and Pyright. The platform roadmap extends to multi-feed real-time tracking, Redis caching, PostGIS spatial queries, and ML-based predictions — see `docs/PLANNING/Implementation-Plan.md`.

## Core Principles

**KISS** (Keep It Simple, Stupid)

- Prefer simple, readable solutions over clever abstractions

**YAGNI** (You Aren't Gonna Need It)

- Don't build features until they're actually needed

**Vertical Slice Architecture**

- Each feature owns its database models, schemas, routes, and business logic
- Features live in separate directories under `app/` (e.g., `app/products/`, `app/orders/`)
- Shared utilities go in `app/shared/` only when used by 3+ features
- Core infrastructure (`app/core/`) is shared across all features

**Type Safety (CRITICAL)**

- Strict type checking enforced (MyPy + Pyright in strict mode)
- All functions, methods, and variables MUST have type annotations
- Zero type suppressions allowed
- All functions must have complete type hints
- Strict mypy & pyright configuration is enforced
- No `Any` types without explicit justification
- Test files have relaxed typing rules (see pyproject.toml)

**Python Anti-Patterns (avoid these — they cause lint/type errors)**

1. **No `assert` in production code** — Ruff S101 forbids assert outside test files. Use conditional checks:
   - BAD: `assert cache is not None; return cache.data`
   - GOOD: `if cache is not None: return cache.data`
2. **No `object` type hints** — Forces isinstance + assert chains. Import and use the actual type:
   - BAD: `def process(data: object) -> str:` then `assert isinstance(data, MyClass)`
   - GOOD: `def process(data: MyClass) -> str:`
3. **Untyped third-party libraries** — When a dependency lacks `py.typed` (e.g., protobuf-generated code):
   - mypy: Add `[[tool.mypy.overrides]]` with `ignore_missing_imports = true` for the module
   - pyright: Add file-level `# pyright: reportUnknownVariableType=false` directives to the ONE file that interfaces with the untyped library
   - **NEVER use pyright `[[executionEnvironments]]` with a scoped `root`** — it breaks import resolution for `app.*` modules
4. **Mock exceptions must match catch blocks** — If code catches `httpx.HTTPError`, mock with `httpx.ConnectError`, not `Exception`
5. **Only import what you use** — Ruff F401 catches unused imports. Don't import `field` from dataclasses unless you call `field()`
6. **No unnecessary noqa/type-ignore** — Ruff RUF100 flags unused suppression comments
7. **No EN DASH in strings** — Ruff RUF001 forbids ambiguous Unicode like `–` (EN DASH). LLMs generate these in time ranges and prose. Always use `-` (HYPHEN-MINUS)
8. **Pydantic AI `ctx` must be referenced** — Ruff ARG001 flags unused args. Tool functions require `ctx: RunContext[...]` — always reference it (e.g., `_settings = ctx.deps.settings`)
9. **Narrow dict unions before Pydantic** — `dict[str, str | list[str] | None]` values are too broad for `str | None` fields. Use isinstance: `str(val) if isinstance(val := d.get("key"), str) else None`
10. **Untyped lib decorators need 3-layer fix** — When adding an untyped lib (e.g., slowapi): (a) mypy `[[overrides]]` with `ignore_missing_imports`, (b) pyright file-level directives on EVERY file using the decorator, (c) ruff per-file-ignores for ARG001 if lib forces unused params. All three simultaneously.
11. **Test imports must precede module-level setup** — `limiter.enabled = False` after imports triggers Ruff E402. All `from ... import` lines first, then setup.
12. **No `type: ignore` in test files** — mypy relaxes tests. `# type: ignore[arg-type]` becomes "unused ignore". Use pyright file-level `# pyright: reportArgumentType=false` instead.
13. **Pydantic constraints on shared models affect all paths** — `max_length` on a shared model blocks both input AND output. Put input-only validation in a `field_validator` on the REQUEST model.
14. **Singleton close must catch RuntimeError** — TestClient closes event loop before lifespan cleanup. Wrap `await client.aclose()` in `try/except RuntimeError: pass`.
15. **`verify=False` needs `# noqa: S501`** — Ruff S501 flags `httpx.AsyncClient(verify=False)`. Add `# noqa: S501` with comment explaining why.
16. **ARG001 applies to ALL unused params** — Not just `ctx`. Use `_ = param_name` for intentionally unused params.
17. **`dict.get()` returns full union - use walrus** — `isinstance(d.get("k"), int)` doesn't narrow `d["k"]`. Use `val if isinstance(val := d.get("k"), int) else None`.
18. **Dict literal invariance in tests** — `{"k": "v"}` inferred as `dict[str, str]` not compatible with `dict[str, str | None]`. Add explicit annotations.
19. **Lazy-loaded untyped lib models use `Any`, not `object`** — `object` blocks `.encode()/.predict()` (mypy `attr-defined`). Use `Any | None` + `# noqa: ANN401` on `-> Any` helpers.
20. **Dataclass `field(default_factory=dict)` needs typed lambda** — Pyright infers `dict[Unknown, Unknown]`. Use `field(default_factory=lambda: dict[str, str | int | None]())`.
21. **Untyped lib method returns need `str()` wrapping** — `page.get_text()`, `pytesseract.image_to_string()` return `Unknown`. Wrap in `str()`.
22. **Partially annotated test functions need `-> None`** — Adding param type (e.g., `tmp_path: Path`) without return type triggers mypy `no-untyped-def`. Always: `def test_foo(param: Type) -> None:`.
23. **Pydantic `Field(None)` confuses pyright about defaults** — Pass defaulted fields explicitly in tests: `Model(required="x", optional=None)`.

**AI-Optimized Patterns**

- Structured logging: Use `domain.component.action_state` pattern (hybrid dotted namespace)
  - Format: `{domain}.{component}.{action}_{state}`
  - Examples: `user.registration_started`, `product.create_completed`, `agent.tool.execution_failed`
  - See `docs/logging-standard.md` for complete event taxonomy
- Request correlation: All logs include `request_id` automatically via context vars
- Consistent verbose naming: Predictable patterns for AI code generation

## Slash Commands

23 AI-assisted development commands (16 backend + 7 frontend). Run with `/command-name` in Claude Code. Full documentation: `.claude/commands/CLAUDE.md`.

### Backend Commands

| Command | Description |
|---------|-------------|
| `/be-init-project` | Initialize and validate the VTV development environment |
| `/be-create-feature` | Scaffold a complete vertical slice feature directory |
| `/be-prime` | Load full VTV project context into the current session |
| `/be-prime-tools` | Load AI agent tool designs, patterns, and architecture context |
| `/be-planning` | Research codebase and create a self-contained implementation plan |
| `/be-execute` | Execute a VTV implementation plan file step by step |
| `/implement-fix` | Apply the fix described in an RCA document with regression tests |
| `/be-validate` | Run all quality checks — formatting, linting, type checking, and tests |
| `/review` | Review code against all 8 VTV quality standards |
| `/code-review-fix` | Fix issues found in a code review report |
| `/commit` | Stage files and create a conventional commit with safety checks |
| `/rca` | Investigate a bug and produce a root cause analysis document |
| `/execution-report` | Generate report comparing implementation against the plan |
| `/system-review` | Analyze implementation vs plan for process improvements |
| `/update-docs` | Update project documentation after a feature is implemented and committed |
| `/be-end-to-end-feature` | Autonomously develop a complete feature through all 6 phases |

### Frontend Commands

| Command | Description |
|---------|-------------|
| `/fe-prime` | Load full VTV frontend context (design system, components, pages, i18n, RBAC) |
| `/fe-planning` | Research frontend codebase and create a page/feature implementation plan |
| `/fe-create-page` | Scaffold a new Next.js page with i18n, RBAC, sidebar nav, and design tokens |
| `/fe-execute` | Execute a frontend implementation plan file step by step |
| `/fe-validate` | Run frontend quality checks — TypeScript, lint, build, design system, i18n, a11y |
| `/fe-review` | Review frontend code against all 8 VTV frontend quality standards |
| `/fe-end-to-end-page` | Autonomously develop a complete frontend page through all 6 phases |

**Workflows:** Feature dev, bug fix, code quality, agent tools, process improvement — see `.claude/commands/CLAUDE.md` for chained workflows.

**Frontend workflow:** `/fe-prime` → `/fe-planning` → `/fe-execute` → `/fe-validate` → `/commit`

## Essential Commands

### Development

```bash
# Start development server (port 8123)
uv run uvicorn app.main:app --reload --port 8123
```

### Testing

```bash
# Run unit tests (354 tests, ~7s execution)
uv run pytest -v -m "not integration"

# Run all tests including integration (182 tests, requires Docker)
uv run pytest -v

# Run integration tests only
uv run pytest -v -m integration

# Run specific test
uv run pytest -v app/core/tests/test_database.py::test_function_name
```

### Type Checking must be green

```bash
# MyPy (strict mode)
uv run mypy app/

# Pyright (strict mode)
uv run pyright app/
```

### Linting & Formatting must be green

```bash
# Check linting
uv run ruff check .

# Auto-format code
uv run ruff format .
```

### Database Migrations

```bash
# Create new migration
uv run alembic revision --autogenerate -m "description"

# Apply migrations
uv run alembic upgrade head

# Rollback one migration
uv run alembic downgrade -1

# Start PostgreSQL (Docker)
docker-compose up -d
```

### Docker

```bash
# Build and start all services (requires AUTH_SECRET env var)
AUTH_SECRET=$(openssl rand -base64 32) docker-compose up -d --build

# View app logs
docker-compose logs -f app

# Stop all services
docker-compose down
```

**Docker services:** `db` (PostgreSQL + pgvector), `app` (FastAPI, non-root user), `cms` (Next.js), `nginx` (reverse proxy on port 80). App and CMS are internal-only (expose, not ports) — nginx proxies all external traffic. Resource limits enforced per service. **Planned additions:** Redis (real-time cache), PostGIS extension (spatial queries) — see `docs/PLANNING/Implementation-Plan.md`.

## Architecture

### Project Structure

```
VTV/
├── app/
│   ├── core/           # Infrastructure (config, database, logging, middleware, health, rate_limit, exceptions)
│   │   └── agents/     # AI agent module (see Agent Module below)
│   │       ├── quota.py     # Daily per-IP query quota tracker (50/day default)
│   │       ├── tools/
│   │       │   ├── transit/  # Transit tools (5/5 implemented ✅)
│   │       │   ├── obsidian/ # Obsidian vault tools (4/4 implemented ✅)
│   │       │   └── knowledge/# Knowledge base search tool (1/1 implemented ✅)
│   │       └── tests/
│   ├── shared/         # Cross-feature utilities (pagination, timestamps, error schemas)
│   ├── knowledge/      # RAG knowledge base + document management system (DMS)
│   │   ├── models.py       # Document (title, description, file_path), DocumentChunk (pgvector Vector(1024))
│   │   ├── schemas.py      # DocumentUpload/Update/Response, DocumentContentResponse, DomainListResponse, Search*
│   │   ├── repository.py   # CRUD + vector search + fulltext search + domain listing
│   │   ├── service.py      # Ingest pipeline + hybrid search + DMS operations (update, download, content)
│   │   ├── embedding.py    # Configurable embedding provider (OpenAI/Jina/local)
│   │   ├── processing.py   # Multi-format text extraction (PDF, DOCX, Excel, CSV, email, image, text)
│   │   ├── chunking.py     # Recursive text chunking with overlap
│   │   ├── reranker.py     # Cross-encoder reranking (local/noop)
│   │   ├── routes.py       # 9 REST endpoints under /api/v1/knowledge (CRUD + download + content + domains + search)
│   │   └── tests/          # 30 unit tests
│   ├── stops/          # Stop management (CRUD with Haversine proximity search)
│   │   ├── schemas.py      # StopCreate, StopUpdate, StopResponse, StopNearbyParams
│   │   ├── models.py       # Stop model with plain Float lat/lon columns
│   │   ├── repository.py   # Async CRUD + Haversine proximity search
│   │   ├── service.py      # Business logic + structured logging
│   │   ├── exceptions.py   # StopNotFoundError, DuplicateStopError
│   │   ├── routes.py       # 6 REST endpoints under /api/v1/stops
│   │   └── tests/          # Unit tests (repository, service, routes)
│   ├── transit/        # Transit REST API (real-time vehicle positions for CMS frontend)
│   │   ├── schemas.py      # VehiclePosition, VehiclePositionsResponse
│   │   ├── service.py      # TransitService — enriches GTFS-RT with static data (in-memory cache)
│   │   ├── routes.py       # GET /api/v1/transit/vehicles (rate limited: 30/min)
│   │   └── tests/          # 9 unit tests
│   │   # Planned: GTFS importer, GTFS-RT poller, Redis pipeline, WebSocket — see Implementation-Plan.md
│   ├── main.py         # FastAPI application entry point
│   ├── {feature}/      # Feature slices (e.g., products/, orders/)
│   └── tests/          # Integration tests spanning multiple features
├── reference/          # Architecture docs and templates
│   ├── vsa-patterns.md         # Async VSA patterns (repository, service, routes, cross-feature)
│   ├── feature-readme-template.md  # Template for feature README.md files
│   ├── PRD.md                  # Product requirements document
│   └── mvp-tool-designs.md    # Agent tool specifications
├── cms/               # Frontend monorepo (Turborepo + pnpm workspaces)
│   ├── apps/web/          # Next.js 16 application (@vtv/web)
│   ├── packages/ui/       # Design tokens and shared UI (@vtv/ui)
│   ├── packages/sdk/      # OpenAPI TypeScript client (@vtv/sdk)
│   ├── packages/typescript-config/  # Shared tsconfig presets
│   └── design-system/vtv/ # Design system docs (MASTER.md + page overrides)
├── nginx/             # Reverse proxy (rate limiting, connection limits, defense-in-depth)
│   ├── nginx.conf         # Rate limiting zones, upstream backends, security headers
│   └── Dockerfile         # nginx:1.27-alpine
├── .claude/commands/   # 23 slash commands (see .claude/commands/CLAUDE.md for full docs)
├── .agents/            # Agent workflow outputs
│   ├── plans/              # Implementation plans created by /be-planning
│   ├── code-reviews/       # Code review reports created by /review
│   ├── execution-reports/  # Execution reports created by /execution-report
│   └── system-reviews/     # System reviews created by /system-review
├── docs/rca/           # Root cause analysis documents created by /rca
├── alembic/            # Database migration scripts
└── pyproject.toml      # Dependencies, tooling config (ruff, mypy, pyright, pytest)
```

### Database

**SQLAlchemy Setup**

- Async engine with connection pooling (pool_size=5, max_overflow=10)
- Base class: `app.core.database.Base` (extends `DeclarativeBase`)
- Session dependency: `get_db()` from `app.core.database`
- All models should inherit `TimestampMixin` from `app.shared.models` for automatic `created_at`/`updated_at`

**Migration Workflow**

1. Define/modify models inheriting from `Base` and `TimestampMixin`
2. Run `uv run alembic revision --autogenerate -m "description"`
3. Review generated migration in `alembic/versions/`
4. Apply: `uv run alembic upgrade head`

### Logging

**Philosophy:** Logs are optimized for AI agent consumption. Include enough context for an LLM to understand and fix issues without human intervention.

**Structured Logging (structlog)**

- JSON output for AI-parseable logs
- Request ID correlation using `contextvars`
- Logger: `from app.core.logging import get_logger; logger = get_logger(__name__)`
- Event naming: Hybrid dotted namespace pattern `domain.component.action_state`
  - Examples: `user.registration_completed`, `database.connection_initialized`, `request.http_received`
  - Detailed taxonomy: See `docs/logging-standard.md`
- Exception logging: Always include `exc_info=True` for stack traces

**Event Pattern Guidelines:**

- **Format:** `{domain}.{component}.{action}_{state}`
- **Domains:** application, request, database, health, agent, external, feature-name
- **States:** `_started`, `_completed`, `_failed`, `_validated`, `_rejected`, `_retrying`
- **Why:** OpenTelemetry compliant, AI/LLM parseable, grep-friendly, scalable for agents

**Middleware**

- `BodySizeLimitMiddleware`: Rejects requests >100KB with HTTP 413
- `RequestLoggingMiddleware`: Logs all requests with correlation IDs
- `CORSMiddleware`: Configured for local development (see `app.core.config`)
- Adds `X-Request-ID` header to all responses

**Rate Limiting (slowapi)**

- Per-IP rate limiting via `app.core.rate_limit.limiter`
- Endpoint-specific limits: `/v1/chat/completions` (10/min), `/api/v1/transit/vehicles` (30/min), `/api/v1/knowledge/*` (10-30/min), `/health/*` (60/min)
- X-Forwarded-For aware for nginx proxy compatibility
- Disable in tests: `limiter.enabled = False`

**Query Quota (`app.core.agents.quota`)**

- Daily per-IP quota for LLM chat endpoint (50 queries/day default)
- In-memory tracker with automatic 24h reset per IP
- Returns HTTP 429 when exceeded

### Documentation Style

**Use Google-style docstrings** for all functions, classes, and modules:

```python
def process_request(user_id: str, query: str) -> dict[str, Any]:
    """Process a user request and return results.

    Args:
        user_id: Unique identifier for the user.
        query: The search query string.

    Returns:
        Dictionary containing results and metadata.

    Raises:
        ValueError: If query is empty or invalid.
        ProcessingError: If processing fails after retries.
    """
```

### Tool Docstrings for Agents

**Critical Difference:** Tool docstrings are read by LLMs during tool selection. They must guide the agent to choose the RIGHT tool, use it EFFICIENTLY, and compose tools into workflows.

Standard Google-style docstrings document **what code does** for human developers.
Agent tool docstrings guide **when to use the tool and how** for LLM reasoning.

**Key Principles:**

1. **Guide Tool Selection** - Agent must choose this tool over alternatives
2. **Prevent Token Waste** - Steer toward efficient parameter choices
3. **Enable Composition** - Show how tool fits into multi-step workflows
4. **Set Expectations** - Explain performance characteristics and limitations
5. **Provide Examples** - Concrete usage with realistic data

### Shared Utilities

**Pagination** (`app.shared.schemas`)

- `PaginationParams`: Query params with `.offset` property
- `PaginatedResponse[T]`: Generic response with `.total_pages` property

**Timestamps** (`app.shared.models`)

- `TimestampMixin`: Adds `created_at` and `updated_at` columns
- `utcnow()`: Timezone-aware UTC datetime helper

**Error Handling** (`app.shared.schemas`, `app.core.exceptions`)

- `ErrorResponse`: Standard error response format
- Global exception handlers configured in `app.main`

### Agent Module

VTV's primary feature is a Pydantic AI agent (`Agent[UnifiedDeps, str]`). It follows the feature slice pattern with a `tools/` subdirectory:

```
app/core/agents/
├── agent.py           # Agent creation with UnifiedDeps, 10 tool registrations
├── routes.py          # /v1/chat/completions, /v1/models (rate limited + quota enforced)
├── service.py         # Agent orchestration, deps injection, model building (singleton)
├── schemas.py         # OpenAI-compatible request/response schemas (size-constrained)
├── config.py          # LLM provider settings (model names, tokens, timeouts)
├── quota.py           # Daily per-IP query quota tracker (50/day, auto-reset)
├── exceptions.py      # Agent-specific exceptions (TransitDataError, ObsidianError → HTTP 503)
├── tools/
│   ├── transit/       # Transit tools (see below)
│   │   ├── schemas.py         # Response models (BusStatus, RouteOverview, StopDepartures, RouteSchedule, StopResult, AdherenceReport, DriverAvailabilityReport, etc.)
│   │   ├── deps.py            # UnifiedDeps dataclass + factory (transit + obsidian HTTP clients)
│   │   ├── client.py          # GTFS-RT protobuf client with 20s cache
│   │   ├── static_cache.py    # Static GTFS ZIP parser (routes/stops/trips/calendar/stop_times, 24h TTL)
│   │   ├── query_bus_status.py # Tool 1: 3 actions (status, route_overview, stop_departures)
│   │   ├── get_route_schedule.py # Tool 2: timetable queries by route/date/direction/time window
│   │   ├── search_stops.py    # Tool 3: 2 actions (search by name, nearby by lat/lon)
│   │   ├── get_adherence_report.py # Tool 4: on-time performance metrics (route + network)
│   │   ├── check_driver_availability.py # Tool 5: driver staffing queries by shift/date/route
│   │   ├── driver_data.py     # Mock driver data provider (Phase 2: replaced by CMS API client)
│   │   └── tests/             # 104 unit tests
│   ├── obsidian/      # Obsidian vault tools (see below)
│   │   ├── schemas.py         # Response models (VaultSearchResponse, NoteContent, FolderListResponse, BulkOperationResult, etc.)
│   │   ├── client.py          # Obsidian Local REST API client (httpx, SSL verify=False)
│   │   ├── query_vault.py     # Tool 6: 5 actions (search, find_by_tags, list, recent, glob)
│   │   ├── manage_notes.py    # Tool 7: 5 actions (create, read, update, delete, move) + frontmatter/section helpers
│   │   ├── manage_folders.py  # Tool 8: 4 actions (create, delete, list, move)
│   │   ├── bulk_operations.py # Tool 9: 5 actions (move, tag, delete, update_frontmatter, create) with dry_run
│   │   └── tests/             # 68 unit tests
│   └── knowledge/     # Knowledge base search tool (see below)
│       ├── schemas.py         # Response models (KnowledgeSearchResult, KnowledgeSearchResponse)
│       ├── search_knowledge.py # Tool 10: RAG search over uploaded documents (with citation support)
│       └── tests/             # 7 unit tests
└── tests/             # 22 agent-level tests
```

`config.py` is feature-specific (not in `core/`) because LLM settings are agent-specific. Tools are grouped by domain under `tools/`, each with agent-optimized docstrings (see "Tool Docstrings for Agents" above).

**Transit Tools (5, all read-only — AI advises, humans decide):**
- `query_bus_status` ✅ — Current delay/position for a route or vehicle (3 actions: status, route_overview, stop_departures). Data source: GTFS-RT feeds from Rigas Satiksme.
- `get_route_schedule` ✅ — Timetable for a route and service date, with direction and time window filters. Data source: GTFS static ZIP (stop_times.txt, calendar.txt, calendar_dates.txt).
- `search_stops` ✅ — Search stops by name (substring) or proximity (lat/lon radius). Data source: GTFS static ZIP (stops.txt) with stop-to-routes index.
- `get_adherence_report` ✅ — On-time performance metrics for routes or network. Compares GTFS-RT delays against static schedules. Data source: GTFS-RT trip updates + GTFS static ZIP.
- `check_driver_availability` ✅ — Driver availability by shift/date/route with per-shift summaries. Data source: Mock provider (Phase 2: VTV CMS tRPC API).

**Obsidian Vault Tools (4, read-write with safety guards):**
- `obsidian_query_vault` ✅ — Search and discover (search, find_by_tags, list, recent, glob). Data source: Obsidian Local REST API.
- `obsidian_manage_notes` ✅ — Individual note CRUD (create, read, update, delete, move) with frontmatter parsing and section editing. Data source: Obsidian Local REST API.
- `obsidian_manage_folders` ✅ — Folder operations (create, delete, list, move). Delete requires `confirm=true`. Data source: Obsidian Local REST API.
- `obsidian_bulk_operations` ✅ — Batch operations (move, tag, delete, update_frontmatter, create) with `dry_run` preview. Data source: Obsidian Local REST API.

**Knowledge Base Tool (1, read-only search):**
- `search_knowledge_base` ✅ — RAG-powered search over uploaded documents (PDF, DOCX, Excel, CSV, email, image, text). Hybrid vector + fulltext search with RRF fusion and cross-encoder reranking. Returns `document_id` for citation links. Agent system prompt includes CITATION RULES for formatting `[title](/{locale}/documents/{id})` links. Data source: PostgreSQL + pgvector via `app/knowledge/` feature slice. DMS features: file persistence at `data/documents/{id}/`, metadata editing (PATCH), file download, content preview, domain listing.

**Agent Safety Constraints:**
- Transit tools: read-only, no write operations
- Vault deletes: require `confirm: true` parameter
- Bulk operations: support `dry_run` for preview before execution
- Path sandboxing: prevents directory traversal (`../`)
- No vault file access outside configured vault path
- Monthly spending cap on Claude API (EUR 100 hard limit)
- Token budget per user per day (50 queries) — enforced via `QueryQuotaTracker` in `app/core/agents/quota.py`
- Rate limiting: 10 req/min on chat endpoint, 30/min on transit, 60/min on health (slowapi)
- Request size: 100KB body limit (middleware), 20 messages max, 4000 char content max per message

### Configuration

- Environment variables via Pydantic Settings (`app.core.config`)
- Required: `DATABASE_URL` (postgresql+asyncpg://...)
- Copy `.env.example` to `.env` for local development
- Settings singleton: `get_settings()` from `app.core.config`
- Rate limit settings: `RATE_LIMIT_CHAT`, `RATE_LIMIT_TRANSIT`, `RATE_LIMIT_HEALTH`, `RATE_LIMIT_DEFAULT`
- Query quota: `AGENT_DAILY_QUOTA` (default: 50)
- Obsidian vault: `OBSIDIAN_API_KEY` (Local REST API key), `OBSIDIAN_VAULT_URL` (default: `https://127.0.0.1:27124`)
- Document storage: `DOCUMENT_STORAGE_PATH` (default: `data/documents`) — persistent file storage for uploaded documents
- Knowledge base embedding: `EMBEDDING_PROVIDER` (openai/jina/local), `EMBEDDING_MODEL`, `EMBEDDING_DIMENSION` (1024), `EMBEDDING_API_KEY`, `EMBEDDING_BASE_URL`
- Knowledge base reranker: `RERANKER_PROVIDER` (local/none), `RERANKER_MODEL`, `RERANKER_TOP_K` (10)
- Knowledge base tuning: `KNOWLEDGE_CHUNK_SIZE` (512), `KNOWLEDGE_CHUNK_OVERLAP` (50), `KNOWLEDGE_SEARCH_LIMIT` (50)
- Auth: `AUTH_SECRET` required in Docker (generate with `openssl rand -base64 32`)

## Frontend (CMS)

The VTV frontend is a Turborepo monorepo under `cms/` with pnpm workspaces.

### Tech Stack

- **Framework:** Next.js 16 (App Router) + React 19
- **Styling:** Tailwind CSS v4 + three-tier design tokens (primitive → semantic → component)
- **Components:** shadcn/ui with CVA variants, `cn()` utility for class merging
- **Auth:** Auth.js v5 with 4-role RBAC (admin, dispatcher, editor, viewer)
- **i18n:** next-intl with Latvian (`lv`) and English (`en`) locales
- **Build:** Turborepo with pnpm workspaces
- **SDK:** @hey-api/openapi-ts for TypeScript client generation from FastAPI

### Frontend Environment Setup

```bash
# Install dependencies
cd cms && pnpm install

# Create .env.local from example (required for Auth.js)
cp cms/apps/web/.env.example cms/apps/web/.env.local
# Then generate a real secret:
openssl rand -base64 32  # paste output as AUTH_SECRET value
```

### Frontend Essential Commands

```bash
# Install dependencies
cd cms && pnpm install

# TypeScript type check
pnpm --filter @vtv/web type-check

# Lint
pnpm --filter @vtv/web lint

# Build (catches SSR issues)
pnpm --filter @vtv/web build

# Dev server (port 3000)
pnpm --filter @vtv/web dev

# Generate SDK client (requires FastAPI running on port 8123)
pnpm --filter @vtv/sdk generate-sdk
```

### Frontend Directory Structure

```
cms/apps/web/src/
├── app/[locale]/
│   ├── layout.tsx              # Root locale layout with sidebar nav
│   ├── (dashboard)/
│   │   ├── page.tsx            # Dashboard (default authenticated page)
│   │   ├── chat/page.tsx       # AI assistant chat (streaming SSE, bilingual)
│   │   ├── documents/page.tsx  # Document management (upload, table, filters, detail panel)
│   │   ├── routes/page.tsx     # Route management (CRUD, filters, resizable map panel; mobile: tab layout)
│   │   └── {page}/page.tsx     # Future feature pages (stops, schedules, etc.)
│   ├── login/page.tsx          # Login page (public)
│   └── unauthorized/page.tsx   # Unauthorized redirect page
├── components/
│   ├── ui/                     # shadcn/ui components (button, table, dialog, tabs, etc.)
│   ├── app-sidebar.tsx         # Responsive sidebar (desktop aside + mobile hamburger Sheet)
│   ├── dashboard/              # Dashboard-specific components (metric-card, calendar)
│   ├── documents/              # Document management (table, filters, upload, detail, delete dialog)
│   └── routes/                 # Route management components (table, filters, form, detail, map)
├── hooks/                      # Custom React hooks (use-mobile, use-vehicle-positions)
├── types/                      # TypeScript types (route.ts, dashboard.ts, document.ts)
├── lib/                        # Utilities (cn, agent-client, documents-client, mock data)
└── i18n/                       # next-intl configuration
```

### Page Creation Conventions

Every new page requires:
1. **Page component** at `cms/apps/web/src/app/[locale]/(dashboard)/{page}/page.tsx`
2. **i18n keys** in both `cms/apps/web/messages/lv.json` and `en.json`
3. **Sidebar nav entry** in `cms/apps/web/src/components/app-sidebar.tsx`
4. **Middleware matcher** in `cms/apps/web/middleware.ts` with role permissions
5. **Design tokens** — use semantic tokens from `tokens.css`, never hardcode colors

Use `/fe-create-page {name}` to scaffold, or `/fe-planning {description}` for a full plan.

### Design System Hierarchy

1. **MASTER.md** (`cms/design-system/vtv/MASTER.md`) — Global rules: spacing scale, typography, color system, component patterns
2. **Page overrides** (`cms/design-system/vtv/pages/{page}.md`) — Page-specific design rules that override or extend MASTER.md
3. **Design tokens** (`cms/packages/ui/src/tokens.css`) — CSS custom properties in three tiers:
   - Primitive: `--color-blue-500`, raw values
   - Semantic: `--color-surface-primary`, `--color-text-secondary`, contextual meaning
   - Component: `--button-bg`, component-specific aliases

### Component Patterns

- Use shadcn/ui components from `cms/apps/web/src/components/ui/`
- CVA (Class Variance Authority) for component variants
- `cn()` from `cms/apps/web/src/lib/utils.ts` for conditional class merging
- Server components by default, `'use client'` only when needed (forms, interactivity)
- `useTranslations` from `next-intl` for all user-visible text
- Accessibility: ARIA labels, alt text, keyboard navigation, skip links, focus rings

## Development Guidelines

**When Creating New Features**

Use `/be-create-feature {name}` to scaffold, or follow these steps manually:

1. Create feature directory under `app/` (e.g., `app/products/`)
2. Create files **in this order**: schemas → models → repository → service → exceptions → routes → tests
3. Full structure:
   ```
   app/{feature}/
   ├── __init__.py
   ├── schemas.py         # Pydantic request/response models
   ├── models.py          # SQLAlchemy models (Base + TimestampMixin, Mapped[] annotations)
   ├── repository.py      # Async data access (AsyncSession + select())
   ├── service.py         # Business logic + structured logging
   ├── exceptions.py      # Inherit from app.core.exceptions base classes
   ├── routes.py          # FastAPI endpoints (thin — delegate to service)
   ├── tests/
   │   ├── conftest.py    # Feature-specific fixtures
   │   ├── test_service.py
   │   └── test_routes.py
   └── README.md          # Feature docs (see reference/feature-readme-template.md)
   ```
4. Models inherit from `Base` and `TimestampMixin`, use `Mapped[]` type annotations
5. Repositories take `AsyncSession`, use `select()` — see `reference/vsa-patterns.md`
6. Services create repositories, apply business rules, do structured logging
7. Routes are thin: create service via `Depends(get_service)`, call service methods, no try/except (let global handler catch feature exceptions)
8. Wire router in `app/main.py`: `app.include_router(feature_router)`
9. Create migration: `uv run alembic revision --autogenerate -m "add {feature} table"`

**Layer Responsibilities:**
- **Routes** → HTTP concerns (status codes, dependency injection)
- **Service** → Business logic, validation, logging, orchestration
- **Repository** → Database operations only (no business logic)
- **Exceptions** → Inherit from `core.exceptions` for automatic HTTP status mapping

**Cross-Feature Data Access:**
- **Read** from other features' repositories freely (import and use with same session)
- **Never write** to another feature's tables directly
- All repositories sharing the same `AsyncSession` = single transaction
- Document cross-feature dependencies in both READMEs

**Three-Feature Rule for `shared/`:**
1. First feature: Write code inline
2. Second feature: Duplicate (add `# NOTE: duplicated from {other}`)
3. Third feature: Extract to `app/shared/` and refactor all three

**Type Checking**

- Run both MyPy and Pyright before committing
- No type suppressions (`# type: ignore`, `# pyright: ignore`) unless absolutely necessary
- Document suppressions with inline comments explaining why

**Testing**

- Write tests alongside feature code in `tests/` subdirectory
- Use `@pytest.mark.integration` for tests requiring real database
- Fast unit tests preferred (<1s total execution time)
- Test fixtures in `app/tests/conftest.py`

**Logging Best Practices**

- Start action: `logger.info("feature.action_started", **context)`
- Success: `logger.info("feature.action_completed", **context)`
- Failure: `logger.error("feature.action_failed", exc_info=True, error=str(e), error_type=type(e).__name__, **context)`
- Include context: IDs, durations, error details
- Avoid generic events like "processing" or "handling"
- Use standard states: `_started`, `_completed`, `_failed`, `_validated`, `_rejected`

**Database Patterns**

- Always use async/await with SQLAlchemy
- Use `select()` instead of `.query()` (SQLAlchemy 2.0 style)
- Leverage `expire_on_commit=False` in session config
- Test database operations with `@pytest.mark.integration`

**API Patterns**

- Health checks: `/health`, `/health/db`, `/health/ready`
- Pagination: Use `PaginationParams` and `PaginatedResponse[T]`
- Error responses: Use `ErrorResponse` schema
- Route prefixes: Use router `prefix` parameter for feature namespacing

## Key Reference Documents

- `reference/vsa-patterns.md` — Async repository, service, routes, cross-feature orchestration, and model patterns adapted for VTV's stack
- `reference/feature-readme-template.md` — Template for documenting feature slices
- `reference/PRD.md` — Product requirements and vision
- `reference/mvp-tool-designs.md` — Agent tool specifications and composition chains
- `.claude/commands/CLAUDE.md` — Full documentation for all 23 slash commands with usage, behavior, and workflows
- `docs/TODO.md` — Planned features with effort estimates and links to planning docs
- `docs/PLANNING/Implementation-Plan.md` — Full Latvia transit platform roadmap (4 phases, live tracking, journey planning, ML)
- `docs/PLANNING/rag-improvements.md` — RAG knowledge base enhancement plan (10 improvements)
- `docs/PLANNING/sop-file-automation.md` — Automated document ingestion and SOP generation plan
- `docs/PLANNING/latvian-language-and-model-research.md` — Model benchmarks, embedding selection, DMS architecture decisions


<claude-mem-context>
# Recent Activity

<!-- This section is auto-generated by claude-mem. Edit content outside the tags. -->

### Feb 11, 2026

| ID | Time | T | Title | Read |
|----|------|---|-------|------|
| #13719 | 3:26 PM | 🔵 | VTV Project Initial State Assessment | ~280 |
</claude-mem-context>