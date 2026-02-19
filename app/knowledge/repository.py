# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false
"""Data access layer for knowledge base with pgvector hybrid search."""

from sqlalchemy import distinct, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.knowledge.models import Document, DocumentChunk


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
    ) -> list[Document]:
        """List documents with pagination and optional filtering.

        Args:
            offset: Number of records to skip.
            limit: Maximum records to return.
            domain: Filter by domain.
            status: Filter by processing status.
            language: Filter by language.

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
        query = query.order_by(Document.created_at.desc()).offset(offset).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def count_documents(
        self,
        *,
        domain: str | None = None,
        status: str | None = None,
    ) -> int:
        """Count documents matching the given filters.

        Args:
            domain: Filter by domain.
            status: Filter by processing status.

        Returns:
            Total number of matching documents.
        """
        query = select(func.count()).select_from(Document)
        if domain:
            query = query.where(Document.domain == domain)
        if status:
            query = query.where(Document.status == status)
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

    async def update_document(
        self,
        document_id: int,
        **kwargs: str | None,
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

    async def list_domains(self) -> list[str]:
        """List all unique document domains.

        Returns:
            Sorted list of unique domain strings.
        """
        result = await self.db.execute(select(distinct(Document.domain)).order_by(Document.domain))
        return list(result.scalars().all())

    async def bulk_create_chunks(self, chunks: list[DocumentChunk]) -> None:
        """Bulk insert document chunks.

        Args:
            chunks: List of DocumentChunk instances to insert.
        """
        self.db.add_all(chunks)
        await self.db.commit()

    async def search_vector(
        self,
        query_embedding: list[float],
        limit: int,
        domain: str | None = None,
        language: str | None = None,
    ) -> list[tuple[DocumentChunk, Document, float]]:
        """Search chunks by vector similarity (cosine distance).

        Args:
            query_embedding: Query embedding vector.
            limit: Maximum results.
            domain: Optional domain filter.
            language: Optional language filter.

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
    ) -> list[tuple[DocumentChunk, Document, float]]:
        """Search chunks using PostgreSQL full-text search.

        Uses 'simple' configuration (no language-specific stemming)
        for cross-language support.

        Args:
            query_text: Search text.
            limit: Maximum results.
            domain: Optional domain filter.
            language: Optional language filter.

        Returns:
            List of (chunk, document, rank) tuples sorted by rank descending.
        """
        ts_query = func.plainto_tsquery(text("'simple'"), query_text)
        ts_vector = func.to_tsvector(text("'simple'"), DocumentChunk.content)
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

        result = await self.db.execute(query)
        rows: list[tuple[DocumentChunk, Document, float]] = [
            (row[0], row[1], float(row[2])) for row in result.all()
        ]
        return rows
