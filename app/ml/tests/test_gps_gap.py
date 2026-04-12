"""Tests for GPS gap anomaly detection (ML-4.2)."""

from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.ml.anomaly.gps_gap import GPSGapEvaluator
from app.ml.tests.conftest import make_db_result, make_gap_row


@pytest.fixture
def evaluator() -> GPSGapEvaluator:
    """Create a GPSGapEvaluator instance."""
    return GPSGapEvaluator()


@pytest.mark.asyncio
async def test_gps_gap_detected(
    evaluator: GPSGapEvaluator,
    mock_redis: MagicMock,
    mock_settings: MagicMock,
    mock_db: AsyncMock,
) -> None:
    """Vehicle with no updates for 6 min during active trip fires alert."""
    now = datetime.datetime.now(tz=datetime.UTC)
    # Three vehicles: v1 stale (6 min), v2+v3 fresh -> 1/3 = 33% < 50% threshold
    # so no feed outage, just per-vehicle gap alert for v1
    rows = [
        make_gap_row("v1", "riga", now - datetime.timedelta(minutes=6)),
        make_gap_row("v2", "riga", now - datetime.timedelta(minutes=1)),
        make_gap_row("v3", "riga", now - datetime.timedelta(minutes=1)),
    ]
    mock_db.execute = AsyncMock(return_value=make_db_result(rows))

    alerts = await evaluator.check(mock_db, mock_redis, mock_settings)

    assert len(alerts) == 1
    assert alerts[0].alert_type == "gps_gap"
    assert alerts[0].source_entity_id == "v1"


@pytest.mark.asyncio
async def test_vehicle_recently_updated(
    evaluator: GPSGapEvaluator,
    mock_redis: MagicMock,
    mock_settings: MagicMock,
    mock_db: AsyncMock,
) -> None:
    """Vehicle with recent update (2 min ago) does not fire alert."""
    now = datetime.datetime.now(tz=datetime.UTC)
    rows = [
        make_gap_row("v1", "riga", now - datetime.timedelta(minutes=2)),
    ]
    mock_db.execute = AsyncMock(return_value=make_db_result(rows))

    alerts = await evaluator.check(mock_db, mock_redis, mock_settings)

    assert len(alerts) == 0


@pytest.mark.asyncio
async def test_feed_wide_suppression(
    evaluator: GPSGapEvaluator,
    mock_redis: MagicMock,
    mock_settings: MagicMock,
    mock_db: AsyncMock,
) -> None:
    """80% of feed vehicles have gap - one feed_outage, no per-vehicle alerts."""
    now = datetime.datetime.now(tz=datetime.UTC)
    stale = now - datetime.timedelta(minutes=10)
    fresh = now - datetime.timedelta(minutes=1)
    # 4 stale out of 5 = 80% > 50% threshold
    rows = [
        make_gap_row("v1", "riga", stale),
        make_gap_row("v2", "riga", stale),
        make_gap_row("v3", "riga", stale),
        make_gap_row("v4", "riga", stale),
        make_gap_row("v5", "riga", fresh),
    ]
    mock_db.execute = AsyncMock(return_value=make_db_result(rows))

    alerts = await evaluator.check(mock_db, mock_redis, mock_settings)

    # Should be exactly 1 feed_outage, no per-vehicle gps_gap alerts
    assert len(alerts) == 1
    assert alerts[0].alert_type == "feed_outage"
    assert alerts[0].source_entity_type is None
    assert alerts[0].details is not None
    assert alerts[0].details["feed_id"] == "riga"
    assert alerts[0].details["gap_count"] == 4


@pytest.mark.asyncio
async def test_partial_feed_gap_no_suppression(
    evaluator: GPSGapEvaluator,
    mock_redis: MagicMock,
    mock_settings: MagicMock,
    mock_db: AsyncMock,
) -> None:
    """30% gap - per-vehicle gps_gap alerts, no feed_outage."""
    now = datetime.datetime.now(tz=datetime.UTC)
    stale = now - datetime.timedelta(minutes=10)
    fresh = now - datetime.timedelta(minutes=1)
    # 3 stale out of 10 = 30% < 50% threshold
    rows = [
        make_gap_row("v1", "riga", stale),
        make_gap_row("v2", "riga", stale),
        make_gap_row("v3", "riga", stale),
        make_gap_row("v4", "riga", fresh),
        make_gap_row("v5", "riga", fresh),
        make_gap_row("v6", "riga", fresh),
        make_gap_row("v7", "riga", fresh),
        make_gap_row("v8", "riga", fresh),
        make_gap_row("v9", "riga", fresh),
        make_gap_row("v10", "riga", fresh),
    ]
    mock_db.execute = AsyncMock(return_value=make_db_result(rows))

    alerts = await evaluator.check(mock_db, mock_redis, mock_settings)

    assert len(alerts) == 3
    assert all(a.alert_type == "gps_gap" for a in alerts)
    assert not any(a.alert_type == "feed_outage" for a in alerts)


@pytest.mark.asyncio
async def test_cooldown_suppresses_gap_alert(
    evaluator: GPSGapEvaluator,
    mock_redis: MagicMock,
    mock_settings: MagicMock,
    mock_db: AsyncMock,
) -> None:
    """Redis cooldown active - skip duplicate gap alert."""
    now = datetime.datetime.now(tz=datetime.UTC)
    rows = [
        make_gap_row("v1", "riga", now - datetime.timedelta(minutes=10)),
    ]
    mock_db.execute = AsyncMock(return_value=make_db_result(rows))
    mock_redis.get = AsyncMock(return_value=b"1")

    alerts = await evaluator.check(mock_db, mock_redis, mock_settings)

    assert len(alerts) == 0


@pytest.mark.asyncio
async def test_feed_outage_cooldown(
    evaluator: GPSGapEvaluator,
    mock_redis: MagicMock,
    mock_settings: MagicMock,
    mock_db: AsyncMock,
) -> None:
    """Feed outage cooldown key exists - skip duplicate feed alert."""
    now = datetime.datetime.now(tz=datetime.UTC)
    stale = now - datetime.timedelta(minutes=10)
    fresh = now - datetime.timedelta(minutes=1)
    # 4 stale out of 5 = 80% -> feed outage
    rows = [
        make_gap_row("v1", "riga", stale),
        make_gap_row("v2", "riga", stale),
        make_gap_row("v3", "riga", stale),
        make_gap_row("v4", "riga", stale),
        make_gap_row("v5", "riga", fresh),
    ]
    mock_db.execute = AsyncMock(return_value=make_db_result(rows))
    # Feed outage cooldown exists
    mock_redis.get = AsyncMock(return_value=b"1")

    alerts = await evaluator.check(mock_db, mock_redis, mock_settings)

    # Feed outage suppressed by cooldown, per-vehicle suppressed by feed membership
    assert len(alerts) == 0
