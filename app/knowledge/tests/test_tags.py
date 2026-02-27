# pyright: reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportCallIssue=false, reportArgumentType=false
"""Tests for knowledge base tag endpoints.

Covers: list tags, create tag, delete tag, duplicate tag,
add tags to document, remove tag from document, filter by tag.
"""

from __future__ import annotations

from collections.abc import Generator
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.knowledge.exceptions import DuplicateTagError
from app.knowledge.routes import get_service
from app.knowledge.schemas import (
    DocumentResponse,
    TagListResponse,
    TagResponse,
)
from app.knowledge.service import KnowledgeService
from app.shared.schemas import PaginatedResponse

if TYPE_CHECKING:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = MagicMock()


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
    from app.main import app as _app

    _app.dependency_overrides[get_current_user] = _mock_admin_user
    yield
    _app.dependency_overrides.pop(get_current_user, None)


def _mock_service() -> AsyncMock:
    """Create a mock KnowledgeService."""
    return AsyncMock(spec=KnowledgeService)


def _client() -> tuple[TestClient, FastAPI]:
    """Return a TestClient with rate limiting disabled and auth bypassed."""
    from fastapi.testclient import TestClient

    from app.core.rate_limit import limiter
    from app.main import app

    limiter.enabled = False
    app.dependency_overrides[get_current_user] = _mock_admin_user
    return TestClient(app), app


def _make_doc_response(**overrides: object) -> DocumentResponse:
    """Build a DocumentResponse with sensible defaults."""
    defaults: dict[str, object] = {
        "id": 1,
        "filename": "test.pdf",
        "title": None,
        "description": None,
        "domain": "transit",
        "source_type": "pdf",
        "language": "lv",
        "file_size_bytes": 1024,
        "status": "completed",
        "error_message": None,
        "chunk_count": 5,
        "metadata_json": None,
        "ocr_applied": False,
        "tags": [],
        "created_at": _NOW,
        "updated_at": _NOW,
    }
    defaults.update(overrides)
    return DocumentResponse(**defaults)


# ---------------------------------------------------------------------------
# 1. List tags - empty
# ---------------------------------------------------------------------------


def test_list_tags_empty():
    """GET /tags with no tags should return empty list."""
    mock_svc = _mock_service()
    mock_svc.list_tags = AsyncMock(return_value=TagListResponse(tags=[], total=0))
    client, app = _client()
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        response = client.get("/api/v1/knowledge/tags")
        assert response.status_code == 200
        data = response.json()
        assert data["tags"] == []
        assert data["total"] == 0
    finally:
        app.dependency_overrides.pop(get_service, None)


# ---------------------------------------------------------------------------
# 2. Create tag - success
# ---------------------------------------------------------------------------


def test_create_tag_success():
    """POST /tags should create tag and return 201."""
    tag_resp = TagResponse(id=1, name="transit", created_at=_NOW)
    mock_svc = _mock_service()
    mock_svc.create_tag = AsyncMock(return_value=tag_resp)
    client, app = _client()
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        response = client.post("/api/v1/knowledge/tags", json={"name": "Transit"})
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "transit"
        assert data["id"] == 1
    finally:
        app.dependency_overrides.pop(get_service, None)


# ---------------------------------------------------------------------------
# 3. Create tag - duplicate returns 409
# ---------------------------------------------------------------------------


def test_create_tag_duplicate():
    """POST /tags with existing name should return 409 Conflict."""
    mock_svc = _mock_service()
    mock_svc.create_tag = AsyncMock(side_effect=DuplicateTagError("Tag 'transit' already exists"))
    client, app = _client()
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        response = client.post("/api/v1/knowledge/tags", json={"name": "transit"})
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_service, None)


# ---------------------------------------------------------------------------
# 4. Delete tag - success
# ---------------------------------------------------------------------------


def test_delete_tag_success():
    """DELETE /tags/{id} should return 204."""
    mock_svc = _mock_service()
    mock_svc.delete_tag = AsyncMock(return_value=None)
    client, app = _client()
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        response = client.delete("/api/v1/knowledge/tags/1")
        assert response.status_code == 204
        assert response.content == b""
        mock_svc.delete_tag.assert_awaited_once_with(1)
    finally:
        app.dependency_overrides.pop(get_service, None)


# ---------------------------------------------------------------------------
# 5. Delete tag - not found
# ---------------------------------------------------------------------------


def test_delete_tag_not_found():
    """DELETE /tags/{id} for missing tag should return 404."""
    from app.knowledge.exceptions import TagNotFoundError

    mock_svc = _mock_service()
    mock_svc.delete_tag = AsyncMock(side_effect=TagNotFoundError("Tag 999 not found"))
    client, app = _client()
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        response = client.delete("/api/v1/knowledge/tags/999")
        assert response.status_code == 404
        assert "999" in response.json()["error"]
    finally:
        app.dependency_overrides.pop(get_service, None)


# ---------------------------------------------------------------------------
# 6. Add tags to document
# ---------------------------------------------------------------------------


def test_add_tags_to_document():
    """POST /documents/{id}/tags should add tags and return updated document."""
    tag_resp = TagResponse(id=1, name="transit", created_at=_NOW)
    doc = _make_doc_response(tags=[tag_resp])
    mock_svc = _mock_service()
    mock_svc.add_tags_to_document = AsyncMock(return_value=doc)
    client, app = _client()
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        response = client.post(
            "/api/v1/knowledge/documents/1/tags",
            json={"tag_ids": [1]},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["tags"]) == 1
        assert data["tags"][0]["name"] == "transit"
    finally:
        app.dependency_overrides.pop(get_service, None)


# ---------------------------------------------------------------------------
# 7. Remove tag from document
# ---------------------------------------------------------------------------


def test_remove_tag_from_document():
    """DELETE /documents/{id}/tags/{tag_id} should remove tag."""
    doc = _make_doc_response(tags=[])
    mock_svc = _mock_service()
    mock_svc.remove_tag_from_document = AsyncMock(return_value=doc)
    client, app = _client()
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        response = client.delete("/api/v1/knowledge/documents/1/tags/1")
        assert response.status_code == 200
        data = response.json()
        assert data["tags"] == []
    finally:
        app.dependency_overrides.pop(get_service, None)


# ---------------------------------------------------------------------------
# 8. List documents filtered by tag
# ---------------------------------------------------------------------------


def test_list_documents_by_tag():
    """GET /documents?tag=transit should filter by tag."""
    doc = _make_doc_response()
    mock_svc = _mock_service()
    mock_svc.list_documents = AsyncMock(
        return_value=PaginatedResponse[DocumentResponse](items=[doc], total=1, page=1, page_size=20)
    )
    client, app = _client()
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        response = client.get(
            "/api/v1/knowledge/documents",
            params={"tag": "transit", "page": 1, "page_size": 20},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1

        # Verify tag was passed to service
        call_kwargs = mock_svc.list_documents.call_args
        assert call_kwargs.kwargs["tag"] == "transit"
    finally:
        app.dependency_overrides.pop(get_service, None)
