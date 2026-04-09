# Plan: AI-3.2 Memory Service — Store, Recall, Compact

## Context

AI-3.1 built the memory vertical slice (models, repository, schemas, routes, 32 tests). The service layer is a thin pass-through to the repository — it has no embedding generation, duplicate detection, time-based decay, compaction, or auto-promotion. This ticket adds lifecycle management so memories are embedded on store, recalled by text query, compacted when similar, decayed by age, and auto-promoted from episodic to procedural after repeated recall.

## Security Context Assessment

**Active contexts:** CTX-RBAC, CTX-INPUT

- **CTX-RBAC** — New `POST /compact` endpoint needs `admin`-only role. Existing endpoints already have `require_role()`.
- **CTX-INPUT** — Compact endpoint accepts no user text input (operates on stored data). New text-based recall accepts `query: str` with `max_length`.

CTX-AUTH, CTX-FILE, CTX-AGENT, CTX-INFRA — **not active**.

## Research Summary

### Existing State (`app/memory/`)

| File | Lines | Status | Gap |
|------|-------|--------|-----|
| `models.py` | 31 | Complete | None |
| `schemas.py` | 58 | Complete | Missing CompactionResult, PromotionResult, MemoryRecallByQueryRequest |
| `repository.py` | 114 | Complete | Missing: find_similar, apply_decay, merge_entries, find_promotable |
| `service.py` | 88 | Complete | Missing: embed-on-store, dedup check, compact, promote, recall-by-query |
| `routes.py` | 99 | Complete | Missing: POST /compact, POST /recall/query |
| `exceptions.py` | — | Complete | None |
| `tests/` | 32 tests | Complete | Need 20+ new tests for lifecycle methods |

### Embedding Provider (reuse from knowledge)

- `app/knowledge/embedding.py:24` — `EmbeddingProvider` Protocol with `async embed(texts) -> list[list[float]]`
- `app/knowledge/embedding.py:280` — `get_embedding_provider(settings)` factory
- `app/knowledge/embedding.py:178` — `CachedEmbeddingProvider` wrapper
- `app/knowledge/service.py:52-71` — Lazy singleton pattern with `_get_embedding()`

The memory service should use the same `_get_embedding()` pattern — import and reuse the knowledge module's embedding infrastructure.

### Config

No `MemoryConfig` exists in `app/core/config.py`. Need to add lifecycle settings.

## Type Check Baseline

| Checker | Errors (app/memory/) |
|---------|---------------------|
| Pyright | 0 |
| Mypy | 0 (3 transitive in app/core/agents/) |

## Files to Create/Modify

| Action | File | Purpose |
|--------|------|---------|
| UPDATE | `app/core/config.py` | Add memory lifecycle config fields |
| UPDATE | `app/memory/schemas.py` | Add CompactionResult, PromotionResult, MemoryRecallByQueryRequest |
| UPDATE | `app/memory/repository.py` | Add find_similar, apply_decay, merge_entries, find_promotable, update_type |
| UPDATE | `app/memory/service.py` | Add embed-on-store, dedup, compact, promote, recall_by_query |
| UPDATE | `app/memory/routes.py` | Add POST /compact, POST /recall/query |
| UPDATE | `app/memory/tests/conftest.py` | Add new fixtures for lifecycle tests |
| UPDATE | `app/memory/tests/test_service.py` | Add tests for compact, promote, dedup, embed-on-store |
| UPDATE | `app/memory/tests/test_repository.py` | Add tests for find_similar, apply_decay, merge, find_promotable |
| UPDATE | `app/memory/tests/test_routes.py` | Add tests for POST /compact, POST /recall/query |

## Implementation Steps

### Step 1: Add Memory Config to Settings

**File:** `app/core/config.py`
**Action:** ADD fields to existing `Settings` class

Add these fields (grouped with a comment):
```python
# Memory lifecycle
memory_enabled: bool = True
memory_procedural_decay_days: int = 90
memory_episodic_decay_days: int = 30
memory_query_pattern_decay_days: int = 60
memory_promotion_threshold: int = 3
memory_max_recall_results: int = 5
memory_duplicate_threshold: float = 0.95
memory_merge_threshold: float = 0.92
memory_decay_min_weight: float = 0.1
```

**Validation:** `uv run ruff check app/core/config.py && uv run pyright app/core/config.py`

---

### Step 2: Add Schemas

**File:** `app/memory/schemas.py`
**Action:** ADD new schemas

Add after existing schemas:

```python
class MemoryRecallByQueryRequest(BaseModel):
    """Request schema for text-based memory recall (service embeds the query)."""
    query: str = Field(max_length=2000)
    agent_type: str | None = Field(default=None, max_length=50)
    memory_type: MemoryType | None = None
    limit: int = Field(default=5, ge=1, le=100)
    min_score: float = Field(default=0.0, ge=0.0, le=1.0)


class CompactionResult(BaseModel):
    """Response for memory compaction operation."""
    decayed_deleted: int = Field(description="Entries below decay threshold removed")
    merged: int = Field(description="Pairs of similar entries merged")
    promoted: int = Field(description="Episodic entries promoted to procedural")


class PromotionResult(BaseModel):
    """Response for episodic-to-procedural promotion."""
    promoted: int = Field(description="Number of entries promoted")
```

**Validation:** `uv run ruff format app/memory/schemas.py && uv run ruff check app/memory/schemas.py && uv run pyright app/memory/schemas.py`

---

### Step 3: Add Repository Methods

**File:** `app/memory/repository.py`
**Action:** ADD 5 new methods to `MemoryRepository`

**3a. `find_similar(embedding, threshold=0.95) -> list[MemoryEntry]`**
- Cosine distance search where `1 - distance >= threshold`
- Used by store() for duplicate detection

**3b. `apply_decay(memory_type, decay_days) -> int`**
- `UPDATE memory_entries SET decay_weight = decay_weight * 0.95 WHERE memory_type = :type AND updated_at < now() - interval ':days days' AND is_evergreen = false`
- Use SQLAlchemy `update()` with `func.now() - text(f"interval '{days} days'")`
- Actually use: `from sqlalchemy import func, text` and `func.now() - func.cast(text(f"'{days} days'"), Interval)` or simpler: filter by `MemoryEntry.updated_at < utcnow() - timedelta(days=days)` (Python-side date calc is fine for this)
- Returns rowcount

**3c. `merge_entries(keep_id, remove_id, merged_content, merged_embedding) -> MemoryEntry`**
- Update keep entry with new content/embedding, max recalled_count, source="compaction"
- Delete remove entry
- Return updated entry

**3d. `find_similar_pairs(threshold=0.92) -> list[tuple[MemoryEntry, MemoryEntry, float]]`**
- Self-join on cosine distance, return pairs above threshold
- Use: `SELECT a.id, b.id, 1 - (a.embedding <=> b.embedding) as score FROM memory_entries a, memory_entries b WHERE a.id < b.id AND 1 - (a.embedding <=> b.embedding) > :threshold`
- Return as list of (entry_a, entry_b, score) tuples

**3e. `find_promotable(threshold=3) -> list[MemoryEntry]`**
- `SELECT * FROM memory_entries WHERE memory_type = 'episodic' AND recalled_count >= :threshold`

**3f. `update_memory_type(entry_id, new_type) -> None`**
- Simple UPDATE for promotion

**Validation:** `uv run ruff format app/memory/repository.py && uv run ruff check app/memory/repository.py && uv run pyright app/memory/repository.py`

---

### Step 4: Upgrade Service with Lifecycle Methods

**File:** `app/memory/service.py`
**Action:** UPDATE — add embedding singleton, modify store(), add compact/promote/recall_by_query

**4a. Add embedding singleton** (copy pattern from `app/knowledge/service.py:52-71`):
```python
from app.core.config import get_settings
from app.knowledge.embedding import (
    CachedEmbeddingProvider,
    EmbeddingProvider,
    get_embedding_provider,
)

_embedding_provider: EmbeddingProvider | None = None

def _get_embedding() -> EmbeddingProvider:
    global _embedding_provider
    if _embedding_provider is None:
        settings = get_settings()
        provider = get_embedding_provider(settings)
        if settings.embedding_cache_enabled:
            provider = CachedEmbeddingProvider(
                provider=provider,
                provider_name=settings.embedding_provider,
                ttl=settings.embedding_cache_ttl,
            )
        _embedding_provider = provider
    return _embedding_provider
```

**4b. Modify `store()`:**
- If `data.embedding` is None, generate it: `embedding = (await _get_embedding().embed([data.content]))[0]`
- Before storing, check for duplicates: `similar = await self.repository.find_similar(embedding, settings.memory_duplicate_threshold)`
- If duplicate found (cosine > 0.95), log skip and return existing entry
- Otherwise store with the generated embedding

**4c. Add `recall_by_query(request: MemoryRecallByQueryRequest)`:**
- Embed the query text: `embedding = (await _get_embedding().embed([request.query]))[0]`
- Delegate to existing `self.repository.recall(embedding, ...)`
- Increment recalled_count for results
- Return `list[MemoryRecallResponse]`

**4d. Add `compact() -> CompactionResult`:**
- Step 1: Apply decay per type using settings (procedural=90d, episodic=30d, query_pattern=60d, semantic=evergreen skip)
- Step 2: Delete decayed entries below `memory_decay_min_weight`
- Step 3: Find similar pairs (> merge_threshold), merge them
- Step 4: Promote eligible episodic entries
- Return CompactionResult with counts
- Log: `memory.service.compact_completed`

**4e. Add `promote_episodes() -> int`:**
- Find episodic entries with `recalled_count >= promotion_threshold`
- Update their memory_type to "procedural"
- Log: `memory.service.promote_completed`
- Return count

**Validation:** `uv run ruff format app/memory/service.py && uv run ruff check app/memory/service.py && uv run pyright app/memory/service.py`

---

### Step 5: Add Routes

**File:** `app/memory/routes.py`
**Action:** ADD 2 new endpoints

**5a. `POST /api/v1/memory/compact`** — Admin-only, triggers compact cycle
```python
@router.post("/compact", response_model=CompactionResult)
@limiter.limit("2/minute")
async def compact_memories(
    request: Request,
    service: MemoryService = Depends(get_service),
    _current_user: User = Depends(require_role("admin")),
) -> CompactionResult:
    _ = request
    return await service.compact()
```

**5b. `POST /api/v1/memory/recall/query`** — Text-based recall
```python
@router.post("/recall/query", response_model=list[MemoryRecallResponse])
@limiter.limit("10/minute")
async def recall_by_query(
    request: Request,
    data: MemoryRecallByQueryRequest,
    service: MemoryService = Depends(get_service),
    _current_user: User = Depends(require_role("admin", "agent")),
) -> list[MemoryRecallResponse]:
    _ = request
    return await service.recall_by_query(data)
```

Import new schemas: `CompactionResult`, `MemoryRecallByQueryRequest`.

**IMPORTANT:** Place `/compact` and `/recall/query` routes BEFORE `/{entry_id}` to avoid path parameter collision.

**Validation:** `uv run ruff format app/memory/routes.py && uv run ruff check app/memory/routes.py && uv run pyright app/memory/routes.py`

---

### Step 6: Add Repository Tests

**File:** `app/memory/tests/test_repository.py`
**Action:** ADD tests for new repository methods

Tests to add:
- `test_find_similar_returns_matches` — mock cosine distance query, verify threshold filtering
- `test_find_similar_returns_empty_no_matches`
- `test_apply_decay_updates_entries` — verify UPDATE executed with correct filters
- `test_apply_decay_returns_rowcount`
- `test_merge_entries_keeps_higher_recalled` — verify update + delete
- `test_find_similar_pairs_returns_above_threshold`
- `test_find_similar_pairs_empty_when_no_similar`
- `test_find_promotable_returns_episodic_above_threshold`
- `test_find_promotable_empty_when_none_qualify`
- `test_update_memory_type_executes`

**Validation:** `uv run pytest app/memory/tests/test_repository.py -v --tb=short`

---

### Step 7: Add Service Tests

**File:** `app/memory/tests/test_service.py`
**Action:** ADD tests for lifecycle methods

Tests to add (mock repository + embedding provider):
- `test_store_generates_embedding_when_none` — verify `_get_embedding().embed()` called
- `test_store_skips_duplicate` — mock find_similar returning entry, verify store NOT called
- `test_store_uses_provided_embedding` — verify embed NOT called when embedding already set
- `test_recall_by_query_embeds_text` — verify embed called with query text
- `test_recall_by_query_returns_scored_results`
- `test_compact_applies_decay_per_type` — verify apply_decay called with correct days per type
- `test_compact_deletes_decayed` — verify delete_decayed called
- `test_compact_merges_similar` — mock find_similar_pairs, verify merge_entries called
- `test_compact_promotes_episodes` — verify promote_episodes called
- `test_compact_returns_result` — verify CompactionResult fields
- `test_promote_episodes_updates_type` — mock find_promotable, verify update_memory_type called
- `test_promote_episodes_returns_count`

Mock pattern for embedding:
```python
with patch("app.memory.service._get_embedding") as mock_embed:
    mock_provider = AsyncMock()
    mock_provider.embed.return_value = [make_embedding()]
    mock_embed.return_value = mock_provider
```

**Validation:** `uv run pytest app/memory/tests/test_service.py -v --tb=short`

---

### Step 8: Add Route Tests

**File:** `app/memory/tests/test_routes.py`
**Action:** ADD tests for new endpoints

Tests to add:
- `test_compact_returns_result` — POST /compact with admin auth
- `test_compact_requires_admin` — verify non-admin gets 403
- `test_recall_by_query_returns_results` — POST /recall/query
- `test_recall_by_query_validates_max_length` — query exceeding 2000 chars gets 422

**Validation:** `uv run pytest app/memory/tests/test_routes.py -v --tb=short`

---

### Step 9: Final Validation

Run full suite:
```bash
uv run ruff format app/memory/ app/core/config.py
uv run ruff check --fix app/memory/ app/core/config.py
uv run pyright app/memory/
uv run mypy app/memory/
uv run pytest app/memory/tests/ -v --tb=short
```

## Preflight Warnings

- **Route ordering:** FastAPI matches routes in registration order. `POST /compact` and `POST /recall/query` must be registered BEFORE `GET /{entry_id}` — otherwise `/compact` is parsed as `entry_id="compact"`.
- **Embedding singleton reset in tests:** The module-level `_embedding_provider` must be reset between tests. Use `patch("app.memory.service._embedding_provider", None)` or `patch("app.memory.service._get_embedding")`.
- **find_similar_pairs self-join:** pgvector's `<=>` operator works on Vector columns. The raw SQL approach may need `text()` wrapping. Prefer SQLAlchemy `select()` with aliased tables.
- **Anti-pattern #5:** No unused imports — only import `CompactionResult`, `PromotionResult`, `MemoryRecallByQueryRequest` after adding the routes/service methods that use them.
- **Anti-pattern #11:** Adding `MemoryRecallByQueryRequest` won't break existing consumers since it's a new schema, not modifying existing ones.

## Security Checklist

- [x] All existing endpoints have `require_role()` — verified in routes.py
- [ ] New `POST /compact` uses `require_role("admin")` — admin-only
- [ ] New `POST /recall/query` uses `require_role("admin", "agent")`
- [ ] `@limiter.limit()` on both new endpoints
- [ ] `query: str` field has `max_length=2000` constraint
- [ ] No credentials exposed in compact/promote logs
- [x] `escape_like()` not needed — no ILIKE queries in memory

## Verification

- [ ] `make lint` passes (ruff format + check)
- [ ] `make types` passes (mypy + pyright)
- [ ] `uv run pytest app/memory/tests/ -v` — all tests pass, 50+ total
- [ ] `make security-audit-quick` passes
- [ ] Pyright errors <= baseline (0 errors before)
- [ ] New endpoints have auth + rate limiting
- [ ] Route ordering verified: /compact and /recall/query before /{entry_id}
