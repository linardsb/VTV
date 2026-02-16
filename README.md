# VTV — Unified CMS and AI Agent Service for Riga City Bus Operations

FastAPI + Pydantic AI agent service for transit operations and Obsidian knowledge management, built with vertical slice architecture. Next.js CMS frontend with Turborepo monorepo.

**GTFS-compliant | Swappable LLM | AI-optimized codebase**

## Overview

VTV is a unified transit operations platform for Riga's municipal bus system. This repository contains:

1. **AI Agent Service** — A FastAPI application providing a Pydantic AI agent with 9 tools: 5 read-only transit queries and 4 Obsidian vault operations
2. **CMS Frontend** — A Next.js 16 application (`cms/`) for transit operations management with RBAC, i18n, and a design token system

The agent exposes an OpenAI-compatible `/v1/chat/completions` endpoint (streaming + non-streaming) that the Next.js CMS consumes via its embedded chat sidebar.

## Quick Start

### Backend (Agent Service)

```bash
# 1. Clone the repository
git clone <your-repo>
cd vtv

# 2. Install dependencies
uv sync

# 3. Start services (PostgreSQL)
docker-compose up -d

# 4. Set up environment
cp .env.example .env  # Edit DATABASE_URL if needed

# 5. Run migrations
uv run alembic upgrade head

# 6. Start development server
uv run uvicorn app.main:app --reload --port 8123
```

Visit `http://localhost:8123/docs` for Swagger UI.

### Frontend (CMS)

```bash
# 1. Install dependencies
cd cms && pnpm install

# 2. Start development server
pnpm --filter @vtv/web dev
```

Visit `http://localhost:3000` for the CMS.

## Architecture

```
┌─────────────────────────────────────────────────┐
│        Next.js 16 CMS (Turborepo Monorepo)      │
│  Routes, Stops, Schedules, GTFS, AI Chat        │
│              │                       │          │
│  Auth.js v5 + RBAC          POST /v1/chat/      │
│  next-intl (lv/en)          completions         │
│  Tailwind v4 + Tokens               │          │
└──────────────────────────────────────┼──────────┘
                                       │
                          ┌────────────▼──────────┐
                          │  FastAPI Agent Service │
                          │  (this repository)     │
                          │                       │
                          │  Unified Pydantic AI   │
                          │  Agent (9 tools)       │
                          │                       │
                          │  Transit    Obsidian   │
                          │  Tools (5)  Tools (4)  │
                          └────────────────────────┘
```

### AI Agent — One Agent, All Tools

The LLM decides which tools to use based on the user's query. No routing logic, no agent registry.

**Transit Tools (5, all read-only — AI advises, humans decide):**

| Tool | Purpose | Data Source |
|------|---------|------------|
| `query_bus_status` | Current delay/position for a route or vehicle | VTV API |
| `get_route_schedule` | Timetable for a route and service date | VTV API |
| `search_stops` | Search stops by name or proximity (lat/lon) | VTV API |
| `get_adherence_report` | On-time performance metrics for routes/periods | VTV API |
| `check_driver_availability` | Available drivers for a shift/date | VTV API |

**Obsidian Vault Tools (4):**

| Tool | Purpose | Actions |
|------|---------|---------|
| `obsidian_query_vault` | Search and discover | search, find_by_tags, list, recent, glob |
| `obsidian_manage_notes` | Note CRUD | create, read, update, delete, move |
| `obsidian_manage_folders` | Folder operations | create, delete, list, move |
| `obsidian_bulk_operations` | Batch operations | move, tag, delete, update_frontmatter, create |

### LLM Provider Strategy

The agent treats the LLM as a swappable dependency — switch providers with a single env var:

```bash
# Cloud API (best reasoning)
LLM_PROVIDER=anthropic
LLM_MODEL=claude-sonnet-4-5

# Fully local (zero cost)
LLM_PROVIDER=ollama
LLM_MODEL=llama3.1:70b

# Local with cloud fallback
LLM_PROVIDER=ollama
LLM_MODEL=llama3.1:70b
LLM_FALLBACK_PROVIDER=anthropic
LLM_FALLBACK_MODEL=claude-sonnet-4-5
```

Supports: Ollama, Anthropic, OpenAI, Groq, OpenRouter, any OpenAI-compatible API.

### Safety Constraints

- Transit tools: **read-only**, no write operations
- Vault deletes: require `confirm: true`
- Bulk operations: support `dry_run` for preview
- Path sandboxing: prevents directory traversal (`../`)
- Monthly spending cap on cloud LLM API

## Project Structure

```
VTV/
├── app/                    # Backend (FastAPI + Pydantic AI)
│   ├── core/               # Infrastructure (config, database, logging, middleware, health, exceptions)
│   ├── shared/             # Cross-feature utilities (pagination, timestamps, error schemas)
│   ├── agent/              # AI agent feature (tools/, routes, service, schemas)
│   ├── {feature}/          # Feature slices (routes.py, service.py, repository.py, models.py, schemas.py)
│   ├── tests/              # Application-level tests
│   └── main.py             # FastAPI entry point
├── cms/                    # Frontend (Next.js 16 + Turborepo)
│   ├── apps/web/           # Next.js application (@vtv/web)
│   ├── packages/ui/        # Design tokens and shared UI (@vtv/ui)
│   ├── packages/sdk/       # OpenAPI TypeScript client (@vtv/sdk)
│   ├── packages/typescript-config/  # Shared tsconfig presets
│   └── design-system/vtv/  # Design system docs (MASTER.md + page overrides)
├── reference/              # Architecture docs (PRD, tool designs, VSA patterns)
├── docs/                   # Development standards (logging, pytest, SQLAlchemy, RCA)
├── alembic/                # Database migrations
├── .claude/commands/       # 21 Claude Code slash commands
└── pyproject.toml          # Python dependencies and tooling config
```

## Commands

### Backend

```bash
# Development
uv run uvicorn app.main:app --reload --port 8123

# Testing (75 tests, <1.2s execution)
uv run pytest -v                    # All tests
uv run pytest -v -m integration     # Integration tests only

# Type checking (strict mode)
uv run mypy app/
uv run pyright app/

# Linting
uv run ruff check .
uv run ruff format .

# Database migrations
uv run alembic revision --autogenerate -m "description"
uv run alembic upgrade head

# Docker
docker-compose up -d --build
```

### Frontend

```bash
cd cms

# Development
pnpm --filter @vtv/web dev

# Type check
pnpm --filter @vtv/web type-check

# Lint
pnpm --filter @vtv/web lint

# Build
pnpm --filter @vtv/web build

# Generate SDK client (requires FastAPI on port 8123)
pnpm --filter @vtv/sdk generate-sdk
```

## Slash Commands

21 Claude Code commands for AI-assisted development:

### Backend Commands (16)

| Command | Purpose |
|---------|---------|
| `/init-project` | Initialize dev environment (Docker, env, migrations, health checks) |
| `/prime` | Load full backend codebase context |
| `/prime-tools` | Load tool designs, patterns, and agent architecture |
| `/planning` | Research and create implementation plan for a feature |
| `/create-feature` | Scaffold a new VSA feature slice |
| `/execute` | Implement a plan autonomously |
| `/end-to-end-feature` | Full feature lifecycle (plan, implement, test, commit) |
| `/validate` | Run full validation suite (lint, types, tests) |
| `/review` | Review code against VTV standards |
| `/code-review-fix` | Fix issues found in a code review report |
| `/rca` | Root cause analysis for bugs |
| `/implement-fix` | Implement fix from RCA document |
| `/execution-report` | Compare implementation against plan |
| `/system-review` | Analyze implementation vs plan for process improvements |
| `/update-docs` | Update project documentation after feature implementation |
| `/commit` | Create conventional commit with safety checks |

### Frontend Commands (5)

| Command | Purpose |
|---------|---------|
| `/fe-prime` | Load frontend context (design system, components, pages, i18n, RBAC) |
| `/fe-planning` | Plan a frontend page or feature |
| `/fe-create-page` | Scaffold a new Next.js page with i18n, RBAC, sidebar nav |
| `/fe-execute` | Execute a frontend plan step by step |
| `/fe-validate` | Run frontend quality checks (TypeScript, lint, build, design system, i18n, a11y) |

### Workflow Chains

```
Backend:  /prime → /planning → /execute → /validate → /commit
Frontend: /fe-prime → /fe-planning → /fe-execute → /fe-validate → /commit
```

## Tech Stack

### Backend

| Layer | Technology |
|-------|-----------|
| Language | Python 3.12+ |
| Framework | FastAPI 0.120+ |
| Agent | Pydantic AI 1.58+ |
| ORM | SQLAlchemy 2.0+ (async) |
| Database | PostgreSQL 18 + asyncpg |
| Migrations | Alembic |
| Validation | Pydantic 2.0+ |
| Type Checking | MyPy + Pyright (strict) |
| Linting | Ruff |
| Testing | pytest + pytest-asyncio |
| Package Manager | uv |

### Frontend

| Layer | Technology |
|-------|-----------|
| Framework | Next.js 16 (App Router) |
| UI Library | React 19 |
| Styling | Tailwind CSS v4 + design tokens |
| Components | shadcn/ui + CVA |
| Auth | Auth.js v5 (4-role RBAC) |
| i18n | next-intl (Latvian + English) |
| Build | Turborepo + pnpm workspaces |
| SDK | @hey-api/openapi-ts |

## Requirements

- Python 3.12+
- uv
- Node.js 20+
- pnpm 9+
- Docker + Docker Compose
- PostgreSQL 18+ (via Docker or cloud provider)

## Key References

- [PRD](reference/PRD.md) — Full product requirements
- [MVP Tool Designs](reference/mvp-tool-designs.md) — Detailed Obsidian tool specifications
- [VSA Patterns](reference/vsa-patterns.md) — Async vertical slice architecture patterns
- [Logging Standard](docs/logging-standard.md) — Structured logging conventions
- [Pytest Standard](docs/pytest-standard.md) — Testing patterns and configuration
- [Commands](/.claude/commands/CLAUDE.md) — Full documentation for all 21 slash commands

## License

MIT
