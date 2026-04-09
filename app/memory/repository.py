# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Repository for agent memory entries with pgvector similarity search."""

from datetime import timedelta

from sqlalchemy import delete, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.memory.models import MemoryEntry
from app.shared.models import utcnow

logger = get_logger(__name__)


class MemoryRepository:
    """Data access layer for memory entries."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def store(self, entry: MemoryEntry) -> MemoryEntry:
        """Persist a new memory entry."""
        self.db.add(entry)
        await self.db.commit()
        await self.db.refresh(entry)
        return entry

    async def get(self, entry_id: int) -> MemoryEntry | None:
        """Get a memory entry by ID."""
        result = await self.db.execute(select(MemoryEntry).where(MemoryEntry.id == entry_id))
        return result.scalar_one_or_none()

    async def recall(
        self,
        embedding: list[float],
        agent_type: str | None = None,
        memory_type: str | None = None,
        limit: int = 10,
        min_score: float = 0.0,
    ) -> list[tuple[MemoryEntry, float]]:
        """Recall memories by cosine similarity.

        Args:
            embedding: Query embedding vector (1024-dim).
            agent_type: Optional filter by agent type.
            memory_type: Optional filter by memory type.
            limit: Maximum results to return.
            min_score: Minimum similarity score (0-1). Cosine distance
                is converted: score = 1 - distance.

        Returns:
            List of (entry, score) tuples sorted by score descending.
        """
        distance = MemoryEntry.embedding.cosine_distance(embedding).label("distance")
        query = (
            select(MemoryEntry, distance)
            .where(MemoryEntry.embedding.is_not(None))
            .order_by(distance)
            .limit(limit)
        )
        if agent_type is not None:
            query = query.where(MemoryEntry.agent_type == agent_type)
        if memory_type is not None:
            query = query.where(MemoryEntry.memory_type == memory_type)

        result = await self.db.execute(query)
        rows: list[tuple[MemoryEntry, float]] = []
        for row in result.all():
            score = 1.0 - float(row[1])
            if score >= min_score:
                rows.append((row[0], score))
        return rows

    async def get_by_type(
        self,
        memory_type: str,
        limit: int = 50,
    ) -> list[MemoryEntry]:
        """Get memory entries by type, ordered by most recent."""
        result = await self.db.execute(
            select(MemoryEntry)
            .where(MemoryEntry.memory_type == memory_type)
            .order_by(MemoryEntry.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def increment_recalled_count(self, entry_id: int) -> None:
        """Increment the recall counter for a memory entry."""
        await self.db.execute(
            update(MemoryEntry)
            .where(MemoryEntry.id == entry_id)
            .values(recalled_count=MemoryEntry.recalled_count + 1)
        )
        await self.db.commit()

    async def delete_decayed(self, threshold: float) -> int:
        """Delete non-evergreen entries with decay_weight below threshold.

        Returns:
            Number of entries deleted.
        """
        result = await self.db.execute(
            delete(MemoryEntry)
            .where(MemoryEntry.decay_weight < threshold)
            .where(MemoryEntry.is_evergreen.is_(False))
        )
        await self.db.commit()
        rowcount = result.rowcount  # type: ignore[attr-defined]
        count: int = int(rowcount) if rowcount else 0
        logger.info(
            "memory.repository.delete_decayed_completed",
            threshold=threshold,
            deleted_count=count,
        )
        return count

    async def find_similar(
        self,
        embedding: list[float],
        threshold: float = 0.95,
    ) -> list[tuple[MemoryEntry, float]]:
        """Find entries with cosine similarity >= threshold.

        Args:
            embedding: Query embedding vector.
            threshold: Minimum cosine similarity (0-1).

        Returns:
            List of (entry, score) tuples above threshold.
        """
        distance = MemoryEntry.embedding.cosine_distance(embedding).label("distance")
        query = (
            select(MemoryEntry, distance)
            .where(MemoryEntry.embedding.is_not(None))
            .order_by(distance)
        )
        result = await self.db.execute(query)
        rows: list[tuple[MemoryEntry, float]] = []
        for row in result.all():
            score = 1.0 - float(row[1])
            if score >= threshold:
                rows.append((row[0], score))
        return rows

    async def apply_decay(self, memory_type: str, decay_days: int) -> int:
        """Apply decay to non-evergreen entries older than decay_days.

        Multiplies decay_weight by 0.95 for matching entries.

        Returns:
            Number of entries updated.
        """
        cutoff = utcnow() - timedelta(days=decay_days)
        result = await self.db.execute(
            update(MemoryEntry)
            .where(MemoryEntry.memory_type == memory_type)
            .where(MemoryEntry.updated_at < cutoff)
            .where(MemoryEntry.is_evergreen.is_(False))
            .values(decay_weight=MemoryEntry.decay_weight * 0.95)
        )
        await self.db.commit()
        rowcount = result.rowcount  # type: ignore[attr-defined]
        count: int = int(rowcount) if rowcount else 0
        logger.info(
            "memory.repository.apply_decay_completed",
            memory_type=memory_type,
            decay_days=decay_days,
            updated_count=count,
        )
        return count

    async def merge_entries(
        self,
        keep_id: int,
        remove_id: int,
        merged_content: str,
        merged_embedding: list[float],
    ) -> MemoryEntry | None:
        """Merge two entries: update keep, delete remove.

        The kept entry gets the merged content/embedding, the max recalled_count,
        and source set to 'compaction'.

        Returns:
            Updated entry, or None if keep entry not found.
        """
        keep = await self.get(keep_id)
        remove = await self.get(remove_id)
        if keep is None or remove is None:
            return None

        max_recalled = max(keep.recalled_count, remove.recalled_count)
        await self.db.execute(
            update(MemoryEntry)
            .where(MemoryEntry.id == keep_id)
            .values(
                content=merged_content,
                embedding=merged_embedding,
                recalled_count=max_recalled,
                source="compaction",
            )
        )
        await self.db.execute(delete(MemoryEntry).where(MemoryEntry.id == remove_id))
        await self.db.commit()

        updated = await self.get(keep_id)
        logger.info(
            "memory.repository.merge_entries_completed",
            keep_id=keep_id,
            remove_id=remove_id,
        )
        return updated

    async def find_similar_pairs(
        self,
        threshold: float = 0.92,
    ) -> list[tuple[MemoryEntry, MemoryEntry, float]]:
        """Find pairs of entries with cosine similarity above threshold.

        Uses a self-join with a.id < b.id to avoid duplicates.

        Returns:
            List of (entry_a, entry_b, score) tuples.
        """
        raw_sql = text(
            "SELECT a.id AS a_id, b.id AS b_id, "
            "1 - (a.embedding <=> b.embedding) AS score "
            "FROM memory_entries a, memory_entries b "
            "WHERE a.id < b.id "
            "AND a.embedding IS NOT NULL "
            "AND b.embedding IS NOT NULL "
            "AND 1 - (a.embedding <=> b.embedding) > :threshold"
        )

        result = await self.db.execute(raw_sql, {"threshold": threshold})
        pairs: list[tuple[MemoryEntry, MemoryEntry, float]] = []
        for row in result.all():
            entry_a = await self.get(row[0])
            entry_b = await self.get(row[1])
            if entry_a is not None and entry_b is not None:
                pairs.append((entry_a, entry_b, float(row[2])))
        return pairs

    async def find_promotable(self, threshold: int = 3) -> list[MemoryEntry]:
        """Find episodic entries recalled enough times for promotion.

        Args:
            threshold: Minimum recalled_count to qualify.

        Returns:
            Episodic entries with recalled_count >= threshold.
        """
        result = await self.db.execute(
            select(MemoryEntry)
            .where(MemoryEntry.memory_type == "episodic")
            .where(MemoryEntry.recalled_count >= threshold)
        )
        return list(result.scalars().all())

    async def update_memory_type(self, entry_id: int, new_type: str) -> None:
        """Update the memory_type of an entry (used for promotion)."""
        await self.db.execute(
            update(MemoryEntry).where(MemoryEntry.id == entry_id).values(memory_type=new_type)
        )
        await self.db.commit()
