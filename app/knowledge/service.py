"""Business logic for knowledge base feature.

Orchestrates document ingestion (extract -> chunk -> embed -> store)
and hybrid search (vector + fulltext + RRF fusion + reranking).
"""

from __future__ import annotations

import shutil
import time
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.knowledge import chunking, processing
from app.knowledge.embedding import EmbeddingProvider, get_embedding_provider
from app.knowledge.exceptions import DocumentNotFoundError, ProcessingError
from app.knowledge.models import DocumentChunk
from app.knowledge.repository import KnowledgeRepository
from app.knowledge.reranker import RerankerProvider, get_reranker_provider
from app.knowledge.schemas import (
    DocumentChunkResponse,
    DocumentContentResponse,
    DocumentResponse,
    DocumentUpdate,
    DocumentUpload,
    DomainListResponse,
    SearchRequest,
    SearchResponse,
    SearchResult,
)
from app.shared.schemas import PaginatedResponse, PaginationParams

logger = get_logger(__name__)

# Module-level lazy singletons for expensive resources
_embedding_provider: EmbeddingProvider | None = None
_reranker_provider: RerankerProvider | None = None


def _get_embedding() -> EmbeddingProvider:
    """Get or create the embedding provider singleton."""
    global _embedding_provider
    if _embedding_provider is None:
        _embedding_provider = get_embedding_provider(get_settings())
    return _embedding_provider


def _get_reranker() -> RerankerProvider:
    """Get or create the reranker provider singleton."""
    global _reranker_provider
    if _reranker_provider is None:
        _reranker_provider = get_reranker_provider(get_settings())
    return _reranker_provider


class KnowledgeService:
    """Business logic for knowledge base operations."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize with database session.

        Args:
            db: SQLAlchemy async session.
        """
        self.db = db
        self.repository = KnowledgeRepository(db)

    async def ingest_document(
        self,
        *,
        file_path: str,
        upload: DocumentUpload,
        filename: str,
        source_type: str,
        file_size: int | None,
    ) -> DocumentResponse:
        """Ingest a document: extract text, chunk, embed, and store.

        Args:
            file_path: Absolute path to the uploaded file on disk.
            upload: Upload metadata (domain, language, title, description).
            filename: Original filename.
            source_type: Detected file type (pdf, docx, email, image, text, xlsx, csv).
            file_size: File size in bytes.

        Returns:
            DocumentResponse for the ingested document.

        Raises:
            ProcessingError: If extraction or embedding fails.
        """
        settings = get_settings()
        start = time.monotonic()
        title = upload.title if upload.title else Path(filename).stem
        logger.info(
            "knowledge.ingest.started",
            filename=filename,
            title=title,
            domain=upload.domain,
            source_type=source_type,
        )

        doc = await self.repository.create_document(
            filename=filename,
            domain=upload.domain,
            source_type=source_type,
            language=upload.language,
            file_size_bytes=file_size,
            metadata_json=upload.metadata_json,
            title=title,
            description=upload.description,
            status="processing",
        )

        try:
            # Extract text
            text = await processing.extract_text(file_path, source_type)

            # Store original file on disk
            storage_dir = Path(settings.document_storage_path) / str(doc.id)
            storage_dir.mkdir(parents=True, exist_ok=True)
            stored_path = storage_dir / filename
            shutil.copy2(file_path, stored_path)
            await self.repository.update_document_file_path(doc.id, str(stored_path))
            logger.info(
                "knowledge.document.file_stored",
                document_id=doc.id,
                file_path=str(stored_path),
            )

            # Chunk
            chunks = chunking.chunk_text(
                text,
                chunk_size=settings.knowledge_chunk_size,
                chunk_overlap=settings.knowledge_chunk_overlap,
            )

            if not chunks:
                await self.repository.update_document_status(doc.id, "completed", None, 0)
                await self.db.refresh(doc)
                return DocumentResponse.model_validate(doc)

            # Embed
            texts = [c.content for c in chunks]
            embeddings = await _get_embedding().embed(texts)

            # Build chunk objects
            chunk_objects = [
                DocumentChunk(
                    document_id=doc.id,
                    content=chunks[i].content,
                    chunk_index=chunks[i].chunk_index,
                    embedding=embeddings[i],
                    metadata_json=None,
                )
                for i in range(len(chunks))
            ]

            # Store
            await self.repository.bulk_create_chunks(chunk_objects)
            await self.repository.update_document_status(doc.id, "completed", None, len(chunks))

        except Exception as e:
            await self.repository.update_document_status(doc.id, "failed", str(e), 0)
            duration_ms = int((time.monotonic() - start) * 1000)
            logger.error(
                "knowledge.ingest.failed",
                exc_info=True,
                error=str(e),
                error_type=type(e).__name__,
                document_id=doc.id,
                duration_ms=duration_ms,
            )
            raise

        duration_ms = int((time.monotonic() - start) * 1000)
        logger.info(
            "knowledge.ingest.completed",
            document_id=doc.id,
            chunk_count=len(chunks),
            duration_ms=duration_ms,
        )

        await self.db.refresh(doc)
        return DocumentResponse.model_validate(doc)

    async def update_document(self, document_id: int, data: DocumentUpdate) -> DocumentResponse:
        """Update document metadata.

        Args:
            document_id: The document's database ID.
            data: Fields to update (only non-None fields are applied).

        Returns:
            Updated DocumentResponse.

        Raises:
            DocumentNotFoundError: If document does not exist.
        """
        logger.info("knowledge.document.update_started", document_id=document_id)
        updated = await self.repository.update_document(
            document_id, **data.model_dump(exclude_unset=True)
        )
        if not updated:
            raise DocumentNotFoundError(f"Document {document_id} not found")
        logger.info("knowledge.document.update_completed", document_id=document_id)
        return DocumentResponse.model_validate(updated)

    async def get_document_content(self, document_id: int) -> DocumentContentResponse:
        """Get document metadata and extracted text chunks.

        Args:
            document_id: The document's database ID.

        Returns:
            DocumentContentResponse with chunks ordered by index.

        Raises:
            DocumentNotFoundError: If document does not exist.
        """
        doc = await self.repository.get_document(document_id)
        if not doc:
            raise DocumentNotFoundError(f"Document {document_id} not found")

        chunks = await self.repository.get_chunks_by_document(document_id)
        logger.info(
            "knowledge.document.content_retrieved",
            document_id=document_id,
            chunk_count=len(chunks),
        )

        return DocumentContentResponse(
            document_id=doc.id,
            filename=doc.filename,
            title=doc.title,
            total_chunks=len(chunks),
            chunks=[
                DocumentChunkResponse(chunk_index=c.chunk_index, content=c.content) for c in chunks
            ],
        )

    async def get_document_file_path(self, document_id: int) -> tuple[str, str]:
        """Get the stored file path and filename for download.

        Args:
            document_id: The document's database ID.

        Returns:
            Tuple of (file_path, filename).

        Raises:
            DocumentNotFoundError: If document does not exist.
            ProcessingError: If file is not stored (legacy document).
        """
        doc = await self.repository.get_document(document_id)
        if not doc:
            raise DocumentNotFoundError(f"Document {document_id} not found")
        if not doc.file_path:
            raise ProcessingError(f"Document {document_id} has no stored file (legacy upload)")
        return (doc.file_path, doc.filename)

    async def list_domains(self) -> DomainListResponse:
        """List all unique document domains.

        Returns:
            DomainListResponse with sorted domain names.
        """
        domains = await self.repository.list_domains()
        logger.info("knowledge.domains.list_completed", domain_count=len(domains))
        return DomainListResponse(domains=domains, total=len(domains))

    async def search(self, request: SearchRequest) -> SearchResponse:
        """Hybrid search: vector + fulltext + RRF fusion + reranking.

        Args:
            request: Search parameters (query, domain, language, limit).

        Returns:
            SearchResponse with ranked results.
        """
        settings = get_settings()
        start = time.monotonic()
        logger.info(
            "knowledge.search.started",
            query_length=len(request.query),
            domain=request.domain,
            language=request.language,
        )

        # Get query embedding
        query_embedding = (await _get_embedding().embed([request.query]))[0]

        # Run both searches
        search_limit = settings.knowledge_search_limit
        vector_results = await self.repository.search_vector(
            query_embedding, search_limit, request.domain, request.language
        )
        text_results = await self.repository.search_fulltext(
            request.query, search_limit, request.domain, request.language
        )

        # RRF fusion
        rrf_k = 60
        chunk_scores: dict[int, float] = {}
        chunk_data: dict[int, tuple[DocumentChunk, str, str, str]] = {}

        for rank, (chunk, doc, _dist) in enumerate(vector_results):
            chunk_scores[chunk.id] = chunk_scores.get(chunk.id, 0.0) + 1.0 / (rrf_k + rank)
            chunk_data[chunk.id] = (chunk, doc.filename, doc.domain, doc.language)

        for rank, (chunk, doc, _rank_score) in enumerate(text_results):
            chunk_scores[chunk.id] = chunk_scores.get(chunk.id, 0.0) + 1.0 / (rrf_k + rank)
            chunk_data[chunk.id] = (chunk, doc.filename, doc.domain, doc.language)

        # Sort by RRF score
        sorted_ids = sorted(chunk_scores.keys(), key=lambda cid: chunk_scores[cid], reverse=True)
        total_candidates = len(sorted_ids)

        # Extract top candidates for reranking
        rerank_limit = min(settings.reranker_top_k, len(sorted_ids))
        top_ids = sorted_ids[:rerank_limit]
        top_contents = [chunk_data[cid][0].content for cid in top_ids]

        # Rerank
        reranked = await _get_reranker().rerank(request.query, top_contents, request.limit)
        is_reranked = settings.reranker_provider.lower() != "none"

        # Build results
        results: list[SearchResult] = []
        for rr in reranked:
            cid = top_ids[rr.index]
            chunk, doc_filename, doc_domain, doc_language = chunk_data[cid]
            results.append(
                SearchResult(
                    chunk_content=chunk.content,
                    document_id=chunk.document_id,
                    document_filename=doc_filename,
                    domain=doc_domain,
                    language=doc_language,
                    chunk_index=chunk.chunk_index,
                    score=rr.score,
                    metadata_json=chunk.metadata_json,
                )
            )

        duration_ms = int((time.monotonic() - start) * 1000)
        logger.info(
            "knowledge.search.completed",
            result_count=len(results),
            total_candidates=total_candidates,
            reranked=is_reranked,
            duration_ms=duration_ms,
        )

        return SearchResponse(
            results=results,
            query=request.query,
            total_candidates=total_candidates,
            reranked=is_reranked,
        )

    async def get_document(self, document_id: int) -> DocumentResponse:
        """Get a document by ID.

        Args:
            document_id: The document's database ID.

        Returns:
            DocumentResponse for the found document.

        Raises:
            DocumentNotFoundError: If document does not exist.
        """
        doc = await self.repository.get_document(document_id)
        if not doc:
            raise DocumentNotFoundError(f"Document {document_id} not found")
        return DocumentResponse.model_validate(doc)

    async def list_documents(
        self,
        pagination: PaginationParams,
        *,
        domain: str | None = None,
        status: str | None = None,
    ) -> PaginatedResponse[DocumentResponse]:
        """List documents with pagination and optional filtering.

        Args:
            pagination: Page and page_size parameters.
            domain: Filter by domain.
            status: Filter by processing status.

        Returns:
            Paginated list of DocumentResponse items.
        """
        docs = await self.repository.list_documents(
            offset=pagination.offset,
            limit=pagination.page_size,
            domain=domain,
            status=status,
        )
        total = await self.repository.count_documents(domain=domain, status=status)
        items = [DocumentResponse.model_validate(d) for d in docs]
        return PaginatedResponse[DocumentResponse](
            items=items,
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
        )

    async def delete_document(self, document_id: int) -> None:
        """Delete a document, its chunks, and stored file.

        Args:
            document_id: The document's database ID.

        Raises:
            DocumentNotFoundError: If document does not exist.
        """
        doc = await self.repository.get_document(document_id)
        if not doc:
            raise DocumentNotFoundError(f"Document {document_id} not found")

        # Clean up stored file if present
        if doc.file_path:
            file_dir = Path(doc.file_path).parent
            shutil.rmtree(file_dir, ignore_errors=True)
            logger.info(
                "knowledge.document.file_deleted",
                document_id=document_id,
                file_dir=str(file_dir),
            )

        await self.repository.delete_document(document_id)
        logger.info("knowledge.delete.completed", document_id=document_id)
