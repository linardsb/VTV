"""Tests for the knowledge base search agent tool."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.agents.tools.knowledge.search_knowledge import search_knowledge_base


@pytest.mark.asyncio
async def test_search_returns_document_id() -> None:
    """Verify search results include document_id for citation links."""
    ctx = MagicMock()
    ctx.deps.settings = MagicMock()
    ctx.deps.settings.embedding_provider = "jina"

    mock_search_result = MagicMock()
    mock_search_result.chunk_content = "Driver must follow schedule adherence rules."
    mock_search_result.document_id = 42
    mock_search_result.document_filename = "driver-handbook.pdf"
    mock_search_result.domain = "transit"
    mock_search_result.language = "en"
    mock_search_result.chunk_index = 3
    mock_search_result.score = 0.8765
    mock_search_result.metadata_json = None

    mock_response = MagicMock()
    mock_response.results = [mock_search_result]
    mock_response.total_candidates = 1

    with patch(
        "app.core.agents.tools.knowledge.search_knowledge.AsyncSessionLocal"
    ) as mock_session_cls:
        mock_session = AsyncMock()
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "app.core.agents.tools.knowledge.search_knowledge.KnowledgeService"
        ) as mock_svc_cls:
            mock_svc = AsyncMock()
            mock_svc.search.return_value = mock_response
            mock_svc_cls.return_value = mock_svc

            result_json = await search_knowledge_base(ctx, query="schedule adherence")

    result = json.loads(result_json)
    assert len(result["results"]) == 1
    assert result["results"][0]["document_id"] == 42
    assert result["results"][0]["source"] == "driver-handbook.pdf"
    assert result["results"][0]["relevance_score"] == 0.8765
    assert result["results"][0]["content"] == "Driver must follow schedule adherence rules."
    assert result["query"] == "schedule adherence"


@pytest.mark.asyncio
async def test_search_empty_query_returns_error() -> None:
    """Verify empty query returns actionable error message."""
    ctx = MagicMock()
    ctx.deps.settings = MagicMock()
    ctx.deps.settings.embedding_provider = "jina"

    result = await search_knowledge_base(ctx, query="")
    assert "Error" in result
    assert "empty" in result.lower()


@pytest.mark.asyncio
async def test_search_whitespace_query_returns_error() -> None:
    """Verify whitespace-only query returns error."""
    ctx = MagicMock()
    ctx.deps.settings = MagicMock()
    ctx.deps.settings.embedding_provider = "jina"

    result = await search_knowledge_base(ctx, query="   ")
    assert "Error" in result


@pytest.mark.asyncio
async def test_search_multiple_results_have_document_ids() -> None:
    """Verify all results in multi-result response include document_id."""
    ctx = MagicMock()
    ctx.deps.settings = MagicMock()
    ctx.deps.settings.embedding_provider = "jina"

    mock_results: list[MagicMock] = []
    for i in range(3):
        r = MagicMock()
        r.chunk_content = f"Content chunk {i}"
        r.document_id = 10 + i
        r.document_filename = f"doc-{i}.pdf"
        r.domain = "transit"
        r.language = "lv"
        r.chunk_index = 0
        r.score = 0.9 - (i * 0.1)
        r.metadata_json = None
        mock_results.append(r)

    mock_response = MagicMock()
    mock_response.results = mock_results
    mock_response.total_candidates = 3

    with patch(
        "app.core.agents.tools.knowledge.search_knowledge.AsyncSessionLocal"
    ) as mock_session_cls:
        mock_session = AsyncMock()
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "app.core.agents.tools.knowledge.search_knowledge.KnowledgeService"
        ) as mock_svc_cls:
            mock_svc = AsyncMock()
            mock_svc.search.return_value = mock_response
            mock_svc_cls.return_value = mock_svc

            result_json = await search_knowledge_base(ctx, query="transit policy")

    result = json.loads(result_json)
    assert len(result["results"]) == 3
    assert result["results"][0]["document_id"] == 10
    assert result["results"][1]["document_id"] == 11
    assert result["results"][2]["document_id"] == 12


@pytest.mark.asyncio
async def test_search_service_error_returns_message() -> None:
    """Verify service exceptions return actionable error string."""
    ctx = MagicMock()
    ctx.deps.settings = MagicMock()
    ctx.deps.settings.embedding_provider = "jina"

    with patch(
        "app.core.agents.tools.knowledge.search_knowledge.AsyncSessionLocal"
    ) as mock_session_cls:
        mock_session = AsyncMock()
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "app.core.agents.tools.knowledge.search_knowledge.KnowledgeService"
        ) as mock_svc_cls:
            mock_svc = AsyncMock()
            mock_svc.search.side_effect = RuntimeError("DB connection lost")
            mock_svc_cls.return_value = mock_svc

            result = await search_knowledge_base(ctx, query="overtime policy")

    assert "error" in result.lower()
    assert "DB connection lost" in result


@pytest.mark.asyncio
async def test_search_truncates_content_to_500_chars() -> None:
    """Verify chunk content is truncated to 500 characters."""
    ctx = MagicMock()
    ctx.deps.settings = MagicMock()
    ctx.deps.settings.embedding_provider = "jina"

    long_content = "A" * 1000

    mock_result = MagicMock()
    mock_result.chunk_content = long_content
    mock_result.document_id = 1
    mock_result.document_filename = "long-doc.pdf"
    mock_result.domain = "hr"
    mock_result.language = "en"
    mock_result.chunk_index = 0
    mock_result.score = 0.95
    mock_result.metadata_json = None

    mock_response = MagicMock()
    mock_response.results = [mock_result]
    mock_response.total_candidates = 1

    with patch(
        "app.core.agents.tools.knowledge.search_knowledge.AsyncSessionLocal"
    ) as mock_session_cls:
        mock_session = AsyncMock()
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "app.core.agents.tools.knowledge.search_knowledge.KnowledgeService"
        ) as mock_svc_cls:
            mock_svc = AsyncMock()
            mock_svc.search.return_value = mock_response
            mock_svc_cls.return_value = mock_svc

            result_json = await search_knowledge_base(ctx, query="hr policy")

    result = json.loads(result_json)
    assert len(result["results"][0]["content"]) == 500


def test_system_prompt_contains_citation_rules() -> None:
    """Verify SYSTEM_PROMPT instructs agent to format citation links."""
    from app.core.agents.agent import SYSTEM_PROMPT

    assert "CITATION RULES" in SYSTEM_PROMPT
    assert "/documents/" in SYSTEM_PROMPT
    assert "document_id" in SYSTEM_PROMPT
