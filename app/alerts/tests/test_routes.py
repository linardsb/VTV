# pyright: reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Unit tests for alert REST API routes."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.alerts.exceptions import AlertNotFoundError, AlertRuleNotFoundError
from app.alerts.routes import get_service
from app.alerts.schemas import (
    AlertInstanceResponse,
    AlertRuleResponse,
    AlertSummaryResponse,
)
from app.alerts.service import AlertService
from app.alerts.tests.conftest import make_alert_instance, make_alert_rule
from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.core.rate_limit import limiter
from app.main import app
from app.shared.schemas import PaginatedResponse

limiter.enabled = False


def _mock_user(role: str = "admin") -> User:
    """Return a mock user with specified role."""
    user = MagicMock(spec=User)
    user.id = 1
    user.email = "admin@vtv.lv"
    user.name = "Admin"
    user.role = role
    user.is_active = True
    return user


@pytest.fixture(autouse=True)
def _setup_auth_override() -> Generator[None, None, None]:
    """Ensure auth override is set before each test and restored after."""
    app.dependency_overrides[get_current_user] = lambda: _mock_user("admin")
    yield
    app.dependency_overrides.pop(get_current_user, None)


def _mock_service() -> AsyncMock:
    """Create a mock AlertService."""
    return AsyncMock(spec=AlertService)


def _make_rule_response(rule_id: int = 1, **overrides: object) -> AlertRuleResponse:
    rule = make_alert_rule(id=rule_id, **overrides)
    return AlertRuleResponse.model_validate(rule)


def _make_alert_response(alert_id: int = 1, **overrides: object) -> AlertInstanceResponse:
    alert = make_alert_instance(id=alert_id, **overrides)
    return AlertInstanceResponse.model_validate(alert)


# --- RBAC tests ---


def test_list_alerts_requires_auth():
    """No auth token -> 401/403."""
    app.dependency_overrides.pop(get_current_user, None)
    client = TestClient(app)
    response = client.get("/api/v1/alerts/")
    assert response.status_code in (401, 403)


def test_list_rules_requires_admin():
    """Dispatcher cannot access rules."""
    app.dependency_overrides[get_current_user] = lambda: _mock_user("dispatcher")
    mock_svc = _mock_service()
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.get("/api/v1/alerts/rules")
        assert response.status_code == 403
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_summary_allows_all_roles():
    """Viewer can access summary."""
    app.dependency_overrides[get_current_user] = lambda: _mock_user("viewer")
    mock_svc = _mock_service()
    mock_svc.get_summary = AsyncMock(
        return_value=AlertSummaryResponse(
            total_active=0, critical=0, high=0, medium=0, low=0, info=0
        )
    )
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.get("/api/v1/alerts/summary")
        assert response.status_code == 200
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_create_alert_requires_dispatcher():
    """Viewer cannot create alerts."""
    app.dependency_overrides[get_current_user] = lambda: _mock_user("viewer")
    mock_svc = _mock_service()
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/alerts/",
            json={
                "title": "Test alert",
                "severity": "high",
                "alert_type": "manual",
            },
        )
        assert response.status_code == 403
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_acknowledge_requires_dispatcher():
    """Viewer cannot acknowledge alerts."""
    app.dependency_overrides[get_current_user] = lambda: _mock_user("viewer")
    mock_svc = _mock_service()
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.post("/api/v1/alerts/1/acknowledge")
        assert response.status_code == 403
    finally:
        app.dependency_overrides.pop(get_service, None)


# --- Happy path tests ---


def test_list_alerts_success():
    mock_svc = _mock_service()
    resp = _make_alert_response(1)
    mock_svc.list_alerts = AsyncMock(
        return_value=PaginatedResponse[AlertInstanceResponse](
            items=[resp], total=1, page=1, page_size=20
        )
    )
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.get("/api/v1/alerts/")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_get_alert_success():
    mock_svc = _mock_service()
    resp = _make_alert_response(1)
    mock_svc.get_alert = AsyncMock(return_value=resp)
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.get("/api/v1/alerts/1")
        assert response.status_code == 200
        assert response.json()["id"] == 1
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_create_alert_success():
    mock_svc = _mock_service()
    resp = _make_alert_response(10)
    mock_svc.create_alert = AsyncMock(return_value=resp)
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/alerts/",
            json={
                "title": "Manual alert",
                "severity": "high",
                "alert_type": "manual",
            },
        )
        assert response.status_code == 201
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_acknowledge_alert_success():
    mock_svc = _mock_service()
    resp = _make_alert_response(1, status="acknowledged")
    mock_svc.acknowledge_alert = AsyncMock(return_value=resp)
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.post("/api/v1/alerts/1/acknowledge")
        assert response.status_code == 200
        assert response.json()["status"] == "acknowledged"
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_resolve_alert_success():
    mock_svc = _mock_service()
    resp = _make_alert_response(1, status="resolved")
    mock_svc.resolve_alert = AsyncMock(return_value=resp)
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.post("/api/v1/alerts/1/resolve")
        assert response.status_code == 200
        assert response.json()["status"] == "resolved"
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_get_summary_success():
    mock_svc = _mock_service()
    mock_svc.get_summary = AsyncMock(
        return_value=AlertSummaryResponse(
            total_active=5, critical=2, high=1, medium=1, low=1, info=0
        )
    )
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.get("/api/v1/alerts/summary")
        assert response.status_code == 200
        data = response.json()
        assert data["total_active"] == 5
        assert data["critical"] == 2
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_list_rules_success():
    mock_svc = _mock_service()
    resp = _make_rule_response(1)
    mock_svc.list_rules = AsyncMock(
        return_value=PaginatedResponse[AlertRuleResponse](
            items=[resp], total=1, page=1, page_size=20
        )
    )
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.get("/api/v1/alerts/rules")
        assert response.status_code == 200
        assert response.json()["total"] == 1
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_create_rule_success():
    mock_svc = _mock_service()
    resp = _make_rule_response(5)
    mock_svc.create_rule = AsyncMock(return_value=resp)
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/alerts/rules",
            json={
                "name": "New Rule",
                "rule_type": "delay_threshold",
                "severity": "high",
                "threshold_config": {"delay_seconds": 600},
            },
        )
        assert response.status_code == 201
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_update_rule_success():
    mock_svc = _mock_service()
    resp = _make_rule_response(1, name="Updated")
    mock_svc.update_rule = AsyncMock(return_value=resp)
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.patch(
            "/api/v1/alerts/rules/1",
            json={"name": "Updated"},
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Updated"
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_delete_rule_success():
    mock_svc = _mock_service()
    mock_svc.delete_rule = AsyncMock()
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.delete("/api/v1/alerts/rules/1")
        assert response.status_code == 204
    finally:
        app.dependency_overrides.pop(get_service, None)


# --- Input validation tests ---


def test_create_rule_empty_name():
    """Empty name -> 422."""
    mock_svc = _mock_service()
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/alerts/rules",
            json={
                "name": "",
                "rule_type": "delay_threshold",
                "severity": "high",
            },
        )
        assert response.status_code == 422
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_get_alert_not_found():
    mock_svc = _mock_service()
    mock_svc.get_alert = AsyncMock(side_effect=AlertNotFoundError("Alert 999 not found"))
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.get("/api/v1/alerts/999")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_get_rule_not_found():
    mock_svc = _mock_service()
    mock_svc.get_rule = AsyncMock(side_effect=AlertRuleNotFoundError("Alert rule 999 not found"))
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.get("/api/v1/alerts/rules/999")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.pop(get_service, None)
