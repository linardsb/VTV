# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

VTV is a unified transit operations platform targeting all of Latvia's public transit, starting with Riga's municipal bus system. This repository contains the **AI Agent Service** — a FastAPI + Pydantic AI application providing a unified agent with 10 tools (5 transit + 4 Obsidian vault + 1 knowledge base). Built with **vertical slice architecture**, optimized for AI-assisted development. Python 3.12+, strict type checking with MyPy and Pyright. Features multi-feed GTFS-RT tracking with Redis caching for sub-ms reads. The platform roadmap extends to PostGIS spatial queries, WebSocket streaming, and ML-based predictions — see `docs/PLANNING/Implementation-Plan.md`.

## Core Principles

**KISS** (Keep It Simple, Stupid) — Prefer simple, readable solutions over clever abstractions.

**YAGNI** (You Aren't Gonna Need It) — Don't build features until they're actually needed.

**Vertical Slice Architecture** — Each feature owns its models, schemas, routes, and business logic under `app/{feature}/`. Shared utilities go in `app/shared/` only when used by 3+ features. Core infrastructure in `app/core/`.

**Type Safety (CRITICAL)** — Strict MyPy + Pyright enforced. All functions must have complete type annotations. No `Any` without justification. Test files have relaxed rules (see `pyproject.toml`).

**Python Anti-Patterns** — 47 documented patterns that cause lint/type errors (includes security and schema validation patterns). See `docs/python-anti-patterns.md`. Also embedded in `/be-execute` and `/be-planning` Known Pitfalls sections.

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
make test            # Unit tests (647 tests, ~15s)
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
make install-hooks   # Install git pre-commit hook (security lint + sensitive file check)
make security-check  # Run Ruff Bandit security rules standalone

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
│   ├── auth/           # JWT auth + RBAC (6 endpoints: login, refresh, seed, reset-password, delete-user; bcrypt, Redis brute-force, token revocation)
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
├── scripts/           # Git hooks (pre-commit: security lint + sensitive file check)
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

**CI Pipeline:** GitHub Actions (`.github/workflows/ci.yml`) runs on push/PR to `main`. Three jobs: `backend-checks` (ruff + dedicated security audit via `ruff --select=S` + mypy + pyright + pytest with PostgreSQL + Redis services), `frontend-checks` (TypeScript + ESLint + build), `e2e-tests` (docker-compose full stack + Playwright, depends on first two jobs). Playwright report uploaded as artifact (14-day retention).

**Pre-commit hook:** `scripts/pre-commit` — fast (<5s) shell script that blocks commits with Bandit security violations, staged sensitive files (`.env`, `*.pem`, `*.key`), or hardcoded postgres credentials. Install via `make install-hooks`.

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
- **Redis brute-force tracking** — Fast-path lockout check before DB query; 5 failed attempts trigger 15-min lockout persisted in Redis with in-memory fallback
- **JWT token revocation** — Redis-backed denylist with TTL; `revoke_token(jti)` + `is_token_revoked(jti)` checked in `get_current_user` dependency; fail-open when Redis unavailable
- **Password complexity** — 10+ chars, mixed case, digit required on password reset (not login); enforced via `PasswordResetRequest` schema validator
- **CORS hardened** — Explicit method/header allowlists (no wildcards); `GET, POST, PATCH, DELETE, OPTIONS` only
- **Health endpoint redaction** — No provider names, environment, or error details leaked to unauthenticated callers
- **nginx CSP/HTTPS** — Content-Security-Policy headers, full HTTPS server block with modern TLS ciphers, HSTS
- **Convention enforcement tests** — `app/tests/test_security.py` (84 tests) auto-discovers all route functions and verifies authentication, checks JWT algorithm safety, bcrypt rounds, password complexity on correct schema, nginx security headers, no debug-level logging in security paths, SQL injection posture, container hardening, dependency scanning, backup infrastructure, GDPR deletion, and CSRF protection
- **Container hardening** — All containers run as non-root, `no-new-privileges:true`, `cap_drop: ALL`; production adds `read_only: true` with tmpfs
- **Dependency scanning** — `pip-audit` in CI pipeline as dedicated step; `uv lock --check` verifies lock file integrity
- **Automated backups** — `scripts/db-backup.sh` with configurable retention (default 90 days GDPR); `make db-backup-auto` for cron integration
- **GDPR right-to-erasure** — Admin-only `DELETE /api/v1/auth/users/{id}` removes user data and clears Redis tracking
- **SQL injection prevention** — All queries via SQLAlchemy ORM; convention test verifies no `text()` with f-strings in repositories
- **Out of scope (future):** Full HTTPS/TLS deployment (certs), WebSocket security, API key rotation, SIEM/monitoring integration, database encryption at rest, self-service password reset (needs SMTP), secrets management (Vault/SSM)

### Automated Security Enforcement (5 layers)

Security is enforced automatically at every stage of the development lifecycle — no manual review required to catch common security regressions:

1. **Pre-commit hook** (`scripts/pre-commit`, install via `make install-hooks`) — Runs in <5s before every `git commit`. Blocks: Bandit security violations (hardcoded creds, `assert` in prod, `exec`/`eval`), staged sensitive files (`.env`, `*.pem`, `*.key`), hardcoded `postgres:postgres@` in diffs.

2. **Convention tests** (`app/tests/test_security.py`, 84 tests) — Run in every `make test`, `make check`, and `/be-validate`. The auto-discovery test `TestAllEndpointsRequireAuth` dynamically scans every `routes.py` — adding an endpoint without auth breaks CI. Also enforces: JWT uses HS256 (not `none`), bcrypt >= 12 rounds, password complexity on `PasswordResetRequest` (not `LoginRequest`), security logging at `warning+` (not `debug`), nginx has CSP/HSTS/X-Frame-Options/X-Content-Type-Options, SQL injection posture (no raw SQL with user input), container hardening (non-root, no-new-privileges), dependency scanning in CI, backup infrastructure, GDPR deletion, CSRF protection.

3. **Secure scaffold** (`/be-create-feature`) — New features generate routes with `get_current_user`/`require_role` already in every endpoint signature. Security by default, not by remembering.

4. **CI security gate** (`.github/workflows/ci.yml`) — Dedicated "Security audit" step runs `ruff --select=S` as its own GitHub Actions status check between Lint and Type check. Security violations are a hard PR failure with their own status line — not buried in general lint output.

5. **CI dependency audit** (`.github/workflows/ci.yml`) — `pip-audit` scans all packages for known CVEs as a dedicated step. Lock file integrity verified via `uv lock --check`. Vulnerable dependencies are a hard PR failure.

## Key Reference Documents

- `reference/vsa-patterns.md` — Async repository, service, routes, cross-feature patterns
- `reference/feature-readme-template.md` — Template for feature READMEs
- `reference/PRD.md` — Product requirements and vision
- `reference/mvp-tool-designs.md` — Agent tool specifications
- `.claude/commands/CLAUDE.md` — Full slash command documentation
- `docs/python-anti-patterns.md` — 45 documented Python anti-patterns (includes security patterns)
- `docs/security_audit.txt` — First security audit findings and remediation (13 findings, commit 85bf32d)
- `docs/security_audit_2.txt` — Third security audit: code quality, data integrity, testing gaps (remediated in v3 hardening)
- `.agents/plans/security-hardening-v3.md` — Security hardening v3 plan (19 tasks, 4 phases, all implemented)
- `.agents/plans/security-hardening-v4.md` — Security hardening v4 plan (15 tasks, 4 phases: CI/CD, container, operational, convention tests)
- `docs/security_audit_4.txt` — Fourth security audit: government compliance gaps, container hardening, GDPR (2026-02-24)
- `scripts/db-backup.sh` — Automated PostgreSQL backup with retention policy
- `.github/workflows/ci.yml` — CI pipeline (backend checks + security audit gate, frontend checks, E2E tests)
- `scripts/pre-commit` — Git pre-commit hook (security lint, sensitive files, hardcoded creds)
- `docs/PLANNING/Implementation-Plan.md` — Latvia transit platform roadmap (4 phases)
- `docs/TODO.md` — Planned features with effort estimates
- `.agents/execution-reports/security-hardening-v4.md` — Security v4 execution report (15 tasks, 8 review fixes)
- `.agents/code-reviews/AUDIT-SUMMARY.md` — Full codebase health audit (120 findings, 2026-02-21)


<claude-mem-context>
# Recent Activity

<!-- This section is auto-generated by claude-mem. Edit content outside the tags. -->

### Feb 11, 2026

| ID | Time | T | Title | Read |
|----|------|---|-------|------|
| #13719 | 3:26 PM | 🔵 | VTV Project Initial State Assessment | ~280 |
</claude-mem-context>
