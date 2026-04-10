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
from dataclasses import dataclass

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
