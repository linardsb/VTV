# Knowledge Base (RAG)

RAG-powered document knowledge base providing hybrid search over uploaded organizational documents (PDF, DOCX, email, images, text) with vector similarity + fulltext search, RRF fusion, and cross-encoder reranking.

## Key Flows

### Document Ingestion (Upload)

1. Accept file upload with domain and language metadata
2. Detect source type from MIME content type
3. Save to temp file, extract text (PyMuPDF, python-docx, pytesseract, stdlib)
4. Chunk text recursively (paragraphs -> lines -> sentences -> words)
5. Generate embeddings via configurable provider (OpenAI/Jina/local)
6. Store document metadata + chunks with vector embeddings in PostgreSQL
7. Update document status to "completed" or "failed"

### Hybrid Search

1. Embed query text using the configured embedding provider
2. Run vector similarity search (pgvector cosine distance)
3. Run fulltext search (PostgreSQL `to_tsvector('simple')` with `ts_rank`)
4. Combine results via Reciprocal Rank Fusion (RRF, k=60)
5. Rerank top candidates via cross-encoder (configurable: local or noop)
6. Return ranked results with scores and document metadata

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
| `domain` | String(50) | Not null, indexed | Knowledge domain (transit, hr, legal) |
| `source_type` | String(20) | Not null | File type (pdf, docx, email, image, text) |
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
2. Deleting a document cascades to all its chunks (ON DELETE CASCADE)
3. Empty documents (no extractable text) get status "completed" with chunk_count=0
4. Search uses 'simple' PostgreSQL text search config (no language-specific stemming) to support Latvian + English
5. RRF fusion combines vector and fulltext results; a chunk appearing in both gets boosted
6. Agent tool truncates chunk content to 500 characters for token efficiency
7. Embedding dimension is configurable (default 1024) and must match the pgvector column

## Integration Points

- **Agent Module**: `search_knowledge_base` tool registered in `app/core/agents/agent.py`, uses `AsyncSessionLocal` for direct DB access
- **Core Config**: 11 settings in `app/core/config.py` (embedding, reranker, chunking)
- **Shared Utilities**: Uses `PaginationParams`, `PaginatedResponse`, `TimestampMixin`, `get_db()`, `get_logger()`

## API Endpoints

| Method | Path | Rate Limit | Description |
|--------|------|-----------|-------------|
| POST | `/api/v1/knowledge/documents` | 10/min | Upload and ingest a document |
| GET | `/api/v1/knowledge/documents` | 30/min | List documents (paginated, filterable) |
| GET | `/api/v1/knowledge/documents/{id}` | 30/min | Get document by ID |
| DELETE | `/api/v1/knowledge/documents/{id}` | 10/min | Delete document and its chunks |
| POST | `/api/v1/knowledge/search` | 30/min | Hybrid search with reranking |
