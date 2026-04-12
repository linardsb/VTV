"""Factories and fixtures for QA generator tests."""

from __future__ import annotations

from datetime import UTC
from typing import Any
from unittest.mock import MagicMock

from app.knowledge.evals.schemas import QAPair
from app.knowledge.models import Document, DocumentChunk
from app.knowledge.schemas import SearchResult


def make_mock_chunk(**overrides: Any) -> MagicMock:
    """Return a MagicMock mimicking DocumentChunk with safe defaults."""
    chunk = MagicMock(spec=DocumentChunk)
    chunk.id = overrides.get("id", 1)
    chunk.document_id = overrides.get("document_id", 1)
    chunk.content = overrides.get("content", "A" * 300)
    chunk.chunk_index = overrides.get("chunk_index", 0)
    chunk.heading_path = overrides.get("heading_path", "Section > Subsection")
    chunk.section_type = overrides.get("section_type", "heading")
    chunk.parent_chunk_id = overrides.get("parent_chunk_id", None)
    return chunk


def make_mock_document(**overrides: Any) -> MagicMock:
    """Return a MagicMock mimicking Document with safe defaults."""
    doc = MagicMock(spec=Document)
    doc.id = overrides.get("id", 1)
    doc.language = overrides.get("language", "lv")
    doc.status = overrides.get("status", "completed")
    doc.domain = overrides.get("domain", "transit")
    return doc


def make_qa_pair(**overrides: Any) -> QAPair:
    """Return a QAPair with safe defaults."""
    defaults: dict[str, Any] = {
        "question": "Kads ir marsruta 22 grafiks?",
        "source_chunk_id": 1,
        "source_document_id": 1,
        "source_chunk_index": 0,
        "source_heading_path": "Marsruti > Marsruts 22",
        "language": "lv",
        "generated_at": "2026-04-12T10:00:00+00:00",
        "model_used": "test:test-model",
    }
    defaults.update(overrides)
    return QAPair(**defaults)


def make_search_result(**overrides: Any) -> SearchResult:
    """Return a SearchResult with safe defaults for metrics testing."""
    from datetime import datetime

    defaults: dict[str, Any] = {
        "chunk_content": "Sample chunk text for testing",
        "document_id": 1,
        "document_filename": "test.pdf",
        "domain": "transit",
        "language": "lv",
        "chunk_index": 0,
        "score": 0.85,
        "metadata_json": None,
        "document_created_at": datetime(2026, 1, 1, tzinfo=UTC),
    }
    defaults.update(overrides)
    return SearchResult(**defaults)
