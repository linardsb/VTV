"""Arq job queue wrapper for durable background task execution.

Provides a thin abstraction over arq's Redis-backed job queue with
feature-flag gating. When ``background_queue_enabled`` is ``False``,
``enqueue()`` is a no-op that returns ``None``.
"""

from __future__ import annotations

import datetime
from typing import Any
from urllib.parse import urlparse

from arq.connections import ArqRedis, RedisSettings, create_pool
from arq.jobs import Job

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_pool: ArqRedis | None = None


def _parse_redis_settings(redis_url: str) -> RedisSettings:
    """Parse a redis:// URL into Arq's RedisSettings.

    Args:
        redis_url: Full Redis connection URL.

    Returns:
        Arq-compatible RedisSettings instance.
    """
    parsed = urlparse(redis_url)
    return RedisSettings(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        password=parsed.password or None,
        database=int(parsed.path.lstrip("/") or "0"),
    )


async def get_arq_pool() -> ArqRedis:
    """Get or create the Arq Redis connection pool singleton.

    Returns:
        Active Arq Redis connection pool.
    """
    global _pool
    if _pool is None:
        settings = get_settings()
        redis_settings = _parse_redis_settings(settings.redis_url)
        _pool = await create_pool(redis_settings)
        logger.info("jobs.queue.pool_initialized")
    return _pool


async def close_arq_pool() -> None:
    """Close the Arq Redis pool. Called on app shutdown."""
    global _pool
    if _pool is not None:
        try:
            await _pool.aclose()
        except RuntimeError:
            pass  # Event loop already closed
        _pool = None
        logger.info("jobs.queue.pool_closed")


async def enqueue(
    task_name: str,
    *args: Any,  # noqa: ANN401
    _defer_until: datetime.datetime | None = None,
    _job_id: str | None = None,
) -> Job | None:
    """Enqueue a task on the Arq job queue.

    When ``background_queue_enabled`` is ``False``, logs a warning
    and returns ``None`` (no-op).

    Args:
        task_name: Registered arq function name.
        *args: Positional arguments forwarded to the task.
        _defer_until: Optional future datetime to delay execution.
        _job_id: Optional idempotency key to prevent duplicate jobs.

    Returns:
        The enqueued Job reference, or None if the queue is disabled.
    """
    settings = get_settings()
    if not settings.background_queue_enabled:
        logger.warning(
            "jobs.queue.enqueue_skipped",
            task_name=task_name,
            reason="background_queue_enabled=False",
        )
        return None

    pool = await get_arq_pool()
    job = await pool.enqueue_job(
        task_name,
        *args,
        _defer_until=_defer_until,
        _job_id=_job_id,
    )
    logger.info(
        "jobs.queue.job_enqueued",
        task_name=task_name,
        job_id=_job_id,
    )
    return job
