# pyright: reportUnknownMemberType=false, reportMissingTypeStubs=false, reportArgumentType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Background off-route evaluator - detects vehicles outside their GTFS route corridors (ML-4.1).

Scans Redis vehicle positions, builds PostGIS corridor geometry from GTFS shapes,
and fires alerts when a vehicle drifts outside the corridor for N consecutive checks.
Follows the geofence evaluator pattern (app/geofences/evaluator.py).
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.alerts.models import AlertInstance
from app.alerts.repository import AlertInstanceRepository
from app.alerts.schemas import AlertInstanceCreate
from app.core.config import Settings, get_settings
from app.core.database import get_db_context
from app.core.logging import get_logger
from app.core.metrics import record_poller_tick
from app.core.redis import get_redis

_evaluator_task: asyncio.Task[None] | None = None
logger = get_logger(__name__)

REDIS_VEHICLE_PREFIX = "vehicle:"
REDIS_OFF_ROUTE_PREFIX = "off_route_state:"

# Module-level corridor cache: keyed by "feed_id:gtfs_route_id"
_corridor_cache: dict[str, Any] = {}


async def get_corridor_for_route(
    db: AsyncSession,
    gtfs_route_id: str,
    feed_id: str,
    buffer_m: int,
) -> Any | None:  # noqa: ANN401
    """Build a PostGIS corridor geometry for a GTFS route's shapes.

    Queries all shape variants (outbound + inbound) for the route, buffers each
    by ``buffer_m`` meters, then unions them into a single geometry.

    Args:
        db: Async database session.
        gtfs_route_id: GTFS route ID string (e.g. "22").
        feed_id: Transit feed identifier.
        buffer_m: Buffer distance in meters around the route shape.

    Returns:
        WKB corridor geometry, or None if no shapes exist for this route.
    """
    cache_key = f"{feed_id}:{gtfs_route_id}"
    if cache_key in _corridor_cache:
        return _corridor_cache[cache_key]

    result = await db.execute(
        text("""
            SELECT ST_Union(corridor) AS corridor FROM (
                SELECT ST_Buffer(
                    ST_MakeLine(
                        ST_SetSRID(ST_MakePoint(s.shape_pt_lon, s.shape_pt_lat), 4326)
                        ORDER BY s.shape_pt_sequence
                    )::geography,
                    :buffer_m
                )::geometry AS corridor
                FROM shapes s
                INNER JOIN (
                    SELECT DISTINCT t.shape_id
                    FROM trips t
                    INNER JOIN routes r ON t.route_id = r.id
                    WHERE r.gtfs_route_id = :gtfs_route_id
                      AND r.feed_id = :feed_id
                      AND t.shape_id IS NOT NULL
                ) shapes_for_route ON s.gtfs_shape_id = shapes_for_route.shape_id
                GROUP BY s.gtfs_shape_id
            ) sub
        """),
        {"gtfs_route_id": gtfs_route_id, "feed_id": feed_id, "buffer_m": buffer_m},
    )
    row = result.first()
    corridor = row[0] if row else None

    if corridor is not None:
        _corridor_cache[cache_key] = corridor

    return corridor


async def check_vehicle_in_corridor(
    db: AsyncSession,
    lat: float,
    lon: float,
    corridor: Any,  # noqa: ANN401
) -> bool:
    """Check whether a vehicle position falls within a route corridor.

    Args:
        db: Async database session.
        lat: Vehicle latitude.
        lon: Vehicle longitude.
        corridor: WKB corridor geometry from get_corridor_for_route().

    Returns:
        True if the vehicle is inside the corridor.
    """
    result = await db.execute(
        text("SELECT ST_Contains(:corridor::geometry, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326))"),
        {"corridor": corridor, "lon": lon, "lat": lat},
    )
    return bool(result.scalar())


async def _find_active_off_route_alert(db: AsyncSession, vehicle_id: str) -> AlertInstance | None:
    """Find an existing active off-route alert for a vehicle.

    Args:
        db: Async database session.
        vehicle_id: Vehicle identifier.

    Returns:
        Active AlertInstance or None.
    """
    result = await db.execute(
        select(AlertInstance).where(
            AlertInstance.alert_type == "off_route",
            AlertInstance.source_entity_id == vehicle_id,
            AlertInstance.status == "active",
        )
    )
    return result.scalar_one_or_none()


async def _create_off_route_alert(
    db: AsyncSession,
    alert_repo: AlertInstanceRepository,
    vehicle_id: str,
    route_id: str,
    consecutive_count: int,
) -> None:
    """Create an off-route alert if no active duplicate exists.

    Args:
        db: Async database session.
        alert_repo: Alert instance repository.
        vehicle_id: Vehicle identifier.
        route_id: GTFS route ID string.
        consecutive_count: Number of consecutive out-of-corridor checks.
    """
    existing = await _find_active_off_route_alert(db, vehicle_id)
    if existing:
        return

    data = AlertInstanceCreate(
        title=f"Vehicle {vehicle_id} off route {route_id}",
        severity="high",
        alert_type="off_route",
        source_entity_type="vehicle",
        source_entity_id=vehicle_id,
        rule_id=None,
        details={
            "route_id": route_id,
            "consecutive_hits": consecutive_count,
        },
    )
    await alert_repo.create(data)
    logger.info(
        "transit.anomaly.off_route.fired",
        vehicle_id=vehicle_id,
        route_id=route_id,
        consecutive_hits=consecutive_count,
    )


async def evaluate_off_route_once() -> int:
    """Run one off-route evaluation cycle for all tracked vehicles.

    Scans Redis vehicle keys, checks each against its route corridor,
    tracks consecutive out-of-corridor hits, and fires alerts at the threshold.

    Returns:
        Number of new alerts fired.
    """
    settings = get_settings()
    threshold = settings.anomaly_offroute_consecutive_hits
    buffer_m = settings.anomaly_offroute_buffer_meters
    alerts_fired = 0
    total_vehicles = 0

    try:
        redis = await get_redis()

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
            route_id = data.get("route_id")

            if not isinstance(lat, int | float) or not isinstance(lon, int | float):
                continue
            if not route_id:
                continue

            route_id = str(route_id)
            vehicle_id = str(data.get("vehicle_id", vkey.removeprefix(REDIS_VEHICLE_PREFIX)))
            feed_id = str(data.get("feed_id", "riga"))
            total_vehicles += 1

            async with get_db_context() as db:
                corridor = await get_corridor_for_route(db, route_id, feed_id, buffer_m)

                if corridor is None:
                    logger.debug(
                        "transit.anomaly.off_route.no_corridor",
                        route_id=route_id,
                        feed_id=feed_id,
                    )
                    continue

                inside = await check_vehicle_in_corridor(db, float(lat), float(lon), corridor)

                # Read consecutive count from Redis
                state_key = f"{REDIS_OFF_ROUTE_PREFIX}{vehicle_id}"
                count_raw = await redis.get(state_key)
                current_count = int(str(count_raw)) if count_raw else 0

                if not inside:
                    current_count += 1
                    await redis.set(state_key, str(current_count), ex=300)

                    logger.debug(
                        "transit.anomaly.off_route.candidate",
                        vehicle_id=vehicle_id,
                        route_id=route_id,
                        consecutive_count=current_count,
                    )

                    if current_count >= threshold:
                        alert_repo = AlertInstanceRepository(db)
                        await _create_off_route_alert(
                            db, alert_repo, vehicle_id, route_id, current_count
                        )
                        alerts_fired += 1
                else:
                    if current_count > 0:
                        await redis.delete(state_key)
                        logger.debug(
                            "transit.anomaly.off_route.reset",
                            vehicle_id=vehicle_id,
                        )

    except Exception:
        logger.error(
            "transit.anomaly.off_route.cycle_failed",
            error_type="EvaluationError",
            exc_info=True,
        )
        return alerts_fired

    record_poller_tick("off_route_evaluator")
    logger.info(
        "transit.anomaly.off_route.cycle_completed",
        total_vehicles=total_vehicles,
        alerts_fired=alerts_fired,
    )
    return alerts_fired


async def _evaluator_loop(interval: int) -> None:
    """Main evaluator loop - runs until cancelled.

    Args:
        interval: Seconds between evaluation cycles.
    """
    while True:
        await asyncio.sleep(interval)
        try:
            await evaluate_off_route_once()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.error("transit.anomaly.off_route.cycle_failed", exc_info=True)


async def start_off_route_evaluator(settings: Settings) -> None:
    """Start the background off-route evaluator task.

    Args:
        settings: Application settings (checks enabled flag and interval).
    """
    global _evaluator_task
    if not settings.anomaly_offroute_enabled:
        logger.info("transit.anomaly.off_route.lifecycle_skipped", reason="disabled")
        return
    _evaluator_task = asyncio.create_task(
        _evaluator_loop(settings.anomaly_offroute_check_interval_seconds),
    )
    logger.info(
        "transit.anomaly.off_route.lifecycle_started",
        interval=settings.anomaly_offroute_check_interval_seconds,
    )


async def stop_off_route_evaluator() -> None:
    """Stop the background off-route evaluator task and clear corridor cache."""
    global _evaluator_task
    if _evaluator_task is None:
        return
    _evaluator_task.cancel()
    try:
        await _evaluator_task
    except asyncio.CancelledError:
        pass
    except Exception:
        logger.error("transit.anomaly.off_route.shutdown_error", exc_info=True)
    _evaluator_task = None
    _corridor_cache.clear()
    logger.info("transit.anomaly.off_route.lifecycle_stopped")
