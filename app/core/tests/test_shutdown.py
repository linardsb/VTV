"""Tests for the shutdown coordinator."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from app.core.shutdown import ShutdownCoordinator, ShutdownReport, ShutdownTask


@pytest.mark.asyncio
async def test_shutdown_lifo_drain_order() -> None:
    """Tasks drain in LIFO order (last registered = first drained)."""
    call_order: list[str] = []

    async def drain_a() -> None:
        call_order.append("A")

    async def drain_b() -> None:
        call_order.append("B")

    async def drain_c() -> None:
        call_order.append("C")

    coordinator = ShutdownCoordinator()
    coordinator.register(ShutdownTask(name="A", drain_timeout_s=1.0, drain=drain_a))
    coordinator.register(ShutdownTask(name="B", drain_timeout_s=1.0, drain=drain_b))
    coordinator.register(ShutdownTask(name="C", drain_timeout_s=1.0, drain=drain_c))

    await coordinator.shutdown()

    assert call_order == ["C", "B", "A"]


@pytest.mark.asyncio
async def test_shutdown_drain_timeout_enforced() -> None:
    """A task that exceeds its timeout appears in tasks_timed_out."""

    async def slow_drain() -> None:
        await asyncio.sleep(10)

    coordinator = ShutdownCoordinator()
    coordinator.register(ShutdownTask(name="slow", drain_timeout_s=0.1, drain=slow_drain))

    report = await coordinator.shutdown()

    assert report.tasks_timed_out == ["slow"]
    assert report.tasks_drained == 0


@pytest.mark.asyncio
async def test_shutdown_drain_timeout_does_not_affect_fast_tasks() -> None:
    """A fast task completes normally even with a large timeout budget."""
    coordinator = ShutdownCoordinator()
    coordinator.register(ShutdownTask(name="fast", drain_timeout_s=5.0, drain=AsyncMock()))

    report = await coordinator.shutdown()

    assert report.tasks_drained == 1
    assert report.tasks_timed_out == []


@pytest.mark.asyncio
async def test_shutdown_drain_failure_continues_next_task() -> None:
    """A failing task does not prevent subsequent tasks from draining."""

    async def failing_drain() -> None:
        msg = "drain exploded"
        raise RuntimeError(msg)

    ok_drain = AsyncMock()

    coordinator = ShutdownCoordinator()
    # Register ok first, failing second -> LIFO drains failing first, then ok
    coordinator.register(ShutdownTask(name="ok", drain_timeout_s=1.0, drain=ok_drain))
    coordinator.register(ShutdownTask(name="failing", drain_timeout_s=1.0, drain=failing_drain))

    report = await coordinator.shutdown()

    assert report.tasks_failed == ["failing"]
    assert report.tasks_drained == 1
    ok_drain.assert_awaited_once()


@pytest.mark.asyncio
async def test_shutdown_report_aggregation() -> None:
    """Report correctly aggregates success, timeout, and failure counts."""

    async def timeout_drain() -> None:
        await asyncio.sleep(10)

    async def failing_drain() -> None:
        msg = "boom"
        raise RuntimeError(msg)

    coordinator = ShutdownCoordinator()
    coordinator.register(ShutdownTask(name="success", drain_timeout_s=1.0, drain=AsyncMock()))
    coordinator.register(ShutdownTask(name="timeout", drain_timeout_s=0.05, drain=timeout_drain))
    coordinator.register(ShutdownTask(name="failure", drain_timeout_s=1.0, drain=failing_drain))

    report = await coordinator.shutdown()

    # LIFO: failure, timeout, success
    assert report.tasks_failed == ["failure"]
    assert report.tasks_timed_out == ["timeout"]
    assert report.tasks_drained == 1
    assert report.total_duration_ms > 0


@pytest.mark.asyncio
async def test_shutdown_empty_coordinator_noop() -> None:
    """Shutdown with no tasks returns empty report without errors."""
    coordinator = ShutdownCoordinator()
    report = await coordinator.shutdown()

    assert report == ShutdownReport()


@pytest.mark.asyncio
async def test_shutdown_task_registration_idempotent() -> None:
    """Registering the same task name twice keeps only the first."""
    coordinator = ShutdownCoordinator()
    drain1 = AsyncMock()
    drain2 = AsyncMock()
    coordinator.register(ShutdownTask(name="dup", drain_timeout_s=1.0, drain=drain1))
    coordinator.register(ShutdownTask(name="dup", drain_timeout_s=2.0, drain=drain2))

    assert len(coordinator._tasks) == 1

    await coordinator.shutdown()
    drain1.assert_awaited_once()
    drain2.assert_not_awaited()


@pytest.mark.asyncio
async def test_shutdown_logs_structured_events() -> None:
    """Coordinator emits structured log events for started, drained, completed."""
    coordinator = ShutdownCoordinator()
    coordinator.register(ShutdownTask(name="task_a", drain_timeout_s=1.0, drain=AsyncMock()))

    with patch("app.core.shutdown.logger") as mock_logger:
        await coordinator.shutdown()

    # Verify key structured events
    info_calls = [call.args[0] for call in mock_logger.info.call_args_list]
    assert "shutdown.coordinator.started" in info_calls
    assert "shutdown.task.drained" in info_calls
    assert "shutdown.coordinator.completed" in info_calls


@pytest.mark.asyncio
async def test_shutdown_startup_failure_triggers_partial_drain() -> None:
    """Only registered tasks are drained; unregistered tasks are not affected."""
    drain_b = AsyncMock()

    coordinator = ShutdownCoordinator()
    # Only register B (simulating A failed to start and was never registered)
    coordinator.register(ShutdownTask(name="B", drain_timeout_s=1.0, drain=drain_b))

    report = await coordinator.shutdown()

    assert report.tasks_drained == 1
    drain_b.assert_awaited_once()


@pytest.mark.asyncio
async def test_shutdown_total_duration_ms_populated() -> None:
    """total_duration_ms is populated after draining tasks."""
    coordinator = ShutdownCoordinator()
    coordinator.register(ShutdownTask(name="quick", drain_timeout_s=1.0, drain=AsyncMock()))

    report = await coordinator.shutdown()

    assert report.total_duration_ms >= 0
