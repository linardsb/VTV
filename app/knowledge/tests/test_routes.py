# pyright: reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportCallIssue=false, reportArgumentType=false
"""Tests for knowledge base route endpoints.

Covers: upload, list, get, update, delete, download path traversal,
search, filename sanitization, MIME detection, and empty PATCH rejection.
"""

from __future__ import annotations

from collections.abc import Generator
from io import BytesIO
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.knowledge.exceptions import DocumentNotFoundError
from app.knowledge.routes import _detect_source_type, get_service
from app.knowledge.schemas import (
    DocumentResponse,
    DocumentUpdate,
    SearchResponse,
    SearchResult,
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
        "created_at": _NOW,
        "updated_at": _NOW,
    }
    defaults.update(overrides)
    return DocumentResponse(**defaults)


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


# ---------------------------------------------------------------------------
# 1. Upload document - happy path
# ---------------------------------------------------------------------------


def test_upload_document_success():
    """POST /documents with valid file should return 201 with document data."""
    doc = _make_doc_response(id=42, filename="report.pdf")
    mock_svc = _mock_service()
    mock_svc.ingest_document = AsyncMock(return_value=doc)

    client, app = _client()
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        response = client.post(
            "/api/v1/knowledge/documents",
            files={"file": ("report.pdf", BytesIO(b"PDF content"), "application/pdf")},
            data={"domain": "transit", "language": "lv"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["id"] == 42
        assert data["filename"] == "report.pdf"
        mock_svc.ingest_document.assert_awaited_once()

        # Verify the call received the sanitized filename and detected source type
        call_kwargs = mock_svc.ingest_document.call_args
        assert call_kwargs.kwargs["filename"] == "report.pdf"
        assert call_kwargs.kwargs["source_type"] == "pdf"
    finally:
        app.dependency_overrides.pop(get_service, None)


# ---------------------------------------------------------------------------
# 2. Upload exceeds size limit
# ---------------------------------------------------------------------------


async def test_upload_exceeds_size_limit():
    """Route-level streaming check should raise HTTPException 413 for files >50MB.

    Directly invokes the upload_document handler with a mock UploadFile whose
    async reads simulate a stream exceeding the 50MB limit.
    """
    from fastapi import HTTPException

    from app.knowledge.routes import upload_document

    max_upload_size = 50 * 1024 * 1024
    chunk_size = 8192
    chunks_needed = (max_upload_size // chunk_size) + 2

    # Build a mock UploadFile that streams chunks exceeding 50MB
    mock_file = MagicMock()
    mock_file.filename = "big.pdf"
    mock_file.content_type = "application/pdf"
    mock_file.read = AsyncMock(side_effect=[b"x" * chunk_size] * chunks_needed + [b""])

    mock_request = MagicMock()
    mock_svc = _mock_service()

    with pytest.raises(HTTPException) as exc_info:
        await upload_document(
            request=mock_request,
            file=mock_file,
            domain="transit",
            language="lv",
            metadata_json=None,
            title=None,
            description=None,
            service=mock_svc,
        )

    assert exc_info.value.status_code == 413
    assert "50MB" in str(exc_info.value.detail)


# ---------------------------------------------------------------------------
# 3. Upload unsupported MIME type (fix 1.4)
# ---------------------------------------------------------------------------


def test_detect_source_type_known_types():
    """_detect_source_type should map known MIME types correctly."""
    assert _detect_source_type("application/pdf") == "pdf"
    assert _detect_source_type("text/plain") == "text"
    assert _detect_source_type("text/csv") == "csv"
    assert _detect_source_type("text/markdown") == "text"
    assert _detect_source_type("image/png") == "image"
    assert _detect_source_type("image/jpeg") == "image"
    assert _detect_source_type(None) == "text"
    assert (
        _detect_source_type(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        == "docx"
    )
    assert (
        _detect_source_type("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        == "xlsx"
    )


def test_detect_source_type_unknown_returns_unknown():
    """_detect_source_type should return 'unknown' for unrecognized MIME types."""
    assert _detect_source_type("application/octet-stream") == "unknown"
    assert _detect_source_type("application/x-executable") == "unknown"
    assert _detect_source_type("video/mp4") == "unknown"


def test_upload_unsupported_type():
    """POST /documents with unsupported MIME type should return 415."""
    mock_svc = _mock_service()
    client, app = _client()
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        response = client.post(
            "/api/v1/knowledge/documents",
            files={"file": ("virus.exe", BytesIO(b"MZ\x90"), "application/octet-stream")},
            data={"domain": "transit"},
        )
        assert response.status_code == 415
        assert "Unsupported file type" in response.json()["detail"]
        # Service should never be called for unsupported types
        mock_svc.ingest_document.assert_not_awaited()
    finally:
        app.dependency_overrides.pop(get_service, None)


# ---------------------------------------------------------------------------
# 4. List documents with filters
# ---------------------------------------------------------------------------


def test_list_documents_with_filters():
    """GET /documents should pass query params through to service."""
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
            params={"domain": "transit", "status": "completed", "page": 1, "page_size": 20},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1

        # Verify service was called with correct filters
        mock_svc.list_documents.assert_awaited_once()
        call_kwargs = mock_svc.list_documents.call_args
        assert call_kwargs.kwargs["domain"] == "transit"
        assert call_kwargs.kwargs["status"] == "completed"
    finally:
        app.dependency_overrides.pop(get_service, None)


# ---------------------------------------------------------------------------
# 5. Get document not found
# ---------------------------------------------------------------------------


def test_get_document_not_found():
    """GET /documents/{id} for missing document should return 404."""
    mock_svc = _mock_service()
    mock_svc.get_document = AsyncMock(side_effect=DocumentNotFoundError("Document 999 not found"))
    client, app = _client()
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        response = client.get("/api/v1/knowledge/documents/999")
        assert response.status_code == 404
        data = response.json()
        assert "999" in data["error"]
    finally:
        app.dependency_overrides.pop(get_service, None)


# ---------------------------------------------------------------------------
# 6. Delete document - success
# ---------------------------------------------------------------------------


def test_delete_document_success():
    """DELETE /documents/{id} should return 204 with no content."""
    mock_svc = _mock_service()
    mock_svc.delete_document = AsyncMock(return_value=None)
    client, app = _client()
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        response = client.delete("/api/v1/knowledge/documents/1")
        assert response.status_code == 204
        assert response.content == b""
        mock_svc.delete_document.assert_awaited_once_with(1)
    finally:
        app.dependency_overrides.pop(get_service, None)


# ---------------------------------------------------------------------------
# 7. Download - path traversal blocked
# ---------------------------------------------------------------------------


def test_download_document_path_traversal():
    """GET /documents/{id}/download should block paths outside storage root."""
    mock_svc = _mock_service()
    # Return a path that escapes the storage directory
    mock_svc.get_document_file_path = AsyncMock(return_value=("/etc/passwd", "passwd"))
    client, app = _client()
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        with patch("app.core.config.get_settings") as mock_settings:
            mock_settings.return_value.document_storage_path = "/var/data/documents"
            response = client.get("/api/v1/knowledge/documents/1/download")
            # ProcessingError maps to 500 via the global exception handler
            assert response.status_code == 500
    finally:
        app.dependency_overrides.pop(get_service, None)


# ---------------------------------------------------------------------------
# 8. Search documents
# ---------------------------------------------------------------------------


def test_search_documents():
    """POST /search should return search results."""
    mock_svc = _mock_service()
    search_result = SearchResult(
        chunk_content="Riga transit schedule",
        document_id=1,
        document_filename="schedule.pdf",
        domain="transit",
        language="lv",
        chunk_index=0,
        score=0.95,
        metadata_json=None,
    )
    mock_svc.search = AsyncMock(
        return_value=SearchResponse(
            results=[search_result],
            query="transit schedule",
            total_candidates=10,
            reranked=False,
        )
    )
    client, app = _client()
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        response = client.post(
            "/api/v1/knowledge/search",
            json={"query": "transit schedule", "domain": "transit", "limit": 5},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) == 1
        assert data["results"][0]["document_filename"] == "schedule.pdf"
        assert data["query"] == "transit schedule"
        mock_svc.search.assert_awaited_once()
    finally:
        app.dependency_overrides.pop(get_service, None)


# ---------------------------------------------------------------------------
# 9. Upload filename sanitization
# ---------------------------------------------------------------------------


def test_upload_filename_sanitization():
    """Upload should sanitize filenames: strip path components and special chars."""
    doc = _make_doc_response(filename="malicious_script_pdf")
    mock_svc = _mock_service()
    mock_svc.ingest_document = AsyncMock(return_value=doc)
    client, app = _client()
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        # Filename with path traversal and special characters
        response = client.post(
            "/api/v1/knowledge/documents",
            files={
                "file": (
                    "../../etc/malicious<script>.pdf",
                    BytesIO(b"PDF data"),
                    "application/pdf",
                )
            },
            data={"domain": "transit"},
        )
        assert response.status_code == 201
        # Verify the filename was sanitized (special chars replaced with underscores)
        call_kwargs = mock_svc.ingest_document.call_args
        sanitized = call_kwargs.kwargs["filename"]
        # Path components stripped, special chars replaced
        assert "/" not in sanitized
        assert ".." not in sanitized
        assert "<" not in sanitized
        assert ">" not in sanitized
        # Original extension preserved
        assert sanitized.endswith(".pdf")
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_filename_sanitization_dot_prefix():
    """Filenames starting with '.' should be sanitized to 'upload' prefix."""
    doc = _make_doc_response(filename="upload.pdf")
    mock_svc = _mock_service()
    mock_svc.ingest_document = AsyncMock(return_value=doc)
    client, app = _client()
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        response = client.post(
            "/api/v1/knowledge/documents",
            files={"file": (".hidden.pdf", BytesIO(b"PDF data"), "application/pdf")},
            data={"domain": "transit"},
        )
        assert response.status_code == 201
        call_kwargs = mock_svc.ingest_document.call_args
        sanitized = call_kwargs.kwargs["filename"]
        # Dot-prefixed files get 'upload' prefix
        assert not sanitized.startswith(".")
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_filename_sanitization_null_bytes():
    """Null bytes in filenames should be stripped during sanitization."""
    doc = _make_doc_response(filename="test.pdf")
    mock_svc = _mock_service()
    mock_svc.ingest_document = AsyncMock(return_value=doc)
    client, app = _client()
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        response = client.post(
            "/api/v1/knowledge/documents",
            files={
                "file": (
                    "test\x00.pdf",
                    BytesIO(b"PDF data"),
                    "application/pdf",
                )
            },
            data={"domain": "transit"},
        )
        assert response.status_code == 201
        call_kwargs = mock_svc.ingest_document.call_args
        sanitized = call_kwargs.kwargs["filename"]
        assert "\x00" not in sanitized
    finally:
        app.dependency_overrides.pop(get_service, None)


# ---------------------------------------------------------------------------
# 10. Empty PATCH body rejected (fix 1.6)
# ---------------------------------------------------------------------------


def test_empty_update_rejected():
    """DocumentUpdate with no fields should raise ValidationError."""
    with pytest.raises(ValidationError, match=r"(?i)at least one field"):
        DocumentUpdate()


def test_empty_update_explicit_nones_rejected():
    """DocumentUpdate with all explicit Nones should also be rejected."""
    with pytest.raises(ValidationError, match=r"(?i)at least one field"):
        DocumentUpdate(title=None, description=None, domain=None, language=None)


def test_valid_update_accepted():
    """DocumentUpdate with at least one field should succeed."""
    update = DocumentUpdate(title="New Title")
    assert update.title == "New Title"
    assert update.description is None

    update2 = DocumentUpdate(domain="hr")
    assert update2.domain == "hr"
