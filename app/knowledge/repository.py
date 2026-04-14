# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false
"""Data access layer for knowledge base with pgvector hybrid search."""

from datetime import datetime
from typing import cast

from sqlalchemy import delete, distinct, func, or_, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.knowledge.models import Document, DocumentChunk, Tag, document_tags


class KnowledgeRepository:
    """Database operations for knowledge base documents and chunks."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize with an async database session.

        Args:
            db: SQLAlchemy async session.
        """
        self.db = db

    async def create_document(
        self,
        *,
        filename: str,
        domain: str,
        source_type: str,
        language: str,
        file_size_bytes: int | None,
        metadata_json: str | None,
        title: str | None = None,
        description: str | None = None,
        status: str = "pending",
        ocr_applied: bool = False,
        evergreen: bool = False,
        version: int = 1,
        parent_document_id: int | None = None,
        is_latest: bool = True,
    ) -> Document:
        """Create a new document record.

        Args:
            filename: Original filename.
            domain: Knowledge domain category.
            source_type: File type (pdf, docx, email, image, text).
            language: Document language (lv, en).
            file_size_bytes: File size in bytes.
            metadata_json: Optional JSON metadata string.
            title: Human-readable document title.
            description: Optional document description.
            status: Processing status.
            ocr_applied: Whether OCR was used during extraction.

        Returns:
            The newly created Document instance.
        """
        doc = Document(
            filename=filename,
            domain=domain,
            source_type=source_type,
            language=language,
            file_size_bytes=file_size_bytes,
            metadata_json=metadata_json,
            title=title,
            description=description,
            status=status,
            ocr_applied=ocr_applied,
            evergreen=evergreen,
            version=version,
            parent_document_id=parent_document_id,
            is_latest=is_latest,
        )
        self.db.add(doc)
        await self.db.commit()
        await self.db.refresh(doc)
        return doc

    async def get_document(self, document_id: int) -> Document | None:
        """Get a document by primary key ID.

        Args:
            document_id: The document's database ID.

        Returns:
            Document instance or None if not found.
        """
        result = await self.db.execute(select(Document).where(Document.id == document_id))
        return result.scalar_one_or_none()

    async def list_documents(
        self,
        *,
        offset: int = 0,
        limit: int = 100,
        domain: str | None = None,
        status: str | None = None,
        language: str | None = None,
        tag: str | None = None,
        include_superseded: bool = False,
    ) -> list[Document]:
        """List documents with pagination and optional filtering.

        Args:
            offset: Number of records to skip.
            limit: Maximum records to return.
            domain: Filter by domain.
            status: Filter by processing status.
            language: Filter by language.
            tag: Filter by tag name.

        Returns:
            List of Document instances.
        """
        query = select(Document)
        if domain:
            query = query.where(Document.domain == domain)
        if status:
            query = query.where(Document.status == status)
        if language:
            query = query.where(Document.language == language)
        if not include_superseded:
            query = query.where(Document.is_latest.is_(True))
        if tag:
            query = query.join(document_tags, Document.id == document_tags.c.document_id)
            query = query.join(Tag, document_tags.c.tag_id == Tag.id)
            query = query.where(Tag.name == tag)
        query = query.order_by(Document.created_at.desc()).offset(offset).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def count_documents(
        self,
        *,
        domain: str | None = None,
        status: str | None = None,
        tag: str | None = None,
        include_superseded: bool = False,
    ) -> int:
        """Count documents matching the given filters.

        Args:
            domain: Filter by domain.
            status: Filter by processing status.
            tag: Filter by tag name.

        Returns:
            Total number of matching documents.
        """
        query = select(func.count()).select_from(Document)
        if domain:
            query = query.where(Document.domain == domain)
        if status:
            query = query.where(Document.status == status)
        if not include_superseded:
            query = query.where(Document.is_latest.is_(True))
        if tag:
            query = query.join(document_tags, Document.id == document_tags.c.document_id)
            query = query.join(Tag, document_tags.c.tag_id == Tag.id)
            query = query.where(Tag.name == tag)
        result = await self.db.execute(query)
        return result.scalar_one()

    async def update_document_status(
        self,
        document_id: int,
        status: str,
        error_message: str | None,
        chunk_count: int,
    ) -> None:
        """Update a document's processing status.

        Args:
            document_id: The document's database ID.
            status: New processing status.
            error_message: Error message if failed.
            chunk_count: Number of chunks created.
        """
        result = await self.db.execute(select(Document).where(Document.id == document_id))
        doc = result.scalar_one_or_none()
        if doc:
            doc.status = status
            doc.error_message = error_message
            doc.chunk_count = chunk_count
            await self.db.commit()

    async def delete_document(self, document_id: int) -> None:
        """Delete a document and its chunks (CASCADE).

        Args:
            document_id: The document's database ID.
        """
        result = await self.db.execute(select(Document).where(Document.id == document_id))
        doc = result.scalar_one_or_none()
        if doc:
            await self.db.delete(doc)
            await self.db.commit()

    async def delete_chunks_by_document(self, document_id: int) -> int:
        """Delete all chunks for a document, keeping the Document row.

        Used by the AI-4.4 re-chunk migration to wipe stale chunks before
        re-running the ingestion pipeline against the existing file.

        Args:
            document_id: The document's database ID.

        Returns:
            Number of chunk rows deleted.
        """
        result = await self.db.execute(
            delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
        )
        await self.db.commit()
        rowcount = cast(int, result.rowcount)  # type: ignore[attr-defined]
        return rowcount if rowcount else 0

    async def update_document(
        self,
        document_id: int,
        **kwargs: str | bool | None,
    ) -> Document | None:
        """Update document metadata fields.

        Args:
            document_id: The document's database ID.
            **kwargs: Fields to update (title, description, domain, language).

        Returns:
            Updated Document or None if not found.
        """
        result = await self.db.execute(select(Document).where(Document.id == document_id))
        doc = result.scalar_one_or_none()
        if not doc:
            return None
        for key, value in kwargs.items():
            if value is not None:
                setattr(doc, key, value)
        await self.db.commit()
        await self.db.refresh(doc)
        return doc

    async def update_document_file_path(self, document_id: int, file_path: str) -> None:
        """Set the stored file path for a document.

        Args:
            document_id: The document's database ID.
            file_path: Path to the stored file on disk.
        """
        result = await self.db.execute(select(Document).where(Document.id == document_id))
        doc = result.scalar_one_or_none()
        if doc:
            doc.file_path = file_path
            await self.db.commit()

    async def get_chunks_by_document(self, document_id: int) -> list[DocumentChunk]:
        """Get all chunks for a document ordered by index.

        Args:
            document_id: The document's database ID.

        Returns:
            List of DocumentChunk instances ordered by chunk_index.
        """
        result = await self.db.execute(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index)
        )
        return list(result.scalars().all())

    async def get_chunks_by_ids(self, chunk_ids: list[int]) -> list[DocumentChunk]:
        """Fetch multiple chunks by primary key in a single query.

        Used by parent-context expansion: collects all unique parent_chunk_ids
        from search results and loads them in one round-trip.

        Args:
            chunk_ids: List of DocumentChunk IDs to fetch. Empty list returns
                an empty result without issuing a query.

        Returns:
            List of DocumentChunk instances. Order is not guaranteed; callers
            that need ordering should index by ``chunk.id``.
        """
        if not chunk_ids:
            return []
        result = await self.db.execute(select(DocumentChunk).where(DocumentChunk.id.in_(chunk_ids)))
        return list(result.scalars().all())

    async def list_domains(self) -> list[str]:
        """List all unique document domains.

        Returns:
            Sorted list of unique domain strings.
        """
        result = await self.db.execute(select(distinct(Document.domain)).order_by(Document.domain))
        return list(result.scalars().all())

    async def bulk_create_chunks(
        self,
        chunks: list[DocumentChunk],
        *,
        flush_only: bool = False,
    ) -> None:
        """Insert chunks in bulk.

        When ``flush_only=True`` the session is flushed instead of committed,
        which assigns primary-key ids on each ORM instance without ending the
        transaction. The caller is then responsible for issuing a final commit
        (typically via a second call with ``flush_only=False``). This enables
        two-phase parent/child inserts where children must reference
        parent ids that don't yet exist at construction time.

        Args:
            chunks: List of DocumentChunk instances to insert.
            flush_only: When True, flush the session instead of committing.
        """
        self.db.add_all(chunks)
        if flush_only:
            await self.db.flush()
        else:
            await self.db.commit()

    async def search_vector(
        self,
        query_embedding: list[float],
        limit: int,
        domain: str | None = None,
        language: str | None = None,
        created_after: datetime | None = None,
        created_before: datetime | None = None,
        *,
        include_superseded: bool = False,
    ) -> list[tuple[DocumentChunk, Document, float]]:
        """Search chunks by vector similarity (cosine distance).

        Args:
            query_embedding: Query embedding vector.
            limit: Maximum results.
            domain: Optional domain filter.
            language: Optional language filter.
            created_after: Exclude documents created before this timestamp.
            created_before: Exclude documents created after this timestamp.

        Returns:
            List of (chunk, document, distance) tuples sorted by distance ascending.
        """
        distance = DocumentChunk.embedding.cosine_distance(query_embedding).label("distance")
        query = (
            select(DocumentChunk, Document, distance)
            .join(Document, DocumentChunk.document_id == Document.id)
            .where(DocumentChunk.embedding.is_not(None))
            .order_by(distance)
            .limit(limit)
        )
        if domain:
            query = query.where(Document.domain == domain)
        if language:
            query = query.where(Document.language == language)
        if created_after is not None:
            query = query.where(Document.created_at >= created_after)
        if created_before is not None:
            query = query.where(Document.created_at <= created_before)
        if not include_superseded:
            query = query.where(Document.is_latest.is_(True))

        result = await self.db.execute(query)
        rows: list[tuple[DocumentChunk, Document, float]] = [
            (row[0], row[1], float(row[2])) for row in result.all()
        ]
        return rows

    async def search_fulltext(
        self,
        query_text: str,
        limit: int,
        domain: str | None = None,
        language: str | None = None,
        created_after: datetime | None = None,
        created_before: datetime | None = None,
        *,
        lemmatized_query: str | None = None,
        include_superseded: bool = False,
    ) -> list[tuple[DocumentChunk, Document, float]]:
        """Search chunks using PostgreSQL full-text search.

        Uses 'simple' configuration (no built-in stemming). When
        ``lemmatized_query`` is provided and a chunk has a pre-computed
        ``lemmatized_content`` (KB-2, Latvian docs), BM25 runs against
        the lemmatized text — so inflected Latvian forms match. Chunks
        without ``lemmatized_content`` fall back to raw ``content`` via
        COALESCE.

        Args:
            query_text: Raw search text (used when no lemmatized form provided).
            limit: Maximum results.
            domain: Optional domain filter.
            language: Optional language filter.
            created_after: Exclude documents created before this timestamp.
            created_before: Exclude documents created after this timestamp.
            lemmatized_query: Pre-lemmatized query text. When provided, the
                fulltext query runs against it; otherwise ``query_text`` is used.

        Returns:
            List of (chunk, document, rank) tuples sorted by rank descending.
        """
        query_param = lemmatized_query if lemmatized_query else query_text
        ts_query = func.plainto_tsquery(text("'simple'"), query_param)
        chunk_text_expr = func.coalesce(
            DocumentChunk.lemmatized_content,
            DocumentChunk.content,
        )
        ts_vector = func.to_tsvector(text("'simple'"), chunk_text_expr)
        rank = func.ts_rank(ts_vector, ts_query).label("rank")

        query = (
            select(DocumentChunk, Document, rank)
            .join(Document, DocumentChunk.document_id == Document.id)
            .where(ts_vector.bool_op("@@")(ts_query))
            .order_by(rank.desc())
            .limit(limit)
        )
        if domain:
            query = query.where(Document.domain == domain)
        if language:
            query = query.where(Document.language == language)
        if created_after is not None:
            query = query.where(Document.created_at >= created_after)
        if created_before is not None:
            query = query.where(Document.created_at <= created_before)
        if not include_superseded:
            query = query.where(Document.is_latest.is_(True))

        result = await self.db.execute(query)
        rows: list[tuple[DocumentChunk, Document, float]] = [
            (row[0], row[1], float(row[2])) for row in result.all()
        ]
        return rows

    # ------------------------------------------------------------------
    # KB-3: Document versioning
    # ------------------------------------------------------------------

    async def get_latest_by_title_domain(self, *, title: str, domain: str) -> Document | None:
        """Return the current latest version for a ``(title, domain)`` pair.

        Used at ingest time to detect same-title re-uploads. Only rows with
        ``is_latest=true`` are considered — failed or superseded rows never
        become the supersede target.

        Args:
            title: Document title to match exactly.
            domain: Knowledge domain to match exactly.

        Returns:
            The latest ``Document`` in the chain, or None when no prior exists.
        """
        stmt = (
            select(Document)
            .where(
                Document.title == title,
                Document.domain == domain,
                Document.is_latest.is_(True),
            )
            .order_by(Document.version.desc())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def mark_superseded(self, doc_id: int) -> None:
        """Flip ``status='superseded'`` and ``is_latest=false`` for a document.

        Chunks remain intact (no cascade delete). The caller's transaction
        commits this UPDATE together with the sibling ``create_document`` of
        the new version — if either fails, both roll back.

        Args:
            doc_id: The document to mark superseded.
        """
        stmt = (
            update(Document)
            .where(Document.id == doc_id)
            .values(status="superseded", is_latest=False)
        )
        await self.db.execute(stmt)

    async def list_versions(self, document_id: int) -> list[Document]:
        """Return every row in the version chain containing ``document_id``.

        Walks ``parent_document_id`` to the chain root, then BFS-collects all
        descendants. Results are ordered by ``version`` descending (newest
        first). Returns an empty list when ``document_id`` does not exist.

        Args:
            document_id: Any row in the chain.

        Returns:
            Chain members ordered newest-first.
        """
        root = await self._find_chain_root(document_id)
        if root is None:
            return []
        return await self._collect_descendants(root)

    async def _find_chain_root(self, doc_id: int) -> Document | None:
        """Walk ``parent_document_id`` upward to the root of the version chain.

        Depth is capped at 100 hops to defend against pathological cycles
        (which shouldn't be possible given the directional FK, but the guard
        is cheap and prevents an infinite loop on data corruption).
        """
        current = await self.get_document(doc_id)
        if current is None:
            return None
        for _ in range(100):
            if current.parent_document_id is None:
                return current
            parent = await self.get_document(current.parent_document_id)
            if parent is None:
                return current
            current = parent
        return current

    async def _collect_descendants(self, root: Document) -> list[Document]:
        """BFS-collect all descendants of ``root`` + root, ordered by version DESC."""
        collected: dict[int, Document] = {root.id: root}
        frontier: list[int] = [root.id]
        while frontier:
            stmt = select(Document).where(
                or_(
                    Document.parent_document_id.in_(frontier),
                    Document.id.in_(frontier),
                )
            )
            result = await self.db.execute(stmt)
            next_frontier: list[int] = []
            for doc in result.scalars().all():
                if doc.id not in collected:
                    collected[doc.id] = doc
                    next_frontier.append(doc.id)
            frontier = next_frontier
        return sorted(collected.values(), key=lambda d: d.version, reverse=True)

    # ------------------------------------------------------------------
    # Document OCR status
    # ------------------------------------------------------------------

    async def update_document_ocr_applied(self, document_id: int, *, ocr_applied: bool) -> None:
        """Update a document's OCR applied status.

        Args:
            document_id: The document's database ID.
            ocr_applied: Whether OCR was applied.
        """
        result = await self.db.execute(select(Document).where(Document.id == document_id))
        doc = result.scalar_one_or_none()
        if doc:
            doc.ocr_applied = ocr_applied
            await self.db.commit()

    # ------------------------------------------------------------------
    # Tag operations
    # ------------------------------------------------------------------

    async def list_tags(self) -> list[Tag]:
        """List all tags sorted by name.

        Returns:
            List of Tag instances ordered by name.
        """
        result = await self.db.execute(select(Tag).order_by(Tag.name))
        return list(result.scalars().all())

    async def get_tag_by_name(self, name: str) -> Tag | None:
        """Get a tag by its name.

        Args:
            name: Tag name to look up.

        Returns:
            Tag instance or None if not found.
        """
        result = await self.db.execute(select(Tag).where(Tag.name == name))
        return result.scalar_one_or_none()

    async def create_tag(self, name: str) -> Tag:
        """Create a new tag.

        Args:
            name: Tag name (should be lowercase and trimmed).

        Returns:
            The newly created Tag instance.
        """
        tag = Tag(name=name)
        self.db.add(tag)
        await self.db.commit()
        await self.db.refresh(tag)
        return tag

    async def delete_tag(self, tag_id: int) -> bool:
        """Delete a tag by ID.

        Args:
            tag_id: The tag's database ID.

        Returns:
            True if the tag was found and deleted, False otherwise.
        """
        result = await self.db.execute(select(Tag).where(Tag.id == tag_id))
        tag = result.scalar_one_or_none()
        if not tag:
            return False
        await self.db.delete(tag)
        await self.db.commit()
        return True

    async def get_or_create_tag(self, name: str) -> Tag:
        """Find an existing tag or create a new one (race-safe).

        Catches IntegrityError on concurrent inserts to avoid TOCTOU race
        conditions on the unique name constraint.

        Args:
            name: Tag name (should be lowercase and trimmed).

        Returns:
            Existing or newly created Tag instance.
        """
        from sqlalchemy.exc import IntegrityError

        existing = await self.get_tag_by_name(name)
        if existing:
            return existing
        try:
            return await self.create_tag(name)
        except IntegrityError:
            await self.db.rollback()
            tag = await self.get_tag_by_name(name)
            assert tag is not None  # noqa: S101 — guaranteed by unique constraint
            return tag

    async def add_tags_to_document(self, document_id: int, tag_ids: list[int]) -> None:
        """Add tags to a document (ignores duplicates via batched upsert).

        Args:
            document_id: The document's database ID.
            tag_ids: List of tag IDs to associate.
        """
        if not tag_ids:
            return
        values = [{"document_id": document_id, "tag_id": tid} for tid in tag_ids]
        stmt = pg_insert(document_tags).values(values).on_conflict_do_nothing()
        await self.db.execute(stmt)
        await self.db.commit()

    async def remove_tag_from_document(self, document_id: int, tag_id: int) -> None:
        """Remove a tag association from a document.

        Args:
            document_id: The document's database ID.
            tag_id: The tag's database ID.
        """
        stmt = delete(document_tags).where(
            document_tags.c.document_id == document_id,
            document_tags.c.tag_id == tag_id,
        )
        await self.db.execute(stmt)
        await self.db.commit()

    async def get_tags_for_documents(self, document_ids: list[int]) -> dict[int, list[Tag]]:
        """Get all tags for multiple documents in a single query.

        Args:
            document_ids: List of document database IDs.

        Returns:
            Dict mapping document_id to list of Tag instances.
        """
        if not document_ids:
            return {}
        result = await self.db.execute(
            select(document_tags.c.document_id, Tag)
            .join(Tag, document_tags.c.tag_id == Tag.id)
            .where(document_tags.c.document_id.in_(document_ids))
            .order_by(Tag.name)
        )
        tags_map: dict[int, list[Tag]] = {did: [] for did in document_ids}
        for row in result.all():
            doc_id: int = row[0]
            tag: Tag = row[1]
            tags_map[doc_id].append(tag)
        return tags_map

    async def get_tags_for_document(self, document_id: int) -> list[Tag]:
        """Get all tags for a document.

        Args:
            document_id: The document's database ID.

        Returns:
            List of Tag instances ordered by name.
        """
        result = await self.db.execute(
            select(Tag)
            .join(document_tags, Tag.id == document_tags.c.tag_id)
            .where(document_tags.c.document_id == document_id)
            .order_by(Tag.name)
        )
        return list(result.scalars().all())
