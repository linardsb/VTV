"""Shared fixtures for analytics tests."""

import datetime
from unittest.mock import MagicMock

from app.shared.models import utcnow


def make_daily_adherence_report(**overrides: object) -> MagicMock:
    """Factory for DailyAdherenceReport-like mock objects.

    Args:
        **overrides: Attribute overrides to merge into defaults.

    Returns:
        A MagicMock with default report attributes.
    """
    now = utcnow()
    defaults: dict[str, object] = {
        "id": 1,
        "report_date": datetime.date(2026, 4, 10),
        "overall_pct": 88.5,
        "total_trips": 200,
        "on_time_trips": 177,
        "late_trips": 15,
        "early_trips": 8,
        "per_route_json": [
            {
                "route_id": "1",
                "route_short_name": "1",
                "total_trips": 50,
                "on_time_trips": 44,
                "late_trips": 4,
                "early_trips": 2,
                "on_time_pct": 88.0,
                "avg_delay_seconds": 120.5,
            }
        ],
        "per_hour_json": [
            {
                "hour": 7,
                "total_trips": 30,
                "on_time_trips": 26,
                "on_time_pct": 86.7,
            }
        ],
        "anomaly_count": 3,
        "alert_triggered": False,
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock
