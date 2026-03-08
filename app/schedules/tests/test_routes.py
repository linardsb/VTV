# pyright: reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Unit tests for schedule management REST API routes."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.core.rate_limit import limiter
from app.main import app
from app.schedules.routes import get_service
from app.schedules.schemas import (
    CalendarDateResponse,
    CalendarResponse,
    GTFSImportResponse,
    RouteResponse,
    StopTimeResponse,
    TripDetailResponse,
    TripResponse,
    ValidationResult,
)
from app.schedules.service import ScheduleService
from app.schedules.tests.conftest import (
    make_calendar,
    make_calendar_date,
    make_route,
    make_stop_time,
    make_trip,
)
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


def _mock_service() -> AsyncMock:
    """Create a mock ScheduleService.

    Returns:
        AsyncMock configured as a ScheduleService.
    """
    return AsyncMock(spec=ScheduleService)


# --- Route endpoint tests ---


def test_list_routes_200():
    mock_svc = _mock_service()
    r1 = RouteResponse.model_validate(make_route(id=1))
    r2 = RouteResponse.model_validate(make_route(id=2, gtfs_route_id="trol_14"))

    mock_svc.list_routes = AsyncMock(
        return_value=PaginatedResponse[RouteResponse](items=[r1, r2], total=2, page=1, page_size=20)
    )
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.get("/api/v1/schedules/routes")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_list_routes_filter_is_active():
    mock_svc = _mock_service()
    active_route = RouteResponse.model_validate(make_route(id=1, is_active=True))

    mock_svc.list_routes = AsyncMock(
        return_value=PaginatedResponse[RouteResponse](
            items=[active_route], total=1, page=1, page_size=20
        )
    )
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.get("/api/v1/schedules/routes?is_active=true")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        mock_svc.list_routes.assert_called_once()
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_create_route_201():
    mock_svc = _mock_service()
    route = make_route()
    mock_svc.create_route = AsyncMock(return_value=RouteResponse.model_validate(route))
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/schedules/routes",
            json={
                "gtfs_route_id": "bus_22",
                "agency_id": 1,
                "route_short_name": "22",
                "route_long_name": "Centrs - Jugla",
                "route_type": 3,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["gtfs_route_id"] == "bus_22"
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_get_route_200():
    mock_svc = _mock_service()
    route = make_route()
    mock_svc.get_route = AsyncMock(return_value=RouteResponse.model_validate(route))
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.get("/api/v1/schedules/routes/1")
        assert response.status_code == 200
        assert response.json()["route_short_name"] == "22"
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_update_route_200():
    mock_svc = _mock_service()
    updated = make_route(route_long_name="Updated")
    mock_svc.update_route = AsyncMock(return_value=RouteResponse.model_validate(updated))
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.patch("/api/v1/schedules/routes/1", json={"route_long_name": "Updated"})
        assert response.status_code == 200
        assert response.json()["route_long_name"] == "Updated"
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_delete_route_204():
    mock_svc = _mock_service()
    mock_svc.delete_route = AsyncMock(return_value=None)
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.delete("/api/v1/schedules/routes/1")
        assert response.status_code == 204
    finally:
        app.dependency_overrides.pop(get_service, None)


# --- Calendar endpoint tests ---


def test_list_calendars_200():
    mock_svc = _mock_service()
    c1 = CalendarResponse.model_validate(make_calendar())

    mock_svc.list_calendars = AsyncMock(
        return_value=PaginatedResponse[CalendarResponse](items=[c1], total=1, page=1, page_size=20)
    )
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.get("/api/v1/schedules/calendars")
        assert response.status_code == 200
        assert response.json()["total"] == 1
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_create_calendar_201():
    mock_svc = _mock_service()
    cal = make_calendar()
    mock_svc.create_calendar = AsyncMock(return_value=CalendarResponse.model_validate(cal))
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/schedules/calendars",
            json={
                "gtfs_service_id": "weekday_1",
                "monday": True,
                "tuesday": True,
                "wednesday": True,
                "thursday": True,
                "friday": True,
                "saturday": False,
                "sunday": False,
                "start_date": "2026-01-01",
                "end_date": "2026-12-31",
            },
        )
        assert response.status_code == 201
        assert response.json()["gtfs_service_id"] == "weekday_1"
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_add_exception_201():
    mock_svc = _mock_service()
    cd = make_calendar_date()
    mock_svc.add_calendar_exception = AsyncMock(
        return_value=CalendarDateResponse.model_validate(cd)
    )
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/schedules/calendars/1/exceptions",
            json={"date": "2026-03-15", "exception_type": 2},
        )
        assert response.status_code == 201
        assert response.json()["exception_type"] == 2
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_remove_exception_204():
    mock_svc = _mock_service()
    mock_svc.remove_calendar_exception = AsyncMock(return_value=None)
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.delete("/api/v1/schedules/calendar-exceptions/1")
        assert response.status_code == 204
    finally:
        app.dependency_overrides.pop(get_service, None)


# --- Trip endpoint tests ---


def test_list_trips_200():
    mock_svc = _mock_service()
    t1 = TripResponse.model_validate(make_trip())

    mock_svc.list_trips = AsyncMock(
        return_value=PaginatedResponse[TripResponse](items=[t1], total=1, page=1, page_size=20)
    )
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.get("/api/v1/schedules/trips")
        assert response.status_code == 200
        assert response.json()["total"] == 1
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_create_trip_201():
    mock_svc = _mock_service()
    trip = make_trip()
    mock_svc.create_trip = AsyncMock(return_value=TripResponse.model_validate(trip))
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/schedules/trips",
            json={
                "gtfs_trip_id": "trip_22_1",
                "route_id": 1,
                "calendar_id": 1,
                "direction_id": 0,
                "trip_headsign": "Jugla",
            },
        )
        assert response.status_code == 201
        assert response.json()["gtfs_trip_id"] == "trip_22_1"
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_get_trip_with_stop_times_200():
    mock_svc = _mock_service()
    trip = make_trip()
    st1 = StopTimeResponse.model_validate(make_stop_time(id=1, stop_sequence=1))
    st2 = StopTimeResponse.model_validate(make_stop_time(id=2, stop_sequence=2, stop_id=2))
    trip_data = TripResponse.model_validate(trip)
    detail = TripDetailResponse(**trip_data.model_dump(), stop_times=[st1, st2])

    mock_svc.get_trip = AsyncMock(return_value=detail)
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.get("/api/v1/schedules/trips/1")
        assert response.status_code == 200
        data = response.json()
        assert data["gtfs_trip_id"] == "trip_22_1"
        assert len(data["stop_times"]) == 2
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_replace_stop_times_200():
    mock_svc = _mock_service()
    st1 = StopTimeResponse.model_validate(make_stop_time(id=10, stop_sequence=1))
    st2 = StopTimeResponse.model_validate(make_stop_time(id=11, stop_sequence=2, stop_id=2))

    mock_svc.replace_stop_times = AsyncMock(return_value=[st1, st2])
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.put(
            "/api/v1/schedules/trips/1/stop-times",
            json={
                "stop_times": [
                    {
                        "stop_id": 1,
                        "stop_sequence": 1,
                        "arrival_time": "08:00:00",
                        "departure_time": "08:01:00",
                    },
                    {
                        "stop_id": 2,
                        "stop_sequence": 2,
                        "arrival_time": "08:05:00",
                        "departure_time": "08:06:00",
                    },
                ]
            },
        )
        assert response.status_code == 200
        assert len(response.json()) == 2
    finally:
        app.dependency_overrides.pop(get_service, None)


# --- Import endpoint test ---


def test_import_gtfs_200():
    mock_svc = _mock_service()
    mock_svc.import_gtfs = AsyncMock(
        return_value=GTFSImportResponse(
            feed_id="riga",
            agencies_count=1,
            agencies_created=1,
            agencies_updated=0,
            routes_count=5,
            routes_created=3,
            routes_updated=2,
            calendars_count=2,
            calendars_created=2,
            calendars_updated=0,
            calendar_dates_count=3,
            trips_count=10,
            trips_created=8,
            trips_updated=2,
            stop_times_count=100,
            stops_count=50,
            stops_created=40,
            stops_updated=10,
            skipped_stop_times=2,
            warnings=["stop_times.txt: Skipped 2 with unknown stop"],
        )
    )
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/schedules/import",
            files={"file": ("gtfs.zip", b"fake_zip_content", "application/zip")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["agencies_count"] == 1
        assert data["agencies_created"] == 1
        assert data["agencies_updated"] == 0
        assert data["routes_count"] == 5
        assert data["routes_created"] == 3
        assert data["routes_updated"] == 2
        assert data["stops_count"] == 50
        assert data["stops_created"] == 40
    finally:
        app.dependency_overrides.pop(get_service, None)


# --- Validation endpoint test ---


def test_validate_200():
    mock_svc = _mock_service()
    mock_svc.validate_schedule = AsyncMock(
        return_value=ValidationResult(valid=True, errors=[], warnings=[])
    )
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.post("/api/v1/schedules/validate")
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["errors"] == []
    finally:
        app.dependency_overrides.pop(get_service, None)
