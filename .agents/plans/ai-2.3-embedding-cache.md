# Plan: AI-2.3 Embedding Cache

## Context

Dispatchers ask the same questions repeatedly ("route 3 status", "which routes delayed"). Each query triggers an embedding API call (~200ms, costs per-token). Caching embeddings in Redis with TTL avoids redundant API calls, reducing latency from ~200ms to <5ms for cached queries and cutting embedding API costs.

## Security Context Assessment

- **CTX-INPUT**: No — cache operates on internal embedding vectors, not user-facing queries
- **CTX-INFRA**: Yes (light) — Redis key management, TTL configuration
- **CTX-AUTH/RBAC/FILE/AGENT**: No — no new endpoints, no file handling, no auth changes

Only CTX-INFRA applies: ensure no credentials in cache keys, use env-var-configurable TTL.

## Research Summary

### Current Embedding Architecture

- **Protocol**: `EmbeddingProvider` at `embedding.py:22-39` — `embed(texts: list[str]) -> list[list[float]]` + `dimension` property
- **Implementations**: `OpenAIEmbeddingProvider` (lines 42-99), `LocalEmbeddingProvider` (lines 102-158)
- **Factory**: `get_embedding_provider(settings)` at line 161
- **Singleton**: `_get_embedding()` in `service.py:56-61` — lazy global, used at both call sites

### Call Sites (2 total)

| File | Line | Context | Cache Benefit |
|------|------|---------|---------------|
| `service.py:252` | Document ingestion | Batch embed chunks | Low — unique content |
| `service.py:424` | Search query | Single query embed | **High** — repeated queries |

### Redis Access Pattern

- `get_redis()` from `app.core.redis` — async singleton, `decode_responses=True`
- Best reference pattern: `app/core/agents/quota.py:64-133` — Redis with graceful fallback
- Pipeline: `pipeline()` is sync builder, `.execute()` is async

### Config Pattern

Embedding settings at `config.py:164-169` use `embedding_*` prefix. Knowledge settings use `knowledge_*`. New settings follow `embedding_cache_*` naming.

## Test Landscape

- 12 test files in `app/knowledge/tests/`, `conftest.py` has `sample_upload`, `sample_latvian_text`, `sample_english_text`
- Embedding mocked via `patch("app.knowledge.service._get_embedding")` returning AsyncMock with `.embed` method
- Redis mocked via `patch("app.core.redis.get_redis")` returning AsyncMock — pattern from transit/geofence tests
- Anti-pattern #35: `redis.pipeline()` is SYNC (MagicMock), only `execute()` is async

## Type Check Baseline

- **Pyright `app/knowledge/`**: 0 errors, 0 warnings
- **MyPy `app/knowledge/`**: 0 errors (3 pre-existing in unrelated agent module)
- **Pyright `app/core/config.py`**: 0 errors
- **Pyright `app/core/redis.py`**: 0 errors

## Files to Create/Modify

| Action | File | Purpose |
|--------|------|---------|
| UPDATE | `app/core/config.py` | Add `embedding_cache_enabled` + `embedding_cache_ttl` settings |
| UPDATE | `app/knowledge/embedding.py` | Add `CachedEmbeddingProvider` wrapper class + `_normalize_query()` |
| UPDATE | `app/knowledge/service.py` | Wrap provider with cache in `_get_embedding()` |
| CREATE | `app/knowledge/tests/test_embedding_cache.py` | Unit tests for cache hit/miss/fallback/normalization |

## Implementation Steps

### Step 1: Add config settings

**File:** `app/core/config.py`
**Action:** Add two settings after `embedding_base_url` (line 169):

```python
    # Embedding cache (Redis-backed, avoids redundant API calls)
    embedding_cache_enabled: bool = True
    embedding_cache_ttl: int = 3600  # seconds (1 hour)
```

**Validation:** `uv run pyright app/core/config.py`

---

### Step 2: Add `CachedEmbeddingProvider` to embedding.py

**File:** `app/knowledge/embedding.py`
**Action:** Add after `LocalEmbeddingProvider` class (after line 158), before `get_embedding_provider`:

1. Add imports: `import hashlib`, `import json`
2. Add `_normalize_query(text: str) -> str` — lowercase, strip, sort words
3. Add `CachedEmbeddingProvider` class that wraps any `EmbeddingProvider`:

```python
def _normalize_query(text: str) -> str:
    """Normalize text for cache key consistency.

    Lowercases, strips whitespace, sorts words so
    'route 3 status' and 'status route 3' produce the same key.

    Args:
        text: Raw query text.

    Returns:
        Normalized text for hashing.
    """
    return " ".join(sorted(text.lower().split()))


class CachedEmbeddingProvider:
    """Decorator that adds Redis caching to any EmbeddingProvider.

    Cache key: emb:{provider}:{blake2b(normalized_text)[:16]}
    Value: JSON-serialized float list
    TTL: Configurable via settings.embedding_cache_ttl

    Falls back to the wrapped provider on any Redis error.
    """

    def __init__(
        self,
        provider: EmbeddingProvider,
        provider_name: str,
        ttl: int,
    ) -> None:
        self._provider = provider
        self._provider_name = provider_name
        self._ttl = ttl

    def _cache_key(self, text: str) -> str:
        normalized = _normalize_query(text)
        digest = hashlib.blake2b(normalized.encode(), digest_size=8).hexdigest()
        return f"emb:{self._provider_name}:{digest}"

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts with per-text Redis cache lookup.

        For each text: check cache → on hit, use cached vector;
        on miss, batch-embed all misses via the wrapped provider,
        then store results in Redis.

        Args:
            texts: Texts to embed.

        Returns:
            List of embedding vectors (same order as input).
        """
        try:
            from app.core.redis import get_redis
            redis_client = await get_redis()
        except Exception:
            logger.warning("knowledge.embedding_cache.redis_unavailable")
            return await self._provider.embed(texts)

        keys = [self._cache_key(t) for t in texts]
        results: list[list[float] | None] = [None] * len(texts)
        miss_indices: list[int] = []

        # Batch cache lookup
        try:
            cached_values = await redis_client.mget(keys)
            for i, val in enumerate(cached_values):
                if val is not None:
                    results[i] = json.loads(val)
            miss_indices = [i for i, r in enumerate(results) if r is None]
        except Exception:
            logger.warning("knowledge.embedding_cache.read_failed")
            miss_indices = list(range(len(texts)))

        cache_hits = len(texts) - len(miss_indices)
        if cache_hits > 0:
            logger.info(
                "knowledge.embedding_cache.hit",
                hits=cache_hits,
                total=len(texts),
            )

        if not miss_indices:
            # All cache hits — cast away None
            return [r for r in results if r is not None]

        # Embed cache misses
        miss_texts = [texts[i] for i in miss_indices]
        logger.info(
            "knowledge.embedding_cache.miss",
            misses=len(miss_indices),
            total=len(texts),
        )
        fresh_embeddings = await self._provider.embed(miss_texts)

        # Store in cache (fire-and-forget, don't block on write errors)
        try:
            pipe = redis_client.pipeline()
            for idx, embedding in zip(miss_indices, fresh_embeddings):
                pipe.setex(keys[idx], self._ttl, json.dumps(embedding))
            await pipe.execute()
        except Exception:
            logger.warning("knowledge.embedding_cache.write_failed")

        # Merge cached + fresh
        for idx, embedding in zip(miss_indices, fresh_embeddings):
            results[idx] = embedding

        return [r for r in results if r is not None]

    @property
    def dimension(self) -> int:
        return self._provider.dimension
```

**Note:** Import `hashlib` and `json` at the top of the file (after `import time`).

**Validation:** `uv run ruff format app/knowledge/embedding.py && uv run ruff check --fix app/knowledge/embedding.py && uv run pyright app/knowledge/embedding.py`

---

### Step 3: Integrate cache in service.py singleton

**File:** `app/knowledge/service.py`
**Action:** Modify `_get_embedding()` (lines 56-61) to wrap provider with cache:

```python
def _get_embedding() -> EmbeddingProvider:
    """Get or create the embedding provider singleton (with optional cache)."""
    global _embedding_provider
    if _embedding_provider is None:
        settings = get_settings()
        provider = get_embedding_provider(settings)
        if settings.embedding_cache_enabled:
            from app.knowledge.embedding import CachedEmbeddingProvider

            provider = CachedEmbeddingProvider(
                provider=provider,
                provider_name=settings.embedding_provider,
                ttl=settings.embedding_cache_ttl,
            )
        _embedding_provider = provider
    return _embedding_provider
```

Add `EmbeddingProvider` type import if not already present (it is — line 25 of service.py imports from `embedding`).

**Validation:** `uv run ruff format app/knowledge/service.py && uv run ruff check --fix app/knowledge/service.py && uv run pyright app/knowledge/service.py`

---

### Step 4: Write tests

**File:** `app/knowledge/tests/test_embedding_cache.py`

Tests to implement:

**Query normalization:**
- `test_normalize_query_basic` — lowercase + strip + sort words
- `test_normalize_query_idempotent` — same input → same output
- `test_normalize_query_word_order_invariant` — "route 3" == "3 route"

**Cache key generation:**
- `test_cache_key_deterministic` — same text → same key
- `test_cache_key_includes_provider` — key starts with `emb:{provider}:`
- `test_cache_key_different_text` — different texts → different keys

**Cache hit/miss:**
- `test_all_cache_hits` — mock mget returns all cached → provider.embed NOT called
- `test_all_cache_misses` — mock mget returns all None → provider.embed called, setex pipeline used
- `test_partial_cache_hit` — mix of hits and misses → only misses sent to provider, order preserved

**Redis error fallback:**
- `test_redis_unavailable_falls_back` — get_redis raises → provider.embed called directly
- `test_redis_read_error_falls_back` — mget raises → all texts sent to provider
- `test_redis_write_error_still_returns` — pipeline.execute raises → embeddings still returned

**Integration with service:**
- `test_get_embedding_returns_cached_provider_when_enabled` — verify singleton wraps
- `test_get_embedding_returns_raw_provider_when_disabled` — verify no wrapping

**Mocking pattern:**
```python
mock_redis = AsyncMock()
mock_redis.mget = AsyncMock(return_value=[...])
mock_pipeline = MagicMock()
mock_pipeline.setex = MagicMock()
mock_pipeline.execute = AsyncMock(return_value=[])
mock_redis.pipeline = MagicMock(return_value=mock_pipeline)
```

**Validation:** `uv run pytest app/knowledge/tests/test_embedding_cache.py -v`

## Preflight Warnings

- Anti-pattern #35: `redis.pipeline()` is SYNC → use `MagicMock()` not `AsyncMock()` in tests
- Anti-pattern #34: Redis async stubs may need `# type: ignore[misc]` on await lines — check after implementation
- Anti-pattern #5: Don't import `CachedEmbeddingProvider` in service.py top-level if only used conditionally — use lazy import inside `_get_embedding()`
- `_embedding_provider` global is reset by test teardown? Check if tests use `_embedding_provider = None` cleanup

## Security Checklist

No new endpoints added. Internal-only change.

- [x] No credentials in cache keys (uses blake2b hash of normalized text)
- [x] TTL configurable via env var (`EMBEDDING_CACHE_TTL`)
- [x] Graceful fallback on Redis failure (no denial of service)
- [x] No PII in cache values (float vectors only, not reversible to text)

## Verification

- [ ] `make check` passes (lint + types + tests)
- [ ] `make security-audit-quick` passes
- [ ] Pyright errors ≤ baseline (0 errors before)
- [ ] New tests pass: `uv run pytest app/knowledge/tests/test_embedding_cache.py -v`
- [ ] Existing knowledge tests still pass: `uv run pytest app/knowledge/tests/ -v`
- [ ] Security convention tests pass: `uv run pytest app/tests/test_security.py -v`
