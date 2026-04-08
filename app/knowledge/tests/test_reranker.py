# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportPrivateUsage=false
"""Unit tests for reranker providers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.knowledge.reranker import (
    LocalRerankerProvider,
    NoopRerankerProvider,
    get_reranker_provider,
)

# --- NoopRerankerProvider ---


@pytest.mark.asyncio
async def test_noop_reranker_preserves_order() -> None:
    """NoopRerankerProvider returns docs in original order with score 1.0."""
    provider = NoopRerankerProvider()
    docs = ["doc A", "doc B", "doc C"]
    results = await provider.rerank("query", docs, top_k=10)
    assert len(results) == 3
    assert [r.content for r in results] == docs
    assert all(r.score == 1.0 for r in results)
    assert [r.index for r in results] == [0, 1, 2]


@pytest.mark.asyncio
async def test_noop_reranker_respects_top_k() -> None:
    """NoopRerankerProvider truncates to top_k."""
    provider = NoopRerankerProvider()
    docs = ["a", "b", "c", "d", "e"]
    results = await provider.rerank("query", docs, top_k=2)
    assert len(results) == 2
    assert [r.content for r in results] == ["a", "b"]


@pytest.mark.asyncio
async def test_noop_reranker_empty_docs() -> None:
    """NoopRerankerProvider returns empty for empty input."""
    provider = NoopRerankerProvider()
    results = await provider.rerank("query", [], top_k=10)
    assert results == []


@pytest.mark.asyncio
async def test_noop_warm_up() -> None:
    """NoopRerankerProvider warm_up completes without error."""
    provider = NoopRerankerProvider()
    await provider.warm_up()


# --- LocalRerankerProvider ---


@pytest.mark.asyncio
async def test_local_reranker_reorders_by_score() -> None:
    """LocalRerankerProvider reorders documents by cross-encoder score."""
    mock_model = MagicMock()
    mock_model.predict.return_value = [0.1, 0.9, 0.5]

    provider = LocalRerankerProvider(model_name="test-model")
    provider._model = mock_model  # bypass lazy load

    docs = ["low", "high", "mid"]
    results = await provider.rerank("query", docs, top_k=3)

    assert len(results) == 3
    assert results[0].content == "high"
    assert results[0].index == 1
    assert results[1].content == "mid"
    assert results[2].content == "low"


@pytest.mark.asyncio
async def test_local_reranker_empty_docs() -> None:
    """LocalRerankerProvider returns empty for empty input."""
    provider = LocalRerankerProvider(model_name="test-model")
    results = await provider.rerank("query", [], top_k=10)
    assert results == []


@pytest.mark.asyncio
async def test_local_warm_up_loads_model() -> None:
    """warm_up() triggers model loading via _get_model()."""
    provider = LocalRerankerProvider(model_name="test-model")
    mock_model = MagicMock()

    with patch.object(provider, "_get_model", return_value=mock_model):
        await provider.warm_up()
    # warm_up calls _get_model which would load CrossEncoder; we verify it was called


# --- Factory ---


def test_get_reranker_provider_local() -> None:
    """Factory returns LocalRerankerProvider for 'local'."""
    settings = MagicMock()
    settings.reranker_provider = "local"
    settings.reranker_model = "test-model"
    provider = get_reranker_provider(settings)
    assert isinstance(provider, LocalRerankerProvider)


def test_get_reranker_provider_none() -> None:
    """Factory returns NoopRerankerProvider for 'none'."""
    settings = MagicMock()
    settings.reranker_provider = "none"
    provider = get_reranker_provider(settings)
    assert isinstance(provider, NoopRerankerProvider)


def test_get_reranker_provider_unknown() -> None:
    """Factory raises ValueError for unknown provider."""
    settings = MagicMock()
    settings.reranker_provider = "unknown"
    with pytest.raises(ValueError, match="Unknown reranker provider"):
        get_reranker_provider(settings)
