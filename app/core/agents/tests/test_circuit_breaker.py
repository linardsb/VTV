"""Unit tests for the LLM provider circuit breaker (AI-8.1)."""

from __future__ import annotations

import asyncio

import pytest
from structlog.testing import capture_logs

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


def _state(breaker: CircuitBreaker) -> CircuitState:
    """Return ``breaker.state`` through a helper to defeat mypy's
    per-property literal narrowing across multiple identity-check asserts.
    """
    return breaker.state


# --- State transitions --------------------------------------------------


@pytest.mark.asyncio
async def test_starts_closed() -> None:
    breaker = make_breaker()
    assert _state(breaker) is CircuitState.CLOSED
    assert await breaker.call(_ok) == "ok"
    assert _state(breaker) is CircuitState.CLOSED


@pytest.mark.asyncio
async def test_closed_to_open_on_consecutive_failures() -> None:
    breaker = make_breaker(config=make_breaker_config(failure_threshold=3))
    for _ in range(3):
        with pytest.raises(RuntimeError):
            await breaker.call(_fail)
    assert _state(breaker) is CircuitState.OPEN

    call_count = 0

    async def counting_fn() -> None:
        nonlocal call_count
        call_count += 1

    with pytest.raises(CircuitBreakerOpenError):
        await breaker.call(counting_fn)
    assert call_count == 0


@pytest.mark.asyncio
async def test_closed_to_open_on_sliding_window_rate() -> None:
    # failure_threshold high so only the window-rate trigger can fire.
    breaker = make_breaker(
        config=make_breaker_config(
            failure_threshold=100,
            window_size=10,
            failure_rate_threshold=0.5,
        )
    )

    # 5 alternating failure/success entries then 5 more failures → 10/10 window,
    # with 5 failures and 5 successes → rate = 0.5 → trips.
    for _ in range(5):
        with pytest.raises(RuntimeError):
            await breaker.call(_fail)
        await breaker.call(_ok)

    # The window is now full with 5 fails + 5 successes (rate == 0.5),
    # but the last entry was a success. The next failure keeps rate >= 0.5
    # and should trip the breaker.
    with pytest.raises(RuntimeError):
        await breaker.call(_fail)

    assert _state(breaker) is CircuitState.OPEN


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
    assert _state(breaker) is CircuitState.OPEN

    clock.advance(10.0)
    assert await breaker.call(_ok) == "ok"
    assert _state(breaker) is CircuitState.HALF_OPEN


@pytest.mark.asyncio
async def test_half_open_to_closed_after_success_threshold() -> None:
    clock = ManualClock()
    breaker = make_breaker(
        config=make_breaker_config(
            failure_threshold=2,
            recovery_timeout_s=10.0,
            success_threshold=2,
        ),
        clock=clock,
    )
    for _ in range(2):
        with pytest.raises(RuntimeError):
            await breaker.call(_fail)
    clock.advance(10.0)

    await breaker.call(_ok)  # probe 1 -> HALF_OPEN
    assert _state(breaker) is CircuitState.HALF_OPEN
    await breaker.call(_ok)  # probe 2 -> CLOSED
    assert _state(breaker) is CircuitState.CLOSED


@pytest.mark.asyncio
async def test_half_open_to_open_on_any_failure() -> None:
    clock = ManualClock()
    breaker = make_breaker(
        config=make_breaker_config(
            failure_threshold=2,
            recovery_timeout_s=10.0,
            success_threshold=2,
        ),
        clock=clock,
    )
    for _ in range(2):
        with pytest.raises(RuntimeError):
            await breaker.call(_fail)
    clock.advance(10.0)

    with pytest.raises(RuntimeError):
        await breaker.call(_fail)  # probe fails
    assert _state(breaker) is CircuitState.OPEN

    # Without advancing the clock, next call is rejected.
    with pytest.raises(CircuitBreakerOpenError):
        await breaker.call(_ok)


# --- Failure counting & success reset -----------------------------------


@pytest.mark.asyncio
async def test_success_in_closed_resets_consecutive_failures() -> None:
    breaker = make_breaker(config=make_breaker_config(failure_threshold=3))
    with pytest.raises(RuntimeError):
        await breaker.call(_fail)
    with pytest.raises(RuntimeError):
        await breaker.call(_fail)
    await breaker.call(_ok)  # reset consecutive
    with pytest.raises(RuntimeError):
        await breaker.call(_fail)
    with pytest.raises(RuntimeError):
        await breaker.call(_fail)
    assert _state(breaker) is CircuitState.CLOSED


@pytest.mark.asyncio
async def test_window_pruning_at_maxlen() -> None:
    breaker = make_breaker(
        config=make_breaker_config(
            failure_threshold=100,
            window_size=4,
            failure_rate_threshold=0.9,
        )
    )
    # Fill window with failures (rate = 1.0 → trips at step 4).
    # Threshold is 0.9 and consecutive is 100 so only rate should trip.
    with pytest.raises(RuntimeError):
        await breaker.call(_fail)
    with pytest.raises(RuntimeError):
        await breaker.call(_fail)
    with pytest.raises(RuntimeError):
        await breaker.call(_fail)
    with pytest.raises(RuntimeError):
        await breaker.call(_fail)
    assert _state(breaker) is CircuitState.OPEN


@pytest.mark.asyncio
async def test_failure_rate_threshold_needs_full_window() -> None:
    # 2 failures out of 2 calls = 100% but window not full → should NOT trip
    # on rate because len(window) < window_size. With failure_threshold=10,
    # the consecutive trigger is also not armed.
    breaker = make_breaker(
        config=make_breaker_config(
            failure_threshold=10,
            window_size=10,
            failure_rate_threshold=0.5,
        )
    )
    with pytest.raises(RuntimeError):
        await breaker.call(_fail)
    with pytest.raises(RuntimeError):
        await breaker.call(_fail)
    assert _state(breaker) is CircuitState.CLOSED


# --- Recovery timeout ---------------------------------------------------


@pytest.mark.asyncio
async def test_call_rejected_before_recovery_timeout() -> None:
    clock = ManualClock()
    breaker = make_breaker(
        config=make_breaker_config(failure_threshold=2, recovery_timeout_s=10.0),
        clock=clock,
    )
    for _ in range(2):
        with pytest.raises(RuntimeError):
            await breaker.call(_fail)

    clock.advance(9.99)  # just below threshold
    call_count = 0

    async def counting_fn() -> None:
        nonlocal call_count
        call_count += 1

    with pytest.raises(CircuitBreakerOpenError):
        await breaker.call(counting_fn)
    assert call_count == 0


@pytest.mark.asyncio
async def test_recovery_probe_exactly_at_timeout() -> None:
    clock = ManualClock()
    breaker = make_breaker(
        config=make_breaker_config(failure_threshold=2, recovery_timeout_s=10.0),
        clock=clock,
    )
    for _ in range(2):
        with pytest.raises(RuntimeError):
            await breaker.call(_fail)

    clock.advance(10.0)  # exactly at boundary
    assert await breaker.call(_ok) == "ok"
    assert _state(breaker) is CircuitState.HALF_OPEN


# --- Sliding window rate ------------------------------------------------


@pytest.mark.asyncio
async def test_rate_resets_after_close() -> None:
    clock = ManualClock()
    breaker = make_breaker(
        config=make_breaker_config(
            failure_threshold=3,
            recovery_timeout_s=5.0,
            success_threshold=2,
            window_size=10,
        ),
        clock=clock,
    )
    for _ in range(3):
        with pytest.raises(RuntimeError):
            await breaker.call(_fail)
    assert _state(breaker) is CircuitState.OPEN

    clock.advance(5.0)
    await breaker.call(_ok)  # HALF_OPEN probe 1
    await breaker.call(_ok)  # HALF_OPEN probe 2 -> CLOSED
    assert _state(breaker) is CircuitState.CLOSED
    # Internal window cleared on CLOSE: failure_rate starts from zero.
    assert breaker._failure_rate() == 0.0


@pytest.mark.asyncio
async def test_consecutive_does_not_count_old_failures_after_success() -> None:
    breaker = make_breaker(config=make_breaker_config(failure_threshold=3))
    with pytest.raises(RuntimeError):
        await breaker.call(_fail)
    with pytest.raises(RuntimeError):
        await breaker.call(_fail)
    await breaker.call(_ok)  # resets consecutive
    with pytest.raises(RuntimeError):
        await breaker.call(_fail)
    # 1 consecutive failure after the success, so breaker is still CLOSED.
    assert _state(breaker) is CircuitState.CLOSED


# --- Concurrent calls ---------------------------------------------------


@pytest.mark.asyncio
async def test_concurrent_calls_share_state_atomically() -> None:
    breaker = make_breaker(config=make_breaker_config(failure_threshold=3))

    # Phase 1: trip the breaker sequentially.
    for _ in range(3):
        with pytest.raises(RuntimeError):
            await breaker.call(_fail)
    assert _state(breaker) is CircuitState.OPEN

    # Phase 2: concurrent calls after the breaker is already OPEN must
    # fast-fail atomically — every task should see OPEN and be rejected.
    async def never_called() -> None:
        raise AssertionError("fn must not be invoked while breaker is OPEN")

    results = await asyncio.gather(
        *(breaker.call(never_called) for _ in range(10)),
        return_exceptions=True,
    )
    assert all(isinstance(r, CircuitBreakerOpenError) for r in results)
    assert _state(breaker) is CircuitState.OPEN


@pytest.mark.asyncio
async def test_sequential_probes_transition_to_closed() -> None:
    # Substitute for "only one probe at a time" — two sequential probes
    # close the breaker.
    clock = ManualClock()
    breaker = make_breaker(
        config=make_breaker_config(
            failure_threshold=2,
            recovery_timeout_s=5.0,
            success_threshold=2,
        ),
        clock=clock,
    )
    for _ in range(2):
        with pytest.raises(RuntimeError):
            await breaker.call(_fail)
    clock.advance(5.0)

    assert await breaker.call(_ok) == "ok"
    assert await breaker.call(_ok) == "ok"
    assert _state(breaker) is CircuitState.CLOSED


# --- Config gating & invariants -----------------------------------------


def test_breaker_config_validates_inputs() -> None:
    with pytest.raises(ValueError):
        BreakerConfig(failure_threshold=0)
    with pytest.raises(ValueError):
        BreakerConfig(recovery_timeout_s=-1.0)
    with pytest.raises(ValueError):
        BreakerConfig(success_threshold=0)
    with pytest.raises(ValueError):
        BreakerConfig(window_size=0)
    with pytest.raises(ValueError):
        BreakerConfig(failure_rate_threshold=0.0)
    with pytest.raises(ValueError):
        BreakerConfig(failure_rate_threshold=1.1)


@pytest.mark.asyncio
async def test_exception_type_is_preserved() -> None:
    breaker = make_breaker()

    async def boom() -> None:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        await breaker.call(boom)


@pytest.mark.asyncio
async def test_log_events_emitted() -> None:
    breaker = make_breaker(
        name="test-provider",
        config=make_breaker_config(failure_threshold=2),
    )
    with capture_logs() as captured:
        with pytest.raises(RuntimeError):
            await breaker.call(_fail)
        with pytest.raises(RuntimeError):
            await breaker.call(_fail)

    assert _state(breaker) is CircuitState.OPEN
    opened_events = [
        entry for entry in captured if entry.get("event") == "agent.circuit_breaker.opened"
    ]
    assert len(opened_events) == 1
    entry = opened_events[0]
    assert entry["provider"] == "test-provider"
    assert entry["trigger"] == "consecutive"


@pytest.mark.asyncio
async def test_full_happy_path_spec_scenario() -> None:
    """5 failures → OPEN → reject → recovery → 2 probes → CLOSED."""
    clock = ManualClock()
    breaker = make_breaker(
        config=make_breaker_config(
            failure_threshold=5,
            recovery_timeout_s=30.0,
            success_threshold=2,
        ),
        clock=clock,
    )

    for _ in range(5):
        with pytest.raises(RuntimeError):
            await breaker.call(_fail)
    assert _state(breaker) is CircuitState.OPEN

    call_count = 0

    async def counting_fn() -> str:
        nonlocal call_count
        call_count += 1
        return "ok"

    with pytest.raises(CircuitBreakerOpenError):
        await breaker.call(counting_fn)
    assert call_count == 0

    clock.advance(30.0)
    assert await breaker.call(counting_fn) == "ok"
    assert _state(breaker) is CircuitState.HALF_OPEN
    assert await breaker.call(counting_fn) == "ok"
    assert _state(breaker) is CircuitState.CLOSED
    assert call_count == 2
