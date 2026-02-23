# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

VTV is a unified transit operations platform targeting all of Latvia's public transit, starting with Riga's municipal bus system. This repository contains the **AI Agent Service** — a FastAPI + Pydantic AI application providing a unified agent with 10 tools (5 transit + 4 Obsidian vault + 1 knowledge base). Built with **vertical slice architecture**, optimized for AI-assisted development. Python 3.12+, strict type checking with MyPy and Pyright. Features multi-feed GTFS-RT tracking with Redis caching for sub-ms reads. The platform roadmap extends to PostGIS spatial queries, WebSocket streaming, and ML-based predictions — see `docs/PLANNING/Implementation-Plan.md`.

## Core Principles

**KISS** (Keep It Simple, Stupid) — Prefer simple, readable solutions over clever abstractions.

**YAGNI** (You Aren't Gonna Need It) — Don't build features until they're actually needed.

**Vertical Slice Architecture** — Each feature owns its models, schemas, routes, and business logic under `app/{feature}/`. Shared utilities go in `app/shared/` only when used by 3+ features. Core infrastructure in `app/core/`.

**Type Safety (CRITICAL)** — Strict MyPy + Pyright enforced. All functions must have complete type annotations. No `Any` without justification. Test files have relaxed rules (see `pyproject.toml`).

**Python Anti-Patterns** — 45 documented patterns that cause lint/type errors (includes security patterns). See `docs/python-anti-patterns.md`. Also embedded in `/be-execute` and `/be-planning` Known Pitfalls sections.

**Structured Logging** — `domain.component.action_state` pattern via structlog. Logger: `from app.core.logging import get_logger`. Full taxonomy: `docs/logging-standard.md`.

## Slash Commands

24 AI-assisted development commands (16 backend + 7 frontend + 1 testing). Full docs: `.claude/commands/CLAUDE.md`.

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

### Testing Commands

| Command | Description |
|---------|-------------|
| `/e2e` | Run Playwright e2e tests — auto-detects changed features or runs specific test |

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
make test            # Unit tests (612 tests, ~15s)
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
│   ├── auth/           # JWT auth + RBAC (4 endpoints: login, refresh, seed; bcrypt, brute-force lockout)
│   ├── knowledge/      # RAG knowledge base + DMS (9 endpoints, pgvector, multi-format processing)
│   ├── drivers/        # Driver management (5 endpoints, HR profiles, shift/availability, agent integration)
│   ├── events/         # Operational events (5 endpoints, dashboard calendar, date range filter)
│   ├── stops/          # Stop management (6 endpoints, Haversine proximity, location_type filter)
│   ├── schedules/      # GTFS schedule management (23 endpoints, trip CRUD, ZIP import/export)
│   ├── transit/        # Multi-feed GTFS-RT tracking (3 endpoints, Redis cache, background poller)
│   ├── main.py         # FastAPI application entry point
│   └── tests/          # Integration tests
├── cms/               # Frontend monorepo — see cms/CLAUDE.md
├── reference/          # Architecture docs (vsa-patterns.md, PRD.md, feature-readme-template.md)
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
- Migration workflow: define models → `alembic revision --autogenerate` → review → `alembic upgrade head`

### Middleware & Rate Limiting

- `BodySizeLimitMiddleware` (100KB), `RequestLoggingMiddleware` (correlation IDs), `CORSMiddleware`
- Rate limiting via slowapi: auth (10/min login, 30/min refresh, 5/min seed), chat (10/min), transit (30/min), knowledge (10-30/min), schedules (5-30/min), drivers (10-30/min), events (10-30/min), health (60/min)
- Query quota: 50/day per IP for LLM chat endpoint (`app.core.agents.quota`)

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
- **Pages:** Dashboard, Routes, Stops, Schedules, Drivers, Documents, Chat, Login
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

**CI Pipeline:** GitHub Actions (`.github/workflows/ci.yml`) runs on push/PR to `main`. Three jobs: `backend-checks` (ruff + mypy + pyright + pytest with PostgreSQL + Redis services), `frontend-checks` (TypeScript + ESLint + build), `e2e-tests` (docker-compose full stack + Playwright, depends on first two jobs). Playwright report uploaded as artifact (14-day retention).

## Security Practices

- **ILIKE wildcard escaping** — All search queries use `escape_like()` from `app.shared.utils` (rules 40-45 in `docs/python-anti-patterns.md`)
- **Streaming file uploads** — Application-level size enforcement via chunked reads, not just middleware `Content-Length`
- **Filename sanitization** — Regex sanitization + `is_relative_to()` path traversal prevention
- **Credential redaction** — URLs with embedded passwords are redacted before logging
- **Rate limiting** — Uses `X-Real-IP` (nginx-set, not spoofable) instead of `X-Forwarded-For`
- **Transit input validation** — Query params constrained with `max_length` and `pattern`
- **GTFS time validation** — Field validators enforce minutes < 60 and seconds < 60 (hours can exceed 24 per GTFS spec)
- **Content-Length validation** — `BodySizeLimitMiddleware` handles malformed headers defensively (`try/except ValueError`)
- **Cookie security** — Locale cookie set with `SameSite=Lax` attribute
- **Locale-aware redirects** — Auth middleware preserves user's current locale on redirect
- **Docker credentials** — Environment variable interpolation (`${VAR:-default}`) in docker-compose
- **Demo credentials** — Environment-controlled: only seeded when `ENVIRONMENT=development`, password configurable via `DEMO_USER_PASSWORD`
- **Database unique constraints** — `(trip_id, stop_sequence)` and `(calendar_id, date)` prevent GTFS data corruption
- **Knowledge base input validation** — Empty update rejection (`model_validator`), unknown file type rejection instead of silent text fallback
- **JWT Authentication** — All backend endpoints protected via `Depends(get_current_user)` with HS256 JWT tokens (30min access + 7-day refresh). Startup fails hard if `JWT_SECRET_KEY` is default in non-dev environments.
- **RBAC** — `require_role()` dependency enforces function-level authorization: admin (full), editor (data CRUD), dispatcher (driver management), viewer (read-only)
- **authFetch dual-context** — `cms/apps/web/src/lib/auth-fetch.ts` uses dynamic imports: `auth()` on server (cheap, no network), `getSession()` on client (fetches from `/api/auth/session`). Never static-import server-only `auth()` in files used by `'use client'` components.
- **Out of scope (future):** Redis-backed brute-force tracking, full HTTPS/TLS deployment, token revocation

## Key Reference Documents

- `reference/vsa-patterns.md` — Async repository, service, routes, cross-feature patterns
- `reference/feature-readme-template.md` — Template for feature READMEs
- `reference/PRD.md` — Product requirements and vision
- `reference/mvp-tool-designs.md` — Agent tool specifications
- `.claude/commands/CLAUDE.md` — Full slash command documentation
- `docs/python-anti-patterns.md` — 45 documented Python anti-patterns (includes security patterns)
- `docs/security_audit.txt` — First security audit findings and remediation (13 findings, commit 85bf32d)
- `docs/security_audit_2.txt` — Second security audit: code quality, data integrity, testing gaps
- `.github/workflows/ci.yml` — CI pipeline (backend checks, frontend checks, E2E tests)
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
