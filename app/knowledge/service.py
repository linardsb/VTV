"""Business logic for knowledge base feature.

Orchestrates document ingestion (extract -> chunk -> embed -> store)
and hybrid search (vector + fulltext + RRF fusion + reranking).
"""

from __future__ import annotations

import difflib
import json
import re
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Literal, cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.knowledge import chunking, hyde, processing
from app.knowledge.embedding import EmbeddingProvider, get_embedding_provider
from app.knowledge.entity_extractor import EntityExtractor, get_entity_extractor
from app.knowledge.exceptions import (
    DocumentNotFoundError,
    DocumentVersionConflictError,
    DuplicateTagError,
    ProcessingError,
    TagNotFoundError,
)
from app.knowledge.lemmatizer import LemmaTokenizer, get_lemmatizer_provider
from app.knowledge.models import Document, DocumentChunk
from app.knowledge.repository import KnowledgeRepository
from app.knowledge.reranker import RerankerProvider, get_reranker_provider
from app.knowledge.schemas import (
    DocumentChunkResponse,
    DocumentContentResponse,
    DocumentDiffResponse,
    DocumentResponse,
    DocumentTagRequest,
    DocumentUpdate,
    DocumentUpload,
    DocumentVersionItem,
    DomainListResponse,
    ExtractedEntity,
    SearchRequest,
    SearchResponse,
    SearchResult,
    TagCreate,
    TagListResponse,
    TagResponse,
)
from app.shared.models import utcnow
from app.shared.schemas import PaginatedResponse, PaginationParams

logger = get_logger(__name__)

# Module-level lazy singletons for expensive resources
_embedding_provider: EmbeddingProvider | None = None
_reranker_provider: RerankerProvider | None = None
_lemmatizer_provider: LemmaTokenizer | None = None


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


def _get_reranker() -> RerankerProvider:
    """Get or create the reranker provider singleton."""
    global _reranker_provider
    if _reranker_provider is None:
        _reranker_provider = get_reranker_provider(get_settings())
    return _reranker_provider


async def warm_up_reranker() -> None:
    """Pre-load reranker model for startup."""
    provider = _get_reranker()
    await provider.warm_up()


def _get_lemmatizer() -> LemmaTokenizer:
    """Get or create the Latvian lemmatizer provider singleton (KB-2)."""
    global _lemmatizer_provider
    if _lemmatizer_provider is None:
        _lemmatizer_provider = get_lemmatizer_provider(get_settings())
    return _lemmatizer_provider


async def warm_up_lemmatizer() -> None:
    """Pre-load UDPipe model for startup so the first search has no cold start."""
    await _get_lemmatizer().warm_up()


# Semantic patterns: questions, procedural queries (EN + LV)
_SEMANTIC_PATTERNS = [
    "how ",
    "what ",
    "why ",
    "when ",
    "where ",
    "which ",
    "explain",
    "describe",
    "procedure",
    "process",
    "ka ",
    "kas ",
    "kapec ",
    "kur ",
    "kad ",
    "kada ",
]
# Keyword patterns: numeric tokens like route numbers, stop codes
_KEYWORD_RE = re.compile(r"\b\d{1,4}\b")


def _detect_query_type(query: str) -> Literal["keyword", "semantic", "mixed"]:
    """Classify query to tune RRF weights.

    Keyword indicators: route numbers, stop codes, short numeric tokens.
    Semantic indicators: question words, procedural phrases (EN + LV).

    Args:
        query: The user's search query.

    Returns:
        Query classification: keyword, semantic, or mixed.
    """
    query_lower = query.lower()
    has_semantic = any(p in query_lower for p in _SEMANTIC_PATTERNS)
    has_keyword = bool(_KEYWORD_RE.search(query))

    if has_semantic and not has_keyword:
        return "semantic"
    if has_keyword and not has_semantic:
        return "keyword"
    return "mixed"


def _temporal_boost(
    doc_created_at: datetime,
    query_time: datetime,
    *,
    evergreen: bool,
    settings: Settings,
) -> float:
    """Compute temporal relevance multiplier.

    Evergreen documents (regulations, SOPs) always return 1.0.
    Recent documents get boosted, older documents get penalized.

    Args:
        doc_created_at: When the source document was created.
        query_time: Current time for age calculation.
        evergreen: Whether the document is marked evergreen.
        settings: App settings with temporal boost multipliers.

    Returns:
        Multiplier to apply to the RRF score.
    """
    if not settings.temporal_boost_enabled or evergreen:
        return 1.0

    age = query_time - doc_created_at
    if age.days < 1:
        return settings.temporal_boost_today
    if age.days < 7:
        return settings.temporal_boost_this_week
    if age.days < 30:
        return settings.temporal_boost_this_month
    return settings.temporal_boost_older


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

        # KB-3: same-title version detection. Only runs when the caller
        # explicitly provided a title — auto-derived filename stems are not
        # reliable keys for version chains.
        parent_id: int | None = None
        next_version: int = 1
        if upload.title:
            existing = await self.repository.get_latest_by_title_domain(
                title=upload.title, domain=upload.domain
            )
            if existing is not None:
                parent_id = existing.id
                next_version = existing.version + 1
                await self.repository.mark_superseded(existing.id)
                logger.info(
                    "knowledge.document.superseded",
                    superseded_id=existing.id,
                    superseded_version=existing.version,
                    superseded_by_title=upload.title,
                    domain=upload.domain,
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
            ocr_applied=False,  # Updated after extraction if OCR is applied
            evergreen=upload.evergreen,
            version=next_version,
            parent_document_id=parent_id,
            is_latest=True,
        )

        try:
            # Extract text (PDF may apply OCR for scanned documents)
            text, ocr_applied = await processing.extract_text(file_path, source_type)
            if ocr_applied:
                logger.info("knowledge.ingest.ocr_applied", document_id=doc.id)

            # Store original file on disk
            storage_dir = Path(settings.document_storage_path) / str(doc.id)
            storage_dir.mkdir(parents=True, exist_ok=True)
            stored_path = storage_dir / filename
            if not stored_path.resolve().is_relative_to(storage_dir.resolve()):
                raise ProcessingError(f"Invalid filename: {filename}")
            shutil.copy2(file_path, stored_path)
            await self.repository.update_document_file_path(doc.id, str(stored_path))
            logger.info(
                "knowledge.document.file_stored",
                document_id=doc.id,
                file_path=str(stored_path),
            )

            # Chunk + embed + two-phase parent/child store
            chunk_count = await self._chunk_embed_store(
                document_id=doc.id, text=text, language=upload.language
            )

            if chunk_count == 0:
                await self.repository.update_document_status(doc.id, "completed", None, 0)
                return await self.get_document(doc.id)

            await self.repository.update_document_status(doc.id, "completed", None, chunk_count)

            # Update OCR status if OCR was applied
            if ocr_applied:
                await self.repository.update_document_ocr_applied(doc.id, ocr_applied=True)

            # Auto-tag (best-effort, non-blocking)
            await self._auto_tag_document(doc.id, text)

        except Exception as e:
            try:
                await self.repository.update_document_status(doc.id, "failed", str(e), 0)
            except Exception:
                logger.error(
                    "knowledge.ingest.status_update_failed",
                    document_id=doc.id,
                    exc_info=True,
                )
            # Clean up stored file on failure
            try:
                stored_dir = Path(settings.document_storage_path) / str(doc.id)
                if stored_dir.exists():
                    shutil.rmtree(stored_dir)
                    logger.info("knowledge.ingest.cleanup", document_id=doc.id)
            except Exception:
                logger.error("knowledge.ingest.cleanup_failed", document_id=doc.id)
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
            chunk_count=chunk_count,
            duration_ms=duration_ms,
        )

        return await self.get_document(doc.id)

    async def _chunk_embed_store(self, *, document_id: int, text: str, language: str) -> int:
        """Chunk + embed + two-phase parent/child store for a document.

        Used by both fresh ingestion (``ingest_document``) and the AI-4.4
        re-chunk migration (``rechunk_document``). Reads chunking config from
        settings each call so config flips take effect immediately.

        Caller is responsible for setting the document status before/after.

        Args:
            document_id: The document's database ID.
            text: Already-extracted document text.
            language: Document language code. Used to decide whether to run
                the KB-2 Latvian lemmatizer on chunk content.

        Returns:
            Number of chunks created. Returns 0 for empty/whitespace text.
        """
        settings = get_settings()

        if settings.knowledge_semantic_chunking_enabled:
            chunks = chunking.chunk_text_semantic(
                text,
                target_size=settings.knowledge_chunk_target_size,
                min_size=settings.knowledge_chunk_min_size,
                max_size=settings.knowledge_chunk_max_size,
                chunk_overlap=settings.knowledge_chunk_overlap,
            )
        else:
            chunks = chunking.chunk_text(
                text,
                chunk_size=settings.knowledge_chunk_size,
                chunk_overlap=settings.knowledge_chunk_overlap,
            )

        if not chunks:
            return 0

        # KB-2: populate lemmatized_content for Latvian documents so BM25
        # matches inflected forms. No-op for non-Latvian or disabled.
        if settings.latvian_lemmatizer_enabled:
            chunking.apply_lemmatization(chunks, _get_lemmatizer(), language)

        # Embed
        texts = [c.content for c in chunks]
        embeddings = await _get_embedding().embed(texts)

        # Build parent and child chunk objects.
        # Parents must flush first so children can reference parent ids.
        parent_objects: list[DocumentChunk] = []
        parent_position_to_obj: dict[int, DocumentChunk] = {}
        child_specs: list[tuple[chunking.ChunkResult, list[float], int]] = []
        leaf_specs: list[tuple[chunking.ChunkResult, list[float]]] = []

        for chunk_result, embedding in zip(chunks, embeddings, strict=True):
            if chunk_result.is_parent:
                obj = DocumentChunk(
                    document_id=document_id,
                    content=chunk_result.content,
                    chunk_index=chunk_result.chunk_index,
                    embedding=embedding,
                    metadata_json=(
                        json.dumps(chunk_result.metadata) if chunk_result.metadata else None
                    ),
                    parent_chunk_id=None,
                    heading_path=chunk_result.heading_path,
                    section_type=chunk_result.section_type,
                    lemmatized_content=chunk_result.lemmatized_content,
                )
                parent_objects.append(obj)
                parent_position_to_obj[chunk_result.chunk_index] = obj
            elif chunk_result.parent_index is not None:
                child_specs.append((chunk_result, embedding, chunk_result.parent_index))
            else:
                leaf_specs.append((chunk_result, embedding))

        # Phase 1: flush parents to obtain ids
        if parent_objects:
            await self.repository.bulk_create_chunks(parent_objects, flush_only=True)

        # Phase 2: build children + leaves with resolved parent ids
        child_and_leaf_objects: list[DocumentChunk] = []
        for child_result, child_embedding, parent_position in child_specs:
            parent_obj = parent_position_to_obj.get(parent_position)
            parent_id = parent_obj.id if parent_obj is not None else None
            child_and_leaf_objects.append(
                DocumentChunk(
                    document_id=document_id,
                    content=child_result.content,
                    chunk_index=child_result.chunk_index,
                    embedding=child_embedding,
                    metadata_json=(
                        json.dumps(child_result.metadata) if child_result.metadata else None
                    ),
                    parent_chunk_id=parent_id,
                    heading_path=child_result.heading_path,
                    section_type=child_result.section_type,
                    lemmatized_content=child_result.lemmatized_content,
                )
            )
        for leaf_result, leaf_embedding in leaf_specs:
            child_and_leaf_objects.append(
                DocumentChunk(
                    document_id=document_id,
                    content=leaf_result.content,
                    chunk_index=leaf_result.chunk_index,
                    embedding=leaf_embedding,
                    metadata_json=(
                        json.dumps(leaf_result.metadata) if leaf_result.metadata else None
                    ),
                    parent_chunk_id=None,
                    heading_path=leaf_result.heading_path,
                    section_type=leaf_result.section_type,
                    lemmatized_content=leaf_result.lemmatized_content,
                )
            )

        # Phase 3: commit children + leaves (parents commit with this transaction)
        await self.repository.bulk_create_chunks(child_and_leaf_objects)

        # KB-5: extract entities from each persisted chunk and record mentions.
        # Fail-open — single-chunk extraction failures are logged and skipped
        # so chunk ingest stays durable.
        if settings.entity_extraction_enabled:
            try:
                extractor = await get_entity_extractor()
                await self._record_chunk_entities(
                    chunks=[*parent_objects, *child_and_leaf_objects],
                    extractor=extractor,
                    language=language,
                )
            except Exception as exc:
                logger.warning(
                    "knowledge.ingest.entity_extraction_failed",
                    document_id=document_id,
                    error=str(exc),
                    error_type=type(exc).__name__,
                )

        return len(chunks)

    async def _record_chunk_entities(
        self,
        *,
        chunks: list[DocumentChunk],
        extractor: EntityExtractor,
        language: str,
    ) -> None:
        """Extract + persist entity mentions for the given chunks (KB-5).

        Groups extracted entities by the ``(entity_type, normalized_name)``
        pair, upserts them in one round-trip, then inserts the mention rows
        in batches. Per-chunk failures are swallowed with a warning.
        """
        collected: dict[tuple[str, str], ExtractedEntity] = {}
        per_chunk: list[tuple[int, list[ExtractedEntity]]] = []
        for chunk in chunks:
            if not chunk.content:
                continue
            try:
                mentions = extractor.extract(chunk.content, language)
            except Exception as exc:
                logger.warning(
                    "knowledge.entity_extractor.chunk_failed",
                    chunk_id=chunk.id,
                    error=str(exc),
                    error_type=type(exc).__name__,
                )
                continue
            if not mentions:
                continue
            per_chunk.append((chunk.id, mentions))
            for mention in mentions:
                key = (mention.entity_type, mention.normalized_name)
                collected.setdefault(key, mention)

        if not collected:
            return

        id_map = await self.repository.upsert_entities(list(collected.values()))
        for chunk_id, mentions in per_chunk:
            triples: list[tuple[int, int, str]] = []
            for mention in mentions:
                entity_id = id_map.get((mention.entity_type, mention.normalized_name))
                if entity_id is None:
                    continue
                triples.append(
                    (entity_id, mention.mention_count, mention.extraction_method)
                )
            if triples:
                await self.repository.record_mentions(chunk_id, triples)

    async def rechunk_document(self, document_id: int) -> int:
        """Re-chunk a single document using the current chunking config.

        Deletes existing chunks, re-extracts text from the stored file,
        re-runs the chunk → embed → store pipeline, and updates the
        document chunk_count.

        Document metadata, tags, language, domain, and ``evergreen`` flag are
        NOT touched. Auto-tagging is not re-run (it would clobber human edits).

        Args:
            document_id: The document's database ID.

        Returns:
            New chunk count after re-chunking.

        Raises:
            DocumentNotFoundError: Document does not exist.
            ProcessingError: ``file_path`` is missing or extraction fails.
        """
        doc = await self.repository.get_document(document_id)
        if doc is None:
            raise DocumentNotFoundError(f"Document {document_id} not found")
        if not doc.file_path:
            raise ProcessingError(
                f"Document {document_id} has no stored file_path; cannot re-extract"
            )

        start = time.monotonic()
        logger.info(
            "knowledge.rechunk.started",
            document_id=document_id,
            filename=doc.filename,
            source_type=doc.source_type,
        )

        try:
            text, ocr_applied = await processing.extract_text(doc.file_path, doc.source_type)
            await self.repository.delete_chunks_by_document(document_id)
            chunk_count = await self._chunk_embed_store(
                document_id=document_id, text=text, language=doc.language
            )
            await self.repository.update_document_status(
                document_id, "completed", None, chunk_count
            )
            if ocr_applied:
                await self.repository.update_document_ocr_applied(document_id, ocr_applied=True)
        except Exception as e:
            try:
                await self.repository.update_document_status(document_id, "failed", str(e), 0)
            except Exception:
                logger.error(
                    "knowledge.rechunk.status_update_failed",
                    document_id=document_id,
                    exc_info=True,
                )
            duration_ms = int((time.monotonic() - start) * 1000)
            logger.error(
                "knowledge.rechunk.failed",
                exc_info=True,
                error=str(e),
                error_type=type(e).__name__,
                document_id=document_id,
                duration_ms=duration_ms,
            )
            raise

        duration_ms = int((time.monotonic() - start) * 1000)
        logger.info(
            "knowledge.rechunk.completed",
            document_id=document_id,
            chunk_count=chunk_count,
            duration_ms=duration_ms,
        )
        return chunk_count

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
        return await self.get_document(document_id)

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

        # HyDE: optionally expand query before embedding
        embed_text = request.query
        if settings.knowledge_hyde_enabled:
            embed_text = await hyde.expand_query(request.query, settings)

        # Get query embedding (use expanded text for vector, raw query for fulltext)
        query_embedding = (await _get_embedding().embed([embed_text]))[0]

        # Run both searches
        search_limit = settings.knowledge_search_limit
        vector_results = await self.repository.search_vector(
            query_embedding,
            search_limit,
            request.domain,
            request.language,
            request.created_after,
            request.created_before,
            include_superseded=request.include_superseded,
        )
        # KB-2: lemmatize Latvian queries so BM25 matches inflected forms.
        # Fail-safe: exceptions log and fall back to raw query via COALESCE.
        lemmatized_query: str | None = None
        if settings.latvian_lemmatizer_enabled:
            try:
                candidate = _get_lemmatizer().lemmatize(request.query, "lv")
                if candidate and candidate != request.query:
                    lemmatized_query = candidate
            except Exception as exc:
                logger.error(
                    "knowledge.lemmatizer.failed",
                    reason="query_lemmatize_error",
                    error=str(exc),
                    error_type=type(exc).__name__,
                )

        text_results = await self.repository.search_fulltext(
            request.query,
            search_limit,
            request.domain,
            request.language,
            request.created_after,
            request.created_before,
            lemmatized_query=lemmatized_query,
            include_superseded=request.include_superseded,
        )

        # Detect query type and select RRF weights
        query_type = _detect_query_type(request.query)
        logger.info(
            "knowledge.search.query_type_detected",
            query_type=query_type,
            query_length=len(request.query),
        )

        if query_type == "keyword":
            vector_weight = settings.rrf_keyword_vector_weight
            text_weight = settings.rrf_keyword_text_weight
        elif query_type == "semantic":
            vector_weight = settings.rrf_semantic_vector_weight
            text_weight = settings.rrf_semantic_text_weight
        else:
            vector_weight = settings.rrf_mixed_vector_weight
            text_weight = settings.rrf_mixed_text_weight

        # RRF fusion with adaptive weights
        rrf_k = 60
        chunk_scores: dict[int, float] = {}
        chunk_data: dict[int, tuple[DocumentChunk, Document]] = {}

        for rank, (chunk, doc, _dist) in enumerate(vector_results):
            chunk_scores[chunk.id] = chunk_scores.get(chunk.id, 0.0) + vector_weight / (
                rrf_k + rank
            )
            chunk_data[chunk.id] = (chunk, doc)

        for rank, (chunk, doc, _rank_score) in enumerate(text_results):
            chunk_scores[chunk.id] = chunk_scores.get(chunk.id, 0.0) + text_weight / (rrf_k + rank)
            chunk_data[chunk.id] = (chunk, doc)

        # Apply temporal boost
        query_time = utcnow()
        for chunk_id in chunk_scores:
            _, d = chunk_data[chunk_id]
            doc_created = cast(datetime, d.created_at)
            boost = _temporal_boost(
                doc_created, query_time, evergreen=d.evergreen, settings=settings
            )
            chunk_scores[chunk_id] *= boost

        # KB-5: entity boost — multiply scores of chunks sharing entities
        # with the query. Fails open (pure RRF + temporal) on any error.
        if settings.entity_boost_enabled and settings.entity_extraction_enabled:
            try:
                extractor = await get_entity_extractor()
                query_entities = extractor.extract(
                    request.query[:500], request.language or "lv"
                )
                if query_entities:
                    query_entity_ids = await self.repository.get_entity_ids_for_names(
                        [(e.entity_type, e.normalized_name) for e in query_entities]
                    )
                    if query_entity_ids:
                        chunk_entity_map = await self.repository.get_entity_ids_for_chunks(
                            list(chunk_scores.keys())
                        )
                        boost_mult = settings.entity_boost_multiplier
                        boosted = 0
                        for cid in chunk_scores:
                            shared = chunk_entity_map.get(cid, frozenset()) & query_entity_ids
                            if shared:
                                chunk_scores[cid] *= boost_mult
                                boosted += 1
                        logger.info(
                            "knowledge.search.entity_boost_applied",
                            query_entity_count=len(query_entities),
                            matched_entity_ids=len(query_entity_ids),
                            boosted_chunks=boosted,
                            multiplier=boost_mult,
                        )
            except Exception as exc:
                logger.warning(
                    "knowledge.search.entity_boost_failed",
                    error=str(exc),
                    error_type=type(exc).__name__,
                )

        # Sort by boosted RRF score
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
            chunk, d = chunk_data[cid]
            d_created = cast(datetime, d.created_at)
            results.append(
                SearchResult(
                    chunk_content=chunk.content,
                    document_id=chunk.document_id,
                    document_filename=d.filename,
                    domain=d.domain,
                    language=d.language,
                    chunk_index=chunk.chunk_index,
                    score=rr.score,
                    metadata_json=chunk.metadata_json,
                    document_created_at=d_created,
                    heading_path=chunk.heading_path,
                    version=d.version,
                    is_latest=d.is_latest,
                )
            )

        # Filter by confidence threshold
        threshold = settings.knowledge_confidence_threshold
        pre_filter_count = len(results)
        results = [r for r in results if r.score >= threshold]

        logger.info(
            "knowledge.search.confidence_filtered",
            threshold=threshold,
            pre_filter_count=pre_filter_count,
            post_filter_count=len(results),
            query=request.query[:80],
        )

        # Parent-child context expansion (AI-4.3)
        parent_count = 0
        unique_parents = 0
        if settings.knowledge_parent_context_enabled and results:
            # Collect unique parent_chunk_ids from surviving results.
            # chunk_data still holds the ORM instances by chunk.id; locate the
            # source chunk for each SearchResult via (document_id, chunk_index).
            parent_ids: set[int] = set()
            result_to_chunk: dict[int, DocumentChunk] = {}
            for r in results:
                for _cid, (chunk, _doc) in chunk_data.items():
                    if chunk.document_id == r.document_id and chunk.chunk_index == r.chunk_index:
                        result_to_chunk[id(r)] = chunk
                        if chunk.parent_chunk_id is not None:
                            parent_ids.add(chunk.parent_chunk_id)
                        break

            unique_parents = len(parent_ids)
            if parent_ids:
                parent_chunks = await self.repository.get_chunks_by_ids(list(parent_ids))
                parents_by_id: dict[int, DocumentChunk] = {p.id: p for p in parent_chunks}
                max_chars = settings.knowledge_parent_context_max_chars
                for r in results:
                    source_chunk = result_to_chunk.get(id(r))
                    if source_chunk is None or source_chunk.parent_chunk_id is None:
                        continue
                    parent = parents_by_id.get(source_chunk.parent_chunk_id)
                    if parent is None:
                        continue
                    r.parent_chunk_id = parent.id
                    r.parent_content = parent.content[:max_chars]
                    r.heading_path = parent.heading_path
                    parent_count += 1

            logger.info(
                "knowledge.search.parent_context_attached",
                result_count=len(results),
                parent_count=parent_count,
                unique_parents=unique_parents,
            )

        # KB-5: populate SearchResult.entities for surfacing to clients.
        if settings.entity_extraction_enabled and results:
            try:
                top_chunk_ids: list[int] = []
                result_chunk_ids: dict[int, int] = {}
                for r in results:
                    for cid, (chunk, _doc) in chunk_data.items():
                        if (
                            chunk.document_id == r.document_id
                            and chunk.chunk_index == r.chunk_index
                        ):
                            top_chunk_ids.append(cid)
                            result_chunk_ids[id(r)] = cid
                            break
                name_map = await self.repository.get_entity_names_for_chunks(top_chunk_ids)
                for r in results:
                    resolved_cid = result_chunk_ids.get(id(r))
                    if resolved_cid is None:
                        continue
                    names = name_map.get(resolved_cid)
                    if names:
                        r.entities = names
            except Exception as exc:
                logger.warning(
                    "knowledge.search.entity_names_failed",
                    error=str(exc),
                    error_type=type(exc).__name__,
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
        doc_resp = DocumentResponse.model_validate(doc)
        doc_tags = await self.repository.get_tags_for_document(document_id)
        doc_resp.tags = [TagResponse.model_validate(t) for t in doc_tags]
        return doc_resp

    async def list_documents(
        self,
        pagination: PaginationParams,
        *,
        domain: str | None = None,
        status: str | None = None,
        tag: str | None = None,
        include_superseded: bool = False,
    ) -> PaginatedResponse[DocumentResponse]:
        """List documents with pagination and optional filtering.

        Args:
            pagination: Page and page_size parameters.
            domain: Filter by domain.
            status: Filter by processing status.
            tag: Filter by tag name.
            include_superseded: When False (default), hide rows whose
                ``is_latest`` flag has been cleared by a newer version.

        Returns:
            Paginated list of DocumentResponse items.
        """
        docs = await self.repository.list_documents(
            offset=pagination.offset,
            limit=pagination.page_size,
            domain=domain,
            status=status,
            tag=tag,
            include_superseded=include_superseded,
        )
        total = await self.repository.count_documents(
            domain=domain,
            status=status,
            tag=tag,
            include_superseded=include_superseded,
        )

        # Batch load tags for all documents in a single query (avoids N+1)
        doc_ids = [d.id for d in docs]
        tags_map = await self.repository.get_tags_for_documents(doc_ids)

        items: list[DocumentResponse] = []
        for d in docs:
            doc_resp = DocumentResponse.model_validate(d)
            doc_resp.tags = [TagResponse.model_validate(t) for t in tags_map.get(d.id, [])]
            items.append(doc_resp)

        return PaginatedResponse[DocumentResponse](
            items=items,
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
        )

    # ------------------------------------------------------------------
    # KB-3: Document versioning
    # ------------------------------------------------------------------

    async def get_document_versions(self, document_id: int) -> list[DocumentVersionItem]:
        """Return the full version chain for ``document_id``, newest first.

        Args:
            document_id: Any row in the chain.

        Returns:
            List of ``DocumentVersionItem`` ordered by ``version`` descending.

        Raises:
            DocumentNotFoundError: When ``document_id`` does not exist.
        """
        versions = await self.repository.list_versions(document_id)
        if not versions:
            raise DocumentNotFoundError(f"Document {document_id} not found")
        return [DocumentVersionItem.model_validate(d) for d in versions]

    async def get_document_diff(self, document_id: int, v1: int, v2: int) -> DocumentDiffResponse:
        """Produce a unified diff between two versions in the chain.

        Args:
            document_id: Any row in the chain.
            v1: Version number of the "from" side.
            v2: Version number of the "to" side.

        Returns:
            ``DocumentDiffResponse`` with the unified diff and line counts.

        Raises:
            DocumentVersionConflictError: When ``v1 == v2``.
            DocumentNotFoundError: When the document or either version is missing.
        """
        if v1 == v2:
            raise DocumentVersionConflictError("v1 and v2 must differ")
        chain = await self.repository.list_versions(document_id)
        if not chain:
            raise DocumentNotFoundError(f"Document {document_id} not found")
        by_version = {d.version: d for d in chain}
        if v1 not in by_version or v2 not in by_version:
            raise DocumentNotFoundError(f"Version not found in chain for document {document_id}")
        doc_a = by_version[v1]
        doc_b = by_version[v2]
        text_a = await self._concatenate_chunks(doc_a.id)
        text_b = await self._concatenate_chunks(doc_b.id)
        diff_lines = list(
            difflib.unified_diff(
                text_a.splitlines(),
                text_b.splitlines(),
                fromfile=f"v{v1}",
                tofile=f"v{v2}",
                lineterm="",
            )
        )
        added = sum(1 for line in diff_lines if line.startswith("+") and not line.startswith("+++"))
        removed = sum(
            1 for line in diff_lines if line.startswith("-") and not line.startswith("---")
        )
        # ``list_versions`` returns newest-first; the chain root (v=1) is last.
        root = chain[-1]
        logger.info(
            "knowledge.document.diff_completed",
            document_id=root.id,
            v1=v1,
            v2=v2,
            lines_added=added,
            lines_removed=removed,
        )
        return DocumentDiffResponse(
            document_id=root.id,
            v1=v1,
            v2=v2,
            v1_document_id=doc_a.id,
            v2_document_id=doc_b.id,
            unified_diff="\n".join(diff_lines),
            lines_added=added,
            lines_removed=removed,
        )

    async def _concatenate_chunks(self, doc_id: int) -> str:
        """Concatenate a document's chunks in order for text comparison."""
        chunks = await self.repository.get_chunks_by_document(doc_id)
        return "\n".join(c.content for c in chunks)

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

    # ------------------------------------------------------------------
    # Tag management
    # ------------------------------------------------------------------

    async def list_tags(self) -> TagListResponse:
        """List all tags sorted by name.

        Returns:
            TagListResponse with all tags.
        """
        tags = await self.repository.list_tags()
        tag_items = [TagResponse.model_validate(t) for t in tags]
        return TagListResponse(tags=tag_items, total=len(tag_items))

    async def create_tag(self, data: TagCreate) -> TagResponse:
        """Create a new tag.

        Args:
            data: Tag creation data with normalized name.

        Returns:
            The newly created TagResponse.

        Raises:
            DuplicateTagError: If a tag with this name already exists.
        """
        existing = await self.repository.get_tag_by_name(data.name)
        if existing:
            raise DuplicateTagError(f"Tag '{data.name}' already exists")
        tag = await self.repository.create_tag(data.name)
        logger.info("knowledge.tag.created", tag_id=tag.id, tag_name=tag.name)
        return TagResponse.model_validate(tag)

    async def delete_tag(self, tag_id: int) -> None:
        """Delete a tag by ID (CASCADE removes document associations).

        Args:
            tag_id: The tag's database ID.

        Raises:
            TagNotFoundError: If tag does not exist.
        """
        deleted = await self.repository.delete_tag(tag_id)
        if not deleted:
            raise TagNotFoundError(f"Tag {tag_id} not found")
        logger.info("knowledge.tag.deleted", tag_id=tag_id)

    async def add_tags_to_document(
        self, document_id: int, data: DocumentTagRequest
    ) -> DocumentResponse:
        """Add tags to a document.

        Args:
            document_id: The document's database ID.
            data: Request containing tag IDs to assign.

        Returns:
            Updated DocumentResponse with tags.

        Raises:
            DocumentNotFoundError: If document does not exist.
        """
        doc = await self.repository.get_document(document_id)
        if not doc:
            raise DocumentNotFoundError(f"Document {document_id} not found")
        await self.repository.add_tags_to_document(document_id, data.tag_ids)
        logger.info(
            "knowledge.document.tags_updated",
            document_id=document_id,
            tag_ids=data.tag_ids,
            action="add",
        )
        return await self.get_document(document_id)

    async def remove_tag_from_document(self, document_id: int, tag_id: int) -> DocumentResponse:
        """Remove a tag from a document.

        Args:
            document_id: The document's database ID.
            tag_id: The tag's database ID.

        Returns:
            Updated DocumentResponse with tags.

        Raises:
            DocumentNotFoundError: If document does not exist.
        """
        doc = await self.repository.get_document(document_id)
        if not doc:
            raise DocumentNotFoundError(f"Document {document_id} not found")
        await self.repository.remove_tag_from_document(document_id, tag_id)
        logger.info(
            "knowledge.document.tags_updated",
            document_id=document_id,
            tag_id=tag_id,
            action="remove",
        )
        return await self.get_document(document_id)

    # ------------------------------------------------------------------
    # Auto-tagging (LLM classification, best-effort)
    # ------------------------------------------------------------------

    async def _auto_tag_document(self, document_id: int, text: str) -> None:
        """Auto-tag a document using LLM classification.

        Best-effort: failures are logged but never raise exceptions.
        Only runs when auto_tag_enabled is True in settings.

        Args:
            document_id: The document's database ID.
            text: Extracted document text.
        """
        import json as json_lib
        from typing import Any, cast

        settings = get_settings()
        if not settings.auto_tag_enabled:
            return

        logger.info("knowledge.autotag.started", document_id=document_id)

        try:
            from pydantic_ai import Agent

            truncated = text[: settings.auto_tag_max_chars]
            agent = Agent(
                f"{settings.llm_provider}:{settings.llm_model}",
                system_prompt=(
                    "You are a document classifier. Given document text, return 1-3 short "
                    "tags as a JSON array of lowercase single-word strings. "
                    'Example: ["transit", "policy", "safety"]. Return ONLY the JSON array.'
                ),
            )
            result = await agent.run(truncated)
            raw_response = str(result.response)

            # Parse the JSON array from LLM response
            parsed = json_lib.loads(raw_response)
            if not isinstance(parsed, list):
                logger.warning(
                    "knowledge.autotag.failed",
                    document_id=document_id,
                    reason="LLM response is not a list",
                )
                return
            tag_names: list[Any] = cast(list[Any], parsed)  # type: ignore[redundant-cast]

            # Normalize and create/link tags
            created_count = 0
            for name in tag_names[:3]:  # Cap at 3 tags
                if not isinstance(name, str) or not name.strip():
                    continue
                normalized = name.strip().lower()
                tag = await self.repository.get_or_create_tag(normalized)
                await self.repository.add_tags_to_document(document_id, [tag.id])
                created_count += 1

            logger.info(
                "knowledge.autotag.completed",
                document_id=document_id,
                tag_count=created_count,
            )

        except Exception as e:
            logger.warning(
                "knowledge.autotag.failed",
                document_id=document_id,
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True,
            )
