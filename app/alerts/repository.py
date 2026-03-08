"""Data access layer for notification/alerts."""

from __future__ import annotations

import builtins

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.alerts.models import AlertInstance, AlertRule
from app.alerts.schemas import AlertInstanceCreate, AlertRuleCreate, AlertRuleUpdate
from app.shared.models import utcnow


class AlertRuleRepository:
    """Database operations for alert rules."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get(self, rule_id: int) -> AlertRule | None:
        result = await self.db.execute(select(AlertRule).where(AlertRule.id == rule_id))
        return result.scalar_one_or_none()

    async def list(
        self,
        *,
        offset: int = 0,
        limit: int = 100,
        enabled_only: bool = False,
    ) -> list[AlertRule]:
        query = select(AlertRule)
        if enabled_only:
            query = query.where(AlertRule.enabled.is_(True))
        query = query.order_by(AlertRule.id).offset(offset).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def count(self, *, enabled_only: bool = False) -> int:
        query = select(func.count()).select_from(AlertRule)
        if enabled_only:
            query = query.where(AlertRule.enabled.is_(True))
        result = await self.db.execute(query)
        return result.scalar_one()

    async def create(self, data: AlertRuleCreate) -> AlertRule:
        rule = AlertRule(**data.model_dump())
        self.db.add(rule)
        await self.db.commit()
        await self.db.refresh(rule)
        return rule

    async def update(self, rule: AlertRule, data: AlertRuleUpdate) -> AlertRule:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(rule, field, value)
        await self.db.commit()
        await self.db.refresh(rule)
        return rule

    async def delete(self, rule: AlertRule) -> None:
        await self.db.delete(rule)
        await self.db.commit()

    async def get_enabled_rules(self) -> builtins.list[AlertRule]:
        return await self.list(enabled_only=True, limit=1000)


class AlertInstanceRepository:
    """Database operations for alert instances."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get(self, alert_id: int) -> AlertInstance | None:
        result = await self.db.execute(select(AlertInstance).where(AlertInstance.id == alert_id))
        return result.scalar_one_or_none()

    async def list(
        self,
        *,
        offset: int = 0,
        limit: int = 100,
        status: str | None = None,
        severity: str | None = None,
        alert_type: str | None = None,
        source_entity_type: str | None = None,
        source_entity_id: str | None = None,
    ) -> list[AlertInstance]:
        query = select(AlertInstance)
        if status is not None:
            query = query.where(AlertInstance.status == status)
        if severity is not None:
            query = query.where(AlertInstance.severity == severity)
        if alert_type is not None:
            query = query.where(AlertInstance.alert_type == alert_type)
        if source_entity_type is not None:
            query = query.where(AlertInstance.source_entity_type == source_entity_type)
        if source_entity_id is not None:
            query = query.where(AlertInstance.source_entity_id == source_entity_id)
        query = (
            query.order_by(
                case(
                    (AlertInstance.severity == "critical", 1),
                    (AlertInstance.severity == "high", 2),
                    (AlertInstance.severity == "medium", 3),
                    (AlertInstance.severity == "low", 4),
                    (AlertInstance.severity == "info", 5),
                    else_=6,
                ),
                AlertInstance.created_at.desc(),
            )
            .offset(offset)
            .limit(limit)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def count(
        self,
        *,
        status: str | None = None,
        severity: str | None = None,
        alert_type: str | None = None,
        source_entity_type: str | None = None,
        source_entity_id: str | None = None,
    ) -> int:
        query = select(func.count()).select_from(AlertInstance)
        if status is not None:
            query = query.where(AlertInstance.status == status)
        if severity is not None:
            query = query.where(AlertInstance.severity == severity)
        if alert_type is not None:
            query = query.where(AlertInstance.alert_type == alert_type)
        if source_entity_type is not None:
            query = query.where(AlertInstance.source_entity_type == source_entity_type)
        if source_entity_id is not None:
            query = query.where(AlertInstance.source_entity_id == source_entity_id)
        result = await self.db.execute(query)
        return result.scalar_one()

    async def create(self, data: AlertInstanceCreate) -> AlertInstance:
        alert = AlertInstance(**data.model_dump(), status="active")
        self.db.add(alert)
        await self.db.commit()
        await self.db.refresh(alert)
        return alert

    async def acknowledge(self, alert: AlertInstance, user_id: int) -> AlertInstance:
        alert.status = "acknowledged"
        alert.acknowledged_at = utcnow()
        alert.acknowledged_by_id = user_id
        await self.db.commit()
        await self.db.refresh(alert)
        return alert

    async def resolve(self, alert: AlertInstance) -> AlertInstance:
        alert.status = "resolved"
        alert.resolved_at = utcnow()
        await self.db.commit()
        await self.db.refresh(alert)
        return alert

    async def find_active_duplicate(
        self,
        rule_id: int,
        source_entity_type: str,
        source_entity_id: str,
    ) -> AlertInstance | None:
        result = await self.db.execute(
            select(AlertInstance).where(
                AlertInstance.rule_id == rule_id,
                AlertInstance.source_entity_type == source_entity_type,
                AlertInstance.source_entity_id == source_entity_id,
                AlertInstance.status == "active",
            )
        )
        return result.scalar_one_or_none()

    async def get_summary(self) -> dict[str, int]:
        """Count active alerts grouped by severity."""
        result = await self.db.execute(
            select(AlertInstance.severity, func.count())
            .where(AlertInstance.status == "active")
            .group_by(AlertInstance.severity)
        )
        counts = {row[0]: row[1] for row in result.all()}
        total = sum(counts.values())
        return {
            "total_active": total,
            "critical": counts.get("critical", 0),
            "high": counts.get("high", 0),
            "medium": counts.get("medium", 0),
            "low": counts.get("low", 0),
            "info": counts.get("info", 0),
        }
