# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false
# pyright: reportAttributeAccessIssue=false, reportCallIssue=false
"""Tests for DMS backend enhancements: Excel/CSV extraction, document update,
content retrieval, domain listing, file storage, cleanup, and download."""

import csv
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.knowledge.exceptions import DocumentNotFoundError, ProcessingError
from app.knowledge.processing import _extract_csv_sync, _extract_excel_sync
from app.knowledge.schemas import (
    DocumentUpdate,
    DomainListResponse,
)
from app.knowledge.service import KnowledgeService

# --- Test 1: Excel text extraction ---


def test_extract_excel_text() -> None:
    """Excel extraction should produce tab-separated text with sheet headers."""
    mock_cell_a = MagicMock()
    mock_cell_a.value = "Name"
    mock_cell_b = MagicMock()
    mock_cell_b.value = "Age"
    mock_cell_c = MagicMock()
    mock_cell_c.value = "Alice"
    mock_cell_d = MagicMock()
    mock_cell_d.value = 30

    mock_ws = MagicMock()
    mock_ws.iter_rows.return_value = [
        [mock_cell_a, mock_cell_b],
        [mock_cell_c, mock_cell_d],
    ]

    mock_wb = MagicMock()
    mock_wb.sheetnames = ["Sheet1"]
    mock_wb.__getitem__ = MagicMock(return_value=mock_ws)

    with patch("openpyxl.load_workbook", return_value=mock_wb):
        result = _extract_excel_sync("/tmp/test.xlsx")  # noqa: S108

    assert "Sheet1" in result
    assert "Name\tAge" in result
    assert "Alice\t30" in result
    mock_wb.close.assert_called_once()


# --- Test 2: CSV text extraction ---


def test_extract_csv_text(tmp_path: Path) -> None:
    """CSV extraction should return tab-separated text from all rows."""
    csv_file = tmp_path / "test.csv"
    with csv_file.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Name", "Role"])
        writer.writerow(["Bob", "Driver"])
        writer.writerow(["Eve", "Dispatcher"])

    result = _extract_csv_sync(str(csv_file))

    assert "Name\tRole" in result
    assert "Bob\tDriver" in result
    assert "Eve\tDispatcher" in result


# --- Test 3: Document update service ---


async def test_update_document() -> None:
    """Update service should call repository and return updated document."""
    mock_doc = MagicMock()
    mock_doc.id = 1
    mock_doc.filename = "test.pdf"
    mock_doc.title = "New Title"
    mock_doc.description = None
    mock_doc.file_path = None
    mock_doc.domain = "transit"
    mock_doc.source_type = "pdf"
    mock_doc.language = "lv"
    mock_doc.file_size_bytes = 1000
    mock_doc.status = "completed"
    mock_doc.error_message = None
    mock_doc.chunk_count = 5
    mock_doc.metadata_json = None
    mock_doc.ocr_applied = False
    mock_doc.created_at = MagicMock()
    mock_doc.updated_at = MagicMock()

    mock_db = AsyncMock()
    service = KnowledgeService(mock_db)
    service.repository = MagicMock()
    service.repository.update_document = AsyncMock(return_value=mock_doc)
    service.repository.get_document = AsyncMock(return_value=mock_doc)
    service.repository.get_tags_for_document = AsyncMock(return_value=[])

    update_data = DocumentUpdate(title="New Title")
    result = await service.update_document(1, update_data)

    assert result.title == "New Title"
    service.repository.update_document.assert_awaited_once()


# --- Test 4: Document content retrieval ---


async def test_get_document_content() -> None:
    """Content retrieval should return document metadata with ordered chunks."""
    mock_doc = MagicMock()
    mock_doc.id = 1
    mock_doc.filename = "test.pdf"
    mock_doc.title = "Test Doc"

    mock_chunks: list[MagicMock] = []
    for i in range(3):
        chunk = MagicMock()
        chunk.chunk_index = i
        chunk.content = f"Chunk {i} content"
        mock_chunks.append(chunk)

    mock_db = AsyncMock()
    service = KnowledgeService(mock_db)
    service.repository = MagicMock()
    service.repository.get_document = AsyncMock(return_value=mock_doc)
    service.repository.get_chunks_by_document = AsyncMock(return_value=mock_chunks)

    result = await service.get_document_content(1)

    assert result.document_id == 1
    assert result.total_chunks == 3
    assert len(result.chunks) == 3
    assert result.chunks[0].content == "Chunk 0 content"


# --- Test 5: Domain listing ---


async def test_list_domains() -> None:
    """Domain listing should return unique domains with count."""
    mock_db = AsyncMock()
    service = KnowledgeService(mock_db)
    service.repository = MagicMock()
    service.repository.list_domains = AsyncMock(return_value=["hr", "safety", "transit"])

    result = await service.list_domains()

    assert isinstance(result, DomainListResponse)
    assert result.total == 3
    assert result.domains == ["hr", "safety", "transit"]


# --- Test 6: File storage on upload ---


async def test_file_stored_on_ingest() -> None:
    """Ingest should copy file to storage directory and set file_path."""
    mock_doc = MagicMock()
    mock_doc.id = 42
    mock_doc.filename = "sop.pdf"
    mock_doc.title = "SOP"
    mock_doc.description = None
    mock_doc.file_path = "data/documents/42/sop.pdf"
    mock_doc.domain = "transit"
    mock_doc.source_type = "pdf"
    mock_doc.language = "lv"
    mock_doc.file_size_bytes = 5000
    mock_doc.status = "completed"
    mock_doc.error_message = None
    mock_doc.chunk_count = 2
    mock_doc.metadata_json = None
    mock_doc.ocr_applied = False
    mock_doc.created_at = MagicMock()
    mock_doc.updated_at = MagicMock()

    mock_db = AsyncMock()
    service = KnowledgeService(mock_db)
    service.repository = MagicMock()
    service.repository.create_document = AsyncMock(return_value=mock_doc)
    service.repository.update_document_file_path = AsyncMock()
    service.repository.update_document_status = AsyncMock()
    service.repository.bulk_create_chunks = AsyncMock()
    service.repository.get_document = AsyncMock(return_value=mock_doc)
    service.repository.get_tags_for_document = AsyncMock(return_value=[])
    mock_db.refresh = AsyncMock()

    from app.knowledge.schemas import DocumentUpload

    upload = DocumentUpload(
        domain="transit", language="lv", metadata_json=None, title="SOP", description=None
    )

    with (
        patch("app.knowledge.service.processing.extract_text", new_callable=AsyncMock) as mock_ext,
        patch("app.knowledge.service.chunking.chunk_text") as mock_chunk,
        patch("app.knowledge.service.shutil.copy2") as mock_copy,
        patch("app.knowledge.service.Path.mkdir"),
        patch("app.knowledge.service.get_settings") as mock_settings,
    ):
        mock_ext.return_value = ("Some text", False)
        mock_chunk.return_value = []
        mock_settings.return_value.document_storage_path = "data/documents"
        mock_settings.return_value.knowledge_chunk_size = 512
        mock_settings.return_value.knowledge_chunk_overlap = 50
        mock_settings.return_value.auto_tag_enabled = False

        await service.ingest_document(
            file_path="/tmp/sop.pdf",  # noqa: S108
            upload=upload,
            filename="sop.pdf",
            source_type="pdf",
            file_size=5000,
        )

    mock_copy.assert_called_once()
    service.repository.update_document_file_path.assert_awaited_once()


# --- Test 7: File cleanup on delete ---


async def test_file_deleted_on_document_delete() -> None:
    """Delete should remove stored file directory via shutil.rmtree."""
    mock_doc = MagicMock()
    mock_doc.id = 10
    mock_doc.file_path = "data/documents/10/report.pdf"

    mock_db = AsyncMock()
    service = KnowledgeService(mock_db)
    service.repository = MagicMock()
    service.repository.get_document = AsyncMock(return_value=mock_doc)
    service.repository.delete_document = AsyncMock()

    with patch("app.knowledge.service.shutil.rmtree") as mock_rmtree:
        await service.delete_document(10)

    mock_rmtree.assert_called_once_with(Path("data/documents/10"), ignore_errors=True)
    service.repository.delete_document.assert_awaited_once_with(10)


# --- Test 8: Download returns path and filename ---


async def test_get_document_file_path() -> None:
    """get_document_file_path should return (path, filename) tuple."""
    mock_doc = MagicMock()
    mock_doc.file_path = "data/documents/5/schedule.xlsx"
    mock_doc.filename = "schedule.xlsx"

    mock_db = AsyncMock()
    service = KnowledgeService(mock_db)
    service.repository = MagicMock()
    service.repository.get_document = AsyncMock(return_value=mock_doc)

    path, filename = await service.get_document_file_path(5)

    assert path == "data/documents/5/schedule.xlsx"
    assert filename == "schedule.xlsx"


# --- Test 9: Download raises for legacy document ---


async def test_get_document_file_path_legacy_raises() -> None:
    """Legacy documents without file_path should raise ProcessingError."""
    mock_doc = MagicMock()
    mock_doc.id = 3
    mock_doc.file_path = None

    mock_db = AsyncMock()
    service = KnowledgeService(mock_db)
    service.repository = MagicMock()
    service.repository.get_document = AsyncMock(return_value=mock_doc)

    with pytest.raises(ProcessingError, match="no stored file"):
        await service.get_document_file_path(3)


# --- Test 10: Update raises for missing document ---


async def test_update_document_not_found() -> None:
    """Update should raise DocumentNotFoundError for missing documents."""
    mock_db = AsyncMock()
    service = KnowledgeService(mock_db)
    service.repository = MagicMock()
    service.repository.update_document = AsyncMock(return_value=None)

    with pytest.raises(DocumentNotFoundError):
        await service.update_document(999, DocumentUpdate(title="Gone"))
