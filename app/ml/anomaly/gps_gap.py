# pyright: reportUnknownMemberType=false, reportMissingTypeStubs=false
"""GPS gap anomaly detector (ML-4.2).

Detects vehicles with no position updates for a configurable threshold
while on active trips. Catches hardware failures, driver offline, and
feed outages. Includes feed-wide gap suppression to avoid per-vehicle spam
when an entire feed goes down.
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

logger = get_logger(__name__)


class GPSGapEvaluator:
    """Detects GPS gaps and feed-wide outages.

    Queries the most recent position per vehicle, flags those exceeding
    the gap threshold. If a majority of a feed's vehicles gap simultaneously,
    fires a single feed_outage alert instead of per-vehicle alerts.
    """

    async def check(
        self,
        db: AsyncSession,
        redis: Redis,
        settings: Settings,
    ) -> list[AlertInstanceCreate]:
        """Run GPS gap detection for all active vehicles.

        Args:
            db: Async database session.
            redis: Redis client for cooldown checks.
            settings: Application settings with thresholds.

        Returns:
            List of alert instances to create.
        """
        now = datetime.datetime.now(tz=datetime.UTC)
        gap_threshold = datetime.timedelta(minutes=settings.ml_gps_gap_threshold_minutes)

        # Get latest position per vehicle (only vehicles with active trips)
        result = await db.execute(
            text("""
                SELECT vehicle_id, feed_id, MAX(recorded_at) AS last_seen
                FROM vehicle_positions
                WHERE trip_id IS NOT NULL
                GROUP BY vehicle_id, feed_id
            """),
        )
        rows = result.fetchall()

        if not rows:
            return []

        # Classify vehicles by feed: gap vs. active
        feed_gap_vehicles: dict[str, list[str]] = defaultdict(list)
        feed_total_vehicles: dict[str, int] = defaultdict(int)
        gap_vehicles: dict[str, tuple[str, datetime.datetime]] = {}

        for row in rows:
            vehicle_id = str(row[0])
            feed_id = str(row[1])
            last_seen = row[2]
            if not isinstance(last_seen, datetime.datetime):
                continue

            feed_total_vehicles[feed_id] += 1
            age = now - last_seen

            if age > gap_threshold:
                feed_gap_vehicles[feed_id].append(vehicle_id)
                gap_vehicles[vehicle_id] = (feed_id, last_seen)

        alerts: list[AlertInstanceCreate] = []

        # Check for feed-wide outages
        suppressed_feeds: set[str] = set()
        for feed_id, gap_list in feed_gap_vehicles.items():
            total = feed_total_vehicles[feed_id]
            if total == 0:
                continue
            pct = (len(gap_list) * 100) // total
            if pct >= settings.ml_gps_gap_feed_outage_pct:
                # Feed-wide outage — emit one alert instead of per-vehicle
                cooldown_key = f"ml:feed_outage:{feed_id}"
                existing = await redis.get(cooldown_key)
                if existing is None:
                    await redis.set(cooldown_key, "1", ex=settings.ml_anomaly_cooldown_seconds)
                    alerts.append(
                        AlertInstanceCreate(
                            title=f"Feed outage: {feed_id} ({len(gap_list)}/{total} vehicles offline)",
                            severity="critical",
                            alert_type="feed_outage",
                            source_entity_type=None,
                            source_entity_id=None,
                            rule_id=None,
                            details={
                                "feed_id": feed_id,
                                "gap_count": len(gap_list),
                                "total_count": total,
                                "gap_pct": pct,
                            },
                        ),
                    )
                    logger.info(
                        "ml.gps_gap_evaluator.feed_outage_detected",
                        feed_id=feed_id,
                        gap_count=len(gap_list),
                        total_count=total,
                    )
                suppressed_feeds.add(feed_id)

        # Per-vehicle gap alerts (skip vehicles in suppressed feeds)
        for vehicle_id, (feed_id, last_seen) in gap_vehicles.items():
            if feed_id in suppressed_feeds:
                continue

            cooldown_key = f"ml:gps_gap:{vehicle_id}"
            existing = await redis.get(cooldown_key)
            if existing is not None:
                continue

            await redis.set(cooldown_key, "1", ex=settings.ml_anomaly_cooldown_seconds)
            gap_minutes = int((now - last_seen).total_seconds() / 60)
            alerts.append(
                AlertInstanceCreate(
                    title=f"GPS gap: vehicle {vehicle_id} offline for {gap_minutes}min",
                    severity="high",
                    alert_type="gps_gap",
                    source_entity_type="vehicle",
                    source_entity_id=vehicle_id,
                    rule_id=None,
                    details={
                        "feed_id": feed_id,
                        "last_seen": last_seen.isoformat(),
                        "gap_minutes": gap_minutes,
                    },
                ),
            )
            logger.info(
                "ml.gps_gap_evaluator.gap_detected",
                vehicle_id=vehicle_id,
                feed_id=feed_id,
                gap_minutes=gap_minutes,
            )

        return alerts
