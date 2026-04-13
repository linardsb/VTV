# pyright: reportUnknownMemberType=false, reportMissingTypeStubs=false, reportArgumentType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Background crowding alert evaluator - fires alerts for overcrowded predictions (ML-3.3).

Runs on a 2-minute cycle, scanning active vehicles and creating alerts
when the load prediction model predicts overcrowding.
"""

from __future__ import annotations

import asyncio

from app.alerts.repository import AlertInstanceRepository
from app.alerts.schemas import AlertInstanceCreate
from app.core.config import Settings
from app.core.database import get_db_context
from app.core.logging import get_logger
from app.core.metrics import record_poller_tick
from app.ml.load_service import get_load_service
from app.transit.redis_reader import get_vehicles_from_redis

_crowding_task: asyncio.Task[None] | None = None
logger = get_logger(__name__)


async def evaluate_crowding_once(settings: Settings) -> int:
    """Run one crowding evaluation cycle across all active vehicles.

    Scans vehicle positions from Redis, runs load prediction for each,
    and creates alerts for overcrowded predictions (dedup-checked).

    Args:
        settings: Application settings.

    Returns:
        Number of new alerts created.
    """
    total_new = 0
    load_service = get_load_service(settings)

    try:
        response = await get_vehicles_from_redis()
    except Exception:
        logger.warning("alerts.crowding_evaluator.redis_scan_failed", exc_info=True)
        record_poller_tick("crowding_evaluator")
        return 0

    if not response.vehicles:
        record_poller_tick("crowding_evaluator")
        return 0

    try:
        async with get_db_context() as db:
            instance_repo = AlertInstanceRepository(db)

            for vehicle in response.vehicles:
                try:
                    result = await load_service.predict(db, vehicle.vehicle_id, "")
                except Exception:
                    logger.warning(
                        "alerts.crowding_evaluator.predict_failed",
                        vehicle_id=vehicle.vehicle_id,
                        exc_info=True,
                    )
                    continue

                if result.get("fallback") is True:
                    continue

                crowding = result.get("crowding_bucket")
                if crowding != "overcrowded":
                    continue

                # Dedup check: skip if already alerted for this vehicle
                existing = await instance_repo.find_active_duplicate(
                    rule_id=0,
                    source_entity_type="vehicle",
                    source_entity_id=vehicle.vehicle_id,
                )
                if existing:
                    continue

                alert_data = AlertInstanceCreate(
                    title=(
                        f"Crowding alert: vehicle {vehicle.vehicle_id} "
                        f"on route {vehicle.route_short_name} predicted overcrowded"
                    ),
                    severity="critical",
                    alert_type="crowding_prediction",
                    rule_id=None,
                    source_entity_type="vehicle",
                    source_entity_id=vehicle.vehicle_id,
                    details={
                        "vehicle_id": vehicle.vehicle_id,
                        "route_id": vehicle.route_id,
                        "route_short_name": vehicle.route_short_name,
                        "predicted_passenger_count": result.get("predicted_passenger_count"),
                        "crowding_bucket": crowding,
                        "model_version": result.get("model_version"),
                    },
                )
                await instance_repo.create(alert_data)
                total_new += 1

    except Exception:
        logger.error(
            "alerts.crowding_evaluator.cycle_failed",
            error_type="EvaluationError",
            exc_info=True,
        )
        record_poller_tick("crowding_evaluator")
        return total_new

    record_poller_tick("crowding_evaluator")
    return total_new


async def _crowding_loop(settings: Settings, interval: int) -> None:
    """Main crowding evaluator loop - runs until cancelled."""
    while True:
        await asyncio.sleep(interval)
        try:
            count = await evaluate_crowding_once(settings)
            logger.info(
                "alerts.crowding_evaluator.cycle_completed",
                new_alerts=count,
                interval=interval,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.error(
                "alerts.crowding_evaluator.cycle_failed",
                exc_info=True,
            )


async def start_crowding_evaluator(settings: Settings) -> None:
    """Start the background crowding evaluator task."""
    global _crowding_task
    if not settings.alerts_crowding_enabled:
        logger.info("alerts.crowding_evaluator.lifecycle_skipped", reason="disabled")
        return
    _crowding_task = asyncio.create_task(
        _crowding_loop(settings, settings.alerts_crowding_check_interval_seconds)
    )
    logger.info(
        "alerts.crowding_evaluator.lifecycle_started",
        interval=settings.alerts_crowding_check_interval_seconds,
    )


async def stop_crowding_evaluator() -> None:
    """Stop the background crowding evaluator task."""
    global _crowding_task
    if _crowding_task is None:
        return
    _crowding_task.cancel()
    try:
        await _crowding_task
    except asyncio.CancelledError:
        pass
    except Exception:
        logger.error("alerts.crowding_evaluator.shutdown_error", exc_info=True)
    _crowding_task = None
    logger.info("alerts.crowding_evaluator.lifecycle_stopped")
