# pyright: reportUnknownMemberType=false, reportMissingTypeStubs=false
"""Stuck vehicle anomaly detector (ML-4.2).

Detects vehicles that have moved less than a configurable distance threshold
over a time window while on an active trip. Catches breakdowns, accidents,
and traffic pileups.
"""

from __future__ import annotations

import datetime
from collections import defaultdict

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.alerts.schemas import AlertInstanceCreate
from app.core.config import Settings
from app.core.logging import get_logger
from app.shared.geo import haversine_distance

logger = get_logger(__name__)


class StuckVehicleEvaluator:
    """Detects vehicles stuck in place during active trips.

    Queries recent positions from TimescaleDB, computes total movement
    via haversine distance, and flags vehicles under the threshold.
    Layover/terminal stops are excluded via GTFS stop_times cross-reference.
    """

    async def check(
        self,
        db: AsyncSession,
        redis: Redis,
        settings: Settings,
    ) -> list[AlertInstanceCreate]:
        """Run stuck vehicle detection for all active vehicles.

        Args:
            db: Async database session.
            redis: Redis client for cooldown checks.
            settings: Application settings with thresholds.

        Returns:
            List of alert instances to create.
        """
        now = datetime.datetime.now(tz=datetime.UTC)
        window_start = now - datetime.timedelta(minutes=settings.ml_stuck_time_window_minutes)

        # Fetch recent positions for vehicles with active trips
        result = await db.execute(
            text("""
                SELECT vehicle_id, latitude, longitude, recorded_at, trip_id, feed_id
                FROM vehicle_positions
                WHERE recorded_at >= :window_start
                  AND trip_id IS NOT NULL
                ORDER BY vehicle_id, recorded_at
            """).bindparams(window_start=window_start),
        )
        rows = result.fetchall()

        if not rows:
            return []

        # Group positions by vehicle
        vehicle_positions: dict[str, list[tuple[float, float, str, str]]] = defaultdict(list)
        for row in rows:
            vid = str(row[0])
            lat = float(row[1])
            lon = float(row[2])
            trip_id = str(row[4])
            feed_id = str(row[5])
            vehicle_positions[vid].append((lat, lon, trip_id, feed_id))

        # Fetch vehicles at terminal/layover stops (exclude from stuck detection)
        excluded_vehicles = await self._get_layover_vehicles(db, now)

        alerts: list[AlertInstanceCreate] = []

        for vehicle_id, positions in vehicle_positions.items():
            if vehicle_id in excluded_vehicles:
                continue

            # Compute total distance from consecutive positions
            total_distance = 0.0
            for i in range(1, len(positions)):
                total_distance += haversine_distance(
                    positions[i - 1][0],
                    positions[i - 1][1],
                    positions[i][0],
                    positions[i][1],
                )

            if total_distance >= settings.ml_stuck_distance_threshold_m:
                continue

            # Check cooldown
            cooldown_key = f"ml:stuck:{vehicle_id}"
            existing = await redis.get(cooldown_key)
            if existing is not None:
                continue

            # Set cooldown
            await redis.set(cooldown_key, "1", ex=settings.ml_anomaly_cooldown_seconds)

            last_pos = positions[-1]
            alerts.append(
                AlertInstanceCreate(
                    title=f"Vehicle {vehicle_id} stuck ({total_distance:.0f}m in {settings.ml_stuck_time_window_minutes}min)",
                    severity="high",
                    alert_type="stuck_vehicle",
                    source_entity_type="vehicle",
                    source_entity_id=vehicle_id,
                    rule_id=None,
                    details={
                        "feed_id": last_pos[3],
                        "trip_id": last_pos[2],
                        "distance_m": round(total_distance, 1),
                        "window_minutes": settings.ml_stuck_time_window_minutes,
                    },
                ),
            )

            logger.info(
                "ml.stuck_evaluator.vehicle_detected",
                vehicle_id=vehicle_id,
                distance_m=round(total_distance, 1),
                window_minutes=settings.ml_stuck_time_window_minutes,
            )

        return alerts

    async def _get_layover_vehicles(
        self,
        db: AsyncSession,
        now: datetime.datetime,
    ) -> set[str]:
        """Find vehicles currently at a scheduled layover or terminal stop.

        Cross-references active trip's stop_times to identify vehicles at
        stops where the current time falls within arrival/departure window.

        Args:
            db: Async database session.
            now: Current timestamp.

        Returns:
            Set of vehicle IDs to exclude from stuck detection.
        """
        current_time = now.strftime("%H:%M:%S")

        result = await db.execute(
            text("""
                SELECT DISTINCT vp.vehicle_id
                FROM vehicle_positions vp
                JOIN trips t ON t.gtfs_trip_id = vp.trip_id
                JOIN stop_times st ON st.trip_id = t.id
                WHERE vp.trip_id IS NOT NULL
                  AND vp.recorded_at = (
                      SELECT MAX(vp2.recorded_at)
                      FROM vehicle_positions vp2
                      WHERE vp2.vehicle_id = vp.vehicle_id
                  )
                  AND st.stop_sequence = (
                      SELECT MAX(st2.stop_sequence)
                      FROM stop_times st2
                      WHERE st2.trip_id = t.id
                  )
                  AND st.arrival_time <= :current_time
                  AND (st.departure_time >= :current_time OR st.departure_time IS NULL)
            """).bindparams(current_time=current_time),
        )
        return {str(row[0]) for row in result.fetchall()}
