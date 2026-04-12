"""Graceful shutdown coordinator for background lifespan tasks."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class ShutdownTask:
    """A registered background task with its drain function and timeout budget."""

    name: str
    drain_timeout_s: float
    drain: Callable[[], Awaitable[None]]


@dataclass
class ShutdownReport:
    """Summary of a completed shutdown sequence."""

    tasks_drained: int = 0
    tasks_timed_out: list[str] = field(default_factory=lambda: list[str]())
    tasks_failed: list[str] = field(default_factory=lambda: list[str]())
    total_duration_ms: int = 0


class ShutdownCoordinator:
    """Coordinates graceful shutdown of registered background tasks.

    Tasks are drained in LIFO order (last registered = first drained).
    Each task gets an individual timeout budget. Failures in one task
    do not prevent draining subsequent tasks.
    """

    def __init__(self) -> None:
        self._tasks: list[ShutdownTask] = []

    def register(self, task: ShutdownTask) -> None:
        """Register a task for coordinated shutdown.

        Args:
            task: The shutdown task to register. Duplicate names are
                  silently ignored (idempotent registration).
        """
        if any(t.name == task.name for t in self._tasks):
            return
        self._tasks.append(task)
        logger.debug(
            "shutdown.task.registered",
            task_name=task.name,
            drain_timeout_s=task.drain_timeout_s,
        )

    async def shutdown(self) -> ShutdownReport:
        """Drain all registered tasks in LIFO order.

        Returns:
            ShutdownReport summarizing drain results.
        """
        report = ShutdownReport()
        start = time.monotonic()

        if not self._tasks:
            logger.info("shutdown.coordinator.no_tasks")
            return report

        # LIFO order: last registered = first drained
        drain_order = list(reversed(self._tasks))
        logger.info(
            "shutdown.coordinator.started",
            task_count=len(drain_order),
            task_names=[t.name for t in drain_order],
        )

        for task in drain_order:
            task_start = time.monotonic()
            try:
                await asyncio.wait_for(task.drain(), timeout=task.drain_timeout_s)
                elapsed_ms = int((time.monotonic() - task_start) * 1000)
                report.tasks_drained += 1
                logger.info(
                    "shutdown.task.drained",
                    task_name=task.name,
                    duration_ms=elapsed_ms,
                )
            except TimeoutError:
                elapsed_ms = int((time.monotonic() - task_start) * 1000)
                report.tasks_timed_out.append(task.name)
                logger.warning(
                    "shutdown.task.timeout",
                    task_name=task.name,
                    drain_timeout_s=task.drain_timeout_s,
                    duration_ms=elapsed_ms,
                )
            except Exception:
                elapsed_ms = int((time.monotonic() - task_start) * 1000)
                report.tasks_failed.append(task.name)
                logger.error(
                    "shutdown.task.failed",
                    task_name=task.name,
                    duration_ms=elapsed_ms,
                    exc_info=True,
                )

        report.total_duration_ms = int((time.monotonic() - start) * 1000)
        logger.info(
            "shutdown.coordinator.completed",
            tasks_drained=report.tasks_drained,
            tasks_timed_out=report.tasks_timed_out,
            tasks_failed=report.tasks_failed,
            total_duration_ms=report.total_duration_ms,
        )
        return report
