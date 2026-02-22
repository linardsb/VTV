# pyright: reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Unit tests for driver management REST API routes."""

from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app.core.rate_limit import limiter
from app.drivers.exceptions import DriverNotFoundError
from app.drivers.routes import get_service
from app.drivers.schemas import DriverResponse
from app.drivers.service import DriverService
from app.drivers.tests.conftest import make_driver
from app.main import app
from app.shared.schemas import PaginatedResponse

limiter.enabled = False


def _make_response(driver_id: int = 1, **overrides: object) -> DriverResponse:
    """Create a DriverResponse for test assertions."""
    driver = make_driver(id=driver_id, **overrides)
    return DriverResponse.model_validate(driver)


def _mock_service() -> AsyncMock:
    """Create a mock DriverService."""
    return AsyncMock(spec=DriverService)


def test_list_drivers():
    mock_svc = _mock_service()
    resp1 = _make_response(1, first_name="Janis")
    resp2 = _make_response(2, first_name="Anna", employee_number="DRV-002")

    mock_svc.list_drivers = AsyncMock(
        return_value=PaginatedResponse[DriverResponse](
            items=[resp1, resp2], total=2, page=1, page_size=20
        )
    )
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.get("/api/v1/drivers/")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2
    finally:
        app.dependency_overrides.clear()


def test_get_driver():
    mock_svc = _mock_service()
    resp = _make_response(1, first_name="Janis")
    mock_svc.get_driver = AsyncMock(return_value=resp)
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.get("/api/v1/drivers/1")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        assert data["first_name"] == "Janis"
    finally:
        app.dependency_overrides.clear()


def test_get_driver_not_found():
    mock_svc = _mock_service()
    mock_svc.get_driver = AsyncMock(side_effect=DriverNotFoundError("Driver 999 not found"))
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.get("/api/v1/drivers/999")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_create_driver():
    mock_svc = _mock_service()
    resp = _make_response(10, first_name="New", last_name="Driver", employee_number="DRV-099")
    mock_svc.create_driver = AsyncMock(return_value=resp)
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/drivers/",
            json={
                "first_name": "New",
                "last_name": "Driver",
                "employee_number": "DRV-099",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["employee_number"] == "DRV-099"
    finally:
        app.dependency_overrides.clear()


def test_update_driver():
    mock_svc = _mock_service()
    resp = _make_response(1, first_name="Updated")
    mock_svc.update_driver = AsyncMock(return_value=resp)
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.patch(
            "/api/v1/drivers/1",
            json={"first_name": "Updated"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["first_name"] == "Updated"
    finally:
        app.dependency_overrides.clear()


def test_delete_driver():
    mock_svc = _mock_service()
    mock_svc.delete_driver = AsyncMock()
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.delete("/api/v1/drivers/1")
        assert response.status_code == 204
    finally:
        app.dependency_overrides.clear()
