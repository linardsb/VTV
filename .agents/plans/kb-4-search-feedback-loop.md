# Plan: KB-4 Search Feedback Loop

## Context

RRF (Reciprocal Rank Fusion) weights for hybrid search are currently static (configured in AI-1.3 as 6 constants in `Settings`). Real usage patterns may differ from the hand-picked defaults — `keyword` queries may benefit from more fulltext weight than configured, and `semantic` queries vice versa. KB-4 closes the loop:

1. Capture user thumbs-up/down on cited chunks returned from search.
2. Aggregate feedback per `(query_type, chunk_rank_source)` over the last 30 days.
3. Recompute tuned RRF weights daily into Redis.
4. Read tuned weights at search time with fallback to static config.

## Security Context Assessment

| Context | Active? | Why |
|---------|---------|-----|
| CTX-AUTH  | No — reuses existing JWT auth only |
| CTX-RBAC  | **Yes** — new POST endpoint needs `get_current_user` + rate limit + IDOR considerations (feedback tied to user) |
| CTX-FILE  | No |
| CTX-AGENT | No |
| CTX-INFRA | **Yes (minor)** — new Redis keys; no Docker/nginx/CORS changes |
| CTX-INPUT | **Yes** — `query_hash` (path param), `chunk_id` + `relevant` (body). Need `max_length`, `Literal` types, escape_like not needed (no ILIKE) |

**Requirements applied:**
- POST endpoint uses `Depends(get_current_user)`, not role-gated (any authenticated user may rate results), with `@limiter.limit("60/minute")` per endpoint (sub-bucket).
- `query_hash` Path param: `Path(..., min_length=16, max_length=64, pattern=r"^[a-f0-9]+$")`.
- `chunk_id` body field: int with `ge=1`.
- Feedback rows are read-only from users' perspective (no list/get endpoint) — no IDOR surface.
- Redis key namespace: `knowledge:rrf:weights:{query_type}` — no user data in keys.

## Research Summary

**Current RRF implementation** (`app/knowledge/service.py`):
- `_detect_query_type()` at `service.py:112-132` classifies into `"keyword" | "semantic" | "mixed"` using `_KEYWORD_RE = r"\b\d{1,4}\b"` and question-word heuristics.
- `KnowledgeService.search()` at `service.py:575-765` reads weights from `settings.rrf_{type}_{vector|text}_weight` at lines 633-642, runs vector + fulltext branches, fuses with `score + weight / (60 + rank)` at lines 649-660, applies temporal boost and reranking.

**Current RRF config** (`app/core/config.py:269-274`): six floats, all currently hard-coded defaults `0.3/0.5/0.7`.

**Redis singleton** (`app/core/redis.py`): `get_redis()` returns `Redis.from_url(settings.redis_url, decode_responses=True)`. Pipeline operations are SYNC (anti-pattern #35), only `execute()` is async.

**Arq worker** (`app/core/jobs/worker.py`): cron pattern demonstrated by `run_compaction()`, `run_promotion()`, `run_daily_adherence()`. Feature-flag gated by `background_queue_enabled`. `_build_cron_jobs()` is the registration point.

**Reference feature**: `app/memory/` — has `lifecycle.py` with settings-gated `asyncio.create_task` + `get_db_context()` pattern, and matching arq cron wiring in `worker.py`.

**Reference migrations** (recent naming): `g5h6i7j8k9l0_add_parent_child_to_chunks.py`, `w7x8y9z0a1b2_add_lemmatized_content_to_chunks.py`. Use a fresh 12-char alphanumeric ID.

**Shared utilities reused**: `TimestampMixin` (models), `get_logger` (logging), `AppError` + `DomainValidationError` + `NotFoundError` (exceptions), `get_current_user` (auth), `limiter` (rate limit).

## Test Landscape

**Existing knowledge tests** (`app/knowledge/tests/`):
- `conftest.py` (82 lines) — only text/PPTX fixtures, no DB factories.
- `test_repository.py` (651 lines) — defines `make_document()`, `make_chunk()` factories at lines 15-57, `mock_db()` (AsyncMock) + `repo()` fixtures.
- `test_routes.py` (507 lines) — canonical route-test pattern: `_setup_auth_override()` autouse fixture (lines 54-60), `_mock_service()` via `AsyncMock(spec=KnowledgeService)`, `limiter.enabled = False` at line 100, `app.dependency_overrides[get_service] = lambda: mock_svc`.
- `test_embedding_cache.py` (245 lines) — canonical **Redis mock pattern** at lines 60-68: `AsyncMock()` with `mget=AsyncMock`, `pipeline=MagicMock(return_value=mock_pipeline)` where `mock_pipeline.execute = AsyncMock`.

**Reference background task tests** (`app/memory/tests/test_lifecycle.py`): patch `get_settings`, `asyncio.create_task`, `get_db_context` (async context manager), and service class; verify `create_task.call_count` and service method invocation.

**Security convention tests** (`app/tests/test_security.py`): `TestAllEndpointsRequireAuth` + `TestAllMutationsRateLimited` — new POST endpoint must appear in both.

**No fakeredis** — codebase uses `AsyncMock` directly. No existing `asyncio.sleep` patches to conflict with (anti-pattern #61).

## Type Check Baseline

Both tools clean across touched paths — **any new errors are attributable to KB-4 code**.

| Path | Pyright | Mypy |
|------|---------|------|
| `app/knowledge/` | 0 errors | 0 errors (44 files) |
| `app/core/redis.py`, `app/core/config.py` | 0 errors | 0 errors (2 files) |

## Files to Create/Modify

| Action | File | Purpose |
|--------|------|---------|
| CREATE | `alembic/versions/{id}_add_search_feedback.py` | `search_feedback` table |
| CREATE | `app/knowledge/feedback.py` | Feedback service: record, aggregate, recompute, get tuned weights |
| UPDATE | `app/knowledge/models.py` | Add `SearchFeedback` ORM model |
| UPDATE | `app/knowledge/schemas.py` | Add `SearchFeedbackCreate`, `RRFWeights` output |
| UPDATE | `app/knowledge/repository.py` | `create_feedback`, `count_feedback_by_query_type` |
| UPDATE | `app/knowledge/exceptions.py` (or create) | `FeedbackChunkMismatchError` |
| UPDATE | `app/knowledge/routes.py` | `POST /v1/knowledge/search/{query_hash}/feedback` |
| UPDATE | `app/knowledge/service.py` | Compute `query_hash` in search response; read tuned weights from Redis before weight selection |
| UPDATE | `app/core/config.py` | `knowledge_feedback_enabled` (default true), `knowledge_rrf_recompute_cron_hour` (default 3) |
| UPDATE | `app/core/jobs/worker.py` | Register daily `run_rrf_recompute` cron job (guarded by `background_queue_enabled`) |
| UPDATE | `app/knowledge/lifecycle.py` (or create) | `start_knowledge_tasks` / `stop_knowledge_tasks` fallback path when arq disabled |
| UPDATE | `app/main.py` lifespan | Wire `start/stop_knowledge_tasks` with `ShutdownCoordinator` |
| UPDATE | `docs/logging-standard.md` | Document new events: `knowledge.feedback.recorded`, `knowledge.rrf.recomputed`, `knowledge.rrf.recompute_failed` |
| UPDATE | `cms/apps/web/src/components/chat/...` | Thumbs-up/down buttons next to cited sources |
| UPDATE | `cms/apps/web/messages/{en,lv,ru}.json` | i18n keys `chat.feedback.helpful`, `chat.feedback.notHelpful`, `chat.feedback.thanks` |
| CREATE | `app/knowledge/tests/test_feedback.py` | Unit tests for service + weight computation |
| UPDATE | `app/knowledge/tests/test_routes.py` | Feedback endpoint tests |

## Data Model

```python
# app/knowledge/models.py
class SearchFeedback(Base, TimestampMixin):
    __tablename__ = "search_feedback"
    id: Mapped[int] = mapped_column(primary_key=True)
    query_hash: Mapped[str] = mapped_column(String(64), index=True)
    query_type: Mapped[str] = mapped_column(String(16))  # keyword|semantic|mixed
    chunk_id: Mapped[int] = mapped_column(ForeignKey("document_chunks.id", ondelete="CASCADE"), index=True)
    rank_source: Mapped[str] = mapped_column(String(16))  # "vector"|"fulltext"|"both"
    relevant: Mapped[bool] = mapped_column()
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    __table_args__ = (
        Index("ix_search_feedback_qtype_created", "query_type", "created_at"),
        UniqueConstraint("user_id", "query_hash", "chunk_id", name="uq_feedback_user_query_chunk"),
    )
```

`rank_source` is the critical column — tells us which branch (vector / fulltext / both) surfaced the chunk that was rated. Computed at search time from the per-chunk rank maps in `service.py`.

## Weight Computation Algorithm

```
For each query_type (keyword, semantic, mixed):
    rows = feedback from last 30 days WHERE query_type = X AND rank_source IN ('vector','fulltext')
    vec_up = count(relevant=true,  rank_source='vector')
    vec_dn = count(relevant=false, rank_source='vector')
    ft_up  = count(relevant=true,  rank_source='fulltext')
    ft_dn  = count(relevant=false, rank_source='fulltext')
    min_signals = 20  # below this, fall back to static config
    if (vec_up+vec_dn+ft_up+ft_dn) < min_signals:
        skip (preserve existing Redis value or fall back to config)
    vec_score = (vec_up + 1) / (vec_up + vec_dn + 2)   # Laplace-smoothed positive rate
    ft_score  = (ft_up  + 1) / (ft_up  + ft_dn  + 2)
    raw_vec = vec_score / (vec_score + ft_score)
    # Blend 70% tuned + 30% static to prevent runaway drift
    static_vec = settings.rrf_{type}_vector_weight
    vector_weight = round(0.7 * raw_vec + 0.3 * static_vec, 3)
    text_weight   = round(1 - vector_weight, 3)
    # Safety clamp
    vector_weight = max(0.1, min(0.9, vector_weight))
    text_weight = 1 - vector_weight
    SET knowledge:rrf:weights:{query_type} = {"vector": ..., "text": ..., "updated_at": ..., "sample_size": ...}  EX 48h
```

## Implementation Steps

### 1. Config additions
Add to `app/core/config.py` after existing `rrf_*` block:
```python
knowledge_feedback_enabled: bool = True
knowledge_rrf_recompute_cron_hour: int = 3  # UTC
knowledge_rrf_feedback_window_days: int = 30
knowledge_rrf_min_signals_per_type: int = 20
knowledge_rrf_blend_weight: float = 0.7  # tuned vs static
```
**Validation:** `uv run pyright app/core/config.py && uv run mypy app/core/config.py`

### 2. Migration
Create `alembic/versions/{new_id}_add_search_feedback.py` with `search_feedback` table + indexes + unique constraint. Generate revision id with `python -c "import secrets; print(secrets.token_hex(6))"`.
**Validation:** `uv run alembic upgrade head && uv run alembic downgrade -1 && uv run alembic upgrade head`

### 3. Models + schemas
- Add `SearchFeedback` ORM to `app/knowledge/models.py`.
- Add to `app/knowledge/schemas.py`:
  ```python
  QueryType: TypeAlias = Literal["keyword", "semantic", "mixed"]
  RankSource: TypeAlias = Literal["vector", "fulltext", "both"]
  class SearchFeedbackCreate(BaseModel):
      chunk_id: int = Field(..., ge=1)
      relevant: bool
  class RRFWeights(BaseModel):
      query_type: QueryType
      vector_weight: float
      text_weight: float
      sample_size: int
      updated_at: datetime | None
      source: Literal["tuned", "config_fallback"]
  ```
- Extend `SearchResponse` with `query_hash: str | None = None` (default `None` — keeps existing constructors in tests/factories working without changes; `service.py` always populates it).
- Extend `SearchResult` with `rank_source: RankSource = "both"` (default `"both"` — safe for any surface that constructs a SearchResult without rank-branch info, e.g. eval factories).
- **Required follow-up in production**: `service.py` MUST set `rank_source` explicitly from the rank maps (see Step 6) and MUST set `query_hash` on `SearchResponse`. The defaults exist solely so pre-existing callsites (evals factories, route tests) continue to compile.
**Validation:** `uv run ruff check --fix app/knowledge/ && uv run pyright app/knowledge/schemas.py app/knowledge/models.py`

### 4. Repository
Add to `app/knowledge/repository.py`:
- `async def create_feedback(self, *, user_id, query_hash, query_type, chunk_id, rank_source, relevant) -> SearchFeedback` — upsert on `(user_id, query_hash, chunk_id)`.
- `async def feedback_counts(self, *, since: datetime) -> dict[tuple[str, str], dict[str, int]]` returning `{(query_type, rank_source): {"up": n, "down": n}}`. Single query with `GROUP BY`.
- `async def get_chunk_exists(self, chunk_id: int) -> bool`.
**Validation:** `uv run pyright app/knowledge/repository.py`

### 5. Feedback service
Create `app/knowledge/feedback.py`:
- `class FeedbackService(db, redis)`:
  - `async def record(user_id, query_hash, query_type, chunk_id, rank_source, relevant) -> None` — validates chunk exists (`NotFoundError`), calls repo, logs `knowledge.feedback.recorded`.
  - `async def recompute_weights() -> dict[str, RRFWeights]` — implements algorithm above, writes Redis with `EX 172800`, logs `knowledge.rrf.recomputed` with sample sizes.
  - `async def get_tuned_weights(query_type) -> tuple[float, float]` — reads Redis key, falls back to `settings.rrf_{type}_{vector|text}_weight`. On `RedisError`: log warning, return config fallback (fail-open is acceptable here — search quality, not security).

**Query hash helper** in `service.py`:
```python
def _compute_query_hash(query: str, domain: str | None) -> str:
    normalized = " ".join(query.lower().split())
    key = f"{normalized}|{domain or ''}"
    return hashlib.sha256(key.encode()).hexdigest()[:32]
```
**Validation:** `uv run pyright app/knowledge/feedback.py && uv run mypy app/knowledge/feedback.py`

### 6. Wire tuned weights into search
Modify `KnowledgeService.search()` around `service.py:633-642`:
```python
tuned_vec, tuned_text = await self._feedback.get_tuned_weights(query_type)
vector_weight, text_weight = tuned_vec, tuned_text
```
Replace the if/elif/else block. Store `rank_source` in chunk result: track whether each id appeared in vector ranks, fulltext ranks, or both (already implicit in the two-pass loop — thread it through the SearchResult build).

Also set `query_hash` on `SearchResponse`.

**Validation:** `uv run pyright app/knowledge/service.py && uv run pytest app/knowledge/tests/ -x -q`

### 7. Route
Add to `app/knowledge/routes.py`:
```python
@router.post("/search/{query_hash}/feedback", status_code=204)
@limiter.limit("60/minute")
async def submit_search_feedback(
    request: Request,
    query_hash: str = Path(..., min_length=16, max_length=64, pattern=r"^[a-f0-9]+$"),
    query_type: QueryType = Query(...),
    rank_source: RankSource = Query(...),
    body: SearchFeedbackCreate,
    user: User = Depends(get_current_user),
    service: FeedbackService = Depends(get_feedback_service),
) -> None:
    await service.record(user.id, query_hash, query_type, body.chunk_id, rank_source, body.relevant)
```
**Validation:** `uv run pyright app/knowledge/routes.py`

### 8. Daily recompute task
In `app/core/jobs/worker.py` follow `run_compaction` / `run_promotion` pattern:
```python
async def run_rrf_recompute(ctx: dict) -> dict[str, object]:
    async with get_db_context() as db:
        redis = await get_redis()
        service = FeedbackService(db, redis)
        weights = await service.recompute_weights()
        return {"status": "completed", "query_types": list(weights)}
```
Register in `_build_cron_jobs()` as `cron(run_rrf_recompute, hour={knowledge_rrf_recompute_cron_hour}, minute=15)`.

**Fallback path** (for `background_queue_enabled=False`): add `app/knowledge/lifecycle.py` with `start_knowledge_tasks()` creating a loop that sleeps 24h then calls `recompute_weights()`. Use shutdown `asyncio.Event` (anti-pattern #62). Register with `ShutdownCoordinator` in `app/main.py` lifespan.

**Validation:** `uv run pyright app/core/jobs/worker.py app/knowledge/lifecycle.py`

### 9. Tests (`app/knowledge/tests/test_feedback.py`)

Minimum 12 tests:
1. `test_record_feedback_success` — happy path, repo `create_feedback` called with expected kwargs.
2. `test_record_feedback_chunk_not_found_raises` — `NotFoundError` when chunk missing.
3. `test_record_feedback_duplicate_upserts` — same `(user, query_hash, chunk)` twice → single row, latest `relevant` value.
4. `test_compute_weights_below_min_signals_returns_fallback` — < 20 signals → no Redis write for that type.
5. `test_compute_weights_keyword_vector_preferred` — 30 up-votes on vector for keyword queries → `vector_weight` shifts UP above static default.
6. `test_compute_weights_semantic_fulltext_preferred` — inverse direction.
7. `test_compute_weights_mixed_balanced_stable` — equal feedback → stays near 0.5.
8. `test_compute_weights_clamped_to_safety_bounds` — adversarial 100% one-sided feedback → weight clamped to [0.1, 0.9].
9. `test_compute_weights_writes_redis_with_ttl` — verify `set(..., ex=172800)`.
10. `test_get_tuned_weights_fallback_on_redis_error` — `RedisError` → returns `(settings.rrf_keyword_vector_weight, settings.rrf_keyword_text_weight)`.
11. `test_get_tuned_weights_fallback_on_missing_key` — no Redis key → fallback to config.
12. `test_query_hash_stable_across_whitespace` — normalized hash deterministic.

Plus route tests in `test_routes.py`:
13. `test_submit_feedback_success_204`.
14. `test_submit_feedback_requires_auth` — 401 without JWT.
15. `test_submit_feedback_invalid_query_hash` — 422 on non-hex.

Plus lifecycle test `test_feedback_lifecycle.py`:
16. `test_start_knowledge_tasks_respects_feature_flag`.
17. `test_stop_knowledge_tasks_cancels_cleanly`.

Use Redis mock pattern from `test_embedding_cache.py:60-68`. Use `make_chunk`, `make_document` factories from `test_repository.py:15-57`.

**Validation per test file:** `uv run pytest app/knowledge/tests/test_feedback.py -x -q`

### 10. Security convention tests
Add new endpoint to whatever iterates routes in `app/tests/test_security.py` (the `TestAllEndpointsRequireAuth` + mutation rate-limit tests auto-discover from the app). Run `uv run pytest app/tests/test_security.py -q` and confirm green.

### 11. CMS chat UI thumbs-up/down
- Update response type in `cms/apps/web/src/types/knowledge.ts` (if exists) or SDK re-gen: include `query_hash`, `rank_source` on citations.
- Add `<FeedbackButtons citation={c} queryHash={queryHash} queryType={qtype} />` to the citation list in the chat response component.
- Wire `POST /v1/knowledge/search/{query_hash}/feedback?query_type=...&rank_source=...` via SDK.
- i18n keys: `chat.feedback.helpful`, `chat.feedback.notHelpful`, `chat.feedback.thanks`, `chat.feedback.error`.
- Semantic tokens only — no hardcoded colors. Icons: `lucide-react` `ThumbsUp` / `ThumbsDown`. Size: `size-4`, gap uses design system spacing.
- Optimistic UI: disable buttons after click, show a small "Thanks" inline text.

### 12. Logging standard
Add three new events to `docs/logging-standard.md` under `knowledge` domain:
- `knowledge.feedback.recorded` — fields: `query_type`, `rank_source`, `relevant`, `user_id`
- `knowledge.rrf.recomputed` — fields: `query_types`, `sample_sizes`, `updated_weights`
- `knowledge.rrf.recompute_failed` — fields: `error`, `stage`

## Preflight Warnings (anti-pattern compliance)

- **#11 Schema additions**: Adding `query_hash` to `SearchResponse` and `rank_source` to `SearchResult` would break existing constructors. Mitigated by adding **defaults** (see step 3). Four existing callsites verified to rely on defaults:
  - `app/knowledge/tests/test_routes.py:354` — `SearchResult(...)` — safe with default
  - `app/knowledge/tests/test_routes.py:366` — `SearchResponse(...)` — safe with default
  - `app/knowledge/evals/tests/conftest.py:53-69` — `make_search_result()` factory — safe with default
  - `app/knowledge/evals/tests/test_runner.py:33-42` — `_make_search_response()` helper — safe with default
  - `app/core/agents/tools/knowledge/schemas.py` defines a separate `KnowledgeSearchResult`/`KnowledgeSearchResponse` — **not affected** (different schemas).
  - Only production construction sites (`service.py:725` for `SearchResult`, `service.py:802` for `SearchResponse`) must be updated to set the fields explicitly during Step 6.
- **#35 Redis pipeline is SYNC**: use `MagicMock` for pipeline, `AsyncMock` only for `execute()`.
- **#37 bare except**: recompute-failure handler must log (`knowledge.rrf.recompute_failed`).
- **#39 `date` shadowing**: n/a — no `date` fields here.
- **#54 Literal types**: `QueryType` and `RankSource` must be `TypeAlias = Literal[...]`, not plain strings.
- **#57 role leakage in errors**: feedback endpoint errors must not mention roles.
- **#60 `async def` as side_effect**: when mocking `recompute_weights` in lifecycle tests, use `new_callable=AsyncMock`.
- **#61 asyncio.sleep patching**: if lifecycle fallback uses `asyncio.sleep(86400)`, patch the *module-specific* reference `app.knowledge.lifecycle.asyncio.sleep`, and pair with a shutdown `asyncio.Event`.
- **#62 while True + shutdown event**: lifecycle fallback loop must accept `_shutdown_event` and check it in the except block.

## Security Checklist

For the new POST endpoint:
- [x] `get_current_user` dependency (no role gate — any user can vote)
- [x] `@limiter.limit("60/minute")` (sub-bucket configurable via `rate_limit_knowledge_feedback` — add to config if rate-limit tests demand)
- [x] Pydantic request schema (`SearchFeedbackCreate`) with `ge=1`
- [x] Path + query param validators (`min_length`, `max_length`, `pattern`, `Literal`)
- [x] No raw SQL; no LIKE — `escape_like()` not needed
- [x] `AppError` subclasses for chunk-not-found (auto-maps to 404)
- [x] No credentials or internal state in error responses
- [x] Redis failures fall back to static config (fail-open acceptable — search quality, not security boundary)
- [x] Unique constraint `(user_id, query_hash, chunk_id)` prevents vote stuffing (1 vote/user/chunk/query)

## Verification

- [ ] `uv run ruff format app/knowledge/ app/core/config.py app/core/jobs/worker.py`
- [ ] `uv run ruff check --fix app/knowledge/ app/core/config.py app/core/jobs/worker.py`
- [ ] `uv run pyright app/knowledge/ app/core/config.py app/core/jobs/worker.py` — must remain **0 errors** (baseline was 0)
- [ ] `uv run mypy app/knowledge/ app/core/config.py app/core/jobs/worker.py` — must remain **0 errors**
- [ ] `uv run pytest app/knowledge/tests/ -q` — all pass
- [ ] `uv run pytest app/tests/test_security.py -q` — convention tests include new endpoint
- [ ] `uv run pytest app/tests/test_ops_conventions.py -q` — logging taxonomy
- [ ] `make audit-log-taxonomy` — 3 new events recognized
- [ ] `make db-migrate` up + down + up clean
- [ ] Acceptance (manual): submit 20 thumbs-up signals on vector results for `keyword` queries → run recompute → `GET knowledge:rrf:weights:keyword` in Redis shows `vector > settings.rrf_keyword_vector_weight`. Next search uses tuned weights. Clear Redis key → next search falls back to config.
- [ ] `make check` green
- [ ] `make security-audit-quick` green

## Plan saved

`.agents/plans/kb-4-search-feedback-loop.md`
