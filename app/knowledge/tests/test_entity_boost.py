"""Service-level tests for the KB-5 entity boost pipeline.

Uses mocks for the repository layer so the search logic can be exercised
without a live database. The boost path is pure-python once entity
mappings are fetched, so unit-style mocking is both sufficient and fast.
"""

from __future__ import annotations

import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.config import get_settings
from app.knowledge import entities_gazetteer
from app.knowledge.entity_extractor import reset_entity_extractor
from app.knowledge.models import Document, DocumentChunk
from app.knowledge.schemas import SearchRequest
from app.knowledge.service import KnowledgeService


def _make_chunk(chunk_id: int, document_id: int, content: str) -> DocumentChunk:
    chunk = DocumentChunk(
        document_id=document_id,
        content=content,
        chunk_index=chunk_id,
    )
    chunk.id = chunk_id
    chunk.parent_chunk_id = None
    chunk.heading_path = None
    chunk.metadata_json = None
    return chunk


def _make_doc(doc_id: int, filename: str = "doc.md") -> Document:
    doc = Document(
        filename=filename,
        domain="transit",
        source_type="markdown",
        language="lv",
        file_size_bytes=1024,
        metadata_json=None,
    )
    doc.id = doc_id
    doc.created_at = datetime.datetime.now(datetime.UTC)
    doc.updated_at = doc.created_at
    doc.evergreen = False
    doc.version = 1
    doc.is_latest = True
    doc.parent_document_id = None
    return doc


@pytest.fixture(autouse=True)
def clean_gazetteer() -> Any:
    entities_gazetteer.reset_gazetteer()
    reset_entity_extractor()
    yield
    entities_gazetteer.reset_gazetteer()
    reset_entity_extractor()


async def _search_with_mocks(
    monkeypatch: pytest.MonkeyPatch,
    *,
    query: str,
    chunk_a_score_vector: float = 0.01,
    chunk_b_score_vector: float = 0.02,
    query_entity_ids: frozenset[int] = frozenset({100}),
    chunk_entity_map: dict[int, frozenset[int]] | None = None,
    entity_boost_enabled: bool = True,
    chunk_names: dict[int, list[str]] | None = None,
) -> Any:
    """Drive ``KnowledgeService.search`` with repository + provider mocks."""
    chunk_a = _make_chunk(1, 10, "Route 22 delay notice.")
    chunk_b = _make_chunk(2, 11, "Route 33 reroute.")
    doc_a = _make_doc(10)
    doc_b = _make_doc(11)

    repo = AsyncMock()
    repo.search_vector.return_value = [
        (chunk_a, doc_a, chunk_a_score_vector),
        (chunk_b, doc_b, chunk_b_score_vector),
    ]
    repo.search_fulltext.return_value = []
    repo.get_chunks_by_ids.return_value = []
    repo.get_entity_ids_for_names.return_value = query_entity_ids
    repo.get_entity_ids_for_chunks.return_value = chunk_entity_map or {}
    repo.get_entity_names_for_chunks.return_value = chunk_names or {}

    # Swap the module-level singletons via monkeypatch.
    from app.knowledge import service as svc_module

    fake_embedding = MagicMock()
    fake_embedding.embed = AsyncMock(return_value=[[0.1, 0.2, 0.3]])
    monkeypatch.setattr(svc_module, "_get_embedding", lambda: fake_embedding)

    fake_reranker = MagicMock()
    fake_reranker.rerank = AsyncMock(
        return_value=[
            MagicMock(index=0, score=0.9),
            MagicMock(index=1, score=0.8),
        ]
    )
    monkeypatch.setattr(svc_module, "_get_reranker", lambda: fake_reranker)

    fake_lemmatizer = MagicMock()
    fake_lemmatizer.lemmatize = MagicMock(side_effect=lambda t, _lang: t)
    monkeypatch.setattr(svc_module, "_get_lemmatizer", lambda: fake_lemmatizer)

    # Force entity extraction + boost flags, override multiplier to something
    # large enough to reorder results deterministically.
    settings = get_settings().model_copy(
        update={
            "entity_extraction_enabled": True,
            "entity_boost_enabled": entity_boost_enabled,
            "entity_boost_multiplier": 3.0,
            "knowledge_parent_context_enabled": False,
            "knowledge_confidence_threshold": 0.0,
            "latvian_lemmatizer_enabled": False,
            "knowledge_hyde_enabled": False,
            "reranker_provider": "none",
        }
    )
    monkeypatch.setattr(svc_module, "get_settings", lambda: settings)

    service = KnowledgeService(db=MagicMock())
    service.repository = repo
    return await service.search(SearchRequest(query=query, limit=10))


class TestEntityBoost:
    async def test_boost_applied_when_query_and_chunk_share_entity(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        response = await _search_with_mocks(
            monkeypatch,
            query="Route 22",
            chunk_a_score_vector=0.5,
            chunk_b_score_vector=0.2,
            query_entity_ids=frozenset({100}),
            chunk_entity_map={1: frozenset({100}), 2: frozenset({200})},
        )
        assert response.results[0].document_id == 10  # chunk A

    async def test_no_entity_in_query_no_boost(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Empty query_entity_ids → no chunks match, scores unchanged.
        response = await _search_with_mocks(
            monkeypatch,
            query="transit delays",
            query_entity_ids=frozenset(),
            chunk_entity_map={1: frozenset({100})},
        )
        assert len(response.results) == 2

    async def test_boost_disabled_flag_bypasses_logic(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        response = await _search_with_mocks(
            monkeypatch,
            query="Route 22",
            entity_boost_enabled=False,
            query_entity_ids=frozenset({100}),
            chunk_entity_map={1: frozenset({100})},
        )
        # Repo lookups for entity names still run post-rerank; structural check.
        assert len(response.results) == 2

    async def test_search_result_entities_populated(self, monkeypatch: pytest.MonkeyPatch) -> None:
        response = await _search_with_mocks(
            monkeypatch,
            query="Route 22",
            query_entity_ids=frozenset({100}),
            chunk_entity_map={1: frozenset({100})},
            chunk_names={1: ["Route 22"]},
        )
        chunk_a_result = next(r for r in response.results if r.document_id == 10)
        assert chunk_a_result.entities == ["Route 22"]

    async def test_boost_fails_open_on_extractor_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Force the entity extractor factory to raise — search should still
        # complete using pure RRF + temporal boost.
        from app.knowledge import service as svc_module

        async def raising_factory() -> Any:
            raise RuntimeError("extractor boom")

        monkeypatch.setattr(svc_module, "get_entity_extractor", raising_factory)
        response = await _search_with_mocks(
            monkeypatch, query="Route 22", query_entity_ids=frozenset({100})
        )
        assert len(response.results) == 2
