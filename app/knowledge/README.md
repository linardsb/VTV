# Knowledge Base + Document Management System (DMS)

RAG-powered document knowledge base with full document management capabilities. Supports hybrid search over uploaded organizational documents (PDF, DOCX, Excel, CSV, email, images, text) with vector similarity + fulltext search, RRF fusion, and cross-encoder reranking. DMS features include file persistence, metadata editing, file download, content preview, domain listing, tag management (CRUD + document association), scanned PDF OCR detection with pytesseract fallback, and LLM-powered auto-tagging on upload.

## Key Flows

### Document Ingestion (Upload)

1. Accept file upload with domain, language, title, and description metadata
2. Detect source type from MIME content type (PDF, DOCX, Excel, CSV, email, image, text)
3. Save to temp file, extract text (PyMuPDF, python-docx, openpyxl, csv, pytesseract, stdlib)
4. For PDFs: detect scanned pages (< 50 chars extracted) and fall back to OCR via pytesseract (300 DPI, max 50 pages, `lav+eng` language packs)
5. Copy original file to persistent storage at `{DOCUMENT_STORAGE_PATH}/{doc_id}/{filename}`
6. Chunk text using heading-aware semantic chunker (splits at markdown heading boundaries with adaptive sizing) when `knowledge_semantic_chunking_enabled=True`; falls back to recursive fixed-size chunker for unstructured text or when disabled
7. Store heading path metadata (`heading_path`, `heading_level`) in chunk `metadata_json` as JSON
8. Generate embeddings via configurable provider (OpenAI/Jina/local)
8. Store document metadata + chunks with vector embeddings in PostgreSQL
9. Update document status to "completed" or "failed"; set `ocr_applied` flag if OCR was used
10. Auto-tag document via LLM classification (best-effort, non-blocking)
11. Title defaults to filename stem if not provided

### Semantic Chunking (Heading-Aware + Parent-Child)

1. When `knowledge_semantic_chunking_enabled=True` (default), `chunk_text_semantic()` is used instead of the fixed-size recursive splitter
2. Parses markdown `#` headings (already produced by PDF/DOCX/Excel extractors) using regex `^(#{1,6})\s+(.+)$`
3. Builds heading hierarchy as a stack: `# Safety > ## Emergency Procedures > ### Step 1`
4. Splits text into sections at heading boundaries, preserving heading path for each section
5. Merges small sections (< `knowledge_chunk_min_size` chars) with adjacent neighbours up to `knowledge_chunk_target_size`
6. Splits large sections (> `knowledge_chunk_max_size` chars) at paragraph then sentence boundaries, each sub-chunk inheriting the parent heading path
7. Falls back to recursive `chunk_text()` when no headings are detected (< 2 sections)
8. **Parent-child emission (AI-4.2):** Multi-paragraph sections emit one **parent** chunk (full section content) plus N **child** chunks (one per paragraph). Single-paragraph sections stay as leaf chunks (no parent, no children). Each result carries `is_parent: bool` and `parent_index: int | None` (positional index of the parent in the result list, NOT a DB id).
9. **Section type classification:** Each chunk is classified as `"heading" | "body" | "list" | "table"` via `_classify_section_type()` (markdown table detection, bulleted/numbered list detection ≥60% of lines, short single-line headings).
10. Each chunk's `metadata` includes `heading_path`, `heading_level`, `char_start`, `char_end`. Parent chunks additionally carry `child_count`. `heading_path` and `section_type` are also promoted to first-class `ChunkResult` fields so the service can pass them to model columns without re-parsing JSON.
11. Metadata stored as JSON in `DocumentChunk.metadata_json` column; `heading_path`/`section_type` also stored in dedicated columns.
12. Configurable via `knowledge_semantic_chunking_enabled`, `knowledge_chunk_target_size` (800), `knowledge_chunk_min_size` (256), `knowledge_chunk_max_size` (1500)

### Two-Phase Parent-Child Insert (AI-4.2)

1. After chunking + embedding, the service partitions results into parent / child / leaf groups
2. **Phase 1:** parent `DocumentChunk` objects are inserted via `repository.bulk_create_chunks(parents, flush_only=True)`. Flush (not commit) assigns DB ids to parent ORM instances without ending the transaction.
3. **Phase 2:** child + leaf objects are constructed with `parent_chunk_id` resolved from the in-memory parent map (positional `parent_index` → flushed parent's `.id`)
4. **Phase 3:** `repository.bulk_create_chunks(children + leaves)` commits the full transaction (parents + children atomically). Failure in phase 3 rolls back parents too.
5. Both parents and children are embedded and individually searchable. Search-time parent expansion is implemented in AI-4.3 (see below).

### Parent Context Expansion at Query Time (AI-4.3)

1. After RRF fusion, temporal boost, reranking, and confidence filtering produce the final `SearchResult` list, `KnowledgeService.search()` enters the parent-expansion block (gated on `knowledge_parent_context_enabled`, default True)
2. Walk surviving results and locate their source `DocumentChunk` ORM instances in `chunk_data` via `(document_id, chunk_index)`. Collect every distinct `parent_chunk_id` into a `set[int]` so multiple matched children of the same parent only trigger one fetch
3. Single batch round-trip: `repository.get_chunks_by_ids(list(parent_ids))` issues one `SELECT ... WHERE id IN (...)`. Empty parent set short-circuits without SQL
4. For each result whose source chunk has a parent, populate `SearchResult.parent_chunk_id`, `parent_content` (truncated to `knowledge_parent_context_max_chars`, default 3000), and `heading_path` from the fetched parent
5. Leaf chunks (`parent_chunk_id is None`) are left untouched — `parent_content`/`heading_path` stay `None`
6. Logging: emits `knowledge.search.parent_context_attached` with `result_count`, `parent_count`, `unique_parents` so dedupe behavior is observable
7. Disabling the flag (`KNOWLEDGE_PARENT_CONTEXT_ENABLED=false`) reverts to pre-AI-4.3 behavior at runtime — useful as a kill switch if response sizes balloon

### Re-Chunk Migration (AI-4.4)

1. One-shot operations script `scripts/rechunk_documents.py` walks every `Document` row, deletes its existing chunks, and re-runs the ingestion pipeline (extract → semantic chunk → embed → two-phase parent/child store) against the file already on disk
2. `KnowledgeService.rechunk_document(document_id)` is the in-process entry point: resolves the doc, re-extracts text via `processing.extract_text(file_path, source_type)`, calls `repository.delete_chunks_by_document(document_id)` to wipe stale rows (keeps the `Document` itself), re-runs `_chunk_embed_store()` (the same two-phase helper used by fresh ingestion), and updates `chunk_count` + `ocr_applied`
3. Failures mark the document `status="failed"` with the error message via `update_document_status`, then re-raise so the script's outer loop records the doc id and skips to the next
4. **Does NOT** auto-tag — re-running auto-tagging would clobber human-curated tags. **Does NOT** mutate `Document.metadata_json`, `evergreen`, `domain`, `language`, `title`, or `file_path`. Only chunks change.
5. CLI flags: `--dry-run` (preview without DB writes), `--batch-size N` (default 10, min 1, sequential per batch — embedding provider is rate-limited), `--document-id N` (target a single doc for testing), `--limit N` (cap total processed)
6. Documents whose `file_path is None` (legacy uploads or initial-ingest failures) are skipped with `skipped_no_file` counter
7. Reads `DATABASE_URL` via `app.core.config.get_settings()` + `get_db_context()` — never parses or logs the URL directly
8. Run via `make rechunk-dry-run` first, then `make rechunk` to apply. Exit code 1 if any document failed; the summary lists the first 5 failed ids.

### HyDE Query Expansion (Optional)

1. If `knowledge_hyde_enabled=True`, send query to a fast LLM before embedding
2. LLM generates a hypothetical document paragraph answering the query
3. The hypothetical answer is embedded instead of the raw query (embeds closer to actual documents)
4. Raw query is still used for fulltext search (HyDE only affects vector search)
5. Model resolution priority: `knowledge_hyde_model` > fast-tier LLM > primary LLM
6. Graceful degradation: LLM failures fall back to embedding the raw query
7. Output truncated to `knowledge_hyde_max_tokens * 4` chars as safety bound
8. Configurable via `knowledge_hyde_enabled`, `knowledge_hyde_model`, `knowledge_hyde_max_tokens`

### Embedding Cache (Redis-backed)

1. When `embedding_cache_enabled=True`, `_get_embedding()` wraps the provider with `CachedEmbeddingProvider`
2. For each text in a batch, compute cache key: `emb:{provider}:{blake2b(normalized_text)[:16]}`
3. Normalization: lowercase, strip whitespace, sort words (so "route 3 status" == "status route 3")
4. Batch lookup via Redis `mget`; cache hits skip the embedding API entirely
5. Cache misses are batch-embedded via the wrapped provider, then stored via Redis pipeline `setex`
6. Graceful fallback: any Redis error (unavailable, read failure, write failure) falls back to the wrapped provider
7. TTL configurable via `embedding_cache_ttl` (default 1 hour)
8. Logging events: `knowledge.embedding_cache.hit`, `.miss`, `.redis_unavailable`, `.read_failed`, `.write_failed`

### Hybrid Search

1. Embed query text (or HyDE-expanded text if enabled) using the configured embedding provider (with optional cache)
2. Run vector similarity search (pgvector cosine distance)
3. Run fulltext search (PostgreSQL `to_tsvector('simple')` with `ts_rank`) against `COALESCE(document_chunks.lemmatized_content, document_chunks.content)` — Latvian chunks use their pre-lemmatized form (KB-2), everything else falls through to raw content
4. Classify query type: keyword (route numbers, stop codes), semantic (questions, procedural phrases in EN/LV), or mixed
5. Combine results via Reciprocal Rank Fusion (RRF, k=60) with query-adaptive weights (keyword: fulltext 0.7/vector 0.3, semantic: vector 0.7/fulltext 0.3, mixed: 0.5/0.5)
6. Apply temporal boost multiplier based on document age (today: 1.5x, this week: 1.2x, this month: 1.0x, older: 0.8x). Evergreen documents skip temporal decay
7. Rerank top candidates via cross-encoder (configurable: local or noop)
8. Return ranked results with scores, document metadata, and `document_created_at`

### Latvian UDPipe Lemmatization (KB-2)

1. Feature-flagged via `latvian_lemmatizer_enabled` (default `False`; enable after running `make download-udpipe-model`)
2. `app/knowledge/lemmatizer.py` — `LemmaTokenizer` Protocol with `UDPipeLemmatizer` (lazy model load in a worker thread) and `NoopLemmatizer` fallback; factory `get_lemmatizer_provider(settings)` selects by flag
3. Warm-up in FastAPI lifespan is non-fatal — missing model file logs `knowledge.lemmatizer.warm_up_failed` and search degrades to raw-text BM25
4. Ingestion (`service._chunk_embed_store`) calls `chunking.apply_lemmatization(chunks, lemmatizer, language)` for Latvian docs to populate `DocumentChunk.lemmatized_content` alongside `content` (no re-embed, no re-chunk)
5. Search pre-lemmatizes the Latvian query and passes it as `lemmatized_query` kwarg to `repository.search_fulltext`; per-chunk exceptions are caught and logged so a single UDPipe failure never blocks ingestion or search
6. One-shot backfill for existing chunks: `make lemmatize-backfill` (or `--dry-run`) writes `lemmatized_content` without re-embedding

### Search Feedback Loop (KB-4)

1. Every `POST /search` response carries a stable `query_hash` (SHA-256 prefix over normalized `query|domain`) and the detected `query_type` (`keyword` / `semantic` / `mixed`). Each `SearchResult` also carries `rank_source` — `vector`, `fulltext`, or `both` — recording which retrieval branch surfaced that chunk
2. Clients record thumbs-up/down votes via `POST /v1/knowledge/search/{query_hash}/feedback?query_type=...&rank_source=...` with body `{chunk_id, relevant}`. JWT-gated (no role check — any authenticated user may vote), rate-limited to 60/min. The `(user_id, query_hash, chunk_id)` unique constraint prevents vote stuffing (one vote per user per chunk per query; a second call upserts)
3. `FeedbackService.recompute_weights()` aggregates the last `knowledge_rrf_feedback_window_days` days (default 30) grouped by `(query_type, rank_source)`. Only `vector` and `fulltext` rows contribute — `both` rows give no signal about branch preference
4. For each query type: compute Laplace-smoothed positive-rate per branch `(up+1)/(up+down+2)`, normalize to a share, then blend `knowledge_rrf_blend_weight * raw_vec + (1 - blend) * static_vec` (default blend 0.7 tuned / 0.3 static) to prevent runaway drift. Clamp to `[0.1, 0.9]` for safety. Query types below `knowledge_rrf_min_signals_per_type` total votes (default 20) are skipped and fall back to static config
5. Tuned weights written to Redis key `knowledge:rrf:weights:{query_type}` with 48h TTL. Search reads via `FeedbackService.get_tuned_weights(query_type)` with graceful fallback to `settings.rrf_{type}_{vector|text}_weight` on cache miss, corrupt payload, or any `RedisError` (fail-open — search quality, not a security boundary)
6. Daily recompute: when `background_queue_enabled=True`, runs as arq cron job `run_rrf_recompute` at `knowledge_rrf_recompute_cron_hour:15` UTC (default 03:15 UTC). Otherwise the in-process `start_knowledge_tasks()` lifecycle loop recomputes daily at the same hour. Both paths call `FeedbackService.recompute_weights()` with a fresh DB session via `get_db_context()`
7. Feature-flagged via `knowledge_feedback_enabled` (default `True`). Disabling reverts to static RRF weights at both write (no feedback persisted) and read (tuned weights not consulted) paths
8. Logging events: `knowledge.feedback.recorded`, `knowledge.rrf.recomputed`, `knowledge.rrf.recompute_failed`, `knowledge.rrf.tuned_weights_unavailable`, `knowledge.lifecycle.rrf_recompute_completed`

### Tag Management

1. Tags are simple lowercase string labels (normalized on create)
2. CRUD operations: list all tags, create tag, delete tag (CASCADE removes document associations)
3. Many-to-many association: documents can have multiple tags, tags can be on multiple documents
4. Filter documents by tag via `GET /documents?tag=transit`
5. Add/remove tags on individual documents
6. Duplicate tag names return 409 Conflict
7. Race-safe tag creation via IntegrityError catch + rollback + retry

### LLM Auto-Tagging (on Upload)

1. After text extraction, if `auto_tag_enabled=True`, send first N characters to LLM
2. LLM classifies document and suggests 1-3 tags
3. Tags are created via `get_or_create_tag` (idempotent, race-safe)
4. Best-effort: failures are logged as warnings, never block ingestion
5. Configurable via `auto_tag_enabled` and `auto_tag_max_chars` settings

### Document Update (PATCH)

1. Accept partial update with PATCH semantics (only non-None fields applied)
2. Updatable fields: title, description, domain, language, evergreen
3. Return updated document response with enriched tags

### Document Content Preview

1. Fetch document metadata and all chunks ordered by chunk_index
2. Return as DocumentContentResponse with total_chunks count

### File Download

1. Look up stored file_path for the document
2. Return FileResponse with original filename (raises ProcessingError for legacy documents without stored files)

### Document Deletion with File Cleanup

1. Verify document exists
2. Remove stored file directory via `shutil.rmtree(file_dir, ignore_errors=True)`
3. Delete document and cascade-delete all chunks and tag associations from database

### Agent Tool Search

1. Agent calls `search_knowledge_base` tool with natural language query
2. Tool creates `AsyncSessionLocal` session (outside FastAPI request lifecycle)
3. Delegates to `KnowledgeService.search()` for hybrid search
4. Truncates child chunk content to 1500 chars (`_MAX_CONTENT_CHARS`) for token efficiency
5. **Parent context formatting (AI-4.3):** when a result carries `parent_content` + `heading_path`, the agent-facing `content` field is rebuilt as `"[Section: {heading_path}]\n{parent_content[:3000]}\n\n[Matched passage:]\n{child_content[:1500]}"`. If only `parent_content` is present (no heading), the `[Section: ...]` line is omitted. Leaf results (no parent) format as raw child content for back-compat. Raw `parent_content`/`heading_path` are also exposed on `KnowledgeSearchResult` so downstream consumers (memory, logs) can access them without re-parsing the merged string.
6. Logs `agent.knowledge.search_completed` with `parent_contexts_count` so the share of expanded results is observable
7. Returns JSON string (never raises, returns error message on failure)

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
| `ocr_applied` | Boolean | Not null, default false | Whether OCR was applied during text extraction |
| `evergreen` | Boolean | Not null, default false | Skip temporal decay in search scoring (for regulations, SOPs) |
| `created_at` | DateTime | Not null | Auto-set on create |
| `updated_at` | DateTime | Not null | Auto-set on update |

Table: `tags`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | Integer | PK, indexed | Primary key |
| `name` | String(100) | Not null, unique, indexed | Tag name (normalized to lowercase) |
| `created_at` | DateTime | Not null | Auto-set on create |
| `updated_at` | DateTime | Not null | Auto-set on update |

Table: `document_tags` (many-to-many association)

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `document_id` | Integer | FK -> documents.id, CASCADE, not null | Parent document |
| `tag_id` | Integer | FK -> tags.id, CASCADE, not null | Associated tag |
| | | PK (document_id, tag_id) | Composite primary key prevents duplicates |

Table: `document_chunks`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | Integer | PK, indexed | Primary key |
| `document_id` | Integer | FK -> documents.id, CASCADE, indexed | Parent document |
| `content` | Text | Not null | Extracted text chunk |
| `chunk_index` | Integer | Not null | Position in document |
| `embedding` | Vector(1024) | pgvector | Vector embedding for similarity search |
| `metadata_json` | Text | Nullable | Chunk-level metadata (JSON) |
| `parent_chunk_id` | Integer | FK -> document_chunks.id, CASCADE, nullable, indexed | Self-referential link from child paragraph chunks to their parent section chunk (AI-4.2). NULL for parents and standalone leaf chunks. |
| `heading_path` | String(500) | Nullable | Heading hierarchy path (e.g. "Safety > Emergency Procedures > Route Deviation"). Promoted from `metadata_json` for direct column access. |
| `section_type` | String(20) | Nullable | Structural classification: `"heading" \| "body" \| "list" \| "table"`. Used for retrieval boosting/filtering by structural role. |
| `lemmatized_content` | Text | Nullable | KB-2: UDPipe-lemmatized form of `content` for Latvian docs. NULL for non-Latvian/legacy chunks — BM25 falls back to `content` via `COALESCE`. |
| `created_at` | DateTime | Not null | Auto-set on create |
| `updated_at` | DateTime | Not null | Auto-set on update |

Table: `search_feedback` (KB-4)

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | Integer | PK | Primary key |
| `query_hash` | String(64) | Not null, indexed | Stable hash of (normalized query, domain) returned on SearchResponse |
| `query_type` | String(16) | Not null | Query classification: `keyword` / `semantic` / `mixed` |
| `chunk_id` | Integer | FK -> document_chunks.id, CASCADE, indexed | Rated chunk |
| `rank_source` | String(16) | Not null | Retrieval branch that surfaced the chunk: `vector` / `fulltext` / `both` |
| `relevant` | Boolean | Not null | True for thumbs-up, False for thumbs-down |
| `user_id` | Integer | FK -> users.id, SET NULL | Voter; NULLed when the user is deleted |
| `created_at` | DateTime | Not null | Auto-set on create |
| `updated_at` | DateTime | Not null | Auto-set on update |
| | | Index `ix_search_feedback_qtype_created` on `(query_type, created_at)` | Supports the 30-day aggregation query in `feedback_counts()` |
| | | Unique `(user_id, query_hash, chunk_id)` | One vote per user per chunk per query (second call upserts) |

## Business Rules

1. Documents are processed asynchronously: status transitions from "pending" -> "processing" -> "completed" or "failed"
2. Deleting a document cascades to all its chunks and tag associations (ON DELETE CASCADE) and removes stored files
3. Empty documents (no extractable text) get status "completed" with chunk_count=0
4. Search uses 'simple' PostgreSQL text search config (no language-specific stemming) to support Latvian + English
5. RRF fusion combines vector and fulltext results with query-adaptive weights; a chunk appearing in both gets boosted
6. Temporal boost multiplies RRF scores by document age (configurable: today/week/month/older multipliers). Evergreen documents always get 1.0x (no decay)
7. Agent tool truncates chunk content to 1500 characters for token efficiency
7. Embedding dimension is configurable (default 1024) and must match the pgvector column
8. File persistence stores originals at `{DOCUMENT_STORAGE_PATH}/{document_id}/{filename}`
9. Legacy documents (uploaded before DMS) have no stored file; download raises ProcessingError
10. Document update uses PATCH semantics — only non-None fields from `DocumentUpdate` are applied via setattr
11. Excel extraction produces tab-separated text with sheet headers; CSV uses tab separation
12. Title defaults to filename stem if not provided during upload
13. Scanned PDFs (< 50 chars extracted by PyMuPDF) trigger automatic OCR via pytesseract at 300 DPI, limited to first 50 pages
14. `ocr_applied` flag tracks whether OCR was used, enabling frontend OCR badge display
15. Tag names are normalized to lowercase with whitespace stripped on creation
16. Tag names must be unique (409 Conflict on duplicate)
17. Tag deletion cascades to all document associations
18. Documents can have 1-20 tags added in a single request
19. Auto-tagging is best-effort: LLM failures are logged but never block document ingestion
20. Auto-tagging creates/links tags via race-safe `get_or_create_tag` (IntegrityError catch + rollback + retry)
21. Batch tag loading for document lists eliminates N+1 queries
22. **Parent-child chunk hierarchy (AI-4.2):** Multi-paragraph sections produce one parent chunk (full section) + N child chunks (one per paragraph) linked via `parent_chunk_id`. Single-paragraph sections stay as standalone leaf chunks. Both parents and children are embedded and individually searchable. Deleting a parent CASCADE-deletes its children.
23. **Two-phase chunk insert:** Parents are flushed first (`bulk_create_chunks(..., flush_only=True)`) to obtain DB ids before children are constructed with resolved `parent_chunk_id`. Both phases share one `AsyncSession` so parent + child writes commit atomically.
24. **Re-chunk migration (AI-4.4):** `KnowledgeService.rechunk_document()` and `scripts/rechunk_documents.py` allow re-chunking previously-ingested documents under the current chunking config without re-uploading. Existing chunks are deleted via `repository.delete_chunks_by_document()` (keeps the `Document` row), then the same two-phase parent/child store used by fresh ingestion runs against the on-disk file. Document metadata, tags, `evergreen`, language, and domain are preserved. Auto-tagging is intentionally NOT re-run. Failures mark `status="failed"` and re-raise so the script's outer loop can record + skip. Exposed via `make rechunk` and `make rechunk-dry-run`.
25. **Search-time parent context expansion (AI-4.3):** After confidence filtering, `KnowledgeService.search()` collects unique `parent_chunk_id`s from surviving results and batch-fetches them via `repository.get_chunks_by_ids()` in a single round-trip. Multiple matched children of the same parent dedupe to one fetch. Each result is enriched with `parent_chunk_id`, `parent_content` (truncated to `knowledge_parent_context_max_chars`, default 3000), and `heading_path`. Leaf chunks (no parent) are unaffected. Feature-gated on `knowledge_parent_context_enabled` (default True) — disabling reverts to pre-AI-4.3 behavior. The agent tool formatter renders `[Section: {heading_path}]\n{parent_content}\n\n[Matched passage:]\n{child_content}` so the LLM sees the full surrounding section, not just the matched paragraph.

## Integration Points

- **Agent Module**: `search_knowledge_base` tool registered in `app/core/agents/agent.py`, uses `AsyncSessionLocal` for direct DB access. Agent system prompt includes CITATION RULES for `[title](/{locale}/documents/{id})` links.
- **Core Config**: 33 settings in `app/core/config.py` (embedding, embedding_cache, reranker, chunking, semantic_chunking, parent_context, document_storage_path, auto_tag, hyde, temporal_boost, rrf_weights). New in AI-4.3: `knowledge_parent_context_enabled` (default `True`), `knowledge_parent_context_max_chars` (default `3000`).
- **Shared Utilities**: Uses `PaginationParams`, `PaginatedResponse`, `TimestampMixin`, `get_db()`, `get_logger()`
- **Frontend**: Documents management page at `/[locale]/documents` with upload, list, detail, download, delete
- **Pydantic AI**: Auto-tagging and HyDE query expansion use `pydantic-ai` Agent for LLM calls (lazy-imported, provider configured via existing settings)
- **Operations Tooling**: `scripts/rechunk_documents.py` provides a one-shot CLI to re-chunk all existing documents under the current chunking config (AI-4.4). Exposed via `make rechunk` and `make rechunk-dry-run`. Reads DB via `get_db_context()` — no env-var leak.

## API Endpoints

| Method | Path | Auth | Rate Limit | Description |
|--------|------|------|-----------|-------------|
| POST | `/api/v1/knowledge/documents` | admin, editor | 10/min | Upload and ingest a document (with title, description) |
| GET | `/api/v1/knowledge/documents` | any authenticated | 30/min | List documents (paginated, filterable by domain/status/tag) |
| GET | `/api/v1/knowledge/documents/{id}` | any authenticated | 30/min | Get document by ID (with tags) |
| PATCH | `/api/v1/knowledge/documents/{id}` | admin, editor | 10/min | Update document metadata (title, description, domain, language) |
| GET | `/api/v1/knowledge/documents/{id}/download` | any authenticated | 30/min | Download original uploaded file |
| GET | `/api/v1/knowledge/documents/{id}/content` | any authenticated | 30/min | Get extracted text chunks for a document |
| DELETE | `/api/v1/knowledge/documents/{id}` | admin, editor | 10/min | Delete document, chunks, tags, and stored file |
| GET | `/api/v1/knowledge/domains` | any authenticated | 30/min | List unique document domains with count |
| POST | `/api/v1/knowledge/search` | any authenticated | 30/min | Hybrid search with reranking |
| POST | `/api/v1/knowledge/search/{query_hash}/feedback` | any authenticated | 60/min | KB-4: record thumbs-up/down on a cited chunk |
| GET | `/api/v1/knowledge/tags` | any authenticated | 30/min | List all tags sorted by name |
| POST | `/api/v1/knowledge/tags` | admin, editor | 10/min | Create new tag (409 on duplicate) |
| DELETE | `/api/v1/knowledge/tags/{tag_id}` | admin, editor | 10/min | Delete tag and all document associations |
| POST | `/api/v1/knowledge/documents/{id}/tags` | admin, editor | 10/min | Add tags to document (1-20 tag IDs) |
| DELETE | `/api/v1/knowledge/documents/{id}/tags/{tag_id}` | admin, editor | 10/min | Remove tag from document |
