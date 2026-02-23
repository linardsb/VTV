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
  - **Pydantic Update schemas** MUST include `model_validator(mode="before")` to reject empty PATCH/PUT bodies (reject when all fields are None). Pattern: `reject_empty_body` classmethod that raises `ValueError("At least one field must be provided")`
  - **Constrained string fields** MUST use `Literal[...]` types, not bare `str`. When a field only accepts a fixed set of values (priority, status, category, role), define a `TypeAlias = Literal["val1", "val2", ...]` and use it as the field type. This gives Pydantic validation + TypeScript type narrowing for free

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
  12. **Untyped library decorators need a 3-layer fix on FIRST PASS** — When adding an untyped lib (e.g., slowapi):
      - mypy: Add `[[tool.mypy.overrides]]` with `ignore_missing_imports = true` for the module
      - pyright: Add file-level `# pyright: reportUnknownMemberType=false, reportUntypedFunctionDecorator=false` on EVERY file using the decorator
      - ruff: Add per-file-ignores for `ARG001` if the lib forces unused params (e.g., `request: Request` for slowapi)
      - All three layers must be done simultaneously — missing any one causes a validation failure
  13. **`limiter.enabled = False` in tests must come AFTER all imports** — Ruff E402 flags module-level imports placed after non-import statements. Write all `from ... import ...` lines first, then `limiter.enabled = False`.
  14. **Don't add `type: ignore` in test files** — mypy relaxes typing for tests (`disallow_untyped_defs=false`). Adding `# type: ignore[arg-type]` on test lines becomes "unused ignore" (mypy unused-ignore). Use pyright file-level `# pyright: reportArgumentType=false` instead.
  15. **Pydantic field constraints on shared models affect ALL code paths** — `max_length=4000` on `ChatMessage.content` blocks both input AND output. Move input-only validation to a `field_validator` on the REQUEST model, not the shared message model.
  16. **Singleton close must handle closed event loops** — TestClient shuts down the event loop before lifespan cleanup runs. Wrap `await client.aclose()` in `try/except RuntimeError: pass`.
  17. **`verify=False` needs `# noqa: S501`** — Ruff S501 flags `httpx.AsyncClient(verify=False)`. When SSL verification is intentionally disabled (e.g., Obsidian self-signed cert), add `# noqa: S501` on the same line with a comment explaining why.
  18. **ARG001 applies to ALL unused function params, not just `ctx`** — Any function parameter that isn't used in the function body triggers ARG001. For params validated elsewhere (e.g., `recursive` validated in the caller but unused in a helper), add `_ = param_name` with a comment. Rule #9 above covers `ctx` specifically, but this applies to every unused param.
  19. **`dict.get()` returns the full union type — use walrus for isinstance narrowing** — `isinstance(d.get("key"), int)` narrows the `.get()` return but NOT a subsequent `d["key"]` access. The `[]` access still returns the full union. Fix: use walrus operator `val if isinstance(val := d.get("key"), int) else None`. Same for sort key lambdas: `key=lambda r: str(r.get("title", ""))` — always wrap `.get()` in `str()` for sort keys.
  20. **NEVER use `replace_all: true` to remove end-of-line comments** — The Edit tool's `replace_all` can silently collapse lines when removing `# type: ignore` or `# noqa` comments at line endings. The replacement removes the matched text AND the following newline gets lost, merging two statements onto one line. Always use targeted single edits to remove inline comments, or replace the entire line including the newline.
  21. **Clear mypy cache after renaming type aliases** — When renaming a type (e.g., `TransitDeps` to `UnifiedDeps` with `TransitDeps = UnifiedDeps` alias), mypy's incremental cache confuses TypeAlias with TypeInfo and crashes. Always run `rm -rf .mypy_cache` before `uv run mypy app/` after any type alias refactoring.
  22. **Dict literal types must match function param types exactly (invariance)** — In tests, `{"key": "value"}` is inferred as `dict[str, str]` which is NOT compatible with `dict[str, str | list[str] | None]` due to dict invariance. Always add explicit type annotations to dict literals in tests: `fm: dict[str, str | list[str] | int | float | bool | None] = {"key": "value"}`.
  23. **Lazy-loaded untyped lib models use `Any`, not `object`** — When lazy-loading models from untyped libraries (e.g., `sentence-transformers`), type the field as `Any | None`, not `object | None`. The `object` type blocks method calls (`.encode()`, `.predict()`) causing mypy `attr-defined` errors, while `# type: ignore` triggers `unused-ignore`. Use `Any` and add `# noqa: ANN401` on any `-> Any` helper methods that return these models.
  24. **Dataclass `field(default_factory=dict)` needs typed lambda** — Pyright infers `dict[Unknown, Unknown]` from bare `dict`. Use an explicitly typed lambda: `field(default_factory=lambda: dict[str, str | int | None]())` to satisfy pyright's `reportUnknownVariableType`.
  25. **Untyped lib method returns need `str()` wrapping** — Methods on objects from untyped libs (e.g., `page.get_text()` from fitz, `pytesseract.image_to_string()`) return `Unknown` type. Always wrap in `str()`: `text = str(page.get_text())`. This satisfies pyright without needing `reportUnknownArgumentType=false`.
  26. **Partially annotated test functions need `-> None`** — Adding a type annotation to a pytest fixture parameter (e.g., `tmp_path: Path`) without a return type triggers mypy `no-untyped-def` because the function becomes "partially typed". Always add both: `def test_foo(tmp_path: Path) -> None:`. This applies to ANY test function where you annotate even one parameter.
  27. **Pydantic `Field(None, ...)` confuses pyright about required params** — Pyright doesn't understand that `Field(None, description="...")` sets a default of `None`. When constructing models in tests, explicitly pass all `Field(None)` params: `MyModel(required_field="x", optional_field=None)` instead of relying on the Pydantic default.
  28. **Bare `[]` list literals inferred as `list[Unknown]`** — Pyright `reportUnknownMemberType` fires on `.append()` when the list has no type annotation. Always annotate: `items: list[MagicMock] = []` not `items = []`. Same pattern as rule #24 for dicts.
  29. **Adding optional fields to existing Pydantic schemas breaks ALL constructors** — When adding `Field(None, ...)` fields to an existing schema (e.g., adding `title: str | None = Field(None)` to `DocumentUpload`), pyright treats `Field(None)` as NOT having a default. You MUST immediately grep for `SchemaName(` across the ENTIRE codebase and update ALL constructors to pass the new fields explicitly — including test fixtures in `conftest.py`, route handlers, service calls, and inline test constructions. This is rule #27 applied proactively: don't wait for pyright to catch it, fix every constructor in the SAME step that adds the field.
  30. **Existing tests break when new types are added** — When adding support for a new document type, file format, or enum value, grep for tests that assert on "unsupported" or "unknown" types. Tests like `test_unsupported_type_raises("xlsx")` will fail after xlsx becomes supported. Update these tests in the SAME step that adds the new type support.
  31. **`@computed_field` on `@property` needs `# type: ignore[prop-decorator]`** — mypy errors with "Decorators on top of @property are not supported" when Pydantic's `@computed_field` is stacked on `@property`. Always add `# type: ignore[prop-decorator]` on the `@computed_field` line. This is the ONE valid use of `type: ignore` in production code for this pattern.
  32. **Don't guess `# type: ignore` codes — validate then add** — NEVER speculatively add `# type: ignore[arg-type]`, `[type-arg]`, or other codes. mypy's `unused-ignore` rule will flag every wrong guess, creating a fix cycle. Instead: write the code WITHOUT any ignores, run mypy, read the EXACT error code from the output, THEN add the precise `# type: ignore[{code}]`. Same applies to `# noqa:` — verify the violation exists before suppressing it.
  33. **`dict[str, object]` fails Pydantic `**kwargs` unpacking** — When parsing JSON into dicts that get unpacked into Pydantic constructors (`Model(**f)`), use `dict[str, Any]` with `from typing import Any`, NOT `dict[str, object]`. Pyright rejects `object` values for typed `str` parameters. The `Any` type allows the Pydantic constructor to handle validation.
  34. **Redis async client stubs: `await` returns `Awaitable[T] | T`** — The `redis` package has partial type stubs. Methods like `ping()`, `smembers()`, `mget()` are typed as returning `Awaitable[T] | T` which mypy can't `await`. Fix: add `# type: ignore[misc]` on each `await redis_client.method()` line. Also add pyright file-level directive: `# pyright: reportUnknownMemberType=false, reportMissingTypeStubs=false`. For `smembers()` results, also add `reportUnknownArgumentType=false, reportUnknownVariableType=false` since set elements are untyped.
  35. **`redis.pipeline()` is SYNC, not async** — `Redis.pipeline()` returns a `Pipeline` object synchronously, NOT a coroutine. In tests, mock Redis with `MagicMock()` (not `AsyncMock()`), then set `mock_pipe.execute = AsyncMock(return_value=[])` since only `execute()` is async. Using `AsyncMock()` for the Redis object makes `pipeline()` return a coroutine, breaking `pipe.set()` calls.
  36. **Lazy imports inside `if` blocks break `@patch` targets** — When a function lazily imports inside an `if` branch (e.g., `if poller_enabled: from module import func`), you CANNOT patch the importing module's namespace (`@patch("app.service.func")`) because the name doesn't exist at module level. Instead, patch the ORIGINAL module: `@patch("app.module.func")`. The lazy import will then pick up the mock.
  37. **Bare `except: pass` violates Ruff S110** — `try/except SomeError: pass` triggers Ruff S110 ("try-except-pass detected"). Always log in except blocks: `except SomeError: logger.debug("event_name", exc_info=True)`. The ONE exception is `except asyncio.CancelledError: pass` in task cleanup, which Ruff allows because CancelledError is a BaseException.
  38. **Background asyncio tasks must handle ALL exceptions in `stop_*()`** — When cancelling background tasks with `task.cancel(); await task`, only catching `CancelledError` is insufficient. If the task already failed (e.g., Redis `ConnectionError`), `await task` re-raises the original exception, NOT `CancelledError`. Fix: catch `CancelledError` and `Exception` separately: `except asyncio.CancelledError: pass` then `except Exception: logger.debug(...)`. Also wrap `start_*()` functions in try/except so service unavailability (Redis down) doesn't crash app startup.
  39. **`from datetime import date` shadows field names named `date`** — In models/schemas with a field called `date` (e.g., `CalendarDate.date`), importing `from datetime import date` causes pyright to confuse the field name with the type. Always use `import datetime` and reference as `datetime.date` / `datetime.datetime` when ANY model/schema in the file has a field named `date` or `datetime`.
  40. **FastAPI `Query(None)` needs `# noqa: B008`** — Just like `Depends()`, `Query()` is a function call in argument defaults. Ruff B008 flags all of these. Always add `# noqa: B008` on lines using `Query(...)` in FastAPI route function signatures, same as `Depends()`.
  41. **ILIKE search params must escape wildcards** — Any `.ilike(f"%{search}%")` pattern is vulnerable to wildcard injection. Always use `from app.shared.utils import escape_like` and `f"%{escape_like(search)}%"`.
  42. **File uploads must enforce size limits in application code** — Never `await file.read()` without a streaming size check. Use `while chunk := await file.read(8192)` with a running counter and `raise HTTPException(status_code=413)` on overflow.
  43. **User-provided filenames must be regex-sanitized** — Always `re.sub(r"[^\w\-.]", "_", filename)` before using in file paths. After constructing the stored path, validate with `stored_path.resolve().is_relative_to(storage_dir.resolve())`.
  44. **Never log URLs that may contain credentials** — Use `_redact_url()` (via `urllib.parse.urlparse`) to mask passwords before passing URLs to `logger.info()`. Applies to Redis URLs, database URLs, and any external service URLs.
  45. **Rate limiter must use X-Real-IP, not X-Forwarded-For** — `X-Forwarded-For` is client-spoofable. Use `request.headers.get("X-Real-IP")` (set by nginx, trustworthy) with fallback to `get_remote_address(request)`.
  46. **Docker credentials must use env var interpolation** — In docker-compose.yml, use `${POSTGRES_PASSWORD:-postgres}` syntax, never hardcoded `POSTGRES_PASSWORD: postgres`.
  47. **GTFS time validation needs range check** — Regex `^\d{2}:\d{2}:\d{2}$` is format-only.
    Always add field_validator for minutes < 60, seconds < 60.
  48. **Unique constraints for GTFS composite keys** — Always add `__table_args__` with
    UniqueConstraint for natural keys (trip_id+stop_sequence, calendar_id+date).
  49. **Unknown file types must be rejected** — Never default to "text" for unrecognized MIME types.
    Return 415 Unsupported Media Type.
  50. **Wrap error-path DB updates in try/except** — If `update_status("failed")` itself fails
    (DB gone), it masks the original error. Always: try/except around cleanup DB calls.
  51. **Clean up stored files on processing failure** — If file is copied to permanent storage
    before processing, add cleanup in the exception handler.
  52. **Empty PATCH bodies must be rejected** — Add `@model_validator(mode="after")` to reject
    updates where no fields are provided. Prevents unnecessary DB round-trips.
  53. **Content-Length must be parsed defensively** — `int(content_length)` raises ValueError on
    malformed headers. Always wrap in try/except.
  54. **FastAPI `HTTPBearer(auto_error=True)` returns 403, not 401** — The default `HTTPBearer()` returns 403 when the Authorization header is missing (FastAPI framework design), but RFC 7235 requires 401 for missing authentication. Always use `HTTPBearer(auto_error=False)` and handle the missing-token case manually: raise `HTTPException(status_code=401, detail="Not authenticated", headers={"WWW-Authenticate": "Bearer"})`.
  55. **`app.dependency_overrides` is global and leaks between test modules** — FastAPI's `dependency_overrides` dict lives on the shared global `app` object. If one test module sets `app.dependency_overrides[get_current_user] = mock_user`, that override persists into ALL subsequent test modules in the same pytest session. Always use a pytest fixture that saves the original overrides, clears them, yields, then restores: `saved = app.dependency_overrides.copy(); app.dependency_overrides.clear(); yield; app.dependency_overrides = saved`.
  56. **Never expose role names or permission details in authorization error messages** — Error messages like `"Requires one of roles: admin, editor"` leak internal authorization logic to attackers. Always use generic messages: `"Insufficient permissions"`. The 403 status code already communicates "forbidden" — the error detail should NOT enumerate which roles are allowed.

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

## OUTPUT

Report to the user:
- Files created (with paths)
- Files modified (with paths)
- Migration status (if applicable)
- Validation results (pass/fail for each of the 5 commands)
- Any deviations from the plan and why
- Suggested next step: `/commit` or manual review
