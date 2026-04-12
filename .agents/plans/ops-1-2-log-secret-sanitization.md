# Plan: OPS-1.2 Structured-Log Secret Sanitization Filter

## Context

structlog is configured (`app/core/logging.py`) but has no global sensitive field redaction. An exception during LLM setup can surface with `exc_info=True` containing the config repr — which includes API keys — and it lands in GlitchTip. Redacting at the processor level is defense-in-depth regardless of which call site leaks.

## Security Context Assessment

- **CTX-INFRA** — Modifies core infrastructure (logging pipeline). No hardcoded credentials; processor must not introduce new secrets.
- **CTX-AUTH** — Redaction covers auth-related fields (`jwt_secret_key`, `authorization`, `token`, `refresh_token`, `cookie`). Security logging at error+ level must still function (redaction preserves event structure, only replaces values).

Other contexts (RBAC, FILE, AGENT, INPUT) are not triggered — no new endpoints, file handling, agent tools, or user-facing query parameters.

## Research Summary

### Current Processor Chain (`app/core/logging.py:100-109`)

```python
structlog.configure(
    processors=[
        add_request_id,                              # Line 102
        structlog.contextvars.merge_contextvars,      # Line 103
        structlog.processors.add_log_level,           # Line 104
        structlog.processors.TimeStamper(fmt="iso"),  # Line 105
        structlog.processors.StackInfoRenderer(),     # Line 106
        structlog.processors.format_exc_info,         # Line 107 — converts exc_info to "exception" string
        structlog.processors.JSONRenderer(),           # Line 108 — final serialization
    ],
    ...
)
```

**Insertion point:** Between `format_exc_info` (line 107) and `JSONRenderer` (line 108). At this point:
- All fields are populated (request_id, level, timestamp, stack_info)
- Exception tracebacks are already formatted as strings in the `"exception"` key
- We can both redact dict values AND regex-scrub the exception string

### Custom Processor Pattern (`app/core/logging.py:64-78`)

```python
def add_request_id(_logger: WrappedLogger, _method_name: str, event_dict: EventDict) -> EventDict:
```

Follow this exact signature for the new processor.

### Sensitive Fields (from `app/core/config.py` + user spec)

Config fields: `anthropic_api_key` (line 74), `google_api_key` (line 77), `groq_api_key` (line 80), `obsidian_api_key` (line 121), `embedding_api_key` (line 168), `jwt_secret_key` (line 128), `sentry_dsn` (line ~55).

### Existing Patterns

- Request ID validation with safe regex: `app/core/logging.py:32-33`
- Redis URL redaction: `app/core/redis.py` (`_redact_url()`)
- No existing log field redaction processor

## Test Landscape

### Existing Test Infrastructure

- **Primary test file:** `app/core/tests/test_logging.py` (246 lines, 14 tests)
- **Pattern:** `capsys` + `json.loads()` for JSON output validation
- **Processor testing:** Direct call with `(None, "info", event_dict)` signature
- **Fixture:** `reset_request_id` (autouse) clears context var
- **No conftest.py** at `app/core/tests/` — uses root fixtures
- **Security convention tests:** `app/tests/test_security.py` uses `inspect.getsource()` for source-level assertions

### Test Patterns to Follow

```python
# Direct processor testing (from test_logging.py:64-72)
event_dict: dict[str, str] = {"event": "test.event"}
result = add_request_id(None, "info", event_dict)
assert "request_id" in result

# JSON output testing (from test_logging.py:105-121)
setup_logging(log_level="INFO")
logger = get_logger("test")
logger.info("test.operation_started", key="value")
log_data = json.loads(capsys.readouterr().out.strip())
```

## Type Check Baseline

| Target | pyright | mypy |
|--------|---------|------|
| `app/core/logging.py` | 0 errors | 0 errors |
| `app/core/` | 0 errors | 0 errors |

## Files to Create/Modify

| Action | File | Purpose |
|--------|------|---------|
| UPDATE | `app/core/logging.py` | Add `SENSITIVE_KEYS`, `redact_sensitive()`, `_redact_exc_text()`, wire into processor chain |
| UPDATE | `app/core/tests/test_logging.py` | Add 8 unit tests for redaction |

## Implementation Steps

### Step 1: Add sensitive key set and redaction helpers to `app/core/logging.py`

Add after the `_SAFE_REQUEST_ID` regex (line 33), before `get_request_id()`:

```python
import re
from typing import Any

SENSITIVE_KEYS: frozenset[str] = frozenset({
    "api_key",
    "token",
    "authorization",
    "password",
    "groq_api_key",
    "google_api_key",
    "jina_api_key",
    "sentry_dsn",
    "jwt_secret_key",
    "secret",
    "refresh_token",
    "cookie",
    "set-cookie",
})

_REDACTED = "<redacted>"

_EXC_SECRET_PATTERNS = re.compile(
    r"(?:"
    r"(?:GROQ_API_KEY|GOOGLE_API_KEY|JINA_API_KEY|ANTHROPIC_API_KEY|"
    r"OBSIDIAN_API_KEY|EMBEDDING_API_KEY|JWT_SECRET_KEY|SENTRY_DSN"
    r")=\S+"
    r"|Authorization:\s*Bearer\s+\S+"
    r"|eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"
    r")",
    re.IGNORECASE,
)


def _redact_value(value: object) -> object:
    if isinstance(value, dict):
        return {k: _REDACTED if k.lower() in SENSITIVE_KEYS else _redact_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    return value


def _redact_exc_text(text: str) -> str:
    return _EXC_SECRET_PATTERNS.sub(_REDACTED, text)


def redact_sensitive(
    _logger: WrappedLogger, _method_name: str, event_dict: EventDict
) -> EventDict:
    for key in list(event_dict):
        if key.lower() in SENSITIVE_KEYS:
            event_dict[key] = _REDACTED
        else:
            event_dict[key] = _redact_value(event_dict[key])

    exc = event_dict.get("exception")
    if isinstance(exc, str):
        event_dict["exception"] = _redact_exc_text(exc)

    return event_dict
```

Then in `setup_logging()`, insert `redact_sensitive` between `format_exc_info` and `JSONRenderer`:

```python
structlog.processors.format_exc_info,
redact_sensitive,                          # NEW
structlog.processors.JSONRenderer(),
```

**Note on `typing.Any`:** The `_redact_value` helper uses `object` parameter type — this avoids needing `Any`. Dict/list isinstance narrowing handles the recursion. The return is `object` which is correct since we return either `_REDACTED` (str) or the original value.

**Validation:** `uv run ruff format app/core/logging.py && uv run ruff check --fix app/core/logging.py && uv run pyright app/core/logging.py && uv run mypy app/core/logging.py`

### Step 2: Add 8 unit tests to `app/core/tests/test_logging.py`

Append tests after the existing ones. Import `redact_sensitive`, `SENSITIVE_KEYS`, `_redact_exc_text` from `app.core.logging`.

```python
# --- Redaction tests ---

def test_redact_sensitive_top_level_key() -> None:
    event_dict: dict[str, object] = {"event": "test", "api_key": "sk-secret-123", "user": "alice"}
    result = redact_sensitive(None, "info", event_dict)
    assert result["api_key"] == "<redacted>"
    assert result["user"] == "alice"
    assert result["event"] == "test"

def test_redact_sensitive_nested_dict() -> None:
    event_dict: dict[str, object] = {"event": "test", "headers": {"authorization": "Bearer xyz", "content-type": "json"}}
    result = redact_sensitive(None, "info", event_dict)
    headers = result["headers"]
    assert isinstance(headers, dict)
    assert headers["authorization"] == "<redacted>"
    assert headers["content-type"] == "json"

def test_redact_sensitive_list_of_dicts() -> None:
    event_dict: dict[str, object] = {"event": "test", "items": [{"password": "secret", "name": "a"}, {"token": "t", "name": "b"}]}
    result = redact_sensitive(None, "info", event_dict)
    items = result["items"]
    assert isinstance(items, list)
    assert items[0]["password"] == "<redacted>"
    assert items[0]["name"] == "a"
    assert items[1]["token"] == "<redacted>"

def test_redact_sensitive_case_insensitive() -> None:
    event_dict: dict[str, object] = {"event": "test", "API_KEY": "secret", "Password": "abc"}
    result = redact_sensitive(None, "info", event_dict)
    assert result["API_KEY"] == "<redacted>"
    assert result["Password"] == "<redacted>"

def test_redact_exc_info_jwt() -> None:
    exc_text = 'File "config.py", line 10\n  token = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"\nValueError'
    result = _redact_exc_text(exc_text)
    assert "eyJ" not in result
    assert "<redacted>" in result
    assert "ValueError" in result

def test_redact_exc_info_bearer() -> None:
    exc_text = 'httpx.HTTPError: Authorization: Bearer sk-ant-api03-xxxx\nTraceback'
    result = _redact_exc_text(exc_text)
    assert "sk-ant" not in result
    assert "<redacted>" in result
    assert "Traceback" in result

def test_redact_sensitive_passthrough_non_sensitive() -> None:
    event_dict: dict[str, object] = {"event": "test.started", "duration_ms": 42, "status": "ok", "items": [1, 2, 3]}
    result = redact_sensitive(None, "info", event_dict)
    assert result["event"] == "test.started"
    assert result["duration_ms"] == 42
    assert result["status"] == "ok"
    assert result["items"] == [1, 2, 3]

def test_redact_sensitive_empty_dict() -> None:
    event_dict: dict[str, object] = {}
    result = redact_sensitive(None, "info", event_dict)
    assert result == {}
```

**Validation:** `uv run pytest app/core/tests/test_logging.py -v`

### Step 3: Add security convention test to `app/tests/test_security.py`

Add a test class verifying that `redact_sensitive` is in the processor chain (source inspection pattern matching existing `TestRedisUrlRedaction`):

```python
class TestLogSecretSanitization:
    """OPS-1.2: Structured-log secret sanitization filter."""

    def test_redact_processor_in_chain(self) -> None:
        import inspect
        from app.core.logging import setup_logging
        source = inspect.getsource(setup_logging)
        assert "redact_sensitive" in source

    def test_sensitive_keys_cover_api_keys(self) -> None:
        from app.core.logging import SENSITIVE_KEYS
        required = {"api_key", "password", "authorization", "jwt_secret_key", "sentry_dsn", "secret"}
        assert required.issubset(SENSITIVE_KEYS)
```

**Validation:** `uv run pytest app/tests/test_security.py::TestLogSecretSanitization -v`

## Anti-Patterns Checklist

| # | Rule | Status |
|---|------|--------|
| 1 | No `assert` in production code | OK — no asserts |
| 2 | No `object` type hints without narrowing | OK — `_redact_value(value: object)` with isinstance narrowing |
| 5 | No unused imports/variables | OK — all imports used |
| 6 | No unnecessary noqa/type-ignore | OK — none added |
| 7 | Test helpers need return type annotations | OK — processor returns `EventDict` |
| 8 | No EN DASH | OK — using standard hyphen |
| 18 | ARG001 for unused params | OK — `_logger`, `_method_name` follow existing `add_request_id` pattern |

## Preflight Warnings

None — modifying only `app/core/logging.py` (clean file, no fragile patterns) and appending tests.

## Security Checklist

No new endpoints introduced. Checklist items (auth, rate limiting, input validation, error responses, escape_like) are not applicable.

- [x] No hardcoded credentials in sanitization code
- [x] Sensitive key list covers all config.py API key fields
- [x] Processor is fail-safe (no exceptions from redaction logic)
- [x] Redaction preserves log structure (only replaces values)

## Verification

- [ ] `make lint` passes (ruff format + check)
- [ ] `make types` passes (mypy + pyright)
- [ ] `uv run pytest app/core/tests/test_logging.py -v` — all tests pass including 8 new
- [ ] `uv run pytest app/tests/test_security.py::TestLogSecretSanitization -v` — convention test passes
- [ ] `make test` passes (full unit suite)
- [ ] Pyright errors = 0 (baseline: 0)
- [ ] mypy errors = 0 (baseline: 0)
