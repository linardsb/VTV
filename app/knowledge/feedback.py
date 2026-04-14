# pyright: reportUnknownMemberType=false, reportMissingTypeStubs=false
"""KB-4: Search feedback service.

Captures user thumbs-up/down on cited search results, and periodically
recomputes tuned RRF weights from the feedback signal. Tuned weights
are stored in Redis with a 48h TTL; search reads them with graceful
fallback to static ``settings.rrf_*`` values on cache miss or error.
"""

from __future__ import annotations

import hashlib
import json
from datetime import timedelta
from typing import TYPE_CHECKING

from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.knowledge.exceptions import FeedbackChunkNotFoundError
from app.knowledge.repository import KnowledgeRepository
from app.knowledge.schemas import QueryType, RankSource, RRFWeights
from app.shared.models import utcnow

if TYPE_CHECKING:
    from redis.asyncio import Redis

logger = get_logger(__name__)

_WEIGHTS_KEY_PREFIX = "knowledge:rrf:weights:"
_WEIGHTS_TTL_SECONDS = 172_800  # 48 hours


def compute_query_hash(query: str, domain: str | None) -> str:
    """Return a stable 32-char hex hash for a search query.

    Whitespace-collapsed and lowercased so semantically-identical queries
    (e.g. with extra spaces or different case) produce the same hash.

    Args:
        query: Raw search query text.
        domain: Optional domain filter applied to the search.

    Returns:
        32-char lowercase hex string (128 bits of SHA-256 prefix).
    """
    normalized = " ".join(query.lower().split())
    key = f"{normalized}|{domain or ''}"
    return hashlib.sha256(key.encode()).hexdigest()[:32]


def _static_weights(query_type: QueryType) -> tuple[float, float]:
    """Return the static ``(vector, text)`` RRF weights for a query type."""
    settings = get_settings()
    if query_type == "keyword":
        return settings.rrf_keyword_vector_weight, settings.rrf_keyword_text_weight
    if query_type == "semantic":
        return settings.rrf_semantic_vector_weight, settings.rrf_semantic_text_weight
    return settings.rrf_mixed_vector_weight, settings.rrf_mixed_text_weight


class FeedbackService:
    """Record feedback and recompute tuned RRF weights."""

    def __init__(self, db: AsyncSession, redis: Redis) -> None:
        """Initialize with a DB session and the shared Redis client.

        Args:
            db: Async SQLAlchemy session (request-scoped or background).
            redis: Shared Redis client (``app.core.redis.get_redis``).
        """
        self.db = db
        self.redis = redis
        self.repository = KnowledgeRepository(db)

    async def record(
        self,
        *,
        user_id: int | None,
        query_hash: str,
        query_type: QueryType,
        chunk_id: int,
        rank_source: RankSource,
        relevant: bool,
    ) -> None:
        """Persist a feedback vote.

        Args:
            user_id: Voter id (``None`` for anonymous, though route requires auth).
            query_hash: Stable hash returned by ``/search`` response.
            query_type: Search classification (keyword/semantic/mixed).
            chunk_id: Chunk the user rated.
            rank_source: Which retrieval branch surfaced the chunk.
            relevant: True for thumbs-up, False for thumbs-down.

        Raises:
            FeedbackChunkNotFoundError: Chunk does not exist.
        """
        if not await self.repository.chunk_exists(chunk_id):
            raise FeedbackChunkNotFoundError(f"Chunk {chunk_id} not found")

        await self.repository.upsert_feedback(
            user_id=user_id,
            query_hash=query_hash,
            query_type=query_type,
            chunk_id=chunk_id,
            rank_source=rank_source,
            relevant=relevant,
        )
        logger.info(
            "knowledge.feedback.recorded",
            query_type=query_type,
            rank_source=rank_source,
            relevant=relevant,
            user_id=user_id,
        )

    async def recompute_weights(self) -> dict[str, RRFWeights]:
        """Aggregate recent feedback and update tuned weights in Redis.

        Reads the last ``knowledge_rrf_feedback_window_days`` days of
        feedback grouped by ``(query_type, rank_source)``, blends a
        Laplace-smoothed positive-rate ratio with the static config at
        ``knowledge_rrf_blend_weight``, clamps to ``[0.1, 0.9]``, and
        stores per ``query_type``. Query types below
        ``knowledge_rrf_min_signals_per_type`` total votes are skipped
        (the search path falls back to static config for them).

        Returns:
            Mapping of ``query_type`` -> newly persisted ``RRFWeights``.
            Skipped query types are absent from the mapping.
        """
        settings = get_settings()
        since = utcnow() - timedelta(days=settings.knowledge_rrf_feedback_window_days)
        counts = await self.repository.feedback_counts(since=since)

        persisted: dict[str, RRFWeights] = {}
        sample_sizes: dict[str, int] = {}

        query_types: tuple[QueryType, ...] = ("keyword", "semantic", "mixed")
        for query_type in query_types:
            vec = counts.get((query_type, "vector"), {"up": 0, "down": 0})
            ft = counts.get((query_type, "fulltext"), {"up": 0, "down": 0})
            total = vec["up"] + vec["down"] + ft["up"] + ft["down"]
            sample_sizes[query_type] = total
            if total < settings.knowledge_rrf_min_signals_per_type:
                continue

            # Laplace-smoothed positive rates, then normalize to shares.
            vec_score = (vec["up"] + 1) / (vec["up"] + vec["down"] + 2)
            ft_score = (ft["up"] + 1) / (ft["up"] + ft["down"] + 2)
            raw_vec = vec_score / (vec_score + ft_score)

            static_vec, _static_text = _static_weights(query_type)
            blend = settings.knowledge_rrf_blend_weight
            vector_weight = round(blend * raw_vec + (1 - blend) * static_vec, 3)
            vector_weight = max(0.1, min(0.9, vector_weight))
            text_weight = round(1 - vector_weight, 3)

            weights = RRFWeights(
                query_type=query_type,
                vector_weight=vector_weight,
                text_weight=text_weight,
                sample_size=total,
                updated_at=utcnow(),
                source="tuned",
            )
            try:
                await self.redis.set(
                    _WEIGHTS_KEY_PREFIX + query_type,
                    weights.model_dump_json(),
                    ex=_WEIGHTS_TTL_SECONDS,
                )
            except RedisError as exc:
                logger.warning(
                    "knowledge.rrf.recompute_failed",
                    stage="redis_write",
                    query_type=query_type,
                    error=str(exc),
                    error_type=type(exc).__name__,
                )
                continue
            persisted[query_type] = weights

        logger.info(
            "knowledge.rrf.recomputed",
            query_types=list(persisted),
            sample_sizes=sample_sizes,
            updated_weights={
                qt: {"vector": w.vector_weight, "text": w.text_weight}
                for qt, w in persisted.items()
            },
        )
        return persisted

    async def get_tuned_weights(self, query_type: QueryType) -> tuple[float, float]:
        """Return ``(vector_weight, text_weight)`` for a query type.

        Reads the Redis key ``knowledge:rrf:weights:{query_type}``; on
        missing key, corrupt JSON, or any ``RedisError`` falls back to
        ``settings.rrf_{type}_{vector|text}_weight``. Failures are
        logged at warning level (fail-open is acceptable here — search
        quality, not a security boundary).

        Args:
            query_type: Search classification.

        Returns:
            Tuple of ``(vector_weight, text_weight)``.
        """
        try:
            raw = await self.redis.get(_WEIGHTS_KEY_PREFIX + query_type)
        except RedisError as exc:
            logger.warning(
                "knowledge.rrf.tuned_weights_unavailable",
                query_type=query_type,
                stage="redis_read",
                error=str(exc),
                error_type=type(exc).__name__,
            )
            return _static_weights(query_type)
        if raw is None:
            return _static_weights(query_type)
        try:
            payload = json.loads(raw)
            vec = float(payload["vector_weight"])
            txt = float(payload["text_weight"])
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            logger.warning(
                "knowledge.rrf.tuned_weights_unavailable",
                query_type=query_type,
                stage="decode",
                error=str(exc),
                error_type=type(exc).__name__,
            )
            return _static_weights(query_type)
        return vec, txt


__all__ = [
    "FeedbackService",
    "compute_query_hash",
]
