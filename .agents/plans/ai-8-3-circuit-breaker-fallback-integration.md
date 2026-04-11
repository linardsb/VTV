# Plan: AI-8.3 — Circuit Breaker Integration with FallbackModel

## Context

AI-8.1 added the `CircuitBreaker` primitive (`app/core/agents/circuit_breaker.py`) — state machine, config, log events — but never wired it into the hot path. AI-8.2 added per-provider health metrics (`app/core/agents/provider_health.py`) via `track_provider_call()` context manager at three LLM call sites in `service.py`, but `ProviderHealth.state` is hardcoded to `CLOSED` pending AI-8.3.

AI-8.3 closes the loop: a per-provider breaker registry, a provider-chain invoker that skips open breakers **before** incurring call-time timeouts, and a graceful degraded response when the entire chain is exhausted. Pydantic AI's `FallbackModel` is preserved as a belt-and-braces layer when the breaker is disabled or only a single provider remains.

**Verification target**: with breaker enabled, after threshold failures on primary, the next request fails-fast to fallback in <100ms instead of waiting 30s for the primary timeout.

## Security Context Assessment

Triggers from `_shared/security-contexts.md`:

- **CTX-AGENT** (primary): new agent module, LLM integration, tool permissions. Applies:
  - Tool responses must never expose raw credentials/connection strings (breaker logs: provider *name* only, never API keys or endpoints — already enforced in `circuit_breaker.py` logging)
  - Degraded response is a static user-safe string; no exception stack or internal provider name leaked to end users
- **CTX-INFRA** (secondary): new env var reuses existing `circuit_breaker_enabled` kill switch from AI-8.1 — no new secrets, no new endpoints

Not triggered: CTX-AUTH (no auth changes), CTX-RBAC (no new endpoints — admin endpoint is AI-8.2), CTX-FILE (no uploads), CTX-INPUT (no new user-facing input).

## Research Summary

### Circuit breaker primitive (`app/core/agents/circuit_breaker.py`, AI-8.1)

- `CircuitBreaker(name: str, config: BreakerConfig | None = None, *, time_fn=time.monotonic)` — constructor
- `async def call(fn, /, *args, **kwargs) -> T` — raises `CircuitBreakerOpenError` when OPEN; records success/failure; never holds lock across `await fn(...)`
- `state -> CircuitState` property (CLOSED / OPEN / HALF_OPEN)
- `BreakerConfig` fields: `failure_threshold`, `recovery_timeout_s`, `success_threshold`, `window_size`, `failure_rate_threshold`
- Logs: `agent.circuit_breaker.{opened,reopened,half_opened,closed,rejected,probe_success,probe_failure}`

### Existing call sites (`app/core/agents/service.py`)

Three LLM invocation points inside `BaseAgentService._execute()`, all wrapped by `track_provider_call()` (AI-8.2):

| Site | Line | Call | Model arg | Provider key |
|---|---|---|---|---|
| Complex pipeline | `service.py:268-291` | `pipeline.run(...)` | `tier_model` | `get_settings().llm_provider` |
| Correction loop | `service.py:293-322` | `self._correction_loop.run_with_correction(...)` | `tier_model` | `get_settings().llm_provider` |
| Fallback `agent.run()` | `service.py:324-348` | `agent.run(...)` | `tier_model` | `get_settings().llm_provider` |

All three pass `model=tier_model`, where `tier_model` may be `None` (agent default) or a `Model` instance. Provider name is read from `get_settings().llm_provider` regardless of the actual tier model — this is a known simplification inherited from AI-8.2.

### Model resolution (`app/core/agents/config.py`)

- `get_agent_model()` (L39-107) returns `FallbackModel(primary, fallback)` when `llm_fallback_provider` is set, else a single provider Model
- `resolve_tier_model()` (L113-172) returns tier-specific override or `None`
- Provider strings: `"anthropic"`, `"google"`, `"groq"`, `"openai"`, `"ollama"`, `"test"`
- All providers instantiated with explicit API keys from settings — no lazy creation inside agent

### Exception hierarchy (`app/core/agents/exceptions.py`)

- `AgentError` base (L22)
- `CircuitBreakerOpenError(AgentError)` **already exists** (L52-60) → HTTP 503 via `agent_exception_handler` (L63-96, registered L112)
- `AgentExecutionError` (L34) → 502 — catches all other agent failures
- Need to add: `AllProvidersUnavailableError(AgentError)` → 503

### Provider health (`app/core/agents/provider_health.py`, AI-8.2)

- `ProviderHealthTracker` singleton, daily 00:00 UTC reset
- `track_provider_call(tier_model, provider_name)` async context manager — records latency, success/failure, bounded 100-sample deque
- `ProviderHealth.state` field currently always `CircuitState.CLOSED` — **AI-8.3 must update it from the breaker registry**
- Admin endpoint: `GET /v1/chat/provider-health` (already RBAC-gated to admin)
- Helper: `_extract_provider_name(tier_model, default)` handles `None | str | Model`

### Config (`app/core/config.py:295-300`)

```python
circuit_breaker_enabled: bool = True
circuit_breaker_failure_threshold: int = 5
circuit_breaker_recovery_timeout_s: float = 30.0
circuit_breaker_success_threshold: int = 2
circuit_breaker_failure_rate_threshold: float = 0.5
```

All five env-var-backed, feed directly into `BreakerConfig`. No new settings needed.

### Logging conventions

Pattern: `{domain}.{component}.{action}_{state}`. New events for AI-8.3:

- `agent.provider_chain.preempted` — breaker open, skipped ahead of call (primary → fallback)
- `agent.provider_chain.fallback` — runtime failure, moved to next provider in chain
- `agent.provider_chain.exhausted` — all providers unavailable, returning degraded response
- `agent.provider_chain.recovered` — a previously-open breaker is now serving traffic

## Test Landscape

### Fixtures available (`app/core/agents/tests/conftest.py`)

| Name | Purpose |
|---|---|
| `ManualClock` (L111+) | Deterministic `time_fn` for breakers — `advance(seconds)` method |
| `make_breaker_config()` | Fast defaults: `failure_threshold=3, recovery_timeout_s=10.0, success_threshold=2, window_size=10, failure_rate_threshold=0.5` |
| `make_breaker(name, config, clock)` | Wired `CircuitBreaker` instance |
| `make_agent_result(**)` | Factory for `AgentResult` |
| `_reset_skill_cache` (autouse) | Clears module caches each test |

Provider-health tests (`test_provider_health.py`) use `@pytest.fixture(autouse=True) def _reset_singleton()` calling `reset_provider_health_tracker()` — **AI-8.3 must follow the same pattern**: add `reset_provider_breakers()` and a reset fixture.

### Mock patterns

- **LLM override**: `agent.override(model=TestModel())` (Pydantic AI) — used throughout `test_service.py`, `test_base.py`
- **Failure injection**: `mock_agent.run.side_effect = RuntimeError("...")` (`test_service.py:72`) or simple `async def _fail(): raise RuntimeError("boom")` (circuit-breaker tests)
- **No `@pytest.mark.integration`** in agent tests — all unit-level with `@pytest.mark.asyncio`
- **No freezegun** — all timeout tests use `ManualClock.advance()`

### Existing circuit breaker tests (`test_circuit_breaker.py`, 437 lines, 19 tests)

Covers state transitions, sliding-window rate triggers, recovery boundaries, concurrent atomicity, `structlog.testing.capture_logs()` for log assertions. Patterns to reuse for registry tests.

### Fragile patterns (preflight)

| Pattern | Location | Risk |
|---|---|---|
| `assert len(svc.execute_calls) == N` | `test_base.py:316`, `test_agent_result.py:175/206/234/263` | Low — internal test scaffolding, not provider-facing |
| `mock_persist.assert_called_once()` | `test_base.py:295` | Low — memory bridge unchanged by AI-8.3 |
| Hardcoded provider names in `test_config.py` | — | Low — enum is self-documenting |
| `ProviderHealth.state` always `CLOSED` assertion | `test_provider_health.py` | **Medium** — any test that asserts `state == CLOSED` for all providers will break when breaker transitions. Must audit and loosen assertions or trigger through breaker registry. |

## Type Check Baseline

Pre-AI-8.3 state for `app/core/agents/`:

| Tool | Errors | Files |
|---|---|---|
| pyright | **5** | `pipeline.py` ×4, `tools/transit/client.py` ×1 |
| mypy | **3** | `tools/transit/static_store.py` ×2, `pipeline.py` ×1 |

Files targeted by AI-8.3 (`service.py`, `exceptions.py`) are **clean** (0 errors). New files (`llm.py`, test files) must add 0 new errors.

**Post-AI-8.3 gate**: pyright ≤ 5, mypy ≤ 3 in `app/core/agents/`.

## Files to Create / Modify

| Action | File | Purpose |
|---|---|---|
| CREATE | `app/core/agents/llm.py` | Provider breaker registry + `invoke_provider_chain()` wrapper |
| UPDATE | `app/core/agents/exceptions.py` | Add `AllProvidersUnavailableError` (→ 503) |
| UPDATE | `app/core/agents/service.py` | Wrap 3 call sites via `invoke_provider_chain()`; catch `AllProvidersUnavailableError` and return degraded `AgentResult` |
| UPDATE | `app/core/agents/provider_health.py` | `track_provider_call()` passes live `get_breaker_state(provider)` into existing `record_call(state=...)` param |
| UPDATE | `app/core/agents/base.py` | Don't re-wrap `AllProvidersUnavailableError` as `AgentExecutionError` at L254-261 |
| CREATE | `app/core/agents/tests/test_llm.py` | Unit tests for registry + invocation wrapper (5 tests) |
| UPDATE | `app/core/agents/tests/test_service.py` | Integration tests for provider chain + degraded response (8 tests minimum) |
| UPDATE | `app/core/agents/tests/conftest.py` | Add `_reset_provider_breakers` autouse fixture + `make_provider_chain_mock()` helper |
| — | `app/core/agents/tests/test_provider_health.py` | **No changes** — preflight confirmed `record_call(state=...)` passthrough contract is preserved by Step 3 wiring |

No new config settings, no new endpoints, no new routes, no alembic migrations.

## Implementation Steps

### Step 1 — Add `AllProvidersUnavailableError` exception

**File**: `app/core/agents/exceptions.py`

Add after `CircuitBreakerOpenError` (~L60):

```python
class AllProvidersUnavailableError(AgentError):
    """All LLM providers in the fallback chain are unavailable (breakers open or calls failed).

    Mapped to HTTP 503 so clients can retry after ``recovery_timeout_s``.
    """

    def __init__(self, providers_tried: list[str]) -> None:
        self.providers_tried = providers_tried
        super().__init__(
            f"All LLM providers unavailable: {', '.join(providers_tried)}"
        )
```

Extend `agent_exception_handler` (L63-96) to map `AllProvidersUnavailableError` → 503. Register in the handler dispatch isinstance ladder — place alongside `CircuitBreakerOpenError`.

**Validation**: `uv run ruff format app/core/agents/exceptions.py && uv run ruff check --fix app/core/agents/exceptions.py && uv run pyright app/core/agents/exceptions.py && uv run mypy app/core/agents/exceptions.py`

### Step 2 — Create `app/core/agents/llm.py` (breaker registry + invoker)

**File**: `app/core/agents/llm.py` (new, ~150 lines)

Public API:

```python
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

from pydantic_ai.models import Model

from app.core.agents.circuit_breaker import (
    BreakerConfig,
    CircuitBreaker,
    CircuitBreakerOpenError,
    CircuitState,
)
from app.core.agents.exceptions import AllProvidersUnavailableError
from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")

# Module-level registry — lazy init on first get_breaker() call
_breakers: dict[str, CircuitBreaker] = {}
_registry_lock = asyncio.Lock()


def _build_config(settings: Settings) -> BreakerConfig:
    return BreakerConfig(
        failure_threshold=settings.circuit_breaker_failure_threshold,
        recovery_timeout_s=settings.circuit_breaker_recovery_timeout_s,
        success_threshold=settings.circuit_breaker_success_threshold,
        failure_rate_threshold=settings.circuit_breaker_failure_rate_threshold,
    )


def get_breaker(provider_name: str, settings: Settings | None = None) -> CircuitBreaker:
    """Return (or lazily create) the breaker for this provider."""
    if provider_name not in _breakers:
        _breakers[provider_name] = CircuitBreaker(
            name=provider_name,
            config=_build_config(settings or get_settings()),
        )
    return _breakers[provider_name]


def get_breaker_state(provider_name: str) -> CircuitState:
    """Read-only state lookup — used by provider_health.py. Returns CLOSED if unregistered."""
    breaker = _breakers.get(provider_name)
    return breaker.state if breaker is not None else CircuitState.CLOSED


def reset_provider_breakers() -> None:
    """Test-only: clear the registry between tests."""
    _breakers.clear()


def _provider_chain(settings: Settings) -> list[str]:
    chain = [settings.llm_provider]
    if settings.llm_fallback_provider and settings.llm_fallback_provider != settings.llm_provider:
        chain.append(settings.llm_fallback_provider)
    return chain


async def invoke_provider_chain(
    call: Callable[[str], Awaitable[T]],
    *,
    settings: Settings | None = None,
) -> T:
    """Invoke ``call(provider_name)`` across the fallback chain with breaker preemption.

    - If a provider's breaker is OPEN, skip it immediately (no call-time wait).
    - Otherwise, run ``call`` through ``breaker.call(...)``.
    - On failure, move to next provider in chain.
    - If the entire chain is exhausted, raise ``AllProvidersUnavailableError``.

    When ``circuit_breaker_enabled`` is False, the chain is flattened to the single
    primary provider with no breaker wrapping — preserves pre-AI-8 behavior byte-for-byte.
    """
    s = settings or get_settings()

    if not s.circuit_breaker_enabled:
        return await call(s.llm_provider)

    chain = _provider_chain(s)
    tried: list[str] = []
    last_error: Exception | None = None

    for provider in chain:
        breaker = get_breaker(provider, s)
        if breaker.state is CircuitState.OPEN:
            logger.info(
                "agent.provider_chain.preempted",
                provider=provider,
                reason="breaker_open",
            )
            tried.append(provider)
            continue
        try:
            return await breaker.call(call, provider)
        except CircuitBreakerOpenError:
            # Race: breaker opened between state check and call
            tried.append(provider)
            logger.info("agent.provider_chain.preempted", provider=provider, reason="race")
            continue
        except Exception as exc:  # noqa: BLE001 — breaker already recorded the failure
            tried.append(provider)
            last_error = exc
            logger.warning(
                "agent.provider_chain.fallback",
                provider=provider,
                error_type=type(exc).__name__,
            )
            continue

    logger.error(
        "agent.provider_chain.exhausted",
        providers_tried=tried,
        last_error_type=type(last_error).__name__ if last_error else None,
    )
    raise AllProvidersUnavailableError(providers_tried=tried)
```

**Key design notes**:
- `_breakers` dict is module-level but reads are lock-free; writes happen at registration time (small race window tolerated — idempotent overwrite). The `CircuitBreaker` has its own internal lock for state transitions.
- The `call` callable receives the provider name and must build its own model. Caller is responsible for passing the correct `Model` instance to `agent.run(...)` inside the closure.
- When `circuit_breaker_enabled=False`, the function flattens to a single direct call with no breaker, no chain, no registry writes — this is the "byte-for-byte preserved" path required by the verification criterion.
- `FallbackModel` is preserved as belt-and-braces: when the breaker is disabled OR when a single provider is configured, `get_agent_model()` still returns `FallbackModel(...)` and pydantic_ai handles the cascade internally.

**Validation**: `uv run ruff format app/core/agents/llm.py && uv run ruff check --fix app/core/agents/llm.py && uv run pyright app/core/agents/llm.py && uv run mypy app/core/agents/llm.py`

### Step 3 — Wire breaker state into `ProviderHealth` via `track_provider_call`

**File**: `app/core/agents/provider_health.py`

**Preflight correction**: `record_call()` at `provider_health.py:128-155` **already accepts** `state: CircuitState = CircuitState.CLOSED` and applies it to `entry.state` on L149. `test_provider_health.py:264-279` already verifies this passthrough works. The correct wiring is therefore not to mutate `ProviderHealth` — it's to **pass the live breaker state through the existing parameter** at the `track_provider_call()` call site.

Two small changes to `provider_health.py`:

1. Extend `track_provider_call()` (L232-265) to look up the breaker state via `get_breaker_state(provider)` from `app.core.agents.llm` at the point where `record_call` is invoked (both success and failure branches). Circular-import guard: do the import inside the function body (deferred import), since `llm.py` is loaded at service construction time but this contextmanager runs later.

2. Remove or update the TODO comment at L219-223 — the follow-up is now landing.

```python
# Inside track_provider_call's success/failure branches:
from app.core.agents.llm import get_breaker_state  # local to avoid import cycle
breaker_state = get_breaker_state(provider)
tracker.record_call(
    provider,
    latency_ms=latency_ms,
    success=True,  # or False in the except branch
    state=breaker_state,
)
```

**Why this is better than mutating `ProviderHealth.state` on read**:
- Zero changes to `ProviderHealth` dataclass or its invariants
- `test_provider_health.py:264` (passes `state=CircuitState.OPEN` explicitly) stays green — the contract is preserved
- No new circular-import risk in dataclass-level imports
- Snapshot deep-copy in `get_all()` (L171-182) continues to work unchanged

**Validation**: `uv run ruff format app/core/agents/provider_health.py && uv run pyright app/core/agents/provider_health.py && uv run mypy app/core/agents/provider_health.py`

### Step 4 — Wire `invoke_provider_chain` into `service.py` call sites

**File**: `app/core/agents/service.py`

For each of the three call sites (L268, L293, L324), restructure the LLM invocation to go through `invoke_provider_chain`. Pattern for the fallback `agent.run()` site (easiest — others follow same shape):

```python
from app.core.agents.llm import invoke_provider_chain
from app.core.agents.config import resolve_tier_model_for_provider  # new helper in config.py

async def _run_for_provider(provider_name: str) -> AgentRunResult:
    model = resolve_tier_model_for_provider(tier, provider_name) or tier_model
    async with track_provider_call(model, provider_name):
        return await agent.run(
            user_message,
            deps=self._deps,
            message_history=message_history,
            instructions=instructions,
            model=model,
        )

result = await invoke_provider_chain(_run_for_provider)
```

If extending `config.py` with `resolve_tier_model_for_provider(tier, provider)` is too invasive, the simpler path is: use `tier_model` as-is and only swap the top-level primary/fallback. The tier override stays locked to whatever the admin configured, and the breaker chain cascades at the base-provider level. **Recommended simpler approach** — document the decision inline.

Apply the same pattern to all three call sites. The closure must capture `tier_model`, `agent`, `user_message`, etc. Extract a private `_invoke_with_chain()` helper on `BaseAgentService` to avoid three copies.

**Catch `AllProvidersUnavailableError`** inside `_execute()` (or at the service entry point in `base.py`) and return a degraded `AgentResult`:

```python
except AllProvidersUnavailableError as exc:
    logger.error(
        "agent.provider_chain.exhausted",
        providers_tried=exc.providers_tried,
        exc_info=True,
    )
    return AgentResult(
        content="All LLM providers temporarily unavailable — please retry in 30 seconds.",
        confidence=0.0,
        warnings=["provider_chain_exhausted"],
        tools_used=[],
        domain=self._domain,
    )
```

Ensure `base.py:254-261` does NOT re-wrap `AllProvidersUnavailableError` as `AgentExecutionError`. Add explicit `except AllProvidersUnavailableError: raise` before the generic handler, or have service.py return a degraded `AgentResult` directly so the exception never reaches base.py.

**Validation**: `uv run ruff format app/core/agents/service.py app/core/agents/base.py && uv run ruff check --fix app/core/agents/service.py app/core/agents/base.py && uv run pyright app/core/agents/service.py app/core/agents/base.py && uv run mypy app/core/agents/service.py app/core/agents/base.py`

### Step 5 — Unit tests for registry + invoker (`test_llm.py`)

**File**: `app/core/agents/tests/test_llm.py` (new)

5 tests:

1. `test_get_breaker_lazy_init` — first call creates, second returns same instance
2. `test_get_breaker_state_unregistered_returns_closed` — read-only lookup for unknown provider
3. `test_invoke_provider_chain_disabled_passes_through` — with `circuit_breaker_enabled=False`, calls primary directly, no registry writes
4. `test_invoke_provider_chain_primary_open_skips_to_fallback` — set primary breaker to OPEN via direct state manipulation (or trip it with failures + `ManualClock`), confirm fallback receives the call in <1ms of primary skip
5. `test_invoke_provider_chain_all_exhausted_raises` — both providers raise, confirm `AllProvidersUnavailableError(providers_tried=["primary", "fallback"])`

Use `monkeypatch.setenv` or direct `Settings` override for `circuit_breaker_enabled` and provider chain. Use `ManualClock` from conftest for timeout determinism.

**Validation**: `uv run pytest app/core/agents/tests/test_llm.py -v`

### Step 6 — Integration tests in `test_service.py` (8+ tests)

**File**: `app/core/agents/tests/test_service.py`

Extend with new `TestCircuitBreakerIntegration` class:

1. `test_single_provider_trip_fallback_kicks_in` — primary raises 5×, 6th request routes to fallback automatically
2. `test_fallback_also_fails_after_primary` — primary open + fallback raises → `AllProvidersUnavailableError` in chain, degraded `AgentResult` returned
3. `test_all_providers_open_returns_degraded_response` — both breakers pre-opened, service returns `AgentResult(content="All LLM providers temporarily unavailable...", confidence=0.0)` with warning `provider_chain_exhausted`
4. `test_breaker_preempts_before_timeout` — set a slow (2s) mock, trip the breaker, then call again and assert elapsed time <100ms (use `time.monotonic()` deltas on real clock, short timeouts via `ManualClock` for breaker state)
5. `test_breaker_second_request_fast_fails` — companion to #4, simpler: open the breaker manually, call twice, assert both return in constant time
6. `test_recovery_after_timeout` — trip breaker, `ManualClock.advance(recovery_timeout_s + 1)`, next call enters HALF_OPEN and probes; after `success_threshold` successes, state → CLOSED
7. `test_config_disabled_preserves_fallback_model_path` — set `circuit_breaker_enabled=False`, confirm that `get_agent_model()` still returns `FallbackModel`, no breakers registered, runtime behavior matches AI-8.0 baseline (assert `_breakers == {}`)
8. `test_config_disabled_exception_propagates_without_wrapping` — with breaker disabled, primary raises → original exception (not `AllProvidersUnavailableError`) propagates; confirms byte-for-byte preservation

Reuse `agent.override(model=TestModel())` for the happy path and direct `mock_agent.run.side_effect = RuntimeError(...)` for failure injection. Reset breaker registry between tests via new autouse fixture.

**Validation**: `uv run pytest app/core/agents/tests/test_service.py -v`

### Step 7 — Test fixtures and breaker reset

**File**: `app/core/agents/tests/conftest.py`

Add autouse fixture that resets the breaker registry + health tracker between every test:

```python
@pytest.fixture(autouse=True)
def _reset_provider_breakers() -> Iterator[None]:
    from app.core.agents.llm import reset_provider_breakers
    reset_provider_breakers()
    yield
    reset_provider_breakers()
```

Ensure correct import placement and typed `Iterator[None]` return annotation (Python anti-pattern #26). Add `from collections.abc import Iterator`.

Audit `test_provider_health.py` for assertions that hardcode `state == CircuitState.CLOSED` — loosen or drive state explicitly through the registry.

**Validation**: `uv run pytest app/core/agents/tests/ -v`

### Step 8 — Full suite + type checks

Run the full agent module quality gate:

```bash
uv run ruff format app/core/agents/
uv run ruff check app/core/agents/
uv run pyright app/core/agents/ 2>&1 | tail -10
uv run mypy app/core/agents/ 2>&1 | tail -10
uv run pytest app/core/agents/tests/ -v
uv run pytest app/tests/test_security.py -v
```

Confirm pyright ≤ 5 errors, mypy ≤ 3 errors (unchanged from baseline), all new tests pass, no regressions in existing agent tests.

### Step 9 — Verification recipe

Manual verification described in the feature spec:

1. Enable breaker: `CIRCUIT_BREAKER_ENABLED=true` (default)
2. Start backend + configure a primary provider that takes 30s to timeout (e.g., unreachable Ollama at `http://127.0.0.1:9`)
3. Configure a working fallback (`llm_fallback_provider=test`)
4. Send 5 chat requests — each times out after 30s (breaker accumulates failures)
5. Send 6th request — should fail-fast via fallback in <100ms
6. Check `GET /v1/chat/provider-health` — primary state should be `OPEN`
7. Flip `CIRCUIT_BREAKER_ENABLED=false`, restart, repeat steps 4-5 — confirm each request still takes 30s (pre-AI-8 behavior preserved)

## Preflight Warnings

From Agent 2's fragile-pattern scan:

- **`test_provider_health.py`**: any test asserting `ProviderHealth.state == CircuitState.CLOSED` will now reflect live breaker state. Audit and drive through registry or loosen to `state in {CLOSED, HALF_OPEN}`.
- **`test_base.py:316`, `test_agent_result.py:175/206/234/263`**: `assert len(svc.execute_calls) == N` — unaffected by AI-8.3 (internal scaffolding, not provider-facing). No action.
- **`test_base.py:295`**: `mock_persist.assert_called_once()` — unaffected; memory bridge still fires per LLM call. No action.
- **`config.py:101-107`**: `FallbackModel(primary, fallback)` — preserve this path when breaker disabled (verify via Step 6 test #7).
- **Race in `_breakers` dict write**: lock-free write on first registration. Acceptable (idempotent overwrite, internal state machine is locked). If pyright flags the dict mutation, add a short `asyncio.Lock` guard.

## Security Checklist (CTX-AGENT)

- [ ] Breaker logs never include raw API keys or connection strings (already enforced in `circuit_breaker.py`)
- [ ] `_provider_chain()` does not leak internal provider names to end-user error messages — degraded response is a generic string
- [ ] `AllProvidersUnavailableError.providers_tried` is logged at `error` level but only returned via the service-layer degraded `AgentResult` (with a generic `provider_chain_exhausted` warning), never raised to HTTP clients
- [ ] No new endpoints, no RBAC changes — convention test `TestAllEndpointsRequireAuth` in `app/tests/test_security.py` unchanged
- [ ] `circuit_breaker_enabled` kill switch preserves pre-AI-8 behavior byte-for-byte (verified in test #7/#8)

## Anti-Pattern Checks (from `_shared/python-anti-patterns.md`)

- **#5** — only import what's used; no speculative imports in `llm.py`
- **#9** — `ctx` not used here (not a Pydantic AI tool function)
- **#22** — explicit type annotations on test dict literals if any `fake_metrics: dict[str, int | float]` style
- **#26** — test helpers need `-> None` / `-> Iterator[None]` annotations
- **#28** — bare `[]` in tests must be annotated
- **#33** — use `dict[str, Any]` not `dict[str, object]` for breaker config factories if they use `**kwargs` unpacking
- **#37** — no `except: pass` in breaker code; always log
- **#38** — `except BaseException` in background tasks — N/A here
- **#59** — grep for `state == CLOSED` across tests before renaming/behavioral change (done in Step 7)

## Verification Gate

- [ ] `uv run ruff format app/core/agents/` — clean
- [ ] `uv run ruff check app/core/agents/` — 0 violations
- [ ] `uv run pyright app/core/agents/ 2>&1 | tail -5` — ≤ 5 errors (baseline)
- [ ] `uv run mypy app/core/agents/ 2>&1 | tail -5` — ≤ 3 errors (baseline)
- [ ] `uv run pytest app/core/agents/tests/test_llm.py -v` — 5/5 pass
- [ ] `uv run pytest app/core/agents/tests/test_service.py::TestCircuitBreakerIntegration -v` — 8/8 pass
- [ ] `uv run pytest app/core/agents/tests/ -v` — full agent suite green
- [ ] `uv run pytest app/tests/test_security.py -v` — security conventions pass
- [ ] `make check` — full project gate
- [ ] `make security-audit-quick` — clean
- [ ] Manual verification: breaker fails-fast in <100ms after trip (6th request)
- [ ] Manual verification: `CIRCUIT_BREAKER_ENABLED=false` preserves 30s timeout path
- [ ] `ProviderHealth.state` now reflects live breaker state in `GET /v1/chat/provider-health`

## Open Questions / Decision Points for `/be-execute`

1. **Per-site wiring depth**: The simplest path wires only the `agent.run()` fallback site (L324) and leaves the complex pipeline (L268) and correction loop (L293) with the existing `track_provider_call` wrapper + plain invocation. Full coverage of all three sites is more work but aligns with the spec. **Recommendation**: wire all three via a shared `BaseAgentService._invoke_with_chain()` helper to avoid duplication and keep the breaker authoritative for every LLM call.
2. **Tier model override + breaker interaction**: If a tier override specifies a different provider than `settings.llm_provider`, should the breaker key be the override's provider or the settings provider? **Recommendation**: use the settings provider (matches AI-8.2's current extraction) — a future refinement can make breakers tier-aware.
3. **`FallbackModel` inside the chain**: `get_agent_model()` returns `FallbackModel(...)` when configured. If we're cascading at the breaker layer, should we bypass `FallbackModel` and pass a single-provider Model to `agent.run()`? **Recommendation**: yes — pass the single-provider Model for the provider currently being attempted. The `FallbackModel` path is only taken when the breaker is disabled (kill switch on).
