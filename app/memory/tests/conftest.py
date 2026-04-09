"""Fixtures and factories for memory tests."""

from unittest.mock import AsyncMock

import pytest

from app.memory.models import MemoryEntry
from app.memory.repository import MemoryRepository
from app.memory.service import MemoryService
from app.shared.models import utcnow


def make_memory(**overrides: object) -> MemoryEntry:
    """Factory for MemoryEntry with sensible defaults."""
    now = utcnow()
    defaults: dict[str, object] = {
        "id": 1,
        "agent_type": "transit",
        "memory_type": "semantic",
        "content": "Route 5 typically has delays during morning rush hour 07:30-09:00",
        "embedding": None,
        "metadata_json": {"route_id": "5", "confidence": 0.92},
        "decay_weight": 1.0,
        "is_evergreen": False,
        "source": "agent",
        "recalled_count": 0,
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    return MemoryEntry(**defaults)


def make_embedding(dim: int = 1024) -> list[float]:
    """Create a dummy embedding vector."""
    return [0.1] * dim


@pytest.fixture
def mock_db() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def repo(mock_db: AsyncMock) -> MemoryRepository:
    return MemoryRepository(mock_db)


@pytest.fixture
def service(mock_db: AsyncMock) -> MemoryService:
    svc = MemoryService(mock_db)
    svc.repository = AsyncMock()
    return svc


@pytest.fixture
def sample_memory() -> MemoryEntry:
    return make_memory()


@pytest.fixture
def sample_memories() -> list[MemoryEntry]:
    return [
        make_memory(id=1, memory_type="procedural", content="How to check route delays"),
        make_memory(id=2, memory_type="episodic", content="Dispatcher asked about route 5"),
        make_memory(id=3, memory_type="semantic", content="Route 5 peak hours: 07:30-09:00"),
        make_memory(id=4, memory_type="query_pattern", content="Show me route 5 status"),
    ]
