# pyright: reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportCallIssue=false, reportArgumentType=false, reportPrivateUsage=false
"""Unit tests for KB-4 search feedback service."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from redis.exceptions import RedisError

from app.core.config import get_settings
from app.knowledge.exceptions import FeedbackChunkNotFoundError
from app.knowledge.feedback import (
    _WEIGHTS_KEY_PREFIX,
    _WEIGHTS_TTL_SECONDS,
    FeedbackService,
    compute_query_hash,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_redis_mock() -> AsyncMock:
    """Minimal Redis mock with async get/set."""
    r = AsyncMock()
    r.get = AsyncMock(return_value=None)
    r.set = AsyncMock(return_value=True)
    return r


def _service_with_repo(
    counts_return: dict[tuple[str, str], dict[str, int]],
) -> tuple[
    FeedbackService,
    MagicMock,
    AsyncMock,
]:
    """Build a FeedbackService with a mocked repository and Redis."""
    mock_db = AsyncMock()
    mock_redis = _make_redis_mock()
    service = FeedbackService(mock_db, mock_redis)
    repo = MagicMock()
    repo.chunk_exists = AsyncMock(return_value=True)
    repo.upsert_feedback = AsyncMock(return_value=MagicMock(id=1))
    repo.feedback_counts = AsyncMock(return_value=counts_return)
    service.repository = repo
    return service, repo, mock_redis


# ---------------------------------------------------------------------------
# compute_query_hash
# ---------------------------------------------------------------------------


class TestComputeQueryHash:
    def test_deterministic(self) -> None:
        assert compute_query_hash("route 13", "transit") == compute_query_hash(
            "route 13", "transit"
        )

    def test_whitespace_and_case_normalized(self) -> None:
        assert compute_query_hash("Route  13", "transit") == compute_query_hash(
            "route 13", "transit"
        )

    def test_different_domains_produce_different_hashes(self) -> None:
        assert compute_query_hash("route 13", "transit") != compute_query_hash("route 13", "safety")

    def test_hex_and_length(self) -> None:
        h = compute_query_hash("foo", None)
        assert len(h) == 32
        assert all(c in "0123456789abcdef" for c in h)


# ---------------------------------------------------------------------------
# record
# ---------------------------------------------------------------------------


class TestRecord:
    @pytest.mark.asyncio
    async def test_happy_path_calls_repo(self) -> None:
        service, repo, _redis = _service_with_repo({})
        await service.record(
            user_id=7,
            query_hash="a" * 32,
            query_type="keyword",
            chunk_id=42,
            rank_source="vector",
            relevant=True,
        )
        repo.upsert_feedback.assert_awaited_once()
        kwargs = repo.upsert_feedback.call_args.kwargs
        assert kwargs["user_id"] == 7
        assert kwargs["chunk_id"] == 42
        assert kwargs["rank_source"] == "vector"
        assert kwargs["relevant"] is True

    @pytest.mark.asyncio
    async def test_missing_chunk_raises(self) -> None:
        service, repo, _redis = _service_with_repo({})
        repo.chunk_exists = AsyncMock(return_value=False)
        with pytest.raises(FeedbackChunkNotFoundError):
            await service.record(
                user_id=1,
                query_hash="a" * 32,
                query_type="keyword",
                chunk_id=999,
                rank_source="vector",
                relevant=True,
            )
        repo.upsert_feedback.assert_not_called()


# ---------------------------------------------------------------------------
# recompute_weights
# ---------------------------------------------------------------------------


class TestRecomputeWeights:
    @pytest.mark.asyncio
    async def test_below_min_signals_skips_type(self) -> None:
        # 5 total < default min_signals_per_type=20
        counts: dict[tuple[str, str], dict[str, int]] = {
            ("keyword", "vector"): {"up": 3, "down": 1},
            ("keyword", "fulltext"): {"up": 1, "down": 0},
        }
        service, _repo, redis = _service_with_repo(counts)
        result = await service.recompute_weights()
        assert result == {}
        redis.set.assert_not_called()

    @pytest.mark.asyncio
    async def test_keyword_vector_preferred_shifts_up(self) -> None:
        # 30 up-votes on vector for keyword → tuned vector share moves above
        # static default (0.3). Blend 70% tuned + 30% static keeps shift real.
        counts: dict[tuple[str, str], dict[str, int]] = {
            ("keyword", "vector"): {"up": 30, "down": 0},
            ("keyword", "fulltext"): {"up": 0, "down": 5},
        }
        service, _repo, redis = _service_with_repo(counts)
        result = await service.recompute_weights()
        assert "keyword" in result
        assert result["keyword"].vector_weight > get_settings().rrf_keyword_vector_weight
        assert result["keyword"].text_weight == pytest.approx(
            1 - result["keyword"].vector_weight, abs=1e-3
        )
        redis.set.assert_awaited()

    @pytest.mark.asyncio
    async def test_clamped_to_safety_bounds(self) -> None:
        # Adversarial 100% one-sided feedback — should clamp to [0.1, 0.9].
        counts: dict[tuple[str, str], dict[str, int]] = {
            ("mixed", "vector"): {"up": 100, "down": 0},
            ("mixed", "fulltext"): {"up": 0, "down": 100},
        }
        service, _repo, _redis = _service_with_repo(counts)
        result = await service.recompute_weights()
        assert 0.1 <= result["mixed"].vector_weight <= 0.9
        assert 0.1 <= result["mixed"].text_weight <= 0.9

    @pytest.mark.asyncio
    async def test_writes_redis_with_ttl(self) -> None:
        counts: dict[tuple[str, str], dict[str, int]] = {
            ("semantic", "vector"): {"up": 15, "down": 5},
            ("semantic", "fulltext"): {"up": 5, "down": 15},
        }
        service, _repo, redis = _service_with_repo(counts)
        await service.recompute_weights()
        redis.set.assert_awaited()
        call = redis.set.await_args_list[0]
        assert call.args[0] == _WEIGHTS_KEY_PREFIX + "semantic"
        assert call.kwargs["ex"] == _WEIGHTS_TTL_SECONDS

    @pytest.mark.asyncio
    async def test_redis_error_during_write_is_swallowed(self) -> None:
        counts: dict[tuple[str, str], dict[str, int]] = {
            ("keyword", "vector"): {"up": 30, "down": 0},
            ("keyword", "fulltext"): {"up": 0, "down": 0},
        }
        service, _repo, redis = _service_with_repo(counts)
        redis.set = AsyncMock(side_effect=RedisError("boom"))
        result = await service.recompute_weights()
        assert result == {}


# ---------------------------------------------------------------------------
# get_tuned_weights
# ---------------------------------------------------------------------------


class TestGetTunedWeights:
    @pytest.mark.asyncio
    async def test_returns_tuned_when_key_present(self) -> None:
        service, _repo, redis = _service_with_repo({})
        payload = {"vector_weight": 0.55, "text_weight": 0.45}
        redis.get = AsyncMock(return_value=json.dumps(payload))
        vec, txt = await service.get_tuned_weights("keyword")
        assert vec == 0.55
        assert txt == 0.45

    @pytest.mark.asyncio
    async def test_fallback_on_missing_key(self) -> None:
        service, _repo, redis = _service_with_repo({})
        redis.get = AsyncMock(return_value=None)
        vec, txt = await service.get_tuned_weights("keyword")
        settings = get_settings()
        assert vec == settings.rrf_keyword_vector_weight
        assert txt == settings.rrf_keyword_text_weight

    @pytest.mark.asyncio
    async def test_fallback_on_redis_error(self) -> None:
        service, _repo, redis = _service_with_repo({})
        redis.get = AsyncMock(side_effect=RedisError("down"))
        vec, txt = await service.get_tuned_weights("semantic")
        settings = get_settings()
        assert vec == settings.rrf_semantic_vector_weight
        assert txt == settings.rrf_semantic_text_weight

    @pytest.mark.asyncio
    async def test_fallback_on_corrupt_payload(self) -> None:
        service, _repo, redis = _service_with_repo({})
        redis.get = AsyncMock(return_value="not-json{")
        vec, txt = await service.get_tuned_weights("mixed")
        settings = get_settings()
        assert vec == settings.rrf_mixed_vector_weight
        assert txt == settings.rrf_mixed_text_weight


# ---------------------------------------------------------------------------
# Lifecycle flag wiring
# ---------------------------------------------------------------------------


class TestLifecycleFlag:
    @pytest.mark.asyncio
    async def test_start_respects_disabled_flag(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app.knowledge import lifecycle

        mock_settings = MagicMock()
        mock_settings.knowledge_feedback_enabled = False
        mock_settings.background_queue_enabled = False
        monkeypatch.setattr(lifecycle, "get_settings", lambda: mock_settings)

        await lifecycle.start_knowledge_tasks()
        assert lifecycle._recompute_task is None
        await lifecycle.stop_knowledge_tasks()

    @pytest.mark.asyncio
    async def test_start_defers_when_queue_enabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app.knowledge import lifecycle

        mock_settings = MagicMock()
        mock_settings.knowledge_feedback_enabled = True
        mock_settings.background_queue_enabled = True
        monkeypatch.setattr(lifecycle, "get_settings", lambda: mock_settings)

        await lifecycle.start_knowledge_tasks()
        assert lifecycle._recompute_task is None
        await lifecycle.stop_knowledge_tasks()


# Ensure mypy doesn't complain about the unused Any hint.
_: Any = None
