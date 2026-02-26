# Python Anti-Patterns — Avoid These

These rules prevent common lint/type errors in the VTV codebase. Write correct code on first pass.

1. **No `assert` in production code** — Ruff S101. Use `if x is not None:` not `assert x is not None`
2. **No `object` type hints** — Import and use actual types. Never write `def f(data: object)` then isinstance-check
3. **Untyped third-party libraries** — Use mypy `[[overrides]]` + pyright file-level `# pyright:` directives. NEVER use pyright `[[executionEnvironments]]` with scoped `root` — it breaks `app.*` import resolution
4. **Mock exceptions must match catch blocks** — If code catches `httpx.HTTPError`, test with `httpx.ConnectError`, not `Exception`
5. **No unused imports or variables** — Ruff F401 catches unused imports, Ruff F841 catches unused local variables. Don't import or assign speculatively — only write what you actually use
6. **No unnecessary noqa/type-ignore** — Ruff RUF100 flags unused suppression comments
7. **Test helper functions need return type annotations** — mypy `disallow_untyped_defs=false` for tests only relaxes *defining* untyped functions, but `disallow_untyped_call` is still globally true. When `async def test_foo()` calls an untyped helper, mypy raises `no-untyped-call`. Fix: always add `-> ReturnType` to test helpers
8. **No EN DASH in strings** — Ruff RUF001 forbids ambiguous Unicode like `–` (U+2013). Always use `-` (U+002D)
9. **Pydantic AI `ctx` parameter must be referenced** — Ruff ARG001 flags unused function arguments. Always reference it: `_settings = ctx.deps.settings`
10. **Narrow dict value types before passing to Pydantic** — Use isinstance narrowing with walrus operator: `phone=str(val) if isinstance(val := d.get("phone"), str) else None`
11. **Schema field additions break ALL consumers** — When adding a required field to a Pydantic `BaseModel`, you MUST update every file that constructs that model. Search with `Grep` for `ModelName(` across the codebase before editing. Also update mock objects that return the model's source data.
12. **Untyped library decorators need a 3-layer fix on FIRST PASS** — When adding an untyped lib: (a) mypy `[[overrides]]` with `ignore_missing_imports`, (b) pyright file-level directives on EVERY file using the decorator, (c) ruff per-file-ignores for ARG001 if the lib forces unused params. All three layers must be done simultaneously.
13. **`limiter.enabled = False` in tests must come AFTER all imports** — Ruff E402 flags module-level imports placed after non-import statements.
14. **Don't add `type: ignore` in test files** — mypy relaxes typing for tests. Adding `# type: ignore[arg-type]` becomes "unused ignore". Use pyright file-level directives instead.
15. **Pydantic field constraints on shared models affect ALL code paths** — `max_length=4000` on `ChatMessage.content` blocks both input AND output. Move input-only validation to a `field_validator` on the REQUEST model.
16. **Singleton close must handle closed event loops** — TestClient shuts down the event loop before lifespan cleanup. Wrap `await client.aclose()` in `try/except RuntimeError: pass`.
17. **`verify=False` needs `# noqa: S501`** — When SSL verification is intentionally disabled, add `# noqa: S501` with a comment explaining why.
18. **ARG001 applies to ALL unused function params, not just `ctx`** — Any unused parameter triggers ARG001. Add `_ = param_name` with a comment.
19. **`dict.get()` returns the full union type — use walrus for isinstance narrowing** — `isinstance(d.get("key"), int)` narrows `.get()` but NOT subsequent `d["key"]`. Fix: `val if isinstance(val := d.get("key"), int) else None`
20. **NEVER use `replace_all: true` to remove end-of-line comments** — The Edit tool's `replace_all` can silently collapse lines. Always use targeted single edits.
21. **Clear mypy cache after renaming type aliases** — Always run `rm -rf .mypy_cache` after type alias refactoring.
22. **Dict literal types must match function param types exactly (invariance)** — In tests, add explicit type annotations: `fm: dict[str, str | list[str] | int | float | bool | None] = {"key": "value"}`
23. **Lazy-loaded untyped lib models use `Any`, not `object`** — Use `Any | None` and `# noqa: ANN401` on `-> Any` helper methods.
24. **Dataclass `field(default_factory=dict)` needs typed lambda** — Use `field(default_factory=lambda: dict[str, str | int | None]())`.
25. **Untyped lib method returns need `str()` wrapping** — `text = str(page.get_text())` satisfies pyright.
26. **Partially annotated test functions need `-> None`** — Adding a type annotation to any parameter without a return type triggers mypy `no-untyped-def`.
27. **Pydantic `Field(None, ...)` confuses pyright about required params** — Always pass all `Field(None)` params explicitly in constructors.
28. **Bare `[]` list literals inferred as `list[Unknown]`** — Always annotate: `items: list[MagicMock] = []`.
29. **Adding optional fields to existing Pydantic schemas breaks ALL constructors** — Grep for `SchemaName(` and update ALL call sites in the SAME step.
30. **Existing tests break when new types are added** — Update tests that assert on "unsupported" types in the same step.
31. **`@computed_field` on `@property` needs `# type: ignore[prop-decorator]`** — The ONE valid use of `type: ignore` in production code for this pattern.
32. **Don't guess `# type: ignore` codes — validate then add** — Write code WITHOUT ignores, run mypy, read the exact error code, THEN add.
33. **`dict[str, object]` fails Pydantic `**kwargs` unpacking** — Use `dict[str, Any]` with `from typing import Any`.
34. **Redis async client stubs: `await` returns `Awaitable[T] | T`** — Add `# type: ignore[misc]` on await lines. Add pyright file-level `reportUnknownMemberType=false, reportMissingTypeStubs=false`.
35. **`redis.pipeline()` is SYNC, not async** — Mock Redis with `MagicMock()`, not `AsyncMock()`. Only `execute()` is async.
36. **Lazy imports inside `if` blocks break `@patch` targets** — Patch the ORIGINAL module, not the importing module's namespace.
37. **Bare `except: pass` violates Ruff S110** — Always log in except blocks. Exception: `except asyncio.CancelledError: pass`.
38. **Background asyncio tasks must handle ALL exceptions in `stop_*()`** — Catch both `CancelledError` and `Exception` separately.
39. **`from datetime import date` shadows field names named `date`** — Use `import datetime` and `datetime.date` when ANY model has a `date` field.
40. **FastAPI `Query(None)` needs `# noqa: B008`** — Same as `Depends()`.
41. **ILIKE search params must escape wildcards** — Use `escape_like()` from `app.shared.utils`.
42. **File uploads must enforce size limits in application code** — Use `while chunk := await file.read(8192)` with a byte counter.
43. **User-provided filenames must be regex-sanitized** — `re.sub(r"[^\w\-.]", "_", filename)` + `.resolve().is_relative_to()` validation.
44. **Never log URLs that may contain credentials** — Use `_redact_url()` via `urllib.parse.urlparse`.
45. **Rate limiter must use X-Real-IP, not X-Forwarded-For** — X-Forwarded-For is client-spoofable.
46. **Docker credentials must use env var interpolation** — `${POSTGRES_PASSWORD:-postgres}` in docker-compose.
47. **GTFS time validation needs range check** — Regex is format-only. Add field_validator for minutes < 60, seconds < 60.
48. **Unique constraints for GTFS composite keys** — Add `__table_args__` with UniqueConstraint.
49. **Unknown file types must be rejected** — Return 415 Unsupported Media Type.
50. **Wrap error-path DB updates in try/except** — Cleanup DB calls must not mask original errors.
51. **Clean up stored files on processing failure** — Add cleanup in exception handler.
52. **Empty PATCH bodies must be rejected** — Add `@model_validator(mode="before")` with `@classmethod`. Use `mode="before"` so validation runs before Pydantic parsing.
53. **Content-Length must be parsed defensively** — Wrap `int(content_length)` in try/except.
54. **Constrained string fields must use `Literal[...]`** — Define `TypeAlias = Literal["val1", "val2", ...]` and use as field type.
55. **FastAPI `HTTPBearer(auto_error=True)` returns 403, not 401** — Use `HTTPBearer(auto_error=False)` + manual 401 with `WWW-Authenticate: Bearer`.
56. **`app.dependency_overrides` is global and leaks between test modules** — Use a fixture that saves, clears, yields, then restores overrides.
57. **Never expose role names in authorization error messages** — Use generic "Insufficient permissions".
58. **Adding validators to existing schemas can reject previously-valid data** — Trace ALL code paths. Password complexity on `PasswordResetRequest`, NEVER on `LoginRequest`.
59. **Tasks that remove or rename response fields must update downstream tests** — Grep for the old field name across `app/*/tests/` and `app/tests/` in the SAME step.
