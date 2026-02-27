# pyright: reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Unit tests for vehicle management REST API routes."""

import datetime
from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.core.rate_limit import limiter
from app.main import app
from app.shared.schemas import PaginatedResponse
from app.vehicles.exceptions import VehicleAlreadyExistsError, VehicleNotFoundError
from app.vehicles.routes import get_service
from app.vehicles.schemas import MaintenanceRecordResponse, VehicleResponse
from app.vehicles.service import VehicleService

from .conftest import make_maintenance_record, make_vehicle

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


def _make_vehicle_response(vehicle_id: int = 1, **overrides: object) -> VehicleResponse:
    """Create a VehicleResponse for test assertions."""
    vehicle = make_vehicle(id=vehicle_id, **overrides)
    return VehicleResponse.model_validate(vehicle)


def _make_maintenance_response(
    record_id: int = 1, **overrides: object
) -> MaintenanceRecordResponse:
    """Create a MaintenanceRecordResponse for test assertions."""
    record = make_maintenance_record(id=record_id, **overrides)
    return MaintenanceRecordResponse.model_validate(record)


def _mock_service() -> AsyncMock:
    """Create a mock VehicleService."""
    return AsyncMock(spec=VehicleService)


def test_list_vehicles_200():
    mock_svc = _mock_service()
    resp1 = _make_vehicle_response(1, fleet_number="4521")
    resp2 = _make_vehicle_response(2, fleet_number="4522")

    mock_svc.list_vehicles = AsyncMock(
        return_value=PaginatedResponse[VehicleResponse](
            items=[resp1, resp2], total=2, page=1, page_size=20
        )
    )
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.get("/api/v1/vehicles/")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_list_vehicles_with_filters():
    mock_svc = _mock_service()
    mock_svc.list_vehicles = AsyncMock(
        return_value=PaginatedResponse[VehicleResponse](items=[], total=0, page=1, page_size=20)
    )
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.get("/api/v1/vehicles/?search=Solaris&status=active&vehicle_type=bus")
        assert response.status_code == 200
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_get_vehicle_200():
    mock_svc = _mock_service()
    resp = _make_vehicle_response(1, fleet_number="4521")
    mock_svc.get_vehicle = AsyncMock(return_value=resp)
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.get("/api/v1/vehicles/1")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        assert data["fleet_number"] == "4521"
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_get_vehicle_404():
    mock_svc = _mock_service()
    mock_svc.get_vehicle = AsyncMock(side_effect=VehicleNotFoundError(999))
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.get("/api/v1/vehicles/999")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_create_vehicle_201():
    mock_svc = _mock_service()
    resp = _make_vehicle_response(10, fleet_number="4530", license_plate="CD-5678")
    mock_svc.create_vehicle = AsyncMock(return_value=resp)
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/vehicles/",
            json={
                "fleet_number": "4530",
                "vehicle_type": "bus",
                "license_plate": "CD-5678",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["fleet_number"] == "4530"
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_create_vehicle_422_duplicate():
    mock_svc = _mock_service()
    mock_svc.create_vehicle = AsyncMock(side_effect=VehicleAlreadyExistsError("4521"))
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/vehicles/",
            json={
                "fleet_number": "4521",
                "vehicle_type": "bus",
                "license_plate": "AB-1234",
            },
        )
        assert response.status_code == 422
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_update_vehicle_200():
    mock_svc = _mock_service()
    resp = _make_vehicle_response(1, license_plate="NEW-1234")
    mock_svc.update_vehicle = AsyncMock(return_value=resp)
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.patch(
            "/api/v1/vehicles/1",
            json={"license_plate": "NEW-1234"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["license_plate"] == "NEW-1234"
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_update_vehicle_404():
    mock_svc = _mock_service()
    mock_svc.update_vehicle = AsyncMock(side_effect=VehicleNotFoundError(999))
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.patch(
            "/api/v1/vehicles/999",
            json={"license_plate": "NEW-1234"},
        )
        assert response.status_code == 404
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_delete_vehicle_204():
    mock_svc = _mock_service()
    mock_svc.delete_vehicle = AsyncMock()
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.delete("/api/v1/vehicles/1")
        assert response.status_code == 204
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_delete_vehicle_404():
    mock_svc = _mock_service()
    mock_svc.delete_vehicle = AsyncMock(side_effect=VehicleNotFoundError(999))
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.delete("/api/v1/vehicles/999")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_assign_driver_200():
    mock_svc = _mock_service()
    resp = _make_vehicle_response(1, current_driver_id=5)
    mock_svc.assign_driver = AsyncMock(return_value=resp)
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.post("/api/v1/vehicles/1/assign-driver?driver_id=5")
        assert response.status_code == 200
        data = response.json()
        assert data["current_driver_id"] == 5
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_assign_driver_unassign():
    mock_svc = _mock_service()
    resp = _make_vehicle_response(1, current_driver_id=None)
    mock_svc.assign_driver = AsyncMock(return_value=resp)
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.post("/api/v1/vehicles/1/assign-driver")
        assert response.status_code == 200
        data = response.json()
        assert data["current_driver_id"] is None
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_create_maintenance_201():
    mock_svc = _mock_service()
    resp = _make_maintenance_response(1, vehicle_id=1)
    mock_svc.add_maintenance_record = AsyncMock(return_value=resp)
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/vehicles/1/maintenance",
            json={
                "maintenance_type": "scheduled",
                "description": "Oil change",
                "performed_date": str(datetime.datetime.now(tz=datetime.UTC).date()),
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["vehicle_id"] == 1
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_get_maintenance_history_200():
    mock_svc = _mock_service()
    resp1 = _make_maintenance_response(1, vehicle_id=1)

    mock_svc.get_maintenance_history = AsyncMock(
        return_value=PaginatedResponse[MaintenanceRecordResponse](
            items=[resp1], total=1, page=1, page_size=20
        )
    )
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.get("/api/v1/vehicles/1/maintenance")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
    finally:
        app.dependency_overrides.pop(get_service, None)
