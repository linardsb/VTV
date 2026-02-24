---
description: Research codebase and create a self-contained implementation plan
argument-hint: [feature-description] e.g. add obsidian search tool
allowed-tools: Read, Glob, Grep, Write
---

Research the codebase and produce a self-contained plan that `/be-execute` can follow without additional context.

@CLAUDE.md
@reference/PRD.md

# Planning — Create Feature Implementation Plan

## INPUT

**Feature request:** $ARGUMENTS

Make sure the structured planning is between 600 to 700 lines. 

You are creating a detailed implementation plan that ANOTHER AGENT will execute without seeing this conversation. The plan must be completely self-contained with explicit file paths, exact code patterns, and unambiguous steps.

**The test:** Could a developer who knows nothing about this feature implement it from the plan alone? If yes, an agent can too.

## PROCESS

### 1. Understand the feature

- Architecture rules and conventions are loaded via `@CLAUDE.md` above
- Product context is loaded via `@reference/PRD.md` above
- Read `reference/mvp-tool-designs.md` if the feature relates to agent tools
- **If this is an AI agent tool:** flag it as tool planning (see "Agent Tool Planning" section below)
- Explore existing features under `app/` to understand established patterns
- Read `app/main.py` to see current router registrations

### 2. Research existing code

- Identify which existing modules this feature will interact with
- Check `app/shared/` for reusable utilities (TimestampMixin, PaginationParams, PaginatedResponse, ErrorResponse, get_db(), get_logger())
- Find similar features and note **exact file paths with line ranges** for patterns the executing agent must follow
- Check `alembic/versions/` for unapplied or recent migrations that could conflict
- Check `pyproject.toml` for existing dependencies; note any new packages needed (`uv add` commands)
- Check `.env.example` for current env vars; note if the feature needs new ones
- Identify existing features that might need changes when this feature is added (cross-feature impact)
- Research any external libraries/APIs needed — capture documentation URLs with specific sections

### 3. Agent Tool Planning (if applicable)

> **NOTE: This is tool planning for an AI agent.** Tools are functions that an LLM calls during autonomous workflows. Their docstrings, parameter design, and error handling are optimized for machine consumption, not human developers.

If the feature involves agent tools (detected by keywords: tool, agent, MCP, Obsidian tool, transit tool, or if `mvp-tool-designs.md` has a matching spec), apply these additional requirements:

**Read first:**
- `mvp-tool-designs.md` — check if a tool spec already exists for this feature
- CLAUDE.md "Tool Docstrings for Agents" section — the 5 key principles

**Tool-specific design considerations:**
- **Agent-optimized docstrings** — every tool function must include:
  1. When to use this tool (selection guidance)
  2. When NOT to use it (prevent misuse)
  3. Parameter efficiency tips (avoid token waste)
  4. Expected output format and size
  5. Composition hints (what tools to chain before/after)
- **Dry-run support** — tools should accept a `dry_run: bool` parameter that returns what WOULD happen without side effects
- **Token efficiency** — tool responses should be concise and structured; avoid returning large unfiltered payloads
- **Error messages for LLMs** — errors should be actionable ("File not found at X, try listing directory Y first" not just "404")
- **Idempotency** — tools should be safe to retry without side effects where possible

**Tool-specific task order:**
1. Define Pydantic schemas in `schemas.py`
2. Implement tool with structured logging and type hints
3. Register tool with Pydantic AI agent
4. Create unit tests in `app/[feature]/tests/`
5. Add integration tests if needed

**Plan template additions for tools:**
- Add a "Tool Interface" section with function signature, parameter descriptions, and example calls
- Add a "Composition" section showing how this tool fits into multi-step agent workflows
- Add a "Dry-Run Behavior" section if applicable

### 4. Design the vertical slice

Plan the complete feature following VTV's vertical slice structure:
- `app/[feature]/models.py` — SQLAlchemy models inheriting `Base` and `TimestampMixin`
- `app/[feature]/schemas.py` — Pydantic schemas for request/response
- `app/[feature]/routes.py` — FastAPI router with typed endpoints. **Every endpoint MUST have `get_current_user` or `require_role()` dependency** — `TestAllEndpointsRequireAuth` in `app/tests/test_security.py` auto-discovers all routes and fails CI if any lack auth. Only explicitly allowlisted public endpoints (login, health) are exempt.
- `app/[feature]/service.py` — Business logic with structured logging
- `app/[feature]/tests/` — Unit and integration tests

### 5. Write the plan

Create the plan file at `.agents/plans/[feature-name].md` using this template:

```markdown
# Plan: [Feature Name]

## Feature Metadata
**Feature Type**: [New Capability / Enhancement / Refactor / Bug Fix]
**Estimated Complexity**: [Low / Medium / High]
**Primary Systems Affected**: [list]

## Feature Description

[2-3 paragraphs: what this feature does, the problem it solves, and user-facing behavior. Be specific about system impact.]

## User Story

As a [specific type of user]
I want to [specific action/capability]
So that [specific benefit/outcome]

## Solution Approach

[2-3 paragraphs describing the technical approach and why we chose it.]

**Approach Decision:**
We chose [approach] because:
- [Reason 1]
- [Reason 2]

**Alternatives Considered:**
- [Alternative 1]: Rejected because [reason]
- [Alternative 2]: Rejected because [reason]

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, logging patterns, type checking requirements
- `[file-path]` (lines X-Y) — [why relevant, what pattern to learn from it]

### Similar Features (Examples to Follow)
- `[file-path]` (lines X-Y) — [specific pattern demonstrated that should be replicated]

### Files to Modify
- `app/main.py` — Register [feature]_router

## Research Documentation

Use these resources for implementation guidance:

- [Documentation Title](https://url.com/path#anchor)
  - Section: [specific section name]
  - Summary: [what to learn — 1-2 sentences]
  - Use for: [which implementation step needs this]

## Implementation Plan

### Phase 1: Foundation
[What foundational work must happen first — schemas, types, shared utilities, new dependencies]

### Phase 2: Core Implementation
[Main feature implementation — business logic, routes, database models]

### Phase 3: Integration & Validation
[Integration with existing features, testing, validation]

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.
Create one task per file — each task targets exactly one file path.
Use action keywords: CREATE, UPDATE, ADD, REMOVE, REFACTOR, MIRROR

**Schema Impact Tracing:** For any task that adds validators to existing schemas or removes/renames response fields, include a sub-step: "Grep for `SchemaName(` and update all constructors and test assertions." See Known Pitfalls #58-59.

**Import Completeness:** Every code change in a task that adds a function call (e.g., `logger.warning(...)`, `get_redis()`) MUST also specify the required import if it's not already present in the file. Don't assume imports exist — check the file first, include the import in the task.

**Plan Code Quality:** Code snippets included in tasks must follow project lint rules. No `except Exception: pass` (violates Ruff S110 — always include `logger.warning()`). No missing imports. No patterns that the executor would copy verbatim and then fail validation.

CRITICAL: Every task MUST include a **Per-task validation** block with ALL applicable checks in this order:
1. `uv run ruff format [file path]` — auto-format (ALWAYS include)
2. `uv run ruff check --fix [file path]` — lint + auto-fix (ALWAYS include; `--fix` resolves import sorting I001 which `ruff format` does NOT handle)
3. `uv run mypy [file path]` — type check (for all non-test .py files)
4. `uv run pyright [file path]` — type check (when strict typing is critical)
5. `uv run pytest [test path] -v` — run tests (for test files only)
Never omit linting from per-task validation. Every file gets formatted and lint-checked.

### Task 1: [Foundational Task Name]
**File:** `[exact/path/to/file.py]` (create new)
**Action:** CREATE

Create [schema/model/utility]:
- Define [Specific class name] with:
  - `field_name: Type` — [purpose and validation rules]
  - `field_name: Type` — [purpose and validation rules]
- Include Google-style docstring
- All fields have type annotations
- Follow pattern from: `[reference-file.py]` (lines X-Y)

**Per-task validation:**
- `uv run ruff format [exact file path]`
- `uv run ruff check --fix [exact file path]` passes
- `uv run mypy [exact file path]` passes with 0 errors

---

### Task 2: [Implementation Task Name]
**File:** `[exact/path/to/file.py]` (create new OR modify existing)
**Action:** CREATE / UPDATE

Implement [specific function/class]:
- Function signature: `async def function_name(param: Type) -> ReturnType:`
- Use [Specific model] from Task 1
- Add structured logging:
  - `logger.info("[feature].action_started", **context)`
  - `logger.info("[feature].action_completed", **context)`
  - `logger.error("[feature].action_failed", exc_info=True, error=str(e), error_type=type(e).__name__)`
- Follow pattern from: `[reference-file.py]` (lines X-Y)

**Per-task validation:**
- `uv run ruff format [exact file path]`
- `uv run ruff check --fix [exact file path]` passes
- `uv run mypy [exact file path]` passes

---

### Task N-1: [Testing Task Name]
**File:** `app/[feature]/tests/test_[module].py` (create new)
**Action:** Create

**Test 1: Happy path**
```python
async def test_[feature]_success():
    # Test successful execution with valid input
    # Assert expected behavior
```

**Test 2: Edge case — [specific case]**
```python
async def test_[feature]_[edge_case]():
    # Test [specific edge case]
    # Assert proper handling
```

**Test 3: Error case — [specific error]**
```python
@pytest.mark.integration
async def test_[feature]_[error_case]():
    # Test error handling for [specific error]
    # Assert proper exception raised
```

**Per-task validation:**
- `uv run ruff format app/[feature]/tests/test_[module].py`
- `uv run ruff check --fix app/[feature]/tests/test_[module].py` passes
- `uv run pytest app/[feature]/tests/ -v` — all tests pass

---

### Task N: Register Router & Final Integration
**File:** `app/main.py`
**Action:** UPDATE

Add:
```python
from app.[feature].routes import router as [feature]_router
app.include_router([feature]_router)
```

---

## Migration (if applicable)

**If database is running:**
```bash
uv run alembic revision --autogenerate -m "[description]"
uv run alembic upgrade head
```

**If database is NOT running (fallback):** Create migration manually. Specify column types, nullable flags, and foreign keys below so the executing agent can write `op.add_column()` / `op.create_table()` calls by hand:
- [Column 1]: `type`, nullable=[yes/no], default=[value]
- [Column 2]: `type`, nullable=[yes/no]

## Logging Events

- `[feature].action_started` — [when emitted]
- `[feature].action_completed` — [when emitted, include what metrics]
- `[feature].action_failed` — [when emitted, include error context]

## Testing Strategy

### Unit Tests
**Location:** `app/[feature]/tests/test_[module].py`
- [Component 1] — [what to test]
- [Component 2] — [what to test]

### Integration Tests
**Location:** `app/[feature]/tests/test_[module].py`
**Mark with:** `@pytest.mark.integration`
- [Integration point] — [what to test]

### Edge Cases
- [Edge case 1] — [expected behavior]
- [Edge case 2] — [expected behavior]
- Empty/null inputs — [expected behavior]

## Acceptance Criteria

This feature is complete when:
- [ ] [Specific, measurable criterion 1]
- [ ] [Specific, measurable criterion 2]
- [ ] All type checkers pass (mypy + pyright)
- [ ] All tests pass (unit + integration)
- [ ] Structured logging follows `domain.component.action_state` pattern
- [ ] No type suppressions added
- [ ] Router registered in `app/main.py`
- [ ] No regressions in existing tests

## Completion Checklist

Before marking this plan as fully executed:
- [ ] All tasks completed in order
- [ ] Per-task validations passed
- [ ] Full validation pyramid passed (Levels 1-4)
- [ ] No deviations from plan (or deviations documented with reasons)
- [ ] Ready for `/commit`

## Final Validation (5-Level Pyramid)

Run each level in order — every one must pass with 0 errors:

**Level 1: Syntax & Style**
```bash
uv run ruff format .
uv run ruff check --fix .
```

**Level 2: Type Safety**
```bash
uv run mypy app/
uv run pyright app/
```

**Level 3: Unit Tests (feature-specific)**
```bash
uv run pytest app/[feature]/tests/ -v
```

**Level 4: Full Test Suite (unit)**
```bash
uv run pytest -v -m "not integration"
```

**Level 5: Server Validation (if Docker running)**
```bash
curl -s http://localhost:8123/health
```

**Success definition:** Levels 1-4 exit code 0, all tests pass, zero errors or warnings. Level 5 optional.

## Dependencies

- Shared utilities used: [list from app/shared/]
- Core modules used: [list from app/core/]
- New dependencies: [any new packages — include `uv add [package]` commands]
- New env vars: [any new environment variables — include `.env.example` updates]

## Known Pitfalls

The executing agent MUST follow these rules to avoid common errors:

1. **No `assert` in production code** — Ruff S101 forbids assert outside test files. Use conditional checks instead.
2. **No `object` type hints** — Import and use actual types directly. Never write `def f(data: object)` then isinstance-check.
3. **Untyped third-party libraries** — When adding a dependency without `py.typed`:
   - mypy: Add `[[tool.mypy.overrides]]` with `ignore_missing_imports = true`
   - pyright: Add file-level `# pyright: reportUnknown...=false` directives to the ONE file interfacing with the library
   - **NEVER** use pyright `[[executionEnvironments]]` with a scoped `root` — it breaks `app.*` import resolution
4. **Mock exceptions must match catch blocks** — If production code catches `httpx.HTTPError`, tests must mock `httpx.ConnectError` (or another subclass), not bare `Exception`.
5. **No unused imports or variables** — Ruff F401 catches unused imports, Ruff F841 catches unused local variables. Don't write speculative code — only import/assign what you actually use.
6. **No unnecessary noqa/type-ignore** — Ruff RUF100 flags unused suppression comments.
7. **Test helper functions need return type annotations** — mypy `disallow_untyped_defs=false` for tests only relaxes *defining* untyped functions, but `disallow_untyped_call` is still globally true. When `async def test_foo()` (implicitly typed via coroutine return) calls an untyped helper, mypy raises `no-untyped-call`. Fix: always add `-> ReturnType` to test helpers (e.g., `def _make_ctx() -> MagicMock:`).
8. **No EN DASH in strings** — Ruff RUF001 forbids ambiguous Unicode characters like `–` (EN DASH, U+2013). LLMs naturally generate these in time ranges ("05:00–13:00") and prose. Always use `-` (HYPHEN-MINUS, U+002D): `"05:00-13:00"`, `"trainee - supervised only"`.
9. **Pydantic AI `ctx` parameter must be referenced** — Ruff ARG001 flags unused function arguments. Tool functions require `ctx: RunContext[TransitDeps]` even when mock implementations don't need it. Always reference it: `_settings = ctx.deps.settings` and use in logging or guards.
10. **Narrow dict value types before passing to Pydantic** — When extracting values from `dict[str, str | list[str] | None]`, the union type is too broad for Pydantic fields expecting `str | None`. Use isinstance narrowing with walrus operator: `phone=str(val) if isinstance(val := d.get("phone"), str) else None`.
11. **Schema field additions break ALL consumers** — When adding a required field to a Pydantic `BaseModel`, the plan MUST include tasks to update every file that constructs that model (test helpers, mock factories, route tests). Search for `ModelName(` across the codebase during planning. Also ensure test mocks return realistic objects — if production code accesses `mock.routes.get(id).route_type`, the mock must have a real dict with proper objects, not a generic `MagicMock`.
12. **Untyped library decorators need a 3-layer fix** — When planning to add an untyped lib (e.g., slowapi), the plan MUST include ALL THREE layers in the SAME task: (a) mypy `[[overrides]]` with `ignore_missing_imports`, (b) pyright file-level directives on EVERY file using the decorator, (c) ruff per-file-ignores for ARG001 if the lib forces unused params. Missing any layer causes a validation failure.
13. **Test module setup must respect import ordering** — If tests need module-level setup like `limiter.enabled = False`, the plan must specify: all imports FIRST, then the setup line. Ruff E402 flags imports after non-import statements.
14. **No `type: ignore` in test files** — mypy relaxes typing for tests. Adding `# type: ignore[arg-type]` becomes "unused ignore". Plan should specify pyright file-level directives instead.
15. **Pydantic field constraints on shared models affect ALL code paths** — When planning size/length constraints, specify them on the REQUEST model (via `field_validator`), NOT on shared message/response models used by both input and output.
16. **Singleton close must handle closed event loops** — When planning singleton patterns with lifespan cleanup, include `try/except RuntimeError: pass` in close functions. TestClient closes the event loop before lifespan shutdown.
17. **`verify=False` needs `# noqa: S501`** — Ruff S501 flags `httpx.AsyncClient(verify=False)`. When SSL verification is intentionally disabled (e.g., Obsidian self-signed cert), plan must include `# noqa: S501` on the same line with a comment explaining why.
18. **ARG001 applies to ALL unused function params, not just `ctx`** — Any function parameter not used in the body triggers ARG001. For params validated elsewhere (e.g., `recursive` validated in caller but unused in helper), plan must specify `_ = param_name` with a comment. Rule #9 covers `ctx` specifically, but this applies to every unused param.
19. **`dict.get()` returns the full union type — use walrus for isinstance narrowing** — `isinstance(d.get("key"), int)` narrows the `.get()` return but NOT a subsequent `d["key"]` access. Plan must specify walrus operator pattern: `val if isinstance(val := d.get("key"), int) else None`. Also for sort key lambdas: `key=lambda r: str(r.get("title", ""))` — always wrap `.get()` in `str()` for sort keys.
20. **NEVER use `replace_all: true` to remove end-of-line comments** — The Edit tool's `replace_all` can silently collapse lines when removing `# type: ignore` or `# noqa` comments at line endings. Plan should note: always use targeted single edits to remove inline comments, or replace the entire line including the newline.
21. **Clear mypy cache after renaming type aliases** — When renaming a type (e.g., `TransitDeps` to `UnifiedDeps` with `TransitDeps = UnifiedDeps` alias), mypy's incremental cache confuses TypeAlias with TypeInfo and crashes. Plan must include `rm -rf .mypy_cache` step after any type alias refactoring.
22. **Dict literal types must match function param types exactly (invariance)** — In tests, `{"key": "value"}` is inferred as `dict[str, str]` which is NOT compatible with `dict[str, str | list[str] | None]` due to dict invariance. Plan must specify explicit type annotations on dict literals in tests when passing to functions with union-valued dict params.
23. **Lazy-loaded untyped lib models use `Any`, not `object`** — When planning lazy-loaded models from untyped libraries (e.g., sentence-transformers), plan must specify `Any | None` for the field type, not `object | None`. The `object` type blocks method calls (`.encode()`, `.predict()`) causing mypy `attr-defined`, while `# type: ignore` triggers `unused-ignore`. Plan must also specify `# noqa: ANN401` on any `-> Any` helper methods.
24. **Dataclass `field(default_factory=dict)` needs typed lambda** — Pyright infers `dict[Unknown, Unknown]` from bare `dict`. Plan must specify typed lambdas: `field(default_factory=lambda: dict[str, str | int | None]())`.
25. **Untyped lib method returns need `str()` wrapping** — Methods on objects from untyped libs (fitz `page.get_text()`, pytesseract `image_to_string()`) return `Unknown`. Plan must specify `str()` wrapping: `text = str(page.get_text())` to satisfy pyright.
26. **Partially annotated test functions need `-> None`** — Adding a type annotation to a pytest fixture parameter (e.g., `tmp_path: Path`) without a return type triggers mypy `no-untyped-def` (partially typed function). Plan must always specify both param type AND `-> None` return type when any test function parameter is annotated.
27. **Pydantic `Field(None, ...)` confuses pyright about required params** — Pyright doesn't understand that `Field(None, description="...")` sets a default. Plan must specify explicitly passing all `Field(None)` params in test fixtures: `MyModel(required="x", optional=None)`.
28. **Bare `[]` list literals inferred as `list[Unknown]`** — Pyright `reportUnknownMemberType` fires on `.append()` when the list has no type annotation. Plan must specify explicit type annotations on list variables: `items: list[MagicMock] = []` not `items = []`. Same pattern as rule #24 for dicts.
29. **Adding optional fields to existing Pydantic schemas breaks ALL constructors** — When the plan adds `Field(None, ...)` to an existing schema, the plan MUST include a task to grep for `SchemaName(` across the entire codebase and update ALL constructors — test fixtures in `conftest.py`, route handlers, service calls, and inline test constructions. Pyright treats `Field(None)` as NOT providing a default, so every call site needs explicit params. This is rule #27 applied proactively at the planning stage. The task that adds the schema field and the task that updates all consumers MUST be the same task or immediately adjacent.
30. **Existing tests break when new types are added** — When the plan adds support for a new document type, file format, or enum value, the plan MUST include updating any tests that assert on "unsupported" or "unknown" types. Example: adding xlsx support breaks `test_unsupported_type_raises("xlsx")`. Include these test updates in the same task that adds the new type.
31. **`@computed_field` on `@property` needs `# type: ignore[prop-decorator]`** — mypy errors with "Decorators on top of @property are not supported" when Pydantic's `@computed_field` is stacked on `@property`. Plan must specify `# type: ignore[prop-decorator]` on the `@computed_field` line whenever this pattern is used.
32. **Don't guess `# type: ignore` codes — validate then add** — Plan must NOT include speculative `# type: ignore[code]` or `# noqa:` comments. mypy's `unused-ignore` rule flags every wrong guess. Plan should instruct: write code WITHOUT ignores, run mypy, read the exact error code, THEN add the precise ignore. If the plan can't predict the exact mypy code, omit the ignore and let per-task validation reveal the correct one.
33. **`dict[str, object]` fails Pydantic `**kwargs` unpacking** — When planning JSON parsing into dicts that feed Pydantic constructors (`Model(**f)`), plan must specify `dict[str, Any]` with `from typing import Any`, NOT `dict[str, object]`. Pyright rejects `object` values for typed `str` parameters.
34. **Redis async client stubs: `await` returns `Awaitable[T] | T`** — The `redis` package has partial type stubs. Plan must specify: `# type: ignore[misc]` on `await redis_client.ping()`, `await redis_client.smembers()`, and similar calls. Plan must also specify pyright file-level directive: `# pyright: reportUnknownMemberType=false, reportMissingTypeStubs=false` on files using Redis. For `smembers()` results, also add `reportUnknownArgumentType=false, reportUnknownVariableType=false`.
35. **`redis.pipeline()` is SYNC, not async** — `Redis.pipeline()` returns a `Pipeline` object synchronously. Plan must specify: in tests, mock Redis with `MagicMock()` (not `AsyncMock()`), then set `mock_pipe.execute = AsyncMock()` since only `execute()` is async. Using `AsyncMock()` for Redis makes `pipeline()` return a coroutine, breaking `pipe.set()` calls.
36. **Lazy imports inside `if` blocks break `@patch` targets** — When the plan uses lazy imports (e.g., `if enabled: from module import func`), the test tasks must patch the ORIGINAL module (`@patch("app.module.func")`), NOT the importing module's namespace. The name doesn't exist at module level when lazily imported.
37. **Bare `except: pass` violates Ruff S110** — Plan must specify `logger.debug(...)` in every except block, never bare `pass`. The one exception is `except asyncio.CancelledError: pass` which Ruff allows.
38. **Background asyncio tasks must handle ALL exceptions in `stop_*()`** — When planning background task lifecycle (`start_*/stop_*`), plan must specify: (a) `stop_*` catches both `CancelledError` and `Exception` separately when awaiting tasks, (b) `start_*` wraps service connections (Redis, DB) in try/except so unavailability doesn't crash app startup, (c) task `run()` methods wrap I/O operations in try/except to prevent unhandled exceptions from silently terminating tasks.
39. **`from datetime import date` shadows field names named `date`** — In models/schemas with a field called `date` (e.g., `CalendarDate.date`), importing `from datetime import date` causes pyright to confuse the field name with the type. Plan must specify `import datetime` and reference as `datetime.date` / `datetime.datetime` when ANY model/schema in the file has a field named `date` or `datetime`.
40. **FastAPI `Query(None)` needs `# noqa: B008`** — Just like `Depends()`, `Query()` is a function call in argument defaults. Ruff B008 flags all of these. Plan must specify `# noqa: B008` on lines using `Query(...)` in FastAPI route function signatures.
41. **ILIKE search params must escape wildcards** — Any repository method using `f"%{search}%"` in `.ilike()` must use `escape_like()` from `app.shared.utils`. Plan must specify `from app.shared.utils import escape_like` and `f"%{escape_like(search)}%"` pattern.
42. **File uploads must enforce size limits in application code** — Middleware `Content-Length` checks are bypassable. Plan must specify streaming reads with `while chunk := await file.read(8192)` and a running byte counter that raises `HTTPException(413)` on overflow.
43. **User-provided filenames must be regex-sanitized** — Plan must specify `re.sub(r"[^\w\-.]", "_", filename)` AND `stored_path.resolve().is_relative_to(storage_dir.resolve())` validation before writing to disk.
44. **Never log URLs that may contain credentials** — Redis URLs, database URLs, and API endpoints may embed passwords. Plan must specify a `_redact_url()` helper using `urllib.parse.urlparse` to mask passwords before logging.
45. **Rate limiter must use X-Real-IP, not X-Forwarded-For** — `X-Forwarded-For` is client-spoofable. Only `X-Real-IP` (set by nginx) is trustworthy. Plan must specify `request.headers.get("X-Real-IP")` in rate limiting key functions.
46. **Docker credentials must use env var interpolation** — Never hardcode `POSTGRES_PASSWORD: postgres` in docker-compose. Plan must specify `${POSTGRES_PASSWORD:-postgres}` syntax for all database credentials.
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
52. **Empty PATCH bodies must be rejected** — Add `@model_validator(mode="before")` with `@classmethod` to reject
    updates where all fields are None. Use `mode="before"` (not `"after"`) so validation runs before Pydantic parsing. Pattern: `if isinstance(data, dict) and not any(v is not None for v in data.values()): raise ValueError("At least one field must be provided")`. Plan must include corresponding test cases for empty dict AND all-None dict.
53. **Content-Length must be parsed defensively** — `int(content_length)` raises ValueError on
    malformed headers. Always wrap in try/except.
54. **Constrained string fields must use `Literal[...]`** — When a field only accepts a fixed set of values (priority, status, category, role), define a `TypeAlias = Literal["val1", "val2", ...]` and use it as the field type instead of bare `str`. This gives Pydantic validation for free and produces TypeScript union types on the frontend. Plan must include the type alias definition and use it in both Create and Update schemas.
55. **FastAPI `HTTPBearer(auto_error=True)` returns 403, not 401** — The default `HTTPBearer()` returns 403 when the Authorization header is missing (FastAPI framework design), but RFC 7235 requires 401 for missing authentication. Plan must specify `HTTPBearer(auto_error=False)` and a manual check that raises `HTTPException(status_code=401, detail="Not authenticated", headers={"WWW-Authenticate": "Bearer"})` when credentials are `None`.
56. **`app.dependency_overrides` is global and leaks between test modules** — FastAPI's `dependency_overrides` dict lives on the shared global `app` object. If one test module sets `app.dependency_overrides[get_current_user] = mock_user`, that override persists into ALL subsequent test modules in the same pytest session. Plan must include a pytest fixture that saves, clears, and restores overrides: `saved = app.dependency_overrides.copy(); app.dependency_overrides.clear(); yield; app.dependency_overrides = saved`. Apply this fixture to any test module that manipulates `dependency_overrides`.
57. **Never expose role names or permission details in authorization error messages** — Error messages like `"Requires one of roles: admin, editor"` leak internal authorization structure to attackers. Plan must specify generic messages for all 403 responses: `"Insufficient permissions"`. The HTTP status code already communicates "forbidden" — the detail should NOT enumerate allowed roles, scopes, or permissions.
58. **Adding validators to existing schemas can reject previously-valid data** — When a plan adds `@field_validator` to an existing Pydantic schema, the planner MUST trace ALL code paths that construct or submit data through that schema:
    - **INPUT schemas (login, search, filter):** Existing stored data or user credentials must still pass. Password complexity goes on `PasswordResetRequest`/`RegisterRequest`, NEVER on `LoginRequest` — existing users with weak passwords get 422 at login.
    - **UPDATE schemas (PATCH endpoints):** Existing records being re-saved must still validate.
    - **Grep for `SchemaName(` across the codebase** to find all constructors (tests, conftest, services, routes).
    - **Ask: "Will this validator reject data that already exists in production?"** If yes, the validator belongs on a different schema (creation/reset, not submission/login).
    - Plan must also include updating ALL test files that construct the schema with data that would fail the new validator.
59. **Tasks that remove or rename response fields must update downstream tests** — When a plan task removes a field from a response dict, renames a schema field, or changes response shape, the SAME task (or an immediately adjacent task) MUST include: grep for the old field name across `app/*/tests/` and `app/tests/`, then update or remove all assertions on that field. Health endpoint redaction, version info removal, and similar changes always break tests that assert on the old response structure.

## Migration (if applicable)

**Prefer autogenerate when database is running:**
```bash
uv run alembic revision --autogenerate -m "[description]"
uv run alembic upgrade head
```

**When database may not be running:** The plan MUST note that manual migration creation is an acceptable fallback. Include the column types, nullable flags, and foreign keys needed so the executing agent can write the migration by hand if `--autogenerate` fails due to no database connection.

## Notes

[Any additional context: future considerations, known limitations, performance implications, security considerations]

## Pre-Implementation Checklist

The executing agent MUST verify before writing any code:
- [ ] Read all files listed in "Relevant Files" section
- [ ] Reviewed research documentation
- [ ] Understood the solution approach and why alternatives were rejected
- [ ] Clear on task execution order
- [ ] Validation commands are executable in this environment
```

## OUTPUT

1. Save the plan to `.agents/plans/[feature-name].md` (use kebab-case for the filename)
2. Report to the user:
   - Plan file location
   - Summary of what will be created
   - Number of new files and modified files
   - Any architectural decisions made and why (including alternatives rejected)
   - To execute: `/be-execute .agents/plans/[feature-name].md`
