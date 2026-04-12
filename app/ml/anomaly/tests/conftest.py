# pyright: reportUnknownMemberType=false, reportMissingTypeStubs=false
"""Shared fixtures for ML anomaly detection tests."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest


def make_vehicle_data(
    vehicle_id: str = "v1",
    route_id: str = "22",
    lat: float = 56.95,
    lon: float = 24.11,
    feed_id: str = "riga",
) -> dict[str, str | float]:
    """Build a vehicle data dict matching Redis JSON format."""
    return {
        "vehicle_id": vehicle_id,
        "route_id": route_id,
        "latitude": lat,
        "longitude": lon,
        "feed_id": feed_id,
    }


@pytest.fixture
def mock_redis() -> AsyncMock:
    """Create a mock Redis client with scan_iter, get, set, delete."""
    redis = AsyncMock()
    redis.scan_iter = MagicMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock()
    redis.delete = AsyncMock()
    return redis


@pytest.fixture
def mock_db() -> AsyncMock:
    """Create a mock async DB session."""
    return AsyncMock()


@pytest.fixture
def mock_db_context(mock_db: AsyncMock) -> Any:
    """Create a mock get_db_context that yields the mock_db session."""

    @asynccontextmanager
    async def _ctx() -> AsyncIterator[AsyncMock]:
        yield mock_db

    return _ctx
