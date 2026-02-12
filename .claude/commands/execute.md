---
description: Execute a VTV implementation plan file step by step
argument-hint: [path-to-plan] e.g. plans/user-profiles.md
allowed-tools: Read, Write, Edit, Bash(uv run ruff:*), Bash(uv run mypy:*), Bash(uv run pyright:*), Bash(uv run pytest:*), Bash(uv run alembic:*)
---

This command takes a plan file (typically created by `/planning`) and implements every step in it sequentially. It reads the entire plan first to understand the full scope, then creates and modifies files following VTV conventions: strict type annotations, async SQLAlchemy patterns, structured logging with the `domain.component.action_state` format, and Google-style docstrings on all functions.

After implementation, it runs the full 5-step validation suite (ruff format, ruff check, mypy, pyright, pytest) and fixes any failures before reporting results. It also performs post-implementation checks to ensure routers are registered, models inherit `TimestampMixin`, and no type suppressions were introduced. This is the execution counterpart to `/planning` — the plan provides the blueprint, this command builds it.

The plan file must be self-contained with explicit file paths, exact code patterns, and unambiguous steps. If the plan includes database model changes, this command will also run Alembic migrations. After successful execution, use `/commit` to commit the changes.

# Execute — Implement from Plan

## INPUT

**Plan file:** $ARGUMENTS

Read the plan file completely before writing any code.

## PROCESS

### 1. Read and understand the plan

- Read the entire plan file from `$ARGUMENTS`
- Identify all files to create and modify
- Note the implementation order and dependencies between steps

### 2. Implement each step

Follow the plan's implementation steps in exact order. For each step:

- Create or modify the specified file
- Follow VTV conventions from CLAUDE.md:
  - All functions have complete type annotations
  - Models inherit from `Base` and `TimestampMixin`
  - Use `get_db()` for database sessions
  - Use `get_logger(__name__)` for structured logging
  - Logging events follow `domain.component.action_state` pattern
  - Use `select()` not `.query()` for database operations
  - Google-style docstrings for functions
  - Agent-optimized docstrings for tool functions

### 3. Run database migrations (if needed)

If the plan includes new models or schema changes:

```bash
uv run alembic revision --autogenerate -m "[description from plan]"
uv run alembic upgrade head
```

### 4. Validate — ALL must pass

Run each command in sequence. Fix any issues before moving to the next:

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

### 5. Post-implementation checks

Verify:
- [ ] Router registered in `app/main.py`
- [ ] All new functions have type annotations
- [ ] No `# type: ignore` or `# pyright: ignore` added
- [ ] Logging follows `domain.component.action_state` format
- [ ] Models inherit `TimestampMixin`
- [ ] Tests exist and pass

## OUTPUT

Report to the user:
- Files created (with paths)
- Files modified (with paths)
- Migration status (if applicable)
- Validation results (pass/fail for each of the 5 commands)
- Any deviations from the plan and why
- Suggested next step: `/commit` or manual review
