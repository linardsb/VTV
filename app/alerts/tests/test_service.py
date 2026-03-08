# pyright: reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportCallIssue=false
"""Unit tests for AlertService."""

from unittest.mock import AsyncMock

import pytest

from app.alerts.exceptions import AlertNotFoundError, AlertRuleNotFoundError
from app.alerts.schemas import (
    AlertInstanceCreate,
    AlertRuleCreate,
    AlertRuleUpdate,
    AlertSummaryResponse,
)
from app.alerts.service import AlertService
from app.alerts.tests.conftest import make_alert_instance, make_alert_rule
from app.shared.schemas import PaginationParams


@pytest.fixture
def service() -> AlertService:
    mock_db = AsyncMock()
    svc = AlertService(mock_db)
    svc.rule_repository = AsyncMock()
    svc.instance_repository = AsyncMock()
    return svc


# --- Rule CRUD ---


async def test_get_rule_success(service):
    rule = make_alert_rule(id=1)
    service.rule_repository.get = AsyncMock(return_value=rule)

    result = await service.get_rule(1)
    assert result.id == 1
    assert result.name == "High Delay Alert"


async def test_get_rule_not_found(service):
    service.rule_repository.get = AsyncMock(return_value=None)

    with pytest.raises(AlertRuleNotFoundError):
        await service.get_rule(999)


async def test_list_rules(service):
    rules = [make_alert_rule(id=1), make_alert_rule(id=2, name="Rule 2")]
    service.rule_repository.list = AsyncMock(return_value=rules)
    service.rule_repository.count = AsyncMock(return_value=2)

    result = await service.list_rules(PaginationParams())
    assert result.total == 2
    assert len(result.items) == 2


async def test_create_rule(service):
    rule = make_alert_rule(id=5)
    service.rule_repository.create = AsyncMock(return_value=rule)

    data = AlertRuleCreate(
        name="New Rule",
        rule_type="delay_threshold",
        severity="high",
        threshold_config={"delay_seconds": 300},
    )
    result = await service.create_rule(data)
    assert result.id == 5


async def test_update_rule_success(service):
    rule = make_alert_rule(id=1)
    updated = make_alert_rule(id=1, name="Updated")
    service.rule_repository.get = AsyncMock(return_value=rule)
    service.rule_repository.update = AsyncMock(return_value=updated)

    data = AlertRuleUpdate(name="Updated")
    result = await service.update_rule(1, data)
    assert result.name == "Updated"


async def test_update_rule_not_found(service):
    service.rule_repository.get = AsyncMock(return_value=None)

    with pytest.raises(AlertRuleNotFoundError):
        await service.update_rule(999, AlertRuleUpdate(name="X"))


async def test_delete_rule_success(service):
    rule = make_alert_rule(id=1)
    service.rule_repository.get = AsyncMock(return_value=rule)
    service.rule_repository.delete = AsyncMock()

    await service.delete_rule(1)
    service.rule_repository.delete.assert_awaited_once_with(rule)


async def test_delete_rule_not_found(service):
    service.rule_repository.get = AsyncMock(return_value=None)

    with pytest.raises(AlertRuleNotFoundError):
        await service.delete_rule(999)


# --- Instance methods ---


async def test_get_alert_success(service):
    alert = make_alert_instance(id=1)
    service.instance_repository.get = AsyncMock(return_value=alert)

    result = await service.get_alert(1)
    assert result.id == 1
    assert result.status == "active"


async def test_get_alert_not_found(service):
    service.instance_repository.get = AsyncMock(return_value=None)

    with pytest.raises(AlertNotFoundError):
        await service.get_alert(999)


async def test_list_alerts_with_filters(service):
    alerts = [make_alert_instance(id=1)]
    service.instance_repository.list = AsyncMock(return_value=alerts)
    service.instance_repository.count = AsyncMock(return_value=1)

    result = await service.list_alerts(PaginationParams(), status="active", severity="high")
    assert result.total == 1
    assert len(result.items) == 1


async def test_create_alert_manual(service):
    alert = make_alert_instance(id=10)
    service.instance_repository.create = AsyncMock(return_value=alert)

    data = AlertInstanceCreate(
        title="Manual alert",
        severity="medium",
        alert_type="manual",
    )
    result = await service.create_alert(data)
    assert result.id == 10


async def test_acknowledge_alert_success(service):
    alert = make_alert_instance(id=1)
    acked = make_alert_instance(id=1, status="acknowledged")
    service.instance_repository.get = AsyncMock(return_value=alert)
    service.instance_repository.acknowledge = AsyncMock(return_value=acked)

    result = await service.acknowledge_alert(1, user_id=42)
    assert result.status == "acknowledged"


async def test_acknowledge_alert_not_found(service):
    service.instance_repository.get = AsyncMock(return_value=None)

    with pytest.raises(AlertNotFoundError):
        await service.acknowledge_alert(999, user_id=42)


async def test_resolve_alert_success(service):
    alert = make_alert_instance(id=1)
    resolved = make_alert_instance(id=1, status="resolved")
    service.instance_repository.get = AsyncMock(return_value=alert)
    service.instance_repository.resolve = AsyncMock(return_value=resolved)

    result = await service.resolve_alert(1)
    assert result.status == "resolved"


async def test_get_summary(service):
    service.instance_repository.get_summary = AsyncMock(
        return_value={
            "total_active": 5,
            "critical": 2,
            "high": 1,
            "medium": 1,
            "low": 1,
            "info": 0,
        }
    )

    result = await service.get_summary()
    assert isinstance(result, AlertSummaryResponse)
    assert result.total_active == 5
    assert result.critical == 2
