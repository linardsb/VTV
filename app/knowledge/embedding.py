# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportMissingImports=false
"""Configurable embedding provider for document vectorization.

Supports OpenAI API, Jina API (OpenAI-compatible), and local
sentence-transformers models. Provider selected via EMBEDDING_PROVIDER setting.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
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


def _normalize_query(text: str) -> str:
    """Normalize text for cache key consistency.

    Lowercases, strips whitespace, sorts words so
    'route 3 status' and 'status route 3' produce the same key.

    Args:
        text: Raw query text.

    Returns:
        Normalized text for hashing.
    """
    return " ".join(sorted(text.lower().split()))


class CachedEmbeddingProvider:
    """Decorator that adds Redis caching to any EmbeddingProvider.

    Cache key: emb:{provider}:{blake2b(normalized_text)[:16]}
    Value: JSON-serialized float list
    TTL: Configurable via settings.embedding_cache_ttl

    Falls back to the wrapped provider on any Redis error.
    """

    def __init__(
        self,
        provider: EmbeddingProvider,
        provider_name: str,
        ttl: int,
    ) -> None:
        self._provider = provider
        self._provider_name = provider_name
        self._ttl = ttl

    def _cache_key(self, text: str) -> str:
        normalized = _normalize_query(text)
        digest = hashlib.blake2b(normalized.encode(), digest_size=8).hexdigest()
        return f"emb:{self._provider_name}:{digest}"

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts with per-text Redis cache lookup.

        For each text: check cache -> on hit, use cached vector;
        on miss, batch-embed all misses via the wrapped provider,
        then store results in Redis.

        Args:
            texts: Texts to embed.

        Returns:
            List of embedding vectors (same order as input).
        """
        try:
            from app.core.redis import get_redis

            redis_client = await get_redis()
        except Exception:
            logger.warning("knowledge.embedding_cache.redis_unavailable")
            return await self._provider.embed(texts)

        keys = [self._cache_key(t) for t in texts]
        results: list[list[float] | None] = [None] * len(texts)
        miss_indices: list[int] = []

        # Batch cache lookup
        try:
            cached_values = await redis_client.mget(keys)
            for i, val in enumerate(cached_values):
                if val is not None:
                    results[i] = json.loads(val)
            miss_indices = [i for i, r in enumerate(results) if r is None]
        except Exception:
            logger.warning("knowledge.embedding_cache.read_failed")
            miss_indices = list(range(len(texts)))

        cache_hits = len(texts) - len(miss_indices)
        if cache_hits > 0:
            logger.info(
                "knowledge.embedding_cache.hit",
                hits=cache_hits,
                total=len(texts),
            )

        if not miss_indices:
            return [r for r in results if r is not None]

        # Embed cache misses
        miss_texts = [texts[i] for i in miss_indices]
        logger.info(
            "knowledge.embedding_cache.miss",
            misses=len(miss_indices),
            total=len(texts),
        )
        fresh_embeddings = await self._provider.embed(miss_texts)

        # Store in cache (fire-and-forget, don't block on write errors)
        try:
            pipe = redis_client.pipeline()
            for idx, embedding in zip(miss_indices, fresh_embeddings, strict=True):
                pipe.setex(keys[idx], self._ttl, json.dumps(embedding))
            await pipe.execute()
        except Exception:
            logger.warning("knowledge.embedding_cache.write_failed")

        # Merge cached + fresh
        for idx, embedding in zip(miss_indices, fresh_embeddings, strict=True):
            results[idx] = embedding

        return [r for r in results if r is not None]

    @property
    def dimension(self) -> int:
        """Return the embedding dimension."""
        return self._provider.dimension


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
