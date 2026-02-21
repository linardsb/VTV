# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

VTV is a unified transit operations platform targeting all of Latvia's public transit, starting with Riga's municipal bus system. This repository contains the **AI Agent Service** — a FastAPI + Pydantic AI application providing a unified agent with 10 tools (5 transit + 4 Obsidian vault + 1 knowledge base). Built with **vertical slice architecture**, optimized for AI-assisted development. Python 3.12+, strict type checking with MyPy and Pyright. Features multi-feed GTFS-RT tracking with Redis caching for sub-ms reads. The platform roadmap extends to PostGIS spatial queries, WebSocket streaming, and ML-based predictions — see `docs/PLANNING/Implementation-Plan.md`.

## Core Principles

**KISS** (Keep It Simple, Stupid) — Prefer simple, readable solutions over clever abstractions.

**YAGNI** (You Aren't Gonna Need It) — Don't build features until they're actually needed.

**Vertical Slice Architecture** — Each feature owns its models, schemas, routes, and business logic under `app/{feature}/`. Shared utilities go in `app/shared/` only when used by 3+ features. Core infrastructure in `app/core/`.

**Type Safety (CRITICAL)** — Strict MyPy + Pyright enforced. All functions must have complete type annotations. No `Any` without justification. Test files have relaxed rules (see `pyproject.toml`).

**Python Anti-Patterns** — 40 documented patterns that cause lint/type errors. See `docs/python-anti-patterns.md`. Also embedded in `/be-execute` and `/be-planning` Known Pitfalls sections.

**Structured Logging** — `domain.component.action_state` pattern via structlog. Logger: `from app.core.logging import get_logger`. Full taxonomy: `docs/logging-standard.md`.

## Slash Commands

23 AI-assisted development commands (16 backend + 7 frontend). Full docs: `.claude/commands/CLAUDE.md`.

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

**Workflows:** `/be-prime` → `/be-planning` → `/be-execute` → `/be-validate` → `/commit` | Frontend: `/fe-prime` → `/fe-planning` → `/fe-execute` → `/fe-validate` → `/commit`

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
make test            # Unit tests (450 tests, ~14s)
make lint            # Format + lint (ruff)
make types           # mypy + pyright

# Docker (integration / pre-deployment)
make docker          # Full stack (db, redis, auto-migrate, app, cms, nginx on :80)
make docker-logs     # Tail all service logs
make docker-down     # Stop all services

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
│   │   └── agents/     # AI agent module — 10 tools, see app/core/agents/CLAUDE.md
│   ├── shared/         # Cross-feature utilities (pagination, timestamps, error schemas)
│   ├── auth/           # DB-backed authentication (2 endpoints, bcrypt, brute-force lockout)
│   ├── knowledge/      # RAG knowledge base + DMS (9 endpoints, pgvector, multi-format processing)
│   ├── stops/          # Stop management (6 endpoints, Haversine proximity, location_type filter)
│   ├── schedules/      # GTFS schedule management (23 endpoints, trip CRUD, ZIP import/export)
│   ├── transit/        # Multi-feed GTFS-RT tracking (3 endpoints, Redis cache, background poller)
│   ├── main.py         # FastAPI application entry point
│   └── tests/          # Integration tests
├── cms/               # Frontend monorepo — see cms/CLAUDE.md
├── reference/          # Architecture docs (vsa-patterns.md, PRD.md, feature-readme-template.md)
├── nginx/             # Reverse proxy (rate limiting, security headers)
├── .claude/commands/   # 23 slash commands
├── .agents/            # Plans, code reviews, execution reports, system reviews
├── docs/              # Planning docs, RCA documents, anti-patterns reference
├── alembic/            # Database migrations
└── pyproject.toml      # Dependencies, tooling config (ruff, mypy, pyright, pytest)
```

### Database

- **Async SQLAlchemy** with connection pooling (pool_size=5, max_overflow=10)
- Base class: `app.core.database.Base` (extends `DeclarativeBase`)
- Session dependency: `get_db()` from `app.core.database`
- All models inherit `TimestampMixin` from `app.shared.models`
- Migration workflow: define models → `alembic revision --autogenerate` → review → `alembic upgrade head`

### Middleware & Rate Limiting

- `BodySizeLimitMiddleware` (100KB), `RequestLoggingMiddleware` (correlation IDs), `CORSMiddleware`
- Rate limiting via slowapi: auth (10/min login, 5/min seed), chat (10/min), transit (30/min), knowledge (10-30/min), schedules (5-30/min), health (60/min)
- Query quota: 50/day per IP for LLM chat endpoint (`app.core.agents.quota`)

### Shared Utilities

- **Pagination**: `PaginationParams` + `PaginatedResponse[T]` from `app.shared.schemas`
- **Timestamps**: `TimestampMixin` + `utcnow()` from `app.shared.models`
- **Errors**: `AppError` hierarchy (`NotFoundError` → 404, `ValidationError` → 422, feature errors → 500) with global exception handlers in `app.core.exceptions`. `ErrorResponse` schema in `app.shared.schemas`

### Configuration

Environment variables via Pydantic Settings (`app.core.config`). Copy `.env.example` to `.env` for local development. Key settings: `DATABASE_URL` (required), `REDIS_URL`, `TRANSIT_FEEDS_JSON`, `EMBEDDING_PROVIDER`/`EMBEDDING_MODEL`, `OBSIDIAN_API_KEY`. Full list in `.env.example` and `app/core/config.py`.

## Frontend (CMS)

Turborepo monorepo under `cms/` with pnpm workspaces. **Full documentation in `cms/CLAUDE.md` and `cms/apps/web/CLAUDE.md`.**

- **Stack:** Next.js 16 + React 19, Tailwind CSS v4 + three-tier design tokens, shadcn/ui + CVA, Auth.js v5 with 4-role RBAC (DB-backed via `POST /api/v1/auth/login`), next-intl (lv/en)
- **Pages:** Dashboard, Routes, Stops, Schedules, Documents, Chat, Login
- **New page checklist:** page component → i18n keys (lv + en) → sidebar nav → middleware RBAC → semantic tokens only
- **Design system:** `cms/design-system/vtv/MASTER.md` (global) → `pages/{page}.md` (overrides) → `packages/ui/src/tokens.css` (tokens)

## Development Guidelines

Use `/be-create-feature {name}` to scaffold new features. Manual process and patterns documented in `reference/vsa-patterns.md`.

**Feature file order:** schemas → models → repository → service → exceptions → routes → tests

**Layer responsibilities:**
- **Routes** → HTTP concerns (status codes, dependency injection) — thin, delegate to service
- **Service** → Business logic, validation, logging, orchestration
- **Repository** → Database operations only (no business logic)
- **Exceptions** → Inherit from `AppError` in `core.exceptions` for automatic HTTP status mapping

**Cross-feature access:** Read from other repositories freely (same `AsyncSession` = single transaction). Never write to another feature's tables directly.

**Three-feature rule:** Inline first, duplicate second (with `# NOTE`), extract to `app/shared/` on third use.

**Testing:** Tests in `tests/` subdirectory. `@pytest.mark.integration` for DB tests. Fast unit tests preferred.

**Docker services:** `db` (PostgreSQL + pgvector), `redis` (vehicle position cache), `migrate` (Alembic auto-migration, runs once), `app` (FastAPI), `cms` (Next.js), `nginx` (reverse proxy on port 80). Services start in dependency order with healthchecks. All behind nginx.

## Key Reference Documents

- `reference/vsa-patterns.md` — Async repository, service, routes, cross-feature patterns
- `reference/feature-readme-template.md` — Template for feature READMEs
- `reference/PRD.md` — Product requirements and vision
- `reference/mvp-tool-designs.md` — Agent tool specifications
- `.claude/commands/CLAUDE.md` — Full slash command documentation
- `docs/python-anti-patterns.md` — 40 documented Python anti-patterns
- `docs/PLANNING/Implementation-Plan.md` — Latvia transit platform roadmap (4 phases)
- `docs/TODO.md` — Planned features with effort estimates
- `.agents/code-reviews/AUDIT-SUMMARY.md` — Full codebase health audit (120 findings, 2026-02-21)


<claude-mem-context>
# Recent Activity

<!-- This section is auto-generated by claude-mem. Edit content outside the tags. -->

### Feb 11, 2026

| ID | Time | T | Title | Read |
|----|------|---|-------|------|
| #13719 | 3:26 PM | 🔵 | VTV Project Initial State Assessment | ~280 |
</claude-mem-context>
