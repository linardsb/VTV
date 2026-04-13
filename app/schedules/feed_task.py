"""Daily GTFS static auto-import background task (LV-1.2).

Sleeps until the configured hour, then downloads and imports GTFS
static data for all enabled feeds with a static_url configured.
"""

from __future__ import annotations

import asyncio
import datetime

from app.core.config import get_settings
from app.core.database import get_db_context
from app.core.logging import get_logger

logger = get_logger(__name__)

_task: asyncio.Task[None] | None = None


async def _run_daily_feed_import() -> None:
    """Loop: sleep until next run hour, then import all enabled feeds."""
    settings = get_settings()

    while True:
        now = datetime.datetime.now(datetime.UTC)
        next_run = now.replace(
            hour=settings.gtfs_auto_import_hour_utc, minute=0, second=0, microsecond=0
        )
        if next_run <= now:
            next_run += datetime.timedelta(days=1)

        sleep_seconds = (next_run - now).total_seconds()
        logger.info(
            "schedules.feed_task.sleep_started",
            next_run=next_run.isoformat(),
            sleep_seconds=round(sleep_seconds),
        )
        await asyncio.sleep(sleep_seconds)

        for feed in settings.transit_feeds:
            if not feed.enabled or not feed.static_url:
                continue
            try:
                async with get_db_context() as db:
                    from app.schedules.service import ScheduleService

                    service = ScheduleService(db)
                    result = await service.import_feed_from_url(feed.feed_id)
                    logger.info(
                        "schedules.feed_task.import_completed",
                        feed_id=feed.feed_id,
                        routes=result.routes_count,
                        trips=result.trips_count,
                    )
            except Exception:
                logger.error(
                    "schedules.feed_task.import_failed",
                    feed_id=feed.feed_id,
                    exc_info=True,
                )


async def start_feed_import_task() -> None:
    """Start the daily feed import background task if enabled."""
    global _task
    settings = get_settings()
    if not settings.gtfs_auto_import_enabled:
        return
    _task = asyncio.create_task(_run_daily_feed_import())
    logger.info("schedules.feed_task.lifecycle_started")


async def stop_feed_import_task() -> None:
    """Stop the daily feed import background task."""
    global _task
    if _task and not _task.done():
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass
    _task = None
    logger.info("schedules.feed_task.lifecycle_stopped")
