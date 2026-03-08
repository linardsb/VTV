# CLAUDE.md

## Project Overview

VTV is a unified transit operations platform targeting all of Latvia's public transit, starting with Riga's municipal bus system. This repository contains the **AI Agent Service** — a FastAPI + Pydantic AI application providing a unified agent with 11 tools (5 transit + 4 Obsidian vault + 1 knowledge base + 1 skills management). Built with **vertical slice architecture**, optimized for AI-assisted development. Python 3.12+, strict type checking with MyPy and Pyright. Features multi-feed GTFS-RT tracking with Redis caching for sub-ms reads, WebSocket live streaming for real-time vehicle position push, and PostGIS spatial queries for sub-ms proximity search. The platform roadmap extends to ML-based predictions — see `docs/PLANNING/Implementation-Plan.md`.

## Core Principles

**Vertical Slice Architecture** — Each feature owns its models, schemas, routes, and business logic under `app/{feature}/`. Shared utilities go in `app/shared/` only when used by 3+ features. Core infrastructure in `app/core/`.

**Type Safety (CRITICAL)** — Strict MyPy + Pyright enforced. All functions must have complete type annotations. No `Any` without justification. Test files have relaxed rules (see `pyproject.toml`).

**Python Anti-Patterns** — 59 documented patterns that cause lint/type errors (includes security and schema validation patterns). Single source of truth: `.claude/commands/_shared/python-anti-patterns.md`. Also referenced by `/be-execute` and `/be-planning`.

**Structured Logging** — `domain.component.action_state` pattern via structlog. Logger: `from app.core.logging import get_logger`. Full taxonomy: `docs/logging-standard.md`.

## Slash Commands

25 AI-assisted development commands (8 backend + 7 frontend + 9 cross-cutting + 1 testing). Full docs: `.claude/commands/CLAUDE.md`. Workflows: `.claude/commands/WORKFLOW.md`.

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
make test            # Unit tests (879 tests, ~15s)
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
├── app/                # Backend features (VSA: models, schemas, routes, service, tests per feature)
│   ├── core/           # Infrastructure (config, database, logging, middleware, health, rate_limit, redis)
│   │   └── agents/     # AI agent module — 11 tools, see app/core/agents/CLAUDE.md
│   ├── shared/         # Cross-feature utilities (pagination, timestamps, error schemas)
│   ├── alerts/         # Notification/alerts system (11 endpoints, background evaluator, RBAC)
│   ├── analytics/      # Dashboard analytics (4 endpoints, read-only aggregation over vehicles/drivers/transit)
│   ├── auth/           # JWT auth + RBAC + user management (10 endpoints)
│   ├── compliance/     # NeTEx/SIRI EU compliance exports (4 endpoints, XML generation, no DB tables)
│   ├── knowledge/      # RAG knowledge base + DMS (14 endpoints, pgvector, tags, OCR)
│   ├── drivers/        # Driver management (5 endpoints, HR profiles)
│   ├── events/         # Operational events (5 endpoints, JSONB goals)
│   ├── stops/          # Stop management (6 endpoints, PostGIS spatial queries)
│   ├── schedules/      # GTFS schedule management (23 endpoints, ZIP import/export)
│   ├── skills/         # Agent skills system (7 endpoints)
│   ├── transit/        # Multi-feed GTFS-RT tracking (5 REST + 1 WebSocket endpoint, Redis cache + Pub/Sub, TimescaleDB historical storage)
│   ├── vehicles/       # Vehicle management (8 endpoints, fleet CRUD, maintenance, driver assignment)
│   └── tests/          # Integration tests
├── cms/               # Frontend monorepo — see cms/CLAUDE.md
├── .claude/rules/     # Path-scoped rules (backend, frontend, security, testing)
├── .claude/commands/   # 25 slash commands + _shared/ deduplication
├── alembic/            # Database migrations
└── pyproject.toml      # Dependencies, tooling config (ruff, mypy, pyright, pytest)
```

### Database

- **Async SQLAlchemy** with configurable connection pooling (pool_size=3, max_overflow=5)
- Base class: `app.core.database.Base` (extends `DeclarativeBase`)
- Session: `get_db()` from `app.core.database`; standalone: `get_db_context()` for agent tools
- All models inherit `TimestampMixin` from `app.shared.models`

### Shared Utilities

- **Pagination**: `PaginationParams` + `PaginatedResponse[T]` from `app.shared.schemas`
- **Timestamps**: `TimestampMixin` + `utcnow()` from `app.shared.models`
- **Errors**: `AppError` hierarchy (`NotFoundError` → 404, `DomainValidationError` → 422) in `app.core.exceptions`
- **SQL Escaping**: `escape_like()` from `app.shared.utils`
- **Geospatial**: `haversine_distance()` from `app.shared.geo` — used by agent transit tools for in-memory GTFS cache proximity filtering

## Frontend (CMS)

Turborepo monorepo under `cms/` with pnpm workspaces. **Full documentation in `cms/CLAUDE.md` and `cms/apps/web/CLAUDE.md`.**

- **Stack:** Next.js 16 + React 19, Tailwind CSS v4 + semantic tokens, shadcn/ui + CVA, Auth.js v5 (4-role RBAC), next-intl (lv/en)
- **SDK:** `@vtv/sdk` — auto-generated TypeScript client (66 endpoints, 95+ types). All 13 API domains migrated from hand-written fetch to SDK wrappers.
- **Pages:** Dashboard, Routes, Stops, Schedules, Drivers, Vehicles, GTFS, Documents, Users, Chat, Login
- **New page checklist:** page component → i18n keys (lv + en) → sidebar nav → middleware RBAC → semantic tokens only

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

## Security

Security enforced through 6 automated layers. Details in `.claude/rules/security.md` and `docs/sdlc-security-framework.md`.

**Context-triggered security** — 6 security contexts (AUTH, RBAC, FILE, AGENT, INFRA, INPUT) in `.claude/commands/_shared/security-contexts.md` activate based on feature scope during planning and review. Derived from audit_6 findings. Referenced by `/be-planning`, `/fe-planning`, `/review`, `/fe-review`.

## Compact instructions

When compacting, preserve:
- Current task context and active plan file path
- List of all files modified in this session
- Test commands run and their results
- Key decisions made during this session
- Active feature branch name


<claude-mem-context>
# Recent Activity

<!-- This section is auto-generated by claude-mem. Edit content outside the tags. -->

### Feb 11, 2026

| ID | Time | T | Title | Read |
|----|------|---|-------|------|
| #13719 | 3:26 PM | 🔵 | VTV Project Initial State Assessment | ~280 |
</claude-mem-context>
