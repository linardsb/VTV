# pyright: reportUnknownMemberType=false, reportMissingTypeStubs=false
"""Central anomaly alert router with Redis cooldowns (ML-4.3).

Routes anomaly events from detectors to the alert system. Owns all
cooldown and deduplication policy so detectors remain pure detection
functions.
"""

from __future__ import annotations

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.alerts.repository import AlertInstanceRepository
from app.alerts.schemas import AlertInstanceCreate
from app.core.config import Settings
from app.core.logging import get_logger
from app.ml.anomaly.schemas import CHANNEL_MATRIX, AnomalyEvent

logger = get_logger(__name__)


class AnomalyAlertRouter:
    """Routes anomaly events to alerts with Redis cooldowns (ML-4.3).

    Centralizes cooldown/dedup policy that was previously inline in each
    detector. Detectors return raw AnomalyEvent lists; the router decides
    whether to persist them as alerts.
    """

    def __init__(self, redis: Redis, settings: Settings) -> None:
        self._redis = redis
        self._settings = settings

    async def route(self, event: AnomalyEvent, db: AsyncSession) -> bool:
        """Route an anomaly event. Returns True if alert was created, False if suppressed.

        Args:
            event: Immutable anomaly event from a detector.
            db: Async database session for alert persistence.

        Returns:
            True if a new alert was created, False if suppressed by cooldown.
        """
        cooldown_key = f"anomaly:cooldown:{event.anomaly_type}:{event.source_entity_id}"
        if await self._redis.get(cooldown_key) is not None:
            logger.info(
                "anomaly.router.cooldown_suppressed",
                anomaly_type=event.anomaly_type,
                entity_id=event.source_entity_id,
            )
            return False

        alert_data = AlertInstanceCreate(
            title=event.title,
            severity=event.severity,
            alert_type=event.anomaly_type,
            source_entity_type=event.source_entity_type,
            source_entity_id=event.source_entity_id,
            details=event.details,
            rule_id=None,
        )
        repo = AlertInstanceRepository(db)
        await repo.create(alert_data)

        ttl = (
            self._settings.anomaly_cooldown_critical_seconds
            if event.severity == "critical"
            else self._settings.anomaly_cooldown_warning_seconds
        )
        await self._redis.set(cooldown_key, "1", ex=ttl)

        channels = CHANNEL_MATRIX.get(event.anomaly_type, ["dashboard"])
        logger.info(
            "anomaly.router.alert_created",
            anomaly_type=event.anomaly_type,
            severity=event.severity,
            entity_id=event.source_entity_id,
            channels=channels,
        )
        return True
