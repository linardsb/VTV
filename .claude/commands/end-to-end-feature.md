---
description: Autonomously develop a complete VTV feature from planning to commit
argument-hint: [feature-description]
allowed-tools: Read, Write, Edit, Bash(uv run ruff:*), Bash(uv run mypy:*), Bash(uv run pyright:*), Bash(uv run pytest:*), Bash(uv run alembic:*), Bash(git:*)
---

# End-to-End Feature — Full Autonomous Feature Lifecycle

## INPUT

**Feature request:** $ARGUMENTS

You will autonomously develop this feature from research through commit. Follow each phase completely before moving to the next.

## PROCESS

### Phase 1: Prime

Load project understanding. **Detect if this is an agent tool feature** (keywords: tool, agent, MCP, Obsidian tool, transit tool).

**If agent tool feature:**
- Load tool context: read `mvp-tool-designs.md`, `PRD.md` (agent sections), `CLAUDE.md` (tool docstrings section)
- Inventory existing tool implementations in `app/`
- Check tool design patterns (docstrings, dry-run, error formats)
- Follow agent tool planning requirements in Phase 2

**For all features:**
- Read `CLAUDE.md` for architecture and conventions
- Read `PRD.md` for product context
- Explore `app/` directory structure to understand existing features
- Read `app/main.py` for current router registrations
- Check existing shared utilities in `app/shared/`

### Phase 2: Plan

Create a detailed implementation plan:

- Design the vertical slice: models, schemas, routes, service, tests
- Identify shared utilities to reuse (TimestampMixin, PaginationParams, get_db(), get_logger())
- Plan database migrations if needed
- Define structured logging events (`feature.action_state`)
- Save plan to `plans/[feature-name].md`
- Plan must be detailed enough for another agent to execute

### Phase 3: Execute

Implement the plan step by step:

- Create all feature files following VTV conventions
- Complete type annotations on every function
- Models inherit `Base` and `TimestampMixin`
- Use `select()` for queries, `get_db()` for sessions
- Structured logging with `get_logger(__name__)`
- Google-style docstrings on all functions
- Register router in `app/main.py`
- Run migrations if needed:
  ```bash
  uv run alembic revision --autogenerate -m "[description]"
  uv run alembic upgrade head
  ```

### Phase 4: Validate

ALL must pass before proceeding to commit:

```bash
uv run ruff format .
```

```bash
uv run ruff check .
```

```bash
uv run mypy app/
```

```bash
uv run pyright app/
```

```bash
uv run pytest -v
```

Fix any failures before moving on. Do not proceed to commit with failing checks.

### Phase 5: Commit

Stage and commit with conventional format:

- Stage all new and modified files explicitly (not `git add .`)
- Use conventional commit: `feat([scope]): [description]`
- Include `Co-Authored-By: Claude <noreply@anthropic.com>`

## OUTPUT

Present a final summary:

**Feature:** [name]
**Plan:** `plans/[feature-name].md`

**Files Created:**
- [list with paths]

**Files Modified:**
- [list with paths]

**Validation Results:**
- Ruff format: PASS
- Ruff check: PASS
- MyPy: PASS
- Pyright: PASS
- Pytest: PASS ([X] tests, [Y] new)

**Commit:** `[hash]` — `[commit message]`
