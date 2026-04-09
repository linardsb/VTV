# pyright: reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportCallIssue=false, reportArgumentType=false
"""Tests for HyDE (Hypothetical Document Embeddings) query expansion.

Covers: disabled toggle, successful expansion, model resolution,
LLM failure fallback, output truncation.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.knowledge.hyde import _resolve_model, expand_query

# ---------------------------------------------------------------------------
# 1. Model resolution
# ---------------------------------------------------------------------------


def test_resolve_model_dedicated_hyde_model() -> None:
    """Dedicated HyDE model takes priority."""
    settings = MagicMock()
    settings.knowledge_hyde_model = "groq:llama-3-8b"
    assert _resolve_model(settings) == "groq:llama-3-8b"


def test_resolve_model_fast_tier_fallback() -> None:
    """Falls back to fast-tier model when no dedicated HyDE model."""
    settings = MagicMock()
    settings.knowledge_hyde_model = None
    settings.llm_fast_provider = "groq"
    settings.llm_fast_model = "llama-3-8b"
    assert _resolve_model(settings) == "groq:llama-3-8b"


def test_resolve_model_primary_fallback() -> None:
    """Falls back to primary model when no fast tier configured."""
    settings = MagicMock()
    settings.knowledge_hyde_model = None
    settings.llm_fast_provider = None
    settings.llm_fast_model = None
    settings.llm_provider = "anthropic"
    settings.llm_model = "claude-haiku-4-5-20251001"
    assert _resolve_model(settings) == "anthropic:claude-haiku-4-5-20251001"


# ---------------------------------------------------------------------------
# 2. Successful expansion
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_expand_query_success() -> None:
    """Successful LLM call returns expanded text."""
    mock_result = MagicMock()
    mock_result.response = "Ja autobuss sabojājas maršrutā, vadītājam jāsazinās ar dispečeru."

    with patch("pydantic_ai.Agent") as mock_agent_cls:
        mock_agent = AsyncMock()
        mock_agent.run = AsyncMock(return_value=mock_result)
        mock_agent_cls.return_value = mock_agent

        settings = MagicMock()
        settings.knowledge_hyde_model = "test:test-model"
        settings.knowledge_hyde_max_tokens = 200

        result = await expand_query("Ko darīt, ja autobuss sabojājas?", settings)

    assert result == "Ja autobuss sabojājas maršrutā, vadītājam jāsazinās ar dispečeru."
    mock_agent.run.assert_awaited_once()


# ---------------------------------------------------------------------------
# 3. LLM failure fallback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_expand_query_llm_failure_returns_original() -> None:
    """LLM failure falls back to original query."""
    with patch("pydantic_ai.Agent") as mock_agent_cls:
        mock_agent = AsyncMock()
        mock_agent.run = AsyncMock(side_effect=RuntimeError("LLM unavailable"))
        mock_agent_cls.return_value = mock_agent

        settings = MagicMock()
        settings.knowledge_hyde_model = "test:test-model"
        settings.knowledge_hyde_max_tokens = 200

        original = "Ko darīt, ja autobuss sabojājas?"
        result = await expand_query(original, settings)

    assert result == original


# ---------------------------------------------------------------------------
# 4. Output truncation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_expand_query_truncates_long_output() -> None:
    """Long LLM output is truncated to max_tokens * 4 chars."""
    long_text = "A" * 2000
    mock_result = MagicMock()
    mock_result.response = long_text

    with patch("pydantic_ai.Agent") as mock_agent_cls:
        mock_agent = AsyncMock()
        mock_agent.run = AsyncMock(return_value=mock_result)
        mock_agent_cls.return_value = mock_agent

        settings = MagicMock()
        settings.knowledge_hyde_model = "test:test-model"
        settings.knowledge_hyde_max_tokens = 100  # max_chars = 400

        result = await expand_query("test query", settings)

    assert len(result) == 400


# ---------------------------------------------------------------------------
# 5. Integration: HyDE in search flow
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_uses_hyde_when_enabled() -> None:
    """Search embeds HyDE-expanded text when enabled."""
    from app.knowledge.repository import KnowledgeRepository
    from app.knowledge.service import KnowledgeService

    mock_db = AsyncMock()
    service = KnowledgeService(mock_db)

    mock_embedding = MagicMock()
    mock_embedding.embed = AsyncMock(return_value=[[0.1] * 1024])

    with (
        patch.object(KnowledgeRepository, "search_vector", new_callable=AsyncMock, return_value=[]),
        patch.object(
            KnowledgeRepository, "search_fulltext", new_callable=AsyncMock, return_value=[]
        ),
        patch("app.knowledge.service.get_settings") as mock_settings,
        patch("app.knowledge.service._get_embedding", return_value=mock_embedding),
        patch("app.knowledge.service._get_reranker") as mock_reranker_fn,
        patch("app.knowledge.hyde.expand_query", new_callable=AsyncMock) as mock_expand,
    ):
        mock_reranker = MagicMock()
        mock_reranker.rerank = AsyncMock(return_value=[])
        mock_reranker_fn.return_value = mock_reranker

        s = MagicMock()
        s.knowledge_hyde_enabled = True
        s.knowledge_search_limit = 10
        s.knowledge_confidence_threshold = 0.3
        s.rrf_mixed_vector_weight = 0.5
        s.rrf_mixed_text_weight = 0.5
        s.rrf_keyword_vector_weight = 0.3
        s.rrf_keyword_text_weight = 0.7
        s.rrf_semantic_vector_weight = 0.7
        s.rrf_semantic_text_weight = 0.3
        s.temporal_boost_enabled = False
        s.reranker_top_k = 10
        mock_settings.return_value = s

        mock_expand.return_value = "Expanded hypothetical answer"

        from app.knowledge.schemas import SearchRequest

        request = SearchRequest(query="test query", limit=5)
        await service.search(request)

    mock_expand.assert_awaited_once_with("test query", s)
    mock_embedding.embed.assert_awaited_once_with(["Expanded hypothetical answer"])


@pytest.mark.asyncio
async def test_search_skips_hyde_when_disabled() -> None:
    """Search embeds raw query when HyDE is disabled."""
    from app.knowledge.repository import KnowledgeRepository
    from app.knowledge.service import KnowledgeService

    mock_db = AsyncMock()
    service = KnowledgeService(mock_db)

    mock_embedding = MagicMock()
    mock_embedding.embed = AsyncMock(return_value=[[0.1] * 1024])

    with (
        patch.object(KnowledgeRepository, "search_vector", new_callable=AsyncMock, return_value=[]),
        patch.object(
            KnowledgeRepository, "search_fulltext", new_callable=AsyncMock, return_value=[]
        ),
        patch("app.knowledge.service.get_settings") as mock_settings,
        patch("app.knowledge.service._get_embedding", return_value=mock_embedding),
        patch("app.knowledge.service._get_reranker") as mock_reranker_fn,
        patch("app.knowledge.hyde.expand_query", new_callable=AsyncMock) as mock_expand,
    ):
        mock_reranker = MagicMock()
        mock_reranker.rerank = AsyncMock(return_value=[])
        mock_reranker_fn.return_value = mock_reranker

        s = MagicMock()
        s.knowledge_hyde_enabled = False
        s.knowledge_search_limit = 10
        s.knowledge_confidence_threshold = 0.3
        s.rrf_mixed_vector_weight = 0.5
        s.rrf_mixed_text_weight = 0.5
        s.rrf_keyword_vector_weight = 0.3
        s.rrf_keyword_text_weight = 0.7
        s.rrf_semantic_vector_weight = 0.7
        s.rrf_semantic_text_weight = 0.3
        s.temporal_boost_enabled = False
        s.reranker_top_k = 10
        mock_settings.return_value = s

        from app.knowledge.schemas import SearchRequest

        request = SearchRequest(query="test query", limit=5)
        await service.search(request)

    mock_expand.assert_not_awaited()
    mock_embedding.embed.assert_awaited_once_with(["test query"])
