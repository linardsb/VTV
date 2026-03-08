"""Shared test fixtures for the alerts feature."""

from unittest.mock import AsyncMock

import pytest

from app.alerts.models import AlertInstance, AlertRule
from app.shared.models import utcnow


def make_alert_rule(**overrides: object) -> AlertRule:
    """Factory to create an AlertRule model instance with sensible defaults."""
    now = utcnow()
    defaults: dict[str, object] = {
        "id": 1,
        "name": "High Delay Alert",
        "description": None,
        "rule_type": "delay_threshold",
        "severity": "high",
        "threshold_config": {"delay_seconds": 600},
        "enabled": True,
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    return AlertRule(**defaults)


def make_alert_instance(**overrides: object) -> AlertInstance:
    """Factory to create an AlertInstance model instance with sensible defaults."""
    now = utcnow()
    defaults: dict[str, object] = {
        "id": 1,
        "title": "Vehicle RS-1047 delayed 12 min",
        "severity": "high",
        "status": "active",
        "alert_type": "delay_threshold",
        "rule_id": 1,
        "source_entity_type": "vehicle",
        "source_entity_id": "RS-1047",
        "details": {"delay_seconds": 720},
        "acknowledged_at": None,
        "acknowledged_by_id": None,
        "resolved_at": None,
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    return AlertInstance(**defaults)


@pytest.fixture
def sample_rule() -> AlertRule:
    """A single default alert rule instance."""
    return make_alert_rule()


@pytest.fixture
def sample_rules() -> list[AlertRule]:
    """Multiple alert rules of different types."""
    return [
        make_alert_rule(id=1, name="Delay Alert", rule_type="delay_threshold", severity="high"),
        make_alert_rule(
            id=2,
            name="Maintenance Due",
            rule_type="maintenance_due",
            severity="medium",
            threshold_config={"days_before": 7},
        ),
        make_alert_rule(
            id=3,
            name="Registration Expiry",
            rule_type="registration_expiry",
            severity="critical",
            threshold_config={"days_before": 30},
        ),
    ]


@pytest.fixture
def sample_alert() -> AlertInstance:
    """A single default alert instance."""
    return make_alert_instance()


@pytest.fixture
def sample_alerts() -> list[AlertInstance]:
    """Multiple alert instances of different severities/statuses."""
    return [
        make_alert_instance(id=1, severity="critical", status="active"),
        make_alert_instance(
            id=2,
            title="Maintenance overdue RS-2055",
            severity="medium",
            status="acknowledged",
            alert_type="maintenance_due",
        ),
        make_alert_instance(
            id=3,
            title="Registration expiring RS-3001",
            severity="low",
            status="resolved",
            alert_type="registration_expiry",
        ),
    ]


@pytest.fixture
def mock_db() -> AsyncMock:
    """Mock AsyncSession for repository tests."""
    return AsyncMock()
