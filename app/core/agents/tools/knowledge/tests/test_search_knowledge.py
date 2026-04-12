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
    mock_search_result.parent_content = None
    mock_search_result.heading_path = None

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
        r.parent_content = None
        r.heading_path = None
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
async def test_search_truncates_content_to_1500_chars() -> None:
    """Verify chunk content is truncated to 1500 characters."""
    ctx = MagicMock()
    ctx.deps.settings = MagicMock()
    ctx.deps.settings.embedding_provider = "jina"

    long_content = "A" * 3000

    mock_result = MagicMock()
    mock_result.chunk_content = long_content
    mock_result.document_id = 1
    mock_result.document_filename = "long-doc.pdf"
    mock_result.domain = "hr"
    mock_result.language = "en"
    mock_result.chunk_index = 0
    mock_result.score = 0.95
    mock_result.metadata_json = None
    mock_result.parent_content = None
    mock_result.heading_path = None

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
    assert len(result["results"][0]["content"]) == 1500


@pytest.mark.asyncio
async def test_search_no_results_returns_no_documents_message() -> None:
    """Verify empty results after confidence filtering return clear message."""
    ctx = MagicMock()
    ctx.deps.settings = MagicMock()
    ctx.deps.settings.embedding_provider = "jina"

    mock_response = MagicMock()
    mock_response.results = []
    mock_response.total_candidates = 0

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

            result = await search_knowledge_base(ctx, query="nonexistent topic")

    assert "No relevant documents found" in result
    assert "nonexistent topic" in result


@pytest.mark.asyncio
async def test_search_includes_parent_context_in_content() -> None:
    """Parent_content + heading_path should produce [Section:] + [Matched passage:] markers."""
    ctx = MagicMock()
    ctx.deps.settings = MagicMock()
    ctx.deps.settings.embedding_provider = "jina"

    mock_result = MagicMock()
    mock_result.chunk_content = "step 1: call depot X"
    mock_result.document_id = 42
    mock_result.document_filename = "sop.pdf"
    mock_result.domain = "ops"
    mock_result.language = "en"
    mock_result.chunk_index = 3
    mock_result.score = 0.85
    mock_result.metadata_json = None
    mock_result.parent_content = "When bus breaks down on route 22, follow these steps..."
    mock_result.heading_path = "Operations > Breakdown Procedures"

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

            result_json = await search_knowledge_base(ctx, query="breakdown procedure")

    parsed = json.loads(result_json)
    assert len(parsed["results"]) == 1
    content = parsed["results"][0]["content"]
    assert "[Section: Operations > Breakdown Procedures]" in content
    assert "When bus breaks down on route 22" in content
    assert "[Matched passage:]" in content
    assert "step 1: call depot X" in content
    assert parsed["results"][0]["parent_content"] is not None
    assert parsed["results"][0]["heading_path"] == "Operations > Breakdown Procedures"


@pytest.mark.asyncio
async def test_search_omits_parent_markers_when_no_parent() -> None:
    """Leaf chunk results (parent_content=None) format as raw child content."""
    ctx = MagicMock()
    ctx.deps.settings = MagicMock()
    ctx.deps.settings.embedding_provider = "jina"

    mock_result = MagicMock()
    mock_result.chunk_content = "standalone fact"
    mock_result.document_id = 42
    mock_result.document_filename = "sop.pdf"
    mock_result.domain = "ops"
    mock_result.language = "en"
    mock_result.chunk_index = 5
    mock_result.score = 0.7
    mock_result.metadata_json = None
    mock_result.parent_content = None
    mock_result.heading_path = None

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

            result_json = await search_knowledge_base(ctx, query="standalone")

    parsed = json.loads(result_json)
    content = parsed["results"][0]["content"]
    assert "[Section:" not in content
    assert "[Matched passage:]" not in content
    assert content == "standalone fact"
    assert parsed["results"][0]["parent_content"] is None
    assert parsed["results"][0]["heading_path"] is None


@pytest.mark.asyncio
async def test_search_truncates_parent_content_to_3000_chars() -> None:
    """Parent content exceeding _MAX_PARENT_CHARS should be truncated."""
    ctx = MagicMock()
    ctx.deps.settings = MagicMock()
    ctx.deps.settings.embedding_provider = "jina"

    long_parent = "P" * 5000

    mock_result = MagicMock()
    mock_result.chunk_content = "child"
    mock_result.document_id = 1
    mock_result.document_filename = "doc.pdf"
    mock_result.domain = "ops"
    mock_result.language = "en"
    mock_result.chunk_index = 0
    mock_result.score = 0.9
    mock_result.metadata_json = None
    mock_result.parent_content = long_parent
    mock_result.heading_path = "Section A"

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

            result_json = await search_knowledge_base(ctx, query="long parent")

    parsed = json.loads(result_json)
    content = parsed["results"][0]["content"]
    # 3000 'P' chars truncated, then framing markers
    assert "P" * 3000 in content
    assert "P" * 3001 not in content


def test_system_prompt_contains_knowledge_base_behavior() -> None:
    """Verify SYSTEM_PROMPT contains knowledge base behavior guidance."""
    from app.core.agents.agent import SYSTEM_PROMPT

    assert "KNOWLEDGE BASE BEHAVIOR" in SYSTEM_PROMPT
    assert "No relevant documents found" in SYSTEM_PROMPT
    assert "Do NOT fabricate" in SYSTEM_PROMPT


def test_system_prompt_contains_citation_rules() -> None:
    """Verify SYSTEM_PROMPT instructs agent to format citation links."""
    from app.core.agents.agent import SYSTEM_PROMPT

    assert "CITATION RULES" in SYSTEM_PROMPT
    assert "/documents/" in SYSTEM_PROMPT
    assert "document_id" in SYSTEM_PROMPT


# --- AI-10.1: Heading breadcrumb citation tests ---


def test_heading_to_slug_basic() -> None:
    """Verify basic heading is converted to kebab-case slug."""
    from app.core.agents.tools.knowledge.search_knowledge import _heading_to_slug

    assert _heading_to_slug("Route Deviation") == "route-deviation"


def test_heading_to_slug_latvian_diacritics() -> None:
    """Verify Latvian diacritics are stripped via NFKD decomposition."""
    from app.core.agents.tools.knowledge.search_knowledge import _heading_to_slug

    assert _heading_to_slug("Maršruta novirze") == "marsruta-novirze"


def test_heading_to_slug_special_characters() -> None:
    """Verify special characters are replaced with hyphens."""
    from app.core.agents.tools.knowledge.search_knowledge import _heading_to_slug

    slug = _heading_to_slug("Section 3.1: Safety & Compliance (2024)")
    assert slug == "section-3-1-safety-compliance-2024"


def test_build_citation_anchor_with_heading_path() -> None:
    """Verify citation anchor is built from source + heading path."""
    from app.core.agents.tools.knowledge.search_knowledge import (
        _build_citation_anchor,
    )

    result = _build_citation_anchor("driver-handbook.pdf", "Emergency Procedures > Route Deviation")
    assert result == "driver-handbook - Emergency Procedures > Route Deviation"


def test_build_citation_anchor_null_when_no_heading_path() -> None:
    """Verify None heading_path produces None anchor."""
    from app.core.agents.tools.knowledge.search_knowledge import (
        _build_citation_anchor,
    )

    assert _build_citation_anchor("doc.pdf", None) is None


def test_build_citation_anchor_empty_heading_path_treated_as_null() -> None:
    """Verify empty string heading_path is treated as None."""
    from app.core.agents.tools.knowledge.search_knowledge import (
        _build_citation_anchor,
    )

    assert _build_citation_anchor("doc.pdf", "") is None


def test_build_citation_anchor_single_level_heading() -> None:
    """Verify single-level heading (no >) works correctly."""
    from app.core.agents.tools.knowledge.search_knowledge import (
        _build_citation_anchor,
    )

    result = _build_citation_anchor("doc-title.pdf", "Introduction")
    assert result == "doc-title - Introduction"


@pytest.mark.asyncio
async def test_citation_anchor_populated_in_search_result() -> None:
    """Verify search results include citation_anchor and url_fragment when heading_path exists."""
    ctx = MagicMock()
    ctx.deps.settings = MagicMock()
    ctx.deps.settings.embedding_provider = "jina"

    mock_result = MagicMock()
    mock_result.chunk_content = "Emergency route deviation procedure."
    mock_result.document_id = 42
    mock_result.document_filename = "driver-handbook.pdf"
    mock_result.domain = "transit"
    mock_result.language = "en"
    mock_result.chunk_index = 5
    mock_result.score = 0.92
    mock_result.metadata_json = None
    mock_result.parent_content = None
    mock_result.heading_path = "Emergency Procedures > Route Deviation"

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

            result_json = await search_knowledge_base(ctx, query="route deviation")

    parsed = json.loads(result_json)
    r = parsed["results"][0]
    assert r["citation_anchor"] == "driver-handbook - Emergency Procedures > Route Deviation"
    assert r["url_fragment"] == "route-deviation"


@pytest.mark.asyncio
async def test_citation_anchor_null_when_no_heading() -> None:
    """Verify citation_anchor and url_fragment are null for legacy chunks."""
    ctx = MagicMock()
    ctx.deps.settings = MagicMock()
    ctx.deps.settings.embedding_provider = "jina"

    mock_result = MagicMock()
    mock_result.chunk_content = "Some legacy content."
    mock_result.document_id = 10
    mock_result.document_filename = "old-doc.pdf"
    mock_result.domain = "hr"
    mock_result.language = "en"
    mock_result.chunk_index = 0
    mock_result.score = 0.8
    mock_result.metadata_json = None
    mock_result.parent_content = None
    mock_result.heading_path = None

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

            result_json = await search_knowledge_base(ctx, query="legacy")

    parsed = json.loads(result_json)
    r = parsed["results"][0]
    assert r["citation_anchor"] is None
    assert r["url_fragment"] is None


@pytest.mark.asyncio
async def test_url_fragment_multi_level_breadcrumb() -> None:
    """Verify url_fragment is derived from the last segment of a multi-level breadcrumb."""
    ctx = MagicMock()
    ctx.deps.settings = MagicMock()
    ctx.deps.settings.embedding_provider = "jina"

    mock_result = MagicMock()
    mock_result.chunk_content = "Deep nested content."
    mock_result.document_id = 7
    mock_result.document_filename = "manual.pdf"
    mock_result.domain = "ops"
    mock_result.language = "en"
    mock_result.chunk_index = 2
    mock_result.score = 0.85
    mock_result.metadata_json = None
    mock_result.parent_content = None
    mock_result.heading_path = "A > B > C > D"

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

            result_json = await search_knowledge_base(ctx, query="deep nested")

    parsed = json.loads(result_json)
    r = parsed["results"][0]
    assert r["citation_anchor"] == "manual - A > B > C > D"
    assert r["url_fragment"] == "d"


def test_knowledge_system_prompt_contains_citation_anchor_instructions() -> None:
    """Verify KNOWLEDGE_SYSTEM_PROMPT references citation_anchor and url_fragment."""
    from app.core.agents.agents.knowledge import KNOWLEDGE_SYSTEM_PROMPT

    assert "citation_anchor" in KNOWLEDGE_SYSTEM_PROMPT
    assert "url_fragment" in KNOWLEDGE_SYSTEM_PROMPT
