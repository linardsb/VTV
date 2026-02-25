# pyright: reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Unit tests for agent skills REST API routes."""

from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.core.rate_limit import limiter
from app.main import app
from app.shared.schemas import PaginatedResponse
from app.skills.exceptions import SkillNotFoundError
from app.skills.routes import get_service
from app.skills.schemas import SkillResponse
from app.skills.service import SkillService
from app.skills.tests.conftest import make_skill

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


def _make_response(skill_id: int = 1, **overrides: object) -> SkillResponse:
    """Create a SkillResponse for test assertions."""
    skill = make_skill(id=skill_id, **overrides)
    return SkillResponse.model_validate(skill)


def _mock_service() -> AsyncMock:
    """Create a mock SkillService."""
    return AsyncMock(spec=SkillService)


def test_list_skills():
    mock_svc = _mock_service()
    resp1 = _make_response(1, name="Skill A")
    resp2 = _make_response(2, name="Skill B")

    mock_svc.list_skills = AsyncMock(
        return_value=PaginatedResponse[SkillResponse](
            items=[resp1, resp2], total=2, page=1, page_size=20
        )
    )
    app.dependency_overrides[get_service] = lambda: mock_svc
    app.dependency_overrides[get_current_user] = _mock_admin_user

    try:
        client = TestClient(app)
        response = client.get("/api/v1/skills/")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2
    finally:
        app.dependency_overrides.clear()


def test_get_skill():
    mock_svc = _mock_service()
    resp = _make_response(1, name="Priority System")
    mock_svc.get_skill = AsyncMock(return_value=resp)
    app.dependency_overrides[get_service] = lambda: mock_svc
    app.dependency_overrides[get_current_user] = _mock_admin_user

    try:
        client = TestClient(app)
        response = client.get("/api/v1/skills/1")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        assert data["name"] == "Priority System"
    finally:
        app.dependency_overrides.clear()


def test_get_skill_not_found():
    mock_svc = _mock_service()
    mock_svc.get_skill = AsyncMock(side_effect=SkillNotFoundError("Skill 999 not found"))
    app.dependency_overrides[get_service] = lambda: mock_svc
    app.dependency_overrides[get_current_user] = _mock_admin_user

    try:
        client = TestClient(app)
        response = client.get("/api/v1/skills/999")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_create_skill():
    mock_svc = _mock_service()
    resp = _make_response(10, name="New Skill")
    mock_svc.create_skill = AsyncMock(return_value=resp)
    app.dependency_overrides[get_service] = lambda: mock_svc
    app.dependency_overrides[get_current_user] = _mock_admin_user

    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/skills/",
            json={
                "name": "New Skill",
                "description": "A new skill",
                "content": "Content here",
                "category": "transit_ops",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "New Skill"
    finally:
        app.dependency_overrides.clear()


def test_update_skill():
    mock_svc = _mock_service()
    resp = _make_response(1, name="Updated")
    mock_svc.update_skill = AsyncMock(return_value=resp)
    app.dependency_overrides[get_service] = lambda: mock_svc
    app.dependency_overrides[get_current_user] = _mock_admin_user

    try:
        client = TestClient(app)
        response = client.patch(
            "/api/v1/skills/1",
            json={"name": "Updated"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated"
    finally:
        app.dependency_overrides.clear()


def test_delete_skill():
    mock_svc = _mock_service()
    mock_svc.delete_skill = AsyncMock()
    app.dependency_overrides[get_service] = lambda: mock_svc
    app.dependency_overrides[get_current_user] = _mock_admin_user

    try:
        client = TestClient(app)
        response = client.delete("/api/v1/skills/1")
        assert response.status_code == 204
    finally:
        app.dependency_overrides.clear()


def test_seed_skills():
    mock_svc = _mock_service()
    skills = [make_skill(id=i, name=f"Skill {i}") for i in range(1, 6)]
    mock_svc.seed_default_skills = AsyncMock(return_value=skills)
    app.dependency_overrides[get_service] = lambda: mock_svc
    app.dependency_overrides[get_current_user] = _mock_admin_user

    try:
        client = TestClient(app)
        response = client.post("/api/v1/skills/seed")
        assert response.status_code == 201
        data = response.json()
        assert len(data) == 5
    finally:
        app.dependency_overrides.clear()
