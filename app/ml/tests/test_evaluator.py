"""Tests for anomaly evaluator orchestrator (ML-4.2)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.alerts.schemas import AlertInstanceCreate


@pytest.mark.asyncio
@patch("app.ml.anomaly.evaluator.record_poller_tick")
@patch("app.ml.anomaly.evaluator.get_settings")
@patch("app.ml.anomaly.evaluator.get_db_context")
@patch("app.ml.anomaly.evaluator.get_redis")
@patch("app.ml.anomaly.evaluator._gps_gap_evaluator")
@patch("app.ml.anomaly.evaluator._stuck_evaluator")
async def test_evaluate_anomalies_once_creates_alerts(
    mock_stuck: MagicMock,
    mock_gap: MagicMock,
    mock_get_redis: AsyncMock,
    mock_get_db_context: MagicMock,
    mock_get_settings: MagicMock,
    mock_record_tick: MagicMock,
) -> None:
    """Both detectors return alerts, all persisted via repository."""
    from app.ml.anomaly.evaluator import evaluate_anomalies_once

    # Setup mock DB context
    mock_db = AsyncMock()
    mock_get_db_context.return_value.__aenter__ = AsyncMock(return_value=mock_db)
    mock_get_db_context.return_value.__aexit__ = AsyncMock(return_value=False)

    mock_redis = AsyncMock()
    mock_get_redis.return_value = mock_redis

    mock_settings = MagicMock()
    mock_get_settings.return_value = mock_settings

    stuck_alert = AlertInstanceCreate(
        title="Vehicle v1 stuck",
        severity="high",
        alert_type="stuck_vehicle",
        source_entity_type="vehicle",
        source_entity_id="v1",
        rule_id=None,
        details=None,
    )
    gap_alert = AlertInstanceCreate(
        title="GPS gap: v2",
        severity="high",
        alert_type="gps_gap",
        source_entity_type="vehicle",
        source_entity_id="v2",
        rule_id=None,
        details=None,
    )

    mock_stuck.check = AsyncMock(return_value=[stuck_alert])
    mock_gap.check = AsyncMock(return_value=[gap_alert])

    with patch("app.ml.anomaly.evaluator.AlertInstanceRepository") as mock_repo_cls:
        mock_repo = AsyncMock()
        mock_repo.find_active_duplicate = AsyncMock(return_value=None)
        mock_repo.create = AsyncMock()
        mock_repo_cls.return_value = mock_repo

        count = await evaluate_anomalies_once()

    assert count == 2
    assert mock_repo.create.call_count == 2
    mock_record_tick.assert_called_once_with("anomaly_evaluator")


@pytest.mark.asyncio
@patch("app.ml.anomaly.evaluator.record_poller_tick")
@patch("app.ml.anomaly.evaluator.get_settings")
@patch("app.ml.anomaly.evaluator.get_db_context")
@patch("app.ml.anomaly.evaluator.get_redis")
@patch("app.ml.anomaly.evaluator._gps_gap_evaluator")
@patch("app.ml.anomaly.evaluator._stuck_evaluator")
async def test_evaluate_anomalies_handles_errors(
    mock_stuck: MagicMock,
    mock_gap: MagicMock,
    mock_get_redis: AsyncMock,
    mock_get_db_context: MagicMock,
    mock_get_settings: MagicMock,
    mock_record_tick: MagicMock,
) -> None:
    """One detector raises Exception, other still runs, error logged."""
    from app.ml.anomaly.evaluator import evaluate_anomalies_once

    mock_db = AsyncMock()
    mock_get_db_context.return_value.__aenter__ = AsyncMock(return_value=mock_db)
    mock_get_db_context.return_value.__aexit__ = AsyncMock(return_value=False)

    mock_redis = AsyncMock()
    mock_get_redis.return_value = mock_redis

    mock_settings = MagicMock()
    mock_get_settings.return_value = mock_settings

    # Stuck evaluator raises, gap evaluator returns an alert
    mock_stuck.check = AsyncMock(side_effect=RuntimeError("DB timeout"))
    gap_alert = AlertInstanceCreate(
        title="GPS gap: v2",
        severity="high",
        alert_type="gps_gap",
        source_entity_type="vehicle",
        source_entity_id="v2",
        rule_id=None,
        details=None,
    )
    mock_gap.check = AsyncMock(return_value=[gap_alert])

    with patch("app.ml.anomaly.evaluator.AlertInstanceRepository") as mock_repo_cls:
        mock_repo = AsyncMock()
        mock_repo.find_active_duplicate = AsyncMock(return_value=None)
        mock_repo.create = AsyncMock()
        mock_repo_cls.return_value = mock_repo

        count = await evaluate_anomalies_once()

    # Only the gap alert should be persisted (stuck failed gracefully)
    assert count == 1
    assert mock_repo.create.call_count == 1
