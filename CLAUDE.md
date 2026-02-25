# CLAUDE.md

## Project Overview

VTV is a unified transit operations platform targeting all of Latvia's public transit, starting with Riga's municipal bus system. This repository contains the **AI Agent Service** — a FastAPI + Pydantic AI application providing a unified agent with 11 tools (5 transit + 4 Obsidian vault + 1 knowledge base + 1 skills management). Built with **vertical slice architecture**, optimized for AI-assisted development. Python 3.12+, strict type checking with MyPy and Pyright. Features multi-feed GTFS-RT tracking with Redis caching for sub-ms reads. The platform roadmap extends to PostGIS spatial queries, WebSocket streaming, and ML-based predictions — see `docs/PLANNING/Implementation-Plan.md`.

## Core Principles

**Vertical Slice Architecture** — Each feature owns its models, schemas, routes, and business logic under `app/{feature}/`. Shared utilities go in `app/shared/` only when used by 3+ features. Core infrastructure in `app/core/`.

**Type Safety (CRITICAL)** — Strict MyPy + Pyright enforced. All functions must have complete type annotations. No `Any` without justification. Test files have relaxed rules (see `pyproject.toml`).

**Python Anti-Patterns** — 47 documented patterns that cause lint/type errors (includes security and schema validation patterns). See `docs/python-anti-patterns.md`. Also embedded in `/be-execute` and `/be-planning` Known Pitfalls sections.

**Structured Logging** — `domain.component.action_state` pattern via structlog. Logger: `from app.core.logging import get_logger`. Full taxonomy: `docs/logging-standard.md`.

## Slash Commands

24 AI-assisted development commands (16 backend + 7 frontend + 1 testing). Full docs: `.claude/commands/CLAUDE.md`.

**Workflows:** `/be-prime` → `/be-planning` → `/be-execute` → `/be-validate` → `/commit` | Frontend: `/fe-prime` → `/fe-planning` → `/fe-execute` → `/fe-validate` → `/e2e` → `/commit`

## Essential Commands

All workflows available via `make help`. Key commands:

```bash
# Local development
make db              # Start PostgreSQL + Redis (Docker, needed by backend)
make dev             # Start backend (:8123) + frontend (:3000) in parallel
make dev-be          # Backend only
make dev-fe          # Frontend only

# Quality checks
make check           # All checks (lint + types + tests)
make test            # Unit tests (690 tests, ~18s)
make lint            # Format + lint (ruff)
make types           # mypy + pyright

# E2E testing (Playwright)
make e2e             # Auto-detect changed features, run only those tests
make e2e-all         # Run all 81 e2e tests (CRUD tests conditionally skip when prerequisites missing)
make e2e-ui          # Interactive Playwright UI mode
make e2e-headed      # Run with visible browser

# Docker (integration / pre-deployment)
make docker          # Full stack (db, redis, auto-migrate, app, cms, nginx on :80)
make docker-logs     # Tail all service logs
make docker-down     # Stop all services

# Security
make install-hooks        # Install git pre-commit hook (security lint + secrets detection)
make security-check       # Run Ruff Bandit security rules standalone
make security-audit-quick # Security audit (<10s) - Bandit, sensitive files, creds
make security-audit       # Security audit (~60s) - quick + deps, types, convention tests
make security-audit-full  # Security audit (~120s) - standard + full tests, Docker, nginx

# Database
make db-migrate                    # Run migrations
make db-revision m="description"   # Create new migration
```

## Architecture

### Project Structure

```
VTV/
├── app/
│   ├── core/           # Infrastructure (config, database, logging, middleware, health, rate_limit, redis)
│   │   └── agents/     # AI agent module — 11 tools, see app/core/agents/CLAUDE.md
│   ├── shared/         # Cross-feature utilities (pagination, timestamps, error schemas)
│   ├── auth/           # JWT auth + RBAC + user management (10 endpoints: login, logout, refresh, seed, reset-password, user CRUD; bcrypt, Redis brute-force, token revocation)
│   ├── knowledge/      # RAG knowledge base + DMS (9 endpoints, pgvector, multi-format processing)
│   ├── drivers/        # Driver management (5 endpoints, HR profiles, shift/availability, agent integration)
│   ├── events/         # Operational events (5 endpoints, dashboard calendar, date range filter)
│   ├── stops/          # Stop management (6 endpoints, Haversine proximity, location_type filter)
│   ├── schedules/      # GTFS schedule management (23 endpoints, trip CRUD, ZIP import/export, creator tracking)
│   ├── skills/         # Agent skills system (7 endpoints, reusable knowledge packages, agent context injection)
│   ├── transit/        # Multi-feed GTFS-RT tracking (3 endpoints, Redis cache, background poller)
│   ├── main.py         # FastAPI application entry point
│   └── tests/          # Integration tests
├── cms/               # Frontend monorepo — see cms/CLAUDE.md
├── reference/          # Architecture docs (vsa-patterns.md, PRD.md, feature-readme-template.md)
├── scripts/           # Security tools (pre-commit hook, audit runner, Docker/nginx validators)
├── nginx/             # Reverse proxy (rate limiting, security headers)
├── .claude/commands/   # 24 slash commands
├── .agents/            # Plans, code reviews, execution reports, system reviews
├── docs/              # Planning docs, RCA documents, anti-patterns reference
├── alembic/            # Database migrations
└── pyproject.toml      # Dependencies, tooling config (ruff, mypy, pyright, pytest)
```

### Database

- **Async SQLAlchemy** with connection pooling (pool_size=5, max_overflow=10)
- Base class: `app.core.database.Base` (extends `DeclarativeBase`)
- Session dependency: `get_db()` from `app.core.database`; standalone context: `get_db_context()` for agent tools
- All models inherit `TimestampMixin` from `app.shared.models`

### Middleware & Rate Limiting

- `BodySizeLimitMiddleware` (100KB), `RequestLoggingMiddleware` (correlation IDs), `CORSMiddleware`
- Rate limiting via slowapi: auth (10/min login, 30/min refresh, 5/min seed), chat (10/min), transit (30/min), knowledge (10-30/min), schedules (5-30/min), drivers (10-30/min), events (10-30/min), skills (5-30/min), health (60/min)
- Query quota: 50/day per IP for LLM chat endpoint (`app.core.agents.quota`) — Redis-backed with in-memory fallback

### Shared Utilities

- **Pagination**: `PaginationParams` + `PaginatedResponse[T]` from `app.shared.schemas`
- **Timestamps**: `TimestampMixin` + `utcnow()` from `app.shared.models`
- **Errors**: `AppError` hierarchy (`NotFoundError` → 404, `DomainValidationError` → 422, feature errors → 500) with global exception handlers in `app.core.exceptions`. `ErrorResponse` schema in `app.shared.schemas`
- **SQL Escaping**: `escape_like()` from `app.shared.utils` — escapes `%`, `_`, `\` in ILIKE search params

### Configuration

Environment variables via Pydantic Settings (`app.core.config`). Copy `.env.example` to `.env` for local development. Key settings: `DATABASE_URL` (required), `REDIS_URL`, `JWT_SECRET_KEY` (required in production), `TRANSIT_FEEDS_JSON`, `EMBEDDING_PROVIDER`/`EMBEDDING_MODEL`, `OBSIDIAN_API_KEY`, `DEMO_USER_PASSWORD`. Full list in `.env.example` and `app/core/config.py`.

## Frontend (CMS)

Turborepo monorepo under `cms/` with pnpm workspaces. **Full documentation in `cms/CLAUDE.md` and `cms/apps/web/CLAUDE.md`.**

- **Stack:** Next.js 16 + React 19, Tailwind CSS v4 + three-tier design tokens, shadcn/ui + CVA, Auth.js v5 with 4-role RBAC (DB-backed via `POST /api/v1/auth/login`), next-intl (lv/en)
- **SDK:** `@vtv/sdk` — auto-generated TypeScript client from FastAPI OpenAPI schema (47 endpoints, 68 types). Auth via request interceptor (JWT, dual server/client context). Events domain migrated; 8 more clients to migrate.
- **Pages:** Dashboard, Routes, Stops, Schedules, Drivers, GTFS, Documents, Users, Chat, Login
- **New page checklist:** page component → i18n keys (lv + en) → sidebar nav → middleware RBAC → semantic tokens only
- **Design system:** `cms/design-system/vtv/MASTER.md` (global) → `pages/{page}.md` (overrides) → `packages/ui/src/tokens.css` (tokens)

## Development Guidelines

Use `/be-create-feature {name}` to scaffold new features. Manual process and patterns documented in `reference/vsa-patterns.md`.

**Feature file order:** schemas → models → repository → service → exceptions → routes → tests

**Layer responsibilities:**
- **Routes** → HTTP concerns (status codes, dependency injection) — thin, delegate to service
- **Service** → Business logic, validation, logging, orchestration
- **Repository** → Database operations only (no business logic)
- **Exceptions** → Inherit from `AppError` in `core.exceptions` for automatic HTTP status mapping (`DomainValidationError` not `ValidationError` — avoids Pydantic naming clash)

**Cross-feature access:** Read from other repositories freely (same `AsyncSession` = single transaction). Never write to another feature's tables directly.

**Three-feature rule:** Inline first, duplicate second (with `# NOTE`), extract to `app/shared/` on third use.

**Testing:** Tests in `tests/` subdirectory. `@pytest.mark.integration` for DB tests. Fast unit tests preferred.

**Docker services:** `db` (PostgreSQL + pgvector), `redis` (vehicle position cache), `migrate` (Alembic auto-migration, runs once), `app` (FastAPI), `cms` (Next.js), `nginx` (reverse proxy on port 80). Services start in dependency order with healthchecks. All behind nginx.

**CI Pipeline:** GitHub Actions (`.github/workflows/ci.yml`) runs on push/PR to `main`. Three jobs: `backend-checks` (ruff + dedicated security audit via `ruff --select=S` + mypy + pyright + pytest with PostgreSQL + Redis services), `frontend-checks` (TypeScript + ESLint + build), `e2e-tests` (docker-compose full stack + Playwright, depends on first two jobs). Playwright report uploaded as artifact (14-day retention).

**Pre-commit hook:** `scripts/pre-commit` — fast (<5s) shell script that blocks commits with Bandit security violations, staged sensitive files (`.env`, `*.pem`, `*.key`), hardcoded postgres credentials, and leaked secrets (AWS keys, private keys, JWT tokens). Install via `make install-hooks`.

## Security

Security is enforced automatically through 6 layers -- see `docs/sdlc-security-framework.md` for full documentation.

- **105 convention tests** (`app/tests/test_security.py`) auto-discover all endpoints and enforce auth, JWT safety, container hardening, CORS, GDPR, and 15+ other security properties
- **Pre-commit hook** blocks security violations, sensitive files, and hardcoded credentials (`make install-hooks`)
- **CI security gate** runs Bandit + pip-audit as dedicated PR status checks
- **Secure scaffold** (`/be-create-feature`) generates auth-protected endpoints by default
- Key patterns: `authFetch` dual-context (`cms/apps/web/src/lib/auth-fetch.ts`), session hydration gate (see `cms/apps/web/CLAUDE.md`)

## Key Reference Documents

- `reference/vsa-patterns.md` — Async repository, service, routes, cross-feature patterns
- `reference/PRD.md` — Product requirements and vision
- `docs/python-anti-patterns.md` — 47 documented Python anti-patterns
- `docs/sdlc-security-framework.md` — SDLC security audit framework (6 layers, automated gates)
- `.claude/commands/CLAUDE.md` — Full slash command documentation
- `docs/PLANNING/Implementation-Plan.md` — Latvia transit platform roadmap


<claude-mem-context>
# Recent Activity

<!-- This section is auto-generated by claude-mem. Edit content outside the tags. -->

### Feb 11, 2026

| ID | Time | T | Title | Read |
|----|------|---|-------|------|
| #13719 | 3:26 PM | 🔵 | VTV Project Initial State Assessment | ~280 |
</claude-mem-context>
