# pyright: reportUnknownMemberType=false, reportMissingTypeStubs=false, reportArgumentType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Background geofence evaluator - periodically checks vehicle positions against zones."""

from __future__ import annotations

import asyncio
import datetime
import json

from app.alerts.repository import AlertInstanceRepository
from app.alerts.schemas import AlertInstanceCreate
from app.core.config import Settings
from app.core.database import get_db_context
from app.core.logging import get_logger
from app.core.redis import get_redis
from app.geofences.models import Geofence
from app.geofences.repository import GeofenceEventRepository, GeofenceRepository

_evaluator_task: asyncio.Task[None] | None = None
logger = get_logger(__name__)

REDIS_VEHICLE_PREFIX = "vehicle:"
REDIS_GEOFENCE_STATE_PREFIX = "geofence_state:"


async def evaluate_geofences_once() -> int:
    """Run one evaluation cycle checking vehicle positions against geofences.

    Returns:
        Number of new events created.
    """
    total_new = 0
    try:
        redis = await get_redis()

        # Scan all vehicle keys
        vehicle_keys: list[str] = []
        async for key in redis.scan_iter(f"{REDIS_VEHICLE_PREFIX}*"):
            vehicle_keys.append(str(key))

        if not vehicle_keys:
            return 0

        for vkey in vehicle_keys:
            raw = await redis.get(vkey)
            if not raw:
                continue

            try:
                data = json.loads(str(raw))
            except (json.JSONDecodeError, TypeError):
                continue

            lat = data.get("latitude") or data.get("lat")
            lon = data.get("longitude") or data.get("lon")
            if not isinstance(lat, int | float) or not isinstance(lon, int | float):
                continue

            vehicle_id = data.get("vehicle_id", vkey.removeprefix(REDIS_VEHICLE_PREFIX))
            vehicle_id = str(vehicle_id)
            now = datetime.datetime.now(tz=datetime.UTC)

            async with get_db_context() as db:
                geofence_repo = GeofenceRepository(db)
                event_repo = GeofenceEventRepository(db)
                alert_repo = AlertInstanceRepository(db)

                # Check which geofences contain this vehicle
                containing = await geofence_repo.check_containment(float(lat), float(lon))
                current_ids = {g.id for g in containing}

                # Get previous state from Redis
                state_key = f"{REDIS_GEOFENCE_STATE_PREFIX}{vehicle_id}"
                prev_raw = await redis.get(state_key)
                previous_ids: set[int] = set()
                if prev_raw:
                    try:
                        previous_ids = set(json.loads(str(prev_raw)))
                    except (json.JSONDecodeError, TypeError):
                        pass

                # Detect entries (in current, not in previous)
                for geofence in containing:
                    if geofence.id not in previous_ids:
                        await event_repo.create(
                            geofence_id=geofence.id,
                            vehicle_id=vehicle_id,
                            event_type="enter",
                            entered_at=now,
                            latitude=float(lat),
                            longitude=float(lon),
                        )
                        total_new += 1
                        logger.info(
                            "geofences.evaluator.vehicle_entered",
                            vehicle_id=vehicle_id,
                            geofence_id=geofence.id,
                            geofence_name=geofence.name,
                        )

                        if geofence.alert_on_enter:
                            await _create_alert_if_new(
                                alert_repo,
                                alert_type="geofence_enter",
                                vehicle_id=vehicle_id,
                                geofence=geofence,
                                title=f"Vehicle {vehicle_id} entered zone {geofence.name}",
                            )

                # Detect exits (in previous, not in current)
                for prev_id in previous_ids:
                    if prev_id not in current_ids:
                        geo = await geofence_repo.get(prev_id)
                        if not geo:
                            continue

                        # Close open entry
                        open_entry = await event_repo.get_open_entry(prev_id, vehicle_id)
                        if open_entry:
                            await event_repo.close_entry(open_entry, now)

                        await event_repo.create(
                            geofence_id=prev_id,
                            vehicle_id=vehicle_id,
                            event_type="exit",
                            entered_at=now,
                            latitude=float(lat),
                            longitude=float(lon),
                        )
                        total_new += 1
                        logger.info(
                            "geofences.evaluator.vehicle_exited",
                            vehicle_id=vehicle_id,
                            geofence_id=prev_id,
                            geofence_name=geo.name,
                        )

                        if geo.alert_on_exit:
                            await _create_alert_if_new(
                                alert_repo,
                                alert_type="geofence_exit",
                                vehicle_id=vehicle_id,
                                geofence=geo,
                                title=f"Vehicle {vehicle_id} exited zone {geo.name}",
                            )

                # Check dwell time for vehicles still inside
                for geofence in containing:
                    if geofence.id in previous_ids and geofence.alert_on_dwell:
                        if geofence.dwell_threshold_minutes is None:
                            continue
                        open_entry = await event_repo.get_open_entry(geofence.id, vehicle_id)
                        if not open_entry:
                            continue
                        dwell = (now - open_entry.entered_at).total_seconds()
                        threshold = geofence.dwell_threshold_minutes * 60
                        if dwell >= threshold:
                            await _create_alert_if_new(
                                alert_repo,
                                alert_type="geofence_dwell",
                                vehicle_id=vehicle_id,
                                geofence=geofence,
                                title=(
                                    f"Vehicle {vehicle_id} dwelling in zone"
                                    f" {geofence.name} for {int(dwell / 60)}min"
                                ),
                            )
                            # Create dwell_exceeded event
                            await event_repo.create(
                                geofence_id=geofence.id,
                                vehicle_id=vehicle_id,
                                event_type="dwell_exceeded",
                                entered_at=open_entry.entered_at,
                                latitude=float(lat),
                                longitude=float(lon),
                            )
                            total_new += 1
                            logger.info(
                                "geofences.evaluator.dwell_exceeded",
                                vehicle_id=vehicle_id,
                                geofence_id=geofence.id,
                                dwell_seconds=int(dwell),
                            )

                # Update Redis state
                await redis.set(
                    state_key,
                    json.dumps(list(current_ids)),
                    ex=300,  # 5 min TTL
                )

    except Exception:
        logger.error(
            "geofences.evaluator.cycle_failed",
            error_type="EvaluationError",
            exc_info=True,
        )
    return total_new


async def _create_alert_if_new(
    alert_repo: AlertInstanceRepository,
    *,
    alert_type: str,
    vehicle_id: str,
    geofence: Geofence,
    title: str,
) -> None:
    """Create an alert instance if no active duplicate exists.

    Args:
        alert_repo: Alert instance repository.
        alert_type: Type of geofence alert.
        vehicle_id: Vehicle identifier.
        geofence: Geofence model instance.
        title: Alert title text.
    """
    # Check for existing active alert to avoid duplicates
    # Use geofence_id as a pseudo rule_id for dedup (no actual rule_id for geofence alerts)
    existing = await alert_repo.find_active_duplicate(
        geofence.id,
        "vehicle",
        vehicle_id,
    )
    if existing:
        return

    data = AlertInstanceCreate(
        title=title,
        severity=geofence.alert_severity,
        alert_type=alert_type,
        source_entity_type="vehicle",
        source_entity_id=vehicle_id,
        rule_id=None,
        details={
            "geofence_id": geofence.id,
            "geofence_name": geofence.name,
            "zone_type": geofence.zone_type,
        },
    )
    await alert_repo.create(data)


async def _evaluator_loop(interval: int) -> None:
    """Main evaluator loop - runs until cancelled."""
    while True:
        await asyncio.sleep(interval)
        try:
            count = await evaluate_geofences_once()
            logger.info(
                "geofences.evaluator.cycle_completed",
                new_events=count,
                interval=interval,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.error(
                "geofences.evaluator.cycle_failed",
                exc_info=True,
            )


async def start_geofence_evaluator(settings: Settings) -> None:
    """Start the background geofence evaluator task."""
    global _evaluator_task
    if not settings.geofence_evaluator_enabled:
        logger.info("geofences.evaluator.lifecycle_skipped", reason="disabled")
        return
    _evaluator_task = asyncio.create_task(_evaluator_loop(settings.geofence_check_interval_seconds))
    logger.info(
        "geofences.evaluator.lifecycle_started",
        interval=settings.geofence_check_interval_seconds,
    )


async def stop_geofence_evaluator() -> None:
    """Stop the background geofence evaluator task."""
    global _evaluator_task
    if _evaluator_task is None:
        return
    _evaluator_task.cancel()
    try:
        await _evaluator_task
    except asyncio.CancelledError:
        pass
    except Exception:
        logger.error("geofences.evaluator.shutdown_error", exc_info=True)
    _evaluator_task = None
    logger.info("geofences.evaluator.lifecycle_stopped")
