"""Shared test fixtures for the stops feature."""

from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from app.shared.models import utcnow
from app.stops.models import Stop


def make_stop(**overrides: object) -> Stop:
    """Factory to create a Stop model instance with sensible defaults.

    Args:
        **overrides: Field values to override defaults.

    Returns:
        A Stop instance with all fields populated.
    """
    now = utcnow()
    defaults: dict[str, object] = {
        "id": 1,
        "gtfs_stop_id": "1001",
        "stop_name": "Centrala stacija",
        "stop_lat": 56.9496,
        "stop_lon": 24.1052,
        "stop_desc": None,
        "location_type": 0,
        "parent_station_id": None,
        "wheelchair_boarding": 0,
        "geom": None,
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)

    stop = Stop(**defaults)
    return stop


@pytest.fixture
def stop_factory() -> type:
    """Provide the make_stop factory as a fixture.

    Returns a callable that creates Stop instances.
    """

    class _Factory:
        @staticmethod
        def create(**kwargs: object) -> Stop:
            return make_stop(**kwargs)

    return _Factory


@pytest.fixture
def sample_stop() -> Stop:
    """A single default stop instance."""
    return make_stop()


@pytest.fixture
def sample_stops() -> list[Stop]:
    """Multiple stop instances for list tests."""
    return [
        make_stop(id=1, gtfs_stop_id="1001", stop_name="Centrala stacija"),
        make_stop(id=2, gtfs_stop_id="1002", stop_name="Brivibas iela"),
        make_stop(id=3, gtfs_stop_id="1003", stop_name="Jugla"),
    ]


@pytest.fixture
def mock_db() -> AsyncMock:
    """Mock AsyncSession for repository tests."""
    return AsyncMock()


@pytest.fixture
def nearby_stops() -> list[Stop]:
    """Stops at known distances from (56.9496, 24.1052) for proximity tests."""
    return [
        make_stop(
            id=1,
            gtfs_stop_id="1001",
            stop_name="Very Near Stop",
            stop_lat=56.9497,
            stop_lon=24.1053,
        ),
        make_stop(
            id=2,
            gtfs_stop_id="1002",
            stop_name="Medium Stop",
            stop_lat=56.9520,
            stop_lon=24.1100,
        ),
        make_stop(
            id=3,
            gtfs_stop_id="1003",
            stop_name="Far Stop",
            stop_lat=56.9700,
            stop_lon=24.1500,
        ),
        make_stop(
            id=4,
            gtfs_stop_id="1004",
            stop_name="No Coords Stop",
            stop_lat=None,
            stop_lon=None,
        ),
    ]


def make_stop_response_dict(stop: Stop) -> dict[str, object]:
    """Convert a Stop instance to a dict matching StopResponse shape.

    Args:
        stop: The Stop model instance.

    Returns:
        Dict with all StopResponse fields.
    """
    created = stop.created_at if isinstance(stop.created_at, datetime) else utcnow()
    updated = stop.updated_at if isinstance(stop.updated_at, datetime) else utcnow()
    return {
        "id": stop.id,
        "gtfs_stop_id": stop.gtfs_stop_id,
        "stop_name": stop.stop_name,
        "stop_lat": stop.stop_lat,
        "stop_lon": stop.stop_lon,
        "stop_desc": stop.stop_desc,
        "location_type": stop.location_type,
        "parent_station_id": stop.parent_station_id,
        "wheelchair_boarding": stop.wheelchair_boarding,
        "is_active": stop.is_active,
        "created_at": created.isoformat(),
        "updated_at": updated.isoformat(),
    }
