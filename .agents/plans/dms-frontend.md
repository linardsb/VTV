# Plan: DMS Frontend — Document Management Page

## Feature Metadata
**Feature Type**: New Frontend Page
**Estimated Complexity**: Medium-High
**Primary Systems Affected**: `cms/apps/web/`
**Prerequisite**: `.agents/plans/dms-backend.md` must be completed first (backend API endpoints must exist)

## Feature Description

This plan creates a new `/documents` page in the VTV CMS that provides a complete document management interface for the RAG knowledge base. It connects to the backend API endpoints created by the companion `dms-backend.md` plan.

The page includes a filterable document table, drag-and-drop upload form, document detail panel with chunk preview, and delete confirmation dialog. It follows the exact patterns established by the routes page (the most complex existing page).

## User Story

As a **dispatcher or administrator** using the VTV CMS,
I want to **upload, browse, and manage documents through a web interface**
So that **the knowledge base is populated with operational documents without needing API tools**.

## Solution Approach

Follow the established routes page pattern exactly:
- `"use client"` page component owning all state
- Sub-components in `components/documents/`
- API client in `lib/documents-client.ts`
- Dual-mode filters (sidebar desktop / Sheet mobile)
- Sheet-based upload form and detail panel
- Dialog-based delete confirmation

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Frontend section: tech stack, component patterns, i18n, RBAC
- `cms/apps/web/CLAUDE.md` — Frontend-specific conventions

### Pattern Templates (READ THESE — copy their exact patterns)
- `cms/apps/web/src/app/[locale]/(dashboard)/routes/page.tsx` — Page pattern to follow
- `cms/apps/web/src/components/routes/route-table.tsx` — Table with pagination, sorting, actions
- `cms/apps/web/src/components/routes/route-filters.tsx` — Filter sidebar/sheet dual-mode
- `cms/apps/web/src/components/routes/route-form.tsx` — Sheet-based form
- `cms/apps/web/src/components/routes/route-detail.tsx` — Detail panel with metadata rows
- `cms/apps/web/src/components/routes/delete-route-dialog.tsx` — Delete confirmation dialog
- `cms/apps/web/src/components/app-sidebar.tsx` — Nav items array structure
- `cms/apps/web/middleware.ts` — RBAC permissions and matcher
- `cms/apps/web/src/lib/agent-client.ts` — API client pattern

### Design System
- `cms/design-system/vtv/MASTER.md` — Design rules (spacing, colors, typography)
- `cms/packages/ui/src/tokens.css` — Semantic design tokens

### i18n
- `cms/apps/web/messages/en.json` — English translations (structure to mirror)
- `cms/apps/web/messages/lv.json` — Latvian translations

### Files to Modify
- `cms/apps/web/src/components/app-sidebar.tsx` — Add documents nav item
- `cms/apps/web/middleware.ts` — Add /documents to RBAC and matcher
- `cms/apps/web/messages/en.json` — Add documents namespace
- `cms/apps/web/messages/lv.json` — Add documents namespace (Latvian)
- `cms/apps/web/src/app/[locale]/layout.tsx` — Add Sonner Toaster

### Backend API Contract (created by dms-backend.md)
The frontend calls these endpoints at `{NEXT_PUBLIC_AGENT_URL}/api/v1/knowledge`:
- `GET /documents` — List with pagination, domain/status/language filters
- `GET /documents/{id}` — Single document
- `POST /documents` — Upload (multipart: file + title + description + domain + language)
- `PATCH /documents/{id}` — Update metadata
- `DELETE /documents/{id}` — Delete document + file
- `GET /documents/{id}/content` — Get extracted text chunks
- `GET /documents/{id}/download` — Download original file
- `GET /domains` — List unique domains

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.

---

### Task 1: Install Frontend Dependencies
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
- `pnpm --filter @vtv/web build` still succeeds
- `ls cms/apps/web/src/components/ui/progress.tsx` exists
- `ls cms/apps/web/src/components/ui/sonner.tsx` exists

---

### Task 2: Create Document TypeScript Types
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

### Task 3: Create Documents API Client
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

### Task 4: Add Sonner Toaster to Root Layout
**File:** `cms/apps/web/src/app/[locale]/layout.tsx` (modify existing)
**Action:** UPDATE

Add the `<Toaster />` component from sonner to the root locale layout so toast notifications work on all pages. Import from the shadcn sonner component. Place it after the closing `</SidebarProvider>` but before the closing fragment.

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web build` passes

---

### Task 5: Create Document Table Component
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

### Task 6: Create Document Filters Component
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

### Task 7: Create Document Upload Form
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

### Task 8: Create Document Detail Component
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

### Task 9: Create Delete Document Dialog
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
- Warning message about permanent deletion of document and chunks
- Cancel + Delete buttons
- `useTranslations("documents.delete")`
- Return `null` if `document` is null

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 10: Create Documents Page
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

### Task 11: Update Sidebar Navigation
**File:** `cms/apps/web/src/components/app-sidebar.tsx` (modify existing)
**Action:** UPDATE

Add documents entry to `navItems` array. Insert BEFORE the `chat` item:
```typescript
{ key: "documents", href: "/documents", enabled: true },
```

Icon: Use `FileText` from `lucide-react`. Import at top, add to icon mapping logic.

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 12: Update RBAC Middleware
**File:** `cms/apps/web/middleware.ts` (modify existing)
**Action:** UPDATE

**Add `/documents` to ROLE_PERMISSIONS:**
- `admin`: add `"/documents"`
- `dispatcher`: add `"/documents"` (read-only enforced at component level)
- `editor`: add `"/documents"`
- `viewer`: add `"/documents"` (read-only)

**Update matcher pattern:**
Add `documents` to: `["/(lv|en)/(routes|stops|schedules|gtfs|users|chat|documents)/:path*"]`

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 13: Add English i18n Keys
**File:** `cms/apps/web/messages/en.json` (modify existing)
**Action:** UPDATE

Add `"documents": "Documents"` to the `nav` namespace.

Add top-level `"documents"` namespace with all keys:
```json
"documents": {
  "title": "Document Management",
  "description": "Upload and manage knowledge base documents",
  "search": "Search documents...",
  "filters": {
    "allTypes": "All Types", "pdf": "PDF", "docx": "Word", "xlsx": "Excel",
    "csv": "CSV", "image": "Image", "text": "Text", "email": "Email",
    "allStatuses": "All Statuses", "completed": "Completed", "processing": "Processing",
    "failed": "Failed", "pending": "Pending",
    "allLanguages": "All Languages", "lv": "Latvian", "en": "English",
    "allDomains": "All Domains",
    "type": "Type", "domain": "Domain", "status": "Status", "language": "Language"
  },
  "table": {
    "name": "Name", "type": "Type", "size": "Size", "domain": "Domain",
    "status": "Status", "language": "Language", "uploaded": "Uploaded",
    "actions": "Actions", "noResults": "No documents found",
    "noResultsDescription": "Upload your first document to get started.",
    "showing": "Showing {from}-{to} of {total}"
  },
  "detail": {
    "title": "Document Details", "fileName": "File Name", "fileType": "File Type",
    "fileSize": "File Size", "chunkCount": "Chunks", "domain": "Domain",
    "language": "Language", "uploaded": "Uploaded", "updated": "Updated",
    "description": "Description", "noDescription": "No description",
    "contentPreview": "Content Preview",
    "showAllChunks": "Show all {count} chunks", "chunk": "Chunk {index}"
  },
  "actions": {
    "upload": "Upload Document", "delete": "Delete", "download": "Download", "close": "Close"
  },
  "upload": {
    "title": "Upload Document",
    "dropzone": "Drop files here or click to browse",
    "dropzoneHint": "Supports PDF, DOCX, XLSX, CSV, TXT, images up to 50MB",
    "dropzoneActive": "Drop the file here",
    "dropzoneReject": "File type not supported",
    "selectedFile": "Selected file",
    "titleLabel": "Title", "titlePlaceholder": "Document title (optional)",
    "descriptionLabel": "Description",
    "descriptionPlaceholder": "Brief description of the document...",
    "domainLabel": "Domain", "domainPlaceholder": "Select or type domain",
    "languageLabel": "Language",
    "uploading": "Uploading...", "processing": "Processing document...", "submit": "Upload"
  },
  "delete": {
    "title": "Delete Document",
    "confirmation": "Are you sure you want to delete \"{name}\"?",
    "warning": "This will permanently remove the document and all extracted chunks from the knowledge base.",
    "confirm": "Delete", "cancel": "Cancel"
  },
  "toast": {
    "uploaded": "Document uploaded successfully", "deleted": "Document deleted",
    "uploadError": "Upload failed. Please try again.",
    "deleteError": "Delete failed. Please try again.",
    "downloadError": "Download failed. Please try again."
  },
  "mobile": { "showFilters": "Filters" }
}
```

**Per-task validation:**
- JSON is valid (no trailing commas, proper nesting)
- `pnpm --filter @vtv/web build` passes

---

### Task 14: Add Latvian i18n Keys
**File:** `cms/apps/web/messages/lv.json` (modify existing)
**Action:** UPDATE

Mirror the EXACT same structure as Task 13 but with Latvian translations.

Add `"documents": "Dokumenti"` to `nav` namespace.

Add `"documents"` namespace with Latvian translations. Key translations:
- title: "Dokumentu parvaldiba", description: "Augsupladet un parvaldiet zinasanu bazes dokumentus"
- search: "Meklet dokumentus..."
- filters: allTypes "Visi tipi", allStatuses "Visi statusi", completed "Pabeigts", processing "Apstrade", failed "Kluda", pending "Gaida", allLanguages "Visas valodas", lv "Latviesu", en "Anglu", allDomains "Visi domeni"
- table: name "Nosaukums", noResults "Dokumenti nav atrasti", noResultsDescription "Augsupladet pirmo dokumentu, lai sakt darbu.", showing "Rada {from}-{to} no {total}"
- detail: title "Dokumenta detajas", fileName "Faila nosaukums", fileType "Faila tips", fileSize "Faila izmers", chunkCount "Fragmenti", noDescription "Nav apraksta", contentPreview "Satura prieksskatijums", showAllChunks "Radit visus {count} fragmentus", chunk "Fragments {index}"
- actions: upload "Augsupladet dokumentu", delete "Dzest", download "Lejupladet", close "Aizvert"
- upload: title "Augsupladet dokumentu", dropzone "Ievelciet failus seit vai nokliksiniet", dropzoneHint "Atbalsta PDF, DOCX, XLSX, CSV, TXT, attelus lidz 50MB"
- delete: title "Dzest dokumentu", confirmation "Vai tiesat velaties dzest \"{name}\"?", warning "Dokuments un visi iegutie fragmenti tiks neatgriezeniski nonemti no zinasanu bazes.", confirm "Dzest", cancel "Atcelt"
- toast: uploaded "Dokuments veiksmigi augsupladet", deleted "Dokuments dzests", uploadError "Augsupladesana neizdevas. Meginet velreiz."
- mobile: showFilters "Filtri"

NOTE: Use ONLY ASCII hyphens (U+002D), never EN DASH. Use proper Latvian diacritics.

**Per-task validation:**
- JSON is valid
- `pnpm --filter @vtv/web build` passes

---

### Task 15: Final Frontend Validation
**Action:** RUN FULL VALIDATION

```bash
cd /Users/Berzins/Desktop/VTV/cms
pnpm --filter @vtv/web type-check
pnpm --filter @vtv/web lint
pnpm --filter @vtv/web build
```

All three must pass with 0 errors.

---

## Acceptance Criteria

- [ ] Documents page accessible at `/lv/documents` and `/en/documents`
- [ ] File upload via drag-and-drop works
- [ ] Document table shows documents with pagination, sorting, filters
- [ ] Document detail panel shows metadata and content preview (chunks)
- [ ] Delete confirmation dialog works
- [ ] Sidebar shows "Documents" / "Dokumenti" nav item with correct active state
- [ ] RBAC enforced: all roles can view, admin/editor can upload/delete
- [ ] i18n complete: all strings in both LV and EN
- [ ] Frontend build passes (`pnpm --filter @vtv/web build`)
- [ ] TypeScript type-check passes
- [ ] ESLint passes

## Known Pitfalls

1. **No component definitions inside components** — Extract `DetailRow`, `StatusBadge` etc. to module scope.
2. **`const USER_ROLE: string = "admin"`** — Explicit string annotation for const narrowing.
3. **No `Math.random()` in render** — Use `useId()` or generate IDs outside render.
4. **No `setState` in `useEffect`** — Use key prop remount pattern if needed.
5. **No EN DASH in strings** — Use HYPHEN-MINUS `-` in i18n JSON and all strings.
6. **All callbacks must be `useCallback`** — Prevents unnecessary re-renders.
7. **Design tokens, not hardcoded values** — `p-(--spacing-card)` not `p-3`.
8. **`cursor-pointer` on all clickable elements** — Design system rule.
9. **Empty state for no results** — Icon + message + description.
10. **Mobile: filters in Sheet, not inline** — Use `useIsMobile()` hook.

## Pre-Implementation Checklist

- [ ] Backend plan (`dms-backend.md`) is fully completed and validated
- [ ] Backend API server is running at localhost:8123
- [ ] Read all pattern template files listed in "Relevant Files"
- [ ] Understood the routes page pattern completely
- [ ] Frontend dev dependencies are installed (`cd cms && pnpm install`)
