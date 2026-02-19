# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportMissingImports=false
"""Configurable embedding provider for document vectorization.

Supports OpenAI API, Jina API (OpenAI-compatible), and local
sentence-transformers models. Provider selected via EMBEDDING_PROVIDER setting.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Protocol

import openai

from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class EmbeddingProvider(Protocol):
    """Protocol for embedding providers."""

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of texts into vectors.

        Args:
            texts: Texts to embed.

        Returns:
            List of embedding vectors.
        """
        ...

    @property
    def dimension(self) -> int:
        """Return the embedding dimension."""
        ...


class OpenAIEmbeddingProvider:
    """Embedding provider using OpenAI or Jina API (OpenAI-compatible)."""

    def __init__(
        self,
        model: str,
        api_key: str,
        dim: int,
        base_url: str | None = None,
    ) -> None:
        """Initialize OpenAI embedding provider.

        Args:
            model: Model name (e.g., text-embedding-3-large).
            api_key: API key for authentication.
            dim: Embedding dimension.
            base_url: Optional custom base URL for Jina/other providers.
        """
        self._model = model
        self._dimension = dim
        self._client = openai.AsyncOpenAI(api_key=api_key, base_url=base_url)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts using OpenAI API with batching for >100 texts.

        Args:
            texts: Texts to embed.

        Returns:
            List of embedding vectors.
        """
        start = time.monotonic()
        logger.info("knowledge.embedding.started", text_count=len(texts))

        all_embeddings: list[list[float]] = []
        batch_size = 100

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            response = await self._client.embeddings.create(
                model=self._model,
                input=batch,
            )
            all_embeddings.extend([d.embedding for d in response.data])

        duration_ms = int((time.monotonic() - start) * 1000)
        logger.info(
            "knowledge.embedding.completed",
            text_count=len(texts),
            dimension=self._dimension,
            duration_ms=duration_ms,
        )
        return all_embeddings

    @property
    def dimension(self) -> int:
        """Return the embedding dimension."""
        return self._dimension


class LocalEmbeddingProvider:
    """Embedding provider using local sentence-transformers model.

    Model is lazy-loaded on first use to avoid GPU dependency at startup.
    All inference runs in asyncio.to_thread() to avoid blocking the event loop.
    """

    def __init__(self, model_name: str, dim: int) -> None:
        """Initialize local embedding provider.

        Args:
            model_name: HuggingFace model name (e.g., BAAI/bge-m3).
            dim: Embedding dimension.
        """
        self._model_name = model_name
        self._dimension = dim
        # Any: sentence-transformers lacks py.typed
        self._model: Any | None = None

    def _get_model(self) -> Any:  # noqa: ANN401 — untyped lib (sentence-transformers)
        """Lazy-load the SentenceTransformer model."""
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self._model_name)
        return self._model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts using local model in a thread pool.

        Args:
            texts: Texts to embed.

        Returns:
            List of embedding vectors.
        """
        start = time.monotonic()
        logger.info("knowledge.embedding.started", text_count=len(texts))

        model = self._get_model()
        # CPU-bound: must use to_thread
        raw = await asyncio.to_thread(model.encode, texts)
        embeddings: list[list[float]] = raw.tolist()

        duration_ms = int((time.monotonic() - start) * 1000)
        logger.info(
            "knowledge.embedding.completed",
            text_count=len(texts),
            dimension=self._dimension,
            duration_ms=duration_ms,
        )
        return embeddings

    @property
    def dimension(self) -> int:
        """Return the embedding dimension."""
        return self._dimension


def get_embedding_provider(settings: Settings) -> EmbeddingProvider:
    """Create an embedding provider based on application settings.

    Args:
        settings: Application settings with embedding configuration.

    Returns:
        Configured embedding provider.

    Raises:
        ValueError: If embedding_provider setting is unknown.
    """
    provider = settings.embedding_provider.lower()

    if provider in ("openai", "jina"):
        return OpenAIEmbeddingProvider(
            model=settings.embedding_model,
            api_key=settings.embedding_api_key or "",
            dim=settings.embedding_dimension,
            base_url=settings.embedding_base_url,
        )

    if provider == "local":
        return LocalEmbeddingProvider(
            model_name=settings.embedding_model,
            dim=settings.embedding_dimension,
        )

    msg = f"Unknown embedding provider: {provider}"
    raise ValueError(msg)
