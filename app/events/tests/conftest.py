"""Shared test fixtures for the events feature."""

import datetime
from unittest.mock import AsyncMock

import pytest

from app.events.models import OperationalEvent
from app.shared.models import utcnow


def make_event(**overrides: object) -> OperationalEvent:
    """Factory to create an OperationalEvent model instance with sensible defaults."""
    now = utcnow()
    defaults: dict[str, object] = {
        "id": 1,
        "title": "Bus Fleet Inspection",
        "description": "Quarterly inspection of bus fleet at Depot A",
        "start_datetime": now,
        "end_datetime": now + datetime.timedelta(hours=2),
        "priority": "high",
        "category": "maintenance",
        "goals": None,
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    return OperationalEvent(**defaults)


@pytest.fixture
def sample_event() -> OperationalEvent:
    """A single default event instance."""
    return make_event()


@pytest.fixture
def sample_events() -> list[OperationalEvent]:
    """Multiple event instances for list tests."""
    now = utcnow()
    return [
        make_event(id=1, title="Bus Fleet Inspection"),
        make_event(id=2, title="Route 15 Detour", priority="medium", category="route-change"),
        make_event(
            id=3,
            title="Morning Shift Handover",
            priority="low",
            category="driver-shift",
            start_datetime=now + datetime.timedelta(days=1),
            end_datetime=now + datetime.timedelta(days=1, hours=1),
        ),
    ]


def make_goals_dict(**overrides: object) -> dict[str, object]:
    """Factory to create a goals dict matching EventGoals schema."""
    defaults: dict[str, object] = {
        "items": [
            {"text": "Complete route familiarization", "completed": False, "item_type": "route"},
            {"text": "Review safety procedures", "completed": True, "item_type": "training"},
        ],
        "route_id": 22,
        "transport_type": "bus",
        "vehicle_id": "RS-1047",
    }
    defaults.update(overrides)
    return defaults


@pytest.fixture
def mock_db() -> AsyncMock:
    """Mock AsyncSession for repository tests."""
    return AsyncMock()
