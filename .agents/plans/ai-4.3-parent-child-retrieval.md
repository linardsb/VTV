# Plan: AI-4.3 Parent-Child Retrieval + Context Expansion

## Context

When the hybrid search pipeline returns a child chunk match, automatically fetch and attach the parent chunk content so the agent has the full surrounding section. A child chunk that matches "call depot X" is useless without the parent context "When bus breaks down on route 22, follow these steps: 1. call depot X, 2. reroute via Y, 3. notify dispatcher Z."

**What changes:**
- `KnowledgeService.search()` (`app/knowledge/service.py:475`) — after RRF fusion / rerank but before building `SearchResult`s, collect every unique `parent_chunk_id` from the surviving chunks, batch-fetch parents in one query, and attach them. Deduplicated automatically by the unique-id set.
- `SearchResult` (`app/knowledge/schemas.py:158`) gains 3 nullable fields: `parent_chunk_id`, `parent_content`, `heading_path`. Existing constructors are unaffected — all defaults `None`.
- `KnowledgeRepository` gains `get_chunks_by_ids(chunk_ids)` — single SELECT WHERE id IN (...) returning the parent chunks.
- `KnowledgeSearchResult` (`app/core/agents/tools/knowledge/schemas.py:6`) gains `parent_content: str | None` and `heading_path: str | None`.
- `search_knowledge_base()` (`app/core/agents/tools/knowledge/search_knowledge.py:128`) formats results with parent context: `"[Section: {heading_path}]\n{parent_content}\n\n[Matched passage:]\n{child_content}"`. Parent is truncated to a new `_MAX_PARENT_CHARS = 3000` budget.
- New config flag `knowledge_parent_context_enabled: bool = True` (lowercase, matches the rest of the `knowledge_*` settings group).

**Out of scope:**
- Schema migration — none needed; AI-4.2 already added `parent_chunk_id`, `heading_path`, `section_type` columns.
- Knowledge route changes — `SearchResponse` shape stays additive only. CMS document viewer is untouched.
- Reranker behavior — still operates on child contents only. Parent is purely a post-rerank context expansion.

> ⚠️ **Brief correction:** the user-provided spec said "modify `app/knowledge/repository.py:hybrid_search()`" but the orchestration actually lives in `KnowledgeService.search()` at `service.py:475`. Repository only has `search_vector()` (`repository.py:276`) and `search_fulltext()` (`repository.py:321`) as separate legs that the service fuses via RRF. Parent expansion belongs in the service where `chunk_data` is already assembled.

## Security Context Assessment

| Context | Active? | Reason |
|---|---|---|
| CTX-AUTH | No | No auth/session changes |
| CTX-RBAC | No | No new endpoints; existing knowledge endpoints unchanged |
| CTX-FILE | No | No upload/file path changes |
| CTX-AGENT | **Yes (light)** | Modifies agent tool output format. Parent content originates from server-side chunker output (already-trusted), but the JSON response now contains larger payloads. Token-efficiency guard required. |
| CTX-INFRA | No | No Docker/nginx/config changes |
| CTX-INPUT | No | No new user input surfaces; query path unchanged |

**CTX-AGENT requirements applied:**
- Parent content truncated to `_MAX_PARENT_CHARS = 3000` (matches the existing `_MAX_CONTENT_CHARS = 1500` discipline) so a 5-result response stays well under 25k tokens.
- Feature gated on `settings.knowledge_parent_context_enabled` so it can be disabled at runtime if it inflates responses unexpectedly.
- No credentials, no LLM-generated content surfaces — parent text is the same trusted document chunker output that already round-trips through search.

## Research Summary

### Knowledge service / search pipeline
- **`app/knowledge/service.py:475-623`** — `KnowledgeService.search()` is the actual hybrid orchestrator (vector + fulltext → RRF → temporal boost → rerank → confidence filter → `SearchResponse`). This is where parent expansion plugs in.
- **`service.py:540-551`** — `chunk_data: dict[int, tuple[DocumentChunk, Document]]` already holds every candidate `DocumentChunk` ORM instance, including their `parent_chunk_id` attribute (loaded eagerly via SELECT ... already by the search legs).
- **`service.py:577-594`** — final `SearchResult` build loop. Insert parent attach immediately before this loop so each result row receives its parent fields.
- **`service.py:597-607`** — confidence filter runs after `SearchResult` build; we attach parents BEFORE confidence filter so a dropped child also drops its parent fetch (cheap optimization: filter first then fetch). **Decision: filter THEN fetch parents** to minimize parent SELECTs.

### Repository
- **`app/knowledge/repository.py:226-240`** — `get_chunks_by_document(document_id)` exists but is for the entire document. We need an ID-list variant.
- **`app/knowledge/repository.py:276`** — `search_vector()` returns `(DocumentChunk, Document, distance)` tuples. `DocumentChunk.parent_chunk_id` is a regular column attribute, no relationship loading needed.
- **`app/knowledge/repository.py:251-274`** — `bulk_create_chunks(flush_only)` precedent for two-phase persistence; useful as a style reference for the new helper.

### Models
- **`app/knowledge/models.py:71-95`** — `DocumentChunk(Base, TimestampMixin)` already has `parent_chunk_id: int | None` (indexed self-FK), `heading_path: str | None`, `section_type: str | None`. AI-4.2 commit `cab0b4b`.

### Schemas
- **`app/knowledge/schemas.py:158-169`** — `SearchResult` is a flat Pydantic model. Adding 3 optional fields with `= None` defaults is non-breaking for every existing constructor (only one constructor: `service.py:583-593`).
- **`app/knowledge/schemas.py:172-178`** — `SearchResponse.results: list[SearchResult]`. Unchanged.

### Agent tool surface
- **`app/core/agents/tools/knowledge/schemas.py:6-14`** — `KnowledgeSearchResult` carries `content`, `source`, `domain`, `relevance_score`, `page_or_section`. Add 2 optional fields here.
- **`app/core/agents/tools/knowledge/search_knowledge.py:27`** — `_MAX_CONTENT_CHARS = 1500`. Add `_MAX_PARENT_CHARS = 3000`.
- **`app/core/agents/tools/knowledge/search_knowledge.py:128-138`** — formatter loop builds `KnowledgeSearchResult` per service result. This is the only formatter call site.

### Config
- **`app/core/config.py:181-227`** — knowledge settings group uses lowercase `knowledge_*` with sane defaults, comments above each block. Add `knowledge_parent_context_enabled: bool = True` next to `knowledge_semantic_chunking_enabled` (line 223).
- The user's brief said `KNOWLEDGE__PARENT_CONTEXT_ENABLED` but that's an env-var form. Pydantic settings auto-maps `KNOWLEDGE_PARENT_CONTEXT_ENABLED` env var → `knowledge_parent_context_enabled` field, so users can override via env unchanged.

### Logging conventions
- Module: `knowledge.search.*` and `agent.knowledge.search_*`. Use `_started` / `_completed` / `_failed` suffixes (existing examples at `service.py:486`, `601`, `610`; tool at `search_knowledge.py:86`, `147`, `158`).
- New events to emit:
  - `knowledge.search.parent_context_attached` (info, in service) — fields: `parent_count`, `child_count`, `dedupe_ratio`
  - Reuse `agent.knowledge.search_completed` and add `parent_contexts_count` field

## Test Landscape

### Existing test files (Agent 2)

| File | Purpose |
|---|---|
| `app/knowledge/tests/test_repository.py` (616 lines) | Integration tests w/ AsyncMock session. Has `make_chunk(**overrides)` factory at line 40 that already includes `parent_chunk_id: None` default. |
| `app/knowledge/tests/test_chunking.py` (280 lines) | Pure unit tests for parent-child emission (AI-4.2). Untouched here. |
| `app/knowledge/tests/conftest.py` | `sample_upload`, `sample_latvian_text`, `sample_english_text`. Untouched. |
| `app/core/agents/tools/knowledge/tests/test_search_knowledge.py` (244 lines) | Mocks `AsyncSessionLocal` + `KnowledgeService` class, asserts on JSON-serialized result fields. **Where new agent tool tests go.** |

### Fixtures & factories

- **`test_repository.py:40`** — `make_chunk(**overrides) -> DocumentChunk`: defaults include `id`, `document_id`, `content`, `chunk_index`, `embedding=None`, `metadata_json=None`, `parent_chunk_id=None`, `created_at`, `updated_at`. **No factory change needed** — `parent_chunk_id` already accepted.
- **`test_repository.py:15`** — `make_document(**overrides) -> Document`: includes `evergreen=False`, `created_at`, etc. Used by service-level tests via mock sessions.
- **`test_repository.py:61`** — `mock_db` AsyncMock session fixture.
- **`test_repository.py:67`** — `repo` fixture wrapping `KnowledgeRepository(mock_db)`.

### Mock patterns

- Repository tests use `AsyncMock(spec=AsyncSession)` and assert on the SQL `select()` shape via `db.execute.call_args` — pattern at `test_repository.py:276` (vector search) and similar for fulltext.
- Agent tool tests: `with patch("app.core.agents.tools.knowledge.search_knowledge.AsyncSessionLocal") as session_cm, patch("app.core.agents.tools.knowledge.search_knowledge.KnowledgeService") as svc_cls:` then mock `svc_cls.return_value.search.return_value = SearchResponse(results=[...])`. (See `test_search_knowledge.py:33-43`.)

### Fragile patterns to be aware of

| Pattern | Location | Mitigation |
|---|---|---|
| `len(results) == N` hardcoded asserts | `test_repository.py:137,145,232,276` | Repository result count is unchanged — we add a parallel `get_chunks_by_ids()` call, not a new join. **No regression risk.** |
| Exact content string asserts in agent tool tests | `test_search_knowledge.py` (~L19, L53) | New fields default `None` so existing JSON shape is additive. Pydantic `model_dump()` will include the new keys with `null` values — confirm existing tests don't do `assert json == {...exact...}` (they use `["key"] == value`). |
| `KnowledgeSearchResult(parent_content=None, heading_path=None)` constructor | New | All new constructors specify these explicitly to satisfy anti-pattern #27 (`Field(None)` constructors). |

### Coverage gaps the new tests fill

- Service-level: child chunks with same parent → single parent fetch (dedupe).
- Service-level: child with `parent_chunk_id=None` (leaf chunk) → no parent attached, no error.
- Service-level: feature flag off → no parent fetch, behavior identical to pre-AI-4.3.
- Repository-level: `get_chunks_by_ids` returns all chunks, returns empty list for empty input (no SQL issued).
- Agent tool: formatted `content` field contains `[Section: ...]` and `[Matched passage:]` markers when parent present.
- Agent tool: formatted `content` matches existing format when parent absent (back-compat).

## Type Check Baseline

Run on `2026-04-10` from the agent3 baseline:

| Path | Pyright | Mypy |
|---|---|---|
| `app/knowledge/` | **0 errors, 0 warnings, 0 informations** | Success — 0 new errors (3 pre-existing in `app/core/agents/tools/transit/static_store.py:149-150` and `app/core/agents/pipeline.py:136`, NOT in knowledge) |
| `app/core/agents/tools/knowledge/` | **0 errors, 0 warnings, 0 informations** | Success — 0 new errors (same 3 pre-existing surface via import graph) |

`/be-execute` MUST keep these counts at zero new errors in both checkers for the touched paths.

## Files to Create/Modify

| Action | File | Purpose |
|---|---|---|
| UPDATE | `app/core/config.py` | Add `knowledge_parent_context_enabled: bool = True` (~line 224) |
| UPDATE | `app/knowledge/repository.py` | Add `get_chunks_by_ids(chunk_ids)` helper after `get_chunks_by_document` (~line 240) |
| UPDATE | `app/knowledge/schemas.py` | Add 3 optional fields to `SearchResult` (line 158-169) |
| UPDATE | `app/knowledge/service.py` | Insert parent expansion block in `search()` after confidence filter, before final return (~line 600) |
| UPDATE | `app/core/agents/tools/knowledge/schemas.py` | Add `parent_content`, `heading_path` to `KnowledgeSearchResult` |
| UPDATE | `app/core/agents/tools/knowledge/search_knowledge.py` | Add `_MAX_PARENT_CHARS`, format content with parent markers (~line 128) |
| UPDATE | `app/knowledge/tests/test_repository.py` | Add tests for `get_chunks_by_ids` |
| UPDATE | `app/knowledge/tests/test_service_search_parent_context.py` (new) OR add to existing service test file | Service-level parent attach + dedupe + flag-off tests |
| UPDATE | `app/core/agents/tools/knowledge/tests/test_search_knowledge.py` | Add tests for parent context formatting |
| UPDATE | `app/core/agents/CLAUDE.md` | One-line note in "RAG retrieval" bullet adding `, ✅ parent-child context expansion (AI-4.3)` |
| UPDATE | `CLAUDE.md` | Update `knowledge/` description in Project Structure to mention parent-child context expansion |

## Implementation Steps

### Step 1 — Add config flag

**File:** `app/core/config.py`

After line 226 (`knowledge_chunk_max_size: int = 1500`), inside the `knowledge_*` block:

```python
# Parent-child retrieval (attach parent section as context for matched child chunks)
knowledge_parent_context_enabled: bool = True
knowledge_parent_context_max_chars: int = 3000
```

**Why two settings:** the byte budget needs to be tunable to throttle response size in production without recompiling.

**Validation:**
```bash
uv run ruff format app/core/config.py && uv run ruff check --fix app/core/config.py && uv run pyright app/core/config.py && uv run mypy app/core/config.py
```

### Step 2 — Repository helper: batch chunk fetch by IDs

**File:** `app/knowledge/repository.py`

After `get_chunks_by_document` (line 240), add:

```python
async def get_chunks_by_ids(self, chunk_ids: list[int]) -> list[DocumentChunk]:
    """Fetch multiple chunks by primary key in a single query.

    Used by parent-context expansion: collects all unique parent_chunk_ids
    from search results and loads them in one round-trip.

    Args:
        chunk_ids: List of DocumentChunk IDs to fetch. Empty list returns
            an empty result without issuing a query.

    Returns:
        List of DocumentChunk instances. Order is not guaranteed; callers
        that need ordering should index by ``chunk.id``.
    """
    if not chunk_ids:
        return []
    result = await self.db.execute(
        select(DocumentChunk).where(DocumentChunk.id.in_(chunk_ids))
    )
    return list(result.scalars().all())
```

Notes:
- Empty-list short-circuit avoids issuing a `WHERE id IN ()` (SQLAlchemy will warn, and it's wasteful).
- Return type matches `get_chunks_by_document` exactly.
- No `order_by` — caller deduplicates / indexes by id.

**Validation:**
```bash
uv run ruff format app/knowledge/repository.py && uv run ruff check --fix app/knowledge/repository.py && uv run pyright app/knowledge/repository.py && uv run mypy app/knowledge/repository.py
```

### Step 3 — Add optional fields to `SearchResult`

**File:** `app/knowledge/schemas.py`

Replace lines 158-169 with:

```python
class SearchResult(BaseModel):
    """Single search result with relevance score."""

    chunk_content: str
    document_id: int
    document_filename: str
    domain: str
    language: str
    chunk_index: int
    score: float
    metadata_json: str | None
    document_created_at: datetime

    # Parent-child retrieval (AI-4.3) — populated when the matched chunk
    # has a parent section and parent context expansion is enabled.
    parent_chunk_id: int | None = None
    parent_content: str | None = None
    heading_path: str | None = None
```

**Anti-pattern guard:** Anti-pattern #27 (`Field(None)` confuses pyright about required params). We use bare `int | None = None` defaults — no `Field(None, ...)` — so existing constructors at `service.py:583-593` continue to work without explicit kwargs.

**Validation:**
```bash
uv run ruff format app/knowledge/schemas.py && uv run ruff check --fix app/knowledge/schemas.py && uv run pyright app/knowledge/schemas.py && uv run mypy app/knowledge/schemas.py
```

### Step 4 — Service: parent expansion in `KnowledgeService.search()`

**File:** `app/knowledge/service.py`

In `search()` method, after the confidence filter block (after line 607 `query=request.query[:80],`) and BEFORE the `duration_ms = ...` line at 609, insert:

```python
# Parent-child context expansion (AI-4.3)
parent_count = 0
if settings.knowledge_parent_context_enabled and results:
    # Collect unique parent_chunk_ids from surviving results.
    # chunk_data still holds the ORM instances by chunk.id.
    parent_ids: set[int] = set()
    result_to_chunk: dict[int, DocumentChunk] = {}
    for r in results:
        # Find the matching chunk in chunk_data by (document_id, chunk_index)
        # — chunk.id isn't on SearchResult, so we look it up.
        for cid, (chunk, _doc) in chunk_data.items():
            if (
                chunk.document_id == r.document_id
                and chunk.chunk_index == r.chunk_index
            ):
                result_to_chunk[id(r)] = chunk
                if chunk.parent_chunk_id is not None:
                    parent_ids.add(chunk.parent_chunk_id)
                break

    if parent_ids:
        parent_chunks = await self.repository.get_chunks_by_ids(list(parent_ids))
        parents_by_id: dict[int, DocumentChunk] = {p.id: p for p in parent_chunks}
        max_chars = settings.knowledge_parent_context_max_chars
        for r in results:
            chunk = result_to_chunk.get(id(r))
            if chunk is None or chunk.parent_chunk_id is None:
                continue
            parent = parents_by_id.get(chunk.parent_chunk_id)
            if parent is None:
                continue
            r.parent_chunk_id = parent.id
            r.parent_content = parent.content[:max_chars]
            r.heading_path = parent.heading_path
            parent_count += 1

    logger.info(
        "knowledge.search.parent_context_attached",
        result_count=len(results),
        parent_count=parent_count,
        unique_parents=len(parent_ids),
    )
```

**Why id(r) lookup instead of pre-indexing by chunk.id:** `SearchResult` is built from rerank order, not from the original `chunk_data` keys. `(document_id, chunk_index)` is unique per document and is the natural join key. The double loop is O(N×M) but N≤reranker_top_k=10 and M≤reranker_top_k=10, so worst case is 100 ops — negligible vs the embedding/rerank cost above it.

**Anti-pattern guards:**
- #5 — `parent_count` and `parent_ids` are read in the log call, not unused.
- #34 — Not Redis, no `# type: ignore[misc]` needed.
- #11 — `SearchResult` has new optional fields with defaults; the constructor at `service.py:583` does NOT need updating because the new fields have defaults.

**Validation:**
```bash
uv run ruff format app/knowledge/service.py && uv run ruff check --fix app/knowledge/service.py && uv run pyright app/knowledge/service.py && uv run mypy app/knowledge/service.py
```

### Step 5 — Agent-tool schema fields

**File:** `app/core/agents/tools/knowledge/schemas.py`

Replace the file with:

```python
"""Response schemas for the knowledge base agent tool."""

from pydantic import BaseModel


class KnowledgeSearchResult(BaseModel):
    """Single search result for agent consumption."""

    document_id: int
    content: str
    source: str
    domain: str
    relevance_score: float
    page_or_section: str | None = None
    parent_content: str | None = None
    heading_path: str | None = None


class KnowledgeSearchResponse(BaseModel):
    """Search response optimized for agent token efficiency."""

    results: list[KnowledgeSearchResult]
    total_found: int
    query: str
```

**Validation:**
```bash
uv run ruff format app/core/agents/tools/knowledge/schemas.py && uv run ruff check --fix app/core/agents/tools/knowledge/schemas.py && uv run pyright app/core/agents/tools/knowledge/schemas.py && uv run mypy app/core/agents/tools/knowledge/schemas.py
```

### Step 6 — Agent tool formatter: parent + child markers

**File:** `app/core/agents/tools/knowledge/search_knowledge.py`

(a) Below line 27, add:

```python
_MAX_PARENT_CHARS = 3000
```

(b) Replace the formatter loop at lines 128-138 with:

```python
# Map to agent-optimized schema (truncate content for token efficiency).
# When the matched chunk has a parent section, include it as context using
# heading_path + parent_content markers so the agent can reason about the
# full section, not just the matched paragraph (AI-4.3).
results = []
for r in response.results:
    child_content = r.chunk_content[:_MAX_CONTENT_CHARS]
    if r.parent_content and r.heading_path:
        formatted_content = (
            f"[Section: {r.heading_path}]\n"
            f"{r.parent_content[:_MAX_PARENT_CHARS]}\n\n"
            f"[Matched passage:]\n{child_content}"
        )
    elif r.parent_content:
        formatted_content = (
            f"{r.parent_content[:_MAX_PARENT_CHARS]}\n\n"
            f"[Matched passage:]\n{child_content}"
        )
    else:
        formatted_content = child_content
    results.append(
        KnowledgeSearchResult(
            document_id=r.document_id,
            content=formatted_content,
            source=r.document_filename,
            domain=r.domain,
            relevance_score=round(r.score, 4),
            page_or_section=f"chunk {r.chunk_index}",
            parent_content=r.parent_content,
            heading_path=r.heading_path,
        )
    )
```

**Why both `formatted_content` AND raw `parent_content`:** the agent reads `content` (the merged display string), but downstream consumers (memory storage, logging) may want the raw fields for analysis. Both costs ~0 tokens since the agent only reads `content`.

**Anti-pattern guards:**
- #27 — `KnowledgeSearchResult(parent_content=..., heading_path=...)` constructor passes ALL `Field(None)`-style params explicitly even when None.
- #28 — `results = []` becomes `results: list[KnowledgeSearchResult] = []`.

Update the line `results = []` to:
```python
results: list[KnowledgeSearchResult] = []
```

(c) Update `agent.knowledge.search_completed` log call (line 147-152) to include parent count:

```python
logger.info(
    "agent.knowledge.search_completed",
    result_count=len(results),
    total_found=response.total_candidates,
    parent_contexts_count=sum(1 for r in response.results if r.parent_content),
    duration_ms=duration_ms,
)
```

**Validation:**
```bash
uv run ruff format app/core/agents/tools/knowledge/search_knowledge.py && uv run ruff check --fix app/core/agents/tools/knowledge/search_knowledge.py && uv run pyright app/core/agents/tools/knowledge/search_knowledge.py && uv run mypy app/core/agents/tools/knowledge/search_knowledge.py
```

### Step 7 — Repository tests

**File:** `app/knowledge/tests/test_repository.py`

Add new tests after the existing chunk tests:

```python
@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_chunks_by_ids_returns_matching_chunks(
    repo: KnowledgeRepository, mock_db: AsyncMock
) -> None:
    """get_chunks_by_ids should issue one SELECT and return matched chunks."""
    chunks = [make_chunk(id=10), make_chunk(id=11)]
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = chunks
    mock_db.execute.return_value = mock_result

    result = await repo.get_chunks_by_ids([10, 11])

    assert len(result) == 2
    assert {c.id for c in result} == {10, 11}
    mock_db.execute.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_chunks_by_ids_empty_list_no_query(
    repo: KnowledgeRepository, mock_db: AsyncMock
) -> None:
    """Empty input should short-circuit without issuing SQL."""
    result = await repo.get_chunks_by_ids([])

    assert result == []
    mock_db.execute.assert_not_called()
```

**Anti-pattern guards:** #26 — both helpers are `-> None`; #6 — no unused vars; #28 — list literal `[]` returned from helper, not a literal under test.

**Validation:**
```bash
uv run pytest app/knowledge/tests/test_repository.py::test_get_chunks_by_ids_returns_matching_chunks app/knowledge/tests/test_repository.py::test_get_chunks_by_ids_empty_list_no_query -v
```

### Step 8 — Service tests for parent expansion

**File:** `app/knowledge/tests/test_repository.py` (re-use the same test file — service search is currently tested through this file's mocks; or create `test_service_search.py` if a fresh file is preferred — match whatever convention the previous AI-* slices used; AI-4.2 added tests inline so do the same).

Add 3 tests:

```python
@pytest.mark.asyncio
@pytest.mark.integration
async def test_search_attaches_parent_context_when_enabled(
    monkeypatch: pytest.MonkeyPatch, mock_db: AsyncMock
) -> None:
    """Service.search should attach parent_content for child chunks."""
    # Build: 2 children sharing 1 parent + 1 leaf chunk (no parent)
    parent = make_chunk(id=100, content="Full SOP section text", heading_path="SOP > Breakdown")
    child1 = make_chunk(id=101, parent_chunk_id=100, content="step 1: call depot", chunk_index=1)
    child2 = make_chunk(id=102, parent_chunk_id=100, content="step 2: reroute", chunk_index=2)
    leaf = make_chunk(id=103, parent_chunk_id=None, content="standalone fact", chunk_index=3)
    doc = make_document()

    # Mock vector + fulltext to both return the 3 children
    vector_results = [(child1, doc, 0.1), (child2, doc, 0.2), (leaf, doc, 0.3)]
    text_results: list[tuple[DocumentChunk, Document, float]] = []

    monkeypatch.setattr(
        "app.knowledge.service._get_embedding",
        lambda: MagicMock(embed=AsyncMock(return_value=[[0.0] * 1024])),
    )
    monkeypatch.setattr(
        "app.knowledge.service._get_reranker",
        lambda: MagicMock(rerank=AsyncMock(return_value=[
            MagicMock(index=0, score=0.9),
            MagicMock(index=1, score=0.85),
            MagicMock(index=2, score=0.8),
        ])),
    )

    repo = KnowledgeRepository(mock_db)
    repo.search_vector = AsyncMock(return_value=vector_results)  # type: ignore[method-assign]
    repo.search_fulltext = AsyncMock(return_value=text_results)  # type: ignore[method-assign]
    repo.get_chunks_by_ids = AsyncMock(return_value=[parent])  # type: ignore[method-assign]

    service = KnowledgeService(mock_db)
    service.repository = repo

    response = await service.search(SearchRequest(query="breakdown procedure", limit=5))

    # 2 children should have parent attached, leaf should not
    children_with_parent = [r for r in response.results if r.parent_chunk_id == 100]
    assert len(children_with_parent) == 2
    assert all(r.parent_content == "Full SOP section text" for r in children_with_parent)
    assert all(r.heading_path == "SOP > Breakdown" for r in children_with_parent)

    leaf_results = [r for r in response.results if r.parent_chunk_id is None]
    assert len(leaf_results) == 1
    assert leaf_results[0].parent_content is None

    # Dedupe: get_chunks_by_ids called once with single parent id
    repo.get_chunks_by_ids.assert_called_once_with([100])


@pytest.mark.asyncio
@pytest.mark.integration
async def test_search_skips_parent_fetch_when_flag_disabled(
    monkeypatch: pytest.MonkeyPatch, mock_db: AsyncMock
) -> None:
    """When knowledge_parent_context_enabled=False, no parent fetch should occur."""
    monkeypatch.setattr(
        "app.knowledge.service.get_settings",
        lambda: MagicMock(
            knowledge_parent_context_enabled=False,
            knowledge_parent_context_max_chars=3000,
            knowledge_hyde_enabled=False,
            knowledge_search_limit=50,
            knowledge_confidence_threshold=0.0,
            reranker_top_k=10,
            reranker_provider="none",
            temporal_boost_enabled=False,
            rrf_keyword_vector_weight=0.5,
            rrf_keyword_text_weight=0.5,
            rrf_semantic_vector_weight=0.5,
            rrf_semantic_text_weight=0.5,
            rrf_mixed_vector_weight=0.5,
            rrf_mixed_text_weight=0.5,
        ),
    )
    # ... rest mirrors the test above; assert repo.get_chunks_by_ids NOT called
    # assert all(r.parent_content is None for r in response.results)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_search_dedupes_multiple_children_to_one_parent_fetch(
    monkeypatch: pytest.MonkeyPatch, mock_db: AsyncMock
) -> None:
    """5 children with 2 unique parents → exactly 2 IDs in get_chunks_by_ids call."""
    # Build: children referencing 2 parent ids (100 and 200), 5 total
    # Assert: get_chunks_by_ids.call_args == ([100, 200],) order-insensitive
```

**Anti-pattern guards:**
- #11 — `SearchRequest(query=..., limit=5)` — only `query` is required; `limit` has a default. Confirm with grep before construction.
- #28 — `text_results: list[tuple[...]] = []` annotated explicitly.
- #1 — no `assert` in production code, but tests may use assert.
- #14 — no `# type: ignore[arg-type]` in tests; the only ignores are `[method-assign]` for monkeypatching repository methods (allowed).
- #34 — Not Redis. No misc ignores needed.

**Validation:**
```bash
uv run pytest app/knowledge/tests/test_repository.py -k "parent_context or parent_fetch or dedupes_multiple" -v
```

### Step 9 — Agent tool tests for formatting

**File:** `app/core/agents/tools/knowledge/tests/test_search_knowledge.py`

Add tests:

```python
@pytest.mark.asyncio
async def test_search_knowledge_includes_parent_context_in_content() -> None:
    """When SearchResult has parent_content + heading_path, formatted content
    should include [Section: ...] and [Matched passage:] markers."""
    mock_result = SearchResult(
        chunk_content="step 1: call depot X",
        document_id=42,
        document_filename="sop.pdf",
        domain="ops",
        language="en",
        chunk_index=3,
        score=0.85,
        metadata_json=None,
        document_created_at=datetime(2026, 4, 1),
        parent_chunk_id=10,
        parent_content="When bus breaks down on route 22, follow these steps...",
        heading_path="Operations > Breakdown Procedures",
    )
    mock_response = SearchResponse(
        results=[mock_result],
        query="breakdown",
        total_candidates=1,
        reranked=True,
    )

    with (
        patch(
            "app.core.agents.tools.knowledge.search_knowledge.AsyncSessionLocal"
        ) as session_cm,
        patch(
            "app.core.agents.tools.knowledge.search_knowledge.KnowledgeService"
        ) as svc_cls,
    ):
        session_cm.return_value.__aenter__.return_value = MagicMock()
        svc_cls.return_value.search = AsyncMock(return_value=mock_response)

        result_json = await search_knowledge_base(
            ctx=_make_ctx(rag_enabled=True), query="breakdown procedure"
        )

    parsed = json.loads(result_json)
    assert len(parsed["results"]) == 1
    content = parsed["results"][0]["content"]
    assert "[Section: Operations > Breakdown Procedures]" in content
    assert "When bus breaks down on route 22" in content
    assert "[Matched passage:]" in content
    assert "step 1: call depot X" in content
    assert parsed["results"][0]["parent_content"] is not None
    assert parsed["results"][0]["heading_path"] == "Operations > Breakdown Procedures"


@pytest.mark.asyncio
async def test_search_knowledge_omits_parent_markers_when_no_parent() -> None:
    """Leaf chunk results (parent_content=None) format as raw child content."""
    mock_result = SearchResult(
        chunk_content="standalone fact",
        document_id=42,
        document_filename="sop.pdf",
        domain="ops",
        language="en",
        chunk_index=5,
        score=0.7,
        metadata_json=None,
        document_created_at=datetime(2026, 4, 1),
    )
    # ... patch + run, then assert
    parsed = json.loads(result_json)
    content = parsed["results"][0]["content"]
    assert "[Section:" not in content
    assert "[Matched passage:]" not in content
    assert content == "standalone fact"
```

**Anti-pattern guards:**
- #28 — no bare list literals.
- #11 — `SearchResult(...)` uses ALL fields including new ones explicitly.
- #36 — `KnowledgeService` patched at the importing module's namespace (`search_knowledge.KnowledgeService`), not at `app.knowledge.service.KnowledgeService` — match the existing test pattern at `test_search_knowledge.py:40-43`.

**Validation:**
```bash
uv run pytest app/core/agents/tools/knowledge/tests/test_search_knowledge.py -v
```

### Step 10 — Run full validation

```bash
uv run ruff format app/knowledge/ app/core/agents/tools/knowledge/ app/core/config.py
uv run ruff check --fix app/knowledge/ app/core/agents/tools/knowledge/ app/core/config.py
uv run pyright app/knowledge/ app/core/agents/tools/knowledge/
uv run mypy app/knowledge/ app/core/agents/tools/knowledge/
uv run pytest app/knowledge/tests/ app/core/agents/tools/knowledge/tests/ -v
```

Pyright/mypy MUST be at the same baseline (zero new errors).

### Step 11 — Manual end-to-end verification

1. Start stack: `make db && make dev-be`
2. Upload a multi-section SOP (e.g. via `/api/v1/knowledge/upload` with the documents page):
   - Section 1: Daily safety check
   - Section 2: Pre-trip inspection
   - Section 3: Breakdown procedure (containing "1. call depot X, 2. reroute via Y, 3. notify dispatcher Z")
3. Hit the agent with: "What should I do when a bus breaks down on route 22?"
4. Verify the agent's tool-call response (visible in logs at `agent.knowledge.search_completed`) shows `parent_contexts_count > 0`.
5. Verify the chat answer cites the FULL section, not just the matched paragraph.
6. Toggle `KNOWLEDGE_PARENT_CONTEXT_ENABLED=false` env var, restart, repeat — answer should be narrower.

### Step 12 — Documentation touch-ups

(a) `app/core/agents/CLAUDE.md` — in the "RAG retrieval" bullet, append:
```
, ✅ parent-child context expansion (AI-4.3)
```

(b) `CLAUDE.md` — in the project structure tree, update the `knowledge/` line:
```
│   ├── knowledge/      # RAG knowledge base + DMS (..., parent-child chunk hierarchy, parent context expansion)
```

(c) `app/memory/` description in `CLAUDE.md` is unchanged.

## Preflight Warnings

From the test scout's fragile-pattern audit:

1. **`test_repository.py:137,145,232,276`** — hardcoded `len(results) == N` asserts. **No regression risk** — these test repository-layer search legs, not service-layer fusion. Parent expansion happens in service layer above the repo.
2. **`test_search_knowledge.py:19,53`** — exact-string asserts on agent tool JSON output. New fields default `None` — Pydantic `model_dump()` will include them as `null`. Existing tests must not use `assert json == {exact-dict}`. **Action:** before writing new tests, grep existing assertions and convert any `==` whole-dict comparisons to per-key checks.
3. **AI-4.2 commit `cab0b4b`** — the chunker emits parents that hold the FULL section content, not summaries. Truncation at `_MAX_PARENT_CHARS=3000` is a hard cap; for very long sections the displayed parent will be truncated.
4. **`SearchResult` constructor at `service.py:583`** — uses positional kwargs. Adding optional fields with defaults is safe. **Anti-pattern #11** still requires a grep: `Grep` for `SearchResult(` and verify the only constructor is in `service.py`. (Test files construct it too — those become required updates for tests, not for production code.)

## Security Checklist

CTX-AGENT requirements (only active context for this slice):

- [x] No new agent tool — existing `search_knowledge_base` is enhanced, not added
- [x] No prompt injection vector — parent content is server-side trusted (already in DB)
- [x] Token budget enforced — `_MAX_PARENT_CHARS=3000` in tool, `knowledge_parent_context_max_chars=3000` in service
- [x] Feature gate — `knowledge_parent_context_enabled` flag (default `True`, can disable via env)
- [x] No credentials exposed in tool response or logs — parent content is the same trusted document text
- [x] No new endpoints, no new auth surfaces

CTX-INPUT (not active): no new user input handling.

## Verification

- [ ] `make check` passes (lint + types + tests)
- [ ] `uv run pyright app/knowledge/ app/core/agents/tools/knowledge/` shows **0 errors** (baseline preserved)
- [ ] `uv run mypy app/knowledge/ app/core/agents/tools/knowledge/` shows **0 new errors** (3 pre-existing in transit/ + pipeline.py)
- [ ] New tests pass: `uv run pytest app/knowledge/tests/test_repository.py app/core/agents/tools/knowledge/tests/test_search_knowledge.py -v`
- [ ] `make security-audit-quick` passes
- [ ] Manual e2e: agent answer cites full section context for a child-matched query
- [ ] Toggle off: `KNOWLEDGE_PARENT_CONTEXT_ENABLED=false` produces pre-AI-4.3 output
- [ ] Logs show `knowledge.search.parent_context_attached` and `agent.knowledge.search_completed` with `parent_contexts_count` field
- [ ] Existing 1128 unit tests still pass: `make test`
