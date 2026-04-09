# pyright: reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Unit tests for memory API routes."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.core.rate_limit import limiter
from app.main import app
from app.memory.routes import get_service
from app.memory.schemas import CompactionResult, MemoryEntryResponse, MemoryRecallResponse
from app.memory.service import MemoryService
from app.memory.tests.conftest import make_embedding, make_memory
from app.shared.models import utcnow

limiter.enabled = False


def _mock_admin_user() -> User:
    user = MagicMock(spec=User)
    user.id = 1
    user.email = "admin@vtv.lv"
    user.role = "admin"
    user.is_active = True
    return user


@pytest.fixture(autouse=True)
def _setup_auth_override() -> Generator[None, None, None]:
    app.dependency_overrides[get_current_user] = _mock_admin_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


def _mock_service() -> AsyncMock:
    return AsyncMock(spec=MemoryService)


def _make_response(entry_id: int = 1) -> MemoryEntryResponse:
    now = utcnow()
    return MemoryEntryResponse(
        id=entry_id,
        agent_type="transit",
        memory_type="semantic",
        content="Test memory",
        metadata_json=None,
        decay_weight=1.0,
        is_evergreen=False,
        source="agent",
        recalled_count=0,
        created_at=now,
        updated_at=now,
    )


def test_store_memory_201():
    mock_svc = _mock_service()
    entry = make_memory(id=10)
    mock_svc.store.return_value = entry
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/memory/",
            json={
                "agent_type": "transit",
                "memory_type": "semantic",
                "content": "Test memory",
                "source": "agent",
            },
        )
        assert response.status_code == 201
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_get_memory():
    mock_svc = _mock_service()
    entry = make_memory(id=42)
    mock_svc.get.return_value = entry
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.get("/api/v1/memory/42")
        assert response.status_code == 200
        assert response.json()["id"] == 42
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_recall_accepts_post():
    mock_svc = _mock_service()
    resp = _make_response(1)
    mock_svc.recall.return_value = [
        MemoryRecallResponse(memory=resp, score=0.95),
    ]
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/memory/recall",
            json={
                "embedding": make_embedding(),
                "limit": 5,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["score"] == pytest.approx(0.95)
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_list_by_type_validates_literal():
    mock_svc = _mock_service()
    entries = [make_memory(id=1), make_memory(id=2)]
    mock_svc.get_by_type.return_value = entries
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.get("/api/v1/memory/type/semantic")
        assert response.status_code == 200
        assert len(response.json()) == 2
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_list_by_type_rejects_invalid_type():
    client = TestClient(app)
    response = client.get("/api/v1/memory/type/invalid_type")
    assert response.status_code == 422


def test_delete_decayed_admin_only():
    mock_svc = _mock_service()
    mock_svc.delete_decayed.return_value = 3
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.delete("/api/v1/memory/decayed")
        assert response.status_code == 200
        assert response.json()["deleted_count"] == 3
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_recall_rejects_wrong_embedding_length():
    client = TestClient(app)
    response = client.post(
        "/api/v1/memory/recall",
        json={
            "embedding": [0.1] * 512,  # wrong length
            "limit": 5,
        },
    )
    assert response.status_code == 422


def test_compact_returns_result():
    mock_svc = _mock_service()
    mock_svc.compact.return_value = CompactionResult(decayed_deleted=2, merged=1, promoted=3)
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.post("/api/v1/memory/compact")
        assert response.status_code == 200
        data = response.json()
        assert data["decayed_deleted"] == 2
        assert data["merged"] == 1
        assert data["promoted"] == 3
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_compact_requires_admin():
    """Non-admin users should not be able to trigger compaction."""

    # Override with a non-admin user
    def _mock_agent_user() -> User:
        user = MagicMock(spec=User)
        user.id = 2
        user.email = "agent@vtv.lv"
        user.role = "agent"
        user.is_active = True
        return user

    app.dependency_overrides[get_current_user] = _mock_agent_user
    try:
        client = TestClient(app)
        response = client.post("/api/v1/memory/compact")
        assert response.status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_recall_by_query_returns_results():
    mock_svc = _mock_service()
    resp = _make_response(1)
    mock_svc.recall_by_query.return_value = [
        MemoryRecallResponse(memory=resp, score=0.88),
    ]
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/memory/recall/query",
            json={"query": "route 5 delays", "limit": 5},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["score"] == pytest.approx(0.88)
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_recall_by_query_validates_max_length():
    client = TestClient(app)
    response = client.post(
        "/api/v1/memory/recall/query",
        json={"query": "x" * 2001},
    )
    assert response.status_code == 422
