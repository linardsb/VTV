"""Shared test fixtures for the drivers feature."""

import datetime
from unittest.mock import AsyncMock

import pytest

from app.drivers.models import Driver
from app.shared.models import utcnow


def make_driver(**overrides: object) -> Driver:
    """Factory to create a Driver model instance with sensible defaults.

    Args:
        **overrides: Field values to override defaults.

    Returns:
        A Driver instance with all fields populated.
    """
    now = utcnow()
    defaults: dict[str, object] = {
        "id": 1,
        "employee_number": "DRV-001",
        "first_name": "Janis",
        "last_name": "Berzins",
        "date_of_birth": datetime.date(1985, 3, 15),
        "phone": "+371 20000001",
        "email": "janis.berzins@vtv.lv",
        "address": None,
        "emergency_contact_name": None,
        "emergency_contact_phone": None,
        "photo_url": None,
        "hire_date": datetime.date(2020, 1, 10),
        "license_categories": "D,D1",
        "license_expiry_date": datetime.date(2028, 6, 30),
        "medical_cert_expiry": datetime.date(2027, 12, 31),
        "qualified_route_ids": "bus_1,bus_3,bus_7",
        "default_shift": "morning",
        "status": "available",
        "notes": None,
        "training_records": None,
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    return Driver(**defaults)


@pytest.fixture
def sample_driver() -> Driver:
    """A single default driver instance."""
    return make_driver()


@pytest.fixture
def sample_drivers() -> list[Driver]:
    """Multiple driver instances for list tests."""
    return [
        make_driver(id=1, employee_number="DRV-001", first_name="Janis", last_name="Berzins"),
        make_driver(id=2, employee_number="DRV-002", first_name="Anna", last_name="Kalnina"),
        make_driver(
            id=3,
            employee_number="DRV-003",
            first_name="Maris",
            last_name="Ozols",
            default_shift="afternoon",
        ),
    ]


@pytest.fixture
def mock_db() -> AsyncMock:
    """Mock AsyncSession for repository tests."""
    return AsyncMock()
