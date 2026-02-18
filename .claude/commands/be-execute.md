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

- **Python Anti-Patterns — AVOID THESE (write correct code on first pass):**
  1. **No `assert` in production code** — Ruff S101. Use `if x is not None:` not `assert x is not None`
  2. **No `object` type hints** — Import and use actual types. Never write `def f(data: object)` then isinstance-check
  3. **Untyped third-party libraries** — Use mypy `[[overrides]]` + pyright file-level `# pyright:` directives. NEVER use pyright `[[executionEnvironments]]` with scoped `root` — it breaks `app.*` import resolution
  4. **Mock exceptions must match catch blocks** — If code catches `httpx.HTTPError`, test with `httpx.ConnectError`, not `Exception`
  5. **No unused imports or variables** — Ruff F401 catches unused imports, Ruff F841 catches unused local variables. Don't import or assign speculatively — only write what you actually use
  6. **No unnecessary noqa/type-ignore** — Ruff RUF100 flags unused suppression comments
  7. **Test helper functions need return type annotations** — mypy `disallow_untyped_defs=false` for tests only relaxes *defining* untyped functions, but `disallow_untyped_call` is still globally true. When `async def test_foo()` (implicitly typed via coroutine return) calls an untyped helper, mypy raises `no-untyped-call`. Fix: always add `-> ReturnType` to test helpers (e.g., `def _make_ctx() -> MagicMock:`)
  8. **No EN DASH in strings** — Ruff RUF001 forbids ambiguous Unicode characters like `–` (EN DASH, U+2013). LLMs naturally generate these in time ranges ("05:00–13:00") and prose. Always use `-` (HYPHEN-MINUS, U+002D) instead: `"05:00-13:00"`, `"trainee - supervised only"`
  9. **Pydantic AI `ctx` parameter must be referenced** — Ruff ARG001 flags unused function arguments. Tool functions require `ctx: RunContext[TransitDeps]` even when mock implementations don't need it. Always reference it: `_settings = ctx.deps.settings` and use `_settings` in logging or guards
  10. **Narrow dict value types before passing to Pydantic** — When extracting values from `dict[str, str | list[str] | None]`, the union type is too broad for Pydantic fields expecting `str | None`. Use isinstance narrowing with walrus operator: `phone=str(val) if isinstance(val := d.get("phone"), str) else None`
  11. **Schema field additions break ALL consumers** — When adding a required field to a Pydantic `BaseModel` (e.g., `route_type: int` on `VehiclePosition`), you MUST update every file that constructs that model: test helpers, mock factories, route tests. Search with `Grep` for `ModelName(` across the codebase before editing. Also update mock objects that return the model's source data — if production code does `static.routes.get(id).route_type`, the test mock for `static.routes` must return an object with a real `route_type` int, not a generic `MagicMock`.

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
