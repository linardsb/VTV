# Plan: AI-2.2 HyDE (Hypothetical Document Embeddings)

## Context

Latvian is a low-resource language for embedding models. Even Jina v3 (best multilingual option) has weaker coverage for Latvian. HyDE sidesteps this by generating a hypothetical answer using a fast LLM before embedding — the hypothetical answer is in document-like language, so it embeds closer to actual documents. Expected 15-20% retrieval quality improvement for Latvian queries at ~$0.001/query cost.

## Security Context Assessment

- **CTX-AGENT** — Uses LLM to generate hypothetical answers. Must sanitize LLM output before embedding. Must not expose credentials in logs. Must handle LLM failures gracefully (fallback to raw query).
- **CTX-INPUT** — Processes user search queries through LLM. Prompt injection risk mitigated by using the LLM output only for embedding (not displayed to user).

No new endpoints added — this modifies the internal search pipeline only.

## Research Summary

### Current Search Flow (`app/knowledge/service.py:400-470`)

1. `SearchRequest` with query, domain, language, limit, date filters
2. **Embed query** (line 419): `query_embedding = (await _get_embedding().embed([request.query]))[0]`
3. Vector search + fulltext search in parallel
4. Query type detection → RRF fusion → temporal boost → reranking → confidence filter
5. Return `SearchResponse`

**HyDE integration point:** Before line 419, expand the query via LLM, then embed the expanded text instead of the raw query. Keep raw query for fulltext search (line 431).

### LLM Pattern (auto-tagging, `service.py:758-807`)

```python
from pydantic_ai import Agent
agent = Agent(f"{settings.llm_provider}:{settings.llm_model}", system_prompt="...")
result = await agent.run(text)
response = str(result.response)
```

Fresh Agent instance per call. Errors caught with broad `except Exception` → log warning, continue.

### Config Pattern (`app/core/config.py:206-211`)

Feature toggles: `knowledge_router_enabled: bool = True`, `auto_tag_enabled: bool = False`. Settings accessed via `get_settings()` singleton.

### Fast-tier LLM (`app/core/config.py:66-67`)

`llm_fast_provider: str | None = None`, `llm_fast_model: str | None = None` — falls back to primary model when None.

### Embedding Provider (`app/knowledge/embedding.py`)

Protocol: `EmbeddingProvider.embed(texts: list[str]) -> list[list[float]]`. Singleton via `_get_embedding()` in `service.py:56-61`.

## Test Landscape

- **Template:** `app/knowledge/tests/test_autotag.py` — same LLM mocking pattern needed
- **Mock pattern:** `patch("pydantic_ai.Agent")` + `patch("app.knowledge.service.get_settings")`
- **Fixtures:** `conftest.py` has `sample_latvian_text()`, `sample_english_text()`
- **Factories:** `test_repository.py` has `make_document()`, `make_chunk()`
- **10 existing test modules** with 2,528 lines total

## Type Check Baseline

- **Pyright:** 0 errors on `app/knowledge/`
- **MyPy:** 0 errors on `app/knowledge/` (3 pre-existing in `app/core/agents/`, unrelated)
- **Pyright:** 0 errors on `app/core/config.py`

## Files to Create/Modify

| Action | File | Purpose |
|--------|------|---------|
| CREATE | `app/knowledge/hyde.py` | HyDEExpander class — LLM-based query expansion |
| UPDATE | `app/knowledge/service.py:400-419` | Call HyDE expander before embedding query |
| UPDATE | `app/core/config.py:211` | Add `knowledge_hyde_enabled`, `knowledge_hyde_model`, `knowledge_hyde_max_tokens` settings |
| CREATE | `app/knowledge/tests/test_hyde.py` | Unit tests for HyDE expander + search integration |

## Implementation Steps

### Step 1: Add config settings (`app/core/config.py`)

After line 211 (`auto_tag_max_chars`), add:

```python
    # HyDE query expansion (generate hypothetical answer before embedding)
    knowledge_hyde_enabled: bool = False
    knowledge_hyde_model: str | None = None  # None = use llm_fast or primary model
    knowledge_hyde_max_tokens: int = 200
```

**Validation:** `uv run ruff format app/core/config.py && uv run ruff check --fix app/core/config.py && uv run pyright app/core/config.py`

### Step 2: Create HyDE expander (`app/knowledge/hyde.py`)

Create `app/knowledge/hyde.py` with:

```python
"""HyDE (Hypothetical Document Embeddings) query expansion.

Generates a hypothetical answer to a query using a fast LLM,
then embeds that answer instead of the raw query. Improves
retrieval quality for low-resource languages like Latvian.
"""

from __future__ import annotations

import time

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_HYDE_SYSTEM_PROMPT = (
    "You are a transit operations knowledge assistant. "
    "Given a question, write a short paragraph that would appear in an "
    "internal document answering it. Write in the same language as the "
    "question. Be specific and factual. Do not include greetings or "
    "meta-commentary — output ONLY the answer paragraph."
)


def _resolve_model(settings: Settings) -> str:
    """Resolve the model string for HyDE expansion.

    Priority: knowledge_hyde_model > llm_fast > primary model.
    """
    if settings.knowledge_hyde_model:
        return settings.knowledge_hyde_model

    if settings.llm_fast_provider and settings.llm_fast_model:
        return f"{settings.llm_fast_provider}:{settings.llm_fast_model}"

    return f"{settings.llm_provider}:{settings.llm_model}"


async def expand_query(query: str, settings: Settings | None = None) -> str:
    """Generate a hypothetical document answering the query.

    Uses a fast/cheap LLM to produce document-like text that embeds
    closer to actual knowledge base documents than the raw query.

    Args:
        query: The user's search query.
        settings: Optional settings override (for testing).

    Returns:
        Hypothetical answer text to embed instead of the raw query.
        Falls back to the original query on any error.
    """
    from pydantic_ai import Agent

    if settings is None:
        settings = get_settings()

    model_str = _resolve_model(settings)
    start = time.monotonic()

    try:
        agent = Agent(
            model_str,
            system_prompt=_HYDE_SYSTEM_PROMPT,
        )
        result = await agent.run(query)
        expanded = str(result.response).strip()

        # Truncate to max_tokens * ~4 chars/token as safety bound
        max_chars = settings.knowledge_hyde_max_tokens * 4
        if len(expanded) > max_chars:
            expanded = expanded[:max_chars]

        elapsed_ms = (time.monotonic() - start) * 1000
        logger.info(
            "knowledge.hyde.expansion_completed",
            query_length=len(query),
            expanded_length=len(expanded),
            model=model_str,
            elapsed_ms=round(elapsed_ms, 1),
        )
        return expanded

    except Exception as e:
        elapsed_ms = (time.monotonic() - start) * 1000
        logger.warning(
            "knowledge.hyde.expansion_failed",
            query_length=len(query),
            error=str(e),
            error_type=type(e).__name__,
            elapsed_ms=round(elapsed_ms, 1),
        )
        # Graceful degradation — fall back to raw query
        return query
```

**Design decisions:**
- Module-level function (not class) — matches VTV's pattern for stateless operations
- Falls back to raw query on error — search always works, HyDE is best-effort
- Model resolution: dedicated HyDE model > fast tier > primary model
- Lazy import of `pydantic_ai.Agent` — matches auto-tagging pattern
- Structured logging with `knowledge.hyde.*` domain

**Validation:** `uv run ruff format app/knowledge/hyde.py && uv run ruff check --fix app/knowledge/hyde.py && uv run pyright app/knowledge/hyde.py`

### Step 3: Integrate HyDE into search flow (`app/knowledge/service.py`)

**3a.** Add import at top (after line 20):

```python
from app.knowledge import chunking, hyde, processing
```

(Modify existing `from app.knowledge import chunking, processing` to include `hyde`.)

**3b.** In `search()` method, replace lines 418-419:

```python
        # Get query embedding
        query_embedding = (await _get_embedding().embed([request.query]))[0]
```

With:

```python
        # HyDE: optionally expand query before embedding
        embed_text = request.query
        if settings.knowledge_hyde_enabled:
            embed_text = await hyde.expand_query(request.query, settings)

        # Get query embedding (use expanded text for vector, raw query for fulltext)
        query_embedding = (await _get_embedding().embed([embed_text]))[0]
```

The fulltext search on line 431 already uses `request.query` (raw), which is correct — HyDE only affects vector search.

**Validation:** `uv run ruff format app/knowledge/service.py && uv run ruff check --fix app/knowledge/service.py && uv run pyright app/knowledge/service.py`

### Step 4: Create tests (`app/knowledge/tests/test_hyde.py`)

```python
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


def test_resolve_model_dedicated_hyde_model():
    """Dedicated HyDE model takes priority."""
    settings = MagicMock()
    settings.knowledge_hyde_model = "groq:llama-3-8b"
    assert _resolve_model(settings) == "groq:llama-3-8b"


def test_resolve_model_fast_tier_fallback():
    """Falls back to fast-tier model when no dedicated HyDE model."""
    settings = MagicMock()
    settings.knowledge_hyde_model = None
    settings.llm_fast_provider = "groq"
    settings.llm_fast_model = "llama-3-8b"
    assert _resolve_model(settings) == "groq:llama-3-8b"


def test_resolve_model_primary_fallback():
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
async def test_expand_query_success():
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
async def test_expand_query_llm_failure_returns_original():
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
async def test_expand_query_truncates_long_output():
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
async def test_search_uses_hyde_when_enabled():
    """Search embeds HyDE-expanded text when enabled."""
    from app.knowledge.service import KnowledgeService

    mock_db = AsyncMock()
    service = KnowledgeService(mock_db)

    # Mock repository search methods
    service.repository.search_vector = AsyncMock(return_value=[])
    service.repository.search_fulltext = AsyncMock(return_value=[])

    mock_embedding = MagicMock()
    mock_embedding.embed = AsyncMock(return_value=[[0.1] * 1024])

    with (
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

    # HyDE should have been called with the raw query
    mock_expand.assert_awaited_once_with("test query", s)
    # Embedding should use the expanded text, not raw query
    mock_embedding.embed.assert_awaited_once_with(["Expanded hypothetical answer"])


@pytest.mark.asyncio
async def test_search_skips_hyde_when_disabled():
    """Search embeds raw query when HyDE is disabled."""
    from app.knowledge.service import KnowledgeService

    mock_db = AsyncMock()
    service = KnowledgeService(mock_db)

    service.repository.search_vector = AsyncMock(return_value=[])
    service.repository.search_fulltext = AsyncMock(return_value=[])

    mock_embedding = MagicMock()
    mock_embedding.embed = AsyncMock(return_value=[[0.1] * 1024])

    with (
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

    # HyDE should NOT have been called
    mock_expand.assert_not_awaited()
    # Embedding should use raw query
    mock_embedding.embed.assert_awaited_once_with(["test query"])
```

**Validation:** `uv run ruff format app/knowledge/tests/test_hyde.py && uv run ruff check --fix app/knowledge/tests/test_hyde.py && uv run pytest app/knowledge/tests/test_hyde.py -v`

## Preflight Warnings

- `app/knowledge/service.py:419` — line being modified is a one-liner with no fragile tuple unpacking
- Auto-tagging pattern (lines 758-807) uses lazy `from pydantic_ai import Agent` — HyDE should follow same pattern
- Module-level singletons (`_embedding_provider`, `_reranker_provider`) are not thread-safe but work in asyncio — no concern for HyDE (creates fresh Agent per call)
- `test_autotag.py` line 1 has pyright directives — new `test_hyde.py` must copy the same directives

## Security Checklist

No new endpoints — internal pipeline change only.

- [x] No credentials in LLM prompt or logged output
- [x] LLM output used only for embedding (never displayed to user) — mitigates prompt injection
- [x] Graceful degradation on LLM failure (falls back to raw query)
- [x] Output truncated to prevent embedding oversized text
- [x] Feature disabled by default (`knowledge_hyde_enabled: bool = False`)

## Verification

- [ ] `make lint` passes (ruff format + check)
- [ ] `make types` passes (mypy + pyright)
- [ ] `uv run pytest app/knowledge/tests/test_hyde.py -v` — all 8 tests pass
- [ ] `make test` passes — no regressions in existing 1027 tests
- [ ] Pyright errors ≤ baseline (0 errors before)
- [ ] `make security-audit-quick` passes
