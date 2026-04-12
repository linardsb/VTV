# Plan: AI-9.2 — Blocking Mode for High-Confidence Injections

## Context

Detection without blocking produces alert fatigue. AI-9.1 added OWASP LLM01 injection detection with confidence scoring (log-only). AI-9.2 adds a blocking gate: when any signal exceeds `prompt_injection_block_threshold` (0.85), reject the request with HTTP 400 before calling the LLM. Feature-gated via `prompt_injection_mode` (`"warn"` default, flip to `"block"` per-env).

## Security Context Assessment

| Context | Active | Rationale |
|---------|--------|-----------|
| CTX-AGENT | **Yes** | Modifies agent pipeline, injection defense |
| CTX-AUTH | No | No auth flow changes |
| CTX-RBAC | No | No new endpoints |
| CTX-INPUT | Partially | Validates user prompt content |
| CTX-INFRA | No | Config-only, no Docker/nginx changes |
| CTX-FILE | No | No file handling |

**CTX-AGENT requirements:** Prompt injection defense (blocking mode), output sanitization (error response must not echo prompt), no credential exposure in logs.

## Research Summary

### Injection Detection (AI-9.1 baseline)

- **`app/core/agents/injection_detector.py`** — `InjectionSignal` (frozen dataclass: `pattern_id`, `pattern_name`, `confidence`, `matched_text`, `category`) and `InjectionResult` (frozen: `signals`, `aggregate_confidence`, `category_counts`, `detected` property, `to_log_dict()`)
- **`detect_injection(text: str) -> InjectionResult`** — module-level singleton function (line ~335)
- Confidence aggregation: multi-signal cross-category boost +0.10, same-category +0.05, capped at 0.95

### Pipeline Integration Point

- **`app/core/agents/base.py:180-196`** — Phase 2 (prompt injection check, log-only):
  ```python
  injection_result = detect_injection(current_prompt)
  if injection_result.detected:
      settings = get_settings()
      log_level = "warning"
      if injection_result.aggregate_confidence >= settings.prompt_injection_block_threshold:
          log_level = "error"
      getattr(logger, log_level)("agent.injection.detected", **injection_result.to_log_dict(), prompt_length=len(current_prompt))
  ```
- Phase 3 starts at line ~199 with `_get_model_tier()` — blocking must insert before this

### Configuration

- **`app/core/config.py:295-297`** — existing settings:
  - `prompt_injection_block_threshold: float = 0.85`
  - `prompt_injection_warn_threshold: float = 0.5`
- No mode toggle exists yet — must add `prompt_injection_mode`

### Exception Hierarchy

- **`app/core/agents/exceptions.py`** — `AgentError` base, with `agent_exception_handler()` mapping subclasses to HTTP status codes
- Existing mappings: `AgentExecutionError` → 502, `TransitDataError`/`ObsidianError`/`CircuitBreakerOpenError`/`AllProvidersUnavailableError` → 503
- Handler returns `JSONResponse(status_code=..., content={"error": str(exc), "type": type(exc).__name__})`
- **`setup_agent_exception_handlers(app)`** registered in `app/main.py:182`

### Routes

- **`app/core/agents/routes.py:40-86`** — `POST /v1/chat/completions` calls `service.chat(body)` → `chat_with_trace()`. Exceptions propagate to registered handlers.

## Test Landscape

### Existing Injection Tests
- **`app/core/agents/tests/test_injection_detector.py`** (274 lines, 42 tests) — covers all OWASP patterns, confidence scoring, false positive resilience, edge cases. **No changes needed.**
- **`app/core/agents/tests/test_base.py:361-376`** — 2 helper tests for Phase 2 detection integration

### Key Fixtures (conftest.py)
- `make_agent_result(**overrides)` — factory for `AgentResult`
- `_reset_provider_breakers` — autouse fixture
- `ManualClock` — deterministic time control
- `_FakeAgentService` (test_base.py:34-84) — subclass for testing without real LLM

### Route Test Fixtures (test_routes.py)
- `_setup_auth_override` — overrides `get_current_user` with mock admin
- `_bypass_quota_tracker` — patches quota tracker with `AsyncMock(return_value=True)`

## Type Check Baseline

| Tool | Errors | Files |
|------|--------|-------|
| pyright `app/core/agents/` | **5** | pipeline.py (3), tools/transit/client.py (1), pipeline.py (1) |
| mypy `app/core/agents/` | **3** | tools/transit/static_store.py (2), pipeline.py (1) |
| pyright `app/core/config.py` + `app/core/exceptions.py` | **0** | — |

**Threshold: pyright <= 5, mypy <= 3 (no new errors)**

## Files to Create/Modify

| Action | File | Purpose |
|--------|------|---------|
| UPDATE | `app/core/config.py` | Add `prompt_injection_mode: Literal["warn","block"]` setting |
| UPDATE | `app/core/agents/exceptions.py` | Add `PromptInjectionBlockedError(AgentError)` + handler mapping to 400 |
| UPDATE | `app/core/agents/base.py` | Replace Phase 2 log-only with mode-aware blocking logic |
| CREATE | `app/core/agents/tests/test_injection_blocking.py` | 12+ unit tests for blocking mode |

## Implementation Steps

### Step 1: Add mode config to Settings

**File:** `app/core/config.py`
**Action:** UPDATE — add `prompt_injection_mode` field near existing injection thresholds (line ~295)

```python
# Prompt injection detection (AI-9.1) + blocking (AI-9.2)
prompt_injection_mode: Literal["warn", "block"] = "warn"
prompt_injection_block_threshold: float = 0.85
prompt_injection_warn_threshold: float = 0.5
```

- Import `Literal` from `typing` (likely already imported — verify)
- Env var: `PROMPT_INJECTION_MODE=block` to enable blocking
- Default `"warn"` for safe rollout — logs but does not block

**Validation:** `uv run ruff check app/core/config.py && uv run pyright app/core/config.py`

---

### Step 2: Add PromptInjectionBlockedError exception + handler mapping

**File:** `app/core/agents/exceptions.py`
**Action:** UPDATE

**2a. Add exception class** (after existing exception classes):
```python
class PromptInjectionBlockedError(AgentError):
    """Raised when prompt injection confidence exceeds blocking threshold.

    Maps to HTTP 400. Response body uses a generic message —
    never echoes the injection text back to the caller.
    """
```

**2b. Update `agent_exception_handler`** — add HTTP 400 mapping:
```python
elif isinstance(exc, PromptInjectionBlockedError):
    status_code = status.HTTP_400_BAD_REQUEST
```

**CRITICAL:** The handler currently does `content={"error": str(exc), "type": type(exc).__name__}`. The exception message must be generic — never include the user's prompt text. Use: `"Request blocked by content safety policy"`.

**2c. Override `__str__`** if the exception stores internal details:
The exception should accept internal details for logging but `__str__` returns only the safe message. Alternatively, always construct with the safe message string and log details separately (simpler, preferred).

**Validation:** `uv run ruff check app/core/agents/exceptions.py && uv run pyright app/core/agents/exceptions.py`

---

### Step 3: Add blocking logic to Phase 2

**File:** `app/core/agents/base.py`
**Action:** UPDATE — replace lines 180-196 (Phase 2 block)

```python
# Phase 2: prompt injection check (AI-9.1 detection + AI-9.2 blocking).
injection_result = detect_injection(current_prompt)
if injection_result.detected:
    settings = get_settings()
    log_dict = injection_result.to_log_dict()

    if (
        settings.prompt_injection_mode == "block"
        and injection_result.aggregate_confidence
        >= settings.prompt_injection_block_threshold
    ):
        # AI-9.2: block high-confidence injections before LLM call
        logger.error(
            "agent.injection.blocked",
            **log_dict,
            prompt_length=len(current_prompt),
            mode="block",
            threshold=settings.prompt_injection_block_threshold,
        )
        raise PromptInjectionBlockedError(
            "Request blocked by content safety policy"
        )

    # Log-only path (warn mode, or below threshold in block mode)
    log_level = "warning"
    if injection_result.aggregate_confidence >= settings.prompt_injection_block_threshold:
        log_level = "error"
    getattr(logger, log_level)(
        "agent.injection.detected",
        **log_dict,
        prompt_length=len(current_prompt),
        mode=settings.prompt_injection_mode,
    )
```

**Import:** Add `PromptInjectionBlockedError` to imports from `app.core.agents.exceptions`

**Key design decisions:**
- `mode == "block"` AND `confidence >= threshold` → raise exception (HTTP 400)
- `mode == "warn"` → always log-only, never block (safe rollout default)
- `mode == "block"` AND `confidence < threshold` → log warning only, proceed
- Log event `agent.injection.blocked` uses `logger.error` (high-severity)
- Log event `agent.injection.detected` preserved for below-threshold detections
- `prompt_length` logged (not raw prompt text) — per CTX-AGENT requirements

**Validation:** `uv run ruff check app/core/agents/base.py && uv run pyright app/core/agents/base.py`

---

### Step 4: Write unit tests

**File:** `app/core/agents/tests/test_injection_blocking.py`
**Action:** CREATE — 12+ tests

```python
"""Unit tests for AI-9.2 prompt injection blocking mode.

Tests blocking behavior, warn mode pass-through, exception mapping,
safe response bodies, and structured logging.
"""
```

**Test classes and cases:**

#### `TestPromptInjectionBlockedError` (3 tests)
1. `test_inherits_from_agent_error` — `isinstance(exc, AgentError)` is True
2. `test_maps_to_http_400` — use `TestClient`, patch detection to return high confidence, verify 400
3. `test_response_body_does_not_echo_prompt` — response `{"error": ..., "type": ...}` must not contain the input text

#### `TestBlockModeRejectsHighConfidence` (2 tests)
4. `test_block_mode_rejects_at_threshold` — `aggregate_confidence == 0.85` + `mode="block"` → raises `PromptInjectionBlockedError`
5. `test_block_mode_rejects_above_threshold` — `aggregate_confidence == 0.92` + `mode="block"` → raises

#### `TestBlockModeAllowsLowConfidence` (2 tests)
6. `test_block_mode_allows_below_threshold` — `aggregate_confidence == 0.50` + `mode="block"` → proceeds (no exception)
7. `test_block_mode_allows_clean_text` — no signals detected → proceeds

#### `TestWarnModeNeverBlocks` (1 test)
8. `test_warn_mode_passes_high_confidence` — `aggregate_confidence == 0.92` + `mode="warn"` → logs but does not raise

#### `TestModeConfigToggle` (1 test)
9. `test_mode_defaults_to_warn` — `Settings()` has `prompt_injection_mode == "warn"`

#### `TestBlockingLogging` (2 tests)
10. `test_blocked_logs_agent_injection_blocked` — verify `logger.error` called with `"agent.injection.blocked"` and includes `pattern_ids`, `aggregate_confidence`
11. `test_blocked_log_excludes_raw_prompt` — log kwargs must not contain prompt text (only `prompt_length`)

#### `TestThresholdEdgeCases` (1 test)
12. `test_exactly_at_threshold_is_blocked` — `>= 0.85` blocks, `0.8499...` does not

**Mock strategy:**
- Patch `detect_injection` to return crafted `InjectionResult` with desired confidence/signals
- Patch `get_settings` to control `prompt_injection_mode` and `prompt_injection_block_threshold`
- Use `_FakeAgentService` from test_base.py pattern (or patch `_execute` on real service)
- For route-level tests: use `TestClient(app)` with auth override + quota bypass fixtures

**Validation:** `uv run pytest app/core/agents/tests/test_injection_blocking.py -v && uv run pyright app/core/agents/tests/test_injection_blocking.py`

---

## Preflight Warnings

- `base.py` Phase 2 block (lines 180-196) uses `getattr(logger, log_level)(...)` dynamic dispatch — preserve this pattern for the warn/below-threshold path
- `agent_exception_handler` returns `{"error": str(exc)}` — the exception's `__init__` message becomes the HTTP response body. Must be generic.
- `injection_result.to_log_dict()` returns `dict[str, object]` — spreads cleanly into structlog kwargs
- Existing test `test_injection_detection_detects_known_pattern` in test_base.py:361 may need updating if Phase 2 behavior changes (verify it still passes)

## Security Checklist

- [x] No new endpoints — no RBAC/rate-limit changes needed
- [x] Error response uses generic message — never echoes prompt
- [x] Logs include `pattern_ids`, `aggregate_confidence` but NEVER raw prompt text
- [x] Feature-gated: `mode="warn"` default prevents accidental blocking
- [x] Threshold configurable via env var for per-environment tuning
- [x] Exception maps to 400 (client error, not 500 server error)

## Anti-Pattern Checklist

- [ ] No `assert` in production code (rule 1)
- [ ] No `Any` without justification (rule 2)
- [ ] Complete type annotations on all functions (rule 7)
- [ ] No EN DASH in strings (rule 8)
- [ ] `Literal["warn", "block"]` for constrained config field (rule 54)
- [ ] No unused imports (rule 5)

## Verification

- [ ] `uv run ruff format app/core/agents/ app/core/config.py` — no formatting issues
- [ ] `uv run ruff check app/core/agents/ app/core/config.py` — no lint errors
- [ ] `uv run pyright app/core/agents/` — errors <= 5 (baseline)
- [ ] `uv run mypy app/core/agents/` — errors <= 3 (baseline)
- [ ] `uv run pytest app/core/agents/tests/test_injection_blocking.py -v` — all 12+ tests pass
- [ ] `uv run pytest app/core/agents/tests/test_injection_detector.py -v` — all 42 existing tests still pass
- [ ] `uv run pytest app/core/agents/tests/test_base.py -v` — existing Phase 2 tests still pass
- [ ] `make test` — full unit suite passes
- [ ] `make security-audit-quick` — passes
