# VTV — Unified CMS and AI Agent Service for Riga City Bus Operations

FastAPI + Pydantic AI agent service for transit operations and Obsidian knowledge management, built with vertical slice architecture.

**GTFS-compliant | Swappable LLM | AI-optimized codebase**

## Overview

VTV is a unified transit operations platform for Riga's municipal bus system. This repository contains the **AI Agent Service** — a FastAPI application providing a Pydantic AI agent with 9 tools: 5 read-only transit queries and 4 Obsidian vault operations.

The agent exposes an OpenAI-compatible `/v1/chat/completions` endpoint (streaming + non-streaming) that the Next.js CMS consumes via its embedded chat sidebar.

## Quick Start

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

## Architecture

```
┌─────────────────────────────────────────────────┐
│              Next.js 15 CMS Monolith            │
│  Routes, Stops, Schedules, GTFS, AI Chat        │
│              │                       │          │
│     Drizzle ORM + PostGIS    POST /v1/chat/     │
│              │               completions        │
│     PostgreSQL (Supabase)            │          │
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
| `query_bus_status` | Current delay/position for a route or vehicle | VTV tRPC API |
| `get_route_schedule` | Timetable for a route and service date | VTV tRPC API |
| `search_stops` | Search stops by name or proximity (lat/lon) | VTV tRPC API |
| `get_adherence_report` | On-time performance metrics for routes/periods | VTV tRPC API |
| `check_driver_availability` | Available drivers for a shift/date | VTV tRPC API |

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
app/
├── core/           # Infrastructure (config, database, logging, middleware, health, exceptions)
├── shared/         # Cross-feature utilities (pagination, timestamps, error schemas)
├── agent/          # (Planned) Pydantic AI agent with transit + Obsidian tools
├── {feature}/      # Feature slices (routes.py, service.py, repository.py, models.py, schemas.py)
├── tests/          # Application-level tests
└── main.py         # FastAPI entry point

reference/          # Architecture docs (PRD, tool designs, VSA patterns)
docs/               # Development standards (logging, pytest, SQLAlchemy, RCA)
alembic/            # Database migrations
.claude/commands/   # 13 Claude Code slash commands
```

## Commands

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
uv run alembic downgrade -1

# Docker
docker-compose up -d --build        # Build and start
docker-compose logs -f app          # View logs
docker-compose down                 # Stop
```

## Slash Commands

13 Claude Code commands for AI-assisted development:

| Command | Purpose |
|---------|---------|
| `/init-project` | Initialize dev environment (Docker, env, migrations, health checks) |
| `/prime` | Load full codebase understanding into agent context |
| `/prime-tools` | Load tool designs, patterns, and agent architecture |
| `/planning` | Research and create implementation plan for a feature |
| `/plan-template` | Output blank plan template for manual use |
| `/create-feature` | Scaffold a new VSA feature slice |
| `/execute` | Implement a plan autonomously |
| `/end-to-end-feature` | Full feature lifecycle (plan, implement, test, commit) |
| `/validate` | Run full validation suite (lint, types, tests) |
| `/review` | Review code against VTV standards |
| `/rca` | Root cause analysis for GitHub issues |
| `/implement-fix` | Implement fix from RCA document |
| `/commit` | Create conventional commit |

## Tech Stack

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
| Containerization | Docker + Docker Compose |

## Requirements

- Python 3.12+
- uv
- Docker + Docker Compose
- PostgreSQL 18+ (via Docker or cloud provider)

## Key References

- [PRD](reference/PRD.md) — Full product requirements
- [MVP Tool Designs](reference/mvp-tool-designs.md) — Detailed Obsidian tool specifications
- [VSA Patterns](reference/vsa-patterns.md) — Async vertical slice architecture patterns
- [Logging Standard](docs/logging-standard.md) — Structured logging conventions
- [Pytest Standard](docs/pytest-standard.md) — Testing patterns and configuration

## License

MIT
