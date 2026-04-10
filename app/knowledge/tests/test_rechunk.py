# pyright: reportPrivateUsage=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Tests for the AI-4.4 re-chunk pipeline (KnowledgeService.rechunk_document)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.knowledge import chunking as chunking_module
from app.knowledge import processing as processing_module
from app.knowledge import service as service_module
from app.knowledge.chunking import ChunkResult
from app.knowledge.exceptions import DocumentNotFoundError, ProcessingError
from app.knowledge.service import KnowledgeService
from app.knowledge.tests.test_repository import make_document


def _default_chunks() -> list[ChunkResult]:
    """Return a small parent+child chunk list used by most tests."""
    return [
        ChunkResult(
            content="parent text",
            chunk_index=0,
            heading_path="H",
            section_type="paragraph",
            is_parent=True,
        ),
        ChunkResult(
            content="child text",
            chunk_index=1,
            heading_path="H",
            section_type="paragraph",
            parent_index=0,
        ),
    ]


def _build_service_with_mocks(
    *,
    document: Any | None,
    bulk_create_side_effect: BaseException | None = None,
) -> tuple[KnowledgeService, MagicMock]:
    """Wire a KnowledgeService whose repository methods are all mocked."""
    repo = MagicMock()
    repo.get_document = AsyncMock(return_value=document)
    repo.delete_chunks_by_document = AsyncMock(return_value=0)
    repo.bulk_create_chunks = AsyncMock(side_effect=bulk_create_side_effect)
    repo.update_document_status = AsyncMock()
    repo.update_document_ocr_applied = AsyncMock()

    db_session = AsyncMock()
    service = KnowledgeService(db_session)
    service.repository = repo
    return service, repo


def _patch_pipeline(
    monkeypatch: pytest.MonkeyPatch,
    *,
    extract_result: tuple[str, bool],
    chunks: list[ChunkResult],
    embedding_dim: int = 4,
) -> AsyncMock:
    """Patch processing.extract_text, the chunker, and the embedding singleton.

    Returns the embedding provider mock so callers can override side_effect.
    """

    async def _fake_extract(_path: str, _source: str) -> tuple[str, bool]:
        return extract_result

    monkeypatch.setattr(processing_module, "extract_text", _fake_extract)

    def _fake_semantic(*_args: Any, **_kwargs: Any) -> list[ChunkResult]:
        return chunks

    monkeypatch.setattr(chunking_module, "chunk_text_semantic", _fake_semantic)
    monkeypatch.setattr(chunking_module, "chunk_text", _fake_semantic)

    embedding_provider = MagicMock()
    embedding_provider.embed = AsyncMock(
        return_value=[[0.0] * embedding_dim for _ in chunks],
    )
    monkeypatch.setattr(service_module, "_get_embedding", lambda: embedding_provider)
    return embedding_provider


@pytest.mark.asyncio
async def test_rechunk_document_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """Happy path: deletes old chunks, calls bulk create, marks completed."""
    doc = make_document(
        id=1, file_path="/data/documents/1/foo.md", chunk_count=5, source_type="text"
    )
    service, repo = _build_service_with_mocks(document=doc)
    chunks = _default_chunks()
    _patch_pipeline(monkeypatch, extract_result=("text", False), chunks=chunks)

    new_count = await service.rechunk_document(1)

    assert new_count == len(chunks)
    repo.delete_chunks_by_document.assert_awaited_once_with(1)
    # Two-phase: parents flushed, then children committed
    assert repo.bulk_create_chunks.await_count == 2
    repo.update_document_status.assert_awaited_with(1, "completed", None, len(chunks))
    repo.update_document_ocr_applied.assert_not_awaited()


@pytest.mark.asyncio
async def test_rechunk_document_marks_ocr_when_applied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Re-chunking a PDF where OCR was applied should update ocr_applied flag."""
    doc = make_document(id=2, file_path="/data/documents/2/scan.pdf", source_type="pdf")
    service, repo = _build_service_with_mocks(document=doc)
    _patch_pipeline(monkeypatch, extract_result=("scanned text", True), chunks=_default_chunks())

    await service.rechunk_document(2)

    repo.update_document_ocr_applied.assert_awaited_once_with(2, ocr_applied=True)


@pytest.mark.asyncio
async def test_rechunk_document_missing_file_path_raises() -> None:
    """Documents with no stored file_path must raise without touching chunks."""
    doc = make_document(id=3, file_path=None)
    service, repo = _build_service_with_mocks(document=doc)

    with pytest.raises(ProcessingError):
        await service.rechunk_document(3)

    repo.delete_chunks_by_document.assert_not_awaited()
    repo.bulk_create_chunks.assert_not_awaited()


@pytest.mark.asyncio
async def test_rechunk_document_not_found_raises() -> None:
    """Missing document id raises DocumentNotFoundError."""
    service, repo = _build_service_with_mocks(document=None)

    with pytest.raises(DocumentNotFoundError):
        await service.rechunk_document(999)

    repo.delete_chunks_by_document.assert_not_awaited()


@pytest.mark.asyncio
async def test_rechunk_document_marks_failed_on_chunk_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If bulk_create_chunks raises, doc is marked failed and the error re-raises."""
    doc = make_document(id=4, file_path="/data/documents/1/foo.md")
    service, repo = _build_service_with_mocks(
        document=doc,
        bulk_create_side_effect=RuntimeError("boom"),
    )
    _patch_pipeline(monkeypatch, extract_result=("text", False), chunks=_default_chunks())

    with pytest.raises(RuntimeError, match="boom"):
        await service.rechunk_document(4)

    # Original chunks were deleted before the error
    repo.delete_chunks_by_document.assert_awaited_once_with(4)
    # Failure status was recorded
    repo.update_document_status.assert_awaited_with(4, "failed", "boom", 0)


@pytest.mark.asyncio
async def test_rechunk_document_preserves_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """rechunk_document must NOT touch document metadata or file_path."""
    doc = make_document(id=5, file_path="/data/documents/1/foo.md")
    service, repo = _build_service_with_mocks(document=doc)
    _patch_pipeline(monkeypatch, extract_result=("text", False), chunks=_default_chunks())

    # Add spies for methods that must NOT be called
    repo.update_document = AsyncMock()
    repo.update_document_file_path = AsyncMock()
    # Internal auto-tag should not run on re-chunk
    auto_tag_spy = AsyncMock()
    monkeypatch.setattr(service, "_auto_tag_document", auto_tag_spy)

    await service.rechunk_document(5)

    repo.update_document.assert_not_awaited()
    repo.update_document_file_path.assert_not_awaited()
    auto_tag_spy.assert_not_awaited()
