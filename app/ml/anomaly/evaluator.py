# pyright: reportUnknownMemberType=false, reportMissingTypeStubs=false
"""Background anomaly evaluator orchestrator (ML-4.2).

Runs StuckVehicleEvaluator and GPSGapEvaluator on a configurable interval,
persists alerts via AlertInstanceRepository, and deduplicates via
find_active_duplicate().
"""

from __future__ import annotations

import asyncio

from app.alerts.repository import AlertInstanceRepository
from app.core.config import Settings, get_settings
from app.core.database import get_db_context
from app.core.logging import get_logger
from app.core.metrics import record_poller_tick
from app.core.redis import get_redis
from app.ml.anomaly.gps_gap import GPSGapEvaluator
from app.ml.anomaly.stuck import StuckVehicleEvaluator

_evaluator_task: asyncio.Task[None] | None = None
logger = get_logger(__name__)

_stuck_evaluator = StuckVehicleEvaluator()
_gps_gap_evaluator = GPSGapEvaluator()


async def evaluate_anomalies_once() -> int:
    """Run one anomaly detection cycle with both detectors.

    Returns:
        Number of new alerts created.
    """
    total_created = 0
    redis = await get_redis()

    async with get_db_context() as db:
        settings = get_settings()

        # Run stuck vehicle detection
        try:
            stuck_alerts = await _stuck_evaluator.check(db, redis, settings)
        except Exception:
            logger.error("ml.anomaly_evaluator.stuck_check_failed", exc_info=True)
            stuck_alerts = []

        # Run GPS gap detection
        try:
            gap_alerts = await _gps_gap_evaluator.check(db, redis, settings)
        except Exception:
            logger.error("ml.anomaly_evaluator.gps_gap_check_failed", exc_info=True)
            gap_alerts = []

        # Persist alerts with deduplication
        alert_repo = AlertInstanceRepository(db)
        all_alerts = stuck_alerts + gap_alerts

        for alert_data in all_alerts:
            # Dedup: skip if active alert already exists for same entity
            if alert_data.source_entity_type and alert_data.source_entity_id:
                existing = await alert_repo.find_active_duplicate(
                    0,  # No rule_id for anomaly alerts
                    alert_data.source_entity_type,
                    alert_data.source_entity_id,
                )
                if existing:
                    continue

            await alert_repo.create(alert_data)
            total_created += 1

    record_poller_tick("anomaly_evaluator")
    return total_created


async def _evaluator_loop(interval: int) -> None:
    """Main evaluator loop - runs until cancelled.

    Args:
        interval: Seconds between evaluation cycles.
    """
    while True:
        await asyncio.sleep(interval)
        try:
            count = await evaluate_anomalies_once()
            logger.info(
                "ml.anomaly_evaluator.cycle_completed",
                alerts_created=count,
                interval=interval,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.error("ml.anomaly_evaluator.cycle_failed", exc_info=True)


async def start_anomaly_evaluator(settings: Settings) -> None:
    """Start the background anomaly evaluator task.

    Args:
        settings: Application settings (checks enabled flag).
    """
    global _evaluator_task
    if not settings.ml_anomaly_evaluator_enabled:
        logger.info("ml.anomaly_evaluator.lifecycle_skipped", reason="disabled")
        return
    _evaluator_task = asyncio.create_task(
        _evaluator_loop(settings.ml_anomaly_check_interval_seconds),
    )
    logger.info(
        "ml.anomaly_evaluator.lifecycle_started",
        interval=settings.ml_anomaly_check_interval_seconds,
    )


async def stop_anomaly_evaluator() -> None:
    """Stop the background anomaly evaluator task."""
    global _evaluator_task
    if _evaluator_task is None:
        return
    _evaluator_task.cancel()
    try:
        await _evaluator_task
    except asyncio.CancelledError:
        pass
    except Exception:
        logger.error("ml.anomaly_evaluator.shutdown_error", exc_info=True)
    _evaluator_task = None
    logger.info("ml.anomaly_evaluator.lifecycle_stopped")
