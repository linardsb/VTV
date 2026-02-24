# Python Anti-Patterns

Avoid these — they cause lint/type errors. Referenced from root `CLAUDE.md`.

## Ruff Lint Rules

1. **No `assert` in production code** — Ruff S101 forbids assert outside test files. Use `if x is not None:` conditionals.
2. **Only import what you use** — Ruff F401 catches unused imports. Don't import `field` from dataclasses unless you call `field()`.
3. **No unnecessary noqa/type-ignore** — Ruff RUF100 flags unused suppression comments.
4. **No EN DASH in strings** — Ruff RUF001 forbids `–` (U+2013). LLMs generate these in time ranges and prose. Always use `-` (U+002D).
5. **Pydantic AI `ctx` must be referenced** — Ruff ARG001 flags unused args. Tool functions require `ctx: RunContext[...]` — always reference it (e.g., `_settings = ctx.deps.settings`).
6. **ARG001 applies to ALL unused params** — Not just `ctx`. Use `_ = param_name` for intentionally unused params.
7. **Test imports must precede module-level setup** — `limiter.enabled = False` after imports triggers Ruff E402. All `from ... import` lines first, then setup.
8. **`verify=False` needs `# noqa: S501`** — Ruff S501 flags `httpx.AsyncClient(verify=False)`.
9. **Bare `except: pass` violates Ruff S110** — Always log in except blocks. Only `CancelledError: pass` is allowed.
10. **FastAPI `Query(None)` needs `# noqa: B008`** — Same as `Depends()`, `Query()` is a function call in argument defaults.

## Type System (MyPy + Pyright)

11. **No `object` type hints** — Forces isinstance + assert chains. Import and use the actual type.
12. **Untyped third-party libraries** — When a dependency lacks `py.typed`:
    - mypy: `[[tool.mypy.overrides]]` with `ignore_missing_imports = true`
    - pyright: File-level `# pyright: reportUnknownVariableType=false` on the ONE interfacing file
    - **NEVER use pyright `[[executionEnvironments]]` with a scoped `root`** — breaks `app.*` import resolution
13. **Untyped lib decorators need 3-layer fix** — (a) mypy `[[overrides]]`, (b) pyright file-level directives on EVERY file using it, (c) ruff per-file-ignores for ARG001 if lib forces unused params. All three simultaneously.
14. **No `type: ignore` in test files** — mypy relaxes tests. `# type: ignore[arg-type]` becomes "unused ignore". Use pyright `# pyright: reportArgumentType=false` instead.
15. **Don't guess `# type: ignore` codes** — mypy's `unused-ignore` flags wrong guesses. Write code first, run mypy, add the EXACT error code.
16. **Partially annotated test functions need `-> None`** — Adding param type without return type triggers mypy `no-untyped-def`. Always: `def test_foo(param: Type) -> None:`.
17. **`@computed_field` on `@property` needs `# type: ignore[prop-decorator]`** — mypy doesn't support stacked decorators on `@property`.
18. **Redis async stubs: `await` returns `Awaitable[T] | T`** — Needs `# type: ignore[misc]` on await calls. Add pyright file-level `reportUnknownMemberType=false, reportMissingTypeStubs=false`.

## Pyright-Specific

19. **Narrow dict unions before Pydantic** — `dict[str, str | list[str] | None]` too broad for `str | None` fields. Use walrus: `str(val) if isinstance(val := d.get("key"), str) else None`.
20. **`dict.get()` returns full union — use walrus** — `isinstance(d.get("k"), int)` doesn't narrow. Use `val if isinstance(val := d.get("k"), int) else None`.
21. **Dataclass `field(default_factory=dict)` needs typed lambda** — Pyright infers `dict[Unknown, Unknown]`. Use `field(default_factory=lambda: dict[str, str | int | None]())`.
22. **Bare `[]` list literals inferred as `list[Unknown]`** — Pyright fires on `.append()`. Always annotate: `items: list[X] = []`.
23. **Dict literal invariance in tests** — `{"k": "v"}` inferred as `dict[str, str]`, not `dict[str, str | None]`. Add explicit annotations.
24. **Pydantic `Field(None)` confuses pyright about defaults** — Pass defaulted fields explicitly in tests: `Model(required="x", optional=None)`.
25. **`dict[str, object]` fails Pydantic `**kwargs`** — Use `dict[str, Any]` for dicts unpacked into Pydantic constructors.

## Untyped Library Patterns

26. **Lazy-loaded untyped lib models use `Any`, not `object`** — `object` blocks `.encode()`/`.predict()`. Use `Any | None` + `# noqa: ANN401`.
27. **Untyped lib method returns need `str()` wrapping** — `page.get_text()`, `pytesseract.image_to_string()` return `Unknown`. Wrap in `str()`.
28. **Lazy imports break `@patch` targets** — Patch the ORIGINAL module, not the lazily-importing module.

## Pydantic Gotchas

29. **Pydantic constraints on shared models affect all paths** — `max_length` on shared model blocks input AND output. Move input-only validation to `field_validator` on the REQUEST model.
30. **Adding optional fields to existing schemas breaks ALL constructors** — `Field(None)` confuses pyright. Grep for `SchemaName(` and update ALL call sites.
31. **Adding validators to input schemas can reject existing data** — `@field_validator` on `LoginRequest` password field rejects existing users with weak passwords (422 before auth service is reached). Password complexity goes on `PasswordResetRequest`/`RegisterRequest`, NEVER on `LoginRequest`. Always ask: "Will this validator reject data that already exists in production?"
32. **Removing response fields breaks downstream tests** — When redacting fields from health endpoints, version info, or any response dict, grep for the field name across `app/*/tests/` and `app/tests/` and update all assertions in the SAME step.

## Testing Gotchas

31. **Mock exceptions must match catch blocks** — If code catches `httpx.HTTPError`, mock with `httpx.ConnectError`, not `Exception`.
32. **Existing tests break when new types are added** — Adding support makes "unsupported type" tests fail. Update in the SAME step.
33. **`redis.pipeline()` is SYNC** — Mock Redis with `MagicMock()`, not `AsyncMock()`. Only `pipe.execute()` is async.

## Runtime Patterns

34. **Singleton close must catch RuntimeError** — TestClient closes event loop before lifespan cleanup. Wrap `await client.aclose()` in `try/except RuntimeError: pass`.
35. **Background tasks: `stop_*()` must catch ALL exceptions** — Failed tasks re-raise their error, not `CancelledError`. Also wrap `start_*()` connections in try/except.
36. **`from datetime import date` shadows field names** — In models/schemas with a field called `date`, use `import datetime` + `datetime.date`.

## SQLAlchemy Type Patterns

37. **`dict(result.all())` fails mypy** — `Sequence[Row[tuple[str, int]]]` is not `Iterable[tuple[str, int]]`. Use `{row[0]: row[1] for row in result.all()}`.
38. **`InstrumentedAttribute` is not `ColumnElement`** — MyPy doesn't see `Model.column` as `sa.ColumnElement[str]`. Import `from sqlalchemy.orm.attributes import InstrumentedAttribute` and type as `InstrumentedAttribute[str]`.
39. **`**dict[str, str | None]` unpacking into typed kwargs fails** — Dict invariance: mypy rejects `**config_dict` when constructor expects specific types. Pass keyword arguments explicitly instead of unpacking a dict.

## Security Patterns

40. **ILIKE search params must escape wildcards** — `f"%{search}%"` allows users to inject `%` and `_` wildcards for DoS or data enumeration. Always use `escape_like()` from `app.shared.utils`: `f"%{escape_like(search)}%"`.
41. **File uploads must enforce size limits in application code** — Middleware `Content-Length` checks are bypassable (chunked encoding, missing header). Stream with `while chunk := await file.read(8192)` and a running counter that raises `HTTPException(413)`.
42. **User-provided filenames must be regex-sanitized** — `Path(filename).name` strips directories but allows special chars. Always `re.sub(r"[^\w\-.]", "_", filename)` and validate with `stored_path.resolve().is_relative_to(storage_dir.resolve())`.
43. **Never log URLs that may contain credentials** — Redis/DB URLs may embed passwords. Use `urllib.parse.urlparse` to detect and mask passwords before logging.
44. **Rate limiter must use X-Real-IP, not X-Forwarded-For** — `X-Forwarded-For` is client-spoofable. Only `X-Real-IP` (set by nginx) is trustworthy for per-IP rate limiting.
45. **Docker credentials must use env var interpolation** — Never hardcode `POSTGRES_PASSWORD: postgres` in docker-compose. Use `${POSTGRES_PASSWORD:-postgres}` so production can override via env vars.
