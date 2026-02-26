---
description: Execute a VTV implementation plan file step by step
argument-hint: [path-to-plan] e.g. .agents/plans/user-profiles.md
allowed-tools: Read, Write, Edit, Bash(uv run ruff:*), Bash(uv run mypy:*), Bash(uv run pyright:*), Bash(uv run pytest:*), Bash(uv run alembic:*)
---

Implement a plan file step by step following VTV conventions, then validate.

@.claude/commands/_shared/python-anti-patterns.md

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
  - **Pydantic Update schemas** MUST include `model_validator(mode="before")` to reject empty PATCH/PUT bodies (reject when all fields are None). Pattern: `reject_empty_body` classmethod that raises `ValueError("At least one field must be provided")`
  - **Constrained string fields** MUST use `Literal[...]` types, not bare `str`. When a field only accepts a fixed set of values (priority, status, category, role), define a `TypeAlias = Literal["val1", "val2", ...]` and use it as the field type. This gives Pydantic validation + TypeScript type narrowing for free

- **Python Anti-Patterns** — See the loaded `@_shared/python-anti-patterns.md` reference above. All 59 rules apply during implementation. Write correct code on first pass.

### 3. Run database migrations (if needed)

If the plan includes new models or schema changes:

**Try autogenerate first (requires running database):**
```bash
docker-compose ps 2>/dev/null && uv run alembic revision --autogenerate -m "[description from plan]"
```

**If the database is not running (connection refused, Docker not started):** Create the migration file manually instead of failing. Use the plan's model changes to write explicit `op.add_column()`, `op.create_table()`, etc. calls:
1. Find the latest revision ID in `alembic/versions/`
2. Create a new file `alembic/versions/{id}_{description}.py` with `down_revision` pointing to the latest
3. Write `upgrade()` with `op.add_column()` / `op.create_table()` calls matching the model changes
4. Write `downgrade()` with matching `op.drop_column()` / `op.drop_table()` calls
5. Document in the output that migration was created manually due to no database connection

**Do NOT** treat a missing database as a blocking failure — manual migration creation is standard practice.

### 4. Validate — ALL must pass

Run each command in sequence. Fix any issues before moving to the next:

```bash
uv run ruff format .
```

```bash
uv run ruff check --fix .
```

> **Why `--fix`?** `ruff format` does NOT fix import sorting (I001). Only `ruff check --fix` resolves auto-fixable lint issues like import ordering. This prevents needless failures when adding imports to existing files.

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

**Security convention tests (explicit gate):**

```bash
uv run pytest app/tests/test_security.py -v --tb=short
```

Security convention tests verify all endpoints require auth, JWT safety, bcrypt rounds, nginx headers, container hardening, and SDLC gates. This runs separately from the general test suite to ensure security regressions are immediately visible — not buried in 600+ test results.

**Error recovery rules:**
- **CRITICAL: After ANY code edit to fix a validation error, re-run from Level 1 (ruff format + ruff check --fix) before continuing.** Code changes made to fix type errors (mypy/pyright) frequently introduce import sorting (I001), formatting, or lint regressions. Never skip back to the level you were fixing — always restart the validation sequence from the top.
- If a check fails, attempt to fix the issue, then re-run ALL checks from Level 1 (format → lint → mypy → pyright → pytest)
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
- [ ] Update schemas have `reject_empty_body` model_validator (rejects empty PATCH/PUT)
- [ ] Constrained string fields use `Literal[...]` types, not bare `str`
- [ ] **All route endpoints have `get_current_user` or `require_role()` dependency** — `TestAllEndpointsRequireAuth` auto-discovers all routes and fails if auth is missing. If a new endpoint is legitimately public, add it to the `PUBLIC_ALLOWLIST` in `app/tests/test_security.py`
- [ ] **Security convention tests pass** (already verified in Step 4 — confirm no regressions from post-impl edits)

## OUTPUT

Report to the user:
- Files created (with paths)
- Files modified (with paths)
- Migration status (if applicable)
- Validation results (pass/fail for each of the 5 commands)
- Any deviations from the plan and why
- Suggested next step: `/commit` or manual review
