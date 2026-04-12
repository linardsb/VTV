"""Circuit breaker state machine for LLM provider resilience (AI-8.1).

Classic 3-state breaker: CLOSED -> OPEN -> HALF_OPEN -> CLOSED.

- CLOSED: all calls pass through. Record success/failure on each outcome.
  Trip to OPEN when either (a) consecutive failures >= failure_threshold
  or (b) failure rate over the last ``window_size`` calls >= failure_rate_threshold.
- OPEN: all calls rejected with CircuitBreakerOpenError (no provider call).
  After recovery_timeout_s, transition to HALF_OPEN on next call attempt.
- HALF_OPEN: calls pass through as probes. After success_threshold successful
  probes in a row, transition to CLOSED (counters reset). Any failure in
  HALF_OPEN immediately returns to OPEN.

Mirrors the GTFS-RT breaker at ``app/core/resilience.py`` but adds sliding-window
rate tracking and a dedicated success-threshold probe path. Kept agent-local
(not in ``app/shared/``) per the three-feature rule.
"""

from __future__ import annotations

import asyncio
import time
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import Enum
from typing import TypeVar

from app.core.agents.exceptions import CircuitBreakerOpenError
from app.core.logging import get_logger
from app.core.metrics import update_circuit_breaker_gauge

logger = get_logger(__name__)

T = TypeVar("T")


class CircuitState(str, Enum):
    """States of the LLM provider circuit breaker."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass(frozen=True)
class BreakerConfig:
    """Immutable configuration for a :class:`CircuitBreaker` instance."""

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
    The internal lock is only held for state reads/writes — never across the
    awaited call to ``fn``.
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
        self._window: deque[bool] = deque(maxlen=self._config.window_size)
        self._lock = asyncio.Lock()

    @property
    def name(self) -> str:
        """Return the provider name this breaker is scoped to."""
        return self._name

    @property
    def state(self) -> CircuitState:
        """Return the current state of the breaker."""
        return self._state

    async def call(
        self,
        fn: Callable[..., Awaitable[T]],
        /,
        *args: object,
        **kwargs: object,
    ) -> T:
        """Invoke ``fn(*args, **kwargs)`` through the breaker.

        Raises:
            CircuitBreakerOpenError: When the breaker is OPEN and the recovery
                timeout has not elapsed.

        Returns:
            Whatever ``fn`` returns. If ``fn`` raises, the exception is
            re-raised after recording the failure.
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
                opened_at = self._opened_at
                if opened_at is None:
                    # Defensive: OPEN without timestamp should be impossible.
                    self._opened_at = self._time_fn()
                    logger.warning(
                        "agent.circuit_breaker.rejected",
                        provider=self._name,
                        state=self._state.value,
                    )
                    raise CircuitBreakerOpenError(f"Circuit breaker {self._name!r} is OPEN")
                elapsed = self._time_fn() - opened_at
                if elapsed >= self._config.recovery_timeout_s:
                    self._transition_to(CircuitState.HALF_OPEN, elapsed_s=elapsed)
                else:
                    logger.info(
                        "agent.circuit_breaker.rejected",
                        provider=self._name,
                        state=self._state.value,
                    )
                    raise CircuitBreakerOpenError(f"Circuit breaker {self._name!r} is OPEN")

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
            event = (
                "agent.circuit_breaker.reopened"
                if old_state is CircuitState.HALF_OPEN
                else "agent.circuit_breaker.opened"
            )
            logger.warning(event, provider=self._name, **log_fields)
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
        update_circuit_breaker_gauge(self._name, new_state.value)
