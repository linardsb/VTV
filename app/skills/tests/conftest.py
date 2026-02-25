"""Shared test fixtures for the skills feature."""

from unittest.mock import AsyncMock

import pytest

from app.shared.models import utcnow
from app.skills.models import AgentSkill


def make_skill(**overrides: object) -> AgentSkill:
    """Factory to create an AgentSkill model instance with sensible defaults."""
    now = utcnow()
    defaults: dict[str, object] = {
        "id": 1,
        "name": "Test Skill",
        "description": "A test skill",
        "content": "Test content for the skill",
        "category": "transit_ops",
        "is_active": True,
        "priority": 50,
        "created_by_id": None,
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    return AgentSkill(**defaults)


@pytest.fixture
def sample_skill() -> AgentSkill:
    """A single default skill instance."""
    return make_skill()


@pytest.fixture
def sample_skills() -> list[AgentSkill]:
    """Multiple skill instances for list tests."""
    return [
        make_skill(id=1, name="Priority System", category="transit_ops", priority=90),
        make_skill(id=2, name="Disruption Protocol", category="procedures", priority=80),
        make_skill(id=3, name="Glossary", category="glossary", priority=50),
    ]


@pytest.fixture
def mock_db() -> AsyncMock:
    """Mock AsyncSession for repository tests."""
    return AsyncMock()
