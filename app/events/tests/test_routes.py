# pyright: reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Unit tests for operational events REST API routes."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.core.rate_limit import limiter
from app.events.exceptions import EventNotFoundError
from app.events.routes import get_service
from app.events.schemas import EventResponse
from app.events.service import EventService
from app.events.tests.conftest import make_event
from app.main import app
from app.shared.schemas import PaginatedResponse

limiter.enabled = False


def _mock_admin_user() -> User:
    """Return a mock admin user for testing."""
    user = MagicMock(spec=User)
    user.id = 1
    user.email = "admin@vtv.lv"
    user.name = "Admin"
    user.role = "admin"
    user.is_active = True
    return user


@pytest.fixture(autouse=True)
def _setup_auth_override() -> Generator[None, None, None]:
    """Ensure auth override is set before each test and restored after."""
    app.dependency_overrides[get_current_user] = _mock_admin_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


def _make_response(event_id: int = 1, **overrides: object) -> EventResponse:
    """Create an EventResponse for test assertions."""
    event = make_event(id=event_id, **overrides)
    return EventResponse.model_validate(event)


def _mock_service() -> AsyncMock:
    """Create a mock EventService."""
    return AsyncMock(spec=EventService)


# --- Public read endpoints (no auth required) ---


def test_list_events():
    mock_svc = _mock_service()
    resp1 = _make_response(1, title="Inspection")
    resp2 = _make_response(2, title="Detour")

    mock_svc.list_events = AsyncMock(
        return_value=PaginatedResponse[EventResponse](
            items=[resp1, resp2], total=2, page=1, page_size=20
        )
    )
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.get("/api/v1/events/")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_get_event():
    mock_svc = _mock_service()
    resp = _make_response(1, title="Inspection")
    mock_svc.get_event = AsyncMock(return_value=resp)
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.get("/api/v1/events/1")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        assert data["title"] == "Inspection"
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_get_event_not_found():
    mock_svc = _mock_service()
    mock_svc.get_event = AsyncMock(side_effect=EventNotFoundError("Event 999 not found"))
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.get("/api/v1/events/999")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.pop(get_service, None)


# --- Protected write endpoints (require admin/editor) ---


def test_create_event():
    mock_svc = _mock_service()
    resp = _make_response(10, title="New Event")
    mock_svc.create_event = AsyncMock(return_value=resp)
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/events/",
            json={
                "title": "New Event",
                "start_datetime": "2026-03-01T08:00:00Z",
                "end_datetime": "2026-03-01T10:00:00Z",
                "priority": "high",
                "category": "maintenance",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "New Event"
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_update_event():
    mock_svc = _mock_service()
    resp = _make_response(1, title="Updated")
    mock_svc.update_event = AsyncMock(return_value=resp)
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.patch(
            "/api/v1/events/1",
            json={"title": "Updated"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated"
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_delete_event():
    mock_svc = _mock_service()
    mock_svc.delete_event = AsyncMock()
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.delete("/api/v1/events/1")
        assert response.status_code == 204
    finally:
        app.dependency_overrides.pop(get_service, None)
