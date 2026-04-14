"""KB-4: Background tasks for tuned RRF weight recomputation.

When ``background_queue_enabled`` is ``True`` the daily recompute runs
as an arq cron job (see ``app/core/jobs/worker.py``). Otherwise we
fall back to an in-process loop that sleeps until the configured UTC
hour, recomputes, and repeats. The loop respects a shutdown event so
tests and graceful shutdown terminate deterministically (anti-pattern
#62).
"""

from __future__ import annotations

import asyncio
import datetime

from app.core.config import get_settings
from app.core.database import get_db_context
from app.core.logging import get_logger
from app.core.metrics import record_poller_tick
from app.core.redis import get_redis
from app.knowledge.feedback import FeedbackService

logger = get_logger(__name__)

_recompute_task: asyncio.Task[None] | None = None
_shutdown_event: asyncio.Event | None = None


async def _run_recompute() -> None:
    """Execute one RRF weight recompute cycle."""
    async with get_db_context() as db:
        redis = await get_redis()
        service = FeedbackService(db, redis)
        weights = await service.recompute_weights()
    logger.info(
        "knowledge.lifecycle.rrf_recompute_completed",
        query_types=list(weights),
    )
    record_poller_tick("knowledge_rrf_recompute")


async def _run_daily_at_hour(
    hour: int,
    shutdown_event: asyncio.Event,
) -> None:
    """Loop: sleep until ``hour`` UTC, recompute, repeat (KB-4)."""
    while not shutdown_event.is_set():
        now = datetime.datetime.now(datetime.UTC)
        target = now.replace(hour=hour, minute=15, second=0, microsecond=0)
        if target <= now:
            target += datetime.timedelta(days=1)
        wait_seconds = (target - now).total_seconds()
        logger.info(
            "knowledge.lifecycle.rrf_next_run",
            wait_seconds=int(wait_seconds),
            target_hour=hour,
        )
        try:
            await asyncio.wait_for(shutdown_event.wait(), timeout=wait_seconds)
            return
        except TimeoutError:
            pass
        if shutdown_event.is_set():
            return
        try:
            await _run_recompute()
        except Exception as exc:
            logger.warning(
                "knowledge.rrf.recompute_failed",
                stage="lifecycle_loop",
                error=str(exc),
                error_type=type(exc).__name__,
            )
            if shutdown_event.is_set():
                return


async def start_knowledge_tasks() -> None:
    """Start the KB-4 RRF recompute loop (in-process fallback)."""
    global _recompute_task, _shutdown_event
    settings = get_settings()

    if not settings.knowledge_feedback_enabled:
        logger.info("knowledge.lifecycle.disabled")
        return

    if settings.background_queue_enabled:
        logger.info("knowledge.lifecycle.deferred_to_queue")
        return

    _shutdown_event = asyncio.Event()
    _recompute_task = asyncio.create_task(
        _run_daily_at_hour(settings.knowledge_rrf_recompute_cron_hour, _shutdown_event)
    )
    logger.info(
        "knowledge.lifecycle.tasks_started",
        recompute_hour=settings.knowledge_rrf_recompute_cron_hour,
    )


async def stop_knowledge_tasks() -> None:
    """Signal shutdown and await the recompute loop's exit."""
    global _recompute_task, _shutdown_event

    if _shutdown_event is not None:
        _shutdown_event.set()

    if _recompute_task is not None:
        try:
            await asyncio.wait_for(_recompute_task, timeout=5.0)
        except (TimeoutError, asyncio.CancelledError):
            _recompute_task.cancel()
            try:
                await _recompute_task
            except asyncio.CancelledError:
                pass
        except Exception:
            logger.warning("knowledge.lifecycle.recompute_stop_failed", exc_info=True)

    _recompute_task = None
    _shutdown_event = None
    logger.info("knowledge.lifecycle.tasks_stopped")
