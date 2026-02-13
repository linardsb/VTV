# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

VTV is a unified transit operations platform for Riga's municipal bus system. This repository contains the **AI Agent Service** — a FastAPI + Pydantic AI application providing a unified agent with 9 tools (5 transit + 4 Obsidian vault). Built with **vertical slice architecture**, optimized for AI-assisted development. Python 3.12+, strict type checking with MyPy and Pyright.

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

**AI-Optimized Patterns**

- Structured logging: Use `domain.component.action_state` pattern (hybrid dotted namespace)
  - Format: `{domain}.{component}.{action}_{state}`
  - Examples: `user.registration_started`, `product.create_completed`, `agent.tool.execution_failed`
  - See `docs/logging-standard.md` for complete event taxonomy
- Request correlation: All logs include `request_id` automatically via context vars
- Consistent verbose naming: Predictable patterns for AI code generation

## Essential Commands

### Development

```bash
# Start development server (port 8123)
uv run uvicorn app.main:app --reload --port 8123
```

### Testing

```bash
# Run all tests (75 tests, <3s execution)
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
# Build and start all services
docker-compose up -d --build

# View app logs
docker-compose logs -f app

# Stop all services
docker-compose down
```

## Architecture

### Project Structure

```
VTV/
├── app/
│   ├── core/           # Infrastructure (config, database, logging, middleware, health, exceptions)
│   ├── shared/         # Cross-feature utilities (pagination, timestamps, error schemas)
│   ├── main.py         # FastAPI application entry point
│   ├── agent/          # AI agent feature (see Agent Module below)
│   ├── {feature}/      # Feature slices (e.g., products/, orders/)
│   └── tests/          # Integration tests spanning multiple features
├── reference/          # Architecture docs and templates
│   ├── vsa-patterns.md         # Async VSA patterns (repository, service, routes, cross-feature)
│   ├── feature-readme-template.md  # Template for feature README.md files
│   ├── PRD.md                  # Product requirements document
│   └── mvp-tool-designs.md    # Agent tool specifications
├── .claude/commands/   # 16 slash commands (see .claude/commands/CLAUDE.md for full docs)
├── .agents/            # Agent workflow outputs
│   ├── plans/              # Implementation plans created by /planning
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

- `RequestLoggingMiddleware`: Logs all requests with correlation IDs
- `CORSMiddleware`: Configured for local development (see `app.core.config`)
- Adds `X-Request-ID` header to all responses

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

### Agent Module (Planned)

VTV's primary feature is a Pydantic AI agent. It follows the feature slice pattern with a `tools/` subdirectory:

```
app/agent/
├── routes.py          # /v1/chat/completions, /v1/models
├── service.py         # Agent orchestration, model building
├── schemas.py         # OpenAI-compatible request/response schemas
├── config.py          # LLM provider settings (model names, tokens, timeouts)
├── exceptions.py      # Agent-specific exceptions
├── tools/
│   ├── transit/       # 5 read-only tools (see below)
│   └── obsidian/      # 4 vault tools (see below)
└── tests/
```

`config.py` is feature-specific (not in `core/`) because LLM settings are agent-specific. Tools are grouped by domain under `tools/`, each with agent-optimized docstrings (see "Tool Docstrings for Agents" above).

**Transit Tools (5, all read-only — AI advises, humans decide):**
- `query_bus_status` — Current delay/position for a route or vehicle
- `get_route_schedule` — Timetable for a route and service date
- `search_stops` — Search stops by name or proximity (lat/lon)
- `get_adherence_report` — On-time performance metrics for routes/periods
- `check_driver_availability` — Available drivers for a shift/date

**Obsidian Vault Tools (4):**
- `obsidian_query_vault` — Search and discover (search, find_by_tags, list, recent, glob)
- `obsidian_manage_notes` — Individual note CRUD (create, read, update, delete, move)
- `obsidian_manage_folders` — Folder operations (create, delete, list, move)
- `obsidian_bulk_operations` — Batch operations (move, tag, delete, update_frontmatter, create)

**Agent Safety Constraints:**
- Transit tools: read-only, no write operations
- Vault deletes: require `confirm: true` parameter
- Bulk operations: support `dry_run` for preview before execution
- Path sandboxing: prevents directory traversal (`../`)
- No vault file access outside configured vault path
- Monthly spending cap on Claude API (EUR 100 hard limit)
- Token budget per user per day (50 queries)

### Configuration

- Environment variables via Pydantic Settings (`app.core.config`)
- Required: `DATABASE_URL` (postgresql+asyncpg://...)
- Copy `.env.example` to `.env` for local development
- Settings singleton: `get_settings()` from `app.core.config`

## Development Guidelines

**When Creating New Features**

Use `/create-feature {name}` to scaffold, or follow these steps manually:

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
- `.claude/commands/CLAUDE.md` — Full documentation for all 16 slash commands with usage, behavior, and workflows


<claude-mem-context>
# Recent Activity

<!-- This section is auto-generated by claude-mem. Edit content outside the tags. -->

### Feb 11, 2026

| ID | Time | T | Title | Read |
|----|------|---|-------|------|
| #13719 | 3:26 PM | 🔵 | VTV Project Initial State Assessment | ~280 |
</claude-mem-context>