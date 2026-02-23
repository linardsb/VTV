# pyright: reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportCallIssue=false, reportArgumentType=false
"""Integration tests for knowledge repository."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.knowledge.models import Document, DocumentChunk
from app.knowledge.repository import KnowledgeRepository
from app.shared.models import utcnow


def make_document(**overrides: object) -> Document:
    """Factory for Document instances with sensible defaults."""
    now = utcnow()
    defaults = {
        "id": 1,
        "filename": "test.pdf",
        "title": "Test Document",
        "description": None,
        "file_path": "/data/documents/1/test.pdf",
        "domain": "transit",
        "source_type": "pdf",
        "language": "lv",
        "file_size_bytes": 1024,
        "status": "completed",
        "error_message": None,
        "chunk_count": 3,
        "metadata_json": None,
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    return Document(**defaults)


def make_chunk(**overrides: object) -> DocumentChunk:
    """Factory for DocumentChunk instances with sensible defaults."""
    now = utcnow()
    defaults = {
        "id": 1,
        "document_id": 1,
        "content": "Sample chunk text",
        "chunk_index": 0,
        "embedding": None,
        "metadata_json": None,
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    return DocumentChunk(**defaults)


@pytest.fixture
def mock_db() -> AsyncMock:
    """Provide a mock async database session."""
    return AsyncMock()


@pytest.fixture
def repo(mock_db: AsyncMock) -> KnowledgeRepository:
    """Provide a KnowledgeRepository with mocked DB session."""
    return KnowledgeRepository(mock_db)


# --- Test 1: Create and get document round-trip ---


@pytest.mark.asyncio
@pytest.mark.integration
async def test_create_and_get_document(repo: KnowledgeRepository, mock_db: AsyncMock) -> None:
    """Create a document then retrieve it by ID, verifying field round-trip."""
    doc = make_document(id=7, filename="routes.pdf", domain="transit")

    # Mock commit and refresh for create_document
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()
    mock_db.add = MagicMock()

    # Capture what gets added and return it via refresh
    async def fake_refresh(obj):
        obj.id = 7

    mock_db.refresh.side_effect = fake_refresh

    created = await repo.create_document(
        filename="routes.pdf",
        domain="transit",
        source_type="pdf",
        language="lv",
        file_size_bytes=2048,
        metadata_json=None,
        title="Route Guide",
        description="All city routes",
    )

    mock_db.add.assert_called_once()
    mock_db.commit.assert_awaited_once()
    mock_db.refresh.assert_awaited_once()
    assert created.filename == "routes.pdf"
    assert created.domain == "transit"

    # Now mock get_document
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = doc
    mock_db.execute = AsyncMock(return_value=mock_result)

    fetched = await repo.get_document(7)
    assert fetched is not None
    assert fetched.id == 7
    assert fetched.filename == "routes.pdf"
    assert fetched.domain == "transit"


# --- Test 2: List documents with pagination ---


@pytest.mark.asyncio
@pytest.mark.integration
async def test_list_documents_pagination(repo: KnowledgeRepository, mock_db: AsyncMock) -> None:
    """List documents should respect offset and limit parameters."""
    docs = [make_document(id=i, filename=f"doc_{i}.pdf") for i in range(1, 6)]

    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = docs[:2]
    mock_result.scalars.return_value = mock_scalars
    mock_db.execute = AsyncMock(return_value=mock_result)

    result = await repo.list_documents(offset=0, limit=2)
    assert len(result) == 2
    mock_db.execute.assert_awaited_once()

    # Second page
    mock_scalars.all.return_value = docs[2:4]
    mock_db.execute = AsyncMock(return_value=mock_result)

    result = await repo.list_documents(offset=2, limit=2)
    assert len(result) == 2
    assert result[0].id == 3


# --- Test 3: List documents with domain and status filters ---


@pytest.mark.asyncio
@pytest.mark.integration
async def test_list_documents_filters(repo: KnowledgeRepository, mock_db: AsyncMock) -> None:
    """List documents should filter by domain and status."""
    transit_docs = [make_document(id=1, domain="transit", status="completed")]

    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = transit_docs
    mock_result.scalars.return_value = mock_scalars
    mock_db.execute = AsyncMock(return_value=mock_result)

    result = await repo.list_documents(domain="transit", status="completed")
    assert len(result) == 1
    assert result[0].domain == "transit"
    assert result[0].status == "completed"
    mock_db.execute.assert_awaited_once()

    # Filter by language too
    mock_db.execute = AsyncMock(return_value=mock_result)
    result = await repo.list_documents(domain="transit", language="lv")
    assert len(result) == 1


# --- Test 4: Update document status transitions ---


@pytest.mark.asyncio
@pytest.mark.integration
async def test_update_document_status(repo: KnowledgeRepository, mock_db: AsyncMock) -> None:
    """Update status should transition document through processing states."""
    doc = make_document(id=1, status="pending", chunk_count=0)

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = doc
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.commit = AsyncMock()

    # Transition: pending -> processing
    await repo.update_document_status(1, "processing", None, 0)
    assert doc.status == "processing"
    assert doc.error_message is None
    assert doc.chunk_count == 0

    # Transition: processing -> completed
    mock_db.execute = AsyncMock(return_value=mock_result)
    await repo.update_document_status(1, "completed", None, 5)
    assert doc.status == "completed"
    assert doc.chunk_count == 5

    # Transition: processing -> failed
    doc_failed = make_document(id=2, status="processing")
    mock_result_failed = MagicMock()
    mock_result_failed.scalar_one_or_none.return_value = doc_failed
    mock_db.execute = AsyncMock(return_value=mock_result_failed)

    await repo.update_document_status(2, "failed", "Parse error", 0)
    assert doc_failed.status == "failed"
    assert doc_failed.error_message == "Parse error"
    assert doc_failed.chunk_count == 0


# --- Test 5: Bulk create chunks ---


@pytest.mark.asyncio
@pytest.mark.integration
async def test_bulk_create_chunks(repo: KnowledgeRepository, mock_db: AsyncMock) -> None:
    """Bulk create should add all chunks in a single batch."""
    chunks = [
        make_chunk(id=i, document_id=1, chunk_index=i, content=f"Chunk {i} text") for i in range(5)
    ]

    mock_db.add_all = MagicMock()
    mock_db.commit = AsyncMock()

    await repo.bulk_create_chunks(chunks)

    mock_db.add_all.assert_called_once_with(chunks)
    mock_db.commit.assert_awaited_once()
    assert len(chunks) == 5


# --- Test 6: Vector search with ordered results ---


@pytest.mark.asyncio
@pytest.mark.integration
async def test_search_vector(repo: KnowledgeRepository, mock_db: AsyncMock) -> None:
    """Vector search should return results ordered by cosine distance ascending."""
    doc = make_document(id=1)
    chunk_close = make_chunk(id=1, content="Very relevant text", chunk_index=0)
    chunk_mid = make_chunk(id=2, content="Somewhat relevant", chunk_index=1)
    chunk_far = make_chunk(id=3, content="Not very relevant", chunk_index=2)

    # Simulate DB rows: (chunk, document, distance) tuples
    mock_rows = [
        (chunk_close, doc, 0.1),
        (chunk_mid, doc, 0.4),
        (chunk_far, doc, 0.8),
    ]
    mock_result = MagicMock()
    mock_result.all.return_value = mock_rows
    mock_db.execute = AsyncMock(return_value=mock_result)

    query_embedding = [0.1] * 1024
    results = await repo.search_vector(query_embedding, limit=3)

    assert len(results) == 3
    # Verify ordering by distance (ascending)
    assert results[0][2] < results[1][2] < results[2][2]
    # Verify tuple structure: (chunk, document, distance)
    assert results[0][0].content == "Very relevant text"
    assert results[0][1].id == 1
    assert results[0][2] == pytest.approx(0.1)
    mock_db.execute.assert_awaited_once()


# --- Test 7: Full-text search ---


@pytest.mark.asyncio
@pytest.mark.integration
async def test_search_fulltext(repo: KnowledgeRepository, mock_db: AsyncMock) -> None:
    """Full-text search should return results ordered by rank descending."""
    doc = make_document(id=1)
    chunk_best = make_chunk(id=1, content="Transit route schedule", chunk_index=0)
    chunk_ok = make_chunk(id=2, content="Route information", chunk_index=1)

    # Simulate DB rows: (chunk, document, rank) - highest rank first
    mock_rows = [
        (chunk_best, doc, 0.9),
        (chunk_ok, doc, 0.3),
    ]
    mock_result = MagicMock()
    mock_result.all.return_value = mock_rows
    mock_db.execute = AsyncMock(return_value=mock_result)

    results = await repo.search_fulltext("transit schedule", limit=5)

    assert len(results) == 2
    # Verify ordering by rank (descending - best match first)
    assert results[0][2] > results[1][2]
    assert results[0][0].content == "Transit route schedule"
    assert results[0][2] == pytest.approx(0.9)
    assert results[1][2] == pytest.approx(0.3)
    mock_db.execute.assert_awaited_once()


# --- Test 8: Search with domain filter isolation ---


@pytest.mark.asyncio
@pytest.mark.integration
async def test_search_with_domain_filter(repo: KnowledgeRepository, mock_db: AsyncMock) -> None:
    """Vector search with domain filter should only return matching domain results."""
    transit_doc = make_document(id=1, domain="transit")
    transit_chunk = make_chunk(id=1, document_id=1, content="Bus schedule info")

    # Only transit results should come back when domain="transit"
    mock_rows = [(transit_chunk, transit_doc, 0.2)]
    mock_result = MagicMock()
    mock_result.all.return_value = mock_rows
    mock_db.execute = AsyncMock(return_value=mock_result)

    results = await repo.search_vector(
        query_embedding=[0.1] * 1024,
        limit=10,
        domain="transit",
    )

    assert len(results) == 1
    assert results[0][1].domain == "transit"
    mock_db.execute.assert_awaited_once()

    # With language filter too
    mock_db.execute = AsyncMock(return_value=mock_result)
    results = await repo.search_vector(
        query_embedding=[0.1] * 1024,
        limit=10,
        domain="transit",
        language="lv",
    )
    assert len(results) == 1

    # Full-text search with domain filter
    mock_db.execute = AsyncMock(return_value=mock_result)
    results = await repo.search_fulltext(
        "schedule",
        limit=10,
        domain="transit",
    )
    assert len(results) == 1
    assert results[0][1].domain == "transit"


# --- Test 9: Delete document cascades chunks ---


@pytest.mark.asyncio
@pytest.mark.integration
async def test_delete_document_cascades_chunks(
    repo: KnowledgeRepository, mock_db: AsyncMock
) -> None:
    """Delete should find the document and call db.delete on it."""
    doc = make_document(id=5)

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = doc
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.delete = AsyncMock()
    mock_db.commit = AsyncMock()

    await repo.delete_document(5)

    mock_db.delete.assert_awaited_once_with(doc)
    mock_db.commit.assert_awaited_once()

    # Verify no-op for missing document
    mock_result_none = MagicMock()
    mock_result_none.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result_none)
    mock_db.delete.reset_mock()
    mock_db.commit.reset_mock()

    await repo.delete_document(999)

    mock_db.delete.assert_not_awaited()


# --- Test 10: List unique domains ---


@pytest.mark.asyncio
@pytest.mark.integration
async def test_list_domains(repo: KnowledgeRepository, mock_db: AsyncMock) -> None:
    """List domains should return sorted unique domain strings."""
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = ["hr", "safety", "transit"]
    mock_result.scalars.return_value = mock_scalars
    mock_db.execute = AsyncMock(return_value=mock_result)

    domains = await repo.list_domains()

    assert domains == ["hr", "safety", "transit"]
    assert len(domains) == 3
    mock_db.execute.assert_awaited_once()

    # Empty case
    mock_scalars.all.return_value = []
    mock_db.execute = AsyncMock(return_value=mock_result)

    domains = await repo.list_domains()
    assert domains == []
