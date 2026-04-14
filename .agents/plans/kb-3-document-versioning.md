# Plan: KB-3 Document Versioning with Diff-Aware Search

## Context

SOPs and regulations are updated periodically, but re-uploading a document with
the same title currently **overwrites** the prior copy (chunks cascade-deleted
via FK `documents.id ON DELETE CASCADE`). Dispatchers lose the ability to
answer *"was this procedure updated recently?"* and *"what changed?"*.

KB-3 adds version tracking: re-upload of the same `(title, domain)` creates a
**new** `Document` row, links it to the prior via `parent_document_id`, marks
the prior as `status='superseded'` (chunks retained — **no cascade**), and
defaults all search/listing to the latest version only. Two new endpoints:
`GET /v1/documents/{id}/versions` (history) and
`GET /v1/documents/{id}/diff?v1=&v2=` (unified text diff via `difflib`).

## Security Context Assessment

| Context | Active? | Why |
|---|---|---|
| CTX-AUTH | ❌ | No changes to auth/session/JWT. |
| **CTX-RBAC** | ✅ | Two new GET endpoints — must gate via `require_role(...)`, add rate limits, keep IDOR parity with existing `GET /documents/{id}`. |
| CTX-FILE | ⚠ partial | Upload path reused (no new file handling). Existing magic-bytes/sanitization/streaming-size coverage auto-applies. No new surface. |
| CTX-AGENT | ❌ | No agent tool. |
| CTX-INFRA | ❌ | No Docker/nginx/CORS/SSL changes. |
| **CTX-INPUT** | ✅ | Two new `Query(...)` params on `/diff` (`v1`, `v2`) + one on search/list (`include_superseded`). All must have bounded types (`int, ge=1` / `bool`). Search `title` comparison is already done by equality, not ILIKE — no new wildcard exposure. |

Applied requirements:
- RBAC: mirror existing read-side role set (`"admin", "editor", "dispatcher"`). Admin-only for anything destructive — there is none here. 404 (not 403) for not-found doc IDs (repository returns `None` → `DocumentNotFoundError`).
- Input: `v1`/`v2` as `Query(..., ge=1, le=10_000)`; `include_superseded: bool = False` defaulted to the safe value.

## Research Summary (from Agent 1)

**Core files (with file:line refs):**
- `app/knowledge/models.py:30-56` — `Document` ORM class. No version fields yet.
- `app/knowledge/models.py:71-101` — `DocumentChunk` with `ForeignKey("documents.id", ondelete="CASCADE")`. **Critical**: when marking a doc `superseded`, *do not delete* — cascade would wipe chunks.
- `app/knowledge/schemas.py:10-32` — `DocumentUpload` (input).
- `app/knowledge/schemas.py:87-114` — `DocumentResponse` (add `version`, `is_latest`, `parent_document_id`).
- `app/knowledge/schemas.py:143-155` — `SearchRequest` (add `include_superseded`).
- `app/knowledge/schemas.py:158-175` — `SearchResult` (add `version`, `is_latest`).
- `app/knowledge/service.py:181-302` — `ingest_document()` — inject same-title detection *after* validation, *before* `repository.create_document()`.
- `app/knowledge/service.py:575-765` — `search()`. Thread `include_superseded` down to repo.
- `app/knowledge/repository.py` — add `get_latest_by_title_domain()`; modify `search_vector` / `search_fulltext` / `list_documents` to accept `include_superseded`.
- `app/knowledge/exceptions.py` — existing hierarchy (`DocumentNotFoundError`, etc.). No new class needed; a simple `DomainValidationError` on same-version diff is enough.
- `app/knowledge/routes.py` — existing patterns: `@limiter.limit("30/minute")` for reads, `require_role("admin", "editor", "dispatcher")` for list/get/search, `require_role("admin", "editor")` for mutations.

**Status enum today:** `pending | processing | completed | failed`. **Add `superseded`** as a sixth implicit state. No server-side enum constraint (plain `String(20)`), so just a code-level constant.

**Migration convention:** Latest revision is `v6w7x8y9z0a1` (add_share_links, 2026-04-13). Use revision `w7x8y9z0a1b2` with `down_revision="v6w7x8y9z0a1"`.

**Shared utilities available:** `PaginatedResponse[T]`, `PaginationParams`, `TimestampMixin`, `utcnow()`, `AppError` hierarchy. No need for new shared code.

## Test Landscape (from Agent 2)

**Reusable fixtures (no new ones needed):**
- `app/knowledge/tests/conftest.py:11` — `sample_upload()` → `DocumentUpload(domain="transit", language="lv")`.
- `app/knowledge/tests/test_routes.py:42-50` — `_mock_admin_user()`.
- `app/knowledge/tests/test_routes.py:53-60` — `_setup_auth_override` autouse fixture (prevents anti-pattern #56 leakage).
- `app/knowledge/tests/test_routes.py:63-85` — `_make_doc_response(**overrides)`.
- `app/knowledge/tests/test_routes.py:88-90` — `_mock_service()` returning `AsyncMock(spec=KnowledgeService)`.
- `app/knowledge/tests/test_routes.py:93-102` — `_client()` helper (sets `limiter.enabled=False`).
- `app/knowledge/tests/test_repository.py:15-57` — `make_document()` / `make_chunk()` factories.

**Integration tests:** All 16 in `test_repository.py` mock the `AsyncSession` — they don't require a live DB. Our repo changes can use the same pattern.

**Security convention tests** (auto-apply to new endpoints via generic endpoint audit in `app/tests/test_security.py`): auth-required, rate-limited, role-gated. Nothing to configure — just use the canonical decorators.

**Anti-pattern hygiene to maintain:** #13 (limiter.enabled placement — keep inside `_client()` helper), #56 (dependency_overrides via autouse fixture), #60 (never use `async def` as `side_effect` of a plain `MagicMock` — use `AsyncMock`).

## Type Check Baseline (from Agent 3)

| Tool | Baseline errors |
|---|---|
| pyright 1.1.407 | **0** |
| mypy | **0** ("no issues found in 43 source files") |

Clean slate. Any new errors are attributable to this work.

## Files to Create/Modify

| Action | File | Purpose |
|---|---|---|
| CREATE | `alembic/versions/w7x8y9z0a1b2_add_document_versions.py` | Add `version`, `parent_document_id`, `is_latest` columns + FK + indexes. |
| UPDATE | `app/knowledge/models.py` | Add three mapped columns to `Document`; add self-referential relationship. |
| UPDATE | `app/knowledge/schemas.py` | `DocumentResponse` gains `version`, `is_latest`, `parent_document_id`. `SearchRequest` gains `include_superseded`. `SearchResult` gains `version`, `is_latest`. Add `DocumentVersionItem` and `DocumentDiffResponse`. |
| UPDATE | `app/knowledge/repository.py` | Add `get_latest_by_title_domain`, `list_versions`, `get_by_version`. Thread `include_superseded` through `search_vector`, `search_fulltext`, `list_documents`. |
| UPDATE | `app/knowledge/service.py` | `ingest_document` — same-title detection → supersede old. Add `get_document_versions`, `get_document_diff`. Thread `include_superseded` through `search` / `list_documents`. |
| UPDATE | `app/knowledge/routes.py` | Add `GET /documents/{id}/versions`, `GET /documents/{id}/diff`. Add `include_superseded: bool = Query(False)` to `search` and `list_documents`. |
| UPDATE | `app/knowledge/exceptions.py` | Add `DocumentVersionConflictError(DomainValidationError)` (raised when `v1 == v2` or when both versions do not share a version chain). |
| CREATE | `app/knowledge/tests/test_versioning.py` | 10 unit tests per user spec (service + routes, all mocked). |
| UPDATE | `app/knowledge/tests/test_repository.py` | 2 integration tests (mocked `AsyncSession`) for `get_latest_by_title_domain` and `list_versions`. |

**Router is already registered** — no `app/main.py` change.

## Data Model Details

### Columns on `documents`

| Column | Type | Nullable | Default | Purpose |
|---|---|---|---|---|
| `version` | `Integer` | NO | `1` (server_default `"1"`) | Monotonically increasing per version chain. |
| `parent_document_id` | `Integer` (FK `documents.id ON DELETE SET NULL`) | YES | `NULL` | Points to the immediately prior version. Null for the root (`v1`) of a chain. |
| `is_latest` | `Boolean` | NO | `TRUE` (server_default `"true"`) | Denormalized search filter — flipped to `false` when a newer version supersedes this row. |

### Indexes

- `ix_documents_title_version` — composite on `(title, version DESC)` (the user's spec). Useful for `get_latest_by_title_domain` even though we also filter on `domain`.
- `ix_documents_parent_document_id` — for version-chain traversal.
- `ix_documents_is_latest` — partial index where appropriate is overkill; a plain index is sufficient since `is_latest` will be an equality filter in nearly every search query.

### Invariants (enforced in service layer, not DB)

1. Within one `(title, domain)` group there is at most one row with `is_latest=true`.
2. `is_latest=true` ⇒ `status != 'superseded'`. The reverse is not strictly required (a *failed* processing run also has `is_latest=true` until the next successful re-upload, which is acceptable — failed rows are effectively dead).
3. `parent_document_id IS NULL` ⇔ `version == 1`.

### Chunk handling on supersede

**Do not delete the old Document.** Flip `status='superseded'` and `is_latest=false`. Chunks remain referenced (FK intact), continue to exist in the vector index. Search excludes them by filtering the joined `documents.is_latest=true` (or `status != 'superseded'` — we'll pick `is_latest` because it's cheaper and more explicit).

## Implementation Steps

### Step 1 — Alembic migration

`alembic/versions/w7x8y9z0a1b2_add_document_versions.py`:

```python
"""add document versions

Revision ID: w7x8y9z0a1b2
Revises: v6w7x8y9z0a1
Create Date: 2026-04-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "w7x8y9z0a1b2"
down_revision: str | None = "v6w7x8y9z0a1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )
    op.add_column(
        "documents",
        sa.Column("parent_document_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column(
            "is_latest",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.create_foreign_key(
        "fk_documents_parent_document_id",
        "documents",
        "documents",
        ["parent_document_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_documents_parent_document_id",
        "documents",
        ["parent_document_id"],
    )
    op.create_index(
        "ix_documents_is_latest",
        "documents",
        ["is_latest"],
    )
    op.create_index(
        "ix_documents_title_version",
        "documents",
        ["title", sa.text("version DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_documents_title_version", table_name="documents")
    op.drop_index("ix_documents_is_latest", table_name="documents")
    op.drop_index("ix_documents_parent_document_id", table_name="documents")
    op.drop_constraint("fk_documents_parent_document_id", "documents", type_="foreignkey")
    op.drop_column("documents", "is_latest")
    op.drop_column("documents", "parent_document_id")
    op.drop_column("documents", "version")
```

**Validation:** `uv run alembic upgrade head --sql | head -40` (dry-run; inspect generated SQL without applying).

---

### Step 2 — `app/knowledge/models.py`

Add to `Document` class:

```python
version: Mapped[int] = mapped_column(
    Integer, nullable=False, default=1, server_default=sa.text("1")
)
parent_document_id: Mapped[int | None] = mapped_column(
    Integer, ForeignKey("documents.id", ondelete="SET NULL"), nullable=True, index=True
)
is_latest: Mapped[bool] = mapped_column(
    Boolean, nullable=False, default=True, server_default=sa.text("true"), index=True
)
```

No `relationship()` back-ref — we traverse the chain explicitly in the repository (avoids SQLAlchemy's lazy-load surprises inside async).

**Validation:** `uv run ruff format app/knowledge/models.py && uv run ruff check app/knowledge/models.py && uv run pyright app/knowledge/models.py && uv run mypy app/knowledge/models.py`

---

### Step 3 — `app/knowledge/schemas.py`

Extend existing schemas (anti-pattern #11 / #29 — update ALL constructors of `DocumentResponse`: scan with `Grep` for `DocumentResponse(`):

```python
class DocumentResponse(BaseModel):
    # ...existing fields...
    version: int = 1
    is_latest: bool = True
    parent_document_id: int | None = None
```

```python
class SearchRequest(BaseModel):
    # ...existing fields...
    include_superseded: bool = False
```

```python
class SearchResult(BaseModel):
    # ...existing fields...
    version: int = 1
    is_latest: bool = True
```

New schemas:

```python
class DocumentVersionItem(BaseModel):
    """One entry in a document's version history."""
    id: int
    version: int
    status: str
    is_latest: bool
    parent_document_id: int | None
    filename: str
    file_size_bytes: int | None
    chunk_count: int
    created_at: datetime


class DocumentDiffResponse(BaseModel):
    """Unified-diff representation between two document versions."""
    document_id: int  # chain root (v1.id) — identifies the logical document
    v1: int  # version number
    v2: int
    v1_document_id: int  # concrete row ids
    v2_document_id: int
    unified_diff: str  # output of difflib.unified_diff(...) joined with "\n"
    lines_added: int
    lines_removed: int
```

Defaults are included so legacy constructors continue to pass type checking (anti-pattern #29). All three extended schemas keep backwards-compatible defaults.

**Validation:** `uv run ruff format app/knowledge/schemas.py && uv run ruff check app/knowledge/schemas.py && uv run pyright app/knowledge/schemas.py && uv run mypy app/knowledge/schemas.py`

---

### Step 4 — `app/knowledge/repository.py`

Add three methods and thread `include_superseded` through search/list.

```python
async def get_latest_by_title_domain(
    self, *, title: str, domain: str
) -> Document | None:
    """Return the current (non-superseded) latest version of a (title, domain) group, if any."""
    stmt = (
        select(Document)
        .where(
            Document.title == title,
            Document.domain == domain,
            Document.is_latest.is_(True),
        )
        .order_by(Document.version.desc())
        .limit(1)
    )
    result = await self.db.execute(stmt)
    return result.scalar_one_or_none()


async def list_versions(self, document_id: int) -> list[Document]:
    """Return all versions in the chain containing `document_id`, ordered by version DESC.

    The chain is identified by walking `parent_document_id` to the root, then collecting
    all rows whose chain-root matches.
    """
    root = await self._find_chain_root(document_id)
    if root is None:
        return []
    stmt = (
        select(Document)
        .where(or_(Document.id == root.id, Document.parent_document_id == root.id))
        .order_by(Document.version.desc())
    )
    # For chains deeper than 2, we need recursive collection.
    # Simpler: BFS over parent_document_id descendants.
    return await self._collect_descendants(root)


async def mark_superseded(self, doc_id: int) -> None:
    """Flip status='superseded' and is_latest=false on a document (chunks untouched)."""
    stmt = (
        update(Document)
        .where(Document.id == doc_id)
        .values(status="superseded", is_latest=False)
    )
    await self.db.execute(stmt)
    # Caller owns commit (same transaction as the new version creation).
```

Thread `include_superseded` into `search_vector`, `search_fulltext`, `list_documents`:

```python
async def search_vector(
    self,
    query_embedding: list[float],
    limit: int,
    domain: str | None = None,
    language: str | None = None,
    created_after: datetime | None = None,
    created_before: datetime | None = None,
    include_superseded: bool = False,
) -> list[tuple[DocumentChunk, Document, float]]:
    # ...existing stmt...
    if not include_superseded:
        stmt = stmt.where(Document.is_latest.is_(True))
    # ...
```

Same for `search_fulltext` and `list_documents`.

**Chain traversal helpers** — keep both in the repository. For typical depth (≤10) a bounded iterative BFS is cheaper than a recursive CTE and keeps the change surface small:

```python
async def _find_chain_root(self, doc_id: int) -> Document | None:
    current = await self.get(doc_id)
    if current is None:
        return None
    # Walk parents. Cap depth to prevent pathological cycles.
    for _ in range(100):
        if current.parent_document_id is None:
            return current
        parent = await self.get(current.parent_document_id)
        if parent is None:
            return current
        current = parent
    return current  # safety: abort after 100 hops

async def _collect_descendants(self, root: Document) -> list[Document]:
    """BFS collect all descendants + root, ordered by version DESC."""
    collected: dict[int, Document] = {root.id: root}
    frontier: list[int] = [root.id]
    while frontier:
        stmt = select(Document).where(Document.parent_document_id.in_(frontier))
        result = await self.db.execute(stmt)
        next_frontier: list[int] = []
        for doc in result.scalars().all():
            if doc.id not in collected:
                collected[doc.id] = doc
                next_frontier.append(doc.id)
        frontier = next_frontier
    return sorted(collected.values(), key=lambda d: d.version, reverse=True)
```

**Validation:** `uv run ruff format app/knowledge/repository.py && uv run ruff check app/knowledge/repository.py && uv run pyright app/knowledge/repository.py && uv run mypy app/knowledge/repository.py`

---

### Step 5 — `app/knowledge/service.py` (ingest_document modification)

Inside `ingest_document()`, immediately after validating `upload` but **before** `repository.create_document(...)`:

```python
# --- KB-3: same-title version detection -------------------------------------
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
```

Then pass `version=next_version, parent_document_id=parent_id, is_latest=True` into `repository.create_document(...)` (which needs to accept them — one-line extension of its parameter list).

**Ordering constraint:** `mark_superseded` and `create_document` run in the same `AsyncSession` transaction (committed together at the service's commit boundary). If `create_document` fails, SQLAlchemy rolls both back — the old version stays `is_latest=true`. This is the correct behavior.

Add two new service methods:

```python
async def get_document_versions(self, document_id: int) -> list[DocumentVersionItem]:
    versions = await self.repository.list_versions(document_id)
    if not versions:
        raise DocumentNotFoundError(f"Document {document_id} not found")
    return [
        DocumentVersionItem(
            id=d.id,
            version=d.version,
            status=d.status,
            is_latest=d.is_latest,
            parent_document_id=d.parent_document_id,
            filename=d.filename,
            file_size_bytes=d.file_size_bytes,
            chunk_count=d.chunk_count,
            created_at=d.created_at,
        )
        for d in versions
    ]


async def get_document_diff(
    self, document_id: int, v1: int, v2: int
) -> DocumentDiffResponse:
    if v1 == v2:
        raise DocumentVersionConflictError("v1 and v2 must differ")
    chain = await self.repository.list_versions(document_id)
    if not chain:
        raise DocumentNotFoundError(f"Document {document_id} not found")
    by_version = {d.version: d for d in chain}
    if v1 not in by_version or v2 not in by_version:
        raise DocumentNotFoundError(
            f"Version not found in chain for document {document_id}"
        )
    doc_a, doc_b = by_version[v1], by_version[v2]
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
    removed = sum(1 for line in diff_lines if line.startswith("-") and not line.startswith("---"))
    # Root of chain = the oldest in the chain (version=1). list_versions returns DESC.
    root = chain[-1]
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
    """Concatenate all chunks of a document, ordered by chunk_index, for diffing."""
    chunks = await self.repository.list_chunks_ordered(doc_id)
    return "\n".join(c.content for c in chunks)
```

Add `list_chunks_ordered` to the repository if it doesn't exist — one-liner using `select(DocumentChunk).where(...).order_by(DocumentChunk.chunk_index)`.

Thread `include_superseded` through existing `search()` and `list_documents()` in the service — just forward the parameter to the repository.

**Imports to add at the top of service.py:**

```python
import difflib
from app.knowledge.exceptions import (
    DocumentNotFoundError,
    DocumentVersionConflictError,  # new
)
```

**Validation:** `uv run ruff format app/knowledge/service.py && uv run ruff check app/knowledge/service.py && uv run pyright app/knowledge/service.py && uv run mypy app/knowledge/service.py`

---

### Step 6 — `app/knowledge/exceptions.py`

Add:

```python
class DocumentVersionConflictError(DomainValidationError):
    """Raised when version parameters are invalid (e.g. v1 == v2, or chain mismatch)."""
```

(Inherits `DomainValidationError` → 422 via the global handler in `core/exceptions.py`.)

**Validation:** `uv run ruff format app/knowledge/exceptions.py && uv run ruff check app/knowledge/exceptions.py && uv run pyright app/knowledge/exceptions.py`

---

### Step 7 — `app/knowledge/routes.py`

Add two endpoints + two query params:

```python
@router.get(
    "/documents/{document_id}/versions",
    response_model=list[DocumentVersionItem],
)
@limiter.limit("30/minute")
async def get_document_versions(
    request: Request,
    document_id: int,
    service: KnowledgeService = Depends(get_service),
    _current_user: User = Depends(require_role("admin", "editor", "dispatcher")),
) -> list[DocumentVersionItem]:
    return await service.get_document_versions(document_id)


@router.get(
    "/documents/{document_id}/diff",
    response_model=DocumentDiffResponse,
)
@limiter.limit("30/minute")
async def get_document_diff(
    request: Request,
    document_id: int,
    v1: int = Query(..., ge=1, le=10_000),
    v2: int = Query(..., ge=1, le=10_000),
    service: KnowledgeService = Depends(get_service),
    _current_user: User = Depends(require_role("admin", "editor", "dispatcher")),
) -> DocumentDiffResponse:
    return await service.get_document_diff(document_id, v1, v2)
```

Add `include_superseded: bool = Query(False)` to `list_documents` and to `search_knowledge` (forwarding into the service).

**Note:** `Query(...)` with non-None default values doesn't need `# noqa: B008` — that rule only fires on `Query(None)` / `Depends()` / `File(...)` as default values. The `Query(False)` and `Query(..., ge=1, le=10_000)` calls above DO trigger B008 — add `# noqa: B008` to each.

**Validation:** `uv run ruff format app/knowledge/routes.py && uv run ruff check app/knowledge/routes.py && uv run pyright app/knowledge/routes.py && uv run mypy app/knowledge/routes.py`

---

### Step 8 — Tests: `app/knowledge/tests/test_versioning.py`

Create 10 unit tests (per user spec), all using `AsyncMock(spec=KnowledgeService)` and the existing `_client()` helper:

```python
"""KB-3 Document Versioning tests."""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user
from app.knowledge.exceptions import DocumentVersionConflictError
from app.knowledge.routes import get_service
from app.knowledge.schemas import (
    DocumentDiffResponse,
    DocumentResponse,
    DocumentVersionItem,
    SearchRequest,
)
from app.knowledge.service import KnowledgeService

# Reuse helpers from test_routes.py by importing:
from app.knowledge.tests.test_routes import (
    _client,
    _make_doc_response,
    _mock_admin_user,
    _mock_service,
)


# --- 1. Version creation (v1) ------------------------------------------------

@pytest.mark.asyncio
async def test_ingest_first_upload_creates_v1() -> None:
    """A brand-new title uploads as version=1 with no parent."""
    ...


@pytest.mark.asyncio
async def test_ingest_same_title_increments_to_v2_and_sets_parent() -> None:
    """Re-upload with same (title, domain) creates v2 pointing to v1."""
    ...


# --- 2. Superseded marking --------------------------------------------------

@pytest.mark.asyncio
async def test_ingest_marks_previous_as_superseded() -> None:
    """When v2 is created, repository.mark_superseded(v1.id) is called exactly once."""
    ...


# --- 3. Diff generation ------------------------------------------------------

@pytest.mark.asyncio
async def test_get_document_diff_returns_unified_diff() -> None:
    """Diff between two known chunk sets produces expected +/- lines counts."""
    ...


@pytest.mark.asyncio
async def test_get_document_diff_rejects_same_version() -> None:
    """v1 == v2 raises DocumentVersionConflictError (→ 422)."""
    ...


# --- 4. Search latest-only ---------------------------------------------------

def test_search_defaults_to_latest_only() -> None:
    """POST /search without include_superseded forwards include_superseded=False to service."""
    ...


def test_list_documents_defaults_to_latest_only() -> None:
    """GET /documents forwards include_superseded=False by default."""
    ...


# --- 5. Search with superseded ----------------------------------------------

def test_search_with_include_superseded_returns_all() -> None:
    """POST /search with include_superseded=true forwards through."""
    ...


# --- 6. Version history endpoint --------------------------------------------

def test_get_document_versions_returns_descending_chain() -> None:
    """GET /documents/{id}/versions returns v2, v1 in that order."""
    ...


def test_get_document_versions_404_for_unknown_id() -> None:
    """Unknown document_id → 404 from DocumentNotFoundError."""
    ...
```

Fill in each body using the existing service/route mock patterns from `test_routes.py`. All tests are pure unit (no DB, no real files).

**Validation:** `uv run pytest app/knowledge/tests/test_versioning.py -v`

---

### Step 9 — Repository integration tests

Add to `app/knowledge/tests/test_repository.py`:

```python
@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_latest_by_title_domain_filters_to_is_latest(
    repo: KnowledgeRepository, mock_db: AsyncMock,
) -> None:
    """Ensures the repository query includes `is_latest=true` predicate."""
    ...


@pytest.mark.asyncio
@pytest.mark.integration
async def test_list_versions_collects_chain(
    repo: KnowledgeRepository, mock_db: AsyncMock,
) -> None:
    """BFS collects v1→v2→v3, returns ordered by version DESC."""
    ...
```

**Validation:** `uv run pytest app/knowledge/tests/test_repository.py -v -m integration`

---

### Step 10 — Full validation

```bash
uv run ruff format app/knowledge/ alembic/versions/w7x8y9z0a1b2_add_document_versions.py
uv run ruff check app/knowledge/ alembic/versions/w7x8y9z0a1b2_add_document_versions.py
uv run pyright app/knowledge/
uv run mypy app/knowledge/
uv run pytest app/knowledge/ -v
uv run pytest app/tests/test_security.py -v   # convention coverage for new endpoints
```

## Preflight Warnings

Fragile patterns to keep in mind while editing (flagged by test scout):

1. **Anti-pattern #13** — When adding to `_client()`, keep `limiter.enabled = False` inside the helper function body. Don't hoist to module scope.
2. **Anti-pattern #56** — Don't add new `app.dependency_overrides[...] = ...` at module level. Reuse the `_setup_auth_override` autouse fixture.
3. **Anti-pattern #60** — For any new async mock (e.g. `repository.mark_superseded`), use `AsyncMock`, never `MagicMock(side_effect=async_fn)`.
4. **Anti-pattern #11/#29** — `DocumentResponse` gets three new fields. Every constructor (service code + test factories `_make_doc_response`, repository `to_response` helpers) must be updated in the **same step** as the schema change. Grep: `DocumentResponse(` and `make_document(` before running tests.
5. **Anti-pattern #40 / B008** — All new `Query(...)` defaults need `# noqa: B008` inline comments.
6. **Anti-pattern #39** — `difflib` has no `date` conflict. Safe to use `import difflib`.
7. **Cascade hazard** — *Never* call `delete` on the old `Document` in the supersede path. `ondelete="CASCADE"` on chunks would wipe search data. Only `UPDATE`.
8. **Parent-FK cycle guard** — `_find_chain_root` is capped at 100 hops defensively. If data corruption ever creates a cycle (shouldn't — FK is directional and `parent_document_id` is set at insert time), we bail instead of looping forever.

## Security Checklist (endpoints + input)

For every endpoint added/modified (3 total: `/versions`, `/diff`, plus query-param additions to `/search` and `/documents`):

- [x] `require_role("admin", "editor", "dispatcher")` dependency on new GET endpoints (matches existing list/get pattern).
- [x] `@limiter.limit("30/minute")` on both new endpoints.
- [x] Pydantic response models (`DocumentVersionItem`, `DocumentDiffResponse`) — no raw dict leakage.
- [x] Error responses flow through `AppError` (no internal type leakage).
- [x] `Query(..., ge=1, le=10_000)` bounds on `v1`/`v2` — prevents negative/huge values.
- [x] `include_superseded` defaults to `False` (safe default — newer-only search).
- [x] No ILIKE queries introduced. `get_latest_by_title_domain` uses exact equality; `escape_like()` not required.
- [x] No new file handling — existing upload path security (magic bytes, sanitization, 50MB stream cap) auto-applies.

## Verification

- [ ] `uv run alembic upgrade head` applies cleanly on a fresh DB; `uv run alembic downgrade -1` reverses cleanly.
- [ ] `make check` passes (lint + types + tests).
- [ ] `make security-audit-quick` passes.
- [ ] Pyright errors ≤ **0** (baseline).
- [ ] Mypy errors ≤ **0** (baseline).
- [ ] `app/knowledge/tests/test_versioning.py` — 10 tests pass.
- [ ] `app/knowledge/tests/test_repository.py` — 2 new integration tests pass (existing 16 still pass).
- [ ] `app/tests/test_security.py` — convention tests auto-pick-up new endpoints (auth required + rate-limited).
- [ ] Manual smoke: upload `SOP-001.pdf` → `{version: 1, is_latest: true, parent_document_id: null}`; re-upload same file → new row with `{version: 2, is_latest: true, parent_document_id: 1}`, prior row reads `{status: "superseded", is_latest: false}`; `GET /v1/documents/1/versions` returns both; `GET /v1/documents/1/diff?v1=1&v2=2` returns a unified diff with non-zero line counts; `POST /v1/knowledge/search {"query":"SOP"}` returns only v2 by default, both when `include_superseded: true`.
