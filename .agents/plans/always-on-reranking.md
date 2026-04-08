# Plan: AI-1.1 Always-On Cross-Encoder Reranking

## Context

Vector-only retrieval misranks ~30% of transit SOP queries. Cross-encoder reranking is already implemented (`app/knowledge/reranker.py`) and the config default is `reranker_provider="local"` — meaning reranking is technically always-on. However, three gaps remain:

1. **`sentence-transformers` is not an explicit dependency** — it's transitive only, so `pip install` from a clean env may not pull it
2. **No startup preloading** — the CrossEncoder model lazy-loads on first search (~2-5s cold-start penalty)
3. **Route test hardcodes `reranked=False`** — doesn't reflect production behavior
4. **No startup health log** for reranker readiness

## Security Context Assessment

- **CTX-INPUT** — No new user input paths; reranking operates on internally-fetched document chunks
- No other security contexts triggered — this change modifies defaults and adds preloading, no new endpoints

## Research Summary

### Current Architecture

**Config** (`app/core/config.py:171-174`):
```python
reranker_provider: str = "local"   # local, none
reranker_model: str = "BAAI/bge-reranker-v2-m3"
reranker_top_k: int = 10
```

**Reranker** (`app/knowledge/reranker.py`):
- `LocalRerankerProvider` — lazy-loads `CrossEncoder(model_name)` on `_get_model()`, runs inference via `asyncio.to_thread(model.predict, pairs)`
- `NoopRerankerProvider` — pass-through with score=1.0
- Factory: `get_reranker_provider(settings)` selects based on `reranker_provider`

**Search pipeline** (`app/knowledge/service.py:309-397`):
1. Embed query → 2. Parallel vector + fulltext search (50 candidates each) → 3. RRF fusion (k=60) → 4. Rerank top-10 via cross-encoder → 5. Return results with `reranked=True/False` flag

**Lazy singleton** (`app/knowledge/service.py:60-65`):
```python
def _get_reranker() -> RerankerProvider:
    global _reranker_provider
    if _reranker_provider is None:
        _reranker_provider = get_reranker_provider(get_settings())
    return _reranker_provider
```

**Lifespan** (`app/main.py:84-122`): Starts pollers, alert evaluator, geofence evaluator, WS subscriber. No model preloading.

## Test Landscape

- **71 tests** across 8 modules in `app/knowledge/tests/`
- `test_routes.py:362` — hardcodes `reranked=False` in search test mock
- No dedicated reranker unit tests (reranker.py is untested directly)
- Fixtures: `make_document()`, `make_chunk()`, `_mock_service()`, `_client()`
- Integration tests use `@pytest.mark.asyncio` + `@pytest.mark.integration`

## Type Check Baseline

| Target | Tool | Errors | Notes |
|--------|------|--------|-------|
| `app/knowledge/` | pyright | 0 | Clean |
| `app/knowledge/` | mypy | 3 | All in upstream deps, not in knowledge files |
| `app/core/config.py` | pyright | 0 | Clean |

## Files to Create/Modify

| Action | File | Purpose |
|--------|------|---------|
| UPDATE | `pyproject.toml` | Add `sentence-transformers>=3.0.0` to dependencies |
| UPDATE | `app/knowledge/reranker.py` | Add `warm_up()` method for startup preloading |
| UPDATE | `app/main.py` | Call reranker warm-up during lifespan startup |
| UPDATE | `app/knowledge/tests/test_routes.py` | Fix search test to use `reranked=True` |
| CREATE | `app/knowledge/tests/test_reranker.py` | Unit tests for reranker providers |

## Implementation Steps

### Step 1: Add explicit `sentence-transformers` dependency

**File:** `pyproject.toml`
**Action:** Add `"sentence-transformers>=3.0.0"` to the `dependencies` list (after `sentry-sdk`).

**Validation:** `uv run python -c "from sentence_transformers import CrossEncoder; print('OK')"`

---

### Step 2: Add `warm_up()` method to `LocalRerankerProvider`

**File:** `app/knowledge/reranker.py`
**Action:** Add an async `warm_up()` method that triggers model download/load and logs readiness. Also add it to the `RerankerProvider` protocol and `NoopRerankerProvider`.

```python
# In RerankerProvider protocol:
async def warm_up(self) -> None: ...

# In LocalRerankerProvider:
async def warm_up(self) -> None:
    """Pre-load the cross-encoder model so first search has no cold start."""
    start = time.monotonic()
    logger.info("knowledge.reranker.warming_up", model=self._model_name)
    await asyncio.to_thread(self._get_model)
    duration_ms = int((time.monotonic() - start) * 1000)
    logger.info("knowledge.reranker.loaded", model=self._model_name, duration_ms=duration_ms)

# In NoopRerankerProvider:
async def warm_up(self) -> None:
    """No-op warm up."""
    logger.info("knowledge.reranker.loaded", model="noop")
```

**Validation:** `uv run ruff format app/knowledge/reranker.py && uv run ruff check --fix app/knowledge/reranker.py && uv run pyright app/knowledge/reranker.py`

---

### Step 3: Add startup preloading in lifespan

**File:** `app/main.py`
**Action:** After the existing background task starts (after geofence evaluator), add reranker warm-up. Import `_get_reranker` from service or call `get_reranker_provider` directly.

```python
# After line 114 (start_geofence_evaluator):
from app.knowledge.reranker import get_reranker_provider
reranker = get_reranker_provider(settings)
await reranker.warm_up()
```

Note: This initializes a separate instance from the lazy singleton in `service.py`. To share the singleton, expose a `warm_up_reranker()` function from `service.py` that calls `_get_reranker().warm_up()`.

**Better approach — add to `service.py`:**
```python
async def warm_up_reranker() -> None:
    """Pre-load reranker model for startup."""
    provider = _get_reranker()
    await provider.warm_up()
```

Then in `main.py` (after `start_geofence_evaluator`):
```python
from app.knowledge.service import warm_up_reranker

# PREFLIGHT: Must wrap in try/except — TestClient triggers lifespan in tests,
# and model download would block/fail. Matches start_pollers() guard pattern.
try:
    await warm_up_reranker()
except Exception:
    logger.warning("knowledge.reranker.warm_up_failed", exc_info=True)
```

This ensures the singleton is initialized and shared. The try/except prevents test failures and graceful degradation if model isn't available.

**Validation:** `uv run ruff format app/main.py app/knowledge/service.py && uv run ruff check --fix app/main.py app/knowledge/service.py && uv run pyright app/main.py app/knowledge/service.py`

---

### Step 4: Update route test to reflect `reranked=True`

**File:** `app/knowledge/tests/test_routes.py:362`
**Action:** Change `reranked=False` to `reranked=True` in the search test mock.

**Validation:** `uv run pytest app/knowledge/tests/test_routes.py::test_search_documents -v`

---

### Step 5: Add reranker unit tests

**File:** `app/knowledge/tests/test_reranker.py` (CREATE)
**Action:** Test both providers:

1. `test_noop_reranker_preserves_order` — NoopRerankerProvider returns docs in order with score=1.0
2. `test_noop_reranker_respects_top_k` — truncates to top_k
3. `test_noop_reranker_empty_docs` — empty input returns empty
4. `test_noop_warm_up` — warm_up() completes without error
5. `test_local_reranker_reorders_by_score` — mock `CrossEncoder.predict` to return known scores, verify reordering
6. `test_local_reranker_empty_docs` — empty input returns empty
7. `test_local_warm_up_loads_model` — mock CrossEncoder, verify `_get_model()` called
8. `test_get_reranker_provider_local` — factory returns LocalRerankerProvider
9. `test_get_reranker_provider_none` — factory returns NoopRerankerProvider
10. `test_get_reranker_provider_unknown` — factory raises ValueError

Mock `sentence_transformers.CrossEncoder` to avoid model download in tests.

**Validation:** `uv run pytest app/knowledge/tests/test_reranker.py -v`

---

### Step 6: Run full validation

**Validation:** `make check` (lint + types + tests)

## Preflight Warnings

- `test_routes.py:362` — hardcoded `reranked=False` will change to `True`; no other tests reference this value
- `service.py:60-65` — lazy singleton pattern; warm-up must use `_get_reranker()` to share instance
- `reranker.py:67` — lazy import of `sentence_transformers` inside `_get_model()`; warm-up triggers this

## Security Checklist

No new endpoints added. No user input changes. Not applicable.

## Verification

- [ ] `make check` passes (lint + types + tests)
- [ ] `make security-audit-quick` passes
- [ ] Pyright errors ≤ baseline (0 errors before)
- [ ] `sentence-transformers` in explicit dependencies
- [ ] Startup log shows `knowledge.reranker.loaded` with duration_ms
- [ ] Search response returns `reranked: true` by default
- [ ] New reranker tests pass: `uv run pytest app/knowledge/tests/test_reranker.py -v`
- [ ] Security convention tests pass: `uv run pytest app/tests/test_security.py -v`
