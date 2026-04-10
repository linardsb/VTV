# Plan: AI-4.2 Parent-Child Chunk Model

## Context

Extend the heading-aware semantic chunker (AI-4.1, commit `cae2ecf`) to emit a **parent + child** chunk hierarchy. When a paragraph-level child chunk matches a query, the search response can return the surrounding section (parent) as additional context — critical for SOPs and procedures where steps reference earlier passages.

**What changes:**
- `DocumentChunk` model gains 3 nullable columns: `parent_chunk_id` (self-FK), `heading_path`, `section_type`
- `SemanticChunker` (`chunking.py`) emits one **parent** per multi-paragraph section + **child** chunks for each paragraph; standalone single-paragraph sections remain leaf chunks (no parent, no children)
- `KnowledgeService.ingest_document()` performs a two-phase insert: parents flush first to obtain DB IDs, children are then linked via `parent_chunk_id` and committed
- Migration adds the columns + self-referential FK + index

**Out of scope (deferred):**
- Search-time parent expansion in `service.py:search()` (a follow-up: adds a section "if `chunk.parent_chunk_id`, fetch and attach parent content to `SearchResult`")
- Schema/response surfacing of parent context (leave `SearchResult` unchanged for now)
- New settings/flags

The DB shape and chunker output land in this slice; the retrieval-side use of parent context is its own slice (AI-4.3 territory).

## Security Context Assessment

| Context | Active? | Reason |
|---|---|---|
| CTX-AUTH | No | No auth/session changes |
| CTX-RBAC | No | No new endpoints; existing knowledge endpoints unchanged |
| CTX-FILE | No | Ingestion path unchanged; chunking is internal |
| CTX-AGENT | No | No agent tool surface changes |
| CTX-INFRA | No | No Docker/nginx/config changes |
| CTX-INPUT | **Marginal** | All new fields populated by trusted server-side code (chunker output). `heading_path` derives from user-uploaded markdown but is bounded by document size and stored as `Text`. No injection vector — never executed, never rendered raw. |

**Conclusion:** Pure internal model + chunker change. No security checklist items needed beyond existing model conventions.

## Research Summary

### Current state (Agent 1 — Researcher)

- **`app/knowledge/models.py:71-88`** — `DocumentChunk(Base, TimestampMixin)` with 6 fields (`id`, `document_id`, `content`, `chunk_index`, `embedding` Vector(1024), `metadata_json`). No `__table_args__`.
- **`app/knowledge/chunking.py:12-20`** — `ChunkResult` dataclass: `content`, `chunk_index`, `metadata: dict[str, str | int | None]`.
- **`app/knowledge/chunking.py:166-173`** — internal `_Section` carries `heading_level`, `heading_text`, `heading_path`, `content`.
- **`app/knowledge/chunking.py:323-385`** — `chunk_text_semantic()` pipeline: `_extract_sections` → `_merge_small_sections` → `_split_large_sections` → flat `ChunkResult` list with heading metadata in `.metadata`.
- **`app/knowledge/service.py:250-288`** — ingestion calls semantic chunker, embeds all `c.content`, builds `DocumentChunk(...)` in a single list comprehension, calls `repository.bulk_create_chunks(chunk_objects)` (single commit), then `update_document_status(... chunk_count)`.
- **`app/knowledge/repository.py:251-258`** — `bulk_create_chunks(chunks)` does `add_all(chunks)` + `commit()`.
- **`app/knowledge/repository.py:226-240`** — `get_chunks_by_document` orders by `chunk_index`. **Search methods (`search_vector`, `search_fulltext`) return `(DocumentChunk, Document, score)` tuples** — adding nullable columns is non-breaking.
- **`app/knowledge/schemas.py:117-123`** — `DocumentChunkResponse` only carries `chunk_index` + `content`. `SearchResult` (lines 158-169) carries `metadata_json` which already shuttles heading info as JSON. **No schema changes required for this slice.**
- **`app/knowledge/router.py`** (query routing, signal-based) — does NOT inspect chunks. Unaffected.
- **Migration template:** `alembic/versions/f3a4b5c6d7e8_add_evergreen_to_documents.py` (latest, 2026-04-09). Down-revision is `e2f3a4b5c6d7`. Style: pure `op.add_column` / `op.drop_column`.
- **FK pattern reference:** `e2f3a4b5c6d7_add_geofences_tables.py` shows `sa.ForeignKeyConstraint(["geofence_id"], ["geofences.id"], ondelete="CASCADE")`.
- **Shared utilities already imported in target files:** `Base`, `TimestampMixin`, `Mapped`, `mapped_column`, `ForeignKey`, `Integer`, `String`, `Text`. No new imports needed beyond `String` for the new columns.

### Test landscape (Agent 2 — Test Scout)

- **`app/knowledge/tests/test_chunking.py`** — 18 tests (7 fixed-size + 11 semantic) using fixtures `sample_latvian_text`, `sample_english_text` from `conftest.py`. All pure-function tests, no DB.
- **`app/knowledge/tests/test_repository.py:40-54`** — `make_chunk(**overrides)` factory:
  ```python
  def make_chunk(**overrides: object) -> DocumentChunk: ...
  ```
  Defaults include `id`, `document_id`, `content`, `chunk_index`, `embedding=None`, `metadata_json=None`, `created_at`, `updated_at`. **Adding 3 nullable defaults here is the only factory change needed.**
- **`app/knowledge/tests/conftest.py`** — only fixtures: `sample_upload`, `sample_latvian_text`, `sample_english_text`. No DB session here.
- **No dedicated migration tests** — repo runs alembic in CI/Docker, not via test suite.
- **No security convention test scans `DocumentChunk` model** — adding fields is safe wrt `app/tests/test_security.py`.

### Fragile patterns flagged (Agent 2)

These will break or need attention when chunks roughly double in count:

1. `app/knowledge/tests/test_repository.py:229` — `mock_db.add_all.assert_called_once_with(chunks)` in `test_bulk_create_chunks`. **Two-phase insert means `add_all` is called twice.** Test must be updated.
2. `app/knowledge/tests/test_dms.py:136` — `assert len(result.chunks) == 3` in `test_get_document_content`. Will need adjustment if the underlying fixture's chunker output changes; **but** this test uses a mocked chunk list, so safe IF the mock fixture isn't auto-regenerated. Verify and update if needed.
3. `app/knowledge/tests/test_repository.py:30` — `make_document` fixture default `chunk_count=3`. Doc-level field, unrelated. Safe.
4. `app/knowledge/service.py:275-284` — index-based comprehension `for i in range(len(chunks))`. Stays index-based but the source `chunks` list will now contain ParentChunkResult markers we must handle.
5. **No tuple unpacking issues** — `search_vector` returns 3-tuples; nullable column additions don't change arity.

### Type-check baseline (Agent 3)

| Target | Pyright | Mypy | Ruff |
|---|---|---|---|
| `app/knowledge/` (full dir) | **0** | **3** (all in unrelated `app/core/agents/...`, pre-existing) | clean |
| `models.py` + `chunking.py` only | **0** | **0** | clean |

**Acceptance gate:** After implementation, `uv run pyright app/knowledge/models.py app/knowledge/chunking.py app/knowledge/service.py app/knowledge/repository.py` must report **0 errors**, and `uv run mypy app/knowledge/ 2>&1 | grep -c "^app/knowledge/"` must be **0** (the 3 unrelated mypy errors must remain confined to `app/core/agents/`).

## Files to Create/Modify

| Action | File | Purpose |
|---|---|---|
| UPDATE | `app/knowledge/models.py` | Add `parent_chunk_id`, `heading_path`, `section_type` to `DocumentChunk` |
| CREATE | `alembic/versions/{rev}_add_parent_child_to_chunks.py` | Migration: 3 columns + self-FK + index |
| UPDATE | `app/knowledge/chunking.py` | Promote `heading_path`/`section_type` to `ChunkResult` fields; add `is_parent`, `parent_index`; add `_classify_section_type`; rewrite emission loop in `chunk_text_semantic` to produce parent+child pairs for multi-paragraph sections |
| UPDATE | `app/knowledge/service.py` | Two-phase insert in `ingest_document`: build parent `DocumentChunk` objects, flush via repo, resolve `parent_chunk_id` for children, commit |
| UPDATE | `app/knowledge/repository.py` | Add `flush_only: bool = False` to `bulk_create_chunks`; on `flush_only=True`, call `flush()` instead of `commit()` so caller can read parent IDs before inserting children |
| UPDATE | `app/knowledge/tests/test_repository.py` | Update `make_chunk` factory; update `test_bulk_create_chunks` for two-phase semantics; add tests for `flush_only` |
| UPDATE | `app/knowledge/tests/test_chunking.py` | Add ≥6 new tests for parent/child emission, section_type classification, heading_path field, single-paragraph fallback |
| UPDATE | `app/knowledge/tests/conftest.py` | Add `sample_multi_paragraph_section_text` fixture for parent/child tests (only if needed) |

**No changes to:** `schemas.py`, `routes.py`, `router.py`, `rerank.py`, `query_router.py`, `embedding.py`, `processing.py`, `app/main.py`.

## Implementation Steps

### Step 1 — Extend `ChunkResult` and add classifier (`app/knowledge/chunking.py`)

**Edit `app/knowledge/chunking.py:12-20`** to add 4 new fields to `ChunkResult`:

```python
@dataclass
class ChunkResult:
    """A single chunk of text with position metadata."""

    content: str
    chunk_index: int
    metadata: dict[str, str | int | None] = field(
        default_factory=lambda: dict[str, str | int | None]()
    )
    heading_path: str | None = None
    section_type: str | None = None
    is_parent: bool = False
    parent_index: int | None = None  # positional index in result list, NOT a DB id
```

`heading_path` and `section_type` are duplicated from `.metadata` to first-class fields so the service can pass them straight to model columns without re-parsing JSON. Existing metadata dict is preserved unchanged for the JSON-encoded `metadata_json` column.

**Add `_classify_section_type` helper** (place after `_split_large_sections`, before `chunk_text_semantic`, around line 321):

```python
_LIST_LINE_RE = re.compile(r"^\s*([-*+]|\d+[.)])\s+")
_TABLE_SEP_RE = re.compile(r"\|.*\|")


def _classify_section_type(content: str) -> str:
    """Heuristically classify a section's content type.

    Returns one of: "heading", "body", "list", "table".
    Used to populate ``DocumentChunk.section_type`` so retrieval can
    boost or filter by structural role (e.g. lists for step procedures).
    """
    stripped = content.strip()
    if not stripped:
        return "body"

    lines = [line for line in stripped.split("\n") if line.strip()]
    if not lines:
        return "body"

    # Markdown table: at least 2 pipe lines and a separator row of dashes
    if sum(1 for line in lines if _TABLE_SEP_RE.search(line)) >= 2 and any(
        re.match(r"^\s*\|?[\s:|-]+\|[\s:|-]+\|?\s*$", line) for line in lines
    ):
        return "table"

    # List: 60%+ of non-empty lines look like list items, with a min of 2
    list_lines = sum(1 for line in lines if _LIST_LINE_RE.match(line))
    if list_lines >= 2 and list_lines >= len(lines) * 0.6:
        return "list"

    # Heading-only: a single short line that looks like a header (no body)
    if len(lines) == 1 and len(stripped) <= 80:
        return "heading"

    return "body"
```

**Validation:** `uv run ruff format app/knowledge/chunking.py && uv run ruff check app/knowledge/chunking.py && uv run pyright app/knowledge/chunking.py && uv run mypy app/knowledge/chunking.py`

### Step 2 — Rewrite emission loop in `chunk_text_semantic` (`app/knowledge/chunking.py:323-385`)

Replace the final emission loop (lines 363-384) with parent+child emission. Keep the `_extract_sections → _merge_small_sections → _split_large_sections` pipeline unchanged.

```python
    sections = _merge_small_sections(sections, min_size, target_size)
    sections = _split_large_sections(sections, max_size, chunk_overlap)

    results: list[ChunkResult] = []
    next_index = 0

    for section in sections:
        content = section.content
        if not content.strip():
            continue

        char_start = text.find(content[:80]) if len(content) >= 80 else text.find(content)
        if char_start == -1:
            char_start = 0
        char_end = char_start + len(content)

        heading_path = section.heading_path or None
        section_type = _classify_section_type(content)

        # Split into paragraph children. Empty results = single paragraph.
        paragraphs = [p.strip() for p in re.split(r"\n{2,}", content) if p.strip()]

        # Single paragraph (or empty after split) → leaf chunk, no parent/child
        if len(paragraphs) <= 1:
            metadata: dict[str, str | int | None] = {
                "heading_path": heading_path,
                "heading_level": section.heading_level if section.heading_level > 0 else None,
                "char_start": char_start,
                "char_end": char_end,
            }
            results.append(
                ChunkResult(
                    content=content,
                    chunk_index=next_index,
                    metadata=metadata,
                    heading_path=heading_path,
                    section_type=section_type,
                    is_parent=False,
                    parent_index=None,
                )
            )
            next_index += 1
            continue

        # Multi-paragraph → emit one parent + N children
        parent_metadata: dict[str, str | int | None] = {
            "heading_path": heading_path,
            "heading_level": section.heading_level if section.heading_level > 0 else None,
            "char_start": char_start,
            "char_end": char_end,
            "child_count": len(paragraphs),
        }
        parent_position = next_index
        results.append(
            ChunkResult(
                content=content,
                chunk_index=next_index,
                metadata=parent_metadata,
                heading_path=heading_path,
                section_type=section_type,
                is_parent=True,
                parent_index=None,
            )
        )
        next_index += 1

        cursor = char_start
        for para in paragraphs:
            para_start = text.find(para, cursor) if para else cursor
            if para_start == -1:
                para_start = cursor
            para_end = para_start + len(para)
            cursor = para_end
            child_metadata: dict[str, str | int | None] = {
                "heading_path": heading_path,
                "heading_level": section.heading_level if section.heading_level > 0 else None,
                "char_start": para_start,
                "char_end": para_end,
            }
            results.append(
                ChunkResult(
                    content=para,
                    chunk_index=next_index,
                    metadata=child_metadata,
                    heading_path=heading_path,
                    section_type=_classify_section_type(para),
                    is_parent=False,
                    parent_index=parent_position,
                )
            )
            next_index += 1

    return results
```

**Notes:**
- Single-paragraph sections (the common case for tight SOPs after `_merge_small_sections`) stay as leaf chunks — no extra DB rows.
- Multi-paragraph sections produce 1 parent + N children where each child is one paragraph.
- `parent_index` references the parent's **position in the result list**, NOT a DB id. The service resolves this to a DB id after flushing parents.
- Both parent and children are searchable (both get embedded by service).
- The fallback path at line 357-358 (no headings → delegate to `chunk_text`) is unchanged: `chunk_text` returns leaf chunks with `is_parent=False`, `parent_index=None`.

**Validation:** `uv run ruff format app/knowledge/chunking.py && uv run ruff check app/knowledge/chunking.py && uv run pyright app/knowledge/chunking.py && uv run mypy app/knowledge/chunking.py`

### Step 3 — Add columns to `DocumentChunk` model (`app/knowledge/models.py:71-88`)

Add `String` to the existing imports (already imported on line 11). Add 3 mapped columns + `__table_args__` index. Edit the class:

```python
class DocumentChunk(Base, TimestampMixin):
    """Document chunk with vector embedding for similarity search.

    Each chunk stores extracted text and its vector embedding.
    The embedding column uses pgvector's Vector type for cosine similarity search.

    Parent-child relationships (AI-4.2): a multi-paragraph section is stored
    as one ``parent`` chunk plus one ``child`` chunk per paragraph. Children
    reference their parent via ``parent_chunk_id`` so retrieval can return
    the surrounding section context when a paragraph matches.
    """

    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding = mapped_column(Vector(1024))
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    parent_chunk_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("document_chunks.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    heading_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    section_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
```

**Why these types:**
- `parent_chunk_id` — nullable Integer FK with CASCADE so deleting a section parent removes orphan children. Indexed because retrieval will lookup-by-parent.
- `heading_path` — `String(500)`. Heading paths like "Safety > Emergency Procedures > Route Deviation" rarely exceed 500 chars; bounded to keep B-tree indexes optional and avoid Text overhead.
- `section_type` — `String(20)`. Constrained to literal vocabulary `"heading" | "body" | "list" | "table"`.

**No `__table_args__` needed** — column-level `index=True` on `parent_chunk_id` is sufficient.

**Validation:** `uv run ruff format app/knowledge/models.py && uv run ruff check app/knowledge/models.py && uv run pyright app/knowledge/models.py && uv run mypy app/knowledge/models.py`

### Step 4 — Create alembic migration

**Determine revision id:** check `alembic/versions/` for the most recent down_revision chain. Latest is `f3a4b5c6d7e8` (`add_evergreen_to_documents`). New revision must `Revises: f3a4b5c6d7e8`.

**Create file:** `alembic/versions/g5h6i7j8k9l0_add_parent_child_to_chunks.py`

```python
"""Add parent-child hierarchy columns to document_chunks.

Revision ID: g5h6i7j8k9l0
Revises: f3a4b5c6d7e8
Create Date: 2026-04-10
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "g5h6i7j8k9l0"
down_revision: str | None = "f3a4b5c6d7e8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "document_chunks",
        sa.Column("parent_chunk_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "document_chunks",
        sa.Column("heading_path", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "document_chunks",
        sa.Column("section_type", sa.String(length=20), nullable=True),
    )
    op.create_foreign_key(
        "fk_document_chunks_parent_chunk_id",
        "document_chunks",
        "document_chunks",
        ["parent_chunk_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_document_chunks_parent_chunk_id",
        "document_chunks",
        ["parent_chunk_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_document_chunks_parent_chunk_id", table_name="document_chunks")
    op.drop_constraint(
        "fk_document_chunks_parent_chunk_id",
        "document_chunks",
        type_="foreignkey",
    )
    op.drop_column("document_chunks", "section_type")
    op.drop_column("document_chunks", "heading_path")
    op.drop_column("document_chunks", "parent_chunk_id")
```

**Note:** Revision id `g5h6i7j8k9l0` is illustrative — generate a real one with `make db-revision m="add parent_child to chunks"` if alembic insists on its own hash, OR use this static hex if the project's `script_location` allows manual ids (it does, per existing migrations like `f3a4b5c6d7e8`).

**Validation:**
```bash
make db && sleep 2 && make db-migrate
# Verify columns exist:
docker compose exec db psql -U postgres -d vtv -c "\d document_chunks"
# Should show parent_chunk_id, heading_path, section_type
```

### Step 5 — Add `flush_only` to repository (`app/knowledge/repository.py:251-258`)

```python
async def bulk_create_chunks(
    self,
    chunks: list[DocumentChunk],
    *,
    flush_only: bool = False,
) -> None:
    """Insert chunks in bulk.

    When ``flush_only=True`` the session is flushed instead of committed,
    which assigns primary-key ids on each ORM instance without ending the
    transaction. The caller is then responsible for issuing a final commit
    (typically via a second call with ``flush_only=False``). This enables
    two-phase parent/child inserts where children must reference
    parent ids that don't yet exist at construction time.
    """
    self.db.add_all(chunks)
    if flush_only:
        await self.db.flush()
    else:
        await self.db.commit()
```

**Validation:** `uv run ruff format app/knowledge/repository.py && uv run pyright app/knowledge/repository.py && uv run mypy app/knowledge/repository.py`

### Step 6 — Two-phase insert in service (`app/knowledge/service.py:274-288`)

Replace the chunk-build/store block (lines 274-288) with:

```python
            # Build parent and child chunk objects.
            # Parents must flush first so children can reference parent ids.
            parent_objects: list[DocumentChunk] = []
            parent_position_to_obj: dict[int, DocumentChunk] = {}
            child_specs: list[tuple[ChunkResult, list[float], int]] = []
            leaf_specs: list[tuple[ChunkResult, list[float]]] = []

            for chunk_result, embedding in zip(chunks, embeddings, strict=True):
                if chunk_result.is_parent:
                    obj = DocumentChunk(
                        document_id=doc.id,
                        content=chunk_result.content,
                        chunk_index=chunk_result.chunk_index,
                        embedding=embedding,
                        metadata_json=(
                            json.dumps(chunk_result.metadata)
                            if chunk_result.metadata
                            else None
                        ),
                        parent_chunk_id=None,
                        heading_path=chunk_result.heading_path,
                        section_type=chunk_result.section_type,
                    )
                    parent_objects.append(obj)
                    parent_position_to_obj[chunk_result.chunk_index] = obj
                elif chunk_result.parent_index is not None:
                    child_specs.append((chunk_result, embedding, chunk_result.parent_index))
                else:
                    leaf_specs.append((chunk_result, embedding))

            # Phase 1: flush parents to obtain ids
            if parent_objects:
                await self.repository.bulk_create_chunks(parent_objects, flush_only=True)

            # Phase 2: build children + leaves with resolved parent ids
            child_and_leaf_objects: list[DocumentChunk] = []
            for chunk_result, embedding, parent_position in child_specs:
                parent_obj = parent_position_to_obj.get(parent_position)
                parent_id = parent_obj.id if parent_obj is not None else None
                child_and_leaf_objects.append(
                    DocumentChunk(
                        document_id=doc.id,
                        content=chunk_result.content,
                        chunk_index=chunk_result.chunk_index,
                        embedding=embedding,
                        metadata_json=(
                            json.dumps(chunk_result.metadata)
                            if chunk_result.metadata
                            else None
                        ),
                        parent_chunk_id=parent_id,
                        heading_path=chunk_result.heading_path,
                        section_type=chunk_result.section_type,
                    )
                )
            for chunk_result, embedding in leaf_specs:
                child_and_leaf_objects.append(
                    DocumentChunk(
                        document_id=doc.id,
                        content=chunk_result.content,
                        chunk_index=chunk_result.chunk_index,
                        embedding=embedding,
                        metadata_json=(
                            json.dumps(chunk_result.metadata)
                            if chunk_result.metadata
                            else None
                        ),
                        parent_chunk_id=None,
                        heading_path=chunk_result.heading_path,
                        section_type=chunk_result.section_type,
                    )
                )

            # Phase 3: commit children + leaves (parents commit with this transaction)
            await self.repository.bulk_create_chunks(child_and_leaf_objects)
            await self.repository.update_document_status(
                doc.id, "completed", None, len(chunks)
            )
```

**Add import** at the top of `service.py` if not already present:
```python
from app.knowledge.chunking import ChunkResult  # for type annotation in tuples
```

**Notes:**
- `chunks` contains the unified parent + child + leaf list from `chunk_text_semantic`. `chunk_count` stays `len(chunks)` — total rows including parents.
- Both phases share the same `AsyncSession` (via `self.repository.db`), so phase-1 flush + phase-3 commit form a single transaction. Failure in phase 3 rolls back parents too.
- `embeddings[]` aligns 1:1 with `chunks[]` because `texts = [c.content for c in chunks]` at line 271 already iterates the unified list.
- `strict=True` on `zip` is enforced by Python 3.12+ ruff `B905` rule.

**Validation:** `uv run ruff format app/knowledge/service.py && uv run pyright app/knowledge/service.py && uv run mypy app/knowledge/service.py`

### Step 7 — Update `make_chunk` factory and existing test (`app/knowledge/tests/test_repository.py`)

Edit lines 40-54:

```python
def make_chunk(**overrides: object) -> DocumentChunk:
    """Factory for DocumentChunk instances with sensible defaults."""
    now = utcnow()
    defaults: dict[str, object] = {
        "id": 1,
        "document_id": 1,
        "content": "Sample chunk text",
        "chunk_index": 0,
        "embedding": None,
        "metadata_json": None,
        "parent_chunk_id": None,
        "heading_path": None,
        "section_type": None,
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    return DocumentChunk(**defaults)
```

Update `test_bulk_create_chunks` (around line 216-229) — the assertion that `add_all` was called once is no longer accurate when callers may use `flush_only`. Replace:

```python
@pytest.mark.asyncio
@pytest.mark.integration
async def test_bulk_create_chunks(repo: KnowledgeRepository, mock_db: AsyncMock) -> None:
    chunks = [
        make_chunk(id=i, document_id=1, chunk_index=i, content=f"Chunk {i} text")
        for i in range(5)
    ]
    mock_db.add_all = MagicMock()
    mock_db.commit = AsyncMock()

    await repo.bulk_create_chunks(chunks)

    mock_db.add_all.assert_called_once_with(chunks)
    mock_db.commit.assert_awaited_once()
```

with the same body plus a new test for `flush_only`:

```python
@pytest.mark.asyncio
@pytest.mark.integration
async def test_bulk_create_chunks_flush_only(
    repo: KnowledgeRepository, mock_db: AsyncMock
) -> None:
    chunks = [make_chunk(id=i, document_id=1, chunk_index=i) for i in range(3)]
    mock_db.add_all = MagicMock()
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()

    await repo.bulk_create_chunks(chunks, flush_only=True)

    mock_db.add_all.assert_called_once_with(chunks)
    mock_db.flush.assert_awaited_once()
    mock_db.commit.assert_not_called()
```

**Validation:** `uv run ruff format app/knowledge/tests/test_repository.py && uv run pyright app/knowledge/tests/test_repository.py`

### Step 8 — Add chunker tests (`app/knowledge/tests/test_chunking.py`)

Add the following tests at the end of the file (≥6 new, total satisfies the ≥10-test requirement when combined with test_repository.py additions):

```python
def test_semantic_single_paragraph_section_is_leaf() -> None:
    """A section with one paragraph stays a leaf chunk (no parent/child)."""
    text = "# Title\n\nFirst section body. Just one paragraph here."
    result = chunk_text_semantic(text, target_size=2000, min_size=10)
    assert all(not c.is_parent for c in result)
    assert all(c.parent_index is None for c in result)


def test_semantic_multi_paragraph_section_emits_parent_and_children() -> None:
    """A multi-paragraph section becomes one parent + N child paragraphs."""
    text = (
        "# Procedure\n\n"
        "First paragraph of the procedure section.\n\n"
        "Second paragraph with additional steps.\n\n"
        "Third and final paragraph wraps it up."
    )
    result = chunk_text_semantic(text, target_size=5000, min_size=1, max_size=5000)
    parents = [c for c in result if c.is_parent]
    children = [c for c in result if c.parent_index is not None]
    assert len(parents) == 1
    assert len(children) == 3
    # All children point to the parent's positional index
    assert all(c.parent_index == parents[0].chunk_index for c in children)


def test_semantic_parent_carries_full_section_content() -> None:
    """The parent chunk's content equals the joined section body."""
    text = (
        "## Safety\n\n"
        "Stay alert at all times.\n\n"
        "Report incidents immediately."
    )
    result = chunk_text_semantic(text, target_size=5000, min_size=1, max_size=5000)
    parents = [c for c in result if c.is_parent]
    assert len(parents) == 1
    assert "Stay alert" in parents[0].content
    assert "Report incidents" in parents[0].content


def test_semantic_chunks_carry_heading_path_field() -> None:
    """heading_path is promoted to a first-class ChunkResult field."""
    text = "# A\n\n## B\n\nFirst para.\n\nSecond para."
    result = chunk_text_semantic(text, target_size=5000, min_size=1, max_size=5000)
    chunks_with_path = [c for c in result if c.heading_path]
    assert chunks_with_path
    assert any("B" in (c.heading_path or "") for c in chunks_with_path)


def test_semantic_section_type_classification_list() -> None:
    """Sections that are mostly bulleted lines are classified as 'list'."""
    text = (
        "## Steps\n\n"
        "- First step\n"
        "- Second step\n"
        "- Third step\n"
        "- Fourth step"
    )
    result = chunk_text_semantic(text, target_size=5000, min_size=1, max_size=5000)
    list_chunks = [c for c in result if c.section_type == "list"]
    assert list_chunks


def test_semantic_section_type_classification_table() -> None:
    """Markdown tables classify as 'table'."""
    text = (
        "## Routes\n\n"
        "| Route | Stops |\n"
        "|-------|-------|\n"
        "| 1     | 12    |\n"
        "| 2     | 18    |"
    )
    result = chunk_text_semantic(text, target_size=5000, min_size=1, max_size=5000)
    assert any(c.section_type == "table" for c in result)


def test_semantic_section_type_classification_body_default() -> None:
    """Plain prose sections classify as 'body'."""
    text = (
        "## Overview\n\n"
        "This is a paragraph of plain prose describing the system.\n\n"
        "Another paragraph continues the description in the same body."
    )
    result = chunk_text_semantic(text, target_size=5000, min_size=1, max_size=5000)
    body_chunks = [c for c in result if c.section_type == "body"]
    assert body_chunks


def test_semantic_no_headings_fallback_has_no_parents() -> None:
    """Fallback path (no headings) produces only leaf chunks."""
    text = "Just plain text with no structure. " * 30
    result = chunk_text_semantic(text, target_size=200, min_size=10)
    assert all(not c.is_parent for c in result)
    assert all(c.parent_index is None for c in result)
    assert all(c.heading_path is None for c in result)


def test_semantic_child_chunk_count_metadata() -> None:
    """Parent chunks record child_count in metadata."""
    text = (
        "# Doc\n\n"
        "## Section\n\n"
        "Para one.\n\nPara two.\n\nPara three."
    )
    result = chunk_text_semantic(text, target_size=5000, min_size=1, max_size=5000)
    parents = [c for c in result if c.is_parent]
    assert parents
    assert parents[0].metadata.get("child_count") == 3
```

**Validation:** `uv run ruff format app/knowledge/tests/test_chunking.py && uv run pyright app/knowledge/tests/test_chunking.py && uv run pytest app/knowledge/tests/test_chunking.py -v`

### Step 9 — Run the full check pyramid

```bash
uv run ruff format app/knowledge/
uv run ruff check app/knowledge/ --fix
uv run mypy app/knowledge/
uv run pyright app/knowledge/
uv run pytest app/knowledge/ -v
make db-migrate              # apply the new migration in dev DB
uv run pytest app/knowledge/tests/test_repository.py -v -m integration
make check                   # full project gate
```

## Preflight Warnings

| File:Line | Pattern | Mitigation |
|---|---|---|
| `app/knowledge/service.py:283` | `for i in range(len(chunks))` index-based comprehension | Replaced in Step 6 with explicit zip + per-chunk-type branching |
| `app/knowledge/tests/test_repository.py:229` | `mock_db.add_all.assert_called_once_with(chunks)` | Updated in Step 7; new `flush_only` test added alongside |
| `app/knowledge/tests/test_dms.py:136` | `assert len(result.chunks) == 3` | This test uses a hand-crafted `make_chunk` mock list (not the chunker), so it's UNAFFECTED. Verify by reading the fixture before Step 9; only update if it actually invokes `chunk_text_semantic`. |
| `app/knowledge/chunking.py:357-358` | Fallback to `chunk_text` for headingless docs | `chunk_text` returns `ChunkResult` with default `is_parent=False`, `parent_index=None`, `heading_path=None`, `section_type=None`. Service two-phase logic handles these as "leafs" naturally. |
| `app/knowledge/repository.py:226-240` | `get_chunks_by_document` orders by `chunk_index` | Still correct: parent chunk_index < child chunk_index by construction (parent emitted first). No change needed. |
| `app/knowledge/repository.py:260-354` | `search_vector` / `search_fulltext` return `(DocumentChunk, Document, score)` | Nullable column additions don't change tuple shape. Existing call sites in `service.search()` are unaffected. |

## Verification

- [ ] `uv run ruff check app/knowledge/` clean
- [ ] `uv run pyright app/knowledge/` reports **0 errors** (baseline: 0)
- [ ] `uv run mypy app/knowledge/` produces only the 3 pre-existing unrelated errors in `app/core/agents/...` (baseline: 3, none in `app/knowledge/`)
- [ ] `uv run pytest app/knowledge/tests/test_chunking.py -v` — all existing 18 tests + 9 new tests pass
- [ ] `uv run pytest app/knowledge/tests/test_repository.py -v -m integration` — `test_bulk_create_chunks` updated and `test_bulk_create_chunks_flush_only` passes
- [ ] `make db-migrate` applies cleanly; `\d document_chunks` shows the 3 new columns + FK + index
- [ ] `make check` passes (lint + types + unit tests)
- [ ] Manual integration: upload a markdown SOP via knowledge endpoint, then query the DB:
      ```sql
      SELECT id, parent_chunk_id, heading_path, section_type, length(content)
      FROM document_chunks
      WHERE document_id = (SELECT max(id) FROM documents)
      ORDER BY chunk_index;
      ```
      Expect: at least one row with `parent_chunk_id IS NULL` and `is_parent`-equivalent (multi-paragraph parent), followed by rows with `parent_chunk_id` set to that parent's id.
- [ ] No changes to `app/main.py`, `schemas.py`, or any route file
- [ ] `make security-audit-quick` passes (no new findings)

## Out-of-Scope Follow-ups (do NOT implement here)

- **AI-4.3 search-time parent expansion** in `service.py:search()`: when a child chunk surfaces in reranked results, fetch its parent and attach as `SearchResult.parent_content`. Requires adding `parent_content: str | None` to `SearchResult` schema.
- **Section-type-aware reranking**: boost `list` sections for procedural queries, `table` sections for lookup queries.
- **Backfill migration**: re-chunk existing documents to populate parent/child relationships. Existing chunks remain leaf chunks until re-ingested. Document this in the migration's docstring or release notes.
