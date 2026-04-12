"""Shared test fixtures for ML anomaly detection tests."""

from __future__ import annotations

import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.config import Settings


def make_position_row(
    vehicle_id: str = "v1",
    latitude: float = 56.9496,
    longitude: float = 24.1052,
    recorded_at: datetime.datetime | None = None,
    trip_id: str = "trip_1",
    feed_id: str = "riga",
) -> tuple[str, float, float, datetime.datetime, str, str]:
    """Create a mock position row matching the SQL query result shape.

    Args:
        vehicle_id: Vehicle identifier.
        latitude: WGS84 latitude.
        longitude: WGS84 longitude.
        recorded_at: Position timestamp (defaults to now).
        trip_id: GTFS trip identifier.
        feed_id: Feed identifier.

    Returns:
        Tuple matching the SQL SELECT column order.
    """
    if recorded_at is None:
        recorded_at = datetime.datetime.now(tz=datetime.UTC)
    return (vehicle_id, latitude, longitude, recorded_at, trip_id, feed_id)


def make_gap_row(
    vehicle_id: str = "v1",
    feed_id: str = "riga",
    last_seen: datetime.datetime | None = None,
) -> tuple[str, str, datetime.datetime]:
    """Create a mock gap query row matching the SQL result shape.

    Args:
        vehicle_id: Vehicle identifier.
        feed_id: Feed identifier.
        last_seen: Last position timestamp (defaults to now).

    Returns:
        Tuple matching the SQL SELECT column order.
    """
    if last_seen is None:
        last_seen = datetime.datetime.now(tz=datetime.UTC)
    return (vehicle_id, feed_id, last_seen)


@pytest.fixture
def mock_redis() -> MagicMock:
    """Create a mock Redis client with async get/set."""
    redis = MagicMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    return redis


@pytest.fixture
def mock_settings() -> MagicMock:
    """Create a mock Settings with ML anomaly defaults."""
    s = MagicMock(spec=Settings)
    s.ml_anomaly_evaluator_enabled = True
    s.ml_anomaly_check_interval_seconds = 60
    s.ml_stuck_distance_threshold_m = 20.0
    s.ml_stuck_time_window_minutes = 10
    s.ml_gps_gap_threshold_minutes = 5
    s.ml_gps_gap_feed_outage_pct = 50
    s.ml_anomaly_cooldown_seconds = 900
    return s


@pytest.fixture
def mock_db() -> AsyncMock:
    """Create a mock async DB session."""
    db = AsyncMock()
    return db


def make_db_result(rows: list[Any]) -> MagicMock:
    """Create a mock DB execute result with fetchall().

    Args:
        rows: List of row tuples to return from fetchall().

    Returns:
        Mock result object.
    """
    result = MagicMock()
    result.fetchall.return_value = rows
    return result
