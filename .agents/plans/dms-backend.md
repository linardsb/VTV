# Plan: DMS Backend — Knowledge Base Enhancements

## Feature Metadata
**Feature Type**: Enhancement (extends existing `app/knowledge/` module)
**Estimated Complexity**: Medium
**Primary Systems Affected**: `app/knowledge/`, `app/core/config.py`, `pyproject.toml`
**Companion Plan**: `.agents/plans/dms-frontend.md` (execute AFTER this plan completes)

## Feature Description

The VTV knowledge base currently supports document upload and RAG search, but only via REST API — unusable by non-technical dispatch staff. This plan enhances the backend with file persistence, metadata editing, Excel/CSV extraction, and new API endpoints needed by the frontend DMS page.

The backend enhancements extend the existing `app/knowledge/` vertical slice (NOT a new feature directory) with: file storage on local disk, document metadata update (PATCH), file download endpoint, document content/chunks endpoint, domain listing endpoint, and Excel/CSV text extraction via `openpyxl`. The Document model gains `title`, `description`, and `file_path` columns.

## User Story

As a **dispatcher or administrator** using the VTV CMS,
I want to **upload, browse, and manage documents through a web interface**
So that **the knowledge base is populated with operational documents (SOPs, schedules, regulations) without needing API tools or developer assistance**.

## Solution Approach

We extend the existing `app/knowledge/` module rather than creating a new `app/dms/` feature slice because:
- The `Document` and `DocumentChunk` models already exist in `app/knowledge/models.py`
- The upload/ingestion pipeline already exists in `app/knowledge/service.py`
- The REST endpoints already exist at `/api/v1/knowledge/documents`
- Adding a parallel module would create cross-feature write dependencies (violating VSA)

**Approach Decision:**
We chose extending `app/knowledge/` because:
- All document-related database models live there already
- The ingestion pipeline (extract -> chunk -> embed -> store) is already implemented
- Adding new endpoints to the existing router preserves a single source of truth

**Alternatives Considered:**
- New `app/dms/` feature slice: Rejected because it would need to write to `documents` and `document_chunks` tables owned by `app/knowledge/`, violating the VSA "never write to another feature's tables" rule.

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, logging patterns, type checking requirements
- `app/knowledge/models.py` — Current Document and DocumentChunk SQLAlchemy models
- `app/knowledge/schemas.py` — Current Pydantic schemas (DocumentUpload, DocumentResponse, SearchRequest/Response)
- `app/knowledge/routes.py` — Current 5 REST endpoints at `/api/v1/knowledge`
- `app/knowledge/service.py` — Ingestion pipeline and search logic
- `app/knowledge/repository.py` — Database operations (CRUD + vector/fulltext search)
- `app/knowledge/processing.py` — Text extraction (PDF, DOCX, email, image, text)
- `app/knowledge/exceptions.py` — Knowledge-specific exception hierarchy

### Similar Features (Examples to Follow)
- `app/stops/routes.py` — CRUD route pattern with rate limiting, Depends injection, pyright directives
- `app/stops/schemas.py` — Base/Create/Update/Response schema hierarchy pattern
- `app/stops/service.py` — Service layer with structured logging pattern
- `app/stops/repository.py` — Repository with list/count/create/update/delete pattern

### Files to Modify
- `app/knowledge/models.py` — Add title, description, file_path columns to Document
- `app/knowledge/schemas.py` — Add DocumentUpdate, enhance DocumentResponse, add DocumentContentResponse
- `app/knowledge/repository.py` — Add update_document, get_chunks_by_document, list_domains methods
- `app/knowledge/service.py` — Add file storage, document update, content retrieval, domain listing
- `app/knowledge/routes.py` — Add PATCH, download, content, domains endpoints
- `app/knowledge/processing.py` — Add Excel/CSV extraction
- `app/core/config.py` — Add DOCUMENT_STORAGE_PATH setting
- `pyproject.toml` — Add openpyxl dependency
- `.env.example` — Add DOCUMENT_STORAGE_PATH
- `app/main.py` — No changes needed (knowledge router already registered)

## Implementation Plan

### Phase 1: Foundation (Tasks 1-5)
Add openpyxl dependency, extend Document model with new columns, create migration, update schemas, add Excel/CSV extraction.

### Phase 2: Endpoints & Tests (Tasks 6-10)
Extend repository, service, and routes with update, download, content preview, and domain listing capabilities. Add file persistence to the upload flow. Write backend tests.

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.

---

### Task 1: Add openpyxl Dependency
**File:** `pyproject.toml` (modify existing)
**Action:** UPDATE

Add `openpyxl` to the project dependencies for Excel file reading:
- Add `"openpyxl>=3.1.5"` to the `dependencies` array
- Add mypy override for `openpyxl.*` with `ignore_missing_imports = true` (openpyxl lacks py.typed)

Then run: `uv sync`

**Per-task validation:**
- `uv sync` completes without errors
- `uv run python -c "import openpyxl; print(openpyxl.__version__)"` prints version

---

### Task 2: Update Document Model
**File:** `app/knowledge/models.py` (modify existing)
**Action:** UPDATE

Add three new columns to the `Document` model:
- `title: Mapped[str | None]` — `String(200)`, nullable. Human-readable title; defaults to filename if not provided.
- `description: Mapped[str | None]` — `Text`, nullable. Optional description of the document.
- `file_path: Mapped[str | None]` — `String(500)`, nullable. Filesystem path to stored original file. Null for legacy documents uploaded before DMS.

Place new columns after `filename` and before `domain`. All three are nullable to preserve backward compatibility with existing documents that lack these fields.

Do NOT modify `DocumentChunk` — it remains unchanged.

**Per-task validation:**
- `uv run ruff format app/knowledge/models.py`
- `uv run ruff check --fix app/knowledge/models.py` passes
- `uv run mypy app/knowledge/models.py` passes
- `uv run pyright app/knowledge/models.py` passes

---

### Task 3: Create Database Migration
**Action:** RUN COMMAND

Generate and review the migration:
```bash
uv run alembic revision --autogenerate -m "add title description file_path to documents"
```

Review the generated migration file in `alembic/versions/`. It should contain:
- `op.add_column('documents', sa.Column('title', sa.String(200), nullable=True))`
- `op.add_column('documents', sa.Column('description', sa.Text(), nullable=True))`
- `op.add_column('documents', sa.Column('file_path', sa.String(500), nullable=True))`

The downgrade should drop these three columns. Do NOT apply the migration yet (Docker DB may not be running).

**Per-task validation:**
- Migration file generated in `alembic/versions/`
- `uv run ruff format alembic/versions/*.py`
- `uv run ruff check --fix alembic/versions/*.py` passes

---

### Task 4: Update Pydantic Schemas
**File:** `app/knowledge/schemas.py` (modify existing)
**Action:** UPDATE

Add/modify these schemas:

**Add `DocumentUpdate` schema** (new — for PATCH endpoint):
```python
class DocumentUpdate(BaseModel):
    title: str | None = None          # max_length=200
    description: str | None = None
    domain: str | None = None         # min_length=1, max_length=50
    language: str | None = None       # pattern="^(lv|en)$"
```
All fields optional (PATCH semantics — only update provided fields).

**Update `DocumentUpload`** — add optional fields:
- `title: str | None = None` — max_length=200
- `description: str | None = None`

**Update `DocumentResponse`** — add new fields:
- `title: str | None` — after filename
- `description: str | None`
- `file_path: str | None`
- `has_file: bool` — computed property: True if file_path is not None. Use `@computed_field` from Pydantic.

**Add `DocumentChunkResponse` schema** (new — for content endpoint):
```python
class DocumentChunkResponse(BaseModel):
    chunk_index: int
    content: str
    model_config = ConfigDict(from_attributes=True)
```

**Add `DocumentContentResponse` schema** (new — wraps chunks):
```python
class DocumentContentResponse(BaseModel):
    document_id: int
    filename: str
    title: str | None
    total_chunks: int
    chunks: list[DocumentChunkResponse]
```

**Add `DomainListResponse` schema** (new — for domains endpoint):
```python
class DomainListResponse(BaseModel):
    domains: list[str]
    total: int
```

**Per-task validation:**
- `uv run ruff format app/knowledge/schemas.py`
- `uv run ruff check --fix app/knowledge/schemas.py` passes
- `uv run mypy app/knowledge/schemas.py` passes
- `uv run pyright app/knowledge/schemas.py` passes

---

### Task 5: Add Excel/CSV Extraction
**File:** `app/knowledge/processing.py` (modify existing)
**Action:** UPDATE

Add two new extraction functions:

**`_extract_excel_sync(file_path: str) -> str`:**
- Import `openpyxl` at function scope (lazy import, not top-level) to match the pattern of other extractors
- `wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)`
- Iterate sheets, iterate rows, join cell values with tab separators
- Join rows with newlines, join sheets with `"\n\n--- Sheet: {name} ---\n\n"`
- Close workbook after reading
- Pyright directive at file top: add `reportUnknownMemberType=false` (openpyxl is untyped)

**`_extract_csv_sync(file_path: str) -> str`:**
- Use stdlib `csv` module (already available, no new import needed)
- `csv.reader(open(file_path, encoding="utf-8"))`
- Join cells with tab, rows with newline
- Handle `csv.Error` gracefully (fall back to plain text read)

**Update `extract_text` dispatcher:**
- Add `"xlsx"` -> `_extract_excel_sync`
- Add `"csv"` -> `_extract_csv_sync`

**Update `_detect_source_type` in routes.py:**
- Add `"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"` -> `"xlsx"`
- Add `"text/csv"` -> `"csv"` (currently falls through to `"text"` — make it explicit)

**Per-task validation:**
- `uv run ruff format app/knowledge/processing.py`
- `uv run ruff check --fix app/knowledge/processing.py` passes
- `uv run mypy app/knowledge/processing.py` passes
- `uv run pyright app/knowledge/processing.py` passes

---

### Task 6: Extend Repository
**File:** `app/knowledge/repository.py` (modify existing)
**Action:** UPDATE

Add these new methods to `KnowledgeRepository`:

**`async def update_document(self, document_id: int, *, title: str | None = ..., description: str | None = ..., domain: str | None = ..., language: str | None = ...) -> Document | None`:**
- Use `select(Document).where(Document.id == document_id)` to fetch
- Apply only non-None fields via `setattr`
- `await self.db.commit()` + `await self.db.refresh(doc)`
- Return updated Document or None if not found
- Pattern: mirror `app/stops/repository.py` update method but with explicit kwargs instead of schema

**`async def get_chunks_by_document(self, document_id: int) -> list[DocumentChunk]`:**
- `select(DocumentChunk).where(DocumentChunk.document_id == document_id).order_by(DocumentChunk.chunk_index)`
- Return `list(result.scalars().all())`

**`async def list_domains(self) -> list[str]`:**
- `select(distinct(Document.domain)).order_by(Document.domain)`
- Return sorted list of unique domain strings

**`async def update_document_file_path(self, document_id: int, file_path: str) -> None`:**
- Fetch document, set `file_path`, commit

**Update `list_documents`** — add optional `language: str | None = None` filter parameter.

**Per-task validation:**
- `uv run ruff format app/knowledge/repository.py`
- `uv run ruff check --fix app/knowledge/repository.py` passes
- `uv run mypy app/knowledge/repository.py` passes
- `uv run pyright app/knowledge/repository.py` passes

---

### Task 7: Add Document Storage Path Config
**File:** `app/core/config.py` (modify existing)
**Action:** UPDATE

Add to the `Settings` class:
```python
document_storage_path: str = "data/documents"
```

**File:** `.env.example` (modify existing)
**Action:** UPDATE

Add:
```
# Document storage
DOCUMENT_STORAGE_PATH=data/documents
```

**Per-task validation:**
- `uv run ruff format app/core/config.py`
- `uv run ruff check --fix app/core/config.py` passes
- `uv run mypy app/core/config.py` passes

---

### Task 8: Enhance Service Layer
**File:** `app/knowledge/service.py` (modify existing)
**Action:** UPDATE

**Add file storage to `ingest_document`:**
After successful text extraction (step 2 in current pipeline), BEFORE deleting the temp file:
1. `storage_dir = Path(settings.document_storage_path) / str(doc.id)`
2. `storage_dir.mkdir(parents=True, exist_ok=True)`
3. `stored_path = storage_dir / filename`
4. Copy temp file to `stored_path` using `shutil.copy2`
5. Update document record: `repository.update_document_file_path(doc.id, str(stored_path))`
6. If title was provided in upload, set it; otherwise default to filename stem

**Add `update_document` method:**
```python
async def update_document(self, document_id: int, data: DocumentUpdate) -> DocumentResponse:
```
- Validate document exists (raise `DocumentNotFoundError` if not)
- Call `repository.update_document(document_id, **data.model_dump(exclude_unset=True))`
- Return `DocumentResponse.model_validate(updated_doc)`
- Log: `knowledge.document.update_started`, `knowledge.document.update_completed`

**Add `get_document_content` method:**
```python
async def get_document_content(self, document_id: int) -> DocumentContentResponse:
```
- Fetch document (raise `DocumentNotFoundError` if not found)
- Fetch chunks via `repository.get_chunks_by_document(document_id)`
- Return `DocumentContentResponse` with document metadata and chunk list

**Add `get_document_file_path` method:**
```python
async def get_document_file_path(self, document_id: int) -> tuple[str, str]:
```
- Returns `(file_path, filename)` for the download endpoint
- Raises `DocumentNotFoundError` if document not found
- Raises `ProcessingError` if `file_path` is None (legacy document without stored file)

**Add `list_domains` method:**
```python
async def list_domains(self) -> DomainListResponse:
```
- Calls `repository.list_domains()`
- Returns `DomainListResponse`

**Update `delete_document`:**
- After deleting from DB, also delete the stored file from disk if `file_path` exists
- Use `shutil.rmtree(Path(file_path).parent, ignore_errors=True)` to clean up the `{id}/` directory
- Log: `knowledge.document.file_deleted`

**Per-task validation:**
- `uv run ruff format app/knowledge/service.py`
- `uv run ruff check --fix app/knowledge/service.py` passes
- `uv run mypy app/knowledge/service.py` passes
- `uv run pyright app/knowledge/service.py` passes

---

### Task 9: Add New Backend Routes
**File:** `app/knowledge/routes.py` (modify existing)
**Action:** UPDATE

Add these new endpoints to the existing router (prefix `/api/v1/knowledge`):

**`PATCH /documents/{document_id}`** — Update document metadata:
- Rate limit: `10/minute`
- Request body: `DocumentUpdate`
- Response: `DocumentResponse`
- Status: 200

**`GET /documents/{document_id}/download`** — Download original file:
- Rate limit: `30/minute`
- Response: `FileResponse` (from `fastapi.responses`)
- Sets `Content-Disposition: attachment; filename="{filename}"`
- Returns 404 if document not found, 404 if file not stored (legacy)

**`GET /documents/{document_id}/content`** — Get extracted text chunks:
- Rate limit: `30/minute`
- Response: `DocumentContentResponse`
- Returns all chunks ordered by `chunk_index`

**`GET /domains`** — List all unique domains:
- Rate limit: `30/minute`
- Response: `DomainListResponse`

**Update `POST /documents` upload route:**
- Accept optional `title` and `description` form fields (from updated `DocumentUpload` schema)
- Pass them through to `service.ingest_document`

**Update `_detect_source_type`:**
- Add Excel MIME type mapping
- Add explicit CSV mapping

**Per-task validation:**
- `uv run ruff format app/knowledge/routes.py`
- `uv run ruff check --fix app/knowledge/routes.py` passes
- `uv run mypy app/knowledge/routes.py` passes
- `uv run pyright app/knowledge/routes.py` passes

---

### Task 10: Backend Unit Tests
**File:** `app/knowledge/tests/test_dms.py` (create new)
**Action:** CREATE

Write tests covering the new DMS functionality. Use `unittest.mock.AsyncMock` and `MagicMock` for mocking. Follow the pattern from `app/knowledge/tests/test_processing.py`.

**Test 1: Excel text extraction**
- Mock `openpyxl.load_workbook` to return a workbook with 2 sheets, each with 3 rows
- Assert extracted text contains tab-separated values and sheet headers

**Test 2: CSV text extraction**
- Create a temporary CSV file with `csv.writer`
- Call `_extract_csv_sync` on it
- Assert extracted text contains all rows

**Test 3: Document update service**
- Mock repository to return a Document
- Call `service.update_document(id, DocumentUpdate(title="New Title"))`
- Assert repository.update_document was called with correct args

**Test 4: Document content retrieval**
- Mock repository to return document + 3 chunks
- Call `service.get_document_content(id)`
- Assert response has 3 chunks in correct order

**Test 5: Domain listing**
- Mock repository.list_domains to return `["transit", "hr", "safety"]`
- Assert `DomainListResponse` has 3 domains

**Test 6: File storage on upload**
- Mock the ingestion pipeline
- Assert file is copied to storage path
- Assert document record has `file_path` set

**Test 7: File cleanup on delete**
- Mock document with `file_path` set
- Call `service.delete_document(id)`
- Assert `shutil.rmtree` was called

**Test 8: Download returns path and filename**
- Mock repository to return document with `file_path` set
- Assert `get_document_file_path` returns correct tuple

**Test 9: Download raises for legacy document**
- Mock repository to return document with `file_path = None`
- Assert `ProcessingError` is raised

All test functions must have `-> None` return type annotation.
All mock result lists must have explicit type annotations: `chunks: list[MagicMock] = []`.

**Per-task validation:**
- `uv run ruff format app/knowledge/tests/test_dms.py`
- `uv run ruff check --fix app/knowledge/tests/test_dms.py` passes
- `uv run pytest app/knowledge/tests/test_dms.py -v` — all 9 tests pass

---

## Migration

```bash
uv run alembic revision --autogenerate -m "add title description file_path to documents"
uv run alembic upgrade head
```

New columns are all nullable — zero-downtime migration, existing data is unaffected.

## Logging Events

- `knowledge.document.ingest_started` — existing, enhanced with title field
- `knowledge.document.ingest_completed` — existing, enhanced with file_path
- `knowledge.document.update_started` — NEW: when metadata is patched
- `knowledge.document.update_completed` — NEW: after successful update
- `knowledge.document.file_stored` — NEW: after file copied to storage
- `knowledge.document.file_deleted` — NEW: after stored file removed on delete
- `knowledge.document.content_retrieved` — NEW: when chunks are fetched for preview
- `knowledge.domains.list_completed` — NEW: domain listing

## Testing Strategy

### Backend Unit Tests
**Location:** `app/knowledge/tests/test_dms.py`
- Excel extraction, CSV extraction, document update, content retrieval, domain listing, file storage, file cleanup, download path, legacy document error

### Existing Tests (must still pass)
- `test_processing.py` — 6 tests
- `test_chunking.py` — 6 tests
- `test_embedding.py` — 7 tests

## Acceptance Criteria

- [ ] PATCH `/documents/{id}` updates title, description, domain, language
- [ ] GET `/documents/{id}/download` returns original file
- [ ] GET `/documents/{id}/content` returns extracted text chunks
- [ ] GET `/domains` returns unique domain list
- [ ] Excel (.xlsx) files are extracted to text
- [ ] CSV files are extracted to text
- [ ] Uploaded files are stored on disk at `data/documents/{id}/`
- [ ] Delete removes both DB record and stored file
- [ ] All type checkers pass (mypy + pyright)
- [ ] All tests pass (existing 20 + new 9 = 29)
- [ ] Structured logging follows `domain.component.action_state` pattern

## Final Validation (4-Level Pyramid)

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

**Level 4: Full Test Suite**
```bash
uv run pytest -v -m "not integration"
```

## Dependencies

- **New backend dependency:** `openpyxl>=3.1.5` — add via `uv add openpyxl`
- **New env var:** `DOCUMENT_STORAGE_PATH` (default: `data/documents`)

## Known Pitfalls

1. **No `assert` in production code** — Ruff S101. Use `if x is not None:` conditionals.
2. **No `object` type hints** — Import actual types.
3. **Untyped libraries (openpyxl)** — mypy override added in Task 1. For pyright, add file-level `# pyright: reportUnknownMemberType=false` to `processing.py`.
4. **Mock exceptions must match catch blocks** — Mock exact exception types.
5. **No unused imports or variables** — Ruff F401/F841.
6. **No EN DASH in strings** — Use HYPHEN-MINUS `-` (U+002D) everywhere.
7. **Test helper functions need `-> ReturnType`** — Always add return type.
8. **`request: Request` for slowapi routes** — Add `_ = request` to suppress ARG001.
9. **Bare `[]` list literals need type annotation** — `items: list[MagicMock] = []` not `items = []`.
10. **Pydantic `ConfigDict(from_attributes=True)`** — Required on all response schemas mapping from ORM.
11. **`str()` wrapping for untyped lib returns** — `str(cell.value)` for openpyxl cells.
12. **Partially annotated test functions need `-> None`**.
13. **`shutil` operations need error handling** — `shutil.rmtree(path, ignore_errors=True)`.
14. **`FileResponse` requires absolute path** — Use `Path.resolve()`.

## Pre-Implementation Checklist

- [ ] Read all files listed in "Relevant Files" section
- [ ] Understood that this extends `app/knowledge/`, NOT a new feature directory
- [ ] Confirmed `openpyxl` is not already installed
- [ ] Confirmed `python-multipart` is available (required for UploadFile)
- [ ] Understood the Document model's current column layout
