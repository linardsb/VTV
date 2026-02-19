# pyright: reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Unit tests for stop management REST API routes."""

from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app.core.rate_limit import limiter
from app.main import app
from app.shared.schemas import PaginatedResponse
from app.stops.exceptions import StopAlreadyExistsError, StopNotFoundError
from app.stops.routes import get_service
from app.stops.schemas import StopResponse
from app.stops.service import StopService
from app.stops.tests.conftest import make_stop

limiter.enabled = False


def _make_response(stop_id: int = 1, **overrides: object) -> StopResponse:
    """Create a StopResponse for test assertions.

    Args:
        stop_id: Stop ID.
        **overrides: Additional field overrides.

    Returns:
        A StopResponse instance.
    """
    stop = make_stop(id=stop_id, **overrides)
    return StopResponse.model_validate(stop)


def _mock_service() -> AsyncMock:
    """Create a mock StopService.

    Returns:
        AsyncMock configured as a StopService.
    """
    return AsyncMock(spec=StopService)


def test_list_stops():
    mock_svc = _mock_service()
    resp1 = _make_response(1, stop_name="Stop A")
    resp2 = _make_response(2, stop_name="Stop B", gtfs_stop_id="1002")

    mock_svc.list_stops = AsyncMock(
        return_value=PaginatedResponse[StopResponse](
            items=[resp1, resp2], total=2, page=1, page_size=20
        )
    )
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.get("/api/v1/stops/")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2
    finally:
        app.dependency_overrides.clear()


def test_list_stops_with_search():
    mock_svc = _mock_service()
    resp = _make_response(1, stop_name="Centrala stacija")

    mock_svc.list_stops = AsyncMock(
        return_value=PaginatedResponse[StopResponse](items=[resp], total=1, page=1, page_size=20)
    )
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.get("/api/v1/stops/?search=Centr")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
    finally:
        app.dependency_overrides.clear()


def test_get_stop():
    mock_svc = _mock_service()
    resp = _make_response(1, stop_name="Centrala stacija")
    mock_svc.get_stop = AsyncMock(return_value=resp)
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.get("/api/v1/stops/1")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        assert data["stop_name"] == "Centrala stacija"
    finally:
        app.dependency_overrides.clear()


def test_get_stop_not_found():
    mock_svc = _mock_service()
    mock_svc.get_stop = AsyncMock(side_effect=StopNotFoundError("Stop 999 not found"))
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.get("/api/v1/stops/999")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_create_stop():
    mock_svc = _mock_service()
    resp = _make_response(10, stop_name="New Stop", gtfs_stop_id="9999")
    mock_svc.create_stop = AsyncMock(return_value=resp)
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/stops/",
            json={"stop_name": "New Stop", "gtfs_stop_id": "9999"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["gtfs_stop_id"] == "9999"
    finally:
        app.dependency_overrides.clear()


def test_create_stop_duplicate():
    mock_svc = _mock_service()
    mock_svc.create_stop = AsyncMock(side_effect=StopAlreadyExistsError("already exists"))
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/stops/",
            json={"stop_name": "Dup Stop", "gtfs_stop_id": "1001"},
        )
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_update_stop():
    mock_svc = _mock_service()
    resp = _make_response(1, stop_name="Updated Name")
    mock_svc.update_stop = AsyncMock(return_value=resp)
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.patch(
            "/api/v1/stops/1",
            json={"stop_name": "Updated Name"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["stop_name"] == "Updated Name"
    finally:
        app.dependency_overrides.clear()


def test_delete_stop():
    mock_svc = _mock_service()
    mock_svc.delete_stop = AsyncMock()
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.delete("/api/v1/stops/1")
        assert response.status_code == 204
    finally:
        app.dependency_overrides.clear()


def test_nearby_stops():
    mock_svc = _mock_service()
    resp = _make_response(1, stop_name="Near Stop")
    mock_svc.search_nearby = AsyncMock(return_value=[resp])
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.get("/api/v1/stops/nearby?latitude=56.9496&longitude=24.1052")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["stop_name"] == "Near Stop"
    finally:
        app.dependency_overrides.clear()


def test_nearby_missing_params():
    mock_svc = _mock_service()
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.get("/api/v1/stops/nearby")
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()
