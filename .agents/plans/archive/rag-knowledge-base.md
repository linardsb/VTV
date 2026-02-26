# Plan: RAG Knowledge Base System

## Feature Metadata
**Feature Type**: New Capability
**Estimated Complexity**: High
**Primary Systems Affected**: `app/knowledge/` (new feature slice), `app/core/agents/` (new tool), `app/core/config.py`, `pyproject.toml`, `alembic/`, `docker-compose.yml`

## Feature Description

VTV needs a Retrieval-Augmented Generation (RAG) system to search unstructured organizational knowledge — admin messages, emails, Word documents, PDFs, images, driver records, government API data, compliance docs, and legal materials. Data is multilingual (Latvian primary, English secondary) with ambiguous natural language, synonyms, and domain-specific transit terminology.

Pipeline: **Ingest -> Extract -> Chunk -> Embed -> Store -> Retrieve -> Rerank -> Generate**. Documents uploaded via REST API, processed into chunks, embedded via configurable provider (OpenAI/Jina API or self-hosted BGE-M3), stored in PostgreSQL+pgvector. Retrieval uses hybrid search (vector + full-text) with RRF fusion, reranked by cross-encoder before agent synthesizes a response.

The agent gains a `search_knowledge_base` tool following the same Pydantic AI pattern as existing transit/Obsidian tools. The LLM decides when to use it — no separate routing logic.

## User Story

As a **dispatcher or administrator** I want to **ask the AI assistant about organizational documents, policies, driver info, compliance rules** so that **I can find answers without manually searching hundreds of documents in Latvian or English**.

## Solution Approach

We extend PostgreSQL with pgvector to store embeddings alongside relational data. Single `document_chunks` table with domain/language metadata columns. Embedding provider abstracted behind configurable interface (mirroring LLM provider pattern from `app/core/agents/config.py` lines 15-56).

**Approach Decision:** pgvector in existing PostgreSQL because:
- No new infrastructure; modest scale (thousands of docs, not millions)
- ACID joins between vector results and relational data
- One database, one backup, one migration path

**Alternatives Considered:**
- Qdrant/Pinecone: Rejected — overkill for VTV's scale, adds sync pipeline
- Separate collections per domain: Rejected — single table with metadata filtering enables cross-domain

## Relevant Files

### Core Files (MUST read before implementing)
- `CLAUDE.md` — Architecture rules, anti-patterns 1-14, logging patterns
- `app/core/config.py` (lines 15-76) — Settings class; add embedding/reranker fields after line 75
- `app/core/database.py` (lines 26-32) — `AsyncSessionLocal` session factory; agent tool uses this directly
- `app/core/agents/tools/transit/deps.py` (lines 14-27) — `UnifiedDeps` dataclass
- `app/core/agents/agent.py` (lines 44-82) — `create_agent()` factory + tool list

### Similar Features (exact patterns to replicate)
- `app/stops/models.py` (lines 14-35) — `class Stop(Base, TimestampMixin):` with `Mapped[]` columns
- `app/stops/schemas.py` (lines 8-53) — Schema hierarchy: Base -> Create -> Response with `from_attributes=True`
- `app/stops/repository.py` (lines 10-135) — `__init__(self, db: AsyncSession)`, `select()` queries
- `app/stops/service.py` (lines 53-60) — Service creates own repository in `__init__`
- `app/stops/routes.py` (line 1) — pyright directive, (lines 22-24) service factory, (line 37) `_ = request`
- `app/stops/exceptions.py` (lines 1-22) — Feature exceptions inheriting core bases
- `app/core/agents/tools/transit/search_stops.py` (lines 173-325) — Tool signature, docstring, error return
- `app/core/agents/tools/obsidian/query_vault.py` (lines 125-126) — `_settings = ctx.deps.settings`

### Files to Modify
- `pyproject.toml` (lines 7-20, 66-75, 100-112) — deps, ruff ignores, mypy overrides
- `app/core/config.py` (after line 75) — 11 new settings fields
- `.env.example` (after line 43) — Document new env vars
- `app/core/agents/agent.py` (lines 12-76) — Import + register new tool
- `app/main.py` (lines 33-34, 98) — Import + register knowledge_router
- `alembic/env.py` (after line 10) — Register knowledge models
- `docker-compose.yml` (line 3) — Switch to pgvector PostgreSQL image

## Step by Step Tasks

### Task 1: Install Dependencies & Configure Tooling
**File:** `pyproject.toml` (modify existing)
**Action:** UPDATE

Add to `dependencies` list (after line 19):
```
"pgvector>=0.3.6",
"pymupdf>=1.25.0",
"python-docx>=1.1.2",
"pillow>=11.0.0",
"pytesseract>=0.3.13",
"sentence-transformers>=4.1.0",
"openai>=1.82.0",
```

Add mypy overrides (after the `slowapi.*` override block at line 112). Each override MUST be separate:
```toml
[[tool.mypy.overrides]]
module = "sentence_transformers.*"
ignore_missing_imports = true

[[tool.mypy.overrides]]
module = "pytesseract.*"
ignore_missing_imports = true

[[tool.mypy.overrides]]
module = "docx.*"
ignore_missing_imports = true

[[tool.mypy.overrides]]
module = "fitz.*"
ignore_missing_imports = true

[[tool.mypy.overrides]]
module = "pgvector.*"
ignore_missing_imports = true
```

Add to `[tool.ruff.lint.per-file-ignores]` (after line 75):
```toml
"app/knowledge/routes.py" = ["ARG001"]  # slowapi requires Request param
```

Run: `uv add pgvector pymupdf python-docx pillow pytesseract sentence-transformers openai`

**Per-task validation:**
- `uv run ruff check --fix pyproject.toml`

---

### Task 2: Switch Docker PostgreSQL to pgvector Image
**File:** `docker-compose.yml` (modify existing)
**Action:** UPDATE

Change line 3 from `image: postgres:18-alpine` to:
```yaml
image: pgvector/pgvector:pg18
```

This image includes the `vector` extension pre-installed.

**Per-task validation:** File is YAML, no Python lint. Verify syntax: `docker-compose config --quiet`

---

### Task 3: Add Configuration Settings
**File:** `app/core/config.py` (modify existing)
**Action:** UPDATE

Add after `agent_daily_quota: int = 50` (line 75):
```python
    # Embedding provider (mirrors LLM provider pattern)
    embedding_provider: str = "openai"  # openai, jina, local
    embedding_model: str = "text-embedding-3-large"
    embedding_dimension: int = 1024
    embedding_api_key: str | None = None
    embedding_base_url: str | None = None  # Custom endpoint for local/Jina

    # Reranker
    reranker_provider: str = "local"  # local, none
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    reranker_top_k: int = 10

    # Knowledge base
    knowledge_chunk_size: int = 512
    knowledge_chunk_overlap: int = 50
    knowledge_search_limit: int = 50  # Candidates before reranking
```

**Per-task validation:**
- `uv run ruff format app/core/config.py` / `uv run ruff check --fix app/core/config.py`
- `uv run mypy app/core/config.py` / `uv run pyright app/core/config.py`

---

### Task 4: Update .env.example
**File:** `.env.example` (modify existing)
**Action:** UPDATE

Append after Obsidian section (line 43):
```bash

# Embedding Provider (openai, jina, local)
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-large
EMBEDDING_DIMENSION=1024
# EMBEDDING_API_KEY=your-openai-or-jina-key
# EMBEDDING_BASE_URL=http://localhost:8080

# Reranker (local, none)
RERANKER_PROVIDER=local
RERANKER_MODEL=BAAI/bge-reranker-v2-m3
# RERANKER_TOP_K=10

# Knowledge Base
# KNOWLEDGE_CHUNK_SIZE=512
# KNOWLEDGE_CHUNK_OVERLAP=50
# KNOWLEDGE_SEARCH_LIMIT=50
```

**Per-task validation:** `uv run python -c "from app.core.config import get_settings"`

---

### Task 5: Create Feature Package
**File:** `app/knowledge/__init__.py` (create new)
**Action:** CREATE — Empty `__init__.py`.

Also create `app/knowledge/tests/__init__.py` — Empty.

---

### Task 6: Create Database Models
**File:** `app/knowledge/models.py` (create new)
**Action:** CREATE

```python
# pyright: reportUnknownMemberType=false
"""SQLAlchemy models for knowledge base documents and chunks."""

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from pgvector.sqlalchemy import Vector

from app.core.database import Base
from app.shared.models import TimestampMixin
```

**`Document(Base, TimestampMixin)`** — `__tablename__ = "documents"`:
Follow `app/stops/models.py` line 14 pattern. All columns use `Mapped[type] = mapped_column(...)`:
- `id: Mapped[int]` — `mapped_column(primary_key=True, index=True)`
- `filename: Mapped[str]` — `mapped_column(String(500), nullable=False)`
- `domain: Mapped[str]` — `mapped_column(String(50), nullable=False, index=True)`
- `source_type: Mapped[str]` — `mapped_column(String(20), nullable=False)`
- `language: Mapped[str]` — `mapped_column(String(5), nullable=False, default="lv")`
- `file_size_bytes: Mapped[int | None]` — `mapped_column(Integer, nullable=True)`
- `status: Mapped[str]` — `mapped_column(String(20), nullable=False, default="pending")`
- `error_message: Mapped[str | None]` — `mapped_column(Text, nullable=True)`
- `chunk_count: Mapped[int]` — `mapped_column(Integer, nullable=False, default=0)`
- `metadata_json: Mapped[str | None]` — `mapped_column(Text, nullable=True)`

**`DocumentChunk(Base, TimestampMixin)`** — `__tablename__ = "document_chunks"`:
- `id: Mapped[int]` — primary key
- `document_id: Mapped[int]` — `mapped_column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)`
- `content: Mapped[str]` — `mapped_column(Text, nullable=False)`
- `chunk_index: Mapped[int]` — `mapped_column(Integer, nullable=False)`
- `embedding` — `mapped_column(Vector(1024))` — pgvector column
- `metadata_json: Mapped[str | None]` — `mapped_column(Text, nullable=True)`

NOTE: The `embedding` column uses pgvector `Vector` type. Mypy needs the override from Task 1. Pyright directive is at file top.

**Per-task validation:**
- `uv run ruff format app/knowledge/models.py` / `uv run ruff check --fix app/knowledge/models.py`
- `uv run mypy app/knowledge/models.py` / `uv run pyright app/knowledge/models.py`

---

### Task 7: Create Pydantic Schemas
**File:** `app/knowledge/schemas.py` (create new)
**Action:** CREATE

Follow `app/stops/schemas.py` (lines 8-53) pattern exactly:

```python
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
```

**`DocumentUpload(BaseModel)`:**
- `domain: str = Field(..., min_length=1, max_length=50)`
- `language: str = Field(default="lv", pattern="^(lv|en)$")`
- `metadata_json: str | None = None`

**`DocumentResponse(BaseModel)`:**
- `id: int`, `filename: str`, `domain: str`, `source_type: str`, `language: str`
- `file_size_bytes: int | None`, `status: str`, `error_message: str | None`
- `chunk_count: int`, `metadata_json: str | None`
- `created_at: datetime`, `updated_at: datetime`
- `model_config = ConfigDict(from_attributes=True)` — ONLY on Response, per stops pattern

**`SearchRequest(BaseModel)`:**
- `query: str = Field(..., min_length=1, max_length=1000)`
- `domain: str | None = None`
- `language: str | None = None`
- `limit: int = Field(default=10, ge=1, le=50)`

**`SearchResult(BaseModel)`:**
- `chunk_content: str`, `document_id: int`, `document_filename: str`
- `domain: str`, `language: str`, `chunk_index: int`
- `score: float`, `metadata_json: str | None`

**`SearchResponse(BaseModel)`:**
- `results: list[SearchResult]`, `query: str`
- `total_candidates: int`, `reranked: bool`

**Per-task validation:**
- `uv run ruff format app/knowledge/schemas.py` / `uv run ruff check --fix app/knowledge/schemas.py`
- `uv run mypy app/knowledge/schemas.py` / `uv run pyright app/knowledge/schemas.py`

---

### Task 8: Create Exceptions
**File:** `app/knowledge/exceptions.py` (create new)
**Action:** CREATE

Follow `app/stops/exceptions.py` (lines 1-22) exactly:
```python
"""Feature-specific exceptions for knowledge base.

Inherits from core exceptions for automatic HTTP status code mapping:
- DocumentNotFoundError -> 404
- ProcessingError -> 500
"""
from app.core.exceptions import DatabaseError, NotFoundError


class KnowledgeBaseError(DatabaseError):
    """Base exception for knowledge base errors."""


class DocumentNotFoundError(NotFoundError):
    """Raised when a document is not found by ID."""


class ProcessingError(KnowledgeBaseError):
    """Raised when document extraction, chunking, or embedding fails."""


class EmbeddingProviderError(KnowledgeBaseError):
    """Raised when the embedding API or model fails."""


class UnsupportedDocumentTypeError(KnowledgeBaseError):
    """Raised for unknown file extensions."""
```

**Per-task validation:**
- `uv run ruff format app/knowledge/exceptions.py` / `uv run ruff check --fix app/knowledge/exceptions.py`
- `uv run mypy app/knowledge/exceptions.py`

---

### Task 9: Create Embedding Provider
**File:** `app/knowledge/embedding.py` (create new)
**Action:** CREATE

```python
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false
"""Configurable embedding provider for document vectorization."""
from __future__ import annotations
import asyncio, time
from typing import Protocol
from app.core.config import Settings
from app.core.logging import get_logger
```

**`EmbeddingProvider(Protocol)`:** Two methods:
- `async def embed(self, texts: list[str]) -> list[list[float]]`
- `def dimension(self) -> int` (property)

**`OpenAIEmbeddingProvider`:**
- `__init__(self, model: str, api_key: str, dimension: int, base_url: str | None = None)`
- Creates `openai.AsyncOpenAI(api_key=api_key, base_url=base_url)` in init
- `embed()`: Call `self._client.embeddings.create(model=self._model, input=texts[:100])`. Extract `[d.embedding for d in response.data]`. Batch >100 texts with loop.
- Works for both OpenAI and Jina (Jina uses OpenAI-compatible endpoint)

**`LocalEmbeddingProvider`:**
- `__init__(self, model_name: str, dimension: int)`
- Lazy-loads model: `self._model: SentenceTransformer | None = None`
- `_get_model()`: Creates `SentenceTransformer(model_name)` on first call
- `embed()`: `await asyncio.to_thread(self._get_model().encode, texts)` — MUST use `to_thread` (CPU-bound)
- Convert numpy arrays to `list[list[float]]` via `.tolist()`

**`get_embedding_provider(settings: Settings) -> EmbeddingProvider`:**
- `"openai"` or `"jina"` -> `OpenAIEmbeddingProvider(model=settings.embedding_model, api_key=settings.embedding_api_key or "", dimension=settings.embedding_dimension, base_url=settings.embedding_base_url)`
- `"local"` -> `LocalEmbeddingProvider(model_name=settings.embedding_model, dimension=settings.embedding_dimension)`
- Unknown -> `raise ValueError(f"Unknown embedding provider: {settings.embedding_provider}")`

Logging: `knowledge.embedding.started` (text_count), `knowledge.embedding.completed` (text_count, dimension, duration_ms)

**Per-task validation:**
- `uv run ruff format app/knowledge/embedding.py` / `uv run ruff check --fix app/knowledge/embedding.py`
- `uv run mypy app/knowledge/embedding.py` / `uv run pyright app/knowledge/embedding.py`

---

### Task 10: Create Document Processing Pipeline
**File:** `app/knowledge/processing.py` (create new)
**Action:** CREATE

```python
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false
"""Document text extraction for PDFs, Word, email, images, plain text."""
from __future__ import annotations
import asyncio, email
from pathlib import Path
from app.knowledge.exceptions import UnsupportedDocumentTypeError
from app.core.logging import get_logger
```

**`async def extract_text(file_path: str, source_type: str) -> str`:**
Route by source_type: `pdf` -> `_extract_pdf`, `docx` -> `_extract_docx`, `email` -> `_extract_email`, `image` -> `_extract_image`, `text` -> `_extract_text`. Else raise `UnsupportedDocumentTypeError`.

All private extractors are sync functions called via `await asyncio.to_thread(fn, file_path)`.

**`def _extract_pdf_sync(file_path: str) -> str`:** `import fitz; doc = fitz.open(file_path)`. Loop `doc` pages, `page.get_text()`. Join with `"\n\n"`. Close doc.

**`def _extract_docx_sync(file_path: str) -> str`:** `from docx import Document as DocxDocument`. `doc = DocxDocument(file_path)`. Join `[p.text for p in doc.paragraphs if p.text.strip()]` with `"\n\n"`.

**`def _extract_email_sync(file_path: str) -> str`:** Open file, `email.message_from_file()`. Extract `From`, `To`, `Date`, `Subject` headers. Walk parts for `text/plain`. Combine headers + body.

**`def _extract_image_sync(file_path: str) -> str`:** `import pytesseract; from PIL import Image`. `pytesseract.image_to_string(Image.open(file_path), lang="lav+eng")`.

**`def _extract_text_sync(file_path: str) -> str`:** `Path(file_path).read_text(encoding="utf-8")`

Logging: `knowledge.extraction.started/completed/failed` with source_type, char_count.

**Per-task validation:**
- `uv run ruff format app/knowledge/processing.py` / `uv run ruff check --fix app/knowledge/processing.py`
- `uv run mypy app/knowledge/processing.py` / `uv run pyright app/knowledge/processing.py`

---

### Task 11: Create Recursive Chunker
**File:** `app/knowledge/chunking.py` (create new)
**Action:** CREATE

No pyright directives needed (pure Python, no untyped libs).

```python
"""Recursive text chunking with metadata preservation."""
from dataclasses import dataclass, field

@dataclass
class ChunkResult:
    content: str
    chunk_index: int
    metadata: dict[str, str | int | None] = field(default_factory=dict)
```

**`def chunk_text(text: str, chunk_size: int = 512, chunk_overlap: int = 50) -> list[ChunkResult]`:**
Pure function. Algorithm:
1. If `len(text) <= chunk_size`, return single ChunkResult
2. Try splitting by `"\n\n"` (paragraphs). If all parts <= chunk_size, build chunks with overlap
3. Else try `"\n"` (lines), then `". "` (sentences), then `" "` (words)
4. Build chunks: slide window of `chunk_size` chars with `chunk_overlap` overlap
5. Set `metadata={"char_start": start_pos, "char_end": end_pos}` per chunk
6. Filter out empty/whitespace-only chunks
7. Assign sequential `chunk_index` starting at 0

**Per-task validation:**
- `uv run ruff format app/knowledge/chunking.py` / `uv run ruff check --fix app/knowledge/chunking.py`
- `uv run mypy app/knowledge/chunking.py` / `uv run pyright app/knowledge/chunking.py`

---

### Task 12: Create Reranker
**File:** `app/knowledge/reranker.py` (create new)
**Action:** CREATE

```python
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false
"""Configurable cross-encoder reranker for search result refinement."""
from __future__ import annotations
import asyncio, time
from dataclasses import dataclass
from typing import Protocol
from app.core.config import Settings
from app.core.logging import get_logger
```

**`@dataclass class RerankResult`:** `index: int`, `score: float`, `content: str`

**`RerankerProvider(Protocol)`:** `async def rerank(self, query: str, documents: list[str], top_k: int = 10) -> list[RerankResult]`

**`LocalRerankerProvider`:** Lazy-loads `sentence_transformers.CrossEncoder(model_name)`. `rerank()` runs `model.predict([(query, doc) for doc in documents])` in `asyncio.to_thread()`. Sort by score desc, return top_k.

**`NoopRerankerProvider`:** Returns all docs with `score=1.0` in original order, truncated to `top_k`.

**`get_reranker_provider(settings: Settings) -> RerankerProvider`:** `"local"` -> Local, `"none"` -> Noop. Raises ValueError for unknown.

Logging: `knowledge.reranking.started/completed` with candidate_count, top_k, duration_ms.

**Per-task validation:**
- `uv run ruff format app/knowledge/reranker.py` / `uv run ruff check --fix app/knowledge/reranker.py`
- `uv run mypy app/knowledge/reranker.py` / `uv run pyright app/knowledge/reranker.py`

---

### Task 13: Create Repository with Hybrid Search
**File:** `app/knowledge/repository.py` (create new)
**Action:** CREATE

```python
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false
"""Data access layer for knowledge base with pgvector hybrid search."""
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from app.knowledge.models import Document, DocumentChunk
```

Follow `app/stops/repository.py` (lines 10-135) pattern.

**`KnowledgeRepository.__init__(self, db: AsyncSession) -> None`:** Stores `self.db = db`.

**Methods:** (all `async def`, all typed)
- `create_document(filename, domain, source_type, language, file_size_bytes, metadata_json) -> Document` — pattern from stops repo line 96-109
- `get_document(document_id: int) -> Document | None` — `select(Document).where(Document.id == id)`
- `list_documents(*, offset, limit, domain, status) -> list[Document]` — filter chaining like stops line 64-71
- `count_documents(*, domain, status) -> int` — `select(func.count()).select_from(Document)`
- `update_document_status(document_id, status, error_message, chunk_count) -> None` — fetch + setattr + commit
- `delete_document(document_id: int) -> None` — fetch + `db.delete()` + commit (CASCADE handles chunks)
- `bulk_create_chunks(chunks: list[DocumentChunk]) -> None` — `db.add_all(chunks); await db.commit()`
- `search_vector(query_embedding: list[float], limit: int, domain: str | None, language: str | None) -> list[tuple[DocumentChunk, float]]` — `order_by(DocumentChunk.embedding.cosine_distance(query_embedding))` ascending, JOIN Document
- `search_fulltext(query_text: str, limit: int, domain: str | None, language: str | None) -> list[tuple[DocumentChunk, float]]` — `to_tsvector('simple', content) @@ plainto_tsquery('simple', text)` with `ts_rank`

**Hybrid search is done in the SERVICE layer** (not repository) because RRF fusion is business logic. Repository provides two separate search methods; service combines with RRF.

**Per-task validation:**
- `uv run ruff format app/knowledge/repository.py` / `uv run ruff check --fix app/knowledge/repository.py`
- `uv run mypy app/knowledge/repository.py` / `uv run pyright app/knowledge/repository.py`

---

### Task 14: Create Service Layer
**File:** `app/knowledge/service.py` (create new)
**Action:** CREATE

Follow `app/stops/service.py` (lines 53-60) pattern: service creates its own repository.

```python
from __future__ import annotations
import time
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import get_settings
from app.core.logging import get_logger
from app.knowledge.repository import KnowledgeRepository
from app.knowledge.embedding import EmbeddingProvider, get_embedding_provider
from app.knowledge.reranker import RerankerProvider, get_reranker_provider
from app.knowledge import processing, chunking
from app.knowledge.models import DocumentChunk
from app.knowledge.schemas import DocumentResponse, SearchRequest, SearchResponse, SearchResult
from app.knowledge.exceptions import DocumentNotFoundError
from app.shared.schemas import PaginatedResponse, PaginationParams
```

**Module-level lazy singletons** for expensive resources:
```python
_embedding_provider: EmbeddingProvider | None = None
_reranker_provider: RerankerProvider | None = None

def _get_embedding() -> EmbeddingProvider:
    global _embedding_provider
    if _embedding_provider is None:
        _embedding_provider = get_embedding_provider(get_settings())
    return _embedding_provider
```
Same pattern for reranker. Singletons avoid reloading models per request.

**`KnowledgeService.__init__(self, db: AsyncSession) -> None`:**
- `self.db = db`
- `self.repository = KnowledgeRepository(db)`

**`async def ingest_document(self, file_path, upload, filename, source_type, file_size) -> DocumentResponse`:**
1. `doc = await self.repository.create_document(...)` with status="processing"
2. `try:` block:
   a. `text = await processing.extract_text(file_path, source_type)`
   b. `chunks = chunking.chunk_text(text, settings.knowledge_chunk_size, settings.knowledge_chunk_overlap)`
   c. `texts = [c.content for c in chunks]`
   d. `embeddings = await _get_embedding().embed(texts)` (batch)
   e. Build `DocumentChunk` objects with embeddings
   f. `await self.repository.bulk_create_chunks(chunk_objects)`
   g. `await self.repository.update_document_status(doc.id, "completed", None, len(chunks))`
3. `except Exception as e:` — `await self.repository.update_document_status(doc.id, "failed", str(e), 0)` then `raise`
4. Return `DocumentResponse.model_validate(doc)` — per stops pattern line 155

**`async def search(self, request: SearchRequest) -> SearchResponse`:**
1. `query_embedding = (await _get_embedding().embed([request.query]))[0]`
2. `vector_results = await self.repository.search_vector(query_embedding, settings.knowledge_search_limit, request.domain, request.language)`
3. `text_results = await self.repository.search_fulltext(request.query, settings.knowledge_search_limit, request.domain, request.language)`
4. RRF fusion: combine both result lists, score = `1/(60+rank_v) + 1/(60+rank_t)`, dedup by chunk id
5. Extract top candidates' content strings
6. `reranked = await _get_reranker().rerank(request.query, contents, request.limit)`
7. Map to `SearchResult` objects, return `SearchResponse`

Other methods: `get_document`, `list_documents`, `delete_document` — delegate to repository, raise `DocumentNotFoundError` on None.

Logging: `knowledge.ingest.started/completed/failed`, `knowledge.search.started/completed`, `knowledge.delete.completed`

**Per-task validation:**
- `uv run ruff format app/knowledge/service.py` / `uv run ruff check --fix app/knowledge/service.py`
- `uv run mypy app/knowledge/service.py` / `uv run pyright app/knowledge/service.py`

---

### Task 15: Create API Routes
**File:** `app/knowledge/routes.py` (create new)
**Action:** CREATE

```python
# pyright: reportUnknownMemberType=false, reportUntypedFunctionDecorator=false
"""Knowledge base REST API endpoints."""
import tempfile
from pathlib import Path
from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from fastapi.requests import Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.rate_limit import limiter
from app.knowledge.schemas import DocumentResponse, SearchRequest, SearchResponse
from app.knowledge.service import KnowledgeService
from app.shared.schemas import PaginatedResponse, PaginationParams

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])

def get_service(db: AsyncSession = Depends(get_db)) -> KnowledgeService:  # noqa: B008
    return KnowledgeService(db)
```

5 endpoints following `app/stops/routes.py` pattern EXACTLY (`_ = request` on every handler):

1. **POST /documents** — `@limiter.limit("10/minute")`, accepts `UploadFile`, form fields (domain, language, metadata_json). Save to temp file via `tempfile.NamedTemporaryFile(delete=False)`. Call `service.ingest_document()` in `try/finally` that deletes temp file. Return 201.

2. **GET /documents** — `@limiter.limit("30/minute")`, PaginationParams + optional domain/status query. Return `PaginatedResponse[DocumentResponse]`.

3. **GET /documents/{document_id}** — `@limiter.limit("30/minute")`. Return DocumentResponse.

4. **DELETE /documents/{document_id}** — `@limiter.limit("10/minute")`, `status_code=status.HTTP_204_NO_CONTENT`. Return None.

5. **POST /search** — `@limiter.limit("30/minute")`, body: SearchRequest. Return SearchResponse.

**File type detection:** Map `UploadFile.content_type` to source_type: `application/pdf` -> `"pdf"`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document` -> `"docx"`, `message/rfc822` -> `"email"`, `image/*` -> `"image"`, `text/*` -> `"text"`.

**Per-task validation:**
- `uv run ruff format app/knowledge/routes.py` / `uv run ruff check --fix app/knowledge/routes.py`
- `uv run mypy app/knowledge/routes.py` / `uv run pyright app/knowledge/routes.py`

---

### Task 16: Create Agent Tool Package + Schemas
**Files:** `app/core/agents/tools/knowledge/__init__.py` (empty), `app/core/agents/tools/knowledge/schemas.py`
**Action:** CREATE

```python
"""Response schemas for the knowledge base agent tool."""
from pydantic import BaseModel

class KnowledgeSearchResult(BaseModel):
    content: str
    source: str
    domain: str
    relevance_score: float
    page_or_section: str | None = None

class KnowledgeSearchResponse(BaseModel):
    results: list[KnowledgeSearchResult]
    total_found: int
    query: str
```

**Per-task validation:**
- `uv run ruff format app/core/agents/tools/knowledge/schemas.py`
- `uv run ruff check --fix app/core/agents/tools/knowledge/schemas.py`
- `uv run mypy app/core/agents/tools/knowledge/schemas.py`

---

### Task 17: Create Agent Tool — search_knowledge_base
**File:** `app/core/agents/tools/knowledge/search_knowledge.py` (create new)
**Action:** CREATE

**CRITICAL:** Agent tools do NOT have access to FastAPI's `Depends(get_db)`. The tool must create its own DB session using `AsyncSessionLocal` from `app.core.database`:
```python
from app.core.database import AsyncSessionLocal
```

Tool creates session via: `async with AsyncSessionLocal() as db:`

Full signature following `app/core/agents/tools/transit/search_stops.py` (lines 173-181):
```python
async def search_knowledge_base(
    ctx: RunContext[UnifiedDeps],
    query: str,
    domain: str | None = None,
    language: str | None = None,
    limit: int = 5,
) -> str:
```

Docstring with ALL 5 sections (WHEN TO USE / WHEN NOT TO USE / EFFICIENCY / COMPOSITION / Args+Returns) — see search_stops.py lines 182-218 for format.

Implementation:
1. `_settings = ctx.deps.settings` — MUST reference ctx (ARG001)
2. `start_time = time.monotonic()` / logging
3. Validate: 1 <= limit <= 20, query not empty
4. `async with AsyncSessionLocal() as db:` — create own session
5. `service = KnowledgeService(db)`
6. `response = await service.search(SearchRequest(query=query, domain=domain, language=language, limit=limit))`
7. Map to `KnowledgeSearchResponse`, truncate content to 500 chars
8. `return json.dumps(result.model_dump(), ensure_ascii=False)`
9. Catch `Exception`, return error string (never raise) — per search_stops.py lines 321-325

**Per-task validation:**
- `uv run ruff format app/core/agents/tools/knowledge/search_knowledge.py`
- `uv run ruff check --fix app/core/agents/tools/knowledge/search_knowledge.py`
- `uv run mypy app/core/agents/tools/knowledge/search_knowledge.py`
- `uv run pyright app/core/agents/tools/knowledge/search_knowledge.py`

---

### Task 18: Register Tool with Agent
**File:** `app/core/agents/agent.py` (modify)
**Action:** UPDATE

Add import after line 15 (obsidian imports): `from app.core.agents.tools.knowledge.search_knowledge import search_knowledge_base`

Add to tools list after `obsidian_bulk_operations` (after line 75):
```python
            # Knowledge base (RAG)
            search_knowledge_base,
```

Add to SYSTEM_PROMPT (after Obsidian mention, ~line 32): `"You can also search the organizational knowledge base for policies, compliance documents, legal materials, driver records, and internal communications.\n"`

**Per-task validation:**
- `uv run ruff format app/core/agents/agent.py` / `uv run ruff check --fix app/core/agents/agent.py`
- `uv run mypy app/core/agents/agent.py` / `uv run pyright app/core/agents/agent.py`

---

### Task 19: Register Router in Main App
**File:** `app/main.py` (modify)
**Action:** UPDATE

Add import after line 33 (`from app.stops.routes`): `from app.knowledge.routes import router as knowledge_router`
Add after line 98 (`app.include_router(stops_router)`): `app.include_router(knowledge_router)`

**Per-task validation:**
- `uv run ruff format app/main.py` / `uv run ruff check --fix app/main.py`
- `uv run mypy app/main.py` / `uv run pyright app/main.py`

---

### Task 20: Create Database Migration
**File:** `alembic/env.py` (modify)
**Action:** UPDATE

Add after existing model import (line 10): `import app.knowledge.models  # noqa: F401  # Register Knowledge models for autogenerate`

Generate migration: `uv run alembic revision --autogenerate -m "add knowledge base tables with pgvector"`

**CRITICAL:** Manually edit the generated migration to add at the TOP of `upgrade()`:
```python
op.execute("CREATE EXTENSION IF NOT EXISTS vector")
```

Verify migration has: documents table, document_chunks with Vector(1024), FK CASCADE, HNSW index.

**Per-task validation:** `uv run ruff format alembic/versions/*.py` / `uv run ruff check --fix alembic/versions/*.py`

---

### Task 21: Create Test Fixtures
**File:** `app/knowledge/tests/conftest.py` (create new)
**Action:** CREATE

Fixtures returning typed objects (all helpers MUST have return type annotations — anti-pattern #7):
- `def sample_upload() -> DocumentUpload:` — `DocumentUpload(domain="transit", language="lv")`
- `def sample_latvian_text() -> str:` — Multi-paragraph text with Latvian diacritics

**Per-task validation:** `uv run ruff format app/knowledge/tests/conftest.py` / `uv run ruff check --fix app/knowledge/tests/conftest.py`

---

### Task 22: Create Processing + Chunking Tests
**File:** `app/knowledge/tests/test_processing.py` (create new)
**File:** `app/knowledge/tests/test_chunking.py` (create new)
**Action:** CREATE

**test_processing.py** (6 tests): Mock `fitz`, `docx`, `pytesseract` via `unittest.mock.patch`. Verify `asyncio.to_thread` is called. Verify `UnsupportedDocumentTypeError` for unknown types. Verify image OCR uses `lang="lav+eng"`.

**test_chunking.py** (6 tests): Pure function tests — short text, paragraph splits, overlap verification, empty input, Latvian diacritics preserved, metadata char offsets.

**Per-task validation:**
- `uv run ruff format app/knowledge/tests/test_processing.py app/knowledge/tests/test_chunking.py`
- `uv run ruff check --fix app/knowledge/tests/test_processing.py app/knowledge/tests/test_chunking.py`
- `uv run pytest app/knowledge/tests/test_processing.py app/knowledge/tests/test_chunking.py -v`

---

### Task 23: Create Embedding Tests
**File:** `app/knowledge/tests/test_embedding.py` (create new)
**Action:** CREATE

6 tests: Mock `openai.AsyncOpenAI` and `SentenceTransformer`. Verify batch splitting for >100 texts. Verify `asyncio.to_thread` for local. Verify factory returns correct types. Verify ValueError for unknown provider.

**Per-task validation:**
- `uv run ruff format app/knowledge/tests/test_embedding.py` / `uv run ruff check --fix app/knowledge/tests/test_embedding.py`
- `uv run pytest app/knowledge/tests/test_embedding.py -v`

---

## Logging Events

| Event | When | Context |
|-------|------|---------|
| `knowledge.ingest.started` | Upload received | filename, domain, source_type |
| `knowledge.ingest.completed` | Processing done | document_id, chunk_count, duration_ms |
| `knowledge.ingest.failed` | Processing error | document_id, error, error_type |
| `knowledge.extraction.started/completed/failed` | Text extraction | source_type, char_count |
| `knowledge.embedding.started/completed` | Vectorization | text_count, dimension, duration_ms |
| `knowledge.reranking.started/completed` | Rerank | candidate_count, top_k, duration_ms |
| `knowledge.search.started/completed` | Search | query_length, result_count, duration_ms |
| `knowledge.delete.completed` | Document removed | document_id |

## Acceptance Criteria

- [ ] Documents uploadable via `POST /api/v1/knowledge/documents` (PDF, DOCX, email, image, text)
- [ ] Ingestion: extract -> chunk -> embed -> store in pgvector
- [ ] `POST /api/v1/knowledge/search` returns hybrid results (vector + full-text + RRF)
- [ ] Reranking configurable via `RERANKER_PROVIDER` (local, none)
- [ ] Embedding configurable via `EMBEDDING_PROVIDER` (openai, jina, local)
- [ ] Agent uses `search_knowledge_base` tool (registered, 5-section docstring)
- [ ] mypy + pyright: 0 errors
- [ ] 18+ unit tests pass
- [ ] Logging: `knowledge.{component}.{action}_{state}`
- [ ] Router registered in `app/main.py`
- [ ] No regressions (all existing tests pass)

## Final Validation (5-Level Pyramid)

**Level 1:** `uv run ruff format . && uv run ruff check --fix .`
**Level 2:** `uv run mypy app/ && uv run pyright app/`
**Level 3:** `uv run pytest app/knowledge/tests/ -v`
**Level 4:** `uv run pytest -v -m "not integration"`
**Level 5:** `curl -s http://localhost:8123/health` (optional)

## Dependencies

- **Shared:** PaginationParams, PaginatedResponse, TimestampMixin, get_db(), AsyncSessionLocal, get_logger(), limiter
- **New packages:** `uv add pgvector pymupdf python-docx pillow pytesseract sentence-transformers openai`
- **Docker:** Switch PostgreSQL image to `pgvector/pgvector:pg18`

## Known Pitfalls

1. **5 untyped libs** — pgvector, sentence-transformers, pytesseract, python-docx, pymupdf. Task 1 adds mypy overrides. Each file using them needs `# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false`.
2. **CPU-bound in async** — Extraction, OCR, local models MUST use `asyncio.to_thread()`.
3. **Agent tool has NO `get_db()`** — Use `AsyncSessionLocal` directly (Task 17).
4. **File cleanup** — `try/finally` to delete temp files in routes.
5. **ARG001** — `_ = request` in routes (per-file-ignores), `_settings = ctx.deps.settings` in tool.
6. **No EN DASH** — Latvian text prone to EN DASH. Use HYPHEN-MINUS.
7. **Module-level singletons** — Embedding/reranker lazy-init (avoid startup crash without GPU).
8. **BodySizeLimitMiddleware** — Currently 100KB. Upload endpoint needs higher limit or streaming.
9. **Test helpers need return types** — Anti-pattern #7. Always `-> Type`.
10. **RRF fusion in service, not repo** — Keep repo methods pure (vector search + fulltext search separate).

## Notes

**Future (NOT in scope):** CMS Upload UI, background queue, Latvian stemming, ParadeDB BM25, doc versioning, RBAC, RAGAS evaluation, auto language detection.

**Performance:** Embedding ~200-500ms/batch. Search ~300-600ms total. Local model load ~5-10s first use.

**Security:** Temp file cleanup, parameterized SQL, random filenames. Address 100KB body limit for uploads.
