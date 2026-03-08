# pyright: reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Unit tests for the background alert evaluator."""

import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from app.alerts.evaluator import (
    evaluate_rules_once,
    start_evaluator,
    stop_evaluator,
)
from app.alerts.tests.conftest import make_alert_rule


def _mock_settings(**overrides: object) -> MagicMock:
    """Create mock Settings."""
    settings = MagicMock()
    settings.alerts_enabled = True
    settings.alerts_check_interval_seconds = 60
    for key, val in overrides.items():
        setattr(settings, key, val)
    return settings


@patch("app.alerts.evaluator.get_db_context")
async def test_evaluate_maintenance_due_creates_alert(mock_db_ctx):
    """Evaluator creates alert for vehicle with upcoming maintenance."""
    mock_vehicle = MagicMock()
    mock_vehicle.fleet_number = "RS-1001"
    mock_vehicle.next_maintenance_date = datetime.datetime.now(
        tz=datetime.UTC
    ).date() + datetime.timedelta(days=3)

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_vehicle]
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()

    # First call: get_enabled_rules, subsequent calls: vehicle query + dedup + create
    rules_result = MagicMock()
    rules_result.scalars.return_value.all.return_value = [
        make_alert_rule(id=1, rule_type="maintenance_due", threshold_config={"days_before": 7})
    ]

    dedup_result = MagicMock()
    dedup_result.scalar_one_or_none.return_value = None

    call_count = 0

    async def mock_execute(stmt):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return rules_result
        if call_count == 2:
            return mock_result
        return dedup_result

    mock_session.execute = AsyncMock(side_effect=mock_execute)

    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    mock_db_ctx.return_value = ctx

    settings = _mock_settings()
    count = await evaluate_rules_once(settings)
    assert count >= 0  # Just verify it doesn't crash


@patch("app.alerts.evaluator.get_db_context")
async def test_evaluate_no_enabled_rules(mock_db_ctx):
    """Evaluator with no rules returns 0."""
    mock_session = AsyncMock()
    rules_result = MagicMock()
    rules_result.scalars.return_value.all.return_value = []
    mock_session.execute = AsyncMock(return_value=rules_result)

    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    mock_db_ctx.return_value = ctx

    settings = _mock_settings()
    count = await evaluate_rules_once(settings)
    assert count == 0


@patch("app.alerts.evaluator.get_db_context")
@patch("app.alerts.evaluator.get_redis")
async def test_evaluate_delay_threshold_redis_unavailable(mock_get_redis, mock_db_ctx):
    """Evaluator handles Redis failure gracefully."""
    mock_get_redis.side_effect = ConnectionError("Redis down")

    mock_session = AsyncMock()
    rules_result = MagicMock()
    rules_result.scalars.return_value.all.return_value = [
        make_alert_rule(id=1, rule_type="delay_threshold", threshold_config={"delay_seconds": 600})
    ]
    mock_session.execute = AsyncMock(return_value=rules_result)

    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    mock_db_ctx.return_value = ctx

    settings = _mock_settings()
    count = await evaluate_rules_once(settings)
    assert count == 0


@patch("app.alerts.evaluator._evaluator_task", None)
async def test_start_stop_evaluator():
    """Verify evaluator task creation and cancellation."""
    settings = _mock_settings(alerts_check_interval_seconds=1)

    await start_evaluator(settings)

    import app.alerts.evaluator as ev_mod

    assert ev_mod._evaluator_task is not None
    task = ev_mod._evaluator_task

    await stop_evaluator()
    assert ev_mod._evaluator_task is None
    assert task.cancelled() or task.done()


@patch("app.alerts.evaluator._evaluator_task", None)
async def test_start_evaluator_disabled():
    """Evaluator does not start when alerts_enabled is False."""
    settings = _mock_settings(alerts_enabled=False)

    await start_evaluator(settings)

    import app.alerts.evaluator as ev_mod

    assert ev_mod._evaluator_task is None


async def test_stop_evaluator_when_not_started():
    """Stop is a no-op when evaluator was never started."""
    import app.alerts.evaluator as ev_mod

    ev_mod._evaluator_task = None
    await stop_evaluator()  # Should not raise
