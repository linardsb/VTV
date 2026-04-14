# pyright: reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportCallIssue=false, reportArgumentType=false
"""KB-3 Document Versioning tests.

Covers ingest-time version detection, diff generation, version history,
and include_superseded flag propagation on search + list endpoints. All
tests use mocks for repositories and services — no database required.
"""

from __future__ import annotations

from collections.abc import Generator
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.auth.dependencies import get_current_user
from app.knowledge.exceptions import (
    DocumentNotFoundError,
    DocumentVersionConflictError,
)
from app.knowledge.routes import get_service
from app.knowledge.schemas import (
    DocumentDiffResponse,
    DocumentUpload,
    DocumentVersionItem,
    SearchResponse,
)
from app.knowledge.tests.test_routes import (
    _client,
    _make_doc_response,
    _mock_admin_user,
    _mock_service,
)
from app.shared.models import utcnow

if TYPE_CHECKING:
    from app.knowledge.models import Document


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _setup_auth_override() -> Generator[None, None, None]:
    """Ensure dependency overrides don't leak between tests (anti-pattern #56)."""
    from app.main import app as _app

    _app.dependency_overrides[get_current_user] = _mock_admin_user
    yield
    _app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_document(**overrides: object) -> Document:
    """Factory for Document ORM instances with sensible defaults."""
    from app.knowledge.models import Document

    now = utcnow()
    defaults: dict[str, object] = {
        "id": 1,
        "filename": "sop.pdf",
        "title": "SOP-001",
        "description": None,
        "file_path": "/data/documents/1/sop.pdf",
        "domain": "transit",
        "source_type": "pdf",
        "language": "lv",
        "file_size_bytes": 1024,
        "status": "completed",
        "error_message": None,
        "chunk_count": 3,
        "metadata_json": None,
        "ocr_applied": False,
        "evergreen": False,
        "version": 1,
        "parent_document_id": None,
        "is_latest": True,
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    return Document(**defaults)


def _make_chunk(content: str, chunk_index: int, document_id: int = 1) -> MagicMock:
    """Lightweight mock chunk with the fields `_concatenate_chunks` needs."""
    chunk = MagicMock()
    chunk.content = content
    chunk.chunk_index = chunk_index
    chunk.document_id = document_id
    return chunk


# ---------------------------------------------------------------------------
# 1. Version creation (v1)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ingest_first_upload_creates_v1() -> None:
    """A brand-new (title, domain) uploads as version=1 with no parent."""
    from app.knowledge.service import KnowledgeService

    service = KnowledgeService.__new__(KnowledgeService)
    service.db = AsyncMock()
    service.repository = AsyncMock()

    service.repository.get_latest_by_title_domain = AsyncMock(return_value=None)
    created_doc = _make_document(id=10, title="SOP-001", version=1, parent_document_id=None)
    service.repository.create_document = AsyncMock(return_value=created_doc)
    # Stub downstream ingest pipeline — we only care about the version metadata.
    service._chunk_embed_store = AsyncMock(return_value=0)  # type: ignore[method-assign]
    service.get_document = AsyncMock(return_value=_make_doc_response(id=10, title="SOP-001"))  # type: ignore[method-assign]
    service._auto_tag_document = AsyncMock(return_value=None)  # type: ignore[method-assign]
    service.repository.update_document_status = AsyncMock()
    service.repository.update_document_file_path = AsyncMock()

    # Bypass file I/O: patch shutil.copy2 and Path operations via extraction stub
    from unittest.mock import patch

    with (
        patch(
            "app.knowledge.service.processing.extract_text", AsyncMock(return_value=("text", False))
        ),
        patch("app.knowledge.service.shutil.copy2"),
        patch("app.knowledge.service.Path") as mock_path,
    ):
        mock_path.return_value = MagicMock()
        mock_path.return_value.resolve.return_value.is_relative_to.return_value = True
        mock_path.return_value.stem = "sop"

        await service.ingest_document(
            file_path="fake_src.pdf",
            upload=DocumentUpload(domain="transit", language="lv", title="SOP-001"),
            filename="sop.pdf",
            source_type="pdf",
            file_size=1024,
        )

    # Verify create_document called with version=1, parent_document_id=None
    service.repository.create_document.assert_awaited_once()
    create_kwargs = service.repository.create_document.call_args.kwargs
    assert create_kwargs["version"] == 1
    assert create_kwargs["parent_document_id"] is None
    assert create_kwargs["is_latest"] is True
    # No prior to supersede
    service.repository.mark_superseded.assert_not_called()


@pytest.mark.asyncio
async def test_ingest_same_title_increments_to_v2_and_sets_parent() -> None:
    """Re-upload with the same (title, domain) creates v2 pointing to v1."""
    from app.knowledge.service import KnowledgeService

    service = KnowledgeService.__new__(KnowledgeService)
    service.db = AsyncMock()
    service.repository = AsyncMock()

    existing_v1 = _make_document(id=7, title="SOP-001", version=1, parent_document_id=None)
    service.repository.get_latest_by_title_domain = AsyncMock(return_value=existing_v1)
    service.repository.mark_superseded = AsyncMock()
    created_v2 = _make_document(id=8, title="SOP-001", version=2, parent_document_id=7)
    service.repository.create_document = AsyncMock(return_value=created_v2)
    service._chunk_embed_store = AsyncMock(return_value=0)  # type: ignore[method-assign]
    service.get_document = AsyncMock(return_value=_make_doc_response(id=8, title="SOP-001"))  # type: ignore[method-assign]
    service._auto_tag_document = AsyncMock(return_value=None)  # type: ignore[method-assign]
    service.repository.update_document_status = AsyncMock()
    service.repository.update_document_file_path = AsyncMock()

    from unittest.mock import patch

    with (
        patch(
            "app.knowledge.service.processing.extract_text", AsyncMock(return_value=("text", False))
        ),
        patch("app.knowledge.service.shutil.copy2"),
        patch("app.knowledge.service.Path") as mock_path,
    ):
        mock_path.return_value = MagicMock()
        mock_path.return_value.resolve.return_value.is_relative_to.return_value = True
        mock_path.return_value.stem = "sop"

        await service.ingest_document(
            file_path="fake_src.pdf",
            upload=DocumentUpload(domain="transit", language="lv", title="SOP-001"),
            filename="sop.pdf",
            source_type="pdf",
            file_size=1024,
        )

    create_kwargs = service.repository.create_document.call_args.kwargs
    assert create_kwargs["version"] == 2
    assert create_kwargs["parent_document_id"] == 7
    assert create_kwargs["is_latest"] is True


# ---------------------------------------------------------------------------
# 2. Superseded marking
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ingest_marks_previous_as_superseded() -> None:
    """When v2 is created, repository.mark_superseded(v1.id) is called exactly once."""
    from app.knowledge.service import KnowledgeService

    service = KnowledgeService.__new__(KnowledgeService)
    service.db = AsyncMock()
    service.repository = AsyncMock()

    existing_v1 = _make_document(id=42, title="SOP-001", version=1)
    service.repository.get_latest_by_title_domain = AsyncMock(return_value=existing_v1)
    service.repository.mark_superseded = AsyncMock()
    service.repository.create_document = AsyncMock(
        return_value=_make_document(id=43, version=2, parent_document_id=42)
    )
    service._chunk_embed_store = AsyncMock(return_value=0)  # type: ignore[method-assign]
    service.get_document = AsyncMock(return_value=_make_doc_response(id=43))  # type: ignore[method-assign]
    service._auto_tag_document = AsyncMock(return_value=None)  # type: ignore[method-assign]
    service.repository.update_document_status = AsyncMock()
    service.repository.update_document_file_path = AsyncMock()

    from unittest.mock import patch

    with (
        patch(
            "app.knowledge.service.processing.extract_text", AsyncMock(return_value=("t", False))
        ),
        patch("app.knowledge.service.shutil.copy2"),
        patch("app.knowledge.service.Path") as mock_path,
    ):
        mock_path.return_value = MagicMock()
        mock_path.return_value.resolve.return_value.is_relative_to.return_value = True
        mock_path.return_value.stem = "sop"

        await service.ingest_document(
            file_path="fake_src.pdf",
            upload=DocumentUpload(domain="transit", language="lv", title="SOP-001"),
            filename="sop.pdf",
            source_type="pdf",
            file_size=1024,
        )

    service.repository.mark_superseded.assert_awaited_once_with(42)


# ---------------------------------------------------------------------------
# 3. Diff generation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_document_diff_returns_unified_diff() -> None:
    """Diff between two known chunk sets produces expected +/- lines counts."""
    from app.knowledge.service import KnowledgeService

    service = KnowledgeService.__new__(KnowledgeService)
    service.db = AsyncMock()
    service.repository = AsyncMock()

    v1 = _make_document(id=1, version=1, parent_document_id=None)
    v2 = _make_document(id=2, version=2, parent_document_id=1)
    service.repository.list_versions = AsyncMock(return_value=[v2, v1])
    # v1 text: two lines. v2: first line modified, second same, third added.
    service.repository.get_chunks_by_document = AsyncMock(
        side_effect=[
            [_make_chunk("line 1 old", 0, 1), _make_chunk("line 2 same", 1, 1)],
            [
                _make_chunk("line 1 NEW", 0, 2),
                _make_chunk("line 2 same", 1, 2),
                _make_chunk("line 3 added", 2, 2),
            ],
        ]
    )

    resp = await service.get_document_diff(document_id=2, v1=1, v2=2)
    assert isinstance(resp, DocumentDiffResponse)
    assert resp.v1 == 1 and resp.v2 == 2
    assert resp.v1_document_id == 1 and resp.v2_document_id == 2
    assert resp.lines_added >= 2  # "line 1 NEW" + "line 3 added"
    assert resp.lines_removed >= 1  # "line 1 old"
    assert "line 1 NEW" in resp.unified_diff
    assert "line 1 old" in resp.unified_diff


@pytest.mark.asyncio
async def test_get_document_diff_rejects_same_version() -> None:
    """v1 == v2 raises DocumentVersionConflictError (-> 422)."""
    from app.knowledge.service import KnowledgeService

    service = KnowledgeService.__new__(KnowledgeService)
    service.db = AsyncMock()
    service.repository = AsyncMock()

    with pytest.raises(DocumentVersionConflictError):
        await service.get_document_diff(document_id=1, v1=2, v2=2)


# ---------------------------------------------------------------------------
# 4. Search latest-only (default)
# ---------------------------------------------------------------------------


def test_search_defaults_to_latest_only() -> None:
    """POST /search without include_superseded forwards False to the service."""
    mock_svc = _mock_service()
    mock_svc.search = AsyncMock(
        return_value=SearchResponse(results=[], query="q", total_candidates=0, reranked=False)
    )
    client, app = _client()
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        response = client.post(
            "/api/v1/knowledge/search",
            json={"query": "procedure"},
        )
        assert response.status_code == 200
        mock_svc.search.assert_awaited_once()
        req = mock_svc.search.call_args.args[0]
        assert req.include_superseded is False
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_list_documents_defaults_to_latest_only() -> None:
    """GET /documents forwards include_superseded=False by default."""
    from app.knowledge.schemas import DocumentResponse
    from app.shared.schemas import PaginatedResponse

    mock_svc = _mock_service()
    mock_svc.list_documents = AsyncMock(
        return_value=PaginatedResponse[DocumentResponse](items=[], total=0, page=1, page_size=20)
    )
    client, app = _client()
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        response = client.get("/api/v1/knowledge/documents")
        assert response.status_code == 200
        mock_svc.list_documents.assert_awaited_once()
        assert mock_svc.list_documents.call_args.kwargs["include_superseded"] is False
    finally:
        app.dependency_overrides.pop(get_service, None)


# ---------------------------------------------------------------------------
# 5. Search with superseded
# ---------------------------------------------------------------------------


def test_search_with_include_superseded_returns_all() -> None:
    """POST /search with include_superseded=true forwards through to the service."""
    mock_svc = _mock_service()
    mock_svc.search = AsyncMock(
        return_value=SearchResponse(results=[], query="q", total_candidates=0, reranked=False)
    )
    client, app = _client()
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        response = client.post(
            "/api/v1/knowledge/search",
            json={"query": "procedure", "include_superseded": True},
        )
        assert response.status_code == 200
        req = mock_svc.search.call_args.args[0]
        assert req.include_superseded is True
    finally:
        app.dependency_overrides.pop(get_service, None)


# ---------------------------------------------------------------------------
# 6. Version history endpoint
# ---------------------------------------------------------------------------


def test_get_document_versions_returns_descending_chain() -> None:
    """GET /documents/{id}/versions returns v2, v1 (newest first)."""
    now = utcnow()
    items = [
        DocumentVersionItem(
            id=2,
            version=2,
            status="completed",
            is_latest=True,
            parent_document_id=1,
            filename="sop.pdf",
            file_size_bytes=2048,
            chunk_count=4,
            created_at=now,
        ),
        DocumentVersionItem(
            id=1,
            version=1,
            status="superseded",
            is_latest=False,
            parent_document_id=None,
            filename="sop.pdf",
            file_size_bytes=1024,
            chunk_count=3,
            created_at=now,
        ),
    ]
    mock_svc = _mock_service()
    mock_svc.get_document_versions = AsyncMock(return_value=items)
    client, app = _client()
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        response = client.get("/api/v1/knowledge/documents/2/versions")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["version"] == 2 and data[0]["is_latest"] is True
        assert data[1]["version"] == 1 and data[1]["is_latest"] is False
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_get_document_versions_404_for_unknown_id() -> None:
    """Unknown document_id -> 404 from DocumentNotFoundError."""
    mock_svc = _mock_service()
    mock_svc.get_document_versions = AsyncMock(
        side_effect=DocumentNotFoundError("Document 999 not found")
    )
    client, app = _client()
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        response = client.get("/api/v1/knowledge/documents/999/versions")
        assert response.status_code == 404
        assert "999" in response.json()["error"]
    finally:
        app.dependency_overrides.pop(get_service, None)
