# Plan: AI-8.2 — Per-Provider Health Metrics + Admin Endpoint

## Context

Ops currently has zero visibility into which LLM provider is degrading.
Failures surface only as GlitchTip errors or user-reported slow responses.
AI-8.1 landed the `CircuitBreaker` primitive but didn't wire it into
`_execute()` yet — that wiring is deferred. AI-8.2 adds the observability
half: a `ProviderHealthTracker` singleton recording per-provider
success/failure counts + p50/p95 latency + last failure timestamp + current
breaker state, exposed via admin-only `GET /v1/chat/provider-health`.

Pattern mirrors `CorrectionMetricsTracker` from AI-5.3 (lazy 00:00 UTC
daily reset, module-level singleton, `clock=` injection for tests).

## Security Context Assessment

Active contexts from `_shared/security-contexts.md`:

- **CTX-AGENT** — Response is LLM-adjacent. No prompt injection surface
  (GET endpoint, no user input), but tool/endpoint must never expose
  credentials, API keys, connection strings, or raw exception repr in
  responses or logs. Provider name is an enum-like identifier only.
- **CTX-RBAC** — New admin-only endpoint. Must use `require_role("admin")`
  (not bare `get_current_user`), must be rate-limited, and must ship with
  both an admin-200 test and a dispatcher-403 test. `TestAllEndpointsRequireAuth`
  in `app/tests/test_security.py:666` auto-discovers the new endpoint and
  will fail CI if auth is missing.

Inactive: CTX-AUTH (no auth flow changes), CTX-FILE (no uploads),
CTX-INFRA (no Docker/nginx/CORS), CTX-INPUT (no user-supplied parameters
on the endpoint — just a GET with admin auth).

## Research Summary

### Key divergence from user spec

**The user's spec targets `app/core/agents/llm.py` — that file does not exist.**
Provider invocation lives in three code paths across `service.py` and
indirectly through `pipeline.py`:

| Call site | File:Line | Path |
|-----------|-----------|------|
| Complex tier (outer) | `service.py:268` | `await pipeline.run(...)` |
| Correction loop | `service.py:293` | `await self._correction_loop.run_with_correction(...)` |
| Fallback `agent.run` | `service.py:321` | `await agent.run(...)` |
| Complex sub-phase | `pipeline.py:131` | per-phase `agent.run` inside `pipeline.run()` |

**Decision:** instrument the three sites in `service.py` (outer
call-wrapping). One logical LLM call per chat request, regardless of
internal retries. Do NOT instrument `pipeline.py:131` — it would
double-count complex-tier requests and `pipeline.py` already has 3
pre-existing pyright errors we must not perturb. Document this choice in
the plan file and in the provider_health.py module docstring.

### Reference pattern — metrics.py (AI-5.3)

File: `app/core/agents/metrics.py` (175 lines). The *exact* template:

- `@dataclass` for per-entity counters (we mirror with `ProviderHealth`)
- `class CorrectionMetricsTracker` with `clock: Callable[[], datetime] | None = None`
  injection for deterministic testing
- `_maybe_reset()` called at the top of every public method, compares
  `self._clock().date()` to `self._reset_date`, clears dict + advances
  date on rollover (metrics.py:74-79)
- `snapshot()` returns a deep-copied dict (metrics.py:126-129) so callers
  can't mutate internal state
- `period_start()` returns `datetime.combine(self._reset_date, time.min, tzinfo=UTC)`
  (metrics.py:131-138)
- Module-level singleton: `_metrics_tracker: CorrectionMetricsTracker | None`
  + `get_metrics_tracker()` (lazy init) + `reset_metrics_tracker()` (test-only)
  (metrics.py:150-166)
- `__all__` explicit export list

### Circuit breaker state exposure

`app/core/agents/circuit_breaker.py` is wired for state queries:

- `CircuitState` enum: `CLOSED` / `OPEN` / `HALF_OPEN` (circuit_breaker.py:37-42)
- `CircuitBreaker.state` read-only property (circuit_breaker.py:99-102)
- `CircuitBreaker.name` read-only property (circuit_breaker.py:94-97)

**Per-provider breaker registry does NOT yet exist.** AI-8.1 shipped the
primitive but wiring into `_execute()` was deferred (see `app/core/agents/CLAUDE.md`:
"**Out of scope (AI-8.2 follow-up):** wiring into `_execute()` + per-provider
registry, gated by the `circuit_breaker_enabled` kill switch.").

**Decision:** AI-8.2 adds the *tracker* and the *endpoint*, NOT the breaker
registry. The tracker accepts an optional `state: CircuitState = CircuitState.CLOSED`
parameter on `record_call`. Until `_execute()` is wired in a follow-up PR,
the snapshot will always show `state="closed"` — that's correct behavior
(no live breaker ⇒ calls pass through). A TODO comment in provider_health.py
points at the follow-up. This avoids coupling 8.2 to breaker wiring and
keeps pyright clean on `service.py` (no new `BreakerRegistry` injection).

### Routes pattern — `/chat/metrics` (copy exactly)

File: `app/core/agents/routes.py:113-175`. Exact decorator stack and
imports to mirror:

```python
@router.get("/chat/provider-health", response_model=ProviderHealthResponse)
@limiter.limit("60/minute")   # health endpoints: 60/min (same as /v1/models)
async def get_provider_health(
    request: Request,
    _admin: User = Depends(require_role("admin")),
) -> ProviderHealthResponse:
    ...
```

Existing imports in `routes.py`:

- `from app.auth.dependencies import get_current_user, require_role` (line 14)
- `from app.auth.models import User` (already imported)
- `from app.core.rate_limit import _get_client_ip, limiter` (line 30)

### Schemas pattern — extend `schemas.py`

File: `app/core/agents/schemas.py`. Pattern: small nested `*Snapshot`
model + wrapper `*Response` model, both with `model_config = ConfigDict(strict=True)`.
Append at end of file (after `CorrectionMetricsResponse`, ~line 166).

### Provider name extraction

`tier_model` is one of `None` / `str` / `pydantic_ai.Model` instance
(see `app/core/agents/config.py:113-172`). Provider extraction:

- `None` → `settings.llm_provider` (app/core/config.py:60, default `"test"`)
- `str` like `"anthropic:claude-sonnet"` → `model_str.split(":", 1)[0]`
- `Model` instance → `type(model).__name__.lower().removesuffix("model")`
  (e.g. `AnthropicModel` → `"anthropic"`, `GoogleModel` → `"google"`)

Provider name set: `anthropic`, `google`, `groq`, `ollama`, `test`. Helper
`_extract_provider_name(tier_model, default)` lives in `provider_health.py`
and is covered by its own unit test (don't inline it in `service.py`).

### Settings — no new env vars

Per the user's spec, AI-8.2 does not introduce a kill switch. The tracker
is always-on (zero-overhead when there are no calls). If a rollback
becomes necessary, the instrumentation sites in `service.py` can be
wrapped in a `try/except Exception: pass` — already planned per fail-open
requirement.

## Test Landscape

### Reference test file — test_metrics.py

File: `app/core/agents/tests/test_metrics.py` (247 lines). Structure we
copy:

- Module-level `limiter.enabled = False` (line 23) — mandatory per
  python-anti-patterns.md #13; this line must come AFTER all imports
- `_mock_admin_user()` + `_mock_dispatcher_user()` helpers (lines 26-41)
- `@pytest.fixture(autouse=True) def _reset_singleton()` calling
  `reset_*_tracker()` before and after each test (lines 44-49)
- `@pytest.fixture def _admin_override()` that pushes
  `app.dependency_overrides[get_current_user] = _mock_admin_user` and
  pops it in the teardown (lines 52-56) — the `try/finally` pattern is
  mandatory to prevent leak between test modules (python-anti-patterns.md #56)
- Daily-reset test (lines 93-109) uses a mutable-closure `clock()` + a
  `fake_now` variable that the test advances with `fake_now += timedelta(days=1)`
  — deterministic, no freezegun required
- Admin 403 test (lines 238-246) uses `_mock_dispatcher_user` override and
  asserts `response.json()["detail"] == "Insufficient permissions"`

### Existing fixtures in conftest.py

File: `app/core/agents/tests/conftest.py` (154 lines):

- `_reset_skill_cache` autouse (lines 64-69) — same singleton-reset idiom
- `ManualClock` class (lines 111-126) — used by circuit_breaker tests;
  we don't need it (clock-as-callable is simpler for `ProviderHealthTracker`)
- No existing provider-call mocks — we mock `agent.run`/`pipeline.run`/
  `correction_loop.run_with_correction` at the *service.py* module level,
  not at pydantic_ai level

### Convention test auto-detection

`app/tests/test_security.py::TestAllEndpointsRequireAuth` (lines 666-739)
discovers all routes via `rglob("routes.py")`, inspects function sources
for `require_role` or `get_current_user` references, and fails any
non-allowlisted endpoint that lacks auth. The new
`get_provider_health` function contains `Depends(require_role("admin"))`
so it passes automatically — no allowlist change required.

## Type Check Baseline

Baseline for files touched by AI-8.2 (captured on current `main`):

| File | pyright | mypy | Notes |
|---|---|---|---|
| `app/core/agents/service.py` | 0 | 0 | clean — do not regress |
| `app/core/agents/routes.py` | 0 | 0 | clean — do not regress |
| `app/core/agents/schemas.py` | 0 | 0 | clean — do not regress |
| `app/core/agents/pipeline.py` | **3** | **1** | pre-existing — DO NOT fix, DO NOT regress |
| `app/core/agents/base.py` | 0 | 0 | untouched |
| `app/core/agents/` (module total) | **5** | **3** | — |

**Pre-existing `pipeline.py` errors (do not touch):**

1. `pipeline.py:47` pyright `reportUnknownVariableType` — `phases_completed: list[Unknown]`
2. `pipeline.py:49` pyright `reportUnknownVariableType` — `phase_details: list[Unknown]`
3. `pipeline.py:136` pyright `reportArgumentType` — `Argument of type "object | None" cannot be assigned to parameter "model"`
4. `pipeline.py:136` mypy `arg-type` — same root cause

**Unrelated module errors (out of scope):**

- `app/core/agents/tools/transit/static_store.py:149,150` mypy — async iterable typing
- `app/core/agents/tools/transit/client.py:193` pyright — possibly unbound

**Post-implementation gate:** `uv run pyright app/core/agents/` must report
≤5 errors; `uv run mypy app/core/agents/` must report ≤3 errors. New files
`provider_health.py` + `tests/test_provider_health.py` must land at 0 errors.

## Files to Create/Modify

| Action | File | Purpose |
|--------|------|---------|
| CREATE | `app/core/agents/provider_health.py` | `ProviderHealth` dataclass, `ProviderHealthTracker` class, singleton accessors, `_extract_provider_name` helper |
| CREATE | `app/core/agents/tests/test_provider_health.py` | Tracker unit tests + admin endpoint tests (≥12 tests) |
| UPDATE | `app/core/agents/schemas.py` | Add `ProviderHealthSnapshot`, `ProviderHealthResponse` |
| UPDATE | `app/core/agents/routes.py` | Add `GET /v1/chat/provider-health` endpoint |
| UPDATE | `app/core/agents/service.py` | Instrument 3 call sites (complex, correction, fallback) with `record_call` wrapper |
| UPDATE | `app/core/agents/CLAUDE.md` | 1-line entry in the "Planned Improvements" table for AI-8.2 and new file in directory tree |

## Implementation Steps

### Step 1 — `app/core/agents/provider_health.py` (CREATE)

Create the tracker module following metrics.py line-for-line. Key elements:

```python
"""Per-provider LLM health metrics tracker (AI-8.2)."""

from __future__ import annotations

import datetime
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from statistics import quantiles
from typing import TYPE_CHECKING, Any

from app.core.agents.circuit_breaker import CircuitState
from app.core.logging import get_logger

if TYPE_CHECKING:
    from pydantic_ai.models import Model  # type: ignore[import-not-found]

logger = get_logger(__name__)

_LATENCY_WINDOW = 100  # last N call latencies for p50/p95


@dataclass
class ProviderHealth:
    provider_name: str
    state: CircuitState = CircuitState.CLOSED
    total_calls: int = 0
    total_failures: int = 0
    last_failure_at: datetime.datetime | None = None
    last_success_at: datetime.datetime | None = None
    _latencies_ms: deque[float] = field(
        default_factory=lambda: deque(maxlen=_LATENCY_WINDOW)
    )

    @property
    def failure_rate(self) -> float:
        return self.total_failures / self.total_calls if self.total_calls else 0.0

    def _percentile(self, pct: int) -> float | None:
        """Return the requested percentile or None if <2 observations."""
        if len(self._latencies_ms) < 2:
            return None
        # quantiles(n=100) requires ≥2 data points; return slice at pct-1
        qs = quantiles(self._latencies_ms, n=100, method="inclusive")
        return qs[pct - 1]

    @property
    def p50_latency_ms(self) -> float | None:
        return self._percentile(50)

    @property
    def p95_latency_ms(self) -> float | None:
        return self._percentile(95)


class ProviderHealthTracker:
    """Per-provider health metrics with lazy UTC daily reset."""

    def __init__(
        self,
        *,
        clock: Callable[[], datetime.datetime] | None = None,
    ) -> None:
        self._clock = clock or _utc_now
        self._reset_date: datetime.date = self._clock().date()
        self._providers: dict[str, ProviderHealth] = {}

    def _maybe_reset(self) -> None:
        today = self._clock().date()
        if today != self._reset_date:
            self._providers.clear()
            self._reset_date = today

    def record_call(
        self,
        provider: str,
        *,
        latency_ms: float,
        success: bool,
        state: CircuitState = CircuitState.CLOSED,
    ) -> None:
        self._maybe_reset()
        entry = self._providers.setdefault(
            provider, ProviderHealth(provider_name=provider)
        )
        entry.total_calls += 1
        entry._latencies_ms.append(latency_ms)
        entry.state = state
        now = self._clock()
        if success:
            entry.last_success_at = now
        else:
            entry.total_failures += 1
            entry.last_failure_at = now

    def get_health(self, provider: str) -> ProviderHealth | None:
        self._maybe_reset()
        return self._providers.get(provider)

    def get_all(self) -> list[ProviderHealth]:
        self._maybe_reset()
        return [
            ProviderHealth(
                provider_name=p.provider_name,
                state=p.state,
                total_calls=p.total_calls,
                total_failures=p.total_failures,
                last_failure_at=p.last_failure_at,
                last_success_at=p.last_success_at,
                _latencies_ms=deque(p._latencies_ms, maxlen=_LATENCY_WINDOW),
            )
            for p in sorted(self._providers.values(), key=lambda x: x.provider_name)
        ]

    def period_start(self) -> datetime.datetime:
        self._maybe_reset()
        return datetime.datetime.combine(
            self._reset_date, datetime.time.min, tzinfo=datetime.UTC
        )

    def reset(self) -> None:
        """Test-only: force-clear counters without rolling the date."""
        self._providers.clear()


def _utc_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC)


def _extract_provider_name(
    tier_model: "str | Model | None", default: str
) -> str:
    """Resolve a provider name from the tier_model value.

    TODO(AI-8.2-followup): when `_execute()` is wired to a per-provider
    BreakerRegistry, replace `default` with `settings.llm_provider` at
    call sites and also pass the live CircuitState into record_call().
    """
    if tier_model is None:
        return default
    if isinstance(tier_model, str):
        return tier_model.split(":", 1)[0] or default
    # pydantic_ai.Model instance
    cls_name = type(tier_model).__name__.lower()
    return cls_name.removesuffix("model") or default


_health_tracker: ProviderHealthTracker | None = None


def get_provider_health_tracker() -> ProviderHealthTracker:
    global _health_tracker
    if _health_tracker is None:
        _health_tracker = ProviderHealthTracker()
    return _health_tracker


def reset_provider_health_tracker() -> None:
    global _health_tracker
    _health_tracker = None


__all__ = [
    "ProviderHealth",
    "ProviderHealthTracker",
    "_extract_provider_name",
    "get_provider_health_tracker",
    "reset_provider_health_tracker",
]
```

**Notes:**

- `deque` field uses `default_factory=lambda: deque(maxlen=_LATENCY_WINDOW)`
  (python-anti-patterns.md #24 — typed lambda factory).
- `quantiles(method="inclusive")` is the pandas-compatible default;
  requires ≥2 data points, so `_percentile()` gates on `len(...) < 2`.
- `get_all()` deep-copies via new `ProviderHealth` construction — callers
  cannot mutate internal state (same guarantee as `metrics.snapshot()`).
- `_latencies_ms` is a leading-underscore private field; pyright will not
  warn because it's typed via `field(...)`. Do NOT expose it in the
  response schema.
- Avoid `from pydantic_ai.models import Model` at runtime — use
  `TYPE_CHECKING` block to keep the tracker importable in tests without
  triggering pydantic_ai's heavy import chain.

**Validation:** `uv run ruff format app/core/agents/provider_health.py && uv run ruff check --fix app/core/agents/provider_health.py && uv run pyright app/core/agents/provider_health.py && uv run mypy app/core/agents/provider_health.py`

### Step 2 — `app/core/agents/schemas.py` (UPDATE)

Append to the end of schemas.py:

```python
# --- AI-8.2: Per-provider LLM health ---


class ProviderHealthSnapshot(BaseModel):
    """Per-provider health + circuit breaker state."""

    model_config = ConfigDict(strict=True)

    provider_name: str
    state: str  # "closed" | "open" | "half_open" — CircuitState.value
    total_calls: int
    total_failures: int
    failure_rate: float
    p50_latency_ms: float | None
    p95_latency_ms: float | None
    last_failure_at: datetime.datetime | None
    last_success_at: datetime.datetime | None


class ProviderHealthResponse(BaseModel):
    """Response for GET /v1/chat/provider-health (admin-only)."""

    model_config = ConfigDict(strict=True)

    period_start: datetime.datetime
    generated_at: datetime.datetime
    providers: list[ProviderHealthSnapshot]
```

**Notes:** `state` is typed as `str`, NOT `Literal["closed","open","half_open"]`,
because the endpoint serializes `CircuitState.value` (which is a plain
string). If a future typo in the enum produces an invalid string, we want
the Pydantic error at the API boundary, not a runtime `Literal` crash.

**Validation:** `uv run ruff format app/core/agents/schemas.py && uv run pyright app/core/agents/schemas.py && uv run mypy app/core/agents/schemas.py`

### Step 3 — `app/core/agents/routes.py` (UPDATE)

Add imports at top (merge with existing):

```python
from app.core.agents.provider_health import get_provider_health_tracker
from app.core.agents.schemas import (
    ...,  # existing
    ProviderHealthResponse,
    ProviderHealthSnapshot,
)
```

Append endpoint after `get_correction_metrics` (after line 175):

```python
@router.get("/chat/provider-health", response_model=ProviderHealthResponse)
@limiter.limit("60/minute")
async def get_provider_health(
    request: Request,
    _admin: User = Depends(require_role("admin")),
) -> ProviderHealthResponse:
    """Return per-LLM-provider health metrics for the current UTC day.

    Admin-only. Counters reset at 00:00 UTC. Exposes success/failure counts,
    p50/p95 latency over the last 100 calls per provider, last failure
    timestamp, and current circuit breaker state. Use this to detect
    provider degradation before users report slow responses.

    Args:
        request: Incoming HTTP request (required by slowapi).
        _admin: Injected admin user (RBAC enforcement only).

    Returns:
        Per-provider snapshots plus period metadata.
    """
    tracker = get_provider_health_tracker()
    providers = [
        ProviderHealthSnapshot(
            provider_name=p.provider_name,
            state=p.state.value,
            total_calls=p.total_calls,
            total_failures=p.total_failures,
            failure_rate=p.failure_rate,
            p50_latency_ms=p.p50_latency_ms,
            p95_latency_ms=p.p95_latency_ms,
            last_failure_at=p.last_failure_at,
            last_success_at=p.last_success_at,
        )
        for p in tracker.get_all()
    ]
    return ProviderHealthResponse(
        period_start=tracker.period_start(),
        generated_at=datetime.datetime.now(datetime.UTC),
        providers=providers,
    )
```

**Decorator order (must match existing `/chat/metrics`):** `@router.get` → `@limiter.limit` → `async def` with `request: Request` as first parameter (slowapi requirement), `_admin` second.

**Validation:** `uv run ruff format app/core/agents/routes.py && uv run pyright app/core/agents/routes.py && uv run mypy app/core/agents/routes.py`

### Step 4 — `app/core/agents/service.py` (UPDATE)

Add a private helper inside `BaseAgentService._dispatch(...)` or at
module-level that wraps an awaitable with health tracking. Keep
instrumentation fail-open: if `record_call` itself raises, the LLM
call result is returned normally.

Imports to add:

```python
import time  # if not already imported
from app.core.agents.provider_health import (
    _extract_provider_name,
    get_provider_health_tracker,
)
from app.core.config import get_settings  # already imported — verify
```

Instrumentation pattern (apply to all 3 sites in `service.py`):

```python
# Before each LLM call
_tracker = get_provider_health_tracker()
_settings = get_settings()
_provider = _extract_provider_name(tier_model, _settings.llm_provider)
_t0 = time.monotonic()
try:
    <existing await call — unchanged>
    _latency_ms = (time.monotonic() - _t0) * 1000
    try:
        _tracker.record_call(
            _provider, latency_ms=_latency_ms, success=True
        )
    except Exception:  # noqa: BLE001 — fail-open, never block LLM calls
        logger.warning("agent.provider_health.record_failed", exc_info=True)
except Exception:
    _latency_ms = (time.monotonic() - _t0) * 1000
    try:
        _tracker.record_call(
            _provider, latency_ms=_latency_ms, success=False
        )
    except Exception:  # noqa: BLE001
        logger.warning("agent.provider_health.record_failed", exc_info=True)
    raise
```

**Target call sites (exact lines — unchanged from baseline):**

1. **service.py:268** — `pipeline_result = await pipeline.run(...)` (complex tier)
2. **service.py:293** — `corrected = await self._correction_loop.run_with_correction(...)` (standard + correction)
3. **service.py:321** — `result = await agent.run(...)` (fallback, no correction)

**Refactor to avoid triplication:** Extract a single async context
manager or helper to avoid copying the try/except block three times:

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def _track_provider_call(
    tier_model: str | Model | None,
    default_provider: str,
) -> AsyncIterator[None]:
    tracker = get_provider_health_tracker()
    provider = _extract_provider_name(tier_model, default_provider)
    t0 = time.monotonic()
    try:
        yield
    except Exception:
        latency_ms = (time.monotonic() - t0) * 1000
        try:
            tracker.record_call(provider, latency_ms=latency_ms, success=False)
        except Exception:  # noqa: BLE001
            logger.warning("agent.provider_health.record_failed", exc_info=True)
        raise
    else:
        latency_ms = (time.monotonic() - t0) * 1000
        try:
            tracker.record_call(provider, latency_ms=latency_ms, success=True)
        except Exception:  # noqa: BLE001
            logger.warning("agent.provider_health.record_failed", exc_info=True)
```

This helper lives at module level in `service.py` (or `provider_health.py`
and is imported). Decision: place it in `provider_health.py` as
`track_provider_call()` — cleaner separation; service.py just imports and
uses it.

Apply at each call site:

```python
async with track_provider_call(tier_model, settings.llm_provider):
    pipeline_result = await pipeline.run(...)
```

**Regression guard:** after this step, `uv run pyright app/core/agents/service.py`
must still report 0 errors. `pipeline.py` errors unchanged (3 pyright / 1 mypy).

**Validation:** `uv run ruff format app/core/agents/service.py app/core/agents/provider_health.py && uv run pyright app/core/agents/service.py app/core/agents/provider_health.py && uv run mypy app/core/agents/service.py app/core/agents/provider_health.py`

### Step 5 — `app/core/agents/tests/test_provider_health.py` (CREATE)

Mirror `test_metrics.py` structure exactly. **Minimum 12 tests:**

| # | Name | Purpose |
|---|---|---|
| 1 | `test_tracker_starts_empty` | Fresh tracker → `get_all() == []` |
| 2 | `test_record_success_increments_total_calls` | Single success recorded |
| 3 | `test_record_failure_sets_last_failure_at` | Failure path updates timestamp |
| 4 | `test_mixed_calls_compute_failure_rate` | 4 calls, 1 failure → 0.25 |
| 5 | `test_p50_p95_none_below_two_observations` | Single call → `p50=None, p95=None` |
| 6 | `test_p50_p95_quantile_correctness` | 100 calls with known latencies → verify quantiles |
| 7 | `test_latency_window_bounded_at_100` | 150 calls → `_latencies_ms` has 100 entries |
| 8 | `test_daily_reset_clears_counters_on_utc_rollover` | Advance clock → `get_all() == []` |
| 9 | `test_get_all_deep_copies_state` | Mutating returned entries doesn't affect tracker |
| 10 | `test_extract_provider_name_from_string` | `"anthropic:claude-sonnet"` → `"anthropic"` |
| 11 | `test_extract_provider_name_from_none` | `None` → `default` arg |
| 12 | `test_extract_provider_name_from_model_instance` | Mock model with `__class__.__name__ = "AnthropicModel"` → `"anthropic"` |
| 13 | `test_singleton_reuse_returns_same_instance` | Two `get_provider_health_tracker()` calls return same obj |
| 14 | `test_reset_provider_health_tracker_forces_new_instance` | After reset, new singleton |
| 15 | `test_provider_health_endpoint_returns_empty_when_no_calls` | Admin fetch → `providers: []` |
| 16 | `test_provider_health_endpoint_returns_recorded_providers` | Record 3 providers → response has all 3 sorted |
| 17 | `test_provider_health_endpoint_rejects_non_admin` | Dispatcher gets 403 + `"Insufficient permissions"` |
| 18 | `test_provider_health_endpoint_state_field_matches_circuit_state` | `record_call(state=OPEN)` → response has `state="open"` |

**Fixtures (copy from test_metrics.py):**

- Module-level `limiter.enabled = False` AFTER all imports (python-anti-patterns.md #13)
- `_mock_admin_user()` / `_mock_dispatcher_user()` helpers (return type `-> User`)
- `@pytest.fixture(autouse=True) _reset_singleton` calling
  `reset_provider_health_tracker()` before and after yield
- `_admin_override` fixture with `try/finally` cleanup of
  `app.dependency_overrides` (python-anti-patterns.md #56)

**Daily-reset test pattern:**

```python
def test_daily_reset_clears_counters_on_utc_rollover() -> None:
    fake_now = datetime(2026, 4, 11, 12, 0, tzinfo=UTC)

    def clock() -> datetime:
        return fake_now

    tracker = ProviderHealthTracker(clock=clock)
    tracker.record_call("anthropic", latency_ms=120.0, success=True)
    assert len(tracker.get_all()) == 1
    fake_now = fake_now + timedelta(days=1)
    assert tracker.get_all() == []
```

Note: `fake_now` is reassigned (not mutated); closure captures the outer
name via `nonlocal` or module-level (mirror test_metrics.py:93-109).

**Preflight warning for Test #6 (quantile correctness):** Avoid
hard-coding exact quantile values — use a deterministic sequence like
`range(1, 101)` and assert `p50 ≈ 50`, `p95 ≈ 95` within ±1.0 tolerance.
`statistics.quantiles` method="inclusive" returns the same values as
`numpy.percentile` with `linear` interpolation, so exact integer asserts
work for a 1..100 ramp.

**Return type annotations on EVERY test function (`-> None`)** —
python-anti-patterns.md #26.

**All MagicMock helpers must have explicit return types:** e.g.
`def _mock_admin_user() -> User:` — python-anti-patterns.md #7.

**Validation:** `uv run ruff format app/core/agents/tests/test_provider_health.py && uv run pyright app/core/agents/tests/test_provider_health.py && uv run pytest app/core/agents/tests/test_provider_health.py -v`

### Step 6 — `app/core/agents/CLAUDE.md` (UPDATE)

Two small edits:

1. Add `├── provider_health.py   # AI-8.2: ...` line to the directory tree
   (below `circuit_breaker.py`).
2. Extend point 7 ("Provider resilience") to note AI-8.2 is done:
   `✅ AI-8.2: `ProviderHealthTracker` singleton + admin `GET /v1/chat/provider-health` endpoint...`
3. Update the "tests/" comment to add `AI-8.2 provider health tracker + admin endpoint in test_provider_health.py`.

**Validation:** Visual diff review only — no code gates for markdown.

## Preflight Warnings

- **`pipeline.py` pre-existing errors** (3 pyright + 1 mypy) must not be
  touched. `/be-execute` must verify baseline counts unchanged after every step.
- **`statistics.quantiles` with `<2` observations raises `StatisticsError`** —
  `_percentile()` must gate on `len(_latencies_ms) < 2` before calling.
  Returning `None` instead is intentional and reflected in the response schema.
- **Deque mutation gotcha** — `get_all()` must construct new `ProviderHealth`
  instances with a fresh `deque(...)` copy. Returning the original
  `_latencies_ms` reference would let callers mutate internal state.
- **Module-level `limiter.enabled = False`** must appear AFTER all imports
  in `test_provider_health.py` (python-anti-patterns.md #13, Ruff E402).
- **`_extract_provider_name` removes `"model"` suffix** — pydantic_ai classes
  are named `AnthropicModel`, `GoogleModel`, `GroqModel`, `OpenAIChatModel`.
  `"openaichat"` is acceptable for the Ollama path (it's internal
  observability, not user-facing). Document this in the helper docstring.
- **Avoid freezegun** — use `clock=` parameter on constructor; matches
  metrics.py + circuit_breaker.py patterns and avoids global time mocking
  in async contexts.
- **The tracker is in-process only** — per-worker drift is expected under
  Gunicorn + 4 workers. Document in module docstring. Ops reads are rough
  signals, not distributed consensus. No Redis-backed option in this PR.
- **`record_call` failures must never block LLM calls** — wrap both
  success and failure `record_call` invocations in `try/except Exception`
  with `logger.warning("agent.provider_health.record_failed", exc_info=True)`.
  This is a CTX-AGENT requirement ("fail-open on instrumentation").
- **BLE001 exceptions on bare `except Exception`** — add `# noqa: BLE001`
  with an inline comment explaining fail-open rationale (anti-pattern #6
  says unused noqa is flagged; be precise about the code).
- **Do not add `verify=False` or any SSL bypass** — zero new network calls.
- **Do not expose raw exception repr in log events** — CTX-AGENT: only
  log the provider name + success/failure + latency.

## Security Checklist

New endpoint `GET /v1/chat/provider-health`:

- [x] `Depends(require_role("admin"))` — not bare `get_current_user`
- [x] `@limiter.limit("60/minute")` — matches `/v1/models` and other health endpoints
- [x] No query/path parameters — no input validation needed
- [x] Response uses typed Pydantic `ProviderHealthResponse` (no `Any`, no raw dict)
- [x] No credentials / API keys / connection strings in response body
- [x] No raw exception repr in response body (generic `record_failed` warning log)
- [x] No stack traces in logs of `provider_health.py` itself
- [x] `TestAllEndpointsRequireAuth` will auto-detect and enforce `require_role`
- [x] New dispatcher-403 test included (`test_provider_health_endpoint_rejects_non_admin`)
- [x] New admin-200 test included (`test_provider_health_endpoint_returns_recorded_providers`)

## Verification

- [ ] `uv run ruff format app/core/agents/ app/core/agents/tests/` clean
- [ ] `uv run ruff check app/core/agents/ app/core/agents/tests/` clean
- [ ] `uv run pyright app/core/agents/` reports **≤5** errors (baseline: 5)
- [ ] `uv run mypy app/core/agents/` reports **≤3** errors (baseline: 3)
- [ ] `uv run pyright app/core/agents/provider_health.py` reports **0** errors
- [ ] `uv run mypy app/core/agents/provider_health.py` reports **0** errors
- [ ] `uv run pyright app/core/agents/tests/test_provider_health.py` reports **0** errors
- [ ] `uv run pytest app/core/agents/tests/test_provider_health.py -v` all pass (≥12 tests)
- [ ] `uv run pytest app/core/agents/tests/ -q` — no regressions in existing agents suite
- [ ] `uv run pytest app/tests/test_security.py::TestAllEndpointsRequireAuth -v` — passes (auto-detects new endpoint)
- [ ] `make check` passes (lint + types + tests)
- [ ] `make security-audit-quick` passes
- [ ] **Manual verify:** Fire 20 successful calls through
  `resolve_tier_model("fast")`, then 5 failing calls. `GET /v1/chat/provider-health`
  (as admin) returns per-provider entries with correct counts and p95 latency.
  Circuit breaker state remains `"closed"` (expected — breaker registry wiring
  is AI-8.2-followup scope).

## Out of Scope (Explicit)

- **Breaker registry wiring into `_execute()`** — the tracker's `state`
  field will always be `"closed"` in this PR. A follow-up PR wires up
  per-provider `CircuitBreaker` instances and passes `state=breaker.state`
  into `record_call(...)`.
- **Per-worker state aggregation** — under Gunicorn, 4 workers each
  maintain independent trackers. Ops reads are approximate; a
  Redis-backed or cross-worker aggregation option is future work.
- **Historical / timeseries storage** — no persistence beyond the current
  UTC day. For incident forensics, rely on GlitchTip + structured logs.
- **Alert triggers / PagerDuty integration** — the endpoint is a pull
  API; alerting belongs in a downstream scraper.
- **`llm.py` extraction** — the user's spec references a file that
  doesn't exist. This PR does NOT extract an `llm.py` module. If the
  future wants a unified LLM wrapper (e.g., to centralize the breaker
  registry + health tracker), that's a separate refactor PR.
