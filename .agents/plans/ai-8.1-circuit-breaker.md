# Plan: AI-8.1 — Circuit Breaker State Machine for LLM Providers

## Context

The agent service currently relies on Pydantic AI's `FallbackModel` (wired in `app/core/agents/config.py:103-105`) to recover from LLM provider failures. `FallbackModel` only reacts to hard exceptions raised at call-time — it cannot preempt a degrading primary provider (timeouts, 5xx spikes, quota throttling). Every request pays the full primary-provider latency tax (5–30s) before falling over, which directly hits dispatcher-visible response time.

This task adds a classic 3-state circuit breaker (`CLOSED → OPEN → HALF_OPEN → CLOSED`) that wraps each LLM invocation in `BaseAgentService._execute()`. When consecutive failures exceed `failure_threshold` or the sliding-window failure rate exceeds `failure_rate_threshold`, the breaker opens and fails fast with `CircuitBreakerOpenError`. After `recovery_timeout_s`, it transitions to `HALF_OPEN` to probe; `success_threshold` successful probes close it again.

The repo **already** has a reference breaker for GTFS-RT feeds at `app/core/resilience.py:1-161` — we mirror its shape (state enum, `asyncio.Lock`, `get_logger`) but add sliding-window rate tracking. This is an **agent-module-local** utility, not a new resilience/shared utility, to keep the blast radius tight and follow VSA.

## Security Context Assessment

| Context | Active? | Why |
|---|---|---|
| CTX-AUTH | No | No auth/session/token changes |
| CTX-RBAC | No | No new endpoints, no route changes |
| CTX-FILE | No | No file handling |
| **CTX-AGENT** | **Yes** | Wraps LLM provider invocation inside agent tools path |
| CTX-INFRA | Partial | New config settings — env-var-backed, no secrets |
| CTX-INPUT | No | No user-facing input handling |

**CTX-AGENT requirements that apply:**
- **Tool permissions** — Breaker is read-only state; doesn't expose credentials or tool responses. N/A beyond that.
- **No credential exposure** — Log events MUST NOT include provider API keys, endpoints with creds, or raw exception `repr()` that could dump auth headers. Log only `provider_name`, `state`, `failure_count`, `elapsed_s`.
- **Agent-created artifacts inactive by default** — N/A (breaker is infra, not agent output).
- **Prompt injection defense** — N/A (breaker doesn't touch user input).

**CTX-INFRA requirements that apply:**
- New settings must use env-var interpolation via pydantic-settings (already standard in `app/core/config.py`). No hardcoded values, no secrets in defaults.
- `circuit_breaker_enabled: bool = True` acts as a kill switch — operators can disable globally via env var without redeploy.

## Research Summary

### LLM invocation sites (where to wrap)

- `app/core/agents/service.py:248-344` — `AgentService._execute()` override of `BaseAgentService` hook 8
- Three invocation paths inside `_execute()`:
  1. Line 266: `pipeline.run()` — complex tier
  2. Line 292: `self._correction_loop.run_with_correction(agent, ...)` — standard tier w/ correction
  3. Line 321-327: `agent.run(user_message, deps=..., model=tier_model)` — direct fallback path
- `FallbackModel` is constructed in `app/core/agents/config.py:39-108` via `get_agent_model()` / `resolve_tier_model()`

**Wiring decision:** Wrap at the `_execute()` hook layer (service.py, not the Model layer). Rationale:
- Single place to wrap all three invocation paths
- Keeps breaker logic out of Pydantic AI's type-constrained `Model` surface
- Enables per-tier breakers keyed by tier+provider (future extension)
- Mirrors how `SelfCorrectionLoop` is composed at the service level

**Scope boundary for this task:** Create the breaker primitive + config + exception + tests in this task. The actual `_execute()` wiring is a trivial 5-line wrap that lands in the same PR but uses a single shared breaker instance injected through `BaseAgentService.__init__` (or a module-level registry keyed by provider name). See "Out of scope (follow-up)" below.

### Exception hierarchy

- `app/core/agents/exceptions.py:1-99`
- Base: `AgentError` (line 21)
- Pattern: other subclasses (e.g., `AgentExecutionError`) follow the same shape
- Handler registration at `setup_agent_exception_handlers()` around line 87

### Config location

- `app/core/config.py:278-293` — existing agent settings block
  ```
  agent_self_correction_enabled: bool = True
  agent_max_correction_rounds: int = 1
  agent_multi_agent_enabled: bool = False
  agent_progressive_skills_enabled: bool = True
  agent_confidence_reroute_enabled: bool = True
  agent_confidence_reroute_threshold: float = 0.3
  ```
- Add the 5 new circuit-breaker settings **immediately after line 293** under a `# Circuit breaker (AI-8.1)` comment.

### Reference pattern (reuse shape, not code)

- `app/core/resilience.py:1-161` — existing GTFS-RT circuit breaker:
  - `CircuitState` enum (line 25): `CLOSED / OPEN / HALF_OPEN`
  - `CircuitOpenError` (line 33-46)
  - `__aenter__`/`__aexit__` async context manager
  - `asyncio.Lock` for state transitions
  - Log event: `resilience.circuit_breaker.state_changed`
- We create a **separate** breaker in `app/core/agents/circuit_breaker.py` — DO NOT modify `app/core/resilience.py`. The LLM breaker differs because (a) it needs a sliding-window rate, (b) it needs a `success_threshold` for probe counting in `HALF_OPEN`, (c) it lives in the agent namespace for clarity.

### Logging

- Logger: `from app.core.logging import get_logger` then `logger = get_logger(__name__)`
- Taxonomy: `{domain}.{component}.{action}_{state}` (see `docs/logging-standard.md`)
- Existing `agent.*` events in service.py: `agent.rag_routing`, `agent.skills_load_failed`, `agent.memory.recall_injected`, `agent.correction.triggered/resolved/exhausted`
- New events:
  - `agent.circuit_breaker.opened` — CLOSED → OPEN (fields: `provider`, `failure_count`, `failure_rate`, `trigger` ∈ `{"consecutive","rate"}`)
  - `agent.circuit_breaker.half_opened` — OPEN → HALF_OPEN (fields: `provider`, `elapsed_s`)
  - `agent.circuit_breaker.closed` — HALF_OPEN → CLOSED (fields: `provider`, `successful_probes`)
  - `agent.circuit_breaker.reopened` — HALF_OPEN → OPEN on probe failure (fields: `provider`, `error`)
  - `agent.circuit_breaker.rejected` — call blocked by open breaker (fields: `provider`, `state`)
  - `agent.circuit_breaker.probe_success` / `agent.circuit_breaker.probe_failure` — while HALF_OPEN

### Shared utilities to reuse

- `get_logger` from `app.core.logging`
- `get_settings` / `Settings` from `app.core.config`
- `asyncio.Lock` (stdlib)
- `time.monotonic` (stdlib) — for recovery timeout tracking
- `collections.deque` (stdlib) — for sliding window
- No third-party deps needed; **no pyproject.toml changes**.

## Test Landscape

### Conftest

- `app/core/agents/tests/conftest.py` — existing factories:
  - `make_agent_result(**overrides) -> AgentResult`
  - `make_skill_meta(**overrides) -> SkillMeta`
  - `make_eval_case(**overrides) -> EvalCase`
  - `_reset_skill_cache` autouse fixture (module-level state reset pattern)
- Add a new factory `make_breaker_config(**overrides) -> BreakerConfig` + a `ManualClock` test helper (see below).

### Async testing

- pytest-asyncio in **auto mode** (`pyproject.toml:228-233`) — `@pytest.mark.asyncio` + `async def test_*`
- Established pattern at `app/core/agents/tests/test_service.py:32-75` and `tests/test_correction.py:33-100`:
  - `AsyncMock(side_effect=[...])` for sequential outcomes
  - Private helpers prefixed `_` return MagicMock doubles (typed `-> MagicMock`)
  - `with patch("app.core.agents.service.agent") as mock_agent:` pattern

### Time mocking (critical for recovery-timeout tests)

**Finding (from Scout):** This repo does **NOT** use `freezegun`. Existing tests either:
1. Pre-compute past timestamps: `fetched_at=time.monotonic() - 100`
2. Rely on real elapsed time

**Decision:** Inject a `time_fn: Callable[[], float] = time.monotonic` into `CircuitBreaker.__init__`. In production, defaults to `time.monotonic`. In tests, pass a `ManualClock` instance with an advance-able `.now` attribute. This is explicit, deterministic, dependency-injected — no external libs, mirrors the repo's philosophy.

```python
class ManualClock:
    def __init__(self, start: float = 0.0) -> None:
        self.now = start
    def __call__(self) -> float:
        return self.now
    def advance(self, seconds: float) -> None:
        self.now += seconds
```

### Anti-patterns to avoid in tests (from `_shared/python-anti-patterns.md`)

- Rule 26: `-> None` on all test functions (mypy `no-untyped-def` even with relaxed rules)
- Rule 28: Annotate bare `[]` list literals: `calls: list[int] = []`
- Rule 33: `dict[str, Any]` not `dict[str, object]` for **kwargs
- Rule 7: Test helpers must have return type annotations
- Rule 4: Mock exceptions must match catch blocks — tests must raise the same exception types that `CircuitBreaker.call()` catches
- Rule 37: Don't `except: pass` — log in any except block (breaker internals)

### Security convention tests

- `app/tests/test_security.py` currently asserts endpoint-level auth/rate-limit coverage. Since this task adds **no endpoints**, the existing convention tests will remain green without modification. Verify by running them at the end.

## Type Check Baseline

Captured pre-implementation so any new errors after this task are directly attributable.

| Check | Target | Baseline |
|---|---|---|
| pyright | `app/core/agents/` | **5 errors** (all in `pipeline.py` + `tools/transit/client.py` + `tools/transit/static_store.py` — untouched) |
| pyright | `app/core/config.py` + `app/core/exceptions.py` | **0 errors** |
| mypy | `app/core/agents/` | **3 errors** (all in `tools/transit/static_store.py` + `pipeline.py` — untouched) |
| mypy | `app/core/config.py` + `app/core/exceptions.py` | **0 errors** |
| pytest collect | `app/core/agents/tests/` | **337 tests** |

**Acceptance:** After this task:
- `pyright app/core/agents/` must report **≤ 5 errors** (no new errors in new files).
- `pyright app/core/agents/circuit_breaker.py` + `app/core/agents/tests/test_circuit_breaker.py` must report **0 errors**.
- `pyright app/core/config.py app/core/agents/exceptions.py` must stay at **0 errors**.
- `mypy app/core/agents/` must stay at **≤ 3 errors**.
- pytest collection must be **≥ 337 + 15 = 352 tests** (baseline + new unit tests).

## Files to Create / Modify

| Action | File | Purpose |
|---|---|---|
| CREATE | `app/core/agents/circuit_breaker.py` | `BreakerConfig`, `CircuitState`, `CircuitBreaker`, `CircuitBreakerOpenError` (re-export) |
| UPDATE | `app/core/agents/exceptions.py` | Add `CircuitBreakerOpenError(AgentError)` |
| UPDATE | `app/core/config.py` | 5 new settings after line 293 |
| CREATE | `app/core/agents/tests/test_circuit_breaker.py` | 15+ unit tests |
| UPDATE | `app/core/agents/tests/conftest.py` | Add `make_breaker_config` factory + `ManualClock` helper |
| UPDATE | `docs/logging-standard.md` | Document 6 new `agent.circuit_breaker.*` events (append to agent section) |

**Out of scope (follow-up task AI-8.2):**
- Wiring the breaker into `service.py:_execute()` around each `agent.run()` call
- Per-provider breaker registry keyed by `llm_primary_provider` / `llm_fallback_provider`
- Metric emission to the observability stack (if any)
- Tests that exercise the breaker through `AgentService.chat()`

This task delivers the **primitive + config + exception + exhaustive unit tests**. The wiring is intentionally a separate, reviewable change so it can be gated by the kill switch.

## Implementation Steps

### Step 1 — Add `CircuitBreakerOpenError` to the agent exception hierarchy

**File:** `app/core/agents/exceptions.py`

Add after the existing `AgentError` subclasses (look at the `AgentExecutionError` block for style):

```python
class CircuitBreakerOpenError(AgentError):
    """Raised when an LLM provider circuit breaker is OPEN and rejects a call.

    Maps to HTTP 503 (Service Unavailable) via the agent exception handler.
    The breaker opens after consecutive failures or sliding-window rate
    threshold is exceeded; it auto-recovers via HALF_OPEN probes.
    """
```

Two concrete edits are required:

1. **`agent_exception_handler` (lines 72-76)** — extend the 503 `isinstance` tuple:
   ```python
   elif isinstance(exc, (TransitDataError, ObsidianError, CircuitBreakerOpenError)):
       status_code = status.HTTP_503_SERVICE_UNAVAILABLE
   ```
2. **`setup_agent_exception_handlers` (lines 87-99)** — append one line:
   ```python
   app.add_exception_handler(CircuitBreakerOpenError, handler)
   ```

Do **not** leak internal state (provider names are fine, exception `repr()` of underlying provider errors is not — use a generic message). No existing test asserts on `add_exception_handler.call_count` for the agent handler (the call-count assertion in `app/core/tests/test_exceptions.py:161` is for the unrelated `setup_exception_handlers` — different module, unaffected).

**Validation:**
```
uv run ruff format app/core/agents/exceptions.py && \
uv run ruff check --fix app/core/agents/exceptions.py && \
uv run mypy app/core/agents/exceptions.py && \
uv run pyright app/core/agents/exceptions.py
```

### Step 2 — Add 5 new settings to `app/core/config.py`

**File:** `app/core/config.py`, immediately after line 293 (after `agent_confidence_reroute_threshold`)

```python
    # Circuit breaker (AI-8.1) — LLM provider fast-fail
    circuit_breaker_enabled: bool = True
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_recovery_timeout_s: float = 30.0
    circuit_breaker_success_threshold: int = 2
    circuit_breaker_failure_rate_threshold: float = 0.5
```

Follow pydantic-settings conventions already in the file. No `Field(...)` wrapping unless existing siblings use it. Env var names are auto-derived (`CIRCUIT_BREAKER_ENABLED`, etc.) via the Settings base class config.

**Validation:**
```
uv run ruff format app/core/config.py && \
uv run ruff check --fix app/core/config.py && \
uv run mypy app/core/config.py && \
uv run pyright app/core/config.py
```

Expected: baseline remains 0 errors.

### Step 3 — Create `app/core/agents/circuit_breaker.py`

**File:** `app/core/agents/circuit_breaker.py` (new)

Structure:

```python
"""Circuit breaker state machine for LLM provider resilience (AI-8.1).

Classic 3-state breaker: CLOSED -> OPEN -> HALF_OPEN -> CLOSED.

- CLOSED: all calls pass through. Record success/failure on each outcome.
  Trip to OPEN when either (a) consecutive failures >= failure_threshold
  or (b) failure rate over the last `window_size` calls >= failure_rate_threshold.
- OPEN: all calls rejected with CircuitBreakerOpenError (no provider call).
  After recovery_timeout_s, transition to HALF_OPEN on next call attempt.
- HALF_OPEN: calls pass through as probes. After success_threshold successful
  probes in a row, transition to CLOSED (counters reset). Any failure in
  HALF_OPEN immediately returns to OPEN.

Mirrors the GTFS-RT breaker at app/core/resilience.py but adds sliding-window
rate tracking and a dedicated success-threshold probe path. Kept agent-local
(not in app/shared/) per the three-feature rule.
"""

from __future__ import annotations

import asyncio
import time
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import TypeVar

from app.core.agents.exceptions import CircuitBreakerOpenError
from app.core.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass(frozen=True)
class BreakerConfig:
    failure_threshold: int = 5
    recovery_timeout_s: float = 30.0
    success_threshold: int = 2
    window_size: int = 20
    failure_rate_threshold: float = 0.5

    def __post_init__(self) -> None:
        if self.failure_threshold < 1:
            raise ValueError("failure_threshold must be >= 1")
        if self.recovery_timeout_s < 0:
            raise ValueError("recovery_timeout_s must be >= 0")
        if self.success_threshold < 1:
            raise ValueError("success_threshold must be >= 1")
        if self.window_size < 1:
            raise ValueError("window_size must be >= 1")
        if not 0.0 < self.failure_rate_threshold <= 1.0:
            raise ValueError("failure_rate_threshold must be in (0, 1]")


class CircuitBreaker:
    """Async circuit breaker for a single downstream provider.

    Thread-safe under asyncio via an internal Lock. One instance per provider;
    do not share across providers (each needs independent failure accounting).
    """

    def __init__(
        self,
        name: str,
        config: BreakerConfig | None = None,
        *,
        time_fn: Callable[[], float] = time.monotonic,
    ) -> None:
        self._name = name
        self._config = config or BreakerConfig()
        self._time_fn = time_fn
        self._state: CircuitState = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._consecutive_successes = 0  # used in HALF_OPEN
        self._opened_at: float | None = None
        self._window: deque[bool] = deque(maxlen=self._config.window_size)  # True=success
        self._lock = asyncio.Lock()

    @property
    def name(self) -> str:
        return self._name

    @property
    def state(self) -> CircuitState:
        return self._state

    async def call(
        self,
        fn: Callable[..., Awaitable[T]],
        /,
        *args: object,
        **kwargs: object,
    ) -> T:
        """Invoke `fn(*args, **kwargs)` through the breaker.

        Raises CircuitBreakerOpenError when the breaker is OPEN and the
        recovery timeout has not elapsed. Otherwise invokes `fn`, records
        the outcome, and may transition state.
        """
        await self._before_call()
        try:
            result = await fn(*args, **kwargs)
        except Exception:
            await self._record_failure()
            raise
        await self._record_success()
        return result

    async def _before_call(self) -> None:
        async with self._lock:
            if self._state is CircuitState.OPEN:
                assert_opened = self._opened_at  # narrowing alias
                if assert_opened is None:
                    # Defensive: OPEN without timestamp should be impossible.
                    self._opened_at = self._time_fn()
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker {self._name!r} is OPEN"
                    )
                elapsed = self._time_fn() - assert_opened
                if elapsed >= self._config.recovery_timeout_s:
                    self._transition_to(CircuitState.HALF_OPEN, elapsed_s=elapsed)
                else:
                    logger.info(
                        "agent.circuit_breaker.rejected",
                        provider=self._name,
                        state=self._state.value,
                    )
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker {self._name!r} is OPEN"
                    )

    async def _record_success(self) -> None:
        async with self._lock:
            self._window.append(True)
            if self._state is CircuitState.HALF_OPEN:
                self._consecutive_successes += 1
                logger.info(
                    "agent.circuit_breaker.probe_success",
                    provider=self._name,
                    consecutive_successes=self._consecutive_successes,
                )
                if self._consecutive_successes >= self._config.success_threshold:
                    self._transition_to(
                        CircuitState.CLOSED,
                        successful_probes=self._consecutive_successes,
                    )
            elif self._state is CircuitState.CLOSED:
                self._consecutive_failures = 0

    async def _record_failure(self) -> None:
        async with self._lock:
            self._window.append(False)
            if self._state is CircuitState.HALF_OPEN:
                logger.warning(
                    "agent.circuit_breaker.probe_failure",
                    provider=self._name,
                )
                self._transition_to(CircuitState.OPEN, trigger="probe_failure")
                return
            # CLOSED path
            self._consecutive_failures += 1
            rate = self._failure_rate()
            if self._consecutive_failures >= self._config.failure_threshold:
                self._transition_to(
                    CircuitState.OPEN,
                    trigger="consecutive",
                    failure_count=self._consecutive_failures,
                    failure_rate=rate,
                )
            elif (
                len(self._window) >= self._config.window_size
                and rate >= self._config.failure_rate_threshold
            ):
                self._transition_to(
                    CircuitState.OPEN,
                    trigger="rate",
                    failure_count=self._consecutive_failures,
                    failure_rate=rate,
                )

    def _failure_rate(self) -> float:
        if not self._window:
            return 0.0
        failures = sum(1 for ok in self._window if not ok)
        return failures / len(self._window)

    def _transition_to(self, new_state: CircuitState, **log_fields: object) -> None:
        old_state = self._state
        self._state = new_state
        if new_state is CircuitState.OPEN:
            self._opened_at = self._time_fn()
            self._consecutive_successes = 0
            logger.warning(
                "agent.circuit_breaker.reopened"
                if old_state is CircuitState.HALF_OPEN
                else "agent.circuit_breaker.opened",
                provider=self._name,
                **log_fields,
            )
        elif new_state is CircuitState.HALF_OPEN:
            self._consecutive_successes = 0
            logger.info(
                "agent.circuit_breaker.half_opened",
                provider=self._name,
                **log_fields,
            )
        elif new_state is CircuitState.CLOSED:
            self._consecutive_failures = 0
            self._consecutive_successes = 0
            self._opened_at = None
            self._window.clear()
            logger.info(
                "agent.circuit_breaker.closed",
                provider=self._name,
                **log_fields,
            )
```

**Notes on the implementation:**
- `call()` is **positional-only** for `fn` (via `/`) so `*args` of the target can't collide.
- `_before_call` / `_record_*` are split into 3 lock acquisitions — the actual `fn` invocation happens **outside** the lock (never hold a lock across `await` to an external service). This matches `app/core/resilience.py` behavior.
- `window.maxlen` auto-evicts old entries, no manual pruning.
- `Any` is avoided; `object` for `**log_fields: object` is fine since structlog accepts arbitrary kwargs (pyright-compatible).
- `TypeVar T` gives `call()` precise return typing.
- The `assert_opened` alias avoids pyright `reportOptionalMemberAccess` on `self._opened_at`.
- Anti-pattern rule 2: no `object` parameter that we then isinstance-check. `*args: object` / `**kwargs: object` is passed through as-is — we never narrow them.
- Anti-pattern rule 33: **kwargs forwarded as `object`, not `Any`, because we never unpack them into a Pydantic model.
- Anti-pattern rule 37: no bare `except: pass`. The outer `try/except Exception` re-raises after recording.

**Validation:**
```
uv run ruff format app/core/agents/circuit_breaker.py && \
uv run ruff check --fix app/core/agents/circuit_breaker.py && \
uv run mypy app/core/agents/circuit_breaker.py && \
uv run pyright app/core/agents/circuit_breaker.py
```

Target: 0 errors / 0 warnings on the new file.

### Step 4 — Extend `conftest.py` with breaker factory + `ManualClock`

**File:** `app/core/agents/tests/conftest.py`

Append (do not modify existing fixtures):

```python
from app.core.agents.circuit_breaker import BreakerConfig, CircuitBreaker


class ManualClock:
    """Deterministic monotonic clock for circuit-breaker tests.

    Instances are callable — pass as `time_fn=clock` to CircuitBreaker.
    Advance with `.advance(seconds)`.
    """

    def __init__(self, start: float = 0.0) -> None:
        self.now: float = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def make_breaker_config(**overrides: object) -> BreakerConfig:
    """BreakerConfig factory with fast defaults for unit tests."""
    defaults: dict[str, object] = {
        "failure_threshold": 3,
        "recovery_timeout_s": 10.0,
        "success_threshold": 2,
        "window_size": 10,
        "failure_rate_threshold": 0.5,
    }
    defaults.update(overrides)
    return BreakerConfig(**defaults)  # type: ignore[arg-type]


def make_breaker(
    name: str = "test-provider",
    *,
    config: BreakerConfig | None = None,
    clock: ManualClock | None = None,
) -> CircuitBreaker:
    """CircuitBreaker factory wired to an optional ManualClock."""
    clock = clock or ManualClock()
    return CircuitBreaker(
        name=name,
        config=config or make_breaker_config(),
        time_fn=clock,
    )
```

**Note on the `# type: ignore`:** The `BreakerConfig(**defaults)` call expands a `dict[str, object]` which pyright/mypy cannot statically verify against the dataclass field types. Anti-pattern rule 33 says prefer `dict[str, Any]`, but in conftest we can't import `typing.Any` without adding noise; the single targeted `# type: ignore[arg-type]` is the smallest fix. Alternatively, switch `defaults` to `dict[str, Any]` — **pick whichever the pre-commit hook leaves green on first pass**.

**Validation:**
```
uv run ruff format app/core/agents/tests/conftest.py && \
uv run ruff check --fix app/core/agents/tests/conftest.py && \
uv run mypy app/core/agents/tests/conftest.py && \
uv run pyright app/core/agents/tests/conftest.py
```

### Step 5 — Write `test_circuit_breaker.py`

**File:** `app/core/agents/tests/test_circuit_breaker.py` (new)

Test list (≥ 15 tests, all `-> None` annotated per anti-pattern rule 26):

**State transitions (6):**
1. `test_starts_closed` — New breaker has `state == CLOSED` and allows calls.
2. `test_closed_to_open_on_consecutive_failures` — 3 sequential failures (threshold=3) → OPEN, 4th call raises `CircuitBreakerOpenError` without invoking fn.
3. `test_closed_to_open_on_sliding_window_rate` — fill window_size=10 with 5 failures + 5 successes below consecutive threshold → rate = 0.5 → trips.
4. `test_open_to_half_open_after_recovery_timeout` — Advance `ManualClock` past `recovery_timeout_s` → next call transitions to HALF_OPEN and invokes fn.
5. `test_half_open_to_closed_after_success_threshold` — 2 successful probes (success_threshold=2) → CLOSED, counters reset.
6. `test_half_open_to_open_on_any_failure` — First probe fails → immediately OPEN, no second probe allowed until next recovery timeout.

**Failure counting & success reset (3):**
7. `test_success_in_closed_resets_consecutive_failures` — failure, failure, success, failure, failure → still CLOSED (not 3 consecutive).
8. `test_window_pruning_at_maxlen` — fill window beyond window_size, oldest entries evicted, rate computed only over last `window_size`.
9. `test_failure_rate_threshold_needs_full_window` — 2 failures out of 2 calls (100% rate but window not full) should NOT trip on rate (only on consecutive count if threshold met).

**Recovery timeout (2):**
10. `test_call_rejected_before_recovery_timeout` — OPEN + clock advanced `recovery_timeout_s - 0.01` → rejection, fn not invoked.
11. `test_recovery_probe_exactly_at_timeout` — elapsed == `recovery_timeout_s` → transitions to HALF_OPEN (boundary: `>=`).

**Sliding window rate (2):**
12. `test_rate_resets_after_close` — trip on rate, recover via probes, verify `_window` cleared on CLOSE.
13. `test_consecutive_does_not_count_old_failures_after_success` — f,f,s,f → `_consecutive_failures` is 1 (success reset), NOT 3.

**Concurrent calls (2):**
14. `test_concurrent_calls_share_state_atomically` — 10 `asyncio.gather` tasks all failing concurrently, exactly `failure_threshold` of them record before state flips (use a counter in the fake fn). Verify final state is OPEN and subsequent calls are rejected.
15. `test_half_open_only_allows_single_probe_at_a_time` — While one probe is in-flight (use `asyncio.Event`), a second concurrent call is rejected. *(If the lock-release-during-await semantics make this hard, substitute with: two sequential probes succeed → CLOSED.)*

**Config gating & invariants (3):**
16. `test_breaker_config_validates_inputs` — `BreakerConfig(failure_threshold=0)` raises `ValueError`; same for negative recovery_timeout, bad rate, etc.
17. `test_exception_type_is_preserved` — `fn` raising `RuntimeError("boom")` → `RuntimeError` re-raised (breaker does NOT swallow).
18. `test_log_events_emitted` — Use `caplog` / structlog capture to assert `agent.circuit_breaker.opened` fires on first trip with `provider="test-provider"` and `trigger="consecutive"`.

**Test skeleton example (share with planner for style):**

```python
import asyncio

import pytest

from app.core.agents.circuit_breaker import (
    BreakerConfig,
    CircuitBreaker,
    CircuitState,
)
from app.core.agents.exceptions import CircuitBreakerOpenError
from app.core.agents.tests.conftest import (
    ManualClock,
    make_breaker,
    make_breaker_config,
)


async def _fail() -> None:
    raise RuntimeError("boom")


async def _ok() -> str:
    return "ok"


@pytest.mark.asyncio
async def test_starts_closed() -> None:
    breaker = make_breaker()
    assert breaker.state is CircuitState.CLOSED
    assert await breaker.call(_ok) == "ok"


@pytest.mark.asyncio
async def test_closed_to_open_on_consecutive_failures() -> None:
    breaker = make_breaker(config=make_breaker_config(failure_threshold=3))
    for _ in range(3):
        with pytest.raises(RuntimeError):
            await breaker.call(_fail)
    assert breaker.state is CircuitState.OPEN
    call_count = 0

    async def counting_fn() -> None:
        nonlocal call_count
        call_count += 1

    with pytest.raises(CircuitBreakerOpenError):
        await breaker.call(counting_fn)
    assert call_count == 0


@pytest.mark.asyncio
async def test_open_to_half_open_after_recovery_timeout() -> None:
    clock = ManualClock()
    breaker = make_breaker(
        config=make_breaker_config(failure_threshold=2, recovery_timeout_s=10.0),
        clock=clock,
    )
    for _ in range(2):
        with pytest.raises(RuntimeError):
            await breaker.call(_fail)
    assert breaker.state is CircuitState.OPEN

    clock.advance(10.0)
    # Next call should probe (half-open) and succeed
    assert await breaker.call(_ok) == "ok"
    assert breaker.state is CircuitState.HALF_OPEN
```

**Validation:**
```
uv run ruff format app/core/agents/tests/test_circuit_breaker.py && \
uv run ruff check --fix app/core/agents/tests/test_circuit_breaker.py && \
uv run mypy app/core/agents/tests/test_circuit_breaker.py && \
uv run pyright app/core/agents/tests/test_circuit_breaker.py && \
uv run pytest app/core/agents/tests/test_circuit_breaker.py -v
```

Target: all tests pass, 0 type errors.

### Step 6 — Document new log events

**File:** `docs/logging-standard.md`

Append to the `agent.*` section a row for each of the 6 new events (opened / half_opened / closed / reopened / rejected / probe_success / probe_failure) with fields and severity. Keep it to ~8 lines total. Do NOT restructure the existing taxonomy — this is a pure append.

**Validation:** visual review only.

### Step 7 — Full suite validation

```
uv run ruff format app/ && \
uv run ruff check --fix app/ && \
uv run mypy app/core/agents/ app/core/config.py app/core/exceptions.py && \
uv run pyright app/core/agents/ app/core/config.py && \
uv run pytest app/core/agents/tests/ -v && \
uv run pytest app/tests/test_security.py -v
```

Expected: all green, pyright ≤ 5 errors (baseline), mypy ≤ 3 errors (baseline), pytest ≥ 352 tests collected.

## Preflight Warnings

From the research + test-scout findings:

1. **Never hold `asyncio.Lock` across the `fn` invocation.** The reference `app/core/resilience.py` is careful about this. `_before_call` / `_record_success` / `_record_failure` each acquire/release — the actual awaited call happens outside any lock. Violating this would serialize all LLM calls, which is catastrophic.
2. **`CircuitState` enum identity comparison.** Use `is` (e.g., `state is CircuitState.CLOSED`), not `==`, to avoid pyright union-narrowing issues. This matches `app/core/resilience.py`.
3. **Anti-pattern rule 39** — there's no `date` field anywhere here, so `import datetime` is not required. Use `time.monotonic` (stdlib) for the clock.
4. **`structlog` kwargs** — passing `**log_fields: object` is fine for structlog.BoundLogger which accepts arbitrary kwargs. Pyright won't complain.
5. **`ManualClock.now` mutation** is deliberately public (no setter needed). Tests call `clock.advance(s)` not `clock.now += s` for clarity, but both work.
6. **Config dataclass is frozen** — `BreakerConfig` uses `frozen=True` so instances are hashable. `__post_init__` validation runs on construction — test invariants land in `test_breaker_config_validates_inputs`.
7. **The 3 mypy errors and 5 pyright errors in the agents module are pre-existing** and all in files we are NOT touching. If they flip red after this change, we introduced them.
8. **Test file collection order**: `conftest.py` fixtures must be valid for the whole directory — don't break existing 337 tests when adding `ManualClock`. Run the full `app/core/agents/tests/` directory in validation to catch import-time regressions.

## Security Checklist (CTX-AGENT + CTX-INFRA)

- [ ] No provider credentials in log fields. Only `provider` (name string), `state`, counters, `elapsed_s`, `trigger`.
- [ ] `CircuitBreakerOpenError.__str__` / handler returns generic message — no raw upstream exception text leaked to HTTP response.
- [ ] Kill switch: `circuit_breaker_enabled=False` fully disables the breaker (follow-up wiring step must honor this).
- [ ] New settings are pydantic-settings (env-var-backed) — no hardcoded constants in module code.
- [ ] No new endpoints, no new routes, no new RBAC surface. `app/tests/test_security.py` remains unaffected.
- [ ] `make security-audit-quick` passes.
- [ ] No `except: pass`, no suppressions (`# type: ignore` / `# noqa`) in production code beyond the single documented conftest `# type: ignore[arg-type]`.

## Verification

- [ ] `uv run ruff format app/` — clean
- [ ] `uv run ruff check app/` — clean
- [ ] `uv run mypy app/core/agents/` — ≤ 3 errors (baseline)
- [ ] `uv run mypy app/core/config.py app/core/agents/exceptions.py` — 0 errors
- [ ] `uv run pyright app/core/agents/` — ≤ 5 errors (baseline)
- [ ] `uv run pyright app/core/agents/circuit_breaker.py app/core/agents/tests/test_circuit_breaker.py` — 0 errors
- [ ] `uv run pytest app/core/agents/tests/ -v` — 337 + ≥15 tests pass
- [ ] `uv run pytest app/tests/test_security.py -v` — all convention tests pass
- [ ] `make security-audit-quick` — passes
- [ ] Manual read: `docs/logging-standard.md` has 6 new event rows documented
- [ ] No changes to `pyproject.toml`, `app/main.py`, or `alembic/` (no deps, no routes, no migrations)

## Acceptance Criteria

From the user's task definition:

- [x] `app/core/agents/circuit_breaker.py` exists with `BreakerConfig`, `CircuitState` (via re-use/redeclare), `CircuitBreaker`, and raises `CircuitBreakerOpenError`
- [x] `BreakerConfig` has exact defaults: `failure_threshold=5`, `recovery_timeout_s=30.0`, `success_threshold=2`, `window_size=20`, `failure_rate_threshold=0.5`
- [x] State transitions implemented per spec: CLOSED→OPEN (consecutive or rate), OPEN→HALF_OPEN (timeout), HALF_OPEN→CLOSED (success_threshold), HALF_OPEN→OPEN (any failure)
- [x] `asyncio.Lock` guards all state reads/writes; lock never held across the `fn` await
- [x] `app/core/config.py` has 5 new settings with correct names and defaults
- [x] 6 log events in the `agent.circuit_breaker.*` namespace, all emitted by the state machine
- [x] ≥15 unit tests covering the 6 transition categories
- [x] Verify scenario from the task: mock provider fails 5 times → breaker opens → 6th call raises `CircuitBreakerOpenError` without invoking provider → after `recovery_timeout_s`, HALF_OPEN, 2 successful probes → CLOSED.
