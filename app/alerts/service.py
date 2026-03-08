"""Business logic for notification/alerts."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.alerts.exceptions import AlertNotFoundError, AlertRuleNotFoundError
from app.alerts.repository import AlertInstanceRepository, AlertRuleRepository
from app.alerts.schemas import (
    AlertInstanceCreate,
    AlertInstanceResponse,
    AlertRuleCreate,
    AlertRuleResponse,
    AlertRuleUpdate,
    AlertSummaryResponse,
)
from app.core.logging import get_logger
from app.shared.schemas import PaginatedResponse, PaginationParams

logger = get_logger(__name__)


class AlertService:
    """Business logic for alert rules and instances."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.rule_repository = AlertRuleRepository(db)
        self.instance_repository = AlertInstanceRepository(db)

    # --- Rule CRUD ---

    async def get_rule(self, rule_id: int) -> AlertRuleResponse:
        logger.info("alerts.rule.fetch_started", rule_id=rule_id)
        rule = await self.rule_repository.get(rule_id)
        if not rule:
            logger.warning("alerts.rule.fetch_failed", rule_id=rule_id, reason="not_found")
            raise AlertRuleNotFoundError(f"Alert rule {rule_id} not found")
        return AlertRuleResponse.model_validate(rule)

    async def list_rules(
        self,
        pagination: PaginationParams,
        *,
        enabled_only: bool = False,
    ) -> PaginatedResponse[AlertRuleResponse]:
        logger.info("alerts.rule.list_started", page=pagination.page)
        rules = await self.rule_repository.list(
            offset=pagination.offset,
            limit=pagination.page_size,
            enabled_only=enabled_only,
        )
        total = await self.rule_repository.count(enabled_only=enabled_only)
        items = [AlertRuleResponse.model_validate(r) for r in rules]
        logger.info("alerts.rule.list_completed", result_count=len(items), total=total)
        return PaginatedResponse[AlertRuleResponse](
            items=items,
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
        )

    async def create_rule(self, data: AlertRuleCreate) -> AlertRuleResponse:
        logger.info("alerts.rule.create_started", name=data.name)
        rule = await self.rule_repository.create(data)
        logger.info("alerts.rule.create_completed", rule_id=rule.id)
        return AlertRuleResponse.model_validate(rule)

    async def update_rule(self, rule_id: int, data: AlertRuleUpdate) -> AlertRuleResponse:
        logger.info("alerts.rule.update_started", rule_id=rule_id)
        rule = await self.rule_repository.get(rule_id)
        if not rule:
            logger.warning("alerts.rule.update_failed", rule_id=rule_id, reason="not_found")
            raise AlertRuleNotFoundError(f"Alert rule {rule_id} not found")
        rule = await self.rule_repository.update(rule, data)
        logger.info("alerts.rule.update_completed", rule_id=rule.id)
        return AlertRuleResponse.model_validate(rule)

    async def delete_rule(self, rule_id: int) -> None:
        logger.info("alerts.rule.delete_started", rule_id=rule_id)
        rule = await self.rule_repository.get(rule_id)
        if not rule:
            logger.warning("alerts.rule.delete_failed", rule_id=rule_id, reason="not_found")
            raise AlertRuleNotFoundError(f"Alert rule {rule_id} not found")
        await self.rule_repository.delete(rule)
        logger.info("alerts.rule.delete_completed", rule_id=rule_id)

    # --- Instance methods ---

    async def get_alert(self, alert_id: int) -> AlertInstanceResponse:
        logger.info("alerts.instance.fetch_started", alert_id=alert_id)
        alert = await self.instance_repository.get(alert_id)
        if not alert:
            logger.warning("alerts.instance.fetch_failed", alert_id=alert_id, reason="not_found")
            raise AlertNotFoundError(f"Alert {alert_id} not found")
        return AlertInstanceResponse.model_validate(alert)

    async def list_alerts(
        self,
        pagination: PaginationParams,
        *,
        status: str | None = None,
        severity: str | None = None,
        alert_type: str | None = None,
        source_entity_type: str | None = None,
        source_entity_id: str | None = None,
    ) -> PaginatedResponse[AlertInstanceResponse]:
        logger.info("alerts.instance.list_started", page=pagination.page)
        alerts = await self.instance_repository.list(
            offset=pagination.offset,
            limit=pagination.page_size,
            status=status,
            severity=severity,
            alert_type=alert_type,
            source_entity_type=source_entity_type,
            source_entity_id=source_entity_id,
        )
        total = await self.instance_repository.count(
            status=status,
            severity=severity,
            alert_type=alert_type,
            source_entity_type=source_entity_type,
            source_entity_id=source_entity_id,
        )
        items = [AlertInstanceResponse.model_validate(a) for a in alerts]
        logger.info("alerts.instance.list_completed", result_count=len(items), total=total)
        return PaginatedResponse[AlertInstanceResponse](
            items=items,
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
        )

    async def create_alert(self, data: AlertInstanceCreate) -> AlertInstanceResponse:
        logger.info("alerts.instance.create_started", title=data.title)
        alert = await self.instance_repository.create(data)
        logger.info(
            "alerts.instance.create_completed",
            alert_id=alert.id,
            severity=alert.severity,
            alert_type=alert.alert_type,
        )
        return AlertInstanceResponse.model_validate(alert)

    async def acknowledge_alert(self, alert_id: int, user_id: int) -> AlertInstanceResponse:
        logger.info("alerts.instance.acknowledge_started", alert_id=alert_id)
        alert = await self.instance_repository.get(alert_id)
        if not alert:
            logger.warning(
                "alerts.instance.acknowledge_failed", alert_id=alert_id, reason="not_found"
            )
            raise AlertNotFoundError(f"Alert {alert_id} not found")
        alert = await self.instance_repository.acknowledge(alert, user_id)
        logger.info("alerts.instance.acknowledge_completed", alert_id=alert_id, user_id=user_id)
        return AlertInstanceResponse.model_validate(alert)

    async def resolve_alert(self, alert_id: int) -> AlertInstanceResponse:
        logger.info("alerts.instance.resolve_started", alert_id=alert_id)
        alert = await self.instance_repository.get(alert_id)
        if not alert:
            logger.warning("alerts.instance.resolve_failed", alert_id=alert_id, reason="not_found")
            raise AlertNotFoundError(f"Alert {alert_id} not found")
        alert = await self.instance_repository.resolve(alert)
        logger.info("alerts.instance.resolve_completed", alert_id=alert_id)
        return AlertInstanceResponse.model_validate(alert)

    async def get_summary(self) -> AlertSummaryResponse:
        logger.info("alerts.summary.fetch_started")
        summary = await self.instance_repository.get_summary()
        logger.info("alerts.summary.fetch_completed", total_active=summary["total_active"])
        return AlertSummaryResponse(**summary)
