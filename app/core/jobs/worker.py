"""Arq worker settings for durable background job execution.

Run with: ``arq app.core.jobs.worker.WorkerSettings``

Schedules memory compaction (every N hours) and promotion (daily at
configured UTC hour) as cron jobs with at-least-once semantics.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, ClassVar

from arq import cron
from arq.connections import RedisSettings
from arq.cron import CronJob
from arq.typing import StartupShutdown, WorkerCoroutine
from arq.worker import Function

from app.core.config import get_settings
from app.core.jobs.queue import _parse_redis_settings
from app.core.logging import get_logger, setup_logging
from app.knowledge.lifecycle import _run_recompute as _run_rrf
from app.memory.lifecycle import _run_compaction, _run_promotion

logger = get_logger(__name__)


async def run_compaction(ctx: dict[str, Any]) -> dict[str, str]:
    """Execute one memory compaction cycle via arq.

    Args:
        ctx: Arq worker context dict.

    Returns:
        Dict with execution status.
    """
    _ = ctx
    try:
        await _run_compaction()
        return {"status": "completed"}
    except Exception:
        logger.error("jobs.worker.compaction_failed", exc_info=True)
        raise


async def run_promotion(ctx: dict[str, Any]) -> dict[str, str]:
    """Execute one memory promotion cycle via arq.

    Args:
        ctx: Arq worker context dict.

    Returns:
        Dict with execution status.
    """
    _ = ctx
    try:
        await _run_promotion()
        return {"status": "completed"}
    except Exception:
        logger.error("jobs.worker.promotion_failed", exc_info=True)
        raise


async def run_daily_adherence(ctx: dict[str, Any]) -> dict[str, str]:
    """Execute one daily adherence report cycle via arq.

    Args:
        ctx: Arq worker context dict.

    Returns:
        Dict with execution status.
    """
    _ = ctx
    try:
        from app.analytics.daily_adherence import _run_daily_adherence

        await _run_daily_adherence()
        return {"status": "completed"}
    except Exception:
        logger.error("jobs.worker.daily_adherence_failed", exc_info=True)
        raise


async def run_rrf_recompute(ctx: dict[str, Any]) -> dict[str, str]:
    """Execute one KB-4 RRF-weight recompute cycle via arq.

    Args:
        ctx: Arq worker context dict.

    Returns:
        Dict with execution status.
    """
    _ = ctx
    try:
        await _run_rrf()
        return {"status": "completed"}
    except Exception:
        logger.error("jobs.worker.rrf_recompute_failed", exc_info=True)
        raise


async def on_startup(ctx: dict[str, Any]) -> None:
    """Worker startup hook - initialize logging."""
    _ = ctx
    settings = get_settings()
    setup_logging(log_level=settings.log_level)
    logger.info("jobs.worker.started")


async def on_shutdown(ctx: dict[str, Any]) -> None:
    """Worker shutdown hook - cleanup."""
    _ = ctx
    logger.info("jobs.worker.stopped")


def _build_cron_jobs() -> list[CronJob]:
    """Build cron job list from settings."""
    settings = get_settings()
    interval = settings.arq_compaction_interval_hours
    compaction_hours = set(range(0, 24, interval))
    promotion_hour = {settings.arq_promotion_cron_hour}

    adherence_hour = {settings.analytics_adherence_cron_hour}

    rrf_hour = {settings.knowledge_rrf_recompute_cron_hour}

    return [
        cron(
            run_compaction,
            hour=compaction_hours,
            minute={0},
            second={0},
            run_at_startup=False,
            unique=True,
        ),
        cron(
            run_promotion,
            hour=promotion_hour,
            minute={0},
            second={0},
            run_at_startup=False,
            unique=True,
        ),
        cron(
            run_daily_adherence,
            hour=adherence_hour,
            minute={0},
            second={0},
            run_at_startup=False,
            unique=True,
        ),
        cron(
            run_rrf_recompute,
            hour=rrf_hour,
            minute={15},
            second={0},
            run_at_startup=False,
            unique=True,
        ),
    ]


def _build_redis_settings() -> RedisSettings:
    """Build Arq RedisSettings from app config."""
    settings = get_settings()
    return _parse_redis_settings(settings.redis_url)


class WorkerSettings:
    """Arq worker configuration.

    Usage::

        arq app.core.jobs.worker.WorkerSettings
    """

    functions: ClassVar[Sequence[WorkerCoroutine | Function]] = [
        run_compaction,
        run_promotion,
        run_daily_adherence,
        run_rrf_recompute,
    ]
    cron_jobs: ClassVar[Sequence[CronJob]] = _build_cron_jobs()
    redis_settings: ClassVar[RedisSettings] = _build_redis_settings()
    max_jobs: ClassVar[int] = get_settings().arq_max_jobs
    job_timeout: ClassVar[int] = get_settings().arq_job_timeout_seconds
    on_startup: ClassVar[StartupShutdown | None] = on_startup
    on_shutdown: ClassVar[StartupShutdown | None] = on_shutdown
