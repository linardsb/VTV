# Plan: AI-1.3 Temporal Boost + RRF Weight Tuning

## Context

Transit documents have dramatically different relevance lifecycles. Shift handover notes from today matter 10x more than last month's. The current RRF fusion applies equal `1.0 / (60 + rank)` weighting to both vector and fulltext results, ignoring document age entirely. This plan adds:

1. **Temporal relevance boost** — recent documents score higher after RRF fusion
2. **Query-type-adaptive RRF weights** — keyword-heavy queries weight fulltext higher, semantic queries weight vector higher
3. **Evergreen flag** — documents marked evergreen (regulations, SOPs) skip temporal decay

## Security Context Assessment

**Active contexts:** CTX-INPUT (new query parameter handling in search), CTX-RBAC (existing endpoints modified)

No new endpoints added. Existing auth/RBAC on search endpoint unchanged. Input validation via Pydantic schemas. No file handling, no agent tools, no infra changes.

## Research Summary

### Current RRF Pipeline (`app/knowledge/service.py:315-413`)

```python
# Lines 355-369 — current equal-weight RRF
rrf_k = 60
chunk_scores: dict[int, float] = {}
for rank, (chunk, doc, _dist) in enumerate(vector_results):
    chunk_scores[chunk.id] = chunk_scores.get(chunk.id, 0.0) + 1.0 / (rrf_k + rank)
for rank, (chunk, doc, _rank_score) in enumerate(text_results):
    chunk_scores[chunk.id] = chunk_scores.get(chunk.id, 0.0) + 1.0 / (rrf_k + rank)
sorted_ids = sorted(chunk_scores.keys(), key=lambda cid: chunk_scores[cid], reverse=True)
```

### Key Files

| File | Role | Key Lines |
|------|------|-----------|
| `app/knowledge/service.py` | Search orchestrator, RRF fusion | 315-413 |
| `app/knowledge/repository.py` | Vector + fulltext DB queries | 258-352 |
| `app/knowledge/models.py` | Document model (needs `evergreen` col) | 30-52 |
| `app/knowledge/schemas.py` | SearchRequest, DocumentResponse, DocumentUpdate | 10-174 |
| `app/knowledge/routes.py` | Search endpoint (no changes needed) | 357-367 |
| `app/core/config.py` | Settings (knowledge section lines 183-190) | 164-190 |
| `app/shared/models.py` | TimestampMixin (created_at for age calc) | 15-42 |

### Scoring Pipeline (current)

1. Embed query → vector search (cosine_distance) + fulltext search (ts_rank)
2. RRF fusion: equal-weight sum of `1/(60+rank)` per ranking list
3. Sort by RRF score, take top-K
4. Optional reranker (BAAI/bge-reranker-v2-m3) → final scores
5. Return SearchResult with score

### Document Model Columns (models.py:30-52)

id, filename, title, description, file_path, domain, source_type, language, file_size_bytes, status, error_message, chunk_count, metadata_json, ocr_applied + TimestampMixin (created_at, updated_at)

## Test Landscape

- **9 test files + conftest** (~2141 lines) in `app/knowledge/tests/`
- **Factories:** `make_document(**overrides)`, `make_chunk(**overrides)` in `test_repository.py`
- **Search tests:** `test_search_vector`, `test_search_fulltext`, date range filters — all in `test_repository.py`
- **RRF fusion:** NOT directly tested at unit level — only indirectly via route tests
- **Mock pattern:** `AsyncMock` for db session, `mock_result.all.return_value = [(chunk, doc, score)]`
- **Markers:** `@pytest.mark.asyncio`, `@pytest.mark.integration` for DB tests
- **No parametrize** — individual test methods preferred

## Type Check Baseline

- **Pyright:** 0 errors on `app/knowledge/`
- **MyPy:** 0 errors in knowledge files (3 transitive errors in `app/core/agents/` — unrelated)

## Files to Create/Modify

| Action | File | Purpose |
|--------|------|---------|
| CREATE | `alembic/versions/{hex}_add_evergreen_to_documents.py` | Add `evergreen` boolean column |
| UPDATE | `app/knowledge/models.py` | Add `evergreen: Mapped[bool]` column |
| UPDATE | `app/knowledge/schemas.py` | Add `evergreen` to DocumentResponse, DocumentUpdate, DocumentUpload |
| UPDATE | `app/knowledge/service.py` | Add `_detect_query_type()`, `_temporal_boost()`, modify RRF fusion |
| UPDATE | `app/core/config.py` | Add temporal boost + RRF weight settings |
| UPDATE | `app/knowledge/tests/test_repository.py` | Add tests for temporal boost + RRF tuning |

## Implementation Steps

### Step 1: Add `evergreen` column to Document model

**File:** `app/knowledge/models.py` (UPDATE)
**Line:** After line 52 (after `ocr_applied`)

Add:
```python
evergreen: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
```

**Validation:** `uv run ruff format app/knowledge/models.py && uv run ruff check --fix app/knowledge/models.py && uv run pyright app/knowledge/models.py`

### Step 2: Create database migration

**Command:** `cd /Users/Berzins/Desktop/VTV && uv run alembic revision --autogenerate -m "add_evergreen_to_documents"`

Review generated migration. Ensure:
- `op.add_column('documents', sa.Column('evergreen', sa.Boolean(), nullable=False, server_default='false'))`
- Downgrade drops the column

**Validation:** Review migration file content.

### Step 3: Update schemas

**File:** `app/knowledge/schemas.py` (UPDATE)

3a. **DocumentUpload** (line ~31): Add field after `description`:
```python
evergreen: bool = False
```

3b. **DocumentUpdate** (line ~47): Add field:
```python
evergreen: bool | None = None
```
Note: Update the `@model_validator(mode="before")` to include `evergreen` in the "at least one field" check.

3c. **DocumentResponse** (line ~112): Add field after `ocr_applied`:
```python
evergreen: bool
```

3d. **SearchResult** (line ~165): Add field:
```python
document_created_at: datetime
```
This exposes when the source document was created, useful for clients to display temporal context.

**Anti-pattern #29:** Grep for all constructors of these schemas (`DocumentUpload(`, `DocumentUpdate(`, `DocumentResponse(`, `SearchResult(`) and update call sites. `evergreen` has defaults so existing constructors won't break, but `document_created_at` on SearchResult is new — update service.py search method where SearchResult is constructed.

**Validation:** `uv run ruff format app/knowledge/schemas.py && uv run ruff check --fix app/knowledge/schemas.py && uv run pyright app/knowledge/schemas.py`

### Step 4: Add config settings

**File:** `app/core/config.py` (UPDATE)
**Location:** After knowledge settings (line ~186)

Add:
```python
# Temporal boost
temporal_boost_enabled: bool = True
temporal_boost_today: float = 1.5      # multiplier for documents created today
temporal_boost_this_week: float = 1.2   # created within 7 days
temporal_boost_this_month: float = 1.0  # created within 30 days
temporal_boost_older: float = 0.8       # older than 30 days

# RRF weight tuning
rrf_keyword_vector_weight: float = 0.3
rrf_keyword_text_weight: float = 0.7
rrf_semantic_vector_weight: float = 0.7
rrf_semantic_text_weight: float = 0.3
rrf_mixed_vector_weight: float = 0.5
rrf_mixed_text_weight: float = 0.5
```

**Validation:** `uv run ruff format app/core/config.py && uv run ruff check --fix app/core/config.py && uv run pyright app/core/config.py`

### Step 5: Implement query type detection and temporal boost in service

**File:** `app/knowledge/service.py` (UPDATE)

5a. **Add `_detect_query_type()` method** — class method or module-level function:

```python
def _detect_query_type(query: str) -> Literal["keyword", "semantic", "mixed"]:
    """Classify query to tune RRF weights.

    Keyword indicators: route numbers, stop codes, short alphanumeric tokens.
    Semantic indicators: question words, procedural phrases.
    """
    query_lower = query.lower()
    # Semantic patterns: questions, procedural queries
    semantic_patterns = [
        "how ", "what ", "why ", "when ", "where ", "which ",
        "explain", "describe", "procedure", "process", "kā ", "kas ", "kāpēc ",
        "kur ", "kad ", "kāda ",
    ]
    # Keyword patterns: route numbers, stop names, codes
    keyword_patterns = re.compile(r"\b\d{1,4}\b")  # numeric tokens like route numbers

    has_semantic = any(p in query_lower for p in semantic_patterns)
    has_keyword = bool(keyword_patterns.search(query))

    if has_semantic and not has_keyword:
        return "semantic"
    if has_keyword and not has_semantic:
        return "keyword"
    return "mixed"
```

5b. **Add `_temporal_boost()` method:**

```python
def _temporal_boost(
    doc_created_at: datetime,
    query_time: datetime,
    evergreen: bool,
    settings: Settings,
) -> float:
    """Compute temporal relevance multiplier.

    Evergreen documents (regulations, SOPs) always return 1.0.
    Recent documents get boosted, older documents get penalized.
    """
    if not settings.temporal_boost_enabled or evergreen:
        return 1.0

    age = query_time - doc_created_at
    if age.days < 1:
        return settings.temporal_boost_today
    if age.days < 7:
        return settings.temporal_boost_this_week
    if age.days < 30:
        return settings.temporal_boost_this_month
    return settings.temporal_boost_older
```

5c. **Modify RRF fusion in `search()` method** (lines 355-369):

Replace the current equal-weight RRF with weighted RRF:

```python
# Detect query type and select weights
query_type = _detect_query_type(request.query)
settings = get_settings()

if query_type == "keyword":
    vector_weight = settings.rrf_keyword_vector_weight
    text_weight = settings.rrf_keyword_text_weight
elif query_type == "semantic":
    vector_weight = settings.rrf_semantic_vector_weight
    text_weight = settings.rrf_semantic_text_weight
else:
    vector_weight = settings.rrf_mixed_vector_weight
    text_weight = settings.rrf_mixed_text_weight

# RRF fusion with adaptive weights
rrf_k = 60
chunk_scores: dict[int, float] = {}
chunk_data: dict[int, tuple[DocumentChunk, str, str, str, datetime, bool]] = {}

for rank, (chunk, doc, _dist) in enumerate(vector_results):
    chunk_scores[chunk.id] = chunk_scores.get(chunk.id, 0.0) + vector_weight / (rrf_k + rank)
    chunk_data[chunk.id] = (chunk, doc.filename, doc.domain, doc.language, doc.created_at, doc.evergreen)

for rank, (chunk, doc, _rank_score) in enumerate(text_results):
    chunk_scores[chunk.id] = chunk_scores.get(chunk.id, 0.0) + text_weight / (rrf_k + rank)
    chunk_data[chunk.id] = (chunk, doc.filename, doc.domain, doc.language, doc.created_at, doc.evergreen)

# Apply temporal boost
query_time = utcnow()
for chunk_id in chunk_scores:
    _, _, _, _, created_at, evergreen = chunk_data[chunk_id]
    boost = _temporal_boost(created_at, query_time, evergreen, settings)
    chunk_scores[chunk_id] *= boost

# Sort by boosted RRF score
sorted_ids = sorted(chunk_scores.keys(), key=lambda cid: chunk_scores[cid], reverse=True)
```

5d. **Update SearchResult construction** (lines ~387-397):

Update the loop that builds SearchResult objects to include `document_created_at`:
```python
document_created_at=chunk_data[chunk_id][4],  # created_at from chunk_data tuple
```

5e. **Add logging for query type detection:**
```python
logger.info("knowledge.search.query_type_detected", query_type=query_type, query_length=len(request.query))
```

**Import:** Add `import re` and `from typing import Literal` at top if not already present. Import `get_settings` from `app.core.config`.

**Validation:** `uv run ruff format app/knowledge/service.py && uv run ruff check --fix app/knowledge/service.py && uv run pyright app/knowledge/service.py`

### Step 6: Update document creation to pass `evergreen`

**File:** `app/knowledge/service.py` (UPDATE)

In `ingest_document()` method, pass `evergreen` from the upload schema to the Document model constructor. Search for where `Document(` is constructed and add `evergreen=upload.evergreen` (or however the upload schema is accessed).

**Validation:** `uv run ruff format app/knowledge/service.py && uv run pyright app/knowledge/service.py`

### Step 7: Update repository for evergreen in document creation

**File:** `app/knowledge/repository.py` (UPDATE)

Check `create_document()` method. If it constructs `Document(...)` from individual params, add `evergreen` parameter. If it uses `**kwargs` from schema, no change needed.

**Validation:** `uv run pyright app/knowledge/repository.py`

### Step 8: Update document update to handle evergreen

**File:** `app/knowledge/service.py` or `app/knowledge/repository.py` (UPDATE)

Ensure `update_document()` handles the new `evergreen` field from `DocumentUpdate`. Since DocumentUpdate likely uses `model_dump(exclude_unset=True)`, this may work automatically — verify.

**Validation:** `uv run pyright app/knowledge/`

### Step 9: Write unit tests

**File:** `app/knowledge/tests/test_repository.py` (UPDATE)

Add tests after existing search tests:

```python
class TestQueryTypeDetection:
    """Tests for _detect_query_type() heuristic."""

    def test_keyword_query_route_number(self) -> None:
        """Route numbers should classify as keyword."""
        from app.knowledge.service import _detect_query_type
        assert _detect_query_type("route 22 schedule") == "keyword"

    def test_keyword_query_stop_code(self) -> None:
        from app.knowledge.service import _detect_query_type
        assert _detect_query_type("stop 1456") == "keyword"

    def test_semantic_query_how_question(self) -> None:
        from app.knowledge.service import _detect_query_type
        assert _detect_query_type("how do I handle a breakdown") == "semantic"

    def test_semantic_query_procedure(self) -> None:
        from app.knowledge.service import _detect_query_type
        assert _detect_query_type("explain the refueling procedure") == "semantic"

    def test_mixed_query(self) -> None:
        from app.knowledge.service import _detect_query_type
        assert _detect_query_type("how does route 22 work") == "mixed"

    def test_plain_text_query_is_mixed(self) -> None:
        from app.knowledge.service import _detect_query_type
        assert _detect_query_type("shift handover notes") == "mixed"

    def test_latvian_semantic_query(self) -> None:
        from app.knowledge.service import _detect_query_type
        assert _detect_query_type("kā rīkoties avārijas gadījumā") == "semantic"


class TestTemporalBoost:
    """Tests for _temporal_boost() multiplier."""

    def test_today_document_gets_boost(self) -> None:
        from app.knowledge.service import _temporal_boost
        now = utcnow()
        result = _temporal_boost(now, now, evergreen=False, settings=get_settings())
        assert result == 1.5

    def test_week_old_document(self) -> None:
        from app.knowledge.service import _temporal_boost
        now = utcnow()
        three_days_ago = now - timedelta(days=3)
        result = _temporal_boost(three_days_ago, now, evergreen=False, settings=get_settings())
        assert result == 1.2

    def test_month_old_document(self) -> None:
        from app.knowledge.service import _temporal_boost
        now = utcnow()
        two_weeks_ago = now - timedelta(days=15)
        result = _temporal_boost(two_weeks_ago, now, evergreen=False, settings=get_settings())
        assert result == 1.0

    def test_old_document_penalized(self) -> None:
        from app.knowledge.service import _temporal_boost
        now = utcnow()
        old = now - timedelta(days=90)
        result = _temporal_boost(old, now, evergreen=False, settings=get_settings())
        assert result == 0.8

    def test_evergreen_skips_decay(self) -> None:
        from app.knowledge.service import _temporal_boost
        now = utcnow()
        old = now - timedelta(days=365)
        result = _temporal_boost(old, now, evergreen=True, settings=get_settings())
        assert result == 1.0

    def test_disabled_returns_neutral(self) -> None:
        from app.knowledge.service import _temporal_boost
        settings = get_settings()
        settings.temporal_boost_enabled = False
        now = utcnow()
        old = now - timedelta(days=90)
        result = _temporal_boost(old, now, evergreen=False, settings=settings)
        assert result == 1.0
```

Also update `make_document()` factory to include `evergreen=False` default.

Update any existing tests that construct `SearchResult` to include `document_created_at`.

**Validation:** `uv run pytest app/knowledge/tests/ -x -q`

### Step 10: Update mock constructors in test_routes.py

**File:** `app/knowledge/tests/test_routes.py` (UPDATE)

Search for `SearchResult(` and `DocumentResponse(` constructors. Add:
- `document_created_at=utcnow()` to SearchResult constructors
- `evergreen=False` to DocumentResponse constructors (if constructed directly)

Also update `_make_doc_response()` factory to include `evergreen=False`.

**Validation:** `uv run pytest app/knowledge/tests/test_routes.py -x -q`

## Preflight Warnings

- **SearchResult constructor** — adding `document_created_at` (required field) will break ALL existing SearchResult constructors. Must update in same step.
- **DocumentResponse constructor** — `evergreen` has no default in response schema, so all constructors must add it. Check `_make_doc_response()` in test_routes.py.
- **`chunk_data` tuple expansion** — changing from 4-tuple to 6-tuple requires updating ALL unpacking sites in service.py search method.
- **Agent tools** — check if `app/core/agents/tools/knowledge/` constructs SearchResult or calls search. If so, update.

## Security Checklist

No new endpoints added. Existing security preserved:
- [x] Search endpoint already has `get_current_user` dependency
- [x] Search endpoint already has `@limiter.limit()` rate limiting
- [x] Input validation via Pydantic SearchRequest (unchanged)
- [x] `escape_like()` not applicable (no ILIKE in search)
- [x] `evergreen` field is `bool` — no injection risk
- [x] No new error responses needed

## Verification

- [ ] `make check` passes (lint + types + tests)
- [ ] `make security-audit-quick` passes
- [ ] Pyright errors ≤ baseline (0 errors before)
- [ ] MyPy errors ≤ baseline (0 errors in knowledge/ before)
- [ ] Security convention tests pass: `uv run pytest app/tests/test_security.py -v`
- [ ] New temporal boost tests pass
- [ ] New query type detection tests pass
- [ ] Existing search tests still pass (no regressions)
