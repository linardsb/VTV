"""Shared test fixtures for the vehicles feature."""

import datetime
from unittest.mock import MagicMock

from app.shared.models import utcnow


def make_vehicle(**overrides: object) -> MagicMock:
    """Factory to create a mock Vehicle with sensible defaults.

    Args:
        **overrides: Field values to override defaults.

    Returns:
        A MagicMock with all vehicle fields populated.
    """
    now = utcnow()
    defaults: dict[str, object] = {
        "id": 1,
        "fleet_number": "4521",
        "vehicle_type": "bus",
        "license_plate": "AB-1234",
        "manufacturer": "Solaris",
        "model_name": "Urbino 12",
        "model_year": 2020,
        "capacity": 90,
        "status": "active",
        "current_driver_id": None,
        "mileage_km": 50000,
        "qualified_route_ids": "1,3,22",
        "registration_expiry": datetime.date(2027, 6, 15),
        "next_maintenance_date": datetime.date(2026, 4, 1),
        "notes": None,
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    mock = MagicMock()
    for key, value in defaults.items():
        setattr(mock, key, value)
    return mock


def make_maintenance_record(**overrides: object) -> MagicMock:
    """Factory to create a mock MaintenanceRecord with sensible defaults.

    Args:
        **overrides: Field values to override defaults.

    Returns:
        A MagicMock with all maintenance record fields populated.
    """
    now = utcnow()
    today = datetime.datetime.now(tz=datetime.UTC).date()
    defaults: dict[str, object] = {
        "id": 1,
        "vehicle_id": 1,
        "maintenance_type": "scheduled",
        "description": "Regular service",
        "performed_date": today,
        "mileage_at_service": 50000,
        "cost_eur": 350.0,
        "next_scheduled_date": today + datetime.timedelta(days=90),
        "performed_by": "Fleet Workshop",
        "notes": None,
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    mock = MagicMock()
    for key, value in defaults.items():
        setattr(mock, key, value)
    return mock
