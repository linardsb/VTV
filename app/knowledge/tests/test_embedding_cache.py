# pyright: reportUnknownMemberType=false
"""Tests for embedding cache (CachedEmbeddingProvider + _normalize_query)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.knowledge.embedding import CachedEmbeddingProvider, _normalize_query

# ---------------------------------------------------------------------------
# Query normalization
# ---------------------------------------------------------------------------


class TestNormalizeQuery:
    def test_basic(self) -> None:
        assert _normalize_query("  Route 3 Status  ") == "3 route status"

    def test_idempotent(self) -> None:
        result = _normalize_query("route 3 status")
        assert _normalize_query(result) == result

    def test_word_order_invariant(self) -> None:
        assert _normalize_query("route 3") == _normalize_query("3 route")


# ---------------------------------------------------------------------------
# Cache key generation
# ---------------------------------------------------------------------------


class TestCacheKey:
    def _provider(self) -> CachedEmbeddingProvider:
        mock_inner = AsyncMock()
        mock_inner.dimension = 1024
        return CachedEmbeddingProvider(provider=mock_inner, provider_name="jina", ttl=3600)

    def test_deterministic(self) -> None:
        p = self._provider()
        assert p._cache_key("hello") == p._cache_key("hello")

    def test_includes_provider(self) -> None:
        p = self._provider()
        assert p._cache_key("hello").startswith("emb:jina:")

    def test_different_text(self) -> None:
        p = self._provider()
        assert p._cache_key("hello") != p._cache_key("world")


# ---------------------------------------------------------------------------
# Cache hit / miss
# ---------------------------------------------------------------------------


class TestCacheHitMiss:
    @staticmethod
    def _make_redis_mock(
        mget_return: list[str | None],
    ) -> AsyncMock:
        mock_redis = AsyncMock()
        mock_redis.mget = AsyncMock(return_value=mget_return)
        mock_pipeline = MagicMock()
        mock_pipeline.setex = MagicMock()
        mock_pipeline.execute = AsyncMock(return_value=[])
        mock_redis.pipeline = MagicMock(return_value=mock_pipeline)
        return mock_redis

    @pytest.mark.asyncio
    async def test_all_cache_hits(self) -> None:
        inner = AsyncMock()
        inner.dimension = 1024
        cached = CachedEmbeddingProvider(provider=inner, provider_name="jina", ttl=3600)

        mock_redis = self._make_redis_mock(["[1.0, 2.0]", "[3.0, 4.0]"])
        with patch(
            "app.core.redis.get_redis",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            result = await cached.embed(["a", "b"])

        assert result == [[1.0, 2.0], [3.0, 4.0]]
        inner.embed.assert_not_called()

    @pytest.mark.asyncio
    async def test_all_cache_misses(self) -> None:
        inner = AsyncMock()
        inner.dimension = 1024
        inner.embed = AsyncMock(return_value=[[1.0], [2.0]])
        cached = CachedEmbeddingProvider(provider=inner, provider_name="jina", ttl=3600)

        mock_redis = self._make_redis_mock([None, None])
        with patch(
            "app.core.redis.get_redis",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            result = await cached.embed(["a", "b"])

        assert result == [[1.0], [2.0]]
        inner.embed.assert_called_once_with(["a", "b"])
        mock_redis.pipeline().setex.assert_called()

    @pytest.mark.asyncio
    async def test_partial_cache_hit(self) -> None:
        inner = AsyncMock()
        inner.dimension = 1024
        inner.embed = AsyncMock(return_value=[[9.0]])
        cached = CachedEmbeddingProvider(provider=inner, provider_name="jina", ttl=3600)

        mock_redis = self._make_redis_mock(["[1.0, 2.0]", None])
        with patch(
            "app.core.redis.get_redis",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            result = await cached.embed(["a", "b"])

        assert result == [[1.0, 2.0], [9.0]]
        inner.embed.assert_called_once_with(["b"])


# ---------------------------------------------------------------------------
# Redis error fallback
# ---------------------------------------------------------------------------


class TestRedisFallback:
    @pytest.mark.asyncio
    async def test_redis_unavailable_falls_back(self) -> None:
        inner = AsyncMock()
        inner.dimension = 1024
        inner.embed = AsyncMock(return_value=[[1.0]])
        cached = CachedEmbeddingProvider(provider=inner, provider_name="jina", ttl=3600)

        with patch(
            "app.core.redis.get_redis",
            new_callable=AsyncMock,
            side_effect=ConnectionError("no redis"),
        ):
            result = await cached.embed(["a"])

        assert result == [[1.0]]
        inner.embed.assert_called_once_with(["a"])

    @pytest.mark.asyncio
    async def test_redis_read_error_falls_back(self) -> None:
        inner = AsyncMock()
        inner.dimension = 1024
        inner.embed = AsyncMock(return_value=[[1.0], [2.0]])
        cached = CachedEmbeddingProvider(provider=inner, provider_name="jina", ttl=3600)

        mock_redis = AsyncMock()
        mock_redis.mget = AsyncMock(side_effect=RuntimeError("read fail"))
        mock_pipeline = MagicMock()
        mock_pipeline.setex = MagicMock()
        mock_pipeline.execute = AsyncMock(return_value=[])
        mock_redis.pipeline = MagicMock(return_value=mock_pipeline)

        with patch(
            "app.core.redis.get_redis",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            result = await cached.embed(["a", "b"])

        assert result == [[1.0], [2.0]]
        inner.embed.assert_called_once_with(["a", "b"])

    @pytest.mark.asyncio
    async def test_redis_write_error_still_returns(self) -> None:
        inner = AsyncMock()
        inner.dimension = 1024
        inner.embed = AsyncMock(return_value=[[1.0]])
        cached = CachedEmbeddingProvider(provider=inner, provider_name="jina", ttl=3600)

        mock_redis = AsyncMock()
        mock_redis.mget = AsyncMock(return_value=[None])
        mock_pipeline = MagicMock()
        mock_pipeline.setex = MagicMock()
        mock_pipeline.execute = AsyncMock(side_effect=RuntimeError("write fail"))
        mock_redis.pipeline = MagicMock(return_value=mock_pipeline)

        with patch(
            "app.core.redis.get_redis",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            result = await cached.embed(["a"])

        assert result == [[1.0]]


# ---------------------------------------------------------------------------
# Integration with service singleton
# ---------------------------------------------------------------------------


class TestServiceIntegration:
    @patch("app.knowledge.service.get_embedding_provider")
    @patch("app.knowledge.service.get_settings")
    def test_returns_cached_provider_when_enabled(
        self, mock_settings: MagicMock, mock_get_provider: MagicMock
    ) -> None:
        import app.knowledge.service as svc

        svc._embedding_provider = None  # reset singleton

        settings = MagicMock()
        settings.embedding_cache_enabled = True
        settings.embedding_cache_ttl = 600
        settings.embedding_provider = "jina"
        mock_settings.return_value = settings

        inner = AsyncMock()
        inner.dimension = 1024
        mock_get_provider.return_value = inner

        result = svc._get_embedding()
        assert isinstance(result, CachedEmbeddingProvider)
        svc._embedding_provider = None  # cleanup

    @patch("app.knowledge.service.get_embedding_provider")
    @patch("app.knowledge.service.get_settings")
    def test_returns_raw_provider_when_disabled(
        self, mock_settings: MagicMock, mock_get_provider: MagicMock
    ) -> None:
        import app.knowledge.service as svc

        svc._embedding_provider = None  # reset singleton

        settings = MagicMock()
        settings.embedding_cache_enabled = False
        mock_settings.return_value = settings

        inner = AsyncMock()
        inner.dimension = 1024
        mock_get_provider.return_value = inner

        result = svc._get_embedding()
        assert not isinstance(result, CachedEmbeddingProvider)
        svc._embedding_provider = None  # cleanup
