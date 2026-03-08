# pyright: reportCallIssue=false, reportUnknownMemberType=false
"""Unit tests for geofence REST API routes."""

from __future__ import annotations

import datetime
from collections.abc import Iterator
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.geofences.routes import get_service
from app.geofences.schemas import GeofenceResponse
from app.shared.schemas import PaginatedResponse


@pytest.fixture(autouse=True)
def _disable_limiter() -> None:
    """Disable rate limiter for tests."""
    from app.core.rate_limit import limiter

    limiter.enabled = False


@pytest.fixture
def client() -> TestClient:
    """Test client."""
    from app.main import app

    return TestClient(app)


@pytest.fixture
def _override_cleanup() -> Iterator[None]:
    """Clean up dependency overrides after each test."""
    from app.main import app

    saved = dict(app.dependency_overrides)
    yield
    app.dependency_overrides.clear()
    app.dependency_overrides.update(saved)


def _mock_user(role: str = "admin") -> AsyncMock:
    """Create a mock user with the given role."""
    user = AsyncMock()
    user.id = 1
    user.email = "test@test.com"
    user.role = role
    user.is_active = True
    return user


def _sample_response() -> GeofenceResponse:
    """Create a sample GeofenceResponse."""
    return GeofenceResponse(
        id=1,
        name="Test Zone",
        zone_type="depot",
        color=None,
        alert_on_enter=True,
        alert_on_exit=True,
        alert_on_dwell=False,
        dwell_threshold_minutes=None,
        alert_severity="medium",
        description=None,
        coordinates=[
            [24.10, 56.94],
            [24.12, 56.94],
            [24.12, 56.96],
            [24.10, 56.96],
            [24.10, 56.94],
        ],
        is_active=True,
        created_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        updated_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
    )


def _setup_auth(role: str) -> None:
    """Set up auth override with the given role."""
    from app.auth.dependencies import get_current_user
    from app.main import app

    mock_user = _mock_user(role)
    app.dependency_overrides[get_current_user] = lambda: mock_user


def _setup_service(mock_service: AsyncMock) -> None:
    """Set up service override."""
    from app.main import app

    app.dependency_overrides[get_service] = lambda: mock_service


class TestListGeofences:
    """Tests for GET /api/v1/geofences/."""

    def test_list_geofences_requires_auth(self, client: TestClient) -> None:
        """Unauthenticated request returns 401 or 403."""
        response = client.get("/api/v1/geofences/")
        assert response.status_code in (401, 403)


class TestCreateGeofence:
    """Tests for POST /api/v1/geofences/."""

    @pytest.mark.usefixtures("_override_cleanup")
    def test_create_geofence_requires_editor(self, client: TestClient) -> None:
        """Viewer role gets forbidden."""
        _setup_auth("viewer")

        response = client.post(
            "/api/v1/geofences/",
            json={
                "name": "Test",
                "zone_type": "depot",
                "coordinates": [
                    [24.10, 56.94],
                    [24.12, 56.94],
                    [24.12, 56.96],
                    [24.10, 56.96],
                    [24.10, 56.94],
                ],
            },
        )
        assert response.status_code == 403

    @pytest.mark.usefixtures("_override_cleanup")
    def test_create_geofence_success(self, client: TestClient) -> None:
        """Editor role can create geofence."""
        _setup_auth("editor")

        mock_service = AsyncMock()
        mock_service.create_geofence = AsyncMock(return_value=_sample_response())
        _setup_service(mock_service)

        response = client.post(
            "/api/v1/geofences/",
            json={
                "name": "Test Zone",
                "zone_type": "depot",
                "coordinates": [
                    [24.10, 56.94],
                    [24.12, 56.94],
                    [24.12, 56.96],
                    [24.10, 56.96],
                    [24.10, 56.94],
                ],
            },
        )
        assert response.status_code == 201

    @pytest.mark.usefixtures("_override_cleanup")
    def test_create_geofence_invalid_coordinates(self, client: TestClient) -> None:
        """Unclosed polygon ring returns 422."""
        _setup_auth("editor")

        response = client.post(
            "/api/v1/geofences/",
            json={
                "name": "Bad Zone",
                "zone_type": "depot",
                "coordinates": [
                    [24.10, 56.94],
                    [24.12, 56.94],
                    [24.12, 56.96],
                ],
            },
        )
        assert response.status_code == 422


class TestDeleteGeofence:
    """Tests for DELETE /api/v1/geofences/{geofence_id}."""

    @pytest.mark.usefixtures("_override_cleanup")
    def test_delete_geofence_requires_admin(self, client: TestClient) -> None:
        """Editor role gets forbidden for delete."""
        _setup_auth("editor")

        response = client.delete("/api/v1/geofences/1")
        assert response.status_code == 403


class TestGetGeofence:
    """Tests for GET /api/v1/geofences/{geofence_id}."""

    @pytest.mark.usefixtures("_override_cleanup")
    def test_get_geofence_success(self, client: TestClient) -> None:
        """Authenticated user can get geofence by ID."""
        _setup_auth("viewer")

        mock_service = AsyncMock()
        mock_service.get_geofence = AsyncMock(return_value=_sample_response())
        _setup_service(mock_service)

        response = client.get("/api/v1/geofences/1")
        assert response.status_code == 200
        assert response.json()["name"] == "Test Zone"


class TestListEvents:
    """Tests for GET /api/v1/geofences/{geofence_id}/events."""

    @pytest.mark.usefixtures("_override_cleanup")
    def test_list_events_success(self, client: TestClient) -> None:
        """List events with time range filters."""
        _setup_auth("viewer")

        mock_service = AsyncMock()
        mock_service.list_events_by_geofence = AsyncMock(
            return_value=PaginatedResponse(items=[], total=0, page=1, page_size=20)
        )
        _setup_service(mock_service)

        response = client.get(
            "/api/v1/geofences/1/events",
            params={
                "start_time": "2026-01-01T00:00:00Z",
                "end_time": "2026-12-31T23:59:59Z",
            },
        )
        assert response.status_code == 200
        assert response.json()["total"] == 0
