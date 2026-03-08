# pyright: reportCallIssue=false
"""Test fixtures for geofence feature tests."""

from unittest.mock import AsyncMock

import pytest

from app.geofences.schemas import GeofenceCreate, GeofenceUpdate
from app.geofences.service import GeofenceService


@pytest.fixture
def mock_db() -> AsyncMock:
    """Mock AsyncSession for unit tests."""
    return AsyncMock()


@pytest.fixture
def sample_geofence_create() -> GeofenceCreate:
    """Sample geofence creation data - polygon around central Riga."""
    return GeofenceCreate(
        name="Central Riga Depot",
        zone_type="depot",
        coordinates=[
            [24.10, 56.94],
            [24.12, 56.94],
            [24.12, 56.96],
            [24.10, 56.96],
            [24.10, 56.94],
        ],
        alert_on_enter=True,
        alert_on_exit=True,
        alert_on_dwell=False,
        alert_severity="medium",
    )


@pytest.fixture
def sample_geofence_update() -> GeofenceUpdate:
    """Sample geofence update data - partial update."""
    return GeofenceUpdate(name="Updated Depot Name")


@pytest.fixture
def geofence_service(mock_db: AsyncMock) -> GeofenceService:
    """GeofenceService instance with mock database."""
    return GeofenceService(mock_db)
