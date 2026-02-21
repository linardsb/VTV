# Code Review: app/knowledge/

**Reviewer:** Claude Opus 4.6
**Date:** 2026-02-21
**Scope:** All files in `app/knowledge/` including `tests/` subdirectory (17 Python files)
**Standards:** Architecture, Type Safety, Error Handling, Security, Performance, Testing, Logging, Code Quality

---

## Summary

The knowledge feature is a well-structured vertical slice implementing RAG-based document ingestion and hybrid search (vector + fulltext + RRF fusion + reranking). The architecture is clean, layer separation is mostly correct, and the code reads well. However, there are several security issues around file uploads, a path traversal vulnerability in the download endpoint, missing file size enforcement, and some architectural concerns around repository-level commits and global mutable singletons. Testing covers the main paths but has significant gaps in edge cases, error paths, and repository/route layers.

**Verdict:** Generally solid implementation. The Critical and High findings should be addressed before production deployment.

---

## Findings

### Critical

#### C1. Path Traversal in File Download Endpoint
**File:** `/Users/Berzins/Desktop/VTV/app/knowledge/routes.py`, lines 147-161
**Standard:** Security

The download endpoint resolves the file path from the database and serves it via `FileResponse`. However, if an attacker can inject a crafted `file_path` into the database (e.g., via a compromised import, direct DB access, or a bug in the storage logic), `.resolve()` does not prevent serving arbitrary files from the filesystem.

```python
@router.get("/documents/{document_id}/download")
async def download_document(...) -> FileResponse:
    file_path, filename = await service.get_document_file_path(document_id)
    return FileResponse(
        path=Path(file_path).resolve(),  # No validation against storage root
        filename=filename,
        media_type="application/octet-stream",
    )
```

**Fix:** Validate that the resolved path starts with the configured `document_storage_path` before serving:
```python
resolved = Path(file_path).resolve()
storage_root = Path(settings.document_storage_path).resolve()
if not str(resolved).startswith(str(storage_root)):
    raise ProcessingError("File path outside storage directory")
```

#### C2. No File Size Limit on Upload
**File:** `/Users/Berzins/Desktop/VTV/app/knowledge/routes.py`, lines 65-105
**Standard:** Security

The `upload_document` endpoint reads the entire file into memory (`content = await file.read()`) with no size check. The project has a `BodySizeLimitMiddleware` at 100KB, but typical document uploads (PDFs, Excel files) will commonly exceed this. Either the middleware blocks legitimate uploads, or if the limit is raised, an attacker can exhaust server memory.

```python
content = await file.read()  # No streaming, no size check
tmp.write(content)
```

**Fix:** Add explicit file size validation in the route, and stream to disk in chunks rather than reading the entire file into memory:
```python
MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50MB
content = await file.read()
if len(content) > MAX_UPLOAD_SIZE:
    raise HTTPException(status_code=413, detail="File too large")
```
Or better, stream in chunks to avoid memory pressure.

#### C3. Filename Injection via Unsanitized Filename
**File:** `/Users/Berzins/Desktop/VTV/app/knowledge/routes.py`, line 89; `/Users/Berzins/Desktop/VTV/app/knowledge/service.py`, lines 124-126
**Standard:** Security

The original filename from the upload is used directly to construct a storage path with no sanitization:

```python
# routes.py
suffix = Path(file.filename or "upload").suffix  # Trusts user input

# service.py
stored_path = storage_dir / filename  # filename comes from user
shutil.copy2(file_path, stored_path)
```

A filename like `../../etc/passwd` or `foo\x00.pdf` could cause path traversal or null-byte injection.

**Fix:** Sanitize the filename before use:
```python
import re
safe_name = re.sub(r'[^\w\-.]', '_', Path(filename).name)
stored_path = storage_dir / safe_name
```

---

### High

#### H1. Repository Commits Inside Individual Methods (Transaction Boundary Leak)
**File:** `/Users/Berzins/Desktop/VTV/app/knowledge/repository.py`, lines 62-63, 154, 166, 189, 204, 238
**Standard:** Architecture

Every repository method calls `await self.db.commit()` internally. This violates the principle that the service layer should own transaction boundaries. If `ingest_document` fails after `create_document` has committed (line 62-63), the database has a partial record in `documents` table with no rollback path. The `try/except` in the service catches the exception and updates the status to "failed", but this is a workaround for what should be a single transaction.

```python
# repository.py - commits happen inside each method
async def create_document(self, ...) -> Document:
    ...
    await self.db.commit()  # Committed independently
    await self.db.refresh(doc)
    return doc
```

**Fix:** Remove commits from repository methods and let the service layer call `await self.db.commit()` once after all operations succeed, or use explicit savepoints for partial rollback.

#### H2. Global Mutable Singletons Without Thread Safety
**File:** `/Users/Berzins/Desktop/VTV/app/knowledge/service.py`, lines 39-56
**Standard:** Architecture, Code Quality

The embedding and reranker providers use module-level mutable globals with no locking:

```python
_embedding_provider: EmbeddingProvider | None = None
_reranker_provider: RerankerProvider | None = None

def _get_embedding() -> EmbeddingProvider:
    global _embedding_provider
    if _embedding_provider is None:
        _embedding_provider = get_embedding_provider(get_settings())
    return _embedding_provider
```

In an async context with concurrent requests, two coroutines could both see `None` and initialize the provider twice. While unlikely to cause a crash (last write wins), it wastes resources and could cause issues with stateful providers. Additionally, these singletons are never reset, making testing harder (must patch module globals).

**Fix:** Use `functools.lru_cache` (matching the `get_settings()` pattern already in the codebase) or initialize providers during FastAPI lifespan startup.

#### H3. `setattr` on Model Without Field Allowlist
**File:** `/Users/Berzins/Desktop/VTV/app/knowledge/repository.py`, lines 186-188
**Standard:** Security

The `update_document` method uses `setattr` with unchecked `**kwargs`:

```python
for key, value in kwargs.items():
    if value is not None:
        setattr(doc, key, value)
```

While the caller (`service.update_document`) passes `data.model_dump(exclude_unset=True)`, there is no allowlist in the repository itself. If a future caller passes unexpected fields (e.g., `status`, `chunk_count`, `id`), they would be silently applied.

**Fix:** Add an explicit allowlist:
```python
UPDATABLE_FIELDS = {"title", "description", "domain", "language"}
for key, value in kwargs.items():
    if key in UPDATABLE_FIELDS and value is not None:
        setattr(doc, key, value)
```

#### H4. `UnsupportedDocumentTypeError` Maps to 500 Instead of 400/422
**File:** `/Users/Berzins/Desktop/VTV/app/knowledge/exceptions.py`, lines 29-30
**Standard:** Error Handling

`UnsupportedDocumentTypeError` inherits from `KnowledgeBaseError -> DatabaseError`. The global exception handler in `app/core/exceptions.py` maps `DatabaseError` to HTTP 500. But an unsupported file type is a client validation error (400 or 422), not a server error.

```python
class UnsupportedDocumentTypeError(KnowledgeBaseError):
    """Raised for unknown file extensions."""
```

**Fix:** Have `UnsupportedDocumentTypeError` inherit from `core.exceptions.ValidationError` instead, which maps to 422.

#### H5. `list_documents` Missing `language` Filter in Count Query
**File:** `/Users/Berzins/Desktop/VTV/app/knowledge/service.py`, lines 399-405; `/Users/Berzins/Desktop/VTV/app/knowledge/repository.py`, lines 110-131
**Standard:** Code Quality (Bug)

The `list_documents` service method passes `domain` and `status` to `count_documents`, but the `list_documents` repository method also accepts a `language` filter. The count query does not accept `language` at all, so when listing with a language filter, the total count will be wrong (counting all documents regardless of language):

```python
# service.py
docs = await self.repository.list_documents(
    offset=pagination.offset,
    limit=pagination.page_size,
    domain=domain,
    status=status,
    # Note: language filter not passed here either
)
total = await self.repository.count_documents(domain=domain, status=status)
# count_documents() doesn't accept language param
```

Additionally, the service `list_documents` method does not expose the `language` filter parameter at all, even though the repository supports it and the list endpoint could benefit from it.

**Fix:** Add `language` parameter to both `count_documents` and the service's `list_documents` method. Expose it as a query parameter in the route.

---

### Medium

#### M1. Temporary File Not Cleaned Up on Ingest Exception
**File:** `/Users/Berzins/Desktop/VTV/app/knowledge/routes.py`, lines 90-105
**Standard:** Code Quality

The temp file is cleaned up in `finally`, which is correct. However, the stored copy in `data/documents/{id}/` is NOT cleaned up when ingestion fails. The service's `ingest_document` method copies the file to permanent storage before embedding, but if embedding fails, the file remains on disk even though the document status is "failed":

```python
# service.py lines 122-127 - file copied before embedding
shutil.copy2(file_path, stored_path)
await self.repository.update_document_file_path(doc.id, str(stored_path))
# ... if embedding fails after this, file stays on disk
```

**Fix:** Move file storage to after successful processing, or add cleanup in the error handler.

#### M2. Embedding Column Not Typed with `Mapped`
**File:** `/Users/Berzins/Desktop/VTV/app/knowledge/models.py`, line 51
**Standard:** Type Safety

All other columns use `Mapped[T]` annotations, but the embedding column uses bare `mapped_column`:

```python
embedding = mapped_column(Vector(1024))  # Missing Mapped annotation
```

This breaks the consistent pattern and means mypy/pyright cannot infer the type. The `# pyright: reportUnknownMemberType=false` at file top is needed partly because of this.

**Fix:** While pgvector's `Vector` type may not fully integrate with SQLAlchemy's `Mapped` type system, adding a comment explaining this limitation would clarify the intentional deviation.

#### M3. Hardcoded Embedding Dimension in Model
**File:** `/Users/Berzins/Desktop/VTV/app/knowledge/models.py`, line 51
**Standard:** Code Quality

The vector dimension is hardcoded to 1024 in the model:

```python
embedding = mapped_column(Vector(1024))
```

But the dimension is configurable via `settings.embedding_dimension`. If someone changes the embedding provider to one with a different dimension, the database column won't match, causing silent truncation or errors.

**Fix:** Document this coupling clearly. Consider using a migration to alter the column if the dimension changes, or at minimum add a startup check that validates `settings.embedding_dimension == 1024`.

#### M4. No Content-Type Validation Beyond Extension Mapping
**File:** `/Users/Berzins/Desktop/VTV/app/knowledge/routes.py`, lines 34-62
**Standard:** Security

The `_detect_source_type` function trusts the MIME type from the upload, which is set by the client and can be spoofed. A malicious file could be uploaded with `content_type: text/plain` but actually contain executable content. There's no magic-byte validation.

```python
def _detect_source_type(content_type: str | None) -> str:
    if content_type is None:
        return "text"  # Defaults to text with no validation
```

**Fix:** For defense in depth, also check the file extension from the filename, and optionally use `python-magic` for magic-byte detection.

#### M5. `ProcessingError` Used for Non-Processing Issues
**File:** `/Users/Berzins/Desktop/VTV/app/knowledge/service.py`, line 262
**Standard:** Error Handling

`ProcessingError` is raised when a document has no stored file (legacy upload), which is not actually a processing error:

```python
raise ProcessingError(f"Document {document_id} has no stored file (legacy upload)")
```

This maps to HTTP 500 via the exception hierarchy, but should be a 404 or a more specific error like `FileNotAvailableError`.

**Fix:** Create a `FileNotAvailableError` or use `DocumentNotFoundError` with a descriptive message.

#### M6. `for i in range(len(chunks))` Anti-Pattern
**File:** `/Users/Berzins/Desktop/VTV/app/knowledge/service.py`, lines 151-159
**Standard:** Code Quality

Uses C-style indexing instead of Pythonic `zip` or `enumerate`:

```python
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
```

**Fix:** Use `zip`:
```python
chunk_objects = [
    DocumentChunk(
        document_id=doc.id,
        content=chunk.content,
        chunk_index=chunk.chunk_index,
        embedding=emb,
        metadata_json=None,
    )
    for chunk, emb in zip(chunks, embeddings, strict=True)
]
```

#### M7. Vector and Fulltext Searches Run Sequentially
**File:** `/Users/Berzins/Desktop/VTV/app/knowledge/service.py`, lines 298-303
**Standard:** Performance

The two search queries (vector + fulltext) run sequentially even though they are independent:

```python
vector_results = await self.repository.search_vector(...)
text_results = await self.repository.search_fulltext(...)
```

**Fix:** Run them concurrently with `asyncio.gather`:
```python
vector_results, text_results = await asyncio.gather(
    self.repository.search_vector(...),
    self.repository.search_fulltext(...),
)
```

Note: This requires both queries to use separate sessions or the same session to support concurrent queries, which may not be the case with a single `AsyncSession`. Verify before applying.

#### M8. No Fulltext Search Index
**File:** `/Users/Berzins/Desktop/VTV/app/knowledge/repository.py`, lines 277-318
**Standard:** Performance

The fulltext search uses `to_tsvector('simple', DocumentChunk.content)` and `plainto_tsquery('simple', ...)` on every query. Without a GIN index on `to_tsvector('simple', content)`, this performs a sequential scan on every search, which will degrade significantly as the chunk table grows.

**Fix:** Add a GIN index in a migration:
```sql
CREATE INDEX idx_document_chunks_content_tsvector
ON document_chunks USING gin(to_tsvector('simple', content));
```

#### M9. `update_document_status` Silently Ignores Missing Documents
**File:** `/Users/Berzins/Desktop/VTV/app/knowledge/repository.py`, lines 133-154
**Standard:** Error Handling

If the document doesn't exist, the method does nothing silently:

```python
if doc:
    doc.status = status
    ...
```

The same pattern applies to `delete_document` (line 162-166) and `update_document_file_path` (line 193-204). While the service layer typically checks existence first, silent failures in the repository can mask bugs.

**Fix:** Either raise an exception or return a boolean indicating success. At minimum, log a warning when the document is not found.

---

### Low

#### L1. Broad Exception Catch in `ingest_document`
**File:** `/Users/Berzins/Desktop/VTV/app/knowledge/service.py`, line 166
**Standard:** Error Handling

The bare `except Exception` catches everything including `KeyboardInterrupt` (indirectly via `BaseException` subclasses). While the re-raise mitigates the damage, it's better to be explicit.

```python
except Exception as e:
    await self.repository.update_document_status(doc.id, "failed", str(e), 0)
```

This is acceptable since it re-raises, but `update_document_status` itself could fail (e.g., DB connection lost), which would mask the original error.

**Fix:** Wrap the status update in its own try/except:
```python
except Exception as e:
    try:
        await self.repository.update_document_status(doc.id, "failed", str(e), 0)
    except Exception:
        logger.error("knowledge.ingest.status_update_failed", document_id=doc.id)
    raise
```

#### L2. No Test Coverage for Repository Layer
**Standard:** Testing

There are no tests for `KnowledgeRepository` methods. All service tests mock the repository. This means SQL query construction, filtering logic, and the critical `search_vector`/`search_fulltext` methods are completely untested.

**Fix:** Add integration tests (marked `@pytest.mark.integration`) that test repository methods against a real database, especially the vector and fulltext search queries.

#### L3. No Test Coverage for Route Layer
**Standard:** Testing

There are no tests for the FastAPI route handlers (`routes.py`). The file upload flow, content-type detection, query parameter parsing, rate limiting, and HTTP status codes are untested.

**Fix:** Add tests using `httpx.AsyncClient` or `fastapi.testclient.TestClient` to verify route behavior, especially the upload endpoint's file handling and error responses.

#### L4. No Test for Search Service Method
**Standard:** Testing

The `search` method in `KnowledgeService` (the most complex method, implementing RRF fusion and reranking) has zero test coverage.

**Fix:** Add unit tests that mock the repository and embedding/reranker providers to verify RRF score calculation, deduplication, and result ordering.

#### L5. `DocumentUpdate` Accepts Empty Patch
**File:** `/Users/Berzins/Desktop/VTV/app/knowledge/schemas.py`, lines 18-24
**Standard:** Code Quality

All fields in `DocumentUpdate` are optional with no validation that at least one field is provided. An empty `{}` body will hit the database and return the unchanged document.

```python
class DocumentUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    domain: str | None = Field(None, min_length=1, max_length=50)
    language: str | None = Field(None, pattern="^(lv|en)$")
```

**Fix:** Add a model validator to reject empty updates:
```python
@model_validator(mode="after")
def check_at_least_one_field(self) -> Self:
    if not any(v is not None for v in self.model_dump(exclude_unset=True).values()):
        raise ValueError("At least one field must be provided")
    return self
```

#### L6. `_detect_source_type` Falls Back to "text" for Unknown Types
**File:** `/Users/Berzins/Desktop/VTV/app/knowledge/routes.py`, line 62
**Standard:** Error Handling

Any unrecognized MIME type (including `application/octet-stream`, `application/zip`) silently defaults to "text" and will be processed by `_extract_text_sync`, which reads the file as UTF-8 text. This could produce garbage output or raise encoding errors.

```python
return "text"  # Catch-all for unknown types
```

**Fix:** Return `"unknown"` and let the processing layer reject it via `UnsupportedDocumentTypeError`, or reject unknown types at the route level.

#### L7. Chunk Position Metadata Uses Heuristic Search
**File:** `/Users/Berzins/Desktop/VTV/app/knowledge/chunking.py`, lines 64-67
**Standard:** Code Quality

The character offset tracking uses `text.find(chunk_text_content[:50], ...)` which is a fragile heuristic. If the first 50 characters of a chunk appear elsewhere in the document, the offset will be wrong.

```python
pos = text.find(chunk_text_content[:50], max(0, char_pos - chunk_overlap))
if pos == -1:
    pos = char_pos  # Fallback: just estimate
```

**Fix:** Track offsets during the splitting/building phase instead of reverse-engineering them afterward.

#### L8. Missing `async` Marker on Test Functions
**File:** `/Users/Berzins/Desktop/VTV/app/knowledge/tests/test_chunking.py`, lines 7-60 (some tests)
**Standard:** Testing

Some test functions (`test_short_text_single_chunk`, `test_empty_text_no_chunks`, etc.) are synchronous but test synchronous code, which is fine. However, `test_latvian_diacritics_preserved` has a return type annotation (`-> None`) while others don't, creating inconsistency.

**Fix:** Add `-> None` return type annotations to all test functions for consistency.

#### L9. `metadata_json` Stored as Raw String Instead of JSONB
**File:** `/Users/Berzins/Desktop/VTV/app/knowledge/models.py`, line 33
**Standard:** Code Quality

`metadata_json` is stored as `Text` and treated as a raw JSON string. PostgreSQL has native `JSONB` support that would enable querying, indexing, and validation of metadata.

```python
metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
```

**Fix:** Consider migrating to `JSONB` column type for better PostgreSQL integration. This is a low priority since current usage only stores/retrieves the field without querying it.

#### L10. OpenAI Provider Passes Empty String as API Key
**File:** `/Users/Berzins/Desktop/VTV/app/knowledge/embedding.py`, line 178
**Standard:** Error Handling

When `embedding_api_key` is `None`, it falls back to empty string:

```python
api_key=settings.embedding_api_key or "",
```

This will produce a cryptic authentication error from the OpenAI API instead of a clear startup error.

**Fix:** Validate that the API key is set when using OpenAI/Jina providers:
```python
if not settings.embedding_api_key:
    raise ValueError("embedding_api_key is required for OpenAI/Jina providers")
```

---

## Recommendations

### Priority 1 (Critical -- fix before production)
1. **Sanitize uploaded filenames** (C3) to prevent path traversal in storage
2. **Validate download paths** against storage root (C1) to prevent arbitrary file reads
3. **Add file size limits** with streaming upload (C2) to prevent memory exhaustion

### Priority 2 (High -- fix soon)
4. **Move transaction boundaries** to the service layer (H1) for data consistency
5. **Add field allowlist** to `update_document` repository method (H3)
6. **Fix exception hierarchy** for `UnsupportedDocumentTypeError` (H4)
7. **Fix count query** to include language filter (H5)

### Priority 3 (Medium -- plan for next iteration)
8. **Add GIN index** for fulltext search (M8)
9. **Consider concurrent search** queries (M7)
10. **Clean up stored files** on failed ingestion (M1)
11. **Use Pythonic iteration** patterns (M6)

### Priority 4 (Low -- address opportunistically)
12. **Add integration tests** for repository and route layers (L2, L3)
13. **Add unit tests** for the search method (L4)
14. **Validate non-empty updates** in `DocumentUpdate` (L5)
15. **Reject truly unknown file types** instead of defaulting to text (L6)
