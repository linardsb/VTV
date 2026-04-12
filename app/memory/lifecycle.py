"""Memory background tasks: periodic compaction and promotion.

Registers as lifespan tasks in app/main.py. Follows the same
start_*/stop_* pattern as transit pollers and evaluators.
"""

from __future__ import annotations

import asyncio
import datetime
from collections.abc import Awaitable, Callable

from app.core.config import get_settings
from app.core.database import get_db_context
from app.core.logging import get_logger
from app.core.metrics import record_poller_tick
from app.memory.service import MemoryService

logger = get_logger(__name__)

_compaction_task: asyncio.Task[None] | None = None
_promotion_task: asyncio.Task[None] | None = None


async def _run_at_hour(hour: int, name: str, coro_factory: Callable[[], Awaitable[None]]) -> None:
    """Run a coroutine daily at a specific UTC hour."""
    while True:
        now = datetime.datetime.now(datetime.UTC)
        target = now.replace(hour=hour, minute=0, second=0, microsecond=0)
        if target <= now:
            target += datetime.timedelta(days=1)
        wait_seconds = (target - now).total_seconds()
        logger.info(
            f"memory.{name}.next_run",
            wait_seconds=int(wait_seconds),
            target_hour=hour,
        )
        await asyncio.sleep(wait_seconds)
        try:
            await coro_factory()
        except Exception:
            logger.warning(f"memory.{name}.run_failed", exc_info=True)


async def _run_compaction() -> None:
    """Execute one compaction cycle."""
    async with get_db_context() as db:
        service = MemoryService(db)
        result = await service.compact()
    logger.info(
        "memory.lifecycle.compaction_completed",
        decayed_deleted=result.decayed_deleted,
        merged=result.merged,
        promoted=result.promoted,
    )
    record_poller_tick("memory_compaction")


async def _run_promotion() -> None:
    """Execute one promotion cycle."""
    async with get_db_context() as db:
        service = MemoryService(db)
        promoted = await service.promote_episodes()
    logger.info("memory.lifecycle.promotion_completed", promoted_count=promoted)
    record_poller_tick("memory_promotion")


async def start_memory_tasks() -> None:
    """Start periodic memory compaction and promotion tasks."""
    global _compaction_task, _promotion_task
    settings = get_settings()

    if not settings.memory_enabled:
        logger.info("memory.lifecycle.disabled")
        return

    _compaction_task = asyncio.create_task(
        _run_at_hour(settings.memory_compaction_cron_hour, "compaction", _run_compaction)
    )
    _promotion_task = asyncio.create_task(
        _run_at_hour(settings.memory_promotion_cron_hour, "promotion", _run_promotion)
    )
    logger.info(
        "memory.lifecycle.tasks_started",
        compaction_hour=settings.memory_compaction_cron_hour,
        promotion_hour=settings.memory_promotion_cron_hour,
    )


async def stop_memory_tasks() -> None:
    """Cancel and clean up memory background tasks."""
    global _compaction_task, _promotion_task

    for task, name in [(_compaction_task, "compaction"), (_promotion_task, "promotion")]:
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.warning(f"memory.lifecycle.{name}_stop_failed", exc_info=True)

    _compaction_task = None
    _promotion_task = None
    logger.info("memory.lifecycle.tasks_stopped")
