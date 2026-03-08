# pyright: reportUnknownMemberType=false, reportMissingTypeStubs=false, reportArgumentType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Background alert evaluator - periodically checks rules against system state."""

from __future__ import annotations

import asyncio
import datetime
import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.alerts.models import AlertRule
from app.alerts.repository import AlertInstanceRepository, AlertRuleRepository
from app.alerts.schemas import AlertInstanceCreate
from app.core.config import Settings
from app.core.database import get_db_context
from app.core.logging import get_logger
from app.core.redis import get_redis
from app.vehicles.models import Vehicle

_evaluator_task: asyncio.Task[None] | None = None
logger = get_logger(__name__)


async def evaluate_rules_once(settings: Settings) -> int:
    """Run one evaluation cycle across all enabled rules.

    Returns:
        Number of new alerts created.
    """
    total_new = 0
    try:
        async with get_db_context() as db:
            rule_repo = AlertRuleRepository(db)
            rules = await rule_repo.get_enabled_rules()
            for rule in rules:
                if rule.rule_type == "maintenance_due":
                    total_new += await _evaluate_maintenance_due(rule, db)
                elif rule.rule_type == "registration_expiry":
                    total_new += await _evaluate_registration_expiry(rule, db)
                elif rule.rule_type == "delay_threshold":
                    total_new += await _evaluate_delay_threshold(rule, settings)
                # "manual" rules are never auto-evaluated
    except Exception:
        logger.error(
            "alerts.evaluator.cycle_failed",
            error_type="EvaluationError",
            exc_info=True,
        )
    return total_new


async def _evaluate_maintenance_due(rule: AlertRule, db: AsyncSession) -> int:
    """Check vehicles with upcoming or overdue maintenance."""
    threshold_days = int(rule.threshold_config.get("days_before", 7))
    cutoff = datetime.datetime.now(tz=datetime.UTC).date() + datetime.timedelta(days=threshold_days)

    result = await db.execute(
        select(Vehicle).where(
            Vehicle.next_maintenance_date.isnot(None),
            Vehicle.next_maintenance_date <= cutoff,
        )
    )
    vehicles = result.scalars().all()

    instance_repo = AlertInstanceRepository(db)
    count = 0
    for vehicle in vehicles:
        existing = await instance_repo.find_active_duplicate(
            rule.id, "vehicle", vehicle.fleet_number
        )
        if existing:
            continue
        data = AlertInstanceCreate(
            title=f"Maintenance due for vehicle {vehicle.fleet_number}",
            severity=rule.severity,
            alert_type=rule.rule_type,
            source_entity_type="vehicle",
            source_entity_id=vehicle.fleet_number,
            rule_id=rule.id,
            details={"days_before": threshold_days},
        )
        await instance_repo.create(data)
        count += 1
    return count


async def _evaluate_registration_expiry(rule: AlertRule, db: AsyncSession) -> int:
    """Check vehicles with upcoming or expired registration."""
    threshold_days = int(rule.threshold_config.get("days_before", 30))
    cutoff = datetime.datetime.now(tz=datetime.UTC).date() + datetime.timedelta(days=threshold_days)

    result = await db.execute(
        select(Vehicle).where(
            Vehicle.registration_expiry.isnot(None),
            Vehicle.registration_expiry <= cutoff,
        )
    )
    vehicles = result.scalars().all()

    instance_repo = AlertInstanceRepository(db)
    count = 0
    for vehicle in vehicles:
        existing = await instance_repo.find_active_duplicate(
            rule.id, "vehicle", vehicle.fleet_number
        )
        if existing:
            continue
        data = AlertInstanceCreate(
            title=f"Registration expiring for vehicle {vehicle.fleet_number}",
            severity=rule.severity,
            alert_type=rule.rule_type,
            source_entity_type="vehicle",
            source_entity_id=vehicle.fleet_number,
            rule_id=rule.id,
            details={"days_before": threshold_days},
        )
        await instance_repo.create(data)
        count += 1
    return count


async def _evaluate_delay_threshold(rule: AlertRule, settings: Settings) -> int:
    """Check transit vehicle delays against threshold from Redis."""
    _ = settings
    delay_seconds = int(rule.threshold_config.get("delay_seconds", 600))
    count = 0

    try:
        redis = await get_redis()
        keys: list[str] = []
        async for key in redis.scan_iter("vehicle:*"):
            keys.append(str(key))

        async with get_db_context() as db:
            instance_repo = AlertInstanceRepository(db)
            for key in keys:
                raw = await redis.get(key)
                if not raw:
                    continue
                try:
                    data = json.loads(str(raw))
                except (json.JSONDecodeError, TypeError):
                    continue

                delay = data.get("delay", 0)
                if not isinstance(delay, int | float) or delay < delay_seconds:
                    continue

                vehicle_id = data.get("vehicle_id", key.split(":")[-1])
                existing = await instance_repo.find_active_duplicate(
                    rule.id, "vehicle", str(vehicle_id)
                )
                if existing:
                    continue

                alert_data = AlertInstanceCreate(
                    title=f"Vehicle {vehicle_id} delayed {int(delay)}s",
                    severity=rule.severity,
                    alert_type="delay_threshold",
                    source_entity_type="vehicle",
                    source_entity_id=str(vehicle_id),
                    rule_id=rule.id,
                    details={"delay_seconds": int(delay), "threshold": delay_seconds},
                )
                await instance_repo.create(alert_data)
                count += 1
    except Exception:
        logger.warning(
            "alerts.evaluator.delay_check_failed",
            exc_info=True,
        )
        return 0

    return count


async def _evaluator_loop(settings: Settings, interval: int) -> None:
    """Main evaluator loop - runs until cancelled."""
    while True:
        await asyncio.sleep(interval)
        try:
            count = await evaluate_rules_once(settings)
            logger.info(
                "alerts.evaluator.cycle_completed",
                new_alerts=count,
                interval=interval,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.error(
                "alerts.evaluator.cycle_failed",
                exc_info=True,
            )


async def start_evaluator(settings: Settings) -> None:
    """Start the background alert evaluator task."""
    global _evaluator_task
    if not settings.alerts_enabled:
        logger.info("alerts.evaluator.lifecycle_skipped", reason="disabled")
        return
    _evaluator_task = asyncio.create_task(
        _evaluator_loop(settings, settings.alerts_check_interval_seconds)
    )
    logger.info(
        "alerts.evaluator.lifecycle_started",
        interval=settings.alerts_check_interval_seconds,
    )


async def stop_evaluator() -> None:
    """Stop the background alert evaluator task."""
    global _evaluator_task
    if _evaluator_task is None:
        return
    _evaluator_task.cancel()
    try:
        await _evaluator_task
    except asyncio.CancelledError:
        pass
    except Exception:
        logger.error("alerts.evaluator.shutdown_error", exc_info=True)
    _evaluator_task = None
    logger.info("alerts.evaluator.lifecycle_stopped")
