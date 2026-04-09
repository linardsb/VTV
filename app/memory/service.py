"""Business logic for agent memory operations."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.knowledge.embedding import (
    EmbeddingProvider,
    get_embedding_provider,
)
from app.memory.exceptions import MemoryNotFoundError
from app.memory.models import MemoryEntry
from app.memory.repository import MemoryRepository
from app.memory.schemas import (
    CompactionResult,
    MemoryEntryCreate,
    MemoryEntryResponse,
    MemoryRecallByQueryRequest,
    MemoryRecallRequest,
    MemoryRecallResponse,
)

logger = get_logger(__name__)

# Module-level lazy singleton for embedding provider
_embedding_provider: EmbeddingProvider | None = None


def _get_embedding() -> EmbeddingProvider:
    """Get or create the embedding provider singleton (with optional cache)."""
    global _embedding_provider
    if _embedding_provider is None:
        settings = get_settings()
        provider = get_embedding_provider(settings)
        if settings.embedding_cache_enabled:
            from app.knowledge.embedding import CachedEmbeddingProvider

            provider = CachedEmbeddingProvider(
                provider=provider,
                provider_name=settings.embedding_provider,
                ttl=settings.embedding_cache_ttl,
            )
        _embedding_provider = provider
    return _embedding_provider


class MemoryService:
    """Orchestrates memory storage, recall, and maintenance."""

    def __init__(self, db: AsyncSession) -> None:
        self.repository = MemoryRepository(db)

    async def store(self, data: MemoryEntryCreate) -> MemoryEntry:
        """Store a new memory entry, generating embedding and checking duplicates."""
        settings = get_settings()

        # Generate embedding if not provided
        embedding = data.embedding
        if embedding is None:
            embedding = (await _get_embedding().embed([data.content]))[0]

        # Check for duplicates
        similar = await self.repository.find_similar(
            embedding, threshold=settings.memory_duplicate_threshold
        )
        if similar:
            existing_entry, score = similar[0]
            logger.info(
                "memory.service.store_duplicate_skipped",
                existing_id=existing_entry.id,
                score=score,
                content_preview=data.content[:80],
            )
            return existing_entry

        entry = MemoryEntry(
            agent_type=data.agent_type,
            memory_type=data.memory_type,
            content=data.content,
            embedding=embedding,
            metadata_json=data.metadata_json,
            decay_weight=data.decay_weight,
            is_evergreen=data.is_evergreen,
            source=data.source,
        )
        result = await self.repository.store(entry)
        logger.info(
            "memory.service.store_completed",
            memory_id=result.id,
            memory_type=data.memory_type,
            agent_type=data.agent_type,
        )
        return result

    async def get(self, entry_id: int) -> MemoryEntry:
        """Get a memory entry by ID. Raises MemoryNotFoundError if not found."""
        entry = await self.repository.get(entry_id)
        if entry is None:
            raise MemoryNotFoundError(entry_id)
        return entry

    async def recall(self, request: MemoryRecallRequest) -> list[MemoryRecallResponse]:
        """Recall memories by similarity and increment recall counters."""
        rows = await self.repository.recall(
            embedding=request.embedding,
            agent_type=request.agent_type,
            memory_type=request.memory_type,
            limit=request.limit,
            min_score=request.min_score,
        )
        results: list[MemoryRecallResponse] = []
        for entry, score in rows:
            await self.repository.increment_recalled_count(entry.id)
            results.append(
                MemoryRecallResponse(
                    memory=MemoryEntryResponse.model_validate(entry),
                    score=score,
                )
            )
        logger.info(
            "memory.service.recall_completed",
            result_count=len(results),
            agent_type=request.agent_type,
            memory_type=request.memory_type,
        )
        return results

    async def recall_by_query(
        self, request: MemoryRecallByQueryRequest
    ) -> list[MemoryRecallResponse]:
        """Recall memories by text query (embeds the query first)."""
        embedding = (await _get_embedding().embed([request.query]))[0]
        rows = await self.repository.recall(
            embedding=embedding,
            agent_type=request.agent_type,
            memory_type=request.memory_type,
            limit=request.limit,
            min_score=request.min_score,
        )
        results: list[MemoryRecallResponse] = []
        for entry, score in rows:
            await self.repository.increment_recalled_count(entry.id)
            results.append(
                MemoryRecallResponse(
                    memory=MemoryEntryResponse.model_validate(entry),
                    score=score,
                )
            )
        logger.info(
            "memory.service.recall_by_query_completed",
            result_count=len(results),
            query_preview=request.query[:80],
        )
        return results

    async def get_by_type(self, memory_type: str, limit: int = 50) -> list[MemoryEntry]:
        """List memory entries by type."""
        return await self.repository.get_by_type(memory_type, limit)

    async def delete_decayed(self, threshold: float = 0.1) -> int:
        """Remove decayed non-evergreen memories below threshold."""
        count = await self.repository.delete_decayed(threshold)
        logger.info("memory.service.delete_decayed_completed", deleted_count=count)
        return count

    async def compact(self) -> CompactionResult:
        """Run full memory compaction: decay, delete, merge, promote.

        Steps:
            1. Apply time-based decay per memory type
            2. Delete entries below minimum decay weight
            3. Find and merge similar entry pairs
            4. Promote frequently-recalled episodic entries
        """
        settings = get_settings()

        # Step 1: Apply decay per type
        decay_map = {
            "procedural": settings.memory_procedural_decay_days,
            "episodic": settings.memory_episodic_decay_days,
            "query_pattern": settings.memory_query_pattern_decay_days,
            # semantic entries are evergreen — skip decay
        }
        for mem_type, days in decay_map.items():
            await self.repository.apply_decay(mem_type, days)

        # Step 2: Delete entries below threshold
        decayed_deleted = await self.repository.delete_decayed(settings.memory_decay_min_weight)

        # Step 3: Merge similar pairs
        merged = 0
        pairs = await self.repository.find_similar_pairs(threshold=settings.memory_merge_threshold)
        for entry_a, entry_b, _score in pairs:
            # Merge into the entry with higher recalled_count
            if entry_a.recalled_count >= entry_b.recalled_count:
                keep, remove = entry_a, entry_b
            else:
                keep, remove = entry_b, entry_a

            # LLM-based intent merging or simple concatenation
            if settings.memory_llm_merge_enabled:
                merged_content = await self._llm_merge(keep.content, remove.content)
            else:
                merged_content = f"{keep.content}\n---\n{remove.content}"

            # Re-embed the merged content
            merged_embedding = (await _get_embedding().embed([merged_content]))[0]
            await self.repository.merge_entries(
                keep_id=keep.id,
                remove_id=remove.id,
                merged_content=merged_content,
                merged_embedding=merged_embedding,
            )
            merged += 1

        # Step 4: Promote eligible episodic entries
        promoted = await self.promote_episodes()

        logger.info(
            "memory.service.compact_completed",
            decayed_deleted=decayed_deleted,
            merged=merged,
            promoted=promoted,
        )
        return CompactionResult(
            decayed_deleted=decayed_deleted,
            merged=merged,
            promoted=promoted,
        )

    async def promote_episodes(self) -> int:
        """Promote episodic entries to procedural after enough recalls."""
        settings = get_settings()
        promotable = await self.repository.find_promotable(
            threshold=settings.memory_promotion_threshold
        )
        for entry in promotable:
            await self.repository.update_memory_type(entry.id, "procedural")
        logger.info(
            "memory.service.promote_completed",
            promoted_count=len(promotable),
        )
        return len(promotable)

    async def _llm_merge(self, content_a: str, content_b: str) -> str:
        """Merge two memory entries using LLM-based intent summarization.

        Uses a lightweight LLM call to produce a single coherent memory from
        two similar entries. Falls back to concatenation on failure.

        Args:
            content_a: Content of the higher-recall entry (kept).
            content_b: Content of the lower-recall entry (removed).

        Returns:
            Merged content string.
        """
        from pydantic_ai import Agent as PydanticAgent

        from app.core.agents.config import resolve_tier_model

        try:
            tier_model = resolve_tier_model("fast")
            merge_agent: PydanticAgent[None, str] = PydanticAgent(
                model=tier_model,
                system_prompt=(
                    "Merge these two transit operations memory entries into one "
                    "concise summary. Preserve all factual content. Output only "
                    "the merged text, no explanation."
                ),
            )
            result = await merge_agent.run(
                f"Entry A:\n{content_a[:500]}\n\nEntry B:\n{content_b[:500]}"
            )
            logger.info("memory.service.llm_merge_completed")
            return result.output
        except Exception:
            logger.warning("memory.service.llm_merge_failed", exc_info=True)
            return f"{content_a}\n---\n{content_b}"
