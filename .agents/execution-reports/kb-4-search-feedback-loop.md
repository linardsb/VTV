# Execution Report: KB-4 Search Feedback Loop

**Plan:** `.agents/plans/kb-4-search-feedback-loop.md`
**Implemented:** 2026-04-14
**Status:** Backend complete; CMS thumbs-up/down UI deferred

## What Shipped

- Migration `1f0fc7681339_add_search_feedback.py` — `search_feedback` table with indexes + unique constraint
- `app/knowledge/feedback.py` — `FeedbackService` (`record`, `recompute_weights`, `get_tuned_weights`) + `compute_query_hash` helper
- `app/knowledge/lifecycle.py` — in-process `start/stop_knowledge_tasks` (shutdown-event loop, no `asyncio.sleep` patching surface area)
- `app/core/jobs/worker.py` — `run_rrf_recompute` arq job + cron at `knowledge_rrf_recompute_cron_hour:15` UTC
- `app/knowledge/models.py` — `SearchFeedback` ORM with `Index` + `UniqueConstraint` in `__table_args__`
- `app/knowledge/repository.py` — `chunk_exists`, `upsert_feedback` (pg `ON CONFLICT ON CONSTRAINT`), `feedback_counts` (FILTER-based aggregation)
- `app/knowledge/schemas.py` — PEP 695 `type QueryType` / `type RankSource`, `SearchFeedbackCreate`, `RRFWeights`; added `query_hash` + `query_type` to `SearchResponse` and `rank_source` to `SearchResult` (safe defaults for pre-existing constructors)
- `app/knowledge/service.py` — tuned-weight lookup via `FeedbackService.get_tuned_weights(query_type)` with fallback, `rank_source` tracking via `vector_ids` / `text_ids` sets, `compute_query_hash` + `query_type` on response
- `app/knowledge/routes.py` — `POST /v1/knowledge/search/{query_hash}/feedback` (JWT + 60/min, hex path validator, `QueryType` / `RankSource` Literal query params, `SearchFeedbackCreate` body) + `get_feedback_service` dependency
- `app/knowledge/exceptions.py` — `FeedbackChunkNotFoundError` (inherits `NotFoundError`)
- `app/core/config.py` — 5 new settings: `knowledge_feedback_enabled`, `knowledge_rrf_recompute_cron_hour`, `knowledge_rrf_feedback_window_days`, `knowledge_rrf_min_signals_per_type`, `knowledge_rrf_blend_weight`
- `app/main.py` — wired `start_knowledge_tasks` into lifespan + `ShutdownCoordinator` registration
- `docs/logging-standard.md` — documented `jobs.worker.rrf_recompute_failed`
- 17 unit tests in `test_feedback.py` (hash, record, recompute, Redis fallback, lifecycle flags) + 3 route tests in `test_routes.py`

## Deviations From Plan

| Area | Deviation | Why |
|------|-----------|-----|
| Lifecycle loop | Used `asyncio.wait_for(shutdown_event.wait(), timeout=…)` instead of `asyncio.sleep(…)` with event check | Eliminates anti-pattern #61 risk entirely — no `asyncio.sleep` reference to patch. Cleaner than the plan sketch |
| Type aliases | Used PEP 695 `type QueryType = Literal[...]` instead of `TypeAlias = Literal[...]` | Matches existing `app/transit/schemas.py` convention and satisfies Ruff UP040 |
| CMS thumbs-up/down UI (plan step 11) | Deferred | `/be-execute` scope is backend-only. Backend publishes `query_hash` / `query_type` / `rank_source` — UI work needs SDK regen + `/fe-planning add chat feedback buttons` |

## Bugs Found During Implementation

| Bug | Root Cause | Fix Applied |
|-----|-----------|-------------|
| `test_worker_has_cron_jobs` asserted `len == 3` | Added 4th cron job (`run_rrf_recompute`) | Updated assertion to `== 4` and added `run_rrf_recompute` to `test_worker_has_functions`. Location: `app/core/jobs/tests/test_worker.py` |
| `test_search_skips_hyde_when_disabled` tried to `await` an unmocked `get_redis()` | New `settings.knowledge_feedback_enabled` is truthy on `MagicMock()` by default, so `search()` entered the feedback branch and called `await get_redis()` (not mocked) | Added `s.knowledge_feedback_enabled = False` on the mock settings object. Also set `latvian_lemmatizer_enabled = False` and `knowledge_parent_context_enabled = False` defensively. Location: `app/knowledge/tests/test_hyde.py` |

## Validation

- `ruff format` / `ruff check` — clean across touched files
- `mypy app/` — 0 errors (531 files)
- `pyright app/` — 0 errors
- `ruff check --select=S` — clean on KB-4 code
- Knowledge + jobs + security test suites — **434 passed**
- Unit test suite overall: 2384 passed, 2 pre-existing failures unrelated to KB-4 (flaky `test_predict_logs_structured_event`, baseline `test_no_undocumented_log_events` drift from uncommitted LV-2/3 transit work)

## Not Tested (Pending Docker)

`feedback_counts` uses PostgreSQL's `FILTER (WHERE …)` aggregation via SQLAlchemy `func.count().filter(...)`. Tested with unit mocks only; integration coverage deferred until Docker is available.

## Next Steps

1. `/commit` the backend work
2. Regenerate `@vtv/sdk` so `SearchResponse.query_hash` / `query_type` and `SearchResult.rank_source` appear in the TypeScript types
3. `/fe-planning add chat feedback buttons` for the deferred CMS UI
