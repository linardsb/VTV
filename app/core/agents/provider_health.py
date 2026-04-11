"""Per-provider LLM health metrics tracker (AI-8.2).

In-process tracker for per-LLM-provider success/failure counts, latency
percentiles (p50/p95 over the last 100 calls), last success/failure
timestamps, and the current circuit breaker state. Counters auto-reset
at 00:00 UTC each day (lazy-evaluated on access).

Design notes:

* Pattern mirrors ``app/core/agents/metrics.py`` (AI-5.3): module-level
  singleton, lazy ``_maybe_reset`` on every public call, injectable
  ``clock`` for deterministic tests.
* ``track_provider_call`` is an async context manager used by
  ``service.py`` to wrap the three LLM call sites (complex, correction,
  fallback). Fail-open: if ``record_call`` itself raises, the LLM result
  is returned (or the original exception re-raised) unchanged.
* In-process only. Under Gunicorn + 4 workers each worker maintains an
  independent tracker. Ops reads are approximate — use for degradation
  signals, not distributed consensus.
* The ``state`` field on each entry is currently always ``CLOSED``
  because AI-8.2 adds the tracker + endpoint but does NOT wire a
  per-provider ``CircuitBreaker`` registry into ``_execute()``. That
  wiring is a follow-up PR (see ``_extract_provider_name`` docstring).
"""

from __future__ import annotations

import datetime
import time
from collections import deque
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from statistics import quantiles
from typing import TYPE_CHECKING

from app.core.agents.circuit_breaker import CircuitState
from app.core.logging import get_logger

if TYPE_CHECKING:
    from pydantic_ai.models import Model

logger = get_logger(__name__)

_LATENCY_WINDOW = 100  # Last N call latencies tracked per provider for p50/p95.


@dataclass
class ProviderHealth:
    """Accumulated health counters for a single LLM provider.

    Attributes:
        provider_name: Short provider identifier (e.g. ``anthropic``,
            ``google``, ``groq``, ``ollama``, ``test``).
        state: Most recently observed circuit breaker state. Defaults to
            :attr:`CircuitState.CLOSED` until a per-provider breaker
            registry is wired into ``_execute()`` in a follow-up PR.
        total_calls: Total LLM call attempts recorded today.
        total_failures: Total LLM call failures recorded today.
        last_failure_at: UTC timestamp of the most recent failure, or
            ``None`` if no failures yet.
        last_success_at: UTC timestamp of the most recent success, or
            ``None`` if no successes yet.
    """

    provider_name: str
    state: CircuitState = CircuitState.CLOSED
    total_calls: int = 0
    total_failures: int = 0
    last_failure_at: datetime.datetime | None = None
    last_success_at: datetime.datetime | None = None
    _latencies_ms: deque[float] = field(
        default_factory=lambda: deque[float](maxlen=_LATENCY_WINDOW)
    )

    @property
    def failure_rate(self) -> float:
        """Return ``total_failures / total_calls`` (0.0 when no calls)."""
        return self.total_failures / self.total_calls if self.total_calls else 0.0

    def _percentile(self, pct: int) -> float | None:
        """Return the requested percentile or None when <2 observations.

        ``statistics.quantiles`` raises ``StatisticsError`` when given
        fewer than 2 data points, so we gate on length explicitly and
        return ``None`` as a signal to the response schema.
        """
        if len(self._latencies_ms) < 2:
            return None
        qs = quantiles(self._latencies_ms, n=100, method="inclusive")
        return qs[pct - 1]

    @property
    def p50_latency_ms(self) -> float | None:
        """Return the 50th-percentile latency over the sliding window."""
        return self._percentile(50)

    @property
    def p95_latency_ms(self) -> float | None:
        """Return the 95th-percentile latency over the sliding window."""
        return self._percentile(95)


class ProviderHealthTracker:
    """Per-provider health metrics with lazy 00:00 UTC daily reset.

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
        self._providers: dict[str, ProviderHealth] = {}

    def _maybe_reset(self) -> None:
        """Clear all counters if the UTC date has rolled over."""
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
        """Record one LLM call outcome for ``provider``.

        Args:
            provider: Short provider identifier.
            latency_ms: Measured wall-clock latency in milliseconds.
            success: Whether the call completed without raising.
            state: Current circuit breaker state for this provider.
                Defaults to CLOSED until a per-provider registry is wired.
        """
        self._maybe_reset()
        entry = self._providers.setdefault(provider, ProviderHealth(provider_name=provider))
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
        """Return the live health record for ``provider`` (or ``None``)."""
        self._maybe_reset()
        return self._providers.get(provider)

    def get_all(self) -> list[ProviderHealth]:
        """Return a deep-copied, provider-name-sorted list of snapshots.

        Returning fresh :class:`ProviderHealth` instances (with a copied
        latency deque) prevents callers from mutating the tracker's
        internal state — the same guarantee as
        :meth:`CorrectionMetricsTracker.snapshot`.
        """
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
        """Return the UTC midnight at which the current period began."""
        self._maybe_reset()
        return datetime.datetime.combine(
            self._reset_date,
            datetime.time.min,
            tzinfo=datetime.UTC,
        )

    def reset(self) -> None:
        """Force-clear counters without rolling the date. Test-only helper."""
        self._providers.clear()


def _utc_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC)


def _extract_provider_name(
    tier_model: str | Model | None,
    default: str,
) -> str:
    """Resolve a short provider name from a ``tier_model`` value.

    Accepts any of the shapes ``resolve_tier_model`` may return:

    * ``None`` → returns ``default`` (typically ``settings.llm_provider``).
    * ``str`` like ``"anthropic:claude-sonnet"`` → ``"anthropic"``.
    * ``pydantic_ai.Model`` instance → lowercased class name with a
      trailing ``"model"`` suffix removed (``AnthropicModel`` →
      ``"anthropic"``, ``GoogleModel`` → ``"google"``). Classes that do
      not end in ``"model"`` are returned as-is (e.g.
      ``OpenAIChatModel`` → ``"openaichat"``). This is internal
      observability, not user-facing.

    TODO(AI-8.2-followup): when ``_execute()`` is wired to a
    per-provider ``BreakerRegistry``, callers should also pass the live
    ``CircuitState`` into ``record_call`` so the snapshot reflects the
    breaker state instead of the hard-coded ``CLOSED`` default.
    """
    if tier_model is None:
        return default
    if isinstance(tier_model, str):
        return tier_model.split(":", 1)[0] or default
    cls_name = type(tier_model).__name__.lower()
    return cls_name.removesuffix("model") or default


@asynccontextmanager
async def track_provider_call(
    tier_model: str | Model | None,
    default_provider: str,
) -> AsyncIterator[None]:
    """Async context manager wrapping one LLM call with health metrics.

    Usage::

        async with track_provider_call(tier_model, settings.llm_provider):
            result = await agent.run(...)

    Fail-open behavior: if ``record_call`` itself raises, the underlying
    result is still returned (or the original exception re-raised).
    Never let instrumentation block provider calls.

    Args:
        tier_model: The resolved tier model passed into the LLM call
            (used only for provider name extraction).
        default_provider: Fallback provider name when ``tier_model`` is
            ``None`` — typically ``settings.llm_provider``.
    """
    tracker = get_provider_health_tracker()
    provider = _extract_provider_name(tier_model, default_provider)
    t0 = time.monotonic()
    try:
        yield
    except Exception:
        latency_ms = (time.monotonic() - t0) * 1000
        try:
            tracker.record_call(provider, latency_ms=latency_ms, success=False)
        except Exception:
            logger.warning("agent.provider_health.record_failed", exc_info=True)
        raise
    else:
        latency_ms = (time.monotonic() - t0) * 1000
        try:
            tracker.record_call(provider, latency_ms=latency_ms, success=True)
        except Exception:
            logger.warning("agent.provider_health.record_failed", exc_info=True)


_health_tracker: ProviderHealthTracker | None = None


def get_provider_health_tracker() -> ProviderHealthTracker:
    """Get or create the provider health tracker singleton."""
    global _health_tracker
    if _health_tracker is None:
        _health_tracker = ProviderHealthTracker()
    return _health_tracker


def reset_provider_health_tracker() -> None:
    """Replace the singleton with a fresh instance. Test-only helper."""
    global _health_tracker
    _health_tracker = None


__all__ = [
    "ProviderHealth",
    "ProviderHealthTracker",
    "_extract_provider_name",
    "get_provider_health_tracker",
    "reset_provider_health_tracker",
    "track_provider_call",
]
