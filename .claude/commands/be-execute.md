---
description: Execute a VTV implementation plan file step by step
argument-hint: [path-to-plan] e.g. .agents/plans/user-profiles.md
allowed-tools: Read, Write, Edit, Bash(uv run ruff:*), Bash(uv run mypy:*), Bash(uv run pyright:*), Bash(uv run pytest:*), Bash(uv run alembic:*)
---

Implement a plan file step by step following VTV conventions, then validate.

@CLAUDE.md

# Execute — Implement from Plan

## INPUT

**Plan file:** $ARGUMENTS

Read the plan file completely before writing any code.

## PROCESS

### 0. Pre-flight checks

Before reading the plan, verify the environment is ready:
- Verify the plan file at `$ARGUMENTS` exists and is readable
- Verify `.agents/plans/` directory exists
- Check that validation tools are available: `uv run ruff --version`, `uv run mypy --version`

If any pre-flight check fails, STOP and tell the user what's missing.

### 1. Read and understand the plan

- Read the entire plan file from `$ARGUMENTS`
- Identify all files to create and modify
- Note the implementation order and dependencies between steps

### 2. Implement each step

Follow the plan's implementation steps in exact order. For each step:

- Create or modify the specified file
- If you need to deviate from the plan, document why in the output
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
uv run pytest -v -m "not integration"
```

**Integration tests (if Docker is running):**

```bash
docker-compose ps 2>/dev/null && uv run pytest -v -m integration || echo "Skipped — Docker not running"
```

**Error recovery rules:**
- If a check fails, attempt to fix the issue and re-run that specific check
- Maximum 3 fix attempts per check before stopping
- If you cannot fix after 3 attempts, STOP and report the failures to the user with:
  - Which check failed
  - What you tried
  - The exact error output
  - Do NOT proceed to post-implementation checks with failing validation

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
