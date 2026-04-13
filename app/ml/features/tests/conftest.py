# pyright: reportUnknownMemberType=false, reportUnknownArgumentType=false
"""Test fixtures for ETA feature engineering (ML-2.1)."""

from __future__ import annotations

import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pandas as pd
import pytest


def make_eta_features_dict(**overrides: Any) -> dict[str, Any]:
    """Create a dict with all 18 ETA feature fields + sensible defaults.

    Args:
        **overrides: Fields to override from defaults.

    Returns:
        Dict with all feature fields.
    """
    defaults: dict[str, Any] = {
        "day_of_week": 0,  # Monday
        "month": 3,
        "is_school_day": True,
        "is_holiday": False,
        "weather_bucket": "clear",
        "route_type": 3,  # Bus
        "direction": 0,
        "operator": "Rigas Satiksme",
        "time_of_day_hour": 8.5,
        "scheduled_headway_s": 600.0,
        "historical_avg_delay_at_stop_s": 30.0,
        "prev_stop_actual_delay_s": 15.0,
        "trip_elapsed_pct": 0.5,
        "temp_c": 5.0,
        "wind_mps": 3.0,
        "precip_mm_last_hr": 0.0,
        "traffic_count_rolling_7d": 1200.0,
        "accident_count_within_500m": 0,
    }
    defaults.update(overrides)
    return defaults


def make_eta_features_df(n: int = 10, **overrides: Any) -> pd.DataFrame:
    """Create a DataFrame of n rows using the feature factory.

    Args:
        n: Number of rows.
        **overrides: Fields to override in all rows.

    Returns:
        DataFrame with trip_id, stop_sequence, and all 18 feature columns.
    """
    rows = []
    for i in range(n):
        row = make_eta_features_dict(**overrides)
        row["trip_id"] = i + 1
        row["stop_sequence"] = i + 1
        rows.append(row)
    return pd.DataFrame(rows)


@pytest.fixture()
def sample_features_df() -> pd.DataFrame:
    return make_eta_features_df(5)


@pytest.fixture()
def mock_db_session() -> AsyncMock:
    """Pre-configured AsyncMock database session."""
    db = AsyncMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    return db


def make_mapping_result(rows: list[dict[str, Any]]) -> MagicMock:
    """Create a mock result that returns rows via .mappings().first() or .all().

    Args:
        rows: List of row dicts to return.

    Returns:
        MagicMock configured as a SQLAlchemy result proxy.
    """
    mappings_mock = MagicMock()
    mappings_mock.first.return_value = rows[0] if rows else None
    mappings_mock.all.return_value = rows

    result_mock = MagicMock()
    result_mock.mappings.return_value = mappings_mock
    result_mock.first.return_value = tuple(rows[0].values()) if rows else None
    return result_mock


SAMPLE_OBSERVED_AT = datetime.datetime(2026, 3, 15, 8, 30, 0, tzinfo=datetime.UTC)


def make_load_features_df(n: int = 10, **overrides: Any) -> pd.DataFrame:
    """Create a DataFrame of n rows with load feature columns.

    Args:
        n: Number of rows.
        **overrides: Fields to override in all rows.

    Returns:
        DataFrame with all load feature columns.
    """
    rows = []
    for i in range(n):
        row: dict[str, Any] = {
            "gtfs_trip_id": f"trip_{i:03d}",
            "stop_sequence": float(i + 1),
            "stop_id": float(100 + i),
            "date": datetime.date(2026, 3, 15),
            "hour": 8,
            "route_code": "22",
            "transport_type": "bus",
            "tap_count": 5,
            "cumulative_load": 5 * (i + 1),
            "capacity": 60,
            "load_factor_pct": min((5 * (i + 1) / 60) * 100, 100.0),
        }
        row.update(overrides)
        rows.append(row)
    return pd.DataFrame(rows)


def make_correlated_tap(**overrides: Any) -> dict[str, Any]:
    """Create a single correlated tap dict with sensible defaults.

    Args:
        **overrides: Fields to override from defaults.

    Returns:
        Dict representing a correlated e-ticket tap row.
    """
    defaults: dict[str, Any] = {
        "eticket_id": 1,
        "vehicle_number": "4521",
        "validated_at": SAMPLE_OBSERVED_AT,
        "route_code": "22",
        "transport_type": "bus",
        "gtfs_trip_id": "trip_001",
        "vp_lat": 56.9496,
        "vp_lon": 24.1052,
        "position_at": SAMPLE_OBSERVED_AT,
        "stop_id": 101,
        "gtfs_stop_id": "stop_001",
        "stop_sequence": 1,
    }
    defaults.update(overrides)
    return defaults
