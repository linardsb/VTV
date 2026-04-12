"""Tests for stuck vehicle anomaly detection (ML-4.2)."""

from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.ml.anomaly.stuck import StuckVehicleEvaluator
from app.ml.tests.conftest import make_db_result, make_position_row


@pytest.fixture
def evaluator() -> StuckVehicleEvaluator:
    """Create a StuckVehicleEvaluator instance."""
    return StuckVehicleEvaluator()


@pytest.mark.asyncio
async def test_stuck_vehicle_detected(
    evaluator: StuckVehicleEvaluator,
    mock_redis: MagicMock,
    mock_settings: MagicMock,
    mock_db: AsyncMock,
) -> None:
    """Vehicle with < 20m movement over 10 min and active trip fires alert."""
    now = datetime.datetime.now(tz=datetime.UTC)
    # Two positions at nearly the same spot (< 20m apart)
    rows = [
        make_position_row("v1", 56.9496, 24.1052, now - datetime.timedelta(minutes=5)),
        make_position_row("v1", 56.9496, 24.1053, now - datetime.timedelta(minutes=1)),
    ]
    # First call: position query, second call: layover query (empty)
    mock_db.execute = AsyncMock(
        side_effect=[make_db_result(rows), make_db_result([])],
    )

    alerts = await evaluator.check(mock_db, mock_redis, mock_settings)

    assert len(alerts) == 1
    assert alerts[0].alert_type == "stuck_vehicle"
    assert alerts[0].source_entity_id == "v1"


@pytest.mark.asyncio
async def test_vehicle_moving_normally(
    evaluator: StuckVehicleEvaluator,
    mock_redis: MagicMock,
    mock_settings: MagicMock,
    mock_db: AsyncMock,
) -> None:
    """Vehicle with > 20m movement does not fire alert."""
    now = datetime.datetime.now(tz=datetime.UTC)
    # Two positions ~1km apart
    rows = [
        make_position_row("v1", 56.9496, 24.1052, now - datetime.timedelta(minutes=5)),
        make_position_row("v1", 56.9596, 24.1152, now - datetime.timedelta(minutes=1)),
    ]
    mock_db.execute = AsyncMock(
        side_effect=[make_db_result(rows), make_db_result([])],
    )

    alerts = await evaluator.check(mock_db, mock_redis, mock_settings)

    assert len(alerts) == 0


@pytest.mark.asyncio
async def test_no_positions_in_window(
    evaluator: StuckVehicleEvaluator,
    mock_redis: MagicMock,
    mock_settings: MagicMock,
    mock_db: AsyncMock,
) -> None:
    """No recent positions returns no alerts."""
    mock_db.execute = AsyncMock(return_value=make_db_result([]))

    alerts = await evaluator.check(mock_db, mock_redis, mock_settings)

    assert len(alerts) == 0


@pytest.mark.asyncio
async def test_terminal_stop_excluded(
    evaluator: StuckVehicleEvaluator,
    mock_redis: MagicMock,
    mock_settings: MagicMock,
    mock_db: AsyncMock,
) -> None:
    """Vehicle at last stop_sequence of trip is excluded from stuck detection."""
    now = datetime.datetime.now(tz=datetime.UTC)
    rows = [
        make_position_row("v1", 56.9496, 24.1052, now - datetime.timedelta(minutes=5)),
        make_position_row("v1", 56.9496, 24.1053, now - datetime.timedelta(minutes=1)),
    ]
    # First call: positions, second call: layover exclusion returns v1
    mock_db.execute = AsyncMock(
        side_effect=[make_db_result(rows), make_db_result([("v1",)])],
    )

    alerts = await evaluator.check(mock_db, mock_redis, mock_settings)

    assert len(alerts) == 0


@pytest.mark.asyncio
async def test_layover_excluded(
    evaluator: StuckVehicleEvaluator,
    mock_redis: MagicMock,
    mock_settings: MagicMock,
    mock_db: AsyncMock,
) -> None:
    """Vehicle at stop within arrival/departure window is excluded."""
    now = datetime.datetime.now(tz=datetime.UTC)
    rows = [
        make_position_row("v2", 56.9496, 24.1052, now - datetime.timedelta(minutes=5)),
        make_position_row("v2", 56.9496, 24.1053, now - datetime.timedelta(minutes=1)),
    ]
    # Layover query returns v2
    mock_db.execute = AsyncMock(
        side_effect=[make_db_result(rows), make_db_result([("v2",)])],
    )

    alerts = await evaluator.check(mock_db, mock_redis, mock_settings)

    assert len(alerts) == 0


@pytest.mark.asyncio
async def test_cooldown_suppresses_duplicate(
    evaluator: StuckVehicleEvaluator,
    mock_redis: MagicMock,
    mock_settings: MagicMock,
    mock_db: AsyncMock,
) -> None:
    """Redis cooldown key exists - no duplicate alert fired."""
    now = datetime.datetime.now(tz=datetime.UTC)
    rows = [
        make_position_row("v1", 56.9496, 24.1052, now - datetime.timedelta(minutes=5)),
        make_position_row("v1", 56.9496, 24.1053, now - datetime.timedelta(minutes=1)),
    ]
    mock_db.execute = AsyncMock(
        side_effect=[make_db_result(rows), make_db_result([])],
    )
    # Cooldown key exists
    mock_redis.get = AsyncMock(return_value=b"1")

    alerts = await evaluator.check(mock_db, mock_redis, mock_settings)

    assert len(alerts) == 0


@pytest.mark.asyncio
async def test_cooldown_expired_fires_again(
    evaluator: StuckVehicleEvaluator,
    mock_redis: MagicMock,
    mock_settings: MagicMock,
    mock_db: AsyncMock,
) -> None:
    """Redis cooldown key absent - alert fires again."""
    now = datetime.datetime.now(tz=datetime.UTC)
    rows = [
        make_position_row("v1", 56.9496, 24.1052, now - datetime.timedelta(minutes=5)),
        make_position_row("v1", 56.9496, 24.1053, now - datetime.timedelta(minutes=1)),
    ]
    mock_db.execute = AsyncMock(
        side_effect=[make_db_result(rows), make_db_result([])],
    )
    # Cooldown expired (no key)
    mock_redis.get = AsyncMock(return_value=None)

    alerts = await evaluator.check(mock_db, mock_redis, mock_settings)

    assert len(alerts) == 1
    assert alerts[0].alert_type == "stuck_vehicle"
    mock_redis.set.assert_called_once()
