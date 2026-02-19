# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportMissingImports=false
"""Configurable cross-encoder reranker for search result refinement.

Supports local sentence-transformers CrossEncoder or no-op pass-through.
Provider selected via RERANKER_PROVIDER setting.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Protocol

from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class RerankResult:
    """A reranked document with its relevance score."""

    index: int
    score: float
    content: str


class RerankerProvider(Protocol):
    """Protocol for reranker providers."""

    async def rerank(self, query: str, documents: list[str], top_k: int = 10) -> list[RerankResult]:
        """Rerank documents by relevance to query.

        Args:
            query: The search query.
            documents: List of document texts to rerank.
            top_k: Number of top results to return.

        Returns:
            Reranked results sorted by score descending.
        """
        ...


class LocalRerankerProvider:
    """Reranker using local sentence-transformers CrossEncoder.

    Model is lazy-loaded on first use. Inference runs in
    asyncio.to_thread() to avoid blocking the event loop.
    """

    def __init__(self, model_name: str) -> None:
        """Initialize local reranker.

        Args:
            model_name: HuggingFace model name.
        """
        self._model_name = model_name
        # Any: sentence-transformers lacks py.typed
        self._model: Any | None = None

    def _get_model(self) -> Any:  # noqa: ANN401 — untyped lib (sentence-transformers)
        """Lazy-load the CrossEncoder model."""
        if self._model is None:
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(self._model_name)
        return self._model

    async def rerank(self, query: str, documents: list[str], top_k: int = 10) -> list[RerankResult]:
        """Rerank documents using cross-encoder scoring.

        Args:
            query: The search query.
            documents: List of document texts to rerank.
            top_k: Number of top results to return.

        Returns:
            Top-k results sorted by score descending.
        """
        if not documents:
            return []

        start = time.monotonic()
        logger.info(
            "knowledge.reranking.started",
            candidate_count=len(documents),
            top_k=top_k,
        )

        model = self._get_model()
        pairs = [(query, doc) for doc in documents]
        raw_scores = await asyncio.to_thread(model.predict, pairs)

        scored: list[RerankResult] = []
        for i, doc in enumerate(documents):
            score_val: float = float(raw_scores[i])
            scored.append(RerankResult(index=i, score=score_val, content=doc))

        scored.sort(key=lambda r: r.score, reverse=True)

        duration_ms = int((time.monotonic() - start) * 1000)
        logger.info(
            "knowledge.reranking.completed",
            candidate_count=len(documents),
            top_k=top_k,
            duration_ms=duration_ms,
        )

        return scored[:top_k]


class NoopRerankerProvider:
    """Pass-through reranker that preserves original order."""

    async def rerank(self, query: str, documents: list[str], top_k: int = 10) -> list[RerankResult]:
        """Return documents in original order with score 1.0.

        Args:
            query: The search query (unused).
            documents: List of document texts.
            top_k: Number of top results to return.

        Returns:
            Results in original order, truncated to top_k.
        """
        _ = query  # Required by protocol but unused in noop
        return [
            RerankResult(index=i, score=1.0, content=doc) for i, doc in enumerate(documents[:top_k])
        ]


def get_reranker_provider(settings: Settings) -> RerankerProvider:
    """Create a reranker provider based on application settings.

    Args:
        settings: Application settings with reranker configuration.

    Returns:
        Configured reranker provider.

    Raises:
        ValueError: If reranker_provider setting is unknown.
    """
    provider = settings.reranker_provider.lower()

    if provider == "local":
        return LocalRerankerProvider(model_name=settings.reranker_model)

    if provider == "none":
        return NoopRerankerProvider()

    msg = f"Unknown reranker provider: {provider}"
    raise ValueError(msg)
