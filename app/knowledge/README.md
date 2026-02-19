# Knowledge Base + Document Management System (DMS)

RAG-powered document knowledge base with full document management capabilities. Supports hybrid search over uploaded organizational documents (PDF, DOCX, Excel, CSV, email, images, text) with vector similarity + fulltext search, RRF fusion, and cross-encoder reranking. DMS features include file persistence, metadata editing, file download, content preview, and domain listing.

## Key Flows

### Document Ingestion (Upload)

1. Accept file upload with domain, language, title, and description metadata
2. Detect source type from MIME content type (PDF, DOCX, Excel, CSV, email, image, text)
3. Save to temp file, extract text (PyMuPDF, python-docx, openpyxl, csv, pytesseract, stdlib)
4. Copy original file to persistent storage at `{DOCUMENT_STORAGE_PATH}/{doc_id}/{filename}`
5. Chunk text recursively (paragraphs -> lines -> sentences -> words)
6. Generate embeddings via configurable provider (OpenAI/Jina/local)
7. Store document metadata + chunks with vector embeddings in PostgreSQL
8. Update document status to "completed" or "failed"
9. Title defaults to filename stem if not provided

### Hybrid Search

1. Embed query text using the configured embedding provider
2. Run vector similarity search (pgvector cosine distance)
3. Run fulltext search (PostgreSQL `to_tsvector('simple')` with `ts_rank`)
4. Combine results via Reciprocal Rank Fusion (RRF, k=60)
5. Rerank top candidates via cross-encoder (configurable: local or noop)
6. Return ranked results with scores and document metadata

### Document Update (PATCH)

1. Accept partial update with PATCH semantics (only non-None fields applied)
2. Updatable fields: title, description, domain, language
3. Return updated document response

### Document Content Preview

1. Fetch document metadata and all chunks ordered by chunk_index
2. Return as DocumentContentResponse with total_chunks count

### File Download

1. Look up stored file_path for the document
2. Return FileResponse with original filename (raises ProcessingError for legacy documents without stored files)

### Document Deletion with File Cleanup

1. Verify document exists
2. Remove stored file directory via `shutil.rmtree(file_dir, ignore_errors=True)`
3. Delete document and cascade-delete all chunks from database

### Agent Tool Search

1. Agent calls `search_knowledge_base` tool with natural language query
2. Tool creates `AsyncSessionLocal` session (outside FastAPI request lifecycle)
3. Delegates to `KnowledgeService.search()` for hybrid search
4. Truncates results to 500 chars per chunk for token efficiency
5. Returns JSON string (never raises, returns error message on failure)

## Database Schema

Table: `documents`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | Integer | PK, indexed | Primary key |
| `filename` | String(500) | Not null | Original upload filename |
| `title` | String(200) | Nullable | Human-readable document title (defaults to filename stem) |
| `description` | Text | Nullable | Optional document description |
| `file_path` | String(500) | Nullable | Path to stored original file on disk |
| `domain` | String(50) | Not null, indexed | Knowledge domain (transit, hr, safety) |
| `source_type` | String(20) | Not null | File type (pdf, docx, xlsx, csv, email, image, text) |
| `language` | String(5) | Not null, default "lv" | Document language |
| `file_size_bytes` | Integer | Nullable | Upload size in bytes |
| `status` | String(20) | Not null, default "pending" | Processing status (pending, processing, completed, failed) |
| `error_message` | Text | Nullable | Error details if processing failed |
| `chunk_count` | Integer | Not null, default 0 | Number of chunks generated |
| `metadata_json` | Text | Nullable | Optional JSON metadata string |
| `created_at` | DateTime | Not null | Auto-set on create |
| `updated_at` | DateTime | Not null | Auto-set on update |

Table: `document_chunks`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | Integer | PK, indexed | Primary key |
| `document_id` | Integer | FK -> documents.id, CASCADE, indexed | Parent document |
| `content` | Text | Not null | Extracted text chunk |
| `chunk_index` | Integer | Not null | Position in document |
| `embedding` | Vector(1024) | pgvector | Vector embedding for similarity search |
| `metadata_json` | Text | Nullable | Chunk-level metadata |
| `created_at` | DateTime | Not null | Auto-set on create |
| `updated_at` | DateTime | Not null | Auto-set on update |

## Business Rules

1. Documents are processed asynchronously: status transitions from "pending" -> "processing" -> "completed" or "failed"
2. Deleting a document cascades to all its chunks (ON DELETE CASCADE) and removes stored files
3. Empty documents (no extractable text) get status "completed" with chunk_count=0
4. Search uses 'simple' PostgreSQL text search config (no language-specific stemming) to support Latvian + English
5. RRF fusion combines vector and fulltext results; a chunk appearing in both gets boosted
6. Agent tool truncates chunk content to 500 characters for token efficiency
7. Embedding dimension is configurable (default 1024) and must match the pgvector column
8. File persistence stores originals at `{DOCUMENT_STORAGE_PATH}/{document_id}/{filename}`
9. Legacy documents (uploaded before DMS) have no stored file; download raises ProcessingError
10. Document update uses PATCH semantics — only non-None fields from `DocumentUpdate` are applied via setattr
11. Excel extraction produces tab-separated text with sheet headers; CSV uses tab separation
12. Title defaults to filename stem if not provided during upload

## Integration Points

- **Agent Module**: `search_knowledge_base` tool registered in `app/core/agents/agent.py`, uses `AsyncSessionLocal` for direct DB access. Agent system prompt includes CITATION RULES for `[title](/{locale}/documents/{id})` links.
- **Core Config**: 12 settings in `app/core/config.py` (embedding, reranker, chunking, document_storage_path)
- **Shared Utilities**: Uses `PaginationParams`, `PaginatedResponse`, `TimestampMixin`, `get_db()`, `get_logger()`
- **Frontend**: Documents management page at `/[locale]/documents` with upload, list, detail, download, delete

## API Endpoints

| Method | Path | Rate Limit | Description |
|--------|------|-----------|-------------|
| POST | `/api/v1/knowledge/documents` | 10/min | Upload and ingest a document (with title, description) |
| GET | `/api/v1/knowledge/documents` | 30/min | List documents (paginated, filterable by domain/status) |
| GET | `/api/v1/knowledge/documents/{id}` | 30/min | Get document by ID |
| PATCH | `/api/v1/knowledge/documents/{id}` | 10/min | Update document metadata (title, description, domain, language) |
| GET | `/api/v1/knowledge/documents/{id}/download` | 30/min | Download original uploaded file |
| GET | `/api/v1/knowledge/documents/{id}/content` | 30/min | Get extracted text chunks for a document |
| DELETE | `/api/v1/knowledge/documents/{id}` | 10/min | Delete document, chunks, and stored file |
| GET | `/api/v1/knowledge/domains` | 30/min | List unique document domains with count |
| POST | `/api/v1/knowledge/search` | 30/min | Hybrid search with reranking |
