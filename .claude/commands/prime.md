---
description: Load full VTV project context into the current session
argument-hint:
allowed-tools: Read, Glob, Bash(git status:*), Bash(git log:*), Bash(docker-compose ps:*), Bash(curl:*)
---

Load complete VTV project context — architecture, features, infrastructure state — for the current session.

@CLAUDE.md
@reference/PRD.md
@reference/mvp-tool-designs.md

# Prime — Load VTV Project Context

## INPUT

You are priming yourself with a complete understanding of the VTV project. Read everything before producing output.

## PROCESS

### 1. Read core documentation

The three core docs are loaded via `@` references above. Review them for:
- `CLAUDE.md` — architecture, conventions, commands
- `reference/PRD.md` — product requirements and vision
- `reference/mvp-tool-designs.md` — agent tool specifications

### 2. Analyze project structure

- List the directory tree under `app/` (2 levels deep)
- Identify which features exist under `app/` (each feature directory = one vertical slice)
- Read `app/main.py` to see registered routers and middleware

### 3. Check infrastructure state

- Read `docker-compose.yml` for service configuration
- Read `pyproject.toml` for dependencies and tooling config
- Read `alembic/versions/` to understand current migration state

### 4. Assess current state

```
!git status
```

```
!git log --oneline -10
```

### 5. Check running services

```
!docker-compose ps 2>/dev/null || echo "Docker not running"
```

```
!curl -s http://localhost:8123/health 2>/dev/null || echo "API not responding"
```

## OUTPUT

Present a scannable summary using this structure:

**Project:** VTV — [one-line description from PRD]

**Architecture:** Vertical slice | FastAPI + async SQLAlchemy + Pydantic | Python 3.12+

**Tech Stack:**
- Runtime: [versions]
- Database: [PostgreSQL version, async driver]
- Key deps: [structlog, alembic, etc.]

**Features Implemented:**
- [feature name] — [status: complete/in-progress/planned]

**Features Planned (from PRD):**
- [feature name] — [brief description]

**Infrastructure:**
- Docker: [running/stopped]
- API Health: [healthy/unhealthy/not running]
- Database: [connected/disconnected]

**Current Branch:** [branch name]
**Recent Changes:** [last 3 commits, one line each]

**Key Entry Points:**
- API: `app/main.py`
- Config: `app/core/config.py`
- Database: `app/core/database.py`
- Logging: `app/core/logging.py`

**Validation Commands:**
```
uv run ruff format . && uv run ruff check . && uv run mypy app/ && uv run pyright app/ && uv run pytest -v
```

**Next steps:**
- To build a new feature: `/planning [feature description]`
- To scaffold a feature skeleton: `/create-feature [name]`
- To investigate a bug: `/rca [issue-id]`
