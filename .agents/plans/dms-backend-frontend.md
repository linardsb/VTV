# Plan: Document Management System (DMS) — Backend + Frontend

## Feature Metadata
**Feature Type**: Enhancement (extends existing `app/knowledge/` module) + New Frontend Page
**Estimated Complexity**: High (backend enhancements + full new CMS page)
**Primary Systems Affected**: `app/knowledge/`, `cms/apps/web/`, `app/core/config.py`, `pyproject.toml`

## Feature Description

The VTV knowledge base currently supports document upload and RAG search, but only via REST API — unusable by non-technical dispatch staff. This feature adds a complete Document Management System UI to the CMS and enhances the backend with file persistence, metadata editing, Excel/CSV extraction, and a document content preview API.

The backend enhancements extend the existing `app/knowledge/` vertical slice (NOT a new feature directory) with: file storage on local disk, document metadata update (PATCH), file download endpoint, document content/chunks endpoint, domain listing endpoint, and Excel/CSV text extraction via `openpyxl`. The Document model gains `title`, `description`, and `file_path` columns.

The frontend creates a new `/documents` page in the CMS with a filterable document table, drag-and-drop upload form, document detail panel with chunk preview, and delete confirmation dialog. It follows the exact patterns established by the routes page (the most complex existing page).

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
- No cross-feature data ownership conflicts

**Alternatives Considered:**
- New `app/dms/` feature slice: Rejected because it would need to write to `documents` and `document_chunks` tables owned by `app/knowledge/`, violating the VSA "never write to another feature's tables" rule.
- Separate frontend API proxy: Rejected as over-engineering — the CMS can call the FastAPI knowledge endpoints directly via the existing `NEXT_PUBLIC_AGENT_URL` env var.

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
- `cms/apps/web/src/app/[locale]/(dashboard)/routes/page.tsx` — Most complex page, template for documents page
- `cms/apps/web/src/components/routes/route-table.tsx` — Table component with pagination, sorting, actions
- `cms/apps/web/src/components/routes/route-filters.tsx` — Filter sidebar/sheet dual-mode pattern
- `cms/apps/web/src/components/routes/route-form.tsx` — Sheet-based form pattern
- `cms/apps/web/src/components/routes/route-detail.tsx` — Detail panel with metadata rows
- `cms/apps/web/src/components/routes/delete-route-dialog.tsx` — Delete confirmation dialog pattern
- `cms/apps/web/src/components/app-sidebar.tsx` — Navigation items array structure
- `cms/apps/web/middleware.ts` — RBAC permissions and matcher pattern
- `cms/apps/web/src/lib/agent-client.ts` — API client pattern (BASE_URL, error class, typed fetch)

### Files to Modify
- `app/knowledge/models.py` — Add title, description, file_path columns to Document
- `app/knowledge/schemas.py` — Add DocumentUpdate, enhance DocumentResponse, add DocumentContentResponse
- `app/knowledge/repository.py` — Add update_document, get_chunks_by_document, list_domains methods
- `app/knowledge/service.py` — Add file storage, document update, content retrieval, domain listing
- `app/knowledge/routes.py` — Add PATCH, download, content, domains endpoints
- `app/knowledge/processing.py` — Add Excel/CSV extraction
- `app/core/config.py` — Add DOCUMENT_STORAGE_PATH setting
- `pyproject.toml` — Add openpyxl dependency, add ruff per-file-ignores if needed
- `.env.example` — Add DOCUMENT_STORAGE_PATH
- `app/main.py` — No changes needed (knowledge router already registered)
- `cms/apps/web/src/components/app-sidebar.tsx` — Add documents nav item
- `cms/apps/web/middleware.ts` — Add /documents to RBAC and matcher
- `cms/apps/web/messages/en.json` — Add documents namespace
- `cms/apps/web/messages/lv.json` — Add documents namespace (Latvian)

## Implementation Plan

### Phase 1: Backend Foundation (Tasks 1-5)
Add openpyxl dependency, extend Document model with new columns, create migration, update schemas, add Excel/CSV extraction.

### Phase 2: Backend Endpoints (Tasks 6-10)
Extend repository, service, and routes with update, download, content preview, and domain listing capabilities. Add file persistence to the upload flow. Write backend tests.

### Phase 3: Frontend Foundation (Tasks 11-14)
Install frontend dependencies (react-dropzone, shadcn progress + sonner), create TypeScript types and API client module.

### Phase 4: Frontend Components (Tasks 15-20)
Build all document management components: table, filters, upload form, detail panel, delete dialog.

### Phase 5: Frontend Integration (Tasks 21-25)
Create the documents page, wire up sidebar navigation, RBAC middleware, i18n translations. Final validation.

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
- Keep `.csv` also handled as `"csv"` when content_type is `"text/csv"`

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
- Pattern: mirror `app/stops/repository.py` update method but with explicit kwargs instead of schema (since DocumentUpdate has all optional fields)

**`async def get_chunks_by_document(self, document_id: int) -> list[DocumentChunk]`:**
- `select(DocumentChunk).where(DocumentChunk.document_id == document_id).order_by(DocumentChunk.chunk_index)`
- Return `list(result.scalars().all())`

**`async def list_domains(self) -> list[str]`:**
- `select(distinct(Document.domain)).order_by(Document.domain)`
- Return sorted list of unique domain strings

**Update `list_documents`** — add optional `language: str | None = None` filter parameter (currently only filters by domain and status; add language filter too).

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

This is the base directory where uploaded document files are stored. Structure: `{storage_path}/{document_id}/{filename}`.

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

Add a simple helper to the repository for this:
```python
async def update_document_file_path(self, document_id: int, file_path: str) -> None
```

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
- No auth required (public metadata)

**Update `POST /documents` upload route:**
- Accept optional `title` and `description` form fields (from updated `DocumentUpload` schema)
- Pass them through to `service.ingest_document`

**Update `_detect_source_type`:**
- Add Excel MIME type mapping (from Task 5 notes)
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

### Task 11: Install Frontend Dependencies
**Action:** RUN COMMANDS

```bash
cd /Users/Berzins/Desktop/VTV/cms

# Install react-dropzone for drag-and-drop upload
pnpm --filter @vtv/web add react-dropzone

# Install shadcn progress component (upload progress bar)
cd apps/web && npx shadcn@latest add progress --yes

# Install shadcn sonner component (toast notifications)
npx shadcn@latest add sonner --yes
```

**Per-task validation:**
- `pnpm --filter @vtv/web build` still succeeds (no breaking changes)
- `ls cms/apps/web/src/components/ui/progress.tsx` exists
- `ls cms/apps/web/src/components/ui/sonner.tsx` exists

---

### Task 12: Create Document TypeScript Types
**File:** `cms/apps/web/src/types/document.ts` (create new)
**Action:** CREATE

Define TypeScript types matching the backend schemas:

```typescript
export interface DocumentItem {
  id: number;
  filename: string;
  title: string | null;
  description: string | null;
  domain: string;
  source_type: string;
  language: string;
  file_size_bytes: number | null;
  status: string;
  error_message: string | null;
  chunk_count: number;
  has_file: boolean;
  created_at: string;
  updated_at: string;
}

export interface DocumentChunk {
  chunk_index: number;
  content: string;
}

export interface DocumentContentResponse {
  document_id: number;
  filename: string;
  title: string | null;
  total_chunks: number;
  chunks: DocumentChunk[];
}

export interface PaginatedDocuments {
  items: DocumentItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface DomainList {
  domains: string[];
  total: number;
}

export interface DocumentUploadData {
  file: File;
  domain: string;
  language: string;
  title?: string;
  description?: string;
}

export interface DocumentUpdateData {
  title?: string;
  description?: string;
  domain?: string;
  language?: string;
}
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes

---

### Task 13: Create Documents API Client
**File:** `cms/apps/web/src/lib/documents-client.ts` (create new)
**Action:** CREATE

Follow the pattern from `cms/apps/web/src/lib/agent-client.ts`.

```typescript
const BASE_URL = process.env.NEXT_PUBLIC_AGENT_URL ?? "http://localhost:8123";
const API_PREFIX = "/api/v1/knowledge";
```

**Export these async functions:**

`fetchDocuments(params: { page?: number; page_size?: number; domain?: string; status?: string; language?: string }): Promise<PaginatedDocuments>`
- GET `${API_PREFIX}/documents?${queryString}`

`fetchDocument(id: number): Promise<DocumentItem>`
- GET `${API_PREFIX}/documents/${id}`

`uploadDocument(data: DocumentUploadData): Promise<DocumentItem>`
- POST `${API_PREFIX}/documents` with `FormData` (multipart)
- Append file, domain, language, optional title, optional description

`updateDocument(id: number, data: DocumentUpdateData): Promise<DocumentItem>`
- PATCH `${API_PREFIX}/documents/${id}` with JSON body

`deleteDocument(id: number): Promise<void>`
- DELETE `${API_PREFIX}/documents/${id}`

`fetchDocumentContent(id: number): Promise<DocumentContentResponse>`
- GET `${API_PREFIX}/documents/${id}/content`

`downloadDocument(id: number): Promise<Blob>`
- GET `${API_PREFIX}/documents/${id}/download`
- Return `response.blob()`

`fetchDomains(): Promise<DomainList>`
- GET `${API_PREFIX}/domains`

**Error handling:** Create `DocumentsApiError` class extending `Error` with `status: number` property. Throw on non-ok responses with `response.statusText` message.

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 14: Add Sonner Toaster to Root Layout
**File:** `cms/apps/web/src/app/[locale]/layout.tsx` (modify existing)
**Action:** UPDATE

Add the `<Toaster />` component from sonner to the root locale layout so toast notifications work on all pages. Import from the shadcn sonner component. Place it after the closing `</SidebarProvider>` but before the closing fragment.

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web build` passes

---

### Task 15: Create Document Table Component
**File:** `cms/apps/web/src/components/documents/document-table.tsx` (create new)
**Action:** CREATE

Follow the EXACT pattern from `cms/apps/web/src/components/routes/route-table.tsx`.

**Props interface:**
```typescript
interface DocumentTableProps {
  documents: DocumentItem[];
  selectedDocumentId: number | null;
  onSelectDocument: (id: number) => void;
  onDeleteDocument: (doc: DocumentItem) => void;
  isReadOnly: boolean;
  page: number;
  totalPages: number;
  totalItems: number;
  pageSize: number;
  onPageChange: (page: number) => void;
}
```

**Features:**
- Table columns: Name (title or filename), Type (badge), Size (formatted), Domain (badge), Status (badge), Uploaded (date), Actions (dropdown)
- Sort by name, date, size (client-side within current page)
- Status badges: `completed` = green (`status-ontime`), `processing` = amber (`status-delayed`), `failed` = red (`status-critical`), `pending` = gray
- Type badges: `pdf`, `docx`, `xlsx`, `csv`, `image`, `text`, `email`
- File size formatting helper: bytes -> KB/MB
- Actions dropdown: Download (if has_file), Delete (if not read-only)
- Row click calls `onSelectDocument`
- Empty state: icon + "No documents found" message
- Server-side pagination controls at footer (page/totalPages from props, NOT client-side)
- `useTranslations("documents")` for all strings

**Design tokens:** Use `p-(--spacing-card)`, `gap-(--spacing-tight)`, `border-border`, `bg-surface`, `text-foreground`, etc.

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 16: Create Document Filters Component
**File:** `cms/apps/web/src/components/documents/document-filters.tsx` (create new)
**Action:** CREATE

Follow the EXACT pattern from `cms/apps/web/src/components/routes/route-filters.tsx` (dual-mode: sidebar or Sheet).

**Props interface:**
```typescript
interface DocumentFiltersProps {
  search: string;
  onSearchChange: (value: string) => void;
  typeFilter: string;
  onTypeFilterChange: (value: string) => void;
  domainFilter: string;
  onDomainFilterChange: (value: string) => void;
  statusFilter: string;
  onStatusFilterChange: (value: string) => void;
  languageFilter: string;
  onLanguageFilterChange: (value: string) => void;
  domains: string[];
  resultCount: number;
  asSheet?: boolean;
  sheetOpen?: boolean;
  onSheetOpenChange?: (open: boolean) => void;
}
```

**Filter sections:**
1. Search input (filters by filename/title client-side)
2. Type toggle group: All | PDF | DOCX | XLSX | Image | Text
3. Domain select dropdown (populated from `domains` prop — fetched from API)
4. Status toggle group: All | Completed | Processing | Failed
5. Language toggle group: All | LV | EN
6. Result count at bottom

Section labels: `text-xs font-medium text-label-text uppercase tracking-wide`

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 17: Create Document Upload Form
**File:** `cms/apps/web/src/components/documents/document-upload-form.tsx` (create new)
**Action:** CREATE

**Props interface:**
```typescript
interface DocumentUploadFormProps {
  isOpen: boolean;
  onClose: () => void;
  onUploadComplete: (doc: DocumentItem) => void;
  domains: string[];
}
```

**Implementation:**
- Sheet (right side, `w-full sm:w-[480px]`) — slightly wider than route form for dropzone
- Uses `react-dropzone` with `useDropzone` hook
- Dropzone area: dashed border, icon, "Drop files here or click to browse" text
- Accepted file types: `.pdf, .docx, .xlsx, .csv, .txt, .md, .png, .jpg, .jpeg, .eml`
- Max file size: 50MB (`maxSize: 50 * 1024 * 1024`)
- Form fields below dropzone:
  - Title (optional Input)
  - Description (optional Textarea)
  - Domain (Select — with existing domains + ability to type new)
  - Language (Select: Latvian / English, default Latvian)
- Upload button with Progress bar during upload
- Use `uploadDocument` from documents-client.ts
- On success: `toast.success(t("toast.uploaded"))`, call `onUploadComplete`
- On error: `toast.error(t("toast.uploadError"))`
- Show selected file info: name, size, type icon
- `useTranslations("documents")` for all strings
- Dropzone states: idle, drag-active (blue border), rejected (red border)

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 18: Create Document Detail Component
**File:** `cms/apps/web/src/components/documents/document-detail.tsx` (create new)
**Action:** CREATE

Follow the EXACT pattern from `cms/apps/web/src/components/routes/route-detail.tsx`.

**Props interface:**
```typescript
interface DocumentDetailProps {
  document: DocumentItem | null;
  isOpen: boolean;
  onClose: () => void;
  onDelete: (doc: DocumentItem) => void;
  isReadOnly: boolean;
}
```

**Layout (Sheet, right side, `w-full sm:w-[480px]`):**
- Header: document title (or filename if no title), status badge
- Metadata section:
  - File Name, File Type, File Size, Language, Domain
  - Chunk Count, Uploaded date, Updated date
  - Description (if present)
- Actions section:
  - Download button (if `has_file`)
  - Delete button (if not read-only, uses `status-critical` color)
- Content Preview section (collapsible):
  - Fetches chunks from `fetchDocumentContent(doc.id)` on open
  - Shows first 3 chunks as preview text blocks in `ScrollArea`
  - "Show all chunks" expands to full list
  - Each chunk: `bg-surface rounded-lg p-(--spacing-card)` with chunk index label

Uses `DetailRow` helper component (extracted to module scope, NOT defined inside the component body).
Uses `useLocale()` for date formatting via `Intl.DateTimeFormat`.

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 19: Create Delete Document Dialog
**File:** `cms/apps/web/src/components/documents/delete-document-dialog.tsx` (create new)
**Action:** CREATE

Follow the EXACT pattern from `cms/apps/web/src/components/routes/delete-route-dialog.tsx`.

**Props interface:**
```typescript
interface DeleteDocumentDialogProps {
  document: DocumentItem | null;
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (documentId: number) => void;
}
```

- Dialog (centered, NOT Sheet)
- AlertTriangle icon in `bg-status-critical/10` circle
- Title: "Delete Document"
- Warning: "Are you sure you want to delete '{name}'? This will remove the document and all extracted chunks from the knowledge base."
- Cancel + Delete buttons
- `useTranslations("documents.delete")`
- Return `null` if `document` is null

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 20: Create Documents Page
**File:** `cms/apps/web/src/app/[locale]/(dashboard)/documents/page.tsx` (create new)
**Action:** CREATE

Follow the EXACT pattern from `cms/apps/web/src/app/[locale]/(dashboard)/routes/page.tsx`.

**Structure:**
- `"use client"` directive
- `const USER_ROLE: string = "admin"` (explicit string annotation — anti-pattern rule 4)
- `IS_READ_ONLY = USER_ROLE === "viewer"`
- Page height: `h-[calc(100vh-var(--spacing-page)*2)]`
- `useTranslations("documents")` namespace

**State:**
- `documents: DocumentItem[]` — fetched from API
- `selectedDocumentId: number | null`
- `isUploadOpen: boolean`
- `isDeleteOpen: boolean`
- `documentToDelete: DocumentItem | null`
- `page: number` (pagination state)
- `totalPages, totalItems: number`
- `domains: string[]` — fetched from `fetchDomains()`
- Filter state: `search, typeFilter, domainFilter, statusFilter, languageFilter`
- `isLoading: boolean`

**Data fetching:**
- `useEffect` to call `fetchDocuments` with current filter/pagination params
- `useEffect` to call `fetchDomains` on mount
- Client-side search filter on `filename`/`title` (server handles domain/status/language)

**Layout (no mobile ResizablePanel needed — simpler than routes):**
- Header row: h1 "Document Management" + Upload button (hidden when read-only)
- Content: filters sidebar (desktop) + table area
- Mobile: filters in Sheet, triggered by filter button in header

**Callbacks (all `useCallback`):**
- `handleUploadComplete`: Refresh documents list, close upload form
- `handleDelete`: Call `deleteDocument`, refresh list, show toast, close dialog
- `handlePageChange`: Update page state, triggers re-fetch

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 21: Update Sidebar Navigation
**File:** `cms/apps/web/src/components/app-sidebar.tsx` (modify existing)
**Action:** UPDATE

Add documents entry to `navItems` array. Insert BEFORE the `chat` item (documents is a data management page, chat is a tool):
```typescript
{ key: "documents", href: "/documents", enabled: true },
```

The `key` must match the `nav.documents` i18n key added in Task 23.

Icon: Use `FileText` from `lucide-react` for the documents nav item. Import it at the top of the file alongside existing icon imports. Add it to the icon mapping logic.

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 22: Update RBAC Middleware
**File:** `cms/apps/web/middleware.ts` (modify existing)
**Action:** UPDATE

**Add `/documents` to ROLE_PERMISSIONS:**
- `admin`: add `"/documents"` to array
- `dispatcher`: add `"/documents"` (read-only access enforced at component level)
- `editor`: add `"/documents"` to array
- `viewer`: add `"/documents"` (read-only)

**Update matcher pattern:**
Current: `["/(lv|en)/(routes|stops|schedules|gtfs|users|chat)/:path*"]`
Updated: `["/(lv|en)/(routes|stops|schedules|gtfs|users|chat|documents)/:path*"]`

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 23: Add English i18n Keys
**File:** `cms/apps/web/messages/en.json` (modify existing)
**Action:** UPDATE

Add `"documents"` key to the `nav` namespace:
```json
"nav": {
  ...existing keys...,
  "documents": "Documents"
}
```

Add top-level `"documents"` namespace with all keys:
```json
"documents": {
  "title": "Document Management",
  "description": "Upload and manage knowledge base documents",
  "search": "Search documents...",
  "filters": {
    "allTypes": "All Types",
    "pdf": "PDF",
    "docx": "Word",
    "xlsx": "Excel",
    "csv": "CSV",
    "image": "Image",
    "text": "Text",
    "email": "Email",
    "allStatuses": "All Statuses",
    "completed": "Completed",
    "processing": "Processing",
    "failed": "Failed",
    "pending": "Pending",
    "allLanguages": "All Languages",
    "lv": "Latvian",
    "en": "English",
    "allDomains": "All Domains",
    "type": "Type",
    "domain": "Domain",
    "status": "Status",
    "language": "Language"
  },
  "table": {
    "name": "Name",
    "type": "Type",
    "size": "Size",
    "domain": "Domain",
    "status": "Status",
    "language": "Language",
    "uploaded": "Uploaded",
    "actions": "Actions",
    "noResults": "No documents found",
    "noResultsDescription": "Upload your first document to get started.",
    "showing": "Showing {from}-{to} of {total}"
  },
  "detail": {
    "title": "Document Details",
    "fileName": "File Name",
    "fileType": "File Type",
    "fileSize": "File Size",
    "chunkCount": "Chunks",
    "domain": "Domain",
    "language": "Language",
    "uploaded": "Uploaded",
    "updated": "Updated",
    "description": "Description",
    "noDescription": "No description",
    "contentPreview": "Content Preview",
    "showAllChunks": "Show all {count} chunks",
    "chunk": "Chunk {index}"
  },
  "actions": {
    "upload": "Upload Document",
    "delete": "Delete",
    "download": "Download",
    "close": "Close"
  },
  "upload": {
    "title": "Upload Document",
    "dropzone": "Drop files here or click to browse",
    "dropzoneHint": "Supports PDF, DOCX, XLSX, CSV, TXT, images up to 50MB",
    "dropzoneActive": "Drop the file here",
    "dropzoneReject": "File type not supported",
    "selectedFile": "Selected file",
    "titleLabel": "Title",
    "titlePlaceholder": "Document title (optional)",
    "descriptionLabel": "Description",
    "descriptionPlaceholder": "Brief description of the document...",
    "domainLabel": "Domain",
    "domainPlaceholder": "Select or type domain",
    "languageLabel": "Language",
    "uploading": "Uploading...",
    "processing": "Processing document...",
    "submit": "Upload"
  },
  "delete": {
    "title": "Delete Document",
    "confirmation": "Are you sure you want to delete \"{name}\"?",
    "warning": "This will permanently remove the document and all extracted chunks from the knowledge base.",
    "confirm": "Delete",
    "cancel": "Cancel"
  },
  "toast": {
    "uploaded": "Document uploaded successfully",
    "deleted": "Document deleted",
    "uploadError": "Upload failed. Please try again.",
    "deleteError": "Delete failed. Please try again.",
    "downloadError": "Download failed. Please try again."
  },
  "mobile": {
    "showFilters": "Filters"
  }
}
```

**Per-task validation:**
- JSON is valid (no trailing commas, proper nesting)
- `pnpm --filter @vtv/web build` passes

---

### Task 24: Add Latvian i18n Keys
**File:** `cms/apps/web/messages/lv.json` (modify existing)
**Action:** UPDATE

Mirror the EXACT same structure as Task 23 but with Latvian translations.

Add `"documents": "Dokumenti"` to `nav` namespace.

Add `"documents"` namespace. Key translations:
- title: "Dokumentu parvaldiba"
- description: "Augsupladet un parvaldiet zinasanu bazes dokumentus"
- search: "Meklet dokumentus..."
- filters: allTypes "Visi tipi", pdf "PDF", docx "Word", xlsx "Excel", csv "CSV", image "Attels", text "Teksts", email "E-pasts", allStatuses "Visi statusi", completed "Pabeigts", processing "Apstrade", failed "Kluda", pending "Gaida", allLanguages "Visas valodas", lv "Latviesu", en "Anglu", allDomains "Visi domeni", type "Tips", domain "Domens", status "Statuss", language "Valoda"
- table: name "Nosaukums", type "Tips", size "Izmers", domain "Domens", status "Statuss", language "Valoda", uploaded "Augsupladet", actions "Darbibas", noResults "Dokumenti nav atrasti", noResultsDescription "Augsupladet pirmo dokumentu, lai sakt darbu.", showing "Rada {from}-{to} no {total}"
- detail: title "Dokumenta detajas", fileName "Faila nosaukums", fileType "Faila tips", fileSize "Faila izmers", chunkCount "Fragmenti", domain "Domens", language "Valoda", uploaded "Augsupladet", updated "Atjauninats", description "Apraksts", noDescription "Nav apraksta", contentPreview "Satura prieksskatijums", showAllChunks "Radit visus {count} fragmentus", chunk "Fragments {index}"
- actions: upload "Augsupladet dokumentu", delete "Dzest", download "Lejupladet", close "Aizvert"
- upload: title "Augsupladet dokumentu", dropzone "Ievelciet failus seit vai nokliksiniet", dropzoneHint "Atbalsta PDF, DOCX, XLSX, CSV, TXT, attelus lidz 50MB", dropzoneActive "Atlaidiet failu seit", dropzoneReject "Faila tips netiek atbalstits", selectedFile "Izvelets fails", titleLabel "Nosaukums", titlePlaceholder "Dokumenta nosaukums (neobligats)", descriptionLabel "Apraksts", descriptionPlaceholder "Iss dokumenta apraksts...", domainLabel "Domens", domainPlaceholder "Izvelieties vai ievadiet domenu", languageLabel "Valoda", uploading "Augsupladet...", processing "Apstrada dokumentu...", submit "Augsupladet"
- delete: title "Dzest dokumentu", confirmation "Vai tiesat velaties dzest \"{name}\"?", warning "Dokuments un visi iegutie fragmenti tiks neatgriezeniski nonemti no zinasanu bazes.", confirm "Dzest", cancel "Atcelt"
- toast: uploaded "Dokuments veiksmigi augsupladet", deleted "Dokuments dzests", uploadError "Augsupladesana neizdevas. Meginet velreiz.", deleteError "Dzesana neizdevas. Meginet velreiz.", downloadError "Lejupladesana neizdevas. Meginet velreiz."
- mobile: showFilters "Filtri"

NOTE: Use ONLY ASCII hyphens (U+002D), never EN DASH. Use proper Latvian diacritics: a, c, e, g, i, k, l, n, s, u, z (with macrons, cedillas, carons).

**Per-task validation:**
- JSON is valid
- `pnpm --filter @vtv/web build` passes

---

### Task 25: Final Integration Validation
**Action:** RUN FULL VALIDATION

No file changes. Run the complete validation suite.

**Per-task validation:**
This task runs the Final Validation pyramid (all 5 levels).

---

## Migration

```bash
# Generate migration (already done in Task 3)
uv run alembic revision --autogenerate -m "add title description file_path to documents"

# Apply when database is available
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
- Excel extraction — mock openpyxl workbook
- CSV extraction — temp file with csv data
- Document update service — mock repository
- Document content retrieval — mock repository with chunks
- Domain listing — mock repository
- File storage on upload — mock file system operations
- File cleanup on delete — mock shutil.rmtree
- Download path retrieval — happy path + legacy document error

### Existing Tests
**Location:** `app/knowledge/tests/` (existing files)
- `test_processing.py` — 6 tests (unchanged, still pass)
- `test_chunking.py` — 6 tests (unchanged)
- `test_embedding.py` — 7 tests (unchanged)
- All existing tests MUST still pass after changes.

### Frontend Testing
- Manual verification via dev server
- `pnpm --filter @vtv/web build` — catches SSR issues, type errors
- `pnpm --filter @vtv/web type-check` — strict TypeScript
- `pnpm --filter @vtv/web lint` — ESLint

## Acceptance Criteria

This feature is complete when:
- [ ] Documents page accessible at `/lv/documents` and `/en/documents`
- [ ] File upload via drag-and-drop works (PDF, DOCX, XLSX, CSV, TXT, images)
- [ ] Uploaded files are stored on disk and downloadable
- [ ] Document table shows all documents with pagination, sorting, filters
- [ ] Document detail panel shows metadata and content preview (chunks)
- [ ] Delete confirmation dialog works and removes document + file
- [ ] Excel/CSV files are properly extracted to text
- [ ] Sidebar shows "Documents" / "Dokumenti" nav item with correct active state
- [ ] RBAC enforced: all roles can view, admin/editor can upload/delete
- [ ] i18n complete: all strings in both LV and EN
- [ ] All backend type checkers pass (mypy + pyright)
- [ ] All backend tests pass (existing 20 + new 9 = 29 knowledge tests)
- [ ] Frontend build passes (`pnpm --filter @vtv/web build`)
- [ ] No type suppressions added without justification
- [ ] Structured logging follows `domain.component.action_state` pattern

## Completion Checklist

Before marking this plan as fully executed:
- [ ] All 25 tasks completed in order
- [ ] Per-task validations passed
- [ ] Full validation pyramid passed (Levels 1-5)
- [ ] No deviations from plan (or deviations documented with reasons)
- [ ] Ready for `/commit`

## Final Validation (5-Level Pyramid)

Run each level in order — every one must pass with 0 errors:

**Level 1: Syntax & Style (Backend)**
```bash
uv run ruff format .
uv run ruff check --fix .
```

**Level 2: Type Safety (Backend)**
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

**Level 5: Frontend Validation**
```bash
cd cms
pnpm --filter @vtv/web type-check
pnpm --filter @vtv/web lint
pnpm --filter @vtv/web build
```

**Success definition:** Levels 1-5 exit code 0, all tests pass, zero errors or warnings.

## Dependencies

- **Shared utilities used:** `PaginationParams`, `PaginatedResponse` (from `app/shared/schemas`), `TimestampMixin` (from `app/shared/models`), `get_db()` (from `app/core/database`), `get_logger()` (from `app/core/logging`), `limiter` (from `app/core/rate_limit`)
- **Core modules used:** `app/core/config.py` (Settings), `app/core/exceptions.py` (base classes)
- **New backend dependency:** `openpyxl>=3.1.5` — add via `uv add openpyxl`
- **New frontend dependencies:** `react-dropzone` — add via `pnpm --filter @vtv/web add react-dropzone`
- **New shadcn components:** `progress`, `sonner` — add via `npx shadcn@latest add progress sonner`
- **New env var:** `DOCUMENT_STORAGE_PATH` (default: `data/documents`)

## Known Pitfalls

The executing agent MUST follow these rules to avoid common errors:

1. **No `assert` in production code** — Ruff S101. Use `if x is not None:` conditionals.
2. **No `object` type hints** — Import actual types. Never `def f(data: object)` + isinstance.
3. **Untyped libraries (openpyxl)** — mypy override already added in Task 1. For pyright, add file-level `# pyright: reportUnknownMemberType=false` to `processing.py` only.
4. **Mock exceptions must match catch blocks** — If code catches `openpyxl.utils.exceptions.InvalidFileException`, mock that exact exception.
5. **No unused imports or variables** — Ruff F401/F841. Only import what you use.
6. **No EN DASH in strings** — Use HYPHEN-MINUS `-` (U+002D) everywhere, including i18n files and Latvian text. Watch for "from-to" patterns.
7. **Test helper functions need `-> ReturnType`** — Always add return type to test helpers.
8. **`request: Request` for slowapi routes** — Add `_ = request` to suppress ARG001.
9. **Bare `[]` list literals need type annotation** — `items: list[DocumentItem] = []` not `items = []`.
10. **Pydantic `ConfigDict(from_attributes=True)`** — Required on all response schemas that map from ORM objects.
11. **`str()` wrapping for untyped lib returns** — `str(page.get_text())`, `str(cell.value)` for openpyxl cells.
12. **React: No component definitions inside components** — Extract `DetailRow`, `StatusBadge` etc. to module scope.
13. **React: `const USER_ROLE: string = "admin"`** — Explicit string annotation for const narrowing.
14. **React: No `Math.random()` in render** — Use `useId()` or generate IDs outside render.
15. **React: No `setState` in `useEffect`** — Use key prop remount pattern if needed.
16. **Partially annotated test functions need `-> None`** — Always: `def test_foo(param: Type) -> None:`.
17. **`shutil` operations need error handling** — `shutil.rmtree(path, ignore_errors=True)` for cleanup.
18. **`FileResponse` requires absolute path** — Use `Path.resolve()` before passing to `FileResponse`.

## Notes

- **Auto-tagging deferred:** LLM-based auto-tagging on upload (mentioned in TODO) is intentionally deferred to a follow-up plan. This plan delivers the core DMS UI first. Auto-tagging requires significant additional complexity (LLM API calls during upload, async processing, tag suggestion UI). It can be added as an enhancement once the base DMS is usable.
- **File storage is local filesystem:** For MVP, files are stored at `data/documents/{id}/{filename}`. For production Docker deployment, mount this as a named volume in `docker-compose.yml`. Cloud storage (S3/MinIO) is a future enhancement.
- **No bulk upload in this plan:** Single-file upload only. Bulk upload (multiple files in one request) can be added later.
- **Domain is free-text:** No enum constraint on domains. The domains endpoint returns all existing unique domains for the filter dropdown. Users can type new domains during upload.
- **Existing search pipeline unchanged:** The RAG search endpoint (`POST /search`) is NOT modified. It continues to work with the new title/description fields transparently.

## Pre-Implementation Checklist

The executing agent MUST verify before writing any code:
- [ ] Read all files listed in "Relevant Files" section
- [ ] Understood that this extends `app/knowledge/`, NOT a new feature directory
- [ ] Confirmed `openpyxl` is not already installed (`uv pip show openpyxl`)
- [ ] Confirmed `python-multipart` is available (required for UploadFile)
- [ ] Understood the Document model's current column layout
- [ ] Reviewed the routes page pattern for frontend component structure
- [ ] Validation commands are executable in this environment
