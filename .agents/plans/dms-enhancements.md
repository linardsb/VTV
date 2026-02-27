# Plan: DMS Enhancements

## Feature Metadata
**Feature Type**: Enhancement
**Estimated Complexity**: Medium
**Primary Systems Affected**: `app/knowledge/` (processing, models, schemas, routes, service, repository)

## Feature Description

The Document Management System has three remaining backend tasks from the original planning document (`docs/PLANNING/latvian-language-and-model-research.md` lines 218-227): scanned PDF OCR detection, LLM auto-tagging on upload, and tag CRUD endpoints.

**Scanned PDF OCR:** Currently, `_extract_pdf_sync()` in `processing.py` uses PyMuPDF's `page.get_text()` which returns empty strings for scanned/image-only PDFs. This causes silent data loss — documents upload with `chunk_count=0` and status "completed". The fix: detect when PyMuPDF returns little/no text, render pages to images via `page.get_pixmap()`, and OCR them with pytesseract (already a dependency, already used for standalone images with `lang="lav+eng"`). Add an `ocr_applied` boolean column to `Document` so the frontend can show an OCR badge.

**Tag CRUD:** No tag infrastructure exists. We need a `Tag` model, a `document_tags` many-to-many association table, Pydantic schemas for tag create/list/delete, REST endpoints at `/api/v1/knowledge/tags`, and tag filtering on `list_documents`. Tags are simple string labels managed by admin/editor users. Documents can have multiple tags.

**LLM Auto-Tagging:** After text extraction during `ingest_document`, send the first 500 characters to a lightweight LLM call (using the already-configured provider via `pydantic-ai`) to classify domain and suggest 1-3 tags. This is best-effort: if the LLM call fails, ingestion continues normally without tags. Auto-tagging runs asynchronously and does not block the upload response.

## User Story

As an administrator or editor,
I want scanned PDFs to be OCR'd automatically, documents to be auto-tagged on upload, and the ability to manage tags,
So that the knowledge base captures text from all document types, discovery is improved through consistent tagging, and I can organize documents efficiently.

## Solution Approach

We chose to implement all three enhancements as modifications to the existing `app/knowledge/` feature slice rather than creating new feature directories, because:
- All three enhancements modify existing knowledge base behavior (processing pipeline, document model, document routes)
- Tag management is a sub-resource of documents, not a standalone domain
- Keeps the knowledge vertical slice cohesive

**Approach Decision:**
We chose simple string tags with a join table (not JSONB array) because:
- Join table supports efficient filtering (`WHERE EXISTS (SELECT ... FROM document_tags)`)
- Enables `GET /tags` to list all unique tags without scanning all documents
- Supports future tag metadata (description, color, usage count) by expanding the `Tag` model

**Alternatives Considered:**
- JSONB array on `documents.tags`: Rejected — harder to query, no referential integrity, can't list unique tags efficiently
- Separate `tagging` feature slice: Rejected — tags are tightly coupled to documents, would cause unnecessary cross-feature writes

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, logging patterns, type checking requirements
- `app/knowledge/models.py` (all) — Current Document and DocumentChunk models
- `app/knowledge/schemas.py` (all) — Current Pydantic schemas for request/response
- `app/knowledge/processing.py` (lines 63-82) — `_extract_pdf_sync()` that needs OCR fallback
- `app/knowledge/processing.py` (lines 135-151) — `_extract_image_sync()` showing existing OCR pattern
- `app/knowledge/service.py` (lines 71-201) — `ingest_document()` pipeline where OCR and auto-tagging integrate
- `app/knowledge/routes.py` (all) — Current 9 endpoints, pattern for new tag endpoints
- `app/knowledge/repository.py` (all) — Current repository methods, pattern for tag queries
- `app/knowledge/exceptions.py` (all) — Current exception hierarchy

### Similar Features (Examples to Follow)
- `app/knowledge/routes.py` (lines 224-233) — `list_domains()` pattern: simple GET returning list, good template for `list_tags()`
- `app/events/models.py` — Example of foreign key relationships between models
- `app/drivers/routes.py` — Example of CRUD endpoints with `require_role()` and pagination

### Files to Modify
- `app/knowledge/models.py` — Add `Tag`, `document_tags`, `ocr_applied` column
- `app/knowledge/schemas.py` — Add tag schemas, add `tags` and `ocr_applied` to responses
- `app/knowledge/processing.py` — Add OCR fallback to `_extract_pdf_sync()`
- `app/knowledge/service.py` — Add auto-tagging in `ingest_document()`, add tag CRUD methods
- `app/knowledge/routes.py` — Add 4 tag endpoints, add tag filter to `list_documents`
- `app/knowledge/repository.py` — Add tag repository methods
- `app/core/config.py` — Add `auto_tag_enabled` setting

### Files NOT to Modify
- `app/main.py` — Knowledge router is already registered; tag endpoints are sub-routes on the same router

## Implementation Plan

### Phase 1: Foundation (models, schemas, migration, config)
Add database models, schemas, migration, and config settings. No behavior changes yet.

### Phase 2: Scanned PDF OCR
Modify the PDF extractor to detect scanned pages and fall back to pytesseract OCR.

### Phase 3: Tag CRUD
Add tag management endpoints (list, create, delete, tag/untag documents).

### Phase 4: LLM Auto-Tagging
Add lightweight LLM classification in the ingestion pipeline.

### Phase 5: Tests
Add unit tests for all new functionality.

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.

---

### Task 1: Add Tag Model, Association Table, and ocr_applied Column
**File:** `app/knowledge/models.py` (modify existing)
**Action:** UPDATE

Add these to the existing models file:

1. Add `ocr_applied` column to `Document` model:
   - `ocr_applied: Mapped[bool] = mapped_column(default=False)` — tracks whether OCR was used during extraction

2. Add `Tag` model:
   - `__tablename__ = "tags"`
   - `id: Mapped[int]` — primary key, indexed
   - `name: Mapped[str]` — `String(100)`, NOT NULL, unique, indexed
   - Inherits `Base` and `TimestampMixin`

3. Add `document_tags` association table using SQLAlchemy `Table()`:
   - `document_id: Integer, ForeignKey("documents.id", ondelete="CASCADE")`
   - `tag_id: Integer, ForeignKey("tags.id", ondelete="CASCADE")`
   - `PrimaryKeyConstraint("document_id", "tag_id")`

Required imports to add: `from sqlalchemy import Boolean, Column, PrimaryKeyConstraint, Table`

**Per-task validation:**
- `uv run ruff format app/knowledge/models.py`
- `uv run ruff check --fix app/knowledge/models.py`
- `uv run mypy app/knowledge/models.py`
- `uv run pyright app/knowledge/models.py`

---

### Task 2: Add Tag and Document Schemas
**File:** `app/knowledge/schemas.py` (modify existing)
**Action:** UPDATE

1. Add `TagCreate` schema:
   - `name: str = Field(..., min_length=1, max_length=100, description="Tag name")`
   - Add `@field_validator("name")` that strips whitespace and lowercases

2. Add `TagResponse` schema:
   - `id: int`
   - `name: str`
   - `created_at: datetime`
   - `model_config = ConfigDict(from_attributes=True)`

3. Add `TagListResponse` schema:
   - `tags: list[TagResponse]`
   - `total: int`

4. Add `DocumentTagRequest` schema:
   - `tag_ids: list[int] = Field(..., min_length=1, max_length=20, description="Tag IDs to assign")`

5. Update `DocumentResponse` to add:
   - `tags: list[TagResponse] = Field(default_factory=list)`
   - `ocr_applied: bool`

6. **Schema Impact Tracing:** Grep for `DocumentResponse(` and `_make_doc_response(` across `app/knowledge/` — all constructors and test helpers must be updated to include `ocr_applied` and `tags` fields. The `_make_doc_response()` helper in `test_routes.py` needs `ocr_applied=False` and `tags=[]` added to its defaults. The `model_validate()` calls in `service.py` will auto-populate from the ORM model.

**Per-task validation:**
- `uv run ruff format app/knowledge/schemas.py`
- `uv run ruff check --fix app/knowledge/schemas.py`
- `uv run mypy app/knowledge/schemas.py`
- `uv run pyright app/knowledge/schemas.py`

---

### Task 3: Create Database Migration
**Action:** CREATE migration

Create a migration for:
1. Add `ocr_applied` boolean column to `documents` table (NOT NULL, default False)
2. Create `tags` table (id PK, name VARCHAR(100) UNIQUE NOT NULL, created_at, updated_at)
3. Create `document_tags` association table (document_id FK, tag_id FK, composite PK)

**If database is running:**
```bash
uv run alembic revision --autogenerate -m "add_tags_and_ocr_to_documents"
uv run alembic upgrade head
```

**If database is NOT running (manual fallback):**
- `documents.ocr_applied`: `Boolean`, nullable=False, server_default=`sa.text("false")`
- `tags.id`: `Integer`, primary_key=True
- `tags.name`: `String(100)`, nullable=False, unique=True
- `tags.created_at`: `DateTime`, nullable=False, server_default=`sa.text("now()")`
- `tags.updated_at`: `DateTime`, nullable=False, server_default=`sa.text("now()")`
- `document_tags.document_id`: `Integer`, ForeignKey("documents.id", ondelete="CASCADE")
- `document_tags.tag_id`: `Integer`, ForeignKey("tags.id", ondelete="CASCADE")
- PrimaryKeyConstraint on (document_id, tag_id)

**Per-task validation:**
- Migration file passes `uv run ruff format alembic/versions/*.py`
- `uv run alembic upgrade head` succeeds (if DB running)

---

### Task 4: Add Config Setting for Auto-Tagging
**File:** `app/core/config.py` (modify existing)
**Action:** UPDATE

Add to the `Settings` class near the existing knowledge base settings (around line 163):
- `auto_tag_enabled: bool = False` — Feature flag for LLM auto-tagging on upload
- `auto_tag_max_chars: int = 500` — Maximum characters sent to LLM for classification

**Per-task validation:**
- `uv run ruff format app/core/config.py`
- `uv run ruff check --fix app/core/config.py`
- `uv run mypy app/core/config.py`

---

### Task 5: Add OCR Fallback to PDF Extraction
**File:** `app/knowledge/processing.py` (modify existing)
**Action:** UPDATE

Modify `_extract_pdf_sync()` (lines 63-82) to detect scanned PDFs and apply OCR:

1. After the existing PyMuPDF text extraction loop, check if `pages` is empty or total text length < 50 characters (threshold for "likely scanned")
2. If scanned, re-open the document and for each page:
   - Render to pixmap: `pix = page.get_pixmap(dpi=300)`
   - Convert to PIL Image: `Image.frombytes("RGB", (pix.width, pix.height), pix.samples)`
   - Run pytesseract: `pytesseract.image_to_string(image, lang="lav+eng")`
   - Collect non-empty page texts
3. Log `knowledge.extraction.ocr_fallback` with page count and source type
4. Return a tuple `(text, ocr_applied)` instead of just `text`

Update the `extract_text()` function signature to return `tuple[str, bool]`:
- Change return type to `tuple[str, bool]`
- For the PDF extractor, call `_extract_pdf_sync()` which now returns `(text, ocr_applied)`
- For all other extractors, wrap their result: `return (text, False)`

Update `_extract_pdf_sync()` return type to `tuple[str, bool]`.

The `extractors` dict type needs to change. Since only PDF returns a tuple, handle this by:
- Keeping `_extract_pdf_sync` separate from the dict
- Check `if source_type == "pdf"` first, call `_extract_pdf_sync` directly and return its tuple
- For all other types, use the dict as before and return `(text, False)`

Required lazy imports inside `_extract_pdf_sync` (keep existing `import fitz` pattern):
- `import pytesseract` (already lazy-imported in `_extract_image_sync`)
- `from PIL import Image` (already lazy-imported in `_extract_image_sync`)

**Per-task validation:**
- `uv run ruff format app/knowledge/processing.py`
- `uv run ruff check --fix app/knowledge/processing.py`
- `uv run mypy app/knowledge/processing.py`
- `uv run pyright app/knowledge/processing.py`

---

### Task 6: Update Service to Use OCR Result and Handle Tags
**File:** `app/knowledge/service.py` (modify existing)
**Action:** UPDATE

1. **Update `ingest_document()` method:**
   - Change the `extract_text` call (line 120) to unpack the tuple: `text, ocr_applied = await processing.extract_text(file_path, source_type)`
   - After `create_document()`, set `ocr_applied` on the document: add `ocr_applied` to the `create_document` repository call
   - Log `knowledge.ingest.ocr_applied` if `ocr_applied is True`

2. **Add tag management methods to `KnowledgeService`:**
   - `async def list_tags(self) -> TagListResponse` — return all tags sorted by name
   - `async def create_tag(self, data: TagCreate) -> TagResponse` — create new tag, raise on duplicate
   - `async def delete_tag(self, tag_id: int) -> None` — delete tag (CASCADE removes document associations)
   - `async def add_tags_to_document(self, document_id: int, tag_ids: list[int]) -> DocumentResponse` — add tags to document
   - `async def remove_tag_from_document(self, document_id: int, tag_id: int) -> DocumentResponse` — remove single tag from document

3. **Add auto-tagging method (called during ingestion if enabled):**
   - `async def _auto_tag_document(self, document_id: int, text: str) -> None`
   - Check `settings.auto_tag_enabled`; if False, return immediately
   - Truncate text to `settings.auto_tag_max_chars` characters
   - Use `pydantic_ai.Agent` with a simple prompt: "Classify this document. Return 1-3 short tags as a JSON array of strings. Tags should be lowercase single words. Document text: {text}"
   - Parse the JSON array from the LLM response
   - For each tag, find or create in DB, then link to document
   - Wrap entire method in try/except — log warning on failure, never raise (best-effort)
   - Log `knowledge.autotag.completed` with tag count, or `knowledge.autotag.failed`

4. **Call auto-tagging in `ingest_document()` after successful embedding/storage** (before the final status update):
   ```python
   # Auto-tag (best-effort, non-blocking)
   await self._auto_tag_document(doc.id, text)
   ```

5. **Update `list_documents()` to support tag filtering:**
   - Add optional `tag: str | None = None` parameter
   - If provided, join through `document_tags` and `tags` to filter

Required new imports in service.py:
- `from app.knowledge.schemas import TagCreate, TagListResponse, TagResponse`

**Per-task validation:**
- `uv run ruff format app/knowledge/service.py`
- `uv run ruff check --fix app/knowledge/service.py`
- `uv run mypy app/knowledge/service.py`
- `uv run pyright app/knowledge/service.py`

---

### Task 7: Add Tag Repository Methods
**File:** `app/knowledge/repository.py` (modify existing)
**Action:** UPDATE

Add these methods to `KnowledgeRepository`:

1. `async def list_tags(self) -> list[Tag]` — `SELECT * FROM tags ORDER BY name`
2. `async def get_tag_by_name(self, name: str) -> Tag | None` — lookup by name
3. `async def create_tag(self, name: str) -> Tag` — insert new tag, commit, refresh, return
4. `async def delete_tag(self, tag_id: int) -> bool` — delete by ID, return True if found
5. `async def get_or_create_tag(self, name: str) -> Tag` — find existing or create new
6. `async def add_tags_to_document(self, document_id: int, tag_ids: list[int]) -> None` — INSERT INTO document_tags for each tag_id (use `INSERT ... ON CONFLICT DO NOTHING` pattern)
7. `async def remove_tag_from_document(self, document_id: int, tag_id: int) -> None` — DELETE FROM document_tags WHERE document_id=X AND tag_id=Y
8. `async def get_tags_for_document(self, document_id: int) -> list[Tag]` — JOIN document_tags and tags, ordered by name

Required imports to add:
- `from app.knowledge.models import Document, DocumentChunk, Tag, document_tags`

Update `list_documents()` to accept optional `tag: str | None = None` parameter. When provided, add a subquery join:
```python
if tag:
    query = query.join(document_tags, Document.id == document_tags.c.document_id)
    query = query.join(Tag, document_tags.c.tag_id == Tag.id)
    query = query.where(Tag.name == tag)
```

Also update `count_documents()` with the same optional `tag` filter.

**Per-task validation:**
- `uv run ruff format app/knowledge/repository.py`
- `uv run ruff check --fix app/knowledge/repository.py`
- `uv run mypy app/knowledge/repository.py`
- `uv run pyright app/knowledge/repository.py`

---

### Task 8: Add Tag Routes and Update Document List Filter
**File:** `app/knowledge/routes.py` (modify existing)
**Action:** UPDATE

Add 4 new tag endpoints and update the list endpoint:

1. **`GET /api/v1/knowledge/tags`** — List all tags
   - Auth: `get_current_user` (any authenticated user)
   - Rate limit: `30/minute`
   - Returns: `TagListResponse`

2. **`POST /api/v1/knowledge/tags`** — Create a tag
   - Auth: `require_role("admin", "editor")`
   - Rate limit: `10/minute`
   - Body: `TagCreate`
   - Returns: `TagResponse` with status 201
   - Handle duplicate name: return 409 Conflict

3. **`DELETE /api/v1/knowledge/tags/{tag_id}`** — Delete a tag
   - Auth: `require_role("admin", "editor")`
   - Rate limit: `10/minute`
   - Returns: 204 No Content
   - Handle not found: return 404

4. **`POST /api/v1/knowledge/documents/{document_id}/tags`** — Add tags to document
   - Auth: `require_role("admin", "editor")`
   - Rate limit: `10/minute`
   - Body: `DocumentTagRequest`
   - Returns: `DocumentResponse`

5. **`DELETE /api/v1/knowledge/documents/{document_id}/tags/{tag_id}`** — Remove tag from document
   - Auth: `require_role("admin", "editor")`
   - Rate limit: `10/minute`
   - Returns: `DocumentResponse`

6. **Update `list_documents` endpoint** to accept optional `tag` query parameter:
   - Add `tag: str | None = Query(None, max_length=100)` parameter
   - Pass to `service.list_documents(..., tag=tag)`

Required new imports:
- `from app.knowledge.schemas import DocumentTagRequest, TagCreate, TagListResponse, TagResponse`

Follow the existing endpoint pattern from `list_domains()` (lines 224-233) for the GET endpoint, and `delete_document()` (lines 211-221) for the DELETE endpoint.

**Per-task validation:**
- `uv run ruff format app/knowledge/routes.py`
- `uv run ruff check --fix app/knowledge/routes.py`
- `uv run mypy app/knowledge/routes.py`
- `uv run pyright app/knowledge/routes.py`

---

### Task 9: Update create_document Repository Method
**File:** `app/knowledge/repository.py` (modify existing)
**Action:** UPDATE

Update `create_document()` to accept `ocr_applied: bool = False` parameter and pass it to the `Document()` constructor.

**Per-task validation:**
- `uv run ruff format app/knowledge/repository.py`
- `uv run ruff check --fix app/knowledge/repository.py`
- `uv run mypy app/knowledge/repository.py`

---

### Task 10: Update Existing Test Helpers for New Fields
**File:** `app/knowledge/tests/test_routes.py` (modify existing)
**Action:** UPDATE

Update `_make_doc_response()` helper (line 63-82) to include new fields:
- Add `"ocr_applied": False` to the defaults dict
- Add `"tags": []` to the defaults dict

This prevents all 14 existing route tests from breaking due to missing fields in `DocumentResponse`.

**Per-task validation:**
- `uv run ruff format app/knowledge/tests/test_routes.py`
- `uv run ruff check --fix app/knowledge/tests/test_routes.py`
- `uv run pytest app/knowledge/tests/test_routes.py -v`

---

### Task 11: Add OCR Processing Tests
**File:** `app/knowledge/tests/test_processing.py` (modify existing)
**Action:** UPDATE

Add these tests:

**Test 1: PDF OCR fallback on scanned document**
```python
async def test_extract_pdf_ocr_fallback():
    """Scanned PDFs with no extractable text should trigger OCR."""
    # Mock _extract_pdf_sync to return ("OCR text from pages", True)
    with patch("app.knowledge.processing._extract_pdf_sync") as mock_fn:
        mock_fn.return_value = ("OCR extracted text", True)
        text, ocr_applied = await extract_text("/tmp/scanned.pdf", "pdf")
    assert "OCR extracted text" in text
    assert ocr_applied is True
```

**Test 2: Non-scanned PDF returns ocr_applied=False**
```python
async def test_extract_pdf_no_ocr_needed():
    """PDFs with extractable text should not trigger OCR."""
    with patch("app.knowledge.processing._extract_pdf_sync") as mock_fn:
        mock_fn.return_value = ("Normal PDF text", False)
        text, ocr_applied = await extract_text("/tmp/normal.pdf", "pdf")
    assert "Normal PDF text" in text
    assert ocr_applied is False
```

**Test 3: Non-PDF extractors return ocr_applied=False**
```python
async def test_non_pdf_returns_no_ocr():
    """Non-PDF extractors should always return ocr_applied=False."""
    with patch("app.knowledge.processing._extract_text_sync") as mock_fn:
        mock_fn.return_value = "Plain text content"
        text, ocr_applied = await extract_text("/tmp/test.txt", "text")
    assert ocr_applied is False
```

**Update existing tests:** All 6 existing tests call `extract_text()` and expect a string return. Update them to unpack the tuple `(text, ocr_applied)` instead of just `text`.

**Per-task validation:**
- `uv run ruff format app/knowledge/tests/test_processing.py`
- `uv run ruff check --fix app/knowledge/tests/test_processing.py`
- `uv run pytest app/knowledge/tests/test_processing.py -v`

---

### Task 12: Add Tag CRUD Tests
**File:** `app/knowledge/tests/test_tags.py` (create new)
**Action:** CREATE

Add route-level tests following the pattern from `test_routes.py`:

**Test 1: List tags — empty**
```python
def test_list_tags_empty():
    """GET /tags with no tags should return empty list."""
```

**Test 2: Create tag — success**
```python
def test_create_tag_success():
    """POST /tags should create tag and return 201."""
```

**Test 3: Create tag — duplicate returns 409**
```python
def test_create_tag_duplicate():
    """POST /tags with existing name should return 409 Conflict."""
```

**Test 4: Delete tag — success**
```python
def test_delete_tag_success():
    """DELETE /tags/{id} should return 204."""
```

**Test 5: Delete tag — not found**
```python
def test_delete_tag_not_found():
    """DELETE /tags/{id} for missing tag should return 404."""
```

**Test 6: Add tags to document**
```python
def test_add_tags_to_document():
    """POST /documents/{id}/tags should add tags and return updated document."""
```

**Test 7: Remove tag from document**
```python
def test_remove_tag_from_document():
    """DELETE /documents/{id}/tags/{tag_id} should remove tag."""
```

**Test 8: List documents filtered by tag**
```python
def test_list_documents_by_tag():
    """GET /documents?tag=transit should filter by tag."""
```

Use the same test helpers (`_client()`, `_mock_service()`, `_mock_admin_user()`, `_setup_auth_override()`) from `test_routes.py`. Import them or duplicate the minimal set needed.

**Per-task validation:**
- `uv run ruff format app/knowledge/tests/test_tags.py`
- `uv run ruff check --fix app/knowledge/tests/test_tags.py`
- `uv run pytest app/knowledge/tests/test_tags.py -v`

---

### Task 13: Add Auto-Tagging Service Tests
**File:** `app/knowledge/tests/test_autotag.py` (create new)
**Action:** CREATE

Test the `_auto_tag_document` method:

**Test 1: Auto-tagging disabled**
```python
async def test_auto_tag_disabled():
    """When auto_tag_enabled=False, no LLM call should be made."""
```

**Test 2: Auto-tagging success**
```python
async def test_auto_tag_success():
    """Successful LLM call should create and link tags."""
```

**Test 3: Auto-tagging LLM failure**
```python
async def test_auto_tag_llm_failure():
    """LLM failure should log warning but not raise."""
```

**Test 4: Auto-tagging invalid JSON response**
```python
async def test_auto_tag_invalid_response():
    """Non-JSON LLM response should be handled gracefully."""
```

Mock the LLM agent call and settings. Verify that:
- When disabled, no LLM call is made
- When enabled, tags are created and linked
- On failure, no exception propagates (best-effort)

**Per-task validation:**
- `uv run ruff format app/knowledge/tests/test_autotag.py`
- `uv run ruff check --fix app/knowledge/tests/test_autotag.py`
- `uv run pytest app/knowledge/tests/test_autotag.py -v`

---

## Migration

**Prefer autogenerate when database is running:**
```bash
uv run alembic revision --autogenerate -m "add_tags_and_ocr_to_documents"
uv run alembic upgrade head
```

**When database may not be running:** Manual migration is an acceptable fallback. Column specs:
- `documents.ocr_applied`: `Boolean`, NOT NULL, server_default=`sa.text("false")`
- `tags.id`: `Integer`, primary_key=True, autoincrement=True
- `tags.name`: `String(100)`, NOT NULL, unique=True
- `tags.created_at`: `DateTime`, NOT NULL, server_default=`sa.text("now()")`
- `tags.updated_at`: `DateTime`, NOT NULL, server_default=`sa.text("now()")`
- `document_tags.document_id`: `Integer`, ForeignKey("documents.id", ondelete="CASCADE"), NOT NULL
- `document_tags.tag_id`: `Integer`, ForeignKey("tags.id", ondelete="CASCADE"), NOT NULL
- PrimaryKeyConstraint on ("document_id", "tag_id")

## Logging Events

- `knowledge.extraction.ocr_fallback` — PDF had no extractable text, falling back to OCR
- `knowledge.extraction.ocr_completed` — OCR completed with char count
- `knowledge.ingest.ocr_applied` — Document was ingested using OCR
- `knowledge.autotag.started` — Auto-tagging LLM call initiated
- `knowledge.autotag.completed` — Auto-tagging succeeded with tag count
- `knowledge.autotag.failed` — Auto-tagging LLM call failed (warning, not error)
- `knowledge.tag.created` — New tag created
- `knowledge.tag.deleted` — Tag deleted
- `knowledge.document.tags_updated` — Tags added/removed from document

## Testing Strategy

### Unit Tests
**Location:** `app/knowledge/tests/`

- `test_processing.py` — OCR fallback detection, tuple return contract, all existing tests updated
- `test_tags.py` — Tag CRUD routes, document tagging, tag filtering on list
- `test_autotag.py` — Auto-tagging enable/disable, success/failure, JSON parsing

### Integration Tests
**Location:** `app/knowledge/tests/`
**Mark with:** `@pytest.mark.integration`

- Tag creation + document association via repository (requires DB)
- OCR on actual scanned PDF (requires Tesseract installed)

### Edge Cases
- Scanned PDF with mixed pages (some text, some scanned) — should extract both
- Empty PDF (0 pages) — should return empty text with ocr_applied=False
- Tag name normalization (whitespace, casing) — "  Transit " → "transit"
- Duplicate tag creation — should return 409 Conflict
- Removing a tag that doesn't exist on a document — should not error
- Auto-tagging with LLM returning non-JSON — should not crash
- Auto-tagging with LLM returning too many tags — should cap at configured limit

## Acceptance Criteria

This feature is complete when:
- [ ] Scanned PDFs are detected and OCR'd automatically using pytesseract
- [ ] `ocr_applied` boolean is stored on documents and returned in API responses
- [ ] Tag CRUD endpoints work (list, create, delete)
- [ ] Documents can be tagged and untagged via API
- [ ] Document list can be filtered by tag
- [ ] LLM auto-tagging runs on upload when enabled (best-effort, non-blocking)
- [ ] All type checkers pass (mypy + pyright)
- [ ] All tests pass (unit + integration)
- [ ] Structured logging follows `domain.component.action_state` pattern
- [ ] No type suppressions added (except existing ones)
- [ ] No regressions in existing 54 knowledge base tests
- [ ] `DocumentResponse` includes `tags` and `ocr_applied` fields

## Completion Checklist

Before marking this plan as fully executed:
- [ ] All 13 tasks completed in order
- [ ] Per-task validations passed
- [ ] Full validation pyramid passed (Levels 1-4)
- [ ] No deviations from plan (or deviations documented with reasons)
- [ ] Ready for `/commit`

## Final Validation (5-Level Pyramid)

Run each level in order — every one must pass with 0 errors:

**Level 1: Syntax & Style**
```bash
uv run ruff format .
uv run ruff check --fix .
```

**Level 2: Type Safety**
```bash
uv run mypy app/
uv run pyright app/
```

**Level 3: Unit Tests (feature-specific)**
```bash
uv run pytest app/knowledge/tests/ -v
```

**Level 4: Full Test Suite (unit)**
```bash
uv run pytest -v -m "not integration"
```

**Level 5: Server Validation (if Docker running)**
```bash
curl -s http://localhost:8123/health
```

**Success definition:** Levels 1-4 exit code 0, all tests pass, zero errors or warnings. Level 5 optional.

## Dependencies

- Shared utilities used: `TimestampMixin`, `PaginatedResponse`, `PaginationParams`, `get_db()`, `get_logger()`, `AppError`, `NotFoundError`
- Core modules used: `app.core.config.Settings`, `app.core.database.Base`, `app.core.rate_limit.limiter`
- New dependencies: None — `pytesseract`, `pillow`, `pymupdf`, `pydantic-ai` all already installed
- New env vars: `AUTO_TAG_ENABLED=false` (optional, defaults to false), `AUTO_TAG_MAX_CHARS=500` (optional)

## Known Pitfalls

The executing agent MUST follow all 59 Python anti-pattern rules from `@_shared/python-anti-patterns.md`.

Key rules especially relevant to this plan:
- **Rule 11:** `DocumentResponse` field additions — grep for all constructors and update them (Task 10)
- **Rule 29:** Adding `tags` and `ocr_applied` to `DocumentResponse` — all test helpers must be updated
- **Rule 39:** `from datetime import date` shadows — use `import datetime` and `datetime.date` if needed
- **Rule 41:** ILIKE search on tag names — use `escape_like()` if adding search
- **Rule 52:** Empty PATCH bodies rejected — tag operations use separate schemas, not PATCH
- **Rule 55:** `HTTPBearer(auto_error=False)` — all new endpoints must use `get_current_user` or `require_role()` which already handle this correctly

**OCR-specific pitfalls:**
- PyMuPDF's `page.get_pixmap(dpi=300)` can be memory-intensive for large documents — consider limiting to first 50 pages
- Tesseract may not be installed in all environments — wrap OCR in try/except with a clear warning log
- `pix.samples` returns raw bytes; must specify `"RGB"` mode and `(pix.width, pix.height)` dimensions for PIL

**Auto-tagging pitfalls:**
- LLM response may not be valid JSON — always parse defensively with try/except
- LLM may return tags with uppercase, spaces, or special chars — normalize before storing
- Auto-tagging should NEVER block the upload response — wrap in try/except, log warning on failure
- The LLM call needs a fresh agent instance, not the main chat agent — use a simple `Agent('provider:model')` with a classification prompt

## Notes

- **Frontend impact:** The `DocumentResponse` now includes `tags: list[TagResponse]` and `ocr_applied: bool`. The frontend SDK will need regeneration to pick up these new response fields. The existing document list/detail UI will work but won't display tags until frontend components are updated (out of scope for this plan).
- **Performance:** OCR adds ~2-5 seconds per page at 300 DPI. For large scanned PDFs (50+ pages), this could take 2-4 minutes. Consider adding a progress indicator in a future enhancement.
- **Auto-tagging cost:** Using Claude Haiku or similar small model, ~$0.001 per document classification (500 chars input, ~50 chars output).

## Pre-Implementation Checklist

The executing agent MUST verify before writing any code:
- [ ] Read all files listed in "Relevant Files" section
- [ ] Understood the OCR fallback logic in `_extract_pdf_sync()`
- [ ] Understood the `ingest_document()` pipeline in service.py
- [ ] Verified `pytesseract` and `pillow` are in dependencies
- [ ] Understood tag endpoint patterns from existing routes
- [ ] Clear on task execution order (models → schemas → migration → processing → service → repository → routes → tests)
- [ ] Validation commands are executable in this environment
