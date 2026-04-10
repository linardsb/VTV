# Plan: AI-5.3 — Self-Correction Metrics + Admin Dashboard Endpoint

## Context

AI-5.1 added the bounded self-correction loop (`app/core/agents/correction.py`) and AI-5.2
extended QA checks with severity tiers. We now log `agent.correction.triggered/resolved/exhausted`
per request, but have no way to **see in aggregate** whether self-correction is improving
response quality or just adding latency.

AI-5.3 adds an in-process per-check counter, an admin-only `GET /v1/chat/metrics` endpoint
that exposes a snapshot, and a per-correction structured log line (`agent.correction.metric`)
for each check involved. Counters reset at 00:00 UTC daily — high triggered/exhausted ratios
on a specific check name signal a prompt-engineering or validator-tuning opportunity.

The tracker is intentionally **in-process only** (not Redis-backed): reset is daily, the
data is observability not billing, and per-worker drift is acceptable for a debug dashboard.
This mirrors `app/core/agents/quota.py`'s in-memory fallback design but without the Redis path.

## Security Context Assessment

| Context | Active? | Why |
|---|---|---|
| **CTX-RBAC** | ✅ | New `GET /v1/chat/metrics` endpoint — must be admin-only via `require_role("admin")` |
| **CTX-AGENT** | ✅ | Touches the self-correction loop in `app/core/agents/correction.py`. Tracker must not expose raw user prompts/responses — only check_name + counts |
| CTX-INPUT | ➖ | No user input — endpoint takes zero query params |
| CTX-FILE | ➖ | No file handling |
| CTX-AUTH | ➖ | No auth flow changes (uses existing `require_role`) |
| CTX-INFRA | ➖ | No Docker/nginx/CORS changes |

**Applied requirements:**
- `require_role("admin")` (not bare `get_current_user`) so dispatchers/drivers can't read internal QA stats
- `@limiter.limit("30/minute")` to match other admin metric endpoints
- Tracker stores **only** `check_name` strings (controlled vocabulary from validator) + integer counters — never user content, never request bodies
- Convention test `TestRouteAuthenticationConvention::test_all_routes_have_auth` (`app/tests/test_security.py:667-739`) auto-passes when `require_role` appears in the signature

## Research Summary

### Existing self-correction loop — `app/core/agents/correction.py`

| Line range | What it does | Hook for AI-5.3 |
|---|---|---|
| `48` | `logger = get_logger(__name__)` | Reuse |
| `162-202` | `for attempt in range(self._max_rounds + 1):` main loop | Wrap with timer + capture triggering check_names |
| `183-198` | "Either fully clean OR only warning-severity issues" branch — `attempt > 0` is the **resolved** path | Call `tracker.record_resolved()` |
| `200-202` | `if attempt >= self._max_rounds: break` — falls through to exhausted block | (no hook, falls through) |
| `204-209` | `logger.info("agent.correction.triggered", ...)` — fired when there are retryable errors AND we still have retries left | Capture `triggering_check_names` (only on first hit) and call `tracker.record_triggered()` |
| `222-226` | `logger.warning("agent.correction.exhausted", ...)` after the for-loop break | Call `tracker.record_exhausted()` |
| `33-39` | Imports `Issue` from `validation` — `Issue.check_name`, `Issue.description`, `Issue.severity` | Use `Issue.check_name` as the metric key |
| `155-160` | Per-call locals (`history`, `last_warnings`, etc.) | Add `triggering_check_names: set[str] = set()` and `loop_start_monotonic = time.monotonic()` |

### Singleton + lazy-reset reference — `app/core/agents/quota.py`

`quota.py` is the closest pattern in the agent module:

- `_SECONDS_PER_DAY` constant (line 16)
- `_QuotaEntry` dataclass with `field(default_factory=lambda: ...)` (lines 19-24)
- Module-level singleton `_quota_tracker: QueryQuotaTracker | None = None` (line 137)
- `get_quota_tracker()` getter (lines 140-150)

We mirror the singleton getter but use **UTC date rollover**, not monotonic+86_400s, because the spec says "Reset daily at 00:00 UTC" (anchored, not rolling).

### Existing routes pattern — `app/core/agents/routes.py`

| Line | Pattern |
|---|---|
| `1` | `# pyright: reportUnknownMemberType=false, reportUntypedFunctionDecorator=false` (file-level pyright relaxation for slowapi decorators) |
| `11-20` | Imports for `APIRouter`, `Depends`, `Request`, `get_current_user`, `User`, `limiter` |
| `24` | `router = APIRouter(prefix="/v1", tags=["agent"])` |
| `27-34` | `@router.post(...)` → `@limiter.limit("10/minute")` → `async def chat_completions(request: Request, body: ..., service: ... = Depends(...), _current_user: User = Depends(get_current_user))` |

The new endpoint uses the **same prefix** (`/v1`) so the resulting URL is `GET /v1/chat/metrics`.
Router is already registered in `app/main.py` — we don't touch `main.py`.

### Auth dependency — `app/auth/dependencies.py:121-144`

```python
def require_role(*roles: str) -> Callable[..., Coroutine[Any, Any, User]]:
    async def _check_role(
        current_user: User = Depends(get_current_user),  # noqa: B008
    ) -> User:
        if current_user.role not in roles:
            logger.warning("auth.role_escalation_attempt", ...)
            raise HTTPException(403, detail="Insufficient permissions")
        return current_user
    return _check_role
```

**Usage in our route:** `_admin: User = Depends(require_role("admin"))  # noqa: B008`

### Issue model

`app/core/agents/validation.py` defines `Issue` with fields `check_name: str`, `description: str`,
`severity: Literal["error", "warning"]`. `check_name` is a controlled vocabulary set by the
validators (e.g., `"route_existence"`, `"stop_existence"`, `"delay_sanity"`, `"diacritics"`,
`"citation_grounding"`, `"language_match"`, `"stale_data"`).

### Shared utilities to reuse
- `from app.core.logging import get_logger` (structlog)
- `from app.core.rate_limit import limiter`
- `from app.auth.dependencies import require_role`
- `from app.auth.models import User`
- `from pydantic import BaseModel, ConfigDict, Field`

No `TimestampMixin`, no DB model, no migration — this feature is purely in-memory.

## Test Landscape

| File | Relevant content |
|---|---|
| `app/core/agents/tests/test_routes.py:24-40` | `_mock_admin_user()` factory + autouse `_setup_auth_override()` fixture (overrides `get_current_user`) |
| `app/core/agents/tests/test_routes.py:21` | `limiter.enabled = False` already disables rate limiting for this test module |
| `app/core/agents/tests/test_correction.py:283-300` | `_validation_result(*issues)` helper + `Issue(check_name=..., description=..., severity="error")` factory |
| `app/core/agents/tests/test_correction.py` (`_fake_agent`, `_fake_run_result`) | Async mock pattern for `agent.run()` returning sequential outputs — reuse for end-to-end correction-loop instrumentation tests |
| `app/tests/test_security.py:667-739` | `TestRouteAuthenticationConvention::test_all_routes_have_auth` — auto-discovers all `app/*/routes.py` and `app/core/agents/routes.py`. Auto-passes when `require_role` is in the signature. |
| `conftest.py` (root) | Provides `client: TestClient` and an autouse `_clear_auth_cache()` |

**No `freezegun` in dev deps** — for the daily-reset test we inject a `clock: Callable[[], datetime]`
into `CorrectionMetricsTracker.__init__` rather than monkey-patching `datetime.now`.

**No existing `app/core/agents/tests/conftest.py`** — local fixtures live in each test file.
We follow that convention and put admin-override + tracker-reset fixtures inline in
`test_metrics.py`.

### Preflight — fragile patterns to watch
1. `test_routes.py:21` does `limiter.enabled = False` at **module top**. The new test file must
   do the same; ruff E402 will reject placing this between imports (anti-pattern #13).
2. `test_correction.py` asserts on `result.rounds_used == 2` and `fake_agent.run.await_count == 2` —
   adding the tracker must NOT change `rounds_used` semantics. The tracker hooks live next to
   the existing `logger.info` calls, not inside the loop arithmetic.
3. The existing `validation.py:36` has a module-level `last_stale_data_timestamp: float = 0.0`.
   That's an unrelated module — the new tracker singleton must NOT introduce cross-test state
   leakage. Add a `reset()` test helper and call it from a fixture in `test_metrics.py`.
4. `Issue` is imported via `TYPE_CHECKING` in `correction.py:42-46` — but `Issue` is also imported
   at runtime via line `33-39` (it's already in the runtime block). Verify with `Read` before editing.

## Type Check Baseline

| Scope | Pyright | Mypy |
|---|---|---|
| `app/core/agents/correction.py` + `app/core/agents/routes.py` (target files) | **0 errors, 0 warnings** | **0 errors** |
| Whole `app/core/agents/` module (63 files) | 5 errors (pre-existing in `pipeline.py`, `tools/transit/client.py`, `tools/transit/static_store.py`) | 3 errors (pre-existing in `pipeline.py:136`, `tools/transit/static_store.py:149-150`) |

**Acceptance:** After AI-5.3, target files MUST stay at 0/0. Whole-module count MUST stay
≤ 5 pyright / ≤ 3 mypy. Any new error attributable to `correction.py`, `routes.py`, `metrics.py`,
or `schemas.py` is a hard failure.

## Files to Create/Modify

| Action | File | Purpose |
|---|---|---|
| CREATE | `app/core/agents/metrics.py` | `CorrectionMetricsTracker` singleton with per-check counters + daily UTC reset |
| UPDATE | `app/core/agents/schemas.py` | Add `CorrectionCheckSnapshot`, `CorrectionTotals`, `CorrectionMetricsResponse` |
| UPDATE | `app/core/agents/correction.py` | Instrument loop: capture loop start, record triggered/resolved/exhausted, emit `agent.correction.metric` per check |
| UPDATE | `app/core/agents/routes.py` | Add `GET /chat/metrics` admin endpoint + import |
| CREATE | `app/core/agents/tests/test_metrics.py` | 9 tests covering tracker, instrumentation, endpoint, RBAC, daily reset |
| (none) | `app/main.py` | NOT touched — router is already registered |
| (none) | alembic | NOT touched — no DB changes |
| (none) | `pyproject.toml` | NOT touched — no new deps |

## Implementation Steps

### Step 1 — Create `app/core/agents/metrics.py`

```python
"""In-process self-correction metrics tracker (AI-5.3).

Tracks per-check-name counters for the bounded self-correction loop in
``app/core/agents/correction.py``. Counters reset at 00:00 UTC every day
(lazy-evaluated on access). Exposed via ``GET /v1/chat/metrics`` for
admins to monitor whether self-correction is improving response quality.

Design notes:
- In-process only (no Redis). Per-worker drift is acceptable for a debug
  dashboard. The tracker mirrors ``quota.py``'s singleton pattern but uses
  UTC date rollover instead of monotonic+86_400s because the spec calls
  for an anchored 00:00 UTC reset, not a rolling 24h window.
- Stores only ``check_name`` strings (controlled vocabulary from
  validators) and integer counters — never user content or prompts.
- Lazy reset: ``_maybe_reset()`` is called at the top of every public
  method. No background task needed.
"""

from __future__ import annotations

import datetime
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class CheckMetrics:
    """Per-check counters accumulated within the current UTC day.

    Attributes:
        triggered: Number of correction events that began with at least
            one error-severity issue under this ``check_name``.
        resolved: Number of correction events that ended cleanly (no
            retryable errors) for which this ``check_name`` was in the
            initial triggering set.
        exhausted: Number of correction events that hit ``max_rounds``
            without resolving while this ``check_name`` was in the
            initial triggering set.
        total_latency_ms: Sum of full-loop wall-clock latencies for
            ``resolved`` + ``exhausted`` events involving this check.
            Divide by (resolved + exhausted) for the average.
    """

    triggered: int = 0
    resolved: int = 0
    exhausted: int = 0
    total_latency_ms: int = 0


class CorrectionMetricsTracker:
    """Per-check-name counters for the self-correction loop.

    Counters auto-reset at 00:00 UTC. The tracker is process-local and
    intentionally not persisted — see module docstring.

    Args:
        clock: Callable returning the current UTC datetime. Injected for
            testability. Defaults to ``datetime.datetime.now(datetime.UTC)``.
    """

    def __init__(
        self,
        *,
        clock: Callable[[], datetime.datetime] | None = None,
    ) -> None:
        self._clock = clock or _utc_now
        self._reset_date: datetime.date = self._clock().date()
        self._metrics: dict[str, CheckMetrics] = {}

    def _maybe_reset(self) -> None:
        """Clear all counters if the UTC date has rolled over."""
        today = self._clock().date()
        if today != self._reset_date:
            self._metrics.clear()
            self._reset_date = today

    def record_triggered(self, check_names: Iterable[str]) -> None:
        """Record one correction event triggered by these check names.

        Each unique ``check_name`` in ``check_names`` gets a +1 increment.
        Call this exactly once per correction event, with the set of
        check names from the FIRST attempt's retryable issues.
        """
        self._maybe_reset()
        for name in set(check_names):
            self._metrics.setdefault(name, CheckMetrics()).triggered += 1

    def record_resolved(self, check_names: Iterable[str], latency_ms: int) -> None:
        """Record a successful correction with full-loop latency.

        Args:
            check_names: The check_names from the *initial* triggering
                set, not the residual set.
            latency_ms: Wall-clock duration of the entire correction loop.
        """
        self._maybe_reset()
        for name in set(check_names):
            entry = self._metrics.setdefault(name, CheckMetrics())
            entry.resolved += 1
            entry.total_latency_ms += latency_ms
            logger.info(
                "agent.correction.metric",
                check_name=name,
                resolved=True,
                latency_ms=latency_ms,
            )

    def record_exhausted(self, check_names: Iterable[str], latency_ms: int) -> None:
        """Record a correction that ran out of retries."""
        self._maybe_reset()
        for name in set(check_names):
            entry = self._metrics.setdefault(name, CheckMetrics())
            entry.exhausted += 1
            entry.total_latency_ms += latency_ms
            logger.info(
                "agent.correction.metric",
                check_name=name,
                resolved=False,
                latency_ms=latency_ms,
            )

    def snapshot(self) -> dict[str, CheckMetrics]:
        """Return a copy of the current per-check counters."""
        self._maybe_reset()
        return {name: CheckMetrics(**vars(m)) for name, m in self._metrics.items()}

    def period_start(self) -> datetime.datetime:
        """Return the UTC midnight at which the current period began."""
        self._maybe_reset()
        return datetime.datetime.combine(
            self._reset_date,
            datetime.time.min,
            tzinfo=datetime.UTC,
        )

    def reset(self) -> None:
        """Force-clear all counters. Test-only helper."""
        self._metrics.clear()
        self._reset_date = self._clock().date()


def _utc_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC)


# --- Module-level singleton ---

_metrics_tracker: CorrectionMetricsTracker | None = None


def get_metrics_tracker() -> CorrectionMetricsTracker:
    """Get or create the metrics tracker singleton."""
    global _metrics_tracker
    if _metrics_tracker is None:
        _metrics_tracker = CorrectionMetricsTracker()
    return _metrics_tracker


def reset_metrics_tracker() -> None:
    """Replace the singleton with a fresh instance. Test-only."""
    global _metrics_tracker
    _metrics_tracker = None


__all__ = [
    "CheckMetrics",
    "CorrectionMetricsTracker",
    "get_metrics_tracker",
    "reset_metrics_tracker",
]
```

**Validation:**
```bash
uv run ruff format app/core/agents/metrics.py && \
uv run ruff check app/core/agents/metrics.py && \
uv run mypy app/core/agents/metrics.py && \
uv run pyright app/core/agents/metrics.py
```
Expected: 0 errors.

---

### Step 2 — Add response schemas to `app/core/agents/schemas.py`

Append at the bottom (do not touch existing schemas — anti-pattern #11/#29: schema additions
in this module are additive only). Add `import datetime` at the top of the imports block if
not already present (it isn't — current imports are `time`, `uuid`, `Literal`, `pydantic`).

```python
# --- AI-5.3: Self-correction metrics ---


class CorrectionCheckSnapshot(BaseModel):
    """Per-check correction counters for the current UTC day.

    Attributes:
        check_name: Validator check identifier (e.g. ``route_existence``).
        triggered: Correction events whose initial failure set included
            this check.
        resolved: Of the triggered set, how many ended cleanly.
        exhausted: Of the triggered set, how many ran out of retries.
        success_rate: ``resolved / (resolved + exhausted)`` or 0.0 if
            no completed events yet.
        avg_latency_ms: Mean wall-clock latency for completed events
            involving this check, or 0.0 if none.
    """

    model_config = ConfigDict(strict=True)

    check_name: str
    triggered: int
    resolved: int
    exhausted: int
    success_rate: float
    avg_latency_ms: float


class CorrectionTotals(BaseModel):
    """Aggregate counters across all check names."""

    model_config = ConfigDict(strict=True)

    triggered: int
    resolved: int
    exhausted: int
    success_rate: float
    avg_latency_ms: float


class CorrectionMetricsResponse(BaseModel):
    """Response for ``GET /v1/chat/metrics``.

    Attributes:
        period_start: UTC midnight at which the current daily window began.
        generated_at: When this snapshot was rendered.
        checks: Per-check breakdown.
        totals: Aggregate across all checks.
    """

    model_config = ConfigDict(strict=True)

    period_start: datetime.datetime
    generated_at: datetime.datetime
    checks: list[CorrectionCheckSnapshot]
    totals: CorrectionTotals
```

Add `import datetime` at the top of `schemas.py` alongside the existing `import time` /
`import uuid`.

**Validation:**
```bash
uv run ruff format app/core/agents/schemas.py && \
uv run ruff check app/core/agents/schemas.py && \
uv run mypy app/core/agents/schemas.py && \
uv run pyright app/core/agents/schemas.py
```

---

### Step 3 — Instrument `app/core/agents/correction.py`

Three surgical edits — preserve the existing log lines and `CorrectedResult` shape exactly.
Anti-pattern #20: do NOT use `replace_all`. Each edit is targeted.

**Edit 3a — Imports (top of file, after existing imports at line 33-40):**

Add `import time` to the stdlib block at the top of the file (between `from __future__ import annotations` at line 20 and `from dataclasses import ...` at line 22). Then add the runtime import for the tracker after the existing `from app.core.logging import get_logger` line:

```python
import time
# ... (existing imports unchanged) ...
from app.core.agents.metrics import get_metrics_tracker
```

**Edit 3b — Inside `run_with_correction`, just below line 160 (`last_messages: list[ModelMessage] = []`):**

```python
        triggering_check_names: set[str] = set()
        loop_start_monotonic = time.monotonic()
```

**Edit 3c — Replace the resolved branch (lines 183-198). Old:**

```python
            retryable = _retryable_issues(last_issues)
            if not retryable:
                # Either fully clean OR only warning-severity issues.
                if attempt > 0:
                    logger.info(
                        "agent.correction.resolved",
                        round=attempt,
                        residual_warnings=len(last_warnings),
                    )
                return CorrectedResult(
                    output=last_output,
                    warnings=last_warnings,
                    issues=last_issues,
                    rounds_used=attempt + 1,
                    all_messages=last_messages,
                    corrected=attempt > 0,
                )
```

**New (only the `if attempt > 0` block changes — adds tracker call before logger):**

```python
            retryable = _retryable_issues(last_issues)
            if not retryable:
                # Either fully clean OR only warning-severity issues.
                if attempt > 0:
                    latency_ms = int((time.monotonic() - loop_start_monotonic) * 1000)
                    get_metrics_tracker().record_resolved(
                        triggering_check_names, latency_ms
                    )
                    logger.info(
                        "agent.correction.resolved",
                        round=attempt,
                        residual_warnings=len(last_warnings),
                    )
                return CorrectedResult(
                    output=last_output,
                    warnings=last_warnings,
                    issues=last_issues,
                    rounds_used=attempt + 1,
                    all_messages=last_messages,
                    corrected=attempt > 0,
                )
```

**Edit 3d — Replace the triggered branch (lines 204-209). Old:**

```python
            logger.info(
                "agent.correction.triggered",
                round=attempt + 1,
                warning_count=len(retryable),
                first_warning=retryable[0].description[:120],
            )
```

**New (capture triggering check names exactly once, before logging):**

```python
            if not triggering_check_names:
                triggering_check_names = {
                    issue.check_name for issue in retryable if issue.check_name
                }
                get_metrics_tracker().record_triggered(triggering_check_names)
            logger.info(
                "agent.correction.triggered",
                round=attempt + 1,
                warning_count=len(retryable),
                first_warning=retryable[0].description[:120],
            )
```

**Edit 3e — Replace the exhausted branch (lines 222-226). Old:**

```python
        logger.warning(
            "agent.correction.exhausted",
            rounds=self._max_rounds + 1,
            final_warning_count=len(last_warnings),
        )
```

**New (record before logging so a failing logger doesn't lose the metric):**

```python
        latency_ms = int((time.monotonic() - loop_start_monotonic) * 1000)
        get_metrics_tracker().record_exhausted(triggering_check_names, latency_ms)
        logger.warning(
            "agent.correction.exhausted",
            rounds=self._max_rounds + 1,
            final_warning_count=len(last_warnings),
        )
```

**Validation:**
```bash
uv run ruff format app/core/agents/correction.py && \
uv run ruff check app/core/agents/correction.py && \
uv run mypy app/core/agents/correction.py && \
uv run pyright app/core/agents/correction.py && \
uv run pytest app/core/agents/tests/test_correction.py -q
```
Expected: 0 lint/type errors. All existing correction tests still pass — instrumentation is
additive and does not change `rounds_used` or `corrected` semantics.

---

### Step 4 — Add the metrics endpoint to `app/core/agents/routes.py`

**Edit 4a — Imports.** Add to the existing import block:

```python
import datetime

from app.auth.dependencies import get_current_user, require_role
from app.core.agents.metrics import get_metrics_tracker
from app.core.agents.schemas import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    CorrectionCheckSnapshot,
    CorrectionMetricsResponse,
    CorrectionTotals,
)
```

(Append `require_role` to the existing `from app.auth.dependencies import` line; replace
the existing `from app.core.agents.schemas import ChatCompletionRequest, ChatCompletionResponse`
line with the multi-line form above.)

**Edit 4b — New endpoint.** Append after `list_models` (current end of file, line 86):

```python
@router.get("/chat/metrics", response_model=CorrectionMetricsResponse)
@limiter.limit("30/minute")
async def get_correction_metrics(
    request: Request,
    _admin: User = Depends(require_role("admin")),  # noqa: B008
) -> CorrectionMetricsResponse:
    """Return self-correction metrics for the current UTC day.

    Admin-only. Counters reset at 00:00 UTC. Use this to monitor whether
    the bounded self-correction loop in ``correction.py`` is improving
    response quality (high resolved/triggered ratio) or just adding
    latency (high exhausted/triggered ratio).

    Args:
        request: The incoming HTTP request (used for rate limiting).
        _admin: Injected admin user (RBAC enforcement only).

    Returns:
        Per-check counters plus aggregate totals.
    """
    tracker = get_metrics_tracker()
    snapshot = tracker.snapshot()

    checks: list[CorrectionCheckSnapshot] = []
    total_triggered = 0
    total_resolved = 0
    total_exhausted = 0
    total_latency_ms = 0

    for check_name, metrics in sorted(snapshot.items()):
        completed = metrics.resolved + metrics.exhausted
        success_rate = metrics.resolved / completed if completed else 0.0
        avg_latency = metrics.total_latency_ms / completed if completed else 0.0
        checks.append(
            CorrectionCheckSnapshot(
                check_name=check_name,
                triggered=metrics.triggered,
                resolved=metrics.resolved,
                exhausted=metrics.exhausted,
                success_rate=success_rate,
                avg_latency_ms=avg_latency,
            )
        )
        total_triggered += metrics.triggered
        total_resolved += metrics.resolved
        total_exhausted += metrics.exhausted
        total_latency_ms += metrics.total_latency_ms

    completed_total = total_resolved + total_exhausted
    totals = CorrectionTotals(
        triggered=total_triggered,
        resolved=total_resolved,
        exhausted=total_exhausted,
        success_rate=(total_resolved / completed_total) if completed_total else 0.0,
        avg_latency_ms=(total_latency_ms / completed_total) if completed_total else 0.0,
    )

    return CorrectionMetricsResponse(
        period_start=tracker.period_start(),
        generated_at=datetime.datetime.now(datetime.UTC),
        checks=checks,
        totals=totals,
    )
```

**Note:** `get_current_user` stays in the imports because `chat_completions` and `list_models`
still use it. Do NOT remove it.

**Validation:**
```bash
uv run ruff format app/core/agents/routes.py && \
uv run ruff check app/core/agents/routes.py && \
uv run mypy app/core/agents/routes.py && \
uv run pyright app/core/agents/routes.py
```

---

### Step 5 — Create `app/core/agents/tests/test_metrics.py`

```python
"""Tests for AI-5.3 self-correction metrics tracker + admin endpoint."""

from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.core.agents.correction import SelfCorrectionLoop
from app.core.agents.metrics import (
    CorrectionMetricsTracker,
    get_metrics_tracker,
    reset_metrics_tracker,
)
from app.core.agents.validation import Issue, ValidationResult
from app.core.rate_limit import limiter
from app.main import app

# Disable rate limiting for these tests (matches test_routes.py:21)
limiter.enabled = False


def _mock_admin_user() -> User:
    user = MagicMock(spec=User)
    user.id = 1
    user.email = "admin@vtv.lv"
    user.role = "admin"
    user.is_active = True
    return user


def _mock_dispatcher_user() -> User:
    user = MagicMock(spec=User)
    user.id = 2
    user.email = "dispatcher@vtv.lv"
    user.role = "dispatcher"
    user.is_active = True
    return user


@pytest.fixture(autouse=True)
def _reset_singleton() -> Generator[None, None, None]:
    """Ensure each test starts with a fresh tracker singleton."""
    reset_metrics_tracker()
    yield
    reset_metrics_tracker()


@pytest.fixture
def _admin_override() -> Generator[None, None, None]:
    app.dependency_overrides[get_current_user] = _mock_admin_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


# ----- Tracker unit tests -----


def test_tracker_starts_empty() -> None:
    tracker = CorrectionMetricsTracker()
    assert tracker.snapshot() == {}


def test_record_triggered_increments_per_unique_check() -> None:
    tracker = CorrectionMetricsTracker()
    tracker.record_triggered(["route_existence", "route_existence", "diacritics"])
    snap = tracker.snapshot()
    assert snap["route_existence"].triggered == 1
    assert snap["diacritics"].triggered == 1


def test_record_resolved_records_latency_and_count() -> None:
    tracker = CorrectionMetricsTracker()
    tracker.record_triggered(["route_existence"])
    tracker.record_resolved(["route_existence"], latency_ms=250)
    snap = tracker.snapshot()
    assert snap["route_existence"].resolved == 1
    assert snap["route_existence"].total_latency_ms == 250


def test_record_exhausted_records_latency_and_count() -> None:
    tracker = CorrectionMetricsTracker()
    tracker.record_triggered(["citation_grounding"])
    tracker.record_exhausted(["citation_grounding"], latency_ms=900)
    snap = tracker.snapshot()
    assert snap["citation_grounding"].exhausted == 1
    assert snap["citation_grounding"].total_latency_ms == 900


def test_daily_reset_clears_counters_on_utc_rollover() -> None:
    fake_now = datetime(2026, 4, 10, 12, 0, tzinfo=UTC)

    def clock() -> datetime:
        return fake_now

    tracker = CorrectionMetricsTracker(clock=clock)
    tracker.record_triggered(["route_existence"])
    tracker.record_resolved(["route_existence"], latency_ms=100)
    assert tracker.snapshot()["route_existence"].resolved == 1

    # Roll over to next UTC day
    fake_now = fake_now + timedelta(days=1)
    snap = tracker.snapshot()
    assert snap == {}
    # period_start follows the new day
    assert tracker.period_start().date() == fake_now.date()


# ----- Correction loop integration -----


def _validation_result(*issues: Issue) -> ValidationResult:
    return ValidationResult(
        is_valid=not issues,
        issues=list(issues),
        warnings=[i.description for i in issues],
        sanitized_response="",
    )


def _fake_run_result(output: str) -> MagicMock:
    result = MagicMock()
    result.output = output
    result.all_messages = MagicMock(return_value=[])
    return result


@pytest.mark.asyncio
async def test_correction_loop_records_resolved_metric() -> None:
    from unittest.mock import AsyncMock

    error = Issue(
        check_name="route_existence",
        description="Route 999 not found.",
        severity="error",
    )
    fake_agent = MagicMock()
    fake_agent.run = AsyncMock(
        side_effect=[_fake_run_result("bad"), _fake_run_result("good")],
    )

    loop = SelfCorrectionLoop(max_rounds=1)
    with patch(
        "app.core.agents.correction.validate_transit_response",
        side_effect=[_validation_result(error), _validation_result()],
    ):
        result = await loop.run_with_correction(
            fake_agent,
            "Where is bus 999?",
            deps=MagicMock(),
            message_history=None,
            instructions=None,
            model=None,
        )
    assert result.corrected is True

    snap = get_metrics_tracker().snapshot()
    assert snap["route_existence"].triggered == 1
    assert snap["route_existence"].resolved == 1
    assert snap["route_existence"].exhausted == 0
    assert snap["route_existence"].total_latency_ms >= 0


@pytest.mark.asyncio
async def test_correction_loop_records_exhausted_metric() -> None:
    from unittest.mock import AsyncMock

    error = Issue(
        check_name="diacritics",
        description="Missing diacritic.",
        severity="error",
    )
    fake_agent = MagicMock()
    fake_agent.run = AsyncMock(
        side_effect=[_fake_run_result("bad1"), _fake_run_result("bad2")],
    )

    loop = SelfCorrectionLoop(max_rounds=1)
    with patch(
        "app.core.agents.correction.validate_transit_response",
        side_effect=[_validation_result(error), _validation_result(error)],
    ):
        result = await loop.run_with_correction(
            fake_agent,
            "Kur ir autobuss?",
            deps=MagicMock(),
            message_history=None,
            instructions=None,
            model=None,
        )
    assert result.corrected is False

    snap = get_metrics_tracker().snapshot()
    assert snap["diacritics"].triggered == 1
    assert snap["diacritics"].resolved == 0
    assert snap["diacritics"].exhausted == 1


# ----- Endpoint tests -----


def test_metrics_endpoint_returns_empty_snapshot(_admin_override: None) -> None:
    with TestClient(app) as client:
        response = client.get("/v1/chat/metrics")
    assert response.status_code == 200
    body = response.json()
    assert body["checks"] == []
    assert body["totals"]["triggered"] == 0
    assert body["totals"]["success_rate"] == 0.0
    assert "period_start" in body and "generated_at" in body


def test_metrics_endpoint_aggregates_counts(_admin_override: None) -> None:
    tracker = get_metrics_tracker()
    tracker.record_triggered(["route_existence"])
    tracker.record_resolved(["route_existence"], latency_ms=400)
    tracker.record_triggered(["diacritics"])
    tracker.record_exhausted(["diacritics"], latency_ms=800)

    with TestClient(app) as client:
        response = client.get("/v1/chat/metrics")
    assert response.status_code == 200
    body = response.json()

    by_name = {c["check_name"]: c for c in body["checks"]}
    assert by_name["route_existence"]["resolved"] == 1
    assert by_name["route_existence"]["success_rate"] == 1.0
    assert by_name["route_existence"]["avg_latency_ms"] == 400.0
    assert by_name["diacritics"]["exhausted"] == 1
    assert by_name["diacritics"]["success_rate"] == 0.0

    assert body["totals"]["triggered"] == 2
    assert body["totals"]["resolved"] == 1
    assert body["totals"]["exhausted"] == 1
    assert body["totals"]["success_rate"] == 0.5


def test_metrics_endpoint_rejects_non_admin() -> None:
    app.dependency_overrides[get_current_user] = _mock_dispatcher_user
    try:
        with TestClient(app) as client:
            response = client.get("/v1/chat/metrics")
        assert response.status_code == 403
        assert response.json()["detail"] == "Insufficient permissions"
    finally:
        app.dependency_overrides.pop(get_current_user, None)
```

**Validation:**
```bash
uv run ruff format app/core/agents/tests/test_metrics.py && \
uv run ruff check app/core/agents/tests/test_metrics.py && \
uv run pyright app/core/agents/tests/test_metrics.py && \
uv run pytest app/core/agents/tests/test_metrics.py -v
```
Expected: 11 tests pass (5 tracker, 2 loop integration, 4 endpoint — exceeds the "5+" requirement).

---

### Step 6 — Verify the security convention test still passes

```bash
uv run pytest app/tests/test_security.py::TestRouteAuthenticationConvention -v
```

Expected: passes. The new endpoint signature contains `Depends(require_role("admin"))` which
the convention test recognizes.

---

### Step 7 — Full module + global validation

```bash
uv run ruff format app/core/agents/
uv run ruff check app/core/agents/
uv run mypy app/core/agents/
uv run pyright app/core/agents/
uv run pytest app/core/agents/tests/ -q
make check
```

Expected:
- Pyright: ≤ 5 errors in `app/core/agents/` (baseline preserved)
- Mypy: ≤ 3 errors in `app/core/agents/` (baseline preserved)
- All agent module tests pass
- `make check` green

## Preflight Warnings

1. **Anti-pattern #20** — Use targeted Edits for the four `correction.py` changes; never `replace_all`.
2. **Anti-pattern #11/#29** — `CorrectionMetricsResponse` is a NEW schema; no existing call sites
   to update. Verify with `Grep "CorrectionMetricsResponse(" -t py` before declaring done.
3. **Anti-pattern #13** — `limiter.enabled = False` in `test_metrics.py` must sit at module top
   AFTER the imports; ruff E402 will reject any non-import statement before it.
4. **Anti-pattern #38** — No background asyncio tasks added. The lazy-reset design avoids the
   "background task must catch CancelledError + Exception" rule entirely.
5. **Anti-pattern #56** — Tests use the autouse `_reset_singleton` fixture and a scoped
   `_admin_override` fixture; both restore `app.dependency_overrides` on teardown.
6. **Anti-pattern #39** — `correction.py` does not have a `date` field anywhere, so importing
   `datetime` directly in `metrics.py` is safe (we still use `datetime.datetime` and
   `datetime.date` qualified to avoid future shadowing if `correction.py` ever grows one).
7. **`Issue.check_name` empty handling** — The set comprehension filters falsy `check_name`
   values (`if issue.check_name`) to avoid an empty-string bucket if a validator forgets to
   set it. This is defensive only; today every validator sets `check_name`.
8. **Latency monotonic clock** — `time.monotonic()` is the right choice (immune to wall-clock
   adjustments). We use `datetime.now(UTC)` only for the period rollover boundary.

## Security Checklist

- [x] `Depends(require_role("admin"))` on `GET /v1/chat/metrics` (not bare `get_current_user`)
- [x] `@limiter.limit("30/minute")` on the new endpoint
- [x] No user input → no Pydantic input validation needed
- [x] Response uses `CorrectionMetricsResponse` (no internal type leakage)
- [x] No SQL → no `escape_like()` needed
- [x] Tracker stores only check_name strings (controlled vocabulary) + integers — no PII, no prompts, no responses
- [x] Convention test `TestRouteAuthenticationConvention` continues to pass
- [x] Generic 403 message ("Insufficient permissions") via `require_role` — no role names leaked
- [x] `dependency_overrides` cleanup in every test fixture

## Verification

- [ ] `uv run ruff format app/core/agents/` clean
- [ ] `uv run ruff check app/core/agents/` clean
- [ ] `uv run mypy app/core/agents/correction.py app/core/agents/routes.py app/core/agents/metrics.py app/core/agents/schemas.py` → 0 errors
- [ ] `uv run pyright app/core/agents/correction.py app/core/agents/routes.py app/core/agents/metrics.py app/core/agents/schemas.py` → 0 errors, 0 warnings
- [ ] Whole-module pyright ≤ 5 errors (baseline)
- [ ] Whole-module mypy ≤ 3 errors (baseline)
- [ ] `uv run pytest app/core/agents/tests/test_metrics.py -v` → all pass (≥ 9 tests)
- [ ] `uv run pytest app/core/agents/tests/test_correction.py -v` → all pre-existing tests still pass
- [ ] `uv run pytest app/tests/test_security.py::TestRouteAuthenticationConvention -v` → passes
- [ ] `make check` green
- [ ] `make security-audit-quick` passes
- [ ] Manual smoke test: trigger 10 corrections via `test_correction.py` test cases, then verify
      `GET /v1/chat/metrics` (with admin auth override) returns matching counts

## Out of scope (deferred)

- **Persistent metrics** — No database table, no Redis. Per-worker drift is acceptable for an
  observability dashboard. Promote to Redis-backed only if metrics become billing-relevant.
- **Histograms / p95** — Only mean latency is exposed. Add percentiles only when there's a
  concrete need.
- **Frontend dashboard** — The endpoint exists; the CMS page that consumes it is a separate
  AI-5.4 ticket.
- **Complex-tier (`pipeline.py`) instrumentation** — Pipeline has its own retry layer and is
  not wrapped by `SelfCorrectionLoop`. Tracking it is a follow-up under AI-5.x.
