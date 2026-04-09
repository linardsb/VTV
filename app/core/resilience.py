"""Circuit breaker pattern for resilient external service calls.

Prevents cascading failures by tracking consecutive errors and
short-circuiting requests when a service is unhealthy. Particularly
important for GTFS-RT feeds where stale data is preferable to no data.

States:
    CLOSED  - Normal operation; requests flow through.
    OPEN    - Service is unhealthy; requests fail fast.
    HALF_OPEN - Testing recovery; a single request is allowed through.
"""

from __future__ import annotations

import asyncio
import enum
import time
from types import TracebackType

from app.core.logging import get_logger

logger = get_logger(__name__)


class CircuitState(enum.Enum):
    """Circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(Exception):
    """Raised when a call is attempted while the circuit is open.

    Attributes:
        breaker_name: Name of the circuit breaker that rejected the call.
        retry_after: Seconds until the circuit transitions to half-open.
    """

    def __init__(self, breaker_name: str, retry_after: float) -> None:
        self.breaker_name = breaker_name
        self.retry_after = retry_after
        super().__init__(
            f"Circuit breaker '{breaker_name}' is open. Retry after {retry_after:.1f}s."
        )


class CircuitBreaker:
    """Async circuit breaker for protecting external service calls.

    Usage as an async context manager::

        breaker = CircuitBreaker(name="my-service")

        async with breaker:
            result = await call_external_service()

    Args:
        name: Human-readable name for logging.
        failure_threshold: Consecutive failures before opening the circuit.
        reset_timeout: Seconds to wait before transitioning from OPEN to HALF_OPEN.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        reset_timeout: float = 30.0,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout

        self._state = CircuitState.CLOSED
        self._failure_count: int = 0
        self._last_failure_time: float = 0.0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        """Current circuit state."""
        return self._state

    async def __aenter__(self) -> CircuitBreaker:
        """Check circuit state before allowing the call through.

        Raises:
            CircuitOpenError: If the circuit is open and reset timeout hasn't elapsed.
        """
        async with self._lock:
            if self._state == CircuitState.CLOSED:
                return self

            if self._state == CircuitState.OPEN:
                elapsed = time.monotonic() - self._last_failure_time
                if elapsed >= self.reset_timeout:
                    self._state = CircuitState.HALF_OPEN
                    logger.info(
                        "resilience.circuit_breaker.state_changed",
                        breaker=self.name,
                        from_state=CircuitState.OPEN.value,
                        to_state=CircuitState.HALF_OPEN.value,
                    )
                    return self

                retry_after = self.reset_timeout - elapsed
                raise CircuitOpenError(self.name, retry_after)

            # HALF_OPEN — allow the probe request through
            return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool:
        """Record success or failure after the call completes.

        Returns:
            False — exceptions are never suppressed.
        """
        async with self._lock:
            if exc_type is None:
                await self._record_success()
            else:
                await self._record_failure()
        return False

    async def _record_success(self) -> None:
        """Reset failure count and close the circuit on success."""
        if self._state != CircuitState.CLOSED:
            old_state = self._state
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            logger.info(
                "resilience.circuit_breaker.state_changed",
                breaker=self.name,
                from_state=old_state.value,
                to_state=CircuitState.CLOSED.value,
            )
        elif self._failure_count > 0:
            self._failure_count = 0

    async def _record_failure(self) -> None:
        """Increment failure count and potentially open the circuit."""
        self._failure_count += 1
        self._last_failure_time = time.monotonic()

        if self._state == CircuitState.HALF_OPEN or self._failure_count >= self.failure_threshold:
            old_state = self._state
            self._state = CircuitState.OPEN
            logger.warning(
                "resilience.circuit_breaker.state_changed",
                breaker=self.name,
                from_state=old_state.value,
                to_state=CircuitState.OPEN.value,
                failure_count=self._failure_count,
            )
