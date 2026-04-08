# Plan: AI-1.2 Chunk Overlap + Result Truncation Expansion

## Context

**What:** (a) Increase chunk overlap from 50 → 100 chars. (b) Expand search result truncation from 500 → 1500 chars. (c) Add `created_at` range filtering to hybrid search.

**Why:** 50-char overlap loses context at chunk boundaries for Latvian compound words. 500-char truncation cuts mid-concept — dispatchers get incomplete SOP steps. Time-sensitive documents (shift notes) should be filterable by date.

## Security Context Assessment

**Active contexts:** CTX-INPUT (date filter query params), CTX-AGENT (agent tool output change)

- CTX-INPUT: New `created_after`/`created_before` params need Pydantic validation (datetime parsing). No ILIKE needed.
- CTX-AGENT: Truncation increase from 500→1500 is agent output — no injection risk, but increases token cost per result.

## Research Summary

### Search Architecture (no single `hybrid_search()`)

```
KnowledgeService.search(SearchRequest)  →  service.py:315-403
  ├── repository.search_vector()         →  repository.py:256-291
  ├── repository.search_fulltext()       →  repository.py:293-334
  ├── RRF Fusion (k=60)                 →  service.py:345-360
  └── Reranking                          →  service.py:362-369
```

### Files to Modify

| File | Key Lines | What Changes |
|------|-----------|-------------|
| `app/knowledge/chunking.py` | L24 | `chunk_overlap: int = 50` → `100` |
| `app/core/config.py` | L185 | `knowledge_chunk_overlap: int = 50` → `100` |
| `app/core/agents/tools/knowledge/search_knowledge.py` | L26 | `_MAX_CONTENT_CHARS = 500` → `1500` |
| `app/knowledge/repository.py` | L256-291, L293-334 | Add `created_after`/`created_before` params to both search methods |
| `app/knowledge/service.py` | L337-343 | Pass date filters from SearchRequest to repository |
| `app/knowledge/schemas.py` | L140-147 | Add `created_after`/`created_before` fields to SearchRequest |

### Data Model

`Document` inherits `TimestampMixin` → has `created_at: DateTime(timezone=True)` column. **No migration needed** — filtering on existing column.

### Callers of Modified Functions

- `service.search()` called by: `routes.py:359` (REST endpoint) + `search_knowledge.py:89` (agent tool)
- `SearchRequest` constructed in: `routes.py` (from request body) + `search_knowledge.py:89` (agent tool — needs `created_after`/`created_before` params added)

## Test Landscape

### Existing Tests

| File | Tests | Relevant Coverage |
|------|-------|-------------------|
| `test_chunking.py` (60 lines) | 6 tests | Overlap existence (partial — checks length only), diacritics, offsets |
| `test_repository.py` (400 lines) | 10 tests | `search_vector`, `search_fulltext`, domain/language filters |
| `test_search_knowledge.py` (204 lines) | 6 tests | Truncation to 500, empty query, citations, error handling |
| `test_routes.py` (499 lines) | ~12 tests | Upload, search endpoint, MIME detection |
| `test_dms.py` (294 lines) | ~8 tests | Mocks `knowledge_chunk_overlap = 50` at L205-210 |

### Fixtures Available

- `make_document(**overrides)` / `make_chunk(**overrides)` in `test_repository.py`
- `sample_upload()` / `sample_latvian_text()` / `sample_english_text()` in `conftest.py`
- `_make_doc_response()` / `_mock_service()` in `test_routes.py`

### Tests Requiring Update

1. `test_search_knowledge.py:194` — assertion `== 500` → `== 1500`, rename test
2. `test_dms.py:205-210` — mock `knowledge_chunk_overlap = 50` → `100`

## Type Check Baseline

| Tool | Directory | Errors | In Target Files |
|------|-----------|--------|-----------------|
| Pyright | `app/knowledge/` | 0 | 0 |
| Pyright | `app/core/agents/tools/knowledge/` | 0 | 0 |
| MyPy | `app/knowledge/` | 3 (pre-existing in transit, unrelated) | 0 |
| MyPy | `app/core/agents/tools/knowledge/` | 2 (pre-existing in transit, unrelated) | 0 |

**No-regression target:** 0 pyright errors, 0 new mypy errors in target files.

## Implementation Steps

### Step 1: Update chunk overlap defaults

**Files:** `app/knowledge/chunking.py`, `app/core/config.py`

In `chunking.py:24`: change `chunk_overlap: int = 50` → `chunk_overlap: int = 100`

In `config.py:185`: change `knowledge_chunk_overlap: int = 50` → `knowledge_chunk_overlap: int = 100`

**Validation:** `uv run ruff check app/knowledge/chunking.py app/core/config.py && uv run pyright app/knowledge/chunking.py app/core/config.py`

### Step 2: Update truncation constant

**File:** `app/core/agents/tools/knowledge/search_knowledge.py`

Line 26: change `_MAX_CONTENT_CHARS = 500` → `_MAX_CONTENT_CHARS = 1500`

**Validation:** `uv run pyright app/core/agents/tools/knowledge/search_knowledge.py`

### Step 3: Add date filter fields to SearchRequest schema

**File:** `app/knowledge/schemas.py`

Add to `SearchRequest` class (after `limit` field, ~L147):
```python
created_after: datetime | None = Field(None, description="Filter documents created after this timestamp")
created_before: datetime | None = Field(None, description="Filter documents created before this timestamp")
```

Add `from datetime import datetime` import if not present.

**Anti-pattern #29:** Adding optional fields to Pydantic schema — grep for `SearchRequest(` and verify all constructors still work (optional fields default to None, so existing callers are safe).

**Validation:** `uv run pyright app/knowledge/schemas.py`

### Step 4: Add date filter params to repository search methods

**File:** `app/knowledge/repository.py`

Update `search_vector()` signature (~L256) — add params:
```python
created_after: datetime | None = None,
created_before: datetime | None = None,
```

Add WHERE clauses before the ORDER BY:
```python
if created_after is not None:
    query = query.where(Document.created_at >= created_after)
if created_before is not None:
    query = query.where(Document.created_at <= created_before)
```

Same changes to `search_fulltext()` (~L293).

Add `from datetime import datetime` import if not present.

**Validation:** `uv run pyright app/knowledge/repository.py`

### Step 5: Pass date filters through service layer

**File:** `app/knowledge/service.py`

In `search()` method (~L337-343), update both repository calls:
```python
vector_results = await self.repository.search_vector(
    query_embedding, search_limit,
    request.domain, request.language,
    request.created_after, request.created_before,
)
text_results = await self.repository.search_fulltext(
    request.query, search_limit,
    request.domain, request.language,
    request.created_after, request.created_before,
)
```

**Validation:** `uv run pyright app/knowledge/service.py`

### Step 6: Update agent tool to support date filtering

**File:** `app/core/agents/tools/knowledge/search_knowledge.py`

The tool function signature needs optional `created_after`/`created_before` string params (ISO format). Parse them to datetime before passing to `SearchRequest`.

Add to tool function params:
```python
created_after: str | None = None,  # ISO datetime string
created_before: str | None = None,  # ISO datetime string
```

In the SearchRequest construction (~L89), add:
```python
created_after=datetime.fromisoformat(created_after) if created_after else None,
created_before=datetime.fromisoformat(created_before) if created_before else None,
```

Update the tool docstring to document the new parameters.

**Validation:** `uv run pyright app/core/agents/tools/knowledge/search_knowledge.py`

### Step 7: Update existing tests

**File:** `app/core/agents/tools/knowledge/tests/test_search_knowledge.py`

- Rename `test_search_truncates_content_to_500_chars` → `test_search_truncates_content_to_1500_chars`
- Update assertion from `== 500` to `== 1500`
- Update mock content length to be >1500 chars (generate long string)

**File:** `app/knowledge/tests/test_dms.py`

- Line ~205-210: Update mock `knowledge_chunk_overlap = 50` → `100`

**Validation:** `uv run pytest app/core/agents/tools/knowledge/tests/test_search_knowledge.py app/knowledge/tests/test_dms.py -v`

### Step 8: Add new tests for date filtering

**File:** `app/knowledge/tests/test_repository.py`

Add tests using existing `make_document`/`make_chunk` factories:

```python
async def test_search_vector_with_created_after_filter(mock_db):
    """Documents before created_after are excluded."""

async def test_search_fulltext_with_created_before_filter(mock_db):
    """Documents after created_before are excluded."""

async def test_search_vector_with_date_range(mock_db):
    """Both created_after and created_before filter together."""
```

**File:** `app/knowledge/tests/test_chunking.py`

Add test verifying 100-char overlap captures boundary context:

```python
def test_chunk_overlap_100_preserves_boundary_context():
    """100-char overlap preserves Latvian compound words at boundaries."""
    text = "word " * 200  # Long enough for multiple chunks
    result = chunk_text(text, chunk_size=200, chunk_overlap=100)
    assert len(result) >= 2
    # Verify overlap: end of chunk[0] appears in start of chunk[1]
    overlap_text = result[0].content[-100:]
    assert overlap_text in result[1].content
```

**Validation:** `uv run pytest app/knowledge/tests/ -v`

## Preflight Warnings

- `test_dms.py:205-210` hardcodes `knowledge_chunk_overlap = 50` — must update to 100
- `test_search_knowledge.py:194` asserts `== 500` — must update to 1500
- Agent tool `search_knowledge.py` constructs `SearchRequest` directly (L89) — new optional schema fields won't break it (defaults to None)

## Security Checklist

- [x] No new endpoints — existing `/search` endpoint gains optional body fields
- [x] Date params are Pydantic `datetime | None` — auto-validated, no injection risk
- [x] No ILIKE queries — date comparison uses SQLAlchemy `>=`/`<=` operators (parameterized)
- [x] Agent tool date params parsed via `datetime.fromisoformat()` — invalid strings raise ValueError (caught by existing error handler)
- [x] Truncation increase doesn't affect security — agent output only

## Verification

- [ ] `make lint` passes (ruff format + check)
- [ ] `make types` passes (mypy + pyright)
- [ ] `make test` passes (all unit tests)
- [ ] Pyright errors ≤ baseline (0 errors in target files)
- [ ] Truncation test updated: asserts 1500
- [ ] DMS test updated: mocks overlap=100
- [ ] New date filter tests pass
- [ ] `make security-audit-quick` passes
