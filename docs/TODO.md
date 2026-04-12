# VTV TODO

Planned features and improvements. Each item links to its detailed planning document where available.

> Architecture: Vertical Slice, security-first, async-first, Latvian-first
> Pattern: Each task = one planning + implementation session
> Agent Intelligence Plan: [docs/PLANNING/agent-intelligence-plan.md](PLANNING/agent-intelligence-plan.md)

---

## Progress Overview

```
Backend API       ██████████████████████░░  99%  (12/12 features + analytics + compliance exports + multi-feed GTFS-RT + WebSocket live streaming + alerts + fleet + geofences)
CMS Frontend      ███████████████████████░  99%  (17 pages live, real API on all, WebSocket real-time, multi-feed support, EU compliance exports, analytics dashboard, fleet devices/map/telemetry, geofences)
Testing           ████████████████████░░░░  90%  (1618 unit tests, 106 security tests, 81 e2e tests, CI pipeline live with security gates)
Infrastructure    ██████████████████████░░  97%  (Docker, nginx+Brotli, Gunicorn multi-worker, Redis rate limiting, Makefile, 25 slash commands, CI/CD, 6 security audits, SDLC security framework, context-triggered security SDC)
Latvia Platform   ████████░░░░░░░░░░░░░░░  35%  (Riga GTFS + PostGIS + WebSocket + multi-feed GTFS-RT + TimescaleDB historical storage, no multi-city yet)
Agent Intelligence ██████████████████░░░░░  97%  (Phases AI-1 through AI-7 complete — see docs/TODO-archive.md. AI-8 complete: AI-8.1 circuit-breaker primitive + AI-8.2 per-provider health metrics + AI-8.3 provider chain integration with degraded fallback. AI-9 complete: AI-9.1 expanded injection detection + AI-9.2 blocking mode + AI-9.3 output exfiltration validation. AI-10 complete: AI-10.1 heading-breadcrumb citations + AI-10.2 citation format regression tests. AI-11.1 complete: synthetic QA pair generation. Next up: AI-11.2-11.4 retrieval metrics + eval runner + baselines.)
Intelligence/ML   ░░░░░░░░░░░░░░░░░░░░░░░   0%  (Phase 4 — not started)
```

## In Progress

### E2E Testing Maturity

- [ ] **CRUD E2E Tests** - Tests that create/edit/delete records and verify persistence. Current 81 tests cover page loads, filters, navigation, and UI interactions but don't test full write operations (require seeded test data).

---

## Agent Intelligence — Phased Implementation

Techniques learned from merkle-email-hub's production multi-agent system. Full analysis: [docs/PLANNING/agent-intelligence-plan.md](PLANNING/agent-intelligence-plan.md).

**Phases AI-1 through AI-7 complete ✅** — all 28 subtasks done. Detailed records: [docs/TODO-archive.md](TODO-archive.md). Active work starts at AI-8.

---

### Phase AI-8: Circuit Breaker + LLM Provider Reliability (3 days)

> **Sprint deliverable:** LLM provider calls wrapped in a state-machine circuit breaker that tracks failure rates and trips to fallback before latency spikes affect dispatchers. Per-provider health metrics exposed via admin endpoint. Independent of phases AI-1..AI-7.

#### AI-8.1 Circuit Breaker State Machine ✅
**Status:** Done — `app/core/agents/circuit_breaker.py` implements `CircuitState` enum (CLOSED / OPEN / HALF_OPEN), `@dataclass(frozen=True) BreakerConfig` with `__post_init__` validation of all 5 knobs, and `CircuitBreaker` async class with `call(fn, /, *args, **kwargs) -> T` through-caller. State reads/writes are guarded by `asyncio.Lock`; the lock is **never** held across the `fn` await (3 separate acquisitions for `_before_call` / `_record_success` / `_record_failure`, mirroring `app/core/resilience.py` semantics). Sliding-window failure rate via `collections.deque(maxlen=window_size)`; rate trigger only arms once the window is full, so 2 failures in 2 calls with `window_size=10` do NOT trip — prevents false positives on short bursts. Consecutive-failure counter resets on any success in CLOSED. `HALF_OPEN` uses a dedicated `success_threshold` probe counter; any failure during HALF_OPEN immediately returns to OPEN with `trigger="probe_failure"`. Pluggable `time_fn: Callable[[], float] = time.monotonic` for deterministic `ManualClock` tests. `CircuitBreakerOpenError(AgentError)` added to `app/core/agents/exceptions.py` and wired into `agent_exception_handler` → HTTP 503 + `setup_agent_exception_handlers`. 5 new pydantic-settings env-var-backed settings in `app/core/config.py` (`circuit_breaker_enabled/failure_threshold/recovery_timeout_s/success_threshold/failure_rate_threshold`) with defaults exactly matching the plan. 7 structured log events in the `agent.circuit_breaker.*` namespace: `opened` (CLOSED→OPEN, fields `provider`+`failure_count`+`failure_rate`+`trigger`), `half_opened` (OPEN→HALF_OPEN, `elapsed_s`), `closed` (HALF_OPEN→CLOSED, `successful_probes`), `reopened` (HALF_OPEN→OPEN probe_failure), `rejected` (blocked by OPEN breaker, `state`), `probe_success`, `probe_failure` — log fields exclude credentials, provider endpoints, and raw exception `repr()` (CTX-AGENT compliance). `docs/logging-standard.md` agent taxonomy extended with all 7 events. Agent-module-local utility (not `app/shared/`) per the three-feature rule — separate from the existing GTFS-RT breaker at `app/core/resilience.py`, which was left untouched. 19 unit tests in `app/core/agents/tests/test_circuit_breaker.py`: state transitions (6 — starts_closed, consecutive trip, sliding-window rate trip, recovery to HALF_OPEN, HALF_OPEN→CLOSED, HALF_OPEN→OPEN on probe fail), counting/reset (3), recovery-timeout boundary (2 — just-below rejection + exactly-at transition), sliding-window invariants (2), concurrency (2 — concurrent fast-fail after trip, sequential probes close), config validation (1 — all 5 invariants), exception propagation (1), structlog event assertion via `structlog.testing.capture_logs` (1), full 5-fail → OPEN → reject → recover → 2 probes → CLOSED spec scenario (1). `ManualClock` + `make_breaker_config` + `make_breaker` factories appended to `app/core/agents/tests/conftest.py`. `app/core/agents/circuit_breaker.py` + new tests report 0 pyright / 0 mypy errors; wider agent-module baseline preserved (pyright 5 / mypy 3 — all pre-existing in `tools/transit/static_store.py`, `tools/transit/client.py`, `pipeline.py`). 356 agent tests + 106 security convention tests green. **Out of scope (AI-8.2 follow-up):** wiring the breaker into `AgentService._execute()` around each `agent.run()` call and building the per-provider registry — intentionally landed as a separate, kill-switch-gated change. Plan: [.agents/plans/ai-8.1-circuit-breaker.md](../.agents/plans/ai-8.1-circuit-breaker.md). (2026-04-11)

**What:** Create `app/core/agents/circuit_breaker.py` — classic 3-state breaker (`CLOSED` → `OPEN` → `HALF_OPEN` → `CLOSED`) wrapping each LLM provider invocation. Tracks consecutive failures, failure rate over a sliding window, and automatic recovery probes.
**Why:** Current `FallbackModel` only catches hard exceptions at call-time — it cannot preempt a degrading primary provider (timeouts, 5xx spikes). A circuit breaker preempts by opening after N consecutive failures or when the sliding-window failure rate exceeds a threshold, cutting dispatcher-visible latency by 5-30s per failing request.
**Implementation:**
- `app/core/agents/circuit_breaker.py`:
  - `@dataclass(frozen=True) BreakerConfig`: `failure_threshold: int = 5`, `recovery_timeout_s: float = 30.0`, `success_threshold: int = 2`, `window_size: int = 20`, `failure_rate_threshold: float = 0.5`
  - `CircuitBreaker` class with async `call(fn, *args)` method — raises `CircuitBreakerOpenError` when open, records success/failure on each call, sliding-window deque for rate computation
  - State transitions: `CLOSED`→`OPEN` on consecutive/rate trip; `OPEN`→`HALF_OPEN` after `recovery_timeout_s`; `HALF_OPEN`→`CLOSED` after `success_threshold` successes; `HALF_OPEN`→`OPEN` on any failure
  - Thread-safe via `asyncio.Lock` (per-instance)
- `app/core/config.py` — 5 new settings: `circuit_breaker_enabled: bool = True`, `circuit_breaker_failure_threshold: int = 5`, `circuit_breaker_recovery_timeout_s: float = 30.0`, `circuit_breaker_success_threshold: int = 2`, `circuit_breaker_failure_rate_threshold: float = 0.5`
- Structured logging taxonomy: `agent.circuit_breaker.opened`, `agent.circuit_breaker.half_opened`, `agent.circuit_breaker.closed`, `agent.circuit_breaker.rejected` (request blocked by open breaker), `agent.circuit_breaker.probe_success`, `agent.circuit_breaker.probe_failure`
- 15+ unit tests: state transitions (6), failure counting (3), recovery timeout (2), sliding-window rate (2), concurrent calls (2), config gating (1)

**Verify:** Mock a provider that fails 5 times — breaker opens, 6th call raises `CircuitBreakerOpenError` without invoking the provider. Wait past `recovery_timeout_s`, breaker goes `HALF_OPEN`, 2 successful probes close it.

#### AI-8.2 Per-Provider Health Metrics + Admin Endpoint ✅
**Status:** Complete. Plan: `.agents/plans/ai-8.2-provider-health-metrics.md`. Execution report: `.agents/execution-reports/ai-8.2-provider-health-metrics.md`.
**What:** Added `ProviderHealthTracker` singleton that records per-provider success/failure counts, p50/p95 latency, last failure/success timestamps, and current breaker state. Exposed via admin-only `GET /v1/chat/provider-health` endpoint.
**Why:** Ops needs visibility into which LLM provider is degrading before opening incidents. Current observability is zero — failures show up only as GlitchTip errors or user-reported slow responses.
**Shipped:**
- `app/core/agents/provider_health.py`:
  - `@dataclass ProviderHealth`: `provider_name`, `state: CircuitState`, `total_calls`, `total_failures`, `failure_rate`, `p50_latency_ms`, `p95_latency_ms`, `last_failure_at`, `last_success_at`, bounded 100-observation `_latencies_ms` deque
  - `ProviderHealthTracker` singleton with `record_call(provider, *, latency_ms, success, state)`, `get_health(provider)`, `get_all()` (deep-copied + sorted), `period_start()`, `reset()`
  - `_percentile()` gates on `<2` observations to avoid `statistics.StatisticsError`; `quantiles(method="inclusive")` matches pandas/numpy linear interpolation
  - Lazy 00:00 UTC daily reset via `_maybe_reset()` called on every public method (mirrors `metrics.py` AI-5.3 pattern)
  - `track_provider_call()` async context manager — wraps the 3 LLM call sites in `service.py` (complex pipeline, correction loop, fallback `agent.run`). Fail-open: `record_call` errors log `agent.provider_health.record_failed` and never block LLM results
  - `_extract_provider_name()` helper — handles `None` → default, `str` → split on `:`, pydantic_ai.Model instance → lowercased class name with `"model"` suffix stripped
- `app/core/agents/routes.py` — new admin-only `GET /v1/chat/provider-health` (`require_role("admin")`, `60/minute` rate limit) returning `ProviderHealthResponse` with period metadata + sorted provider snapshots
- `app/core/agents/schemas.py` — `ProviderHealthSnapshot` + `ProviderHealthResponse` Pydantic models with `ConfigDict(strict=True)`
- `app/core/agents/service.py` — 3 instrumentation sites wrapped in `async with track_provider_call(tier_model, get_settings().llm_provider)`
- 19 unit tests: tracker primitives (9), provider name extraction (4), singleton lifecycle (2), endpoint 200/403 + state field (4)
- No new env vars, no kill switch — always-on, rollback via wrapping instrumentation in `try/except`
- **Out of scope (AI-8.3 follow-up):** wiring a per-provider `CircuitBreaker` registry into `_execute()` — until then, the `state` field always reports `"closed"`

**Verify:** Admin fires a `GET /v1/chat/provider-health` request; response returns period metadata + per-provider snapshots with success/failure counts and p95 latency.

#### AI-8.3 Circuit Breaker Integration with FallbackModel ✅
**Status:** Done — `app/core/agents/llm.py` introduces a process-wide per-provider breaker registry (`get_breaker`, `get_breaker_state`, `reset_provider_breakers`) plus `invoke_provider_chain[T](call, *, settings)` — a generic async wrapper that walks `[settings.llm_provider, settings.llm_fallback_provider]` and routes the LLM call through `breaker.call(...)`. The chain catches `CircuitBreakerOpenError` (logging `agent.provider_chain.preempted`) and any other exception (logging `agent.provider_chain.fallback`) and continues to the next provider. When the chain is exhausted it logs `agent.provider_chain.exhausted` and raises `AllProvidersUnavailableError(providers_tried)`. Crucial design fix during execution: the wrapper does NOT short-circuit on a direct `breaker.state is OPEN` check — it always goes through `breaker.call`, because OPEN→HALF_OPEN recovery transitions only fire inside `_before_call`. Skipping the call would have left the breaker stuck OPEN forever after `recovery_timeout_s` elapsed. When `circuit_breaker_enabled` is False the helper flattens to a single direct call against the primary with **zero** registry writes — preserves pre-AI-8 semantics byte-for-byte and keeps Pydantic AI's `FallbackModel` as the belt-and-braces layer. New `AllProvidersUnavailableError(AgentError)` in `exceptions.py` (constructor stores `providers_tried: list[str]`) is wired into `agent_exception_handler` → HTTP 503 alongside the existing `CircuitBreakerOpenError`. `app/core/agents/service.py` was refactored: the monolithic `_execute()` is now a 3-helper dispatch (`_execute_complex_tier`, `_execute_correction_tier`, `_execute_fallback_tier`), each one wrapping its LLM call in a closure that runs through `invoke_provider_chain`; per-iteration observability is preserved by `track_provider_call(None, provider_name)` inside the closure so the chain provider name (not the tier-model class name) keys both the breaker registry and the AI-8.2 health tracker. `_execute()` catches `AllProvidersUnavailableError` and returns a static, user-safe degraded `_PipelineOutcome("All LLM providers are temporarily unavailable. Please retry in 30 seconds.", warnings=[], confidence=None, tools_used=())` — `confidence=None` is deliberate so the AI-6.5 confidence re-route gate doesn't fire a doomed retry, and `warnings=[]` skips QA + footnote rendering. Provider names never leak into the user-facing content (CTX-AGENT). `app/core/agents/provider_health.py` no longer hardcodes `state=CLOSED` in `track_provider_call`: it now does a deferred `from app.core.agents.llm import get_breaker_state` (avoids module-load circular import) and passes the live `CircuitState` into `record_call(state=...)` on both success and failure branches — the existing `state=` parameter contract from AI-8.2 was preserved, no changes to `ProviderHealth` fields. The stale AI-8.2-followup TODO in `_extract_provider_name`'s docstring is removed; the dataclass + module docstrings are refreshed to reflect that `state` is now live. New tests: `app/core/agents/tests/test_llm.py` (5 unit tests — lazy registry init, unregistered provider returns CLOSED, disabled-mode passthrough with no registry writes, primary-OPEN skips to fallback, all-exhausted raises) plus a new `TestCircuitBreakerIntegration` class in `test_service.py` (8 tests — single-provider trip routes to fallback, fallback also fails returns degraded, both open returns degraded with no LLM call, fast-fail under 200ms, two consecutive requests both fast-fail, recovery via HALF_OPEN→CLOSED after `recovery_timeout_s=0`, kill-switch off doesn't register breakers, kill-switch off propagates raw exceptions). New `_reset_provider_breakers` autouse fixture appended to `conftest.py` clears the registry around every agent test — same pattern as `_reset_skill_cache`. The pre-existing `test_chat_failure_raises_agent_execution_error` was renamed to `test_chat_failure_with_breaker_disabled_raises_agent_execution_error` and now patches `get_settings` in **both** `service` and `llm` modules to force the kill-switch path; this is the canonical regression test for the byte-for-byte preserved behavior. Validation gates: `ruff format/check` clean across 386 files; mypy 3 errors (baseline preserved — `tools/transit/static_store.py:149/150` + `pipeline.py:136`); pyright 5 errors (baseline preserved — `pipeline.py` x4 + `tools/transit/client.py:193`); 388 agent tests + 1482 unit tests + 106 security convention tests green. The single failing test (`tools/transit/tests/test_client.py::test_fetch_feed_http_error`) was verified to fail on clean `main` before any AI-8.3 changes — pre-existing test pollution from the unrelated GTFS-RT breaker singleton in `app/core/resilience.py`, not introduced here. **Open question deferred:** per-tier-model resolution per chain attempt (open question #3 in the plan) — the current wiring keeps `tier_model` constant across chain iterations and only swaps the breaker key, accepting that with `FallbackModel(primary, fallback)` configured the fail-fast benefit primarily kicks in for single-provider tier overrides. A future refinement can resolve a single-provider Model per chain attempt. Plan: [.agents/plans/ai-8-3-circuit-breaker-fallback-integration.md](../.agents/plans/ai-8-3-circuit-breaker-fallback-integration.md). Execution report: [.agents/execution-reports/ai-8.3-circuit-breaker-fallback-integration.md](../.agents/execution-reports/ai-8.3-circuit-breaker-fallback-integration.md). (2026-04-11)

**Verify:** Inject a primary-provider failure that takes 30s to time out. With circuit breaker enabled, the 6th+ request fails-fast via fallback in <100ms (not 30s). Disable via `CIRCUIT_BREAKER_ENABLED=false` and confirm pre-AI-8 behavior is preserved byte-for-byte.

---

### Phase AI-9: Prompt Injection Hardening (3 days)

> **Sprint deliverable:** Current injection detection is log-only with 3 regex patterns. This phase expands detection, adds confidence-scored blocking, and adds response-side output validation to prevent data exfiltration via crafted responses.

#### ✅ AI-9.1 Expanded Detection Patterns + Confidence Scoring (done 2026-04-12)
**Implemented:** `app/core/agents/injection_detector.py` — 31 compiled regex patterns across 6 OWASP LLM01 categories (override, role_hijack, extraction, delimiter_escape, tool_misuse, encoding). EN/LV multi-language (RU excluded — not supported). Per-match `InjectionSignal(frozen=True)` with confidence scoring (P1=0.90-0.95, P2=0.60-0.70, P3=0.30-0.40). `InjectionResult` with aggregate confidence + multi-signal boost (cross-category >=2 → +0.10, same-category >=2 → +0.05, capped 0.95). Cyrillic homoglyph normalization. Module-level `detect_injection()` singleton. `BaseAgentService.chat()` Phase 2 calls detector with threshold-based log level (warning/error). Config: `prompt_injection_block_threshold=0.85`, `prompt_injection_warn_threshold=0.5`. 42 unit tests. Plan: `.agents/plans/ai-9-1-injection-detection-patterns.md`.

> **RU language note:** Russian language injection patterns were deliberately excluded. AI-9.2 and AI-9.3 plans that reference RU must be updated to exclude them.

#### ✅ AI-9.2 Blocking Mode for High-Confidence Injections (done 2026-04-12)
**Implemented:** `app/core/agents/base.py` Phase 2 — mode-aware blocking gate. `prompt_injection_mode: Literal["warn","block"] = "warn"` in `app/core/config.py` (env var `PROMPT_INJECTION_MODE=block` to enable). When `mode="block"` and `aggregate_confidence >= prompt_injection_block_threshold` (0.85), raises `PromptInjectionBlockedError(AgentError)` → HTTP 400 with generic message (`"Request blocked by content safety policy"` — never echoes injection text). Below-threshold or `mode="warn"` detections log `agent.injection.detected` as before. Blocked requests log `agent.injection.blocked` at error level with `pattern_ids`, `aggregate_confidence`, `prompt_length` (never raw prompt). 12 unit tests in `test_injection_blocking.py` (exception hierarchy, HTTP 400 mapping, response body safety, block/allow threshold boundaries, warn mode passthrough, config defaults, structured log assertions). Plan: `.agents/plans/ai-9-2-injection-blocking-mode.md`.

#### ✅ AI-9.3 Output-Side Data Exfiltration Validation (done 2026-04-12)
**Implemented:** `app/core/agents/output_validator.py` — 15 compiled regex patterns across 5 categories (base64_blob, suspicious_url, system_prompt_leak, pii_leak, code_block). `OutputIssue(frozen=True)` with pattern_id, confidence (0.0-1.0), category, matched_text (truncated 100 chars). `OutputValidationResult` with aggregate confidence + multi-signal boost (cross-category >=2 → +0.10, same-category >=2 → +0.05, capped 0.95). Code fence stripping pre-processing: most patterns scan prose-only text; `code_fence_only` patterns (EX-CODE-01) fire only in transit/vault domains. Module-level `validate_output()` singleton. Config: `output_validation_enabled=True`, `output_validation_mode: Literal["warn","block"] = "warn"`, `output_validation_block_threshold=0.80`. Wired into `BaseAgentService.chat()` Phase 10b (between `_execute()` and `_post_process()`). `OutputExfiltrationBlockedError(AgentError)` → HTTP 400 with generic message. Fail-open: validator exceptions never block responses. 33 unit tests + 14 integration tests (pattern detection, confidence scoring, false positive resilience, block/warn modes, threshold boundaries, config toggles, structured log assertions, fail-open). Plan: `.agents/plans/ai-9-3-output-exfiltration-validation.md`.

---

### Phase AI-10: Enhanced Citation Quality (2 days)

> **Sprint deliverable:** Agent responses cite chunks by heading breadcrumb + section ("Emergency Procedures > Route Deviation") instead of generic "chunk 5". Dispatchers can locate source material in 2 clicks instead of scrolling.
> **Depends on:** AI-4.2 (heading_path column already populated on chunks)

#### ✅ AI-10.1 Render Heading Breadcrumbs in Agent Responses (done 2026-04-12)
**Implemented:** Heading-breadcrumb citations wired through the knowledge search tool and both agent system prompts. `_heading_to_slug()` handles Latvian diacritics via NFKD decomposition. `_build_citation_anchor()` formats `"doc-title - Section > Subsection"`. Two new fields on `KnowledgeSearchResult`: `citation_anchor` (pre-formatted link text) and `url_fragment` (URL-safe anchor slug from last heading segment). Bug fix: `heading_path` was not propagated from `DocumentChunk` to `SearchResult` in `service.py` — now set on every result (parent-context expansion still overwrites when parent exists). Both `KNOWLEDGE_SYSTEM_PROMPT` and unified `SYSTEM_PROMPT` updated with breadcrumb-aware citation format and examples. Legacy chunks (null `heading_path`) fall back to filename-only citation. Frontend anchor landing (`#section-foo` scroll) deferred to a separate FE task. 11 new tests (3 slug generation incl. Latvian diacritics, 4 citation anchor builder, 3 full-flow integration, 1 prompt content assertion). Plan: `.agents/plans/ai-10.1-heading-breadcrumb-citations.md`.

#### ✅ AI-10.2 Agent-Side Citation Format Regression Test (done 2026-04-12)
**Implemented:** 3 new eval cases (knowledge_011-013) added to `knowledge.yaml` with a 6th `citation_format_correct` quality criterion. Case 011 asserts heading-breadcrumb path is present in citation. Case 012 asserts section anchor fragment matches `url_fragment` from tool returns. Case 013 tests legacy-doc fallback when `heading_path` is null — citation must gracefully use filename-only format without fabricating breadcrumbs. `REQUIRED_CRITERIA_COUNT = 5` replaced with `MIN_CRITERIA_COUNT = 5` / `MAX_CRITERIA_COUNT = 6` range validation in `EvalCase.__post_init__`. 8 new/updated tests: 6-criteria acceptance, too-many rejection (now 7), production count (10→13), criteria range validation, AI-10.2-specific assertions, YAML round-trip for 6-criteria cases. Plan: `.agents/plans/ai-10.2-citation-format-regression-tests.md`.

---

### Phase AI-11: RAG Retrieval Eval Pipeline (4 days)

> **Sprint deliverable:** Retrieval quality measured independently of agent response quality. Synthetic QA pairs generated from existing documents, then replayed through `KnowledgeService.search()` to measure faithfulness, relevance, and completeness. `make rag-eval` runs the full retrieval evaluation suite.
> **Depends on:** Phase AI-4 (parent-child chunking), Phase AI-7 (eval framework patterns)
> **Distinct from AI-7:** AI-7 evaluates end-to-end agent responses. AI-11 isolates the retrieval layer (pgvector hybrid search + RRF + rerank + parent expansion) so retrieval regressions can be diagnosed without confounding from LLM behavior.

#### AI-11.1 Synthetic QA Pair Generation from Documents ✅ (2026-04-12)
**What:** Create `app/knowledge/evals/qa_generator.py` — sampler that picks N chunks from the indexed corpus, uses a fast-tier LLM to generate a plausible question for each (in the chunk's language), and records `(question, source_chunk_id, source_heading_path, language)` as the ground-truth set.
**Why:** Hand-writing retrieval test cases doesn't scale and can't cover corpus drift. Generating synthetic QA pairs from the actual corpus guarantees the ground truth references real documents and stays in sync as the KB grows.
**Implemented:**
- `app/knowledge/evals/schemas.py` — `QAPair`, `RetrievalMetrics`, `EvalReport` frozen dataclasses
- `app/knowledge/evals/qa_generator.py` — chunk sampler (stratified by language, filters short/list/table chunks, prefers heading_path), LLM question generation via `pydantic_ai.Agent` (fast tier, same pattern as HyDE), path-sandboxed JSONL writer, CLI with `--count`/`--output-dir`/`--lv-ratio`
- `app/knowledge/evals/__main__.py` — `python -m app.knowledge.evals` entry point
- `Makefile` — `make rag-eval-generate COUNT=100`
- JSONL output git-ignored under `evals/rag/`
- 12 unit tests: schema immutability/serialization (2), chunk filtering (3), LLM success/failure (2), JSONL output + path sandboxing (3), end-to-end pipeline (1), CLI (1)
- Plan: `.agents/plans/ai-11-1-synthetic-qa-generation.md`

**Verify:** `make rag-eval-generate COUNT=20` produces 20 QA pairs in `evals/rag/qa_pairs_{timestamp}.jsonl`. Manual spot-check: 18/20 questions are plausible dispatcher queries whose source chunk is the correct answer.

#### AI-11.2 Retrieval Metrics — Faithfulness, Relevance, Completeness
**What:** Create `app/knowledge/evals/metrics.py` — computes three metrics per QA pair after replaying the question through `KnowledgeService.search()`:
1. **Relevance** — binary: was the source chunk in the top-k results? (recall@k)
2. **Position** — what rank did the source chunk receive? (MRR contribution)
3. **Completeness** — did retrieval surface all chunks that cover the answer, or just one? (for multi-chunk ground truth)
**Why:** These three metrics decompose retrieval quality. Relevance catches "retrieval missed the right doc". Position catches "right doc is at rank 8, user sees top 3". Completeness catches "retrieval found one section but missed a cross-reference".
**Implementation:**
- `app/knowledge/evals/metrics.py`:
  - `compute_metrics(qa_pair: QAPair, search_results: list[SearchResult]) -> RetrievalMetrics`
  - `@dataclass(frozen=True) RetrievalMetrics`: `relevance_hit: bool`, `rank: int | None`, `mrr_contribution: float`, `completeness: float` (0.0-1.0)
  - `aggregate_metrics(per_pair: list[RetrievalMetrics]) -> AggregateReport` — recall@1, recall@3, recall@10, MRR, mean completeness
  - Completeness computation: for each QA pair, ground truth is all chunks sharing the same `parent_chunk_id` or `heading_path` as the source; completeness = matched / total
- Faithfulness handled in AI-11.3 (needs LLM judge, not just rank-based math)
- 12+ unit tests: relevance hit/miss (2), rank extraction (2), MRR math (2), completeness with parent groups (3), aggregate math (2), edge-cases (no results, single result) (1)

**Verify:** Replay 20 QA pairs through the retrieval layer. Report recall@3 ≥ 0.85 on the current system. If below, that's the retrieval regression signal worth acting on.

#### AI-11.3 RAG Eval Runner + Faithfulness Judge
**What:** Create `app/knowledge/evals/runner.py` — runs QA pairs through `KnowledgeService.search()`, computes AI-11.2 metrics, plus an LLM-judged **faithfulness** score: given the retrieved chunks as context, does a fast-tier LLM answer the QA pair's question correctly? (Binary pass/fail).
**Why:** Rank-based metrics miss semantic correctness. A chunk can be rank 1 but still be the wrong answer due to ambiguity. LLM-judged faithfulness validates that the retrieved context actually supports answering the question.
**Implementation:**
- `app/knowledge/evals/runner.py`:
  - `RAGEvalRunner.run(qa_pairs: list[QAPair]) -> EvalReport`
  - For each pair: call `KnowledgeService.search(question)`, compute metrics via AI-11.2, call `FaithfulnessJudge.judge(question, top_k_results, source_chunk_content)`
  - `FaithfulnessJudge` uses `resolve_tier_model("fast")` with a 3-criterion prompt: grounded (answer derivable from chunks), accurate (matches source_chunk_content), complete (no key info missing)
  - Fail-open on any LLM error: mark faithfulness as `error`, continue; never crash the runner
  - Path-sandboxed output via `Path.resolve().is_relative_to()` (same pattern as AI-7.2)
  - Never logs raw chunk content or question text — only IDs, scores, latencies
- Output: `evals/rag/report_{timestamp}.json` with per-pair + aggregate metrics
- CLI: `python -m app.knowledge.evals.runner --qa-pairs evals/rag/qa_pairs_*.jsonl --output evals/rag/`
- `Makefile` — `make rag-eval` (generate + run), `make rag-eval-report` (run on existing QA set)
- 14+ unit tests: runner happy path (2), faithfulness judge success/failure fallback (2), metrics integration (2), path sandboxing (2), CLI arg parsing (2), output schema (2), 0-pair edge case (1), error trace format (1)

**Verify:** `make rag-eval` generates 100 QA pairs, runs them through retrieval, produces a report with recall@3, MRR, mean faithfulness. Report should show current-system numbers ≥ baseline targets (recall@3 ≥ 0.85, faithfulness ≥ 0.80). If below, file a retrieval-quality ticket.

#### AI-11.4 RAG Regression Baselines + CI Integration
**What:** Generate initial retrieval baselines from first `make rag-eval` run. Future runs compare and flag regressions > 3 percentage points on any metric. Add `make rag-eval-check` as CI gate.
**Why:** Retrieval layer has many moving parts (chunker version, reranker model, RRF weights, embedding provider, HyDE toggle). Any of these can silently regress retrieval quality. Baselines + CI gate prevent deploying a regression.
**Implementation:**
- `app/knowledge/evals/regression.py`:
  - `generate_baseline(report: EvalReport) -> RAGBaseline`
  - `check_regression(current: EvalReport, baseline: RAGBaseline, tolerance: float = 0.03) -> list[Regression]`
  - Baseline fields: `recall_at_1`, `recall_at_3`, `recall_at_10`, `mrr`, `mean_completeness`, `mean_faithfulness`, `generated_at`, `corpus_checksum` (sha256 of all chunk ids + hashes — invalidates baseline when corpus changes materially)
  - Baseline JSON: `evals/rag/baseline.json` (committed to git, unlike traces which are git-ignored)
- `Makefile` — `make rag-eval-check` (runs full pipeline, exits 1 on regression), `make rag-eval-update-baseline` (regenerates baseline after intentional changes)
- Optional CI wiring deferred: add `rag-eval-check` to CI pipeline gated behind a `RUN_RAG_EVAL` env var so it only runs on explicit opt-in (it's expensive — LLM calls per pair)
- 10+ unit tests: baseline generation (2), regression detection per metric (4), tolerance math (1), corpus checksum mismatch triggers warning (1), update-baseline flow (1), report format (1)

**Verify:** Run `make rag-eval` to establish baseline. Deliberately weaken the reranker (e.g., disable it via config). Run `make rag-eval-check` — exits 1 with a report showing recall@3 dropped from 0.88 → 0.81, MRR dropped accordingly. Re-enable reranker, rerun, exits 0.

---

### Additional Agent Improvements — Summary

| Phase | Focus | Days | Depends on |
|-------|-------|------|------------|
| AI-8  | Circuit breaker + provider health | 3 | — |
| AI-9  | Prompt injection hardening | 3 | AI-9.1/9.2/9.3 done (2026-04-12) |
| AI-10 | Heading-breadcrumb citations | 2 | AI-4.2, AI-7.1 | Complete (2026-04-12) |
| AI-11 | RAG retrieval eval pipeline | 4 | AI-4, AI-7 | AI-11.1 done (2026-04-12) |

Total remaining agent hardening: **3 days** across 3 subtasks (AI-11.2, AI-11.3, AI-11.4). AI-8, AI-9, AI-10 complete. AI-11.1 complete. AI-11.2-11.4 (retrieval metrics, eval runner, baselines) should run after AI-7 is fully green to reuse its eval infrastructure patterns.

---

## Operations & Platform Hardening — Phased Implementation

Operational maturity work distinct from the AI/ML tracks. Focus: secrets discipline, application metrics, durable background work, per-user authorization, and documentation infrastructure. These phases are independent of AI-8..AI-11 and can be executed in parallel by a second track.

> **Not duplicated from elsewhere:** `CRUD E2E Tests` is already tracked in § In Progress. Circuit breaker + provider health is AI-8. Prompt injection blocking is AI-9. RAG regression guard is AI-11.4. The phases below cover gaps NOT already in another section.
>
> **Starting-state note:** `.env` is currently git-ignored and NOT tracked in git history (verified via `git ls-files .env`). OPS-1 is forward-looking hardening — preventing the next accidental commit, not purging an existing one. Pre-existing agent-module baseline: pyright 5 / mypy 3 errors in `tools/transit/static_store.py`, `tools/transit/client.py`, `pipeline.py` (per AI-8.1 completion note) — OPS-5.1 clears these.

---

### Phase OPS-1: Secrets Discipline & Credential Lifecycle (1 day)

> **Sprint deliverable:** Pre-commit secrets scanning is installed in the local dev loop (not just CI), structured logs never leak credentials even when exceptions bubble through, and operators have a documented runbook for rotating every secret the platform holds.

#### OPS-1.1 Commit `.pre-commit-config.yaml` at Repo Root
**What:** Add `.pre-commit-config.yaml` at the repository root with hooks for ruff-format, ruff-check, mypy, detect-secrets, and trailing-whitespace/end-of-file fixes. Wire `pre-commit install` into a `make bootstrap` target so first-time contributors get hooks automatically on clone. `.pre-commit-config.yaml` does NOT exist today — verified via `ls`.
**Why:** `make install-hooks` exists but is opt-in — a new contributor can ship code through lint that only fails in CI 10 minutes later, and detect-secrets never runs against the first commit. Enforcing hooks locally is a ~1 day, one-time investment that pays back on every PR.
**Implementation:**
- `.pre-commit-config.yaml` (new, at repo root):
  - `ruff` (repo `astral-sh/ruff-pre-commit`) — `ruff-format` + `ruff-check --fix`
  - `mypy` (local hook — runs `uv run mypy app/` to inherit the strict config already in `pyproject.toml`)
  - `detect-secrets` (repo `Yelp/detect-secrets`) with `--baseline .secrets.baseline`; generate initial baseline via `detect-secrets scan > .secrets.baseline`
  - `trailing-whitespace`, `end-of-file-fixer`, `check-yaml`, `check-added-large-files` from `pre-commit-hooks`
- `Makefile` — add `make bootstrap` target running `uv sync --all-extras && pre-commit install && pre-commit install --hook-type commit-msg`. Keep the existing `install-hooks` target as an alias for back-compat.
- `docs/CONTRIBUTING.md` — first step is `make bootstrap`. Document the detect-secrets allowlist workflow (`pre-commit run detect-secrets --all-files` to update baseline intentionally).
- `.github/workflows/*.yml` — add `pre-commit run --all-files` as an early CI job so PRs fail fast if a contributor skipped local hooks.
**Verify:** Fresh `git clone`, run `make bootstrap`, modify a file to add `GROQ_API_KEY="gsk_realkey"`, attempt to commit — detect-secrets blocks. Ruff violations are auto-fixed on commit. CI's `pre-commit run --all-files` passes on a clean tree.

#### OPS-1.2 Structured-Log Secret Sanitization Filter
**What:** Add a `structlog` processor that redacts known-sensitive field names (`api_key`, `token`, `authorization`, `password`, `groq_api_key`, `google_api_key`, `jina_api_key`, `sentry_dsn`, `jwt_secret_key`, `cookie`, `set-cookie`, `refresh_token`, `secret`) from every log event before JSON serialization, plus a redactor that scrubs `exc_info` stack frames for the same patterns.
**Why:** structlog is configured (`docs/logging-standard.md`) but there is no global allowlist of sensitive field names. An exception during LLM setup can surface with `exc_info=True` containing the config repr — which includes API keys — and it lands in GlitchTip. Redacting at the processor level is defense-in-depth regardless of which call site leaks.
**Implementation:**
- `app/core/logging.py` (or wherever structlog is configured):
  - `SENSITIVE_KEYS: frozenset[str] = frozenset({"api_key", "token", "authorization", "password", "groq_api_key", "google_api_key", "jina_api_key", "sentry_dsn", "jwt_secret_key", "secret", "refresh_token", "cookie", "set-cookie"})`
  - `redact_sensitive(logger, method_name, event_dict: dict[str, Any]) -> dict[str, Any]` — recurses into nested dicts and lists, replaces matching keys with `"<redacted>"`, preserves all other keys. Case-insensitive key matching.
  - Insert processor immediately before `structlog.processors.JSONRenderer()` in the chain.
  - Wrap `format_exc_info` with a post-processor that applies regex substitution covering `GROQ_API_KEY=\S+`, `Authorization: Bearer \S+`, JWT pattern `eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+`.
- 8 unit tests: top-level key redaction (1), nested dict redaction (1), list-of-dicts redaction (1), case-insensitive match (1), exc_info JWT redaction (1), exc_info bearer redaction (1), non-sensitive pass-through (1), empty dict edge case (1).
**Verify:** Force an exception inside `app/core/agents/llm.py` provider setup. Inspect the GlitchTip event — no API key visible in any field, no JWT visible in the stack frame. `logger.info("probe", api_key="real_key_here")` renders `"api_key": "<redacted>"` in JSON output.

#### OPS-1.3 Credential Rotation Runbook
**What:** Write `docs/runbooks/credential-rotation.md` with step-by-step procedures for rotating every secret VTV holds (JWT secret key, GROQ, Google, Jina, Sentry DSN, Redis password, PostgreSQL password, Hetzner SSH key, GitHub Actions secrets). Each secret has: location, rotation command, impact/downtime, verification, rollback.
**Why:** On-call has zero playbook for an actual credential incident. A compromised GROQ key at 2am today means googling the dashboard and hoping.
**Implementation:**
- `docs/runbooks/credential-rotation.md` — one section per secret: **Location** (env var name, where it is set in prod), **Rotation command**, **Downtime** (zero / brief / rolling restart), **Verification** (how to confirm new key works), **Rollback**.
- `docs/runbooks/README.md` — runbook index (creates a runbook home that OPS-5.3 and later phases can extend).
- Cross-link from `CLAUDE.md` § Operations.
- Dry-run the runbook against a staging environment for each secret to capture the actual command output as a reference block inside the doc.
**Verify:** A new on-call engineer can take `docs/runbooks/credential-rotation.md` cold, rotate the GROQ key from scratch, and verify the fallback chain is working without reading any other document.

---

### Phase OPS-2: Application Metrics & Deep Health Checks (3 days)

> **Sprint deliverable:** `GET /metrics` exposes Prometheus-format request latency histograms, cache hit/miss counters, agent tool execution time, circuit breaker state, database pool utilization, and background poller liveness. `GET /health` probes every critical dependency in parallel and returns a structured per-dependency status object, not just a 200.

#### OPS-2.1 Prometheus `/metrics` Endpoint
**What:** Add `prometheus-client` dependency and expose a `/metrics` endpoint on the main FastAPI app. Register core counters, histograms, and gauges for HTTP requests, DB pool, Redis cache, agent execution, circuit breaker state (wiring the AI-8.1 breaker's state transitions to a gauge), and background-poller liveness.
**Why:** Sentry/GlitchTip tracks errors but gives zero visibility into latency percentiles, cache hit rates, provider health over time, or rate of "slow but not failing" requests. Ops is blind to degradation until the error rate spikes — that is a 15-minute lag minimum.
**Implementation:**
- `pyproject.toml` — add `prometheus-client ^0.21`.
- `app/core/metrics.py` (new):
  - `REQUEST_LATENCY = Histogram("vtv_http_request_duration_seconds", "HTTP request latency", ["method", "path", "status"], buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0))`
  - `DB_POOL_IN_USE = Gauge("vtv_db_pool_in_use", "SQLAlchemy connections in use")` + `DB_POOL_SIZE`, `DB_POOL_OVERFLOW`
  - `REDIS_CACHE_HITS = Counter("vtv_redis_cache_hits_total", "Redis cache hit count", ["cache_name"])` + parallel `_misses_total`
  - `AGENT_TOOL_DURATION = Histogram("vtv_agent_tool_duration_seconds", "Agent tool invocation latency", ["tool_name", "status"])`
  - `CIRCUIT_BREAKER_STATE = Gauge("vtv_circuit_breaker_state", "0=closed 1=half_open 2=open", ["provider"])`
  - `POLLER_LAST_TICK = Gauge("vtv_poller_last_tick_seconds", "Seconds since the poller last ticked", ["poller_name"])`
- `app/main.py` — mount `prometheus_client.make_asgi_app()` at `/metrics`. Access control via IP allowlist at the reverse-proxy layer (scrapers do not carry JWTs).
- `app/core/metrics_middleware.py` — async middleware that wraps request handling and records `REQUEST_LATENCY.labels(method, path_template, status).observe(duration)`. Path templates come from FastAPI's route resolver, NOT the raw URL, to keep cardinality finite.
- Wire observations at call sites:
  - `app/core/rate_limit.py` — Redis hit/miss counters
  - `app/core/agents/circuit_breaker.py` — update `CIRCUIT_BREAKER_STATE` gauge inside `_transition_to_*` hooks (reuses the existing AI-8.1 state machine)
  - Agent tool layer — wrap tool calls with a histogram observation decorator
  - Background pollers (`app/gtfs_rt/poller.py`, WebSocket subscriber, memory lifecycle workers) — update `POLLER_LAST_TICK` gauge on each tick
- Cardinality guard: document max label combinations per metric in `app/core/metrics.py` docstring. Never label with `user_id` or `vehicle_id` (unbounded).
- 12 unit tests: middleware path templating (2), histogram bucket correctness (1), counter monotonicity (1), gauge transitions (2), label cardinality guard (1), `/metrics` endpoint returns prometheus format (1), 404 cardinality collapse (path_template = `__not_found__`) (1), disabled-metrics feature flag (2), circuit-breaker gauge wiring (1).
**Verify:** `curl localhost:8000/metrics` returns prometheus text format. Hit the vehicles endpoint 100 times — `vtv_http_request_duration_seconds_bucket{le="0.5",path="/v1/vehicles"}` increments. Trip the AI-8.1 circuit breaker — `vtv_circuit_breaker_state{provider="groq"}` flips 0 → 2.

#### OPS-2.2 Deep `/health` Endpoint with Dependency Probes
**What:** Replace the current `/health` implementation with one that probes every critical dependency (PostgreSQL, Redis, reranker model, GTFS-RT feeds, background pollers, LLM providers) in parallel, returns a structured per-dependency object, and degrades status without crashing when any probe fails.
**Why:** Today's `/health` returns 200 as long as the process is up. Docker/Kubernetes/nginx happily route traffic to a worker with an exhausted DB pool or a crashed poller. Deep health catches these before user reports.
**Implementation:**
- `app/core/health.py` (new):
  - `@dataclass(frozen=True) DependencyProbe`: `name: str`, `check: Callable[[], Awaitable[ProbeResult]]`, `timeout_s: float = 2.0`, `critical: bool = True`
  - `@dataclass(frozen=True) ProbeResult`: `status: Literal["ok", "degraded", "down"]`, `latency_ms: float`, `detail: str | None`
  - `HealthChecker.run(*, deep: bool = False) -> HealthReport` — runs probes concurrently via `asyncio.gather(return_exceptions=True)`, aggregates into an overall status (ok if all critical ok; degraded if any non-critical fails; down if any critical fails or times out)
  - Built-in probes:
    - `probe_postgres()` — `SELECT 1` with 2s timeout; also reports `pg_stat_activity` connection count as detail
    - `probe_redis()` — `PING` with 1s timeout
    - `probe_reranker()` — checks that the reranker model is loaded
    - `probe_gtfs_rt_feeds()` — reads last-success timestamp from each feed state; degraded if > 60s stale
    - `probe_pollers()` — checks `POLLER_LAST_TICK` gauge from OPS-2.1; degraded if any poller > 2× its interval stale
    - `probe_llm_providers()` — reads AI-8.1 circuit breaker state per provider; reports `closed|half_open|open` without making a real LLM call (no token cost)
- `app/main.py`:
  - `GET /health` — runs critical probes only (sub-500ms), returns 200 if ok, 503 if down. Kubernetes liveness.
  - `GET /health/deep` — runs every probe including non-critical, returns full `HealthReport` JSON. Admin-auth. Kubernetes readiness.
- 15 unit tests: each probe success (6), each probe failure (6), concurrent execution (1), timeout handling (1), critical vs non-critical aggregation (1).
**Verify:** Stop the Redis container → `/health` returns 503 with `redis: down, detail: "connection refused"`. Pause the GTFS-RT poller for 120s → `/health/deep` reports `gtfs_rt: degraded`. All probes complete in under 500ms even when one times out.

#### OPS-2.3 SLO Definitions + Prometheus Alert Rules
**What:** Document service-level objectives in `docs/slos.md` and commit a starter Prometheus alert rules file (`ops/prometheus/alerts.yml`) that fires on SLO burn: p95 request latency > 500ms for 10 minutes, error rate > 1% for 5 minutes, circuit breaker open > 5 minutes, poller liveness > 2× interval, DB pool > 80% utilized.
**Why:** Metrics without alerts = dashboards nobody looks at. A first pass of SLOs + alerts turns OPS-2.1 into something that can page on-call.
**Implementation:**
- `docs/slos.md` — table of endpoints + SLOs + error budgets + the rationale for each target.
- `ops/prometheus/alerts.yml` — Prometheus alerting rules keyed to the metric names from OPS-2.1. `promtool check rules ops/prometheus/alerts.yml` must pass.
- `ops/prometheus/README.md` — how to load the rules into the Prometheus instance in monitoring infra.
- Each alert description links to a runbook section. Create runbook placeholders in `docs/runbooks/` that OPS-5 will flesh out.
**Verify:** `promtool check rules ops/prometheus/alerts.yml` exits 0. Trigger a synthetic error rate spike in a local Prometheus → alert fires. Each alert's `annotations.runbook_url` points to an existing runbook section.

---

### Phase OPS-3: Durable Background Jobs & Graceful Shutdown (3 days)

> **Sprint deliverable:** Background work (memory compaction, episodic-to-procedural promotion, GTFS-RT polling, WebSocket pub/sub) survives Gunicorn restarts without data loss, respects a coordinated shutdown sequence, and exposes completion status via metrics + a small admin API.

#### OPS-3.1 Shutdown Coordinator for Lifespan Tasks
**What:** Replace the ad-hoc cancel loop in `app/main.py` lifespan with a `ShutdownCoordinator` that tracks every long-running task, honors per-task drain timeouts, and logs a structured shutdown report before the process exits.
**Why:** Gunicorn's default graceful-timeout is 30s. If memory compaction (in `app/memory/lifecycle.py`) is mid-run, it gets SIGKILL'd and can leave the embedding cache inconsistent. Coordinated shutdown with explicit per-task budgets gives each background job a chance to reach a stable checkpoint.
**Implementation:**
- `app/core/shutdown.py` (new):
  - `@dataclass ShutdownTask`: `name: str`, `drain_timeout_s: float`, `drain: Callable[[], Awaitable[None]]`
  - `ShutdownCoordinator`:
    - `register(task: ShutdownTask) -> None`
    - `async shutdown() -> ShutdownReport` — drains in LIFO order via `asyncio.wait_for(..., timeout=task.drain_timeout_s)`; on timeout logs `shutdown.task.timeout` and continues to the next task
  - `@dataclass ShutdownReport`: `tasks_drained: int`, `tasks_timed_out: list[str]`, `total_duration_ms: int`
- `app/main.py` lifespan:
  - During startup, register all background tasks with the coordinator. Suggested budgets: memory compactor = 15s, episodic promoter = 10s, GTFS-RT poller = 5s, WebSocket pub/sub subscriber = 3s, Redis rate-limit bucket flush = 2s. Sum = 35s — trim where needed so total stays below Gunicorn's timeout minus a 5s safety margin.
  - During shutdown call `coordinator.shutdown()` and log the report as `shutdown.report`.
- Tune Gunicorn config: ensure `--graceful-timeout` is explicit (at least 5s above the coordinator budget) so the coordinator, not Gunicorn, decides cutoff.
- 10 unit tests: LIFO drain order (1), drain timeout enforcement (2), drain failure continues next task (1), report aggregation (1), empty coordinator no-op (1), task registration idempotency (1), metric emission on drain (1), startup failure triggers partial drain (1), signal handling (1).
**Verify:** Start VTV, begin a long-running memory compaction, issue `docker stop vtv-api`. Shutdown report logs each task drained in order; none are killed by Gunicorn's timeout. Memory cache remains consistent on next startup.

#### OPS-3.2 Durable Job Queue for Memory Lifecycle
**What:** Move `app/memory/lifecycle.py`'s async-task-based compaction and episodic-to-procedural promotion onto a persistent job queue (Arq on Redis, chosen for async-native integration + minimal surface area). Jobs survive process restarts and can be retried.
**Why:** Bare `asyncio.create_task()` dies with the process. If Gunicorn restarts during a 4-hour compaction run, the job is gone and procedural promotion never catches up, silently degrading agent memory quality over time. A durable queue gives at-least-once semantics with retry on transient failure.
**Implementation:**
- `pyproject.toml` — add `arq ^0.26` (picked over Celery for async-first simplicity; RQ would also work but is sync).
- `app/core/jobs/queue.py` (new) — wraps `arq.create_pool()`; exposes `enqueue(task_name: str, *args, _defer_until: datetime | None = None, _job_id: str | None = None)`.
- `app/core/jobs/worker.py` — Arq `WorkerSettings`: Redis conn from settings, cron entries for scheduled compaction (every 6h) and promotion (daily 03:00 UTC).
- `app/memory/lifecycle.py`:
  - Extract compaction logic into `async def run_compaction(ctx: dict[str, Any]) -> CompactionResult`
  - Extract promotion logic into `async def run_promotion(ctx: dict[str, Any]) -> PromotionResult`
  - Delete the `asyncio.create_task()` scheduling — the worker cron handles it
- `docker-compose.yml` — add `vtv-worker` service running `arq app.core.jobs.worker.WorkerSettings`
- `docker-compose.prod.yml` — same, with resource limits matching `vtv-api`
- Admin API: `GET /admin/jobs/status` returns last run, next run, failure count for each scheduled job (reuses existing admin auth stack)
- Feature flag: `BACKGROUND_QUEUE_ENABLED` (default `false` during rollout so existing behavior is preserved byte-for-byte)
- 14 integration tests: enqueue + execute (2), scheduled cron trigger (1), retry on failure (2), job idempotency via `_job_id` (1), worker survives Redis reconnect (1), compaction result persisted (1), promotion result persisted (1), admin status API (2), feature-flag gating (2), shutdown coordinator integration (1).
**Verify:** Start worker, kill it mid-compaction, restart. The job re-enqueues from cron within 6h and completes successfully. Admin status API shows `last_run`, `next_run`, `last_result`.

#### OPS-3.3 Redis Cache Invalidation Strategy
**What:** Add explicit cache invalidation hooks for entities whose mutation should invalidate cached reads: stops (position cache), routes (route cache), vehicles (position cache), geofences (spatial cache). Wire into the repository layer so mutations auto-invalidate without per-call-site boilerplate.
**Why:** Redis caches vehicle positions (120s TTL) and other entities but there is no bulk invalidation when upstream data changes. A stop moving via a GTFS re-import leaves stale lat/lon cached for up to 120s, which breaks geofence detection and proximity search during migration windows.
**Implementation:**
- `app/core/cache/invalidation.py` (new):
  - `CacheInvalidator` — keyed namespaces (`stops:*`, `routes:*`, `vehicles:position:*`, `geofences:spatial:*`)
  - `async invalidate(namespace: str, *keys: str) -> int` — `DEL` for exact keys; `SCAN` + `DEL` for wildcard on namespace
  - `async invalidate_pattern(pattern: str, *, batch_size: int = 100) -> int` — scan in batches to avoid blocking Redis
- Repository layer:
  - `app/stops/repository.py::update_stop` → invalidate `stops:{stop_id}` + proximity-lookup cache
  - `app/gtfs/import.py::import_stops` → invalidate `stops:*` after import
  - `app/geofences/repository.py::update_geofence` → invalidate `geofences:spatial:*` (whole spatial index)
- Observability: emit `cache.invalidation.performed` structured log events with `namespace`, `keys_invalidated`, `duration_ms`. Reuse the Redis counters from OPS-2.1.
- 10 unit tests: exact-key invalidation (1), pattern invalidation with batching (2), namespace isolation (1), empty-result handling (1), repository-hook auto-invalidation (3), metric emission (1), GTFS import invalidation (1).
**Verify:** Cache a vehicle position, update its stop via CMS → next read returns fresh data. GTFS re-import → all stop caches cleared within 1s. Invalidation never calls `FLUSHDB`.

---

### Phase OPS-4: Per-User Rate Limiting & RBAC Scoping (4 days)

> **Sprint deliverable:** Rate limits are enforced per authenticated user (not global), dispatcher queries are scoped to their assigned routes/depots via a repository-layer filter, and every denied authorization check is audit-logged for compliance review.

#### OPS-4.1 Per-User Rate Limit Bucketing
**What:** Extend `app/core/rate_limit.py` to key slowapi limits on the authenticated user's id (resolved from the existing auth dependency) or remote IP for unauthenticated requests. Introduce tiers: `anonymous` (IP-scoped, 30/min), `dispatcher` (user-scoped, 300/min), `admin` (user-scoped, 1000/min). Heavy endpoints (agent chat, analytics exports) get their own sub-buckets.
**Why:** Current slowapi limiter is global per endpoint. One abusive authenticated client exhausts the bucket for everyone. Per-user bucketing gives fairness and turns rate limits into a real DoS defense for authenticated abuse.
**Implementation:**
- `app/core/rate_limit.py`:
  - Replace the single default key function with `user_or_ip_key(request)` that returns `f"user:{user_id}"` if the request carries an authenticated user (read from wherever the existing auth layer stores it), else `f"ip:{get_remote_address(request)}"`
  - Add `TIER_LIMITS: dict[str, str]` mapping role → rate (anonymous=`"30/minute"`, dispatcher=`"300/minute"`, admin=`"1000/minute"`)
  - Use `@limiter.limit(dynamic_limit_fn)` where `dynamic_limit_fn(request)` reads the authenticated role and returns the matching tier
- `app/core/agents/routes.py` — agent chat gets a separate sub-bucket (`"10/minute"` per user) on top of the tier limit; prevents one user burning through LLM budget
- `app/analytics/routes.py` — export endpoints use `"5/hour"` per user
- Redis keys use the slowapi default (`LIMITER/{key}`); confirm TTL cleanup to avoid key bloat
- 12 unit tests: anonymous IP bucketing (1), authenticated user bucketing (2), tier selection by role (3), per-endpoint sub-bucket stacking (2), Redis TTL expiry (1), missing auth context fallback to IP (1), 429 response includes retry-after (1), admin exemption toggle (1).
**Verify:** Dispatcher A hits analytics at 250/min (under limit) → allowed. Dispatcher B hits vehicles at 500/min → allowed (different endpoint limit). Dispatcher A bursts chat to 20/min → second 10 get 429 without affecting Dispatcher B's chat bucket.

#### OPS-4.2 Dispatcher-Scoped Query Filters (RBAC Scoping)
**What:** Add a `RequestScope` dependency that resolves "what routes/depots/vehicles this user may see" from their role + assignments, and inject it into every repository query for data-scoped models (vehicles, routes, schedules, geofences, alerts). Admins see everything; dispatchers see only their assigned scope; drivers see only their assigned vehicle.
**Why:** Auth has 4 roles but queries are role-checked at the route level only. A dispatcher with scope "routes 1-10" can still read data for routes 11-50 by calling the same endpoint with a different query parameter. This is the biggest authorization gap in the platform.
**Implementation:**
- Data model:
  - `alembic/versions/xxxx_add_dispatcher_assignments.py` — new table `dispatcher_assignments(user_id, route_id, depot_id, assigned_at, assigned_by)`
  - CMS admin page to manage assignments (backend API first; frontend is a follow-up)
- `app/core/auth/scope.py` (new):
  - `@dataclass(frozen=True) RequestScope`: `user_id`, `role`, `route_ids: frozenset[int] | None` (None = unrestricted for admin), `depot_ids: frozenset[int] | None`
  - `async get_request_scope(user = Depends(current_user)) -> RequestScope` — admin → `(None, None)`; dispatcher → loads from assignments table; driver → only their assigned vehicle; viewer → `(None, None)` (read-only everything)
- Repository layer — every repository method returning scoped data takes `scope: RequestScope` and applies:
  ```python
  if scope.route_ids is not None:
      stmt = stmt.where(Route.id.in_(scope.route_ids))
  ```
  Covers `RouteRepository`, `VehicleRepository`, `ScheduleRepository`, `GeofenceRepository`, `AlertRepository`.
- Route handlers inject `scope: RequestScope = Depends(get_request_scope)` and pass to the repository.
- Fail-closed default: if a route forgets to pass `scope`, the repository raises `RBACConfigurationError` at request time (caught by unit tests; never reaches prod).
- Audit logging: emit `rbac.scope.resolved` + `rbac.scope.denied` via structlog.
- 20 unit tests: admin sees all (1), dispatcher scope filter (3), driver single-vehicle scope (2), viewer unrestricted read (1), repository without scope fails (1), dispatcher with empty assignments (1), fail-closed enforcement (2), scope caching in request state (1), RBAC audit log fields (2), assignments CRUD (3), scope invalidation on assignment change (2), HTTP 403 vs empty-result semantics (1).
**Verify:** Dispatcher A (scope routes 1-10) calls `GET /v1/vehicles?route_id=15` → 200 with empty result (not 403, to avoid info leak). Dispatcher A calls `GET /v1/vehicles` → returns only vehicles on routes 1-10. Admin sees everything. Forgetting `scope` on a new endpoint → unit test fails with `RBACConfigurationError`.

#### OPS-4.3 Authorization Audit Log
**What:** Emit a structured `auth.denied` log event whenever a request is blocked by role check, scope filter, or rate limit — with `request_id`, `user_id`, `path`, `reason`, `enforcement_layer`. Persist to a TimescaleDB hypertable `auth_audit_events` for queryability and surface via `GET /admin/audit/auth` with date-range + user filters.
**Why:** Compliance and incident response both need "who tried to access what and got denied". Without audit trails, breach investigation has no primary evidence.
**Implementation:**
- `app/core/auth/audit.py` — helper that emits structured log events and writes to the hypertable.
- `alembic/versions/xxxx_auth_audit_events.py` — TimescaleDB hypertable with 30-day retention, composite index on `(user_id, created_at DESC)`.
- Hook points:
  - `app/core/auth/dependencies.py::current_user` — emits on JWT rejection
  - `app/core/auth/scope.py::get_request_scope` — emits on scope-related denial
  - `app/core/rate_limit.py::handle_rate_limit_exceeded` — emits on 429
- `app/admin/routes.py` — `GET /admin/audit/auth?from=...&to=...&user_id=...` with pagination
- 12 unit tests: denial event emission (3), hypertable insert (1), retention policy (1), admin query filters (3), pagination (1), index usage (EXPLAIN plan assertion) (1), PII redaction (log never contains password/token) (2).
**Verify:** Trigger a 403, 401, and 429 → all three appear in `GET /admin/audit/auth` with enforcement_layer annotation. A dispatcher tries an admin-only endpoint → event logged with `reason="role_required:admin"`.

---

### Phase OPS-5: DX & Documentation Hardening (3 days)

> **Sprint deliverable:** Baseline type errors cleared, four core ADRs committed, database ER diagram auto-generated from SQLAlchemy models, and the logging event taxonomy is exhaustive enough to power GlitchTip dashboards without reverse-engineering the code.

#### OPS-5.1 Clear Baseline Type Errors in Agent Tools + Pipeline
**What:** Fix the 8 pre-existing type errors (5 pyright, 3 mypy) called out in the AI-8.1 completion note: `app/core/agents/tools/transit/client.py`, `app/core/agents/tools/transit/static_store.py`, `app/core/agents/pipeline.py`. No suppressions — fix the underlying types.
**Why:** "Strict type safety" is contradicted by 8 known errors that CI has been told to ignore. These will quietly multiply as the agent surface grows. Clearing them now resets the baseline to zero and lets CI fail on any regression.
**Implementation:**
- Capture the 8 errors: run `uv run mypy app/core/agents/tools/transit/client.py app/core/agents/tools/transit/static_store.py app/core/agents/pipeline.py` and `uv run pyright` against the same files.
- Fix each at the source: add missing generics, narrow `Any` to typed unions, add `@overload` where signatures are ambiguous, replace dict-based records with typed dataclasses or Pydantic models.
- Remove any baseline tolerance from `pyproject.toml` that was relaxing strict checking for these paths.
- Re-run `uv run mypy app/` and `uv run pyright` repo-wide to confirm zero errors.
**Verify:** `uv run mypy app/` → 0 errors. `uv run pyright` → 0 errors. CI's type-check job passes without baseline suppressions.

#### OPS-5.2 Architecture Decision Records
**What:** Write 4 short ADRs capturing the non-obvious architectural choices already in the codebase: (1) Vertical Slice Architecture, (2) Pydantic AI over LangChain, (3) Redis for embedding + position cache, (4) slowapi vs reverse-proxy rate limiting. ADR template: status, context, decision, consequences.
**Why:** Onboarding currently requires archaeology. New contributors re-propose LangChain, re-propose per-feature `shared/` folders, re-propose reverse-proxy rate limits — all already decided and rejected for reasons nobody wrote down. ADRs block the time-sink.
**Implementation:**
- `docs/adr/0001-vertical-slice-architecture.md`
- `docs/adr/0002-pydantic-ai-over-langchain.md`
- `docs/adr/0003-redis-for-cache-layer.md`
- `docs/adr/0004-slowapi-rate-limiting.md`
- `docs/adr/README.md` — index + Nygard ADR template (status / context / decision / consequences)
- Cross-link from `CLAUDE.md` § Architecture and main `README.md`.
**Verify:** Each ADR reads self-contained: a new contributor can read ADR-0002 cold and understand why Pydantic AI won over LangChain without reading any code.

#### OPS-5.3 Database ER Diagram from SQLAlchemy Models
**What:** Add a `make er-diagram` target that generates a Mermaid ER diagram from the SQLAlchemy metadata and writes it to `docs/schema/er.md`. Commit the generated output so it is viewable in GitHub without running the target locally.
**Why:** 23 migrations, no diagram, no single place to understand the schema. Onboarding and refactor discussions both need it.
**Implementation:**
- `scripts/generate_er_diagram.py` — imports all model modules (populates `Base.metadata`), walks `metadata.tables`, emits Mermaid `erDiagram` syntax with foreign keys.
- `Makefile` — `er-diagram: uv run python scripts/generate_er_diagram.py > docs/schema/er.md`
- `docs/schema/er.md` — the generated output (re-run on every migration to keep in sync)
- Optional pre-commit hook that fails the commit if `alembic/versions/` changed without a regenerated `er.md`.
**Verify:** `make er-diagram` regenerates the file. `docs/schema/er.md` renders in GitHub as a Mermaid diagram showing all 20+ tables with foreign-key relationships.

#### OPS-5.4 Logging Taxonomy Audit + Backfill
**What:** Audit `app/core/agents/circuit_breaker.py` (added in AI-8.1), background pollers, and the agent tool layer for structured log events missing from `docs/logging-standard.md`. Add every missing event to the taxonomy with fields + severity + example.
**Why:** AI-8.1 added 7 new `agent.circuit_breaker.*` events and the taxonomy doc is not yet caught up. Dashboard builders in GlitchTip hit "what is this event?" dead ends every time a new subsystem logs.
**Implementation:**
- `scripts/audit_log_taxonomy.py` — greps the code for `structlog.get_logger().*(event=...)` calls, extracts event names, compares against `docs/logging-standard.md`, prints deltas.
- Backfill `docs/logging-standard.md` with missing entries. Target: zero untracked events.
- Add a CI step (optional) that runs the audit script and fails if new events land without doc entries.
**Verify:** `python scripts/audit_log_taxonomy.py` reports 0 missing entries. Every event emitted by the code is documented with fields + severity + example.

---

### Operations & Platform Hardening — Summary

| Phase | Focus | Days | Depends on |
|-------|-------|------|------------|
| OPS-1 | Secrets discipline + rotation runbook | 1 | — |
| OPS-2 | Prometheus /metrics + deep /health + alerts | 3 | AI-8.1 (for breaker gauge) |
| OPS-3 | Graceful shutdown + durable job queue + cache invalidation | 3 | — |
| OPS-4 | Per-user rate limiting + RBAC scoping + audit log | 4 | — |
| OPS-5 | Type baseline + ADRs + ER diagram + logging taxonomy | 3 | — |

Total operational hardening: **14 days** across 16 subtasks. All five phases are independent of AI-8..AI-11 and of each other; a second engineer can run the OPS track in parallel with the agent-intelligence track. Highest-leverage single item is **OPS-2.1 (Prometheus /metrics)** — it unblocks every later conversation about performance, degradation, and capacity, and provides the gauge surface that OPS-2.2 and OPS-2.3 depend on.

---

## Planned Features

### Full Latvia Transit Platform

- [ ] **Phase 1: Foundation** - Database extensions (TimescaleDB), GTFS static importer for all Latvia, CKAN data.gov.lv bridge for immediate ATD data, full-screen transit map in CMS. ~3 weeks remaining effort. *Largely done: GTFS import, Redis cache, REST endpoints, GTFS-RT poller, PostGIS spatial queries (GeoAlchemy2 + GIST index), WebSocket live streaming (backend Pub/Sub + frontend real-time push with HTTP fallback), persistent GTFS storage (DB-backed static data for agent tools), and TimescaleDB historical position storage (hypertable, compression, 90-day retention, vehicle history + delay trend endpoints) are complete. Remaining: multi-city GTFS, CKAN bridge, full-screen map.*
  - Plan: [docs/PLANNING/Implementation-Plan.md](PLANNING/Implementation-Plan.md) (Phase 1)

- [ ] **Phase 2: Full Latvia Coverage** - Additional city feeds (Daugavpils, Jurmala, Pieriga), train positions via WebSocket, Valhalla route matching, ETA calculator, adaptive polling, circuit breakers, TimescaleDB compression, GTFS-RT publisher. ~4 weeks effort.
  - Plan: [docs/PLANNING/Implementation-Plan.md](PLANNING/Implementation-Plan.md) (Phase 2)

- [ ] **Phase 3: Intercity Gap-Fill** - OwnTracks integration for phone-based tracking, Traccar integration for hardware GPS (Teltonika FMB920), OpenTripPlanner for journey planning, shareable tracking links, historical analytics. ~8 weeks effort.
  - Plan: [docs/PLANNING/Implementation-Plan.md](PLANNING/Implementation-Plan.md) (Phase 3)

- [ ] **Phase 4: Intelligence** — Detailed breakdown in [§ Intelligence/ML — Phased Implementation](#intelligenceml--phased-implementation) below (ML-1..ML-5, ~33 days across 17 subtasks).
  - Plan: [docs/PLANNING/Implementation-Plan.md](PLANNING/Implementation-Plan.md) (Phase 4)

### Fleet Management & Vehicle Tracking (LocTracker-inspired)

- [ ] **Phase 2: Fuel + Analytics + LocShare** — Fuel monitoring (refueling/drain detection from OBD), fuel consumption analytics, fleet distance/drive time reports, idle time detection, LocPoints dwell time, LocShare (JWT expiring public tracking links), PDF/CSV report export, speed/device-offline alerts. CMS: fuel dashboard, analytics pages, LocShare management. ~27 days effort.
  - Plan: [docs/PLANNING/fleet-management-tracking.md](PLANNING/fleet-management-tracking.md) (Phase 2)

- [ ] **Phase 3: Tachograph + Driving Hours Compliance** — `app/tachograph/` vertical slice: remote DDD file download (Teltonika Web Tacho + flespi), DDD binary parser, EU 561/2006 driving hours calculator (daily 9/10h, weekly 56h, biweekly 90h, monthly 160h), compliance status endpoints, infringement detection, driving hours alerts. CMS: compliance dashboard, activity timeline, DDD management, violation reports. ~36 days effort.
  - Plan: [docs/PLANNING/fleet-management-tracking.md](PLANNING/fleet-management-tracking.md) (Phase 3)

- [ ] **Phase 4: Routing + Maps Fallback** — OSRM self-hosted (Latvia OSM extract) as Docker sidecar, HERE Fleet Telematics API fallback, route optimization for service vehicles. CMS: route planning UI with map waypoints. ~15 days effort.
  - Plan: [docs/PLANNING/fleet-management-tracking.md](PLANNING/fleet-management-tracking.md) (Phase 4)

- [ ] **Phase 5: Driver Mobile App + Messaging** — `app/messaging/` vertical slice (dispatcher↔driver messaging, task assignment), React Native mobile app (live map, alerts, messaging, tasks), push notifications (FCM/APNs). ~28 days effort.
  - Plan: [docs/PLANNING/fleet-management-tracking.md](PLANNING/fleet-management-tracking.md) (Phase 5)

### Knowledge Base

- [ ] **RAG Knowledge Base Improvements** — Remaining scope after AI-1..AI-7: PPTX extractor, Latvian UDPipe lemmatizer for BM25 stemming, document versioning with diff-aware search, search feedback loop (thumbs-up/down → RRF weight tuning), and entity/knowledge-graph overlay. ~9.5 days effort, ~$0.55/month added cost. _Parent-child chunking, temporal metadata, auto-domain tagging, cross-lingual search, and Excel/CSV are already shipped — see plan doc for status. HTML support dropped as not needed._
  - Plan: [docs/PLANNING/rag-improvements.md](PLANNING/rag-improvements.md)

- [ ] **SOP & File Automation** - Automated document ingestion (folder watcher, email monitor, web scraper, GTFS sync) and LLM-powered SOP generation (incident-to-SOP pipeline, regulation change detection, shift handover notes, template scaffolding). ~13 days total effort, ~$4.50/month LLM cost, saves ~47 hrs/month human time.
  - Plan: [docs/PLANNING/sop-file-automation.md](PLANNING/sop-file-automation.md)

### CMS Features

- [ ] **Route Shape Polylines** - Display route geometry on map from GTFS `shapes.txt`. Requires polyline layer in react-leaflet, shape import during GTFS ZIP processing, and route-shape association. Enhances route visualization significantly.

---

## Intelligence/ML — Phased Implementation

Phase 4 of the Full Latvia Transit Platform — detailed breakdown. Trains ML models on TimescaleDB vehicle history plus public Latvia datasets (e-ticket validations, weather, traffic, accidents) and wires them into the agent as context-aware tools.

> Platform plan: [docs/PLANNING/Implementation-Plan.md § Phase 4](PLANNING/Implementation-Plan.md)
> ML data inventory: 64 monthly GTFS archives + 67 monthly e-ticket archives (~6.5 GB) + weather + traffic, 2018–present, all CC0. Full table at [§ Complete ML Data Inventory](PLANNING/Implementation-Plan.md).
> **Depends on:** Full Latvia Phase 1 (TimescaleDB, GTFS DB tables, Redis) and Phase 2 (multi-feed coverage + 90 days of historical positions accumulated).

### Phase ML-1: Data Ingestion Foundation (6 days)

> **Sprint deliverable:** All 4 historical public datasets imported as queryable tables in Postgres. Foundation for every later phase — no model training possible without this.
> **Depends on:** Full Latvia Phase 1 (Postgres, TimescaleDB, GTFS importer)

#### ML-1.1 Historical GTFS Archive Importer
**What:** Create `app/transit/historical_gtfs_importer.py` — CLI + background task that downloads all 64 monthly Rīgas Satiksme GTFS snapshots from data.gov.lv, de-duplicates against already-imported snapshots, and stores each one in a new `gtfs_snapshots` table (one row per snapshot → link to snapshot-scoped copies of trips/stop_times/calendar).
**Why:** Current GTFS importer only ingests the "latest" feed — overwriting prior data on every run. ML training needs the full temporal history to learn seasonal variations (summer vs winter routes, school vs holiday calendars). A single weekend scripted backfill seeds the entire ML training corpus.
**Implementation:**
- `alembic/versions/h1i2j3k4l5m6_gtfs_snapshots.py` — new tables:
  - `gtfs_snapshots` (id, feed_name, snapshot_date, resource_id, sha256, row_counts_json, imported_at)
  - `gtfs_snapshot_trips`, `gtfs_snapshot_stop_times`, `gtfs_snapshot_calendar` — snapshot-scoped shadow tables with `snapshot_id` FK (TimescaleDB compressed after 30 days)
- `app/transit/historical_gtfs_importer.py`:
  - `list_available_snapshots() -> list[SnapshotMeta]` — fetches dataset resource list from data.gov.lv API, returns sorted by date
  - `import_snapshot(resource_id, snapshot_date)` — downloads ZIP, computes sha256, skips if already imported, parses via existing `gtfs_importer.py` helpers, writes to snapshot-scoped tables
  - `backfill_all(since_date, until_date)` — loops snapshots, respects 1 req/s rate limit, resumable (checkpoint via `gtfs_snapshots.imported_at`)
- `scripts/backfill_gtfs_history.py` — CLI entrypoint with `--since 2018-05` / `--dry-run` flags
- `Makefile` — `make gtfs-backfill SINCE=2018-05`
- Storage impact: ~64 snapshots × ~50MB compressed = ~3.2 GB Postgres (TimescaleDB compression expected to reduce by 5-10×)
- 10+ unit tests: snapshot metadata parsing, duplicate detection (2), rate limiting, resumability (2), corrupt ZIP fallback, end-to-end with fixture ZIPs (2)

**Verify:** `make gtfs-backfill SINCE=2025-10` imports last 3 months without duplicates. Query `SELECT COUNT(*), MIN(snapshot_date), MAX(snapshot_date) FROM gtfs_snapshots;` returns expected rows. Re-run: no new rows (idempotent). Disk usage within projected range.

#### ML-1.2 E-Ticket Validation Data Pipeline
**What:** Create `app/transit/eticket_importer.py` — downloads monthly e-ticket validation archives (~100MB compressed each, 67 total), parses TXT files, writes to `eticket_validations` TimescaleDB hypertable partitioned on `validated_at`. Enables passenger load prediction training.
**Why:** E-ticket data is the most valuable ML dataset in the platform — every tap-on since 2018 mapped to vehicle + route + direction + time. Combined with GPS positions, it predicts bus crowding. The dataset is too large (~45 GB uncompressed) to load on-demand; needs a staged backfill with compression from day one.
**Implementation:**
- `alembic/versions/i2j3k4l5m6n7_eticket_validations.py` — TimescaleDB hypertable:
  - `eticket_validations` (id, record_id, depot, transport_type, vehicle_number, route_name, route_code, direction, validation_id, validated_at TIMESTAMPTZ)
  - `SELECT create_hypertable('eticket_validations', 'validated_at', chunk_time_interval => INTERVAL '7 days')`
  - Compression policy: compress chunks older than 30 days, retention 5 years
  - Index: `(route_code, validated_at DESC)`, `(vehicle_number, validated_at DESC)`
- `app/transit/eticket_importer.py`:
  - `parse_eticket_txt(path) -> Iterator[EticketRecord]` — streaming TXT parser (line-by-line, no full-file load, field encoding Latin-1→UTF-8)
  - `import_monthly_archive(url, archive_date)` — downloads ZIP to temp, extracts, streams each daily TXT, bulk-inserts via `asyncpg.copy_records_to_table` (10-100x faster than SQLAlchemy), deletes temp
  - `backfill_all()` — loops monthly archives oldest-first, resumable via `eticket_imports` tracking table
- `scripts/backfill_eticket_data.py` — CLI with `--month 2026-01`, `--all`, `--dry-run`
- `Makefile` — `make eticket-backfill MONTH=2026-01`
- Resource budget: ~45 GB uncompressed → ~5-8 GB after TimescaleDB compression. Alert ops before running full backfill.
- 12+ unit tests: TXT parsing with Latin-1 quirks (3), bulk copy integration (1), duplicate detection (1), resume semantics (2), schema validation (2), compression policy assertion (1), storage budget guardrail (2)

**Verify:** `make eticket-backfill MONTH=2026-01` imports January 2026 (~100MB). `SELECT route_code, COUNT(*) FROM eticket_validations WHERE validated_at >= '2026-01-01' GROUP BY route_code ORDER BY 2 DESC LIMIT 10` shows realistic ridership (route 22 & 6 should top the list). Compression policy active via `SELECT * FROM timescaledb_information.compression_settings`.

#### ML-1.3 Weather + Traffic Observations ETL
**What:** Create `app/transit/weather_etl.py` and `app/transit/traffic_etl.py` — scheduled pullers for data.gov.lv weather (meteo + road conditions) and traffic count / accident datasets. Writes to dedicated tables with spatial columns for later join against stops/routes.
**Why:** ETA models need weather context (rain +15% delay, snow +40% delay). Traffic counts + accident hotspots feed congestion factors. These datasets update at different cadences (weather hourly, traffic daily, accidents annually) — each needs its own scheduler and idempotent upsert logic.
**Implementation:**
- `alembic/versions/j3k4l5m6n7o8_weather_traffic.py` — 4 new tables:
  - `weather_observations` (station_id, observed_at TIMESTAMPTZ, temp_c, wind_mps, precip_mm, phenomena JSONB, location GEOGRAPHY(POINT)) — TimescaleDB hypertable on `observed_at`
  - `weather_stations` (station_id, name, location GEOGRAPHY(POINT))
  - `traffic_counts` (point_id, period_start, period_end, avg_count_per_day, vehicle_class, location GEOGRAPHY(POINT)) — non-hypertable (low cardinality)
  - `traffic_accidents` (id, occurred_at, severity, fatalities, injuries, location GEOGRAPHY(POINT))
- `app/transit/weather_etl.py`:
  - `pull_meteo_operativie_dati()` — fetches `meteo_operativie_dati.csv` (last 48h), upserts, runs hourly via background task
  - `pull_meteo_arhiva_dati()` — one-shot backfill of last 365 days
  - `pull_laika_operativie_dati()` — weather phenomena (fog, ice, storm) — JSONB merged into `weather_observations.phenomena`
- `app/transit/traffic_etl.py`:
  - `pull_traffic_counts()` — daily pull from `data.lvceli.lv`
  - `pull_traffic_accidents()` — annual one-shot from CAIS dataset (CSV)
- `app/main.py` — schedule `pull_meteo_operativie_dati` every 60 min, `pull_traffic_counts` daily at 04:00 UTC (reuse lifecycle pattern from memory tasks)
- `Makefile` — `make weather-backfill`, `make traffic-backfill`
- PostGIS spatial join usage documented in ML-2.3
- 15+ unit tests: CSV parsing (3), upsert idempotency (2), PostGIS location encoding (2), phenomena JSONB merge (2), scheduled task gating (2), resume semantics (2), HTTP failure retry (2)

**Verify:** Run `make weather-backfill`. Query `SELECT ST_Distance(location, ST_MakePoint(24.105, 56.95)::geography), temp_c FROM weather_observations w JOIN weather_stations s ON w.station_id = s.station_id ORDER BY observed_at DESC LIMIT 5` — returns recent observations near Riga. Hourly background task logs `transit.weather.pulled {count, duration_ms}`.

---

### Phase ML-2: ETA Prediction Model (8 days)

> **Sprint deliverable:** ML-based ETA accurate within ±2 minutes on commuter routes vs the ±5-minute scheduled baseline. Served via `predict_eta()` agent tool and exposed as `GET /v1/transit/vehicles/{id}/eta`.
> **Depends on:** ML-1, Full Latvia Phase 2 (90+ days of TimescaleDB history accumulated)

#### ML-2.1 Feature Engineering Pipeline
**What:** Create `app/ml/features/eta_features.py` — deterministic feature extraction job that joins `vehicle_positions` (TimescaleDB) with `gtfs_stop_times` + `weather_observations` to produce a training matrix. One row per (trip_id, stop_sequence) with features like scheduled_arrival, time_of_day, day_of_week, historical_avg_delay, weather_bucket, prev_stop_delay.
**Why:** ML training data quality dominates model quality. Centralising feature engineering in one module (vs. ad-hoc notebooks) means the training set, online inference, and eval all use the same feature code — no train/serve skew.
**Implementation:**
- `app/ml/features/eta_features.py`:
  - `@dataclass(frozen=True) ETAFeatures`: 18 fields total (8 categorical, 10 numeric)
  - `extract_features(trip_id, stop_sequence, observed_at) -> ETAFeatures` — online path, used by inference
  - `extract_features_batch(from_ts, to_ts) -> pd.DataFrame` — offline path, used by training
  - Categorical: `day_of_week`, `month`, `is_school_day` (from gtfs calendar), `is_holiday`, `weather_bucket` (clear/rain/snow/fog), `route_type`, `direction`, `operator`
  - Numeric: `time_of_day_hour`, `scheduled_headway_s`, `historical_avg_delay_at_stop_s`, `prev_stop_actual_delay_s`, `trip_elapsed_pct`, `temp_c`, `wind_mps`, `precip_mm_last_hr`, `traffic_count_rolling_7d`, `accident_count_within_500m`
- Feature store: materialized view `ml_eta_features_v1` refreshed nightly via `REFRESH MATERIALIZED VIEW CONCURRENTLY`
- `app/ml/features/validation.py` — schema validation (pandera), outlier detection
- 12+ unit tests: each feature extraction (8), missing-data fallbacks (2), train/serve parity regression (1), batch vs online equivalence (1)

**Verify:** Run `python -m app.ml.features.eta_features --from 2026-03-01 --to 2026-03-31 --out /tmp/features.parquet`. Resulting parquet has ~200K rows (1 month × ~6000 trips × ~30 stops per trip). Spot-check 10 random rows against source data.

#### ML-2.2 Baseline Gradient Boosting Model
**What:** Train a LightGBM regression model predicting `actual_arrival_delay_seconds` from ML-2.1 features. Target MAE < 120s (vs ~300s for the naive "scheduled time" baseline). Track versions, metrics, and artifacts via a lightweight in-repo registry.
**Why:** LightGBM is the right first model: fast to train on tabular data, handles categorical features natively, interpretable via SHAP. Deep-learning alternatives (LSTM, graph nets) add complexity without proven lift on this kind of schedule-adherence problem.
**Implementation:**
- `app/ml/models/eta_gbm.py`:
  - `train(features_df, target_col, val_split=0.2) -> ETAModel` — sklearn pipeline (LightGBM + ColumnTransformer), 5-fold CV, early stopping
  - `ETAModel.predict(features: ETAFeatures) -> ETAPrediction` — returns `(predicted_delay_s, confidence_lower, confidence_upper)` via quantile regression heads (0.1 / 0.5 / 0.9)
  - Model artifact: pickled LightGBM booster + feature transformer → `models/eta_gbm_v{N}.pkl` (git-ignored, tracked via `models/registry.json`)
- `app/ml/registry.py`:
  - `ModelRegistry` class: stores model metadata (version, trained_at, training_window, metrics, feature_version) in `models/registry.json` (committed)
  - `load_latest(model_name) -> LoadedModel` with in-memory cache
  - `promote(model_name, version)` — sets "production" pointer
- `scripts/train_eta_model.py` — CLI with `--training-window 60d`, `--target-mae 120`, `--promote` flags
- `Makefile` — `make ml-train-eta`
- Metrics logged + persisted: MAE, RMSE, 90th-percentile error, per-route MAE (fairness check)
- 15+ unit tests: training smoke (1), prediction smoke (1), quantile interval coverage (2), registry promote/rollback (3), reproducibility (fixed seed) (2), feature version mismatch error (1), model versioning (2), SHAP integration (1), end-to-end fixture training (2)

**Verify:** `make ml-train-eta` produces `models/eta_gbm_v1.pkl` with MAE < 120s on held-out validation. `registry.json` shows the version with metrics. Per-route MAE check confirms no route has MAE > 240s (no egregious outlier routes).

#### ML-2.3 Inference Service + Agent Tool Integration
**What:** Expose the trained model via (a) an internal `ETAService` with in-memory model cache, (b) a new `GET /v1/transit/vehicles/{id}/eta?stop_id=X` REST endpoint, and (c) a `predict_eta` agent tool so dispatchers can ask "when will bus 22-47 reach Brīvības?". Wire `query_route_delays` to surface ML-based forecasts alongside historical analysis.
**Why:** A trained model is useless without a serving layer. Keeping inference in-process (no separate model server) is the right call at this scale — VTV serves <10k predictions/day, LightGBM cold-start is <50ms, and a microservice adds ops burden. The agent tool is where dispatchers actually consume predictions.
**Implementation:**
- `app/ml/eta_service.py`:
  - `ETAService` singleton with `predict(trip_id, stop_id, observed_at) -> ETAPrediction`
  - Calls `eta_features.extract_features(...)` then `model.predict(...)`, formats output
  - Hot-reloads model when `registry.json` version pointer changes (checked every 5 min)
  - Falls back to scheduled time + historical_avg_delay if model load fails (never blocks the endpoint)
- `app/transit/routes.py` — `GET /v1/transit/vehicles/{vehicle_id}/eta?stop_id=X` — returns predicted arrival, confidence interval, fallback flag
- `app/core/agents/tools/transit/predict_eta.py` — new agent tool, signature `predict_eta(vehicle_id: str, stop_id: str) -> ETAResponse`, added to `TransitAgent` tool list (and unified agent fallback)
- Update `query_route_delays` (existing) to optionally include ML forecasts via `include_forecast: bool = False` param
- `app/core/agents/agents/transit.py` — extend `TRANSIT_SYSTEM_PROMPT` with a short "When to use `predict_eta`" section
- Structured logging: `transit.eta.predicted {vehicle_id, stop_id, predicted_delay_s, model_version, latency_ms, fallback}`
- 18+ unit tests: happy-path predict (2), fallback on model load failure (2), hot-reload on version change (2), agent tool integration (3), REST endpoint auth + rate limit (3), edge cases (trip already past stop, no schedule) (3), model-version drift log (1), latency budget assertion <100ms p95 (2)

**Verify:** `GET /v1/transit/vehicles/22-47/eta?stop_id=1234` returns `{predicted_arrival_at, delay_s, confidence_interval, model_version: "eta_gbm_v1"}`. Agent query "when does bus 22-47 reach Brīvības?" triggers `predict_eta` tool, returns user-facing ETA. Force fallback (`models/registry.json` pointing to nonexistent version) — endpoint still responds with scheduled time + `fallback: true`.

---

### Phase ML-3: Passenger Load Prediction (6 days)

> **Sprint deliverable:** Crowding predictions ("bus 22 at 08:15 on Monday typically has 47 passengers by Brīvības") exposed to dispatchers via new agent tool. Over-capacity alerts fire 10+ minutes before the vehicle arrives.
> **Depends on:** ML-1.2 (e-ticket data), ML-2 (feature pipeline patterns)

#### ML-3.1 E-Ticket ↔ GTFS-RT Correlation Pipeline
**What:** Create `app/ml/features/load_features.py` — joins `eticket_validations` with `vehicle_positions` to reconstruct per-stop tap-on counts. Output: time series of passenger counts per (trip, stop_sequence, date).
**Why:** E-ticket records lack an explicit stop_id — they only record `(vehicle_number, validated_at)`. Reconstructing "which stop was this tap-on at?" requires joining against the vehicle's GPS trace at that timestamp, then nearest-stop lookup via PostGIS. This correlation is the bridge between raw data and a trainable dataset.
**Implementation:**
- `app/ml/features/load_features.py`:
  - `correlate_taps_to_stops(from_ts, to_ts) -> pd.DataFrame` — spatial-temporal join: for each validation, find the vehicle_position row closest in time (±60s window) and nearest stop (`ST_DWithin`, 100m radius)
  - `extract_load_features(...)` — per (trip_id, stop_sequence, date): tap-on count, cumulative load from start of trip, seat capacity (from vehicle_type), load factor %
- Materialized view `ml_load_features_v1` refreshed nightly, backed by ML-1.2 hypertable compression
- `app/ml/features/vehicle_capacity.py` — capacity lookup table (bus = 60, articulated bus = 100, tram = 200, trolleybus = 80) + overrides from fleet records
- Validation: ensure ≥80% of e-ticket records correlate to a stop within tolerance; flag uncorrelated records for investigation
- 12+ unit tests: spatial-temporal join correctness (3), capacity lookup (2), load factor math (2), unmatched record handling (2), feature determinism (1), per-vehicle override resolution (2)

**Verify:** Run correlation over 1 week of January 2026 data. `SELECT route_code, AVG(load_factor_pct) FROM ml_load_features_v1 WHERE date_trunc('day', validated_at) = '2026-01-15' GROUP BY 1 ORDER BY 2 DESC LIMIT 5` — route 22, 6, 11 should top the chart (main commuter lines). Correlation rate ≥ 80%.

#### ML-3.2 Load Prediction Model
**What:** Train a gradient-boosted model predicting `expected_passenger_count` at (trip_id, stop_sequence) from features like route, direction, time_of_day, day_of_week, weather, school_calendar, historical_avg_load. Output includes crowding bucket (empty/light/moderate/full/overcrowded).
**Why:** Same model architecture as ML-2.2 (LightGBM regressor) but different target + features. Re-using the registry + training infrastructure from ML-2 means ~2 days of the 6-day budget goes to model-specific work, not plumbing.
**Implementation:**
- `app/ml/models/load_gbm.py` — mirror of `eta_gbm.py` but with load-specific features and a classification head for crowding bucket
- `crowding_bucket(load_factor_pct) -> Literal["empty","light","moderate","full","overcrowded"]` — thresholds: <20%, 20-40%, 40-70%, 70-95%, >95%
- Two-head output: regression (passenger count) + classification (bucket). Separate metrics per head: MAE for count, F1-macro for bucket.
- Reuse `app/ml/registry.py` — register as `load_gbm_v1`
- `scripts/train_load_model.py` CLI + `make ml-train-load`
- 12+ unit tests: training smoke, bucket boundaries, per-route fairness (route 22 ≠ rural lines), reproducibility, registry integration

**Verify:** `make ml-train-load` produces `load_gbm_v1.pkl` with count MAE < 12 passengers and bucket F1 > 0.75. Per-route breakdown confirms no systematic bias toward any route.

#### ML-3.3 Crowding Alerts + Agent Tool
**What:** Add `predict_passenger_load(route_id, direction, time_window)` agent tool and a background evaluator (`app/alerts/crowding_evaluator.py`) that flags buses predicted to exceed 95% capacity 10+ minutes before arrival. Wire into existing alerts system from Phase 1B.
**Why:** Predictions without action are dashboards. Dispatchers need proactive alerts so they can deploy overflow vehicles. Reuse the alerts service from the fleet/geofences work (`app/alerts/`) rather than building a parallel notification system.
**Implementation:**
- `app/core/agents/tools/transit/predict_passenger_load.py` — agent tool, reads from `ETAService`-style singleton (`LoadPredictionService`)
- `app/alerts/crowding_evaluator.py` — background task (2 min cycle): for each active trip, predict load at next 3 stops, fire alert if `crowding_bucket == "overcrowded"` and no duplicate alert within last 30 min
- Alert payload includes: `route_id`, `vehicle_id`, `next_stop`, `predicted_load_factor`, `predicted_arrival_at`
- `app/main.py` — register crowding_evaluator in lifespan, gate via `alerts_crowding_enabled: bool = True`
- Agent tool + evaluator share a single `LoadPredictionService` singleton (avoid double-loading model)
- 14+ unit tests: agent tool (3), evaluator duplicate suppression (2), alert payload schema (2), lifespan registration (1), model hot-reload on registry change (2), crowding bucket → alert severity map (2), fail-open when model missing (2)

**Verify:** Start dev stack with ML-1.2 + ML-3.2 complete. Agent query "Which buses on route 22 will be crowded at 08:30 tomorrow?" returns a list with predicted load factors. Force a high-demand scenario in a test DB, confirm crowding alert fires within 2 min cycle.

---

### Phase ML-4: Anomaly Detection (5 days)

> **Sprint deliverable:** Three real-time anomaly detectors (off-route, stuck, GPS gap) catching fleet issues within 2 minutes of occurrence. Alerts routed to dispatchers via existing alerts system.

#### ML-4.1 Off-Route Detection
**What:** Background evaluator using PostGIS route corridors to detect when a vehicle drifts > N meters from its assigned route shape. Uses GTFS `shapes.txt` + `ST_Buffer` to build 50m corridors; triggers when vehicle is outside corridor for ≥ 3 consecutive position updates.
**Why:** Off-route vehicles are the #1 fleet anomaly dispatchers want to know about (wrong turn, driver deviation, service change miscommunication). GTFS shape data is already available once route polylines ship (see "Route Shape Polylines" TODO); detection is a straightforward spatial join.
**Implementation:**
- Prerequisite: `shapes.txt` imported into `gtfs_shapes` table (covered by existing Route Shape Polylines TODO at line 701)
- `app/ml/anomaly/off_route.py`:
  - `build_route_corridors()` — one-time: `ST_Buffer(ST_MakeLine(shape_points), 50)` per route → `route_corridors` materialized view
  - `OffRouteEvaluator.check_vehicle(vehicle_id) -> OffRouteStatus` — `ST_Contains(corridor, vehicle_position)` check
  - Background task: 60s cycle, tracks consecutive-offroute counts per vehicle in Redis, fires alert at 3 consecutive offs (≥3 min drift)
- `app/alerts/` integration via existing `AlertService.create_alert(type="off_route", ...)`
- Threshold configurable: `anomaly_offroute_buffer_meters: int = 50`, `anomaly_offroute_consecutive_hits: int = 3`
- 10+ unit tests: corridor build (2), containment check (2), consecutive tracking (2), Redis state reset on re-entry (1), alert deduplication (1), config tuning (2)

**Verify:** Manually set a test vehicle's position 100m outside its route corridor for 3 polls. Alert fires within 3 min. Move vehicle back inside — Redis state resets. Check evaluator runtime log: `transit.anomaly.off_route.fired {vehicle_id, route_id, drift_m}`.

#### ML-4.2 Stuck Vehicle + GPS Gap Detection
**What:** Two more detectors in the same `app/ml/anomaly/` package: (1) **stuck** — vehicle moved < 20m over last 10 minutes during an active trip; (2) **gps_gap** — no position updates from an active vehicle in the last 5 minutes (despite scheduled trip).
**Why:** "Stuck" catches breakdowns, accidents, and traffic pileups — dispatcher action (re-route other vehicles, notify passengers) requires knowing within minutes. "GPS gap" catches hardware failures, driver going offline, or upstream feed outages — different root cause, different response, so separate alert types.
**Implementation:**
- `app/ml/anomaly/stuck.py`:
  - `StuckVehicleEvaluator.check(vehicle_id)` — compute distance traveled in last 10 min via TimescaleDB window query (`SUM(ST_Distance(lag(pos), pos))`)
  - Exclude terminal stops + scheduled layovers (cross-reference `gtfs_stop_times` arrival_time/departure_time)
- `app/ml/anomaly/gps_gap.py`:
  - `GPSGapEvaluator.check(vehicle_id)` — compare `MAX(observed_at)` vs `NOW()`; fire if gap > 5 min and trip is scheduled active
  - Separate "feed-wide gap" detection: if ≥ 50% of a feed's vehicles gap at once, fire `feed_outage` instead of per-vehicle spam
- Shared base class `BaseAnomalyEvaluator` extracted when 3rd detector lands (three-feature rule)
- 15+ unit tests: stuck detection (3), terminal-stop exclusion (2), gps_gap detection (2), feed-wide suppression (2), spam suppression via Redis cooldown (2), timezone correctness (1), layover exclusion (2), concurrent-vehicle test (1)

**Verify:** Simulate a vehicle not moving for 12 min — stuck alert fires. Stop sending GPS for a vehicle for 6 min — gps_gap fires. Stop a whole feed — one `feed_outage` alert instead of 500 per-vehicle alerts.

#### ML-4.3 Anomaly Detection Routing + Deduplication
**What:** Central `AnomalyAlertRouter` that routes each anomaly type to the right alert channel (dispatcher dashboard, SMS for critical, Slack for ops), enforces per-vehicle cooldowns, and exposes `GET /v1/anomalies/recent` endpoint for the CMS.
**Why:** Three detectors × naive alerting = alert fatigue. Routing + cooldowns + severity mapping are cross-cutting concerns that should live once, in one place, not duplicated into each evaluator.
**Implementation:**
- `app/ml/anomaly/router.py`:
  - `AnomalyAlertRouter.route(anomaly: AnomalyEvent)` — looks up severity + channel from config, checks Redis cooldown, calls `AlertService`
  - Cooldown keys: `anomaly:cooldown:{type}:{vehicle_id}` with TTL per severity (critical=5min, warning=30min)
  - Channel matrix in config: `off_route → dashboard+slack`, `stuck → dashboard+slack+sms(critical)`, `gps_gap → dashboard`, `feed_outage → slack+pager`
- `app/transit/routes.py` — `GET /v1/anomalies/recent?limit=50` returns last N anomalies from a new `anomalies` table (or Redis stream if ephemeral is acceptable)
- `cms/apps/web/src/app/[locale]/anomalies/page.tsx` — minimal dashboard page (separate FE task; tracked as a follow-up)
- 12+ unit tests: router dispatches per type (3), cooldown enforcement (2), severity escalation (2), channel selection (2), endpoint auth (1), cooldown reset on resolve (1), alert payload schema (1)

**Verify:** Trigger all 3 anomaly types for the same vehicle in quick succession. Exactly 3 alerts created (one per type), no duplicates. Trigger same anomaly 30s later — suppressed by cooldown. `GET /v1/anomalies/recent` returns the 3 events in reverse-chronological order.

---

### Phase ML-5: Dashboards + Public API + Text-to-SQL (8 days)

> **Sprint deliverable:** Route performance dashboards in CMS, public developer API with key-based auth, Text-to-SQL via Schema RAG for complex analytics. Closes out Phase 4 of the transit platform.

#### ML-5.1 Route Performance Dashboard (CMS)
**What:** New CMS page `/analytics/routes` — per-route performance metrics: on-time %, avg delay by stop, passenger load trend, anomaly count. Charts via Recharts, data sourced from the existing `app/analytics/` slice (extended with ML-derived aggregates).
**Why:** The ML models and data pipelines are invisible to ops until surfaced in the UI. A single "route performance" page gives operations managers a daily pulse on fleet health, exposing the value of every earlier phase.
**Implementation:**
- `app/analytics/service.py` — new methods: `get_route_performance(route_id, window)`, `get_delay_heatmap(route_id, window)`, `get_load_trend(route_id, window)`
- `app/analytics/routes.py` — 3 new endpoints matching the service methods, cached 5 min via Redis
- `cms/apps/web/src/app/[locale]/analytics/routes/page.tsx`:
  - Route selector (dropdown, pre-populated from GTFS routes)
  - 4 Recharts: on-time % over time (line), avg delay by stop (bar), load factor heatmap (HeatmapChart), anomaly count (stacked area by type)
  - SDK wrapper in `@vtv/sdk`
- `cms/apps/web/messages/lv.json` + `en.json` — ~40 new i18n keys
- RBAC: admin + dispatcher roles
- 10+ backend tests, 6+ frontend component tests

**Verify:** `/analytics/routes` loads in CMS, route selector populates, all 4 charts render with real data for a selected route. Chart data matches `SELECT` queries against the underlying tables. Cache hit on second load (<50ms).

#### ML-5.2 Schedule Adherence Monitoring + Daily Report
**What:** Scheduled daily job that computes fleet-wide schedule adherence (overall %, per-route, per-hour), writes a `daily_adherence_report` row, and publishes an email/Slack summary to dispatcher managers. Alert threshold: overall adherence < 85% → high-severity alert.
**Why:** Dispatchers see real-time delays; managers need daily trend reports to decide on schedule revisions, driver training, or vehicle re-assignment. Automating the report removes the current manual spreadsheet process.
**Implementation:**
- `alembic/versions/k4l5m6n7o8p9_daily_adherence.py` — `daily_adherence_reports` table (date, overall_pct, per_route_json, per_hour_json, anomaly_counts_json, generated_at)
- `app/analytics/daily_adherence.py`:
  - `compute_daily_report(date: date) -> DailyAdherenceReport`
  - `publish_report(report)` — sends to Slack webhook + email (SMTP)
  - Alert threshold check: fires high-severity alert when overall adherence < config threshold
- `app/main.py` — register daily task at 06:00 UTC (after overnight data settles)
- `app/analytics/routes.py` — `GET /v1/analytics/adherence/daily?from=&to=` returns stored reports
- `app/core/config.py` — `analytics_adherence_threshold_pct: float = 85.0`, `analytics_adherence_slack_webhook: str | None = None`
- 10+ unit tests: report computation (3), publish fail-open (2), threshold alerting (2), schedule registration (1), date-range query (2)

**Verify:** Manually invoke `compute_daily_report(date(2026, 04, 10))` — produces report row, prints summary. Simulate adherence < 85%, confirm high-severity alert created. `GET /v1/analytics/adherence/daily?from=2026-04-01&to=2026-04-10` returns stored rows.

#### ML-5.3 Public Developer API with API Key Auth
**What:** New `app/public_api/` vertical slice — read-only subset of transit endpoints (`/public/v1/routes`, `/public/v1/stops`, `/public/v1/vehicles`) gated behind API keys. Per-key rate limiting (default 60/min, configurable per tier). Developer portal landing page in CMS (`/developers`) with self-serve key generation.
**Why:** Third-party app developers (rider apps, transit researchers, journalists) repeatedly ask for direct data access. A dedicated public API is much safer than opening internal endpoints — it lets us rate-limit, version, revoke, and monitor usage independently without touching internal APIs.
**Implementation:**
- `alembic/versions/l5m6n7o8p9q0_api_keys.py` — `api_keys` (id, owner_user_id, key_hash, name, tier, created_at, last_used_at, revoked_at), `api_key_usage` TimescaleDB hypertable
- `app/public_api/`:
  - `models.py`, `schemas.py`, `repository.py`, `service.py` — standard VSA layout
  - `auth.py` — `APIKeyAuth` dependency: reads `X-API-Key` header, hashes, looks up, enforces rate limit via Redis token bucket
  - `routes.py` — 3 endpoints (routes / stops / vehicles), read-only, CORS-enabled, `Cache-Control: public, max-age=30`
- `cms/apps/web/src/app/[locale]/developers/page.tsx`:
  - Landing page with API docs link, key generation form, key list with revoke button
  - Only authenticated users with `editor` role or above can create keys
- `docs/api/public-v1.md` — OpenAPI reference + usage examples (curl + Python)
- Documentation: publish to `data.gov.lv` per CC0 commitment
- 20+ tests: key generation, hash verification (bcrypt same as password), rate limit enforcement, revocation, per-tier limits (60 / 300 / 1000 req/min), CORS headers, CMS key-management UI

**Verify:** Generate a key via CMS. `curl -H "X-API-Key: <key>" https://vtv.lv/public/v1/vehicles` returns live vehicles. Hammer endpoint > 60 req/min → 429. Revoke key → 401. Key usage shows up in `api_key_usage` hypertable.

#### ML-5.4 Text-to-SQL with Schema RAG
**What:** New agent tool `run_analytics_sql(natural_language_question)` that uses pgvector Schema RAG (retrieve 5 similar example queries) + LLM to generate a SELECT statement, validates against a whitelist (SELECT-only, no DDL/DML, query plan cost < 10k), executes, and returns results. Seeded with 200-500 curated examples.
**Why:** Completes Phase 4 of the platform plan. Dispatchers and analysts ask questions the existing tools don't cover ("how many buses were late by > 15 min on route 22 during rain in the last 30 days?"). Text-to-SQL with schema RAG is the pattern that scales without endless manual tool additions. Safety relies on: retrieval-constrained prompting (LLM sees only example SELECTs), SQL parser whitelist, and query-plan cost gate.
**Implementation:**
- `alembic/versions/m6n7o8p9q0r1_schema_examples.py` — `schema_examples` table (id, question_text, question_embedding VECTOR(1024), sql_query TEXT, description, validated_at, tags)
- `app/core/agents/tools/transit/run_analytics_sql.py`:
  - Retrieval: embed `question`, `ORDER BY embedding <=> $1 LIMIT 5` → example queries
  - Prompt: "Given these 5 example queries on the VTV schema, write a SELECT for: {question}. Use only tables: {schema_whitelist}. SELECT only."
  - Validation: `sqlparse` → reject anything that isn't SELECT, no `UPDATE`/`DELETE`/`DROP`/`GRANT`/`COPY`/`;--`
  - Cost check: `EXPLAIN (FORMAT JSON) <query>` → reject if `Total Cost > 10000`
  - Execution: read-only DB user (new role `vtv_readonly_agent` created in migration), 5s statement timeout
- `scripts/seed_schema_examples.py` — loads a hand-curated YAML file into `schema_examples` table with embeddings
- `app/core/agents/agents/transit.py` — add tool to `TransitAgent.tools` and `UnifiedAgent.tools`
- Security (CTX-AGENT, CTX-INPUT): three-layer defense — prompt constraint, parser whitelist, read-only DB role with statement timeout. Explicit test cases for each injection attempt.
- 25+ unit tests: retrieval (3), prompt assembly (2), parser whitelist (8 injection attempts including stacked queries, comment obfuscation, UNION, encoded chars, schema introspection, role escalation, DoS via CROSS JOIN, write attempts), cost gate (3), read-only role enforcement (2), result truncation at 100 rows (2), telemetry log (2), seed script idempotency (2), agent tool integration (1)

**Verify:** Seed 50 example queries. Agent query: "How many buses were > 10 minutes late on route 22 yesterday?" → generates valid SELECT, executes, returns count. Try injection: "'; DROP TABLE documents; --" → parser rejects. Try expensive query "select count(*) from vehicle_positions cross join vehicle_positions" → cost gate rejects. Try write: "update vehicles set active=false" → rejected at parser AND read-only role level (defense in depth).

---

### Intelligence/ML — Summary

| Phase | Focus | Days | Depends on |
|-------|-------|------|------------|
| ML-1  | Data ingestion (GTFS archive, e-ticket, weather, traffic) | 6 | Full Latvia Phase 1 |
| ML-2  | ETA prediction model (LightGBM + weather) | 8 | ML-1, 90d TimescaleDB history |
| ML-3  | Passenger load prediction + crowding alerts | 6 | ML-1.2, ML-2 |
| ML-4  | Anomaly detection (off-route, stuck, GPS gap) | 5 | Route Shape Polylines TODO, alerts slice |
| ML-5  | CMS dashboards, public API, Text-to-SQL | 8 | ML-1..ML-4 |

Total ML platform build-out: **33 days** across 17 subtasks. ML-1 is the single largest unblocker — nothing trains without it. ML-2/ML-3 can partially overlap once ML-1 lands (they share the feature-engineering + registry infrastructure). ML-4 is the most independent phase — only needs route shapes + alerts, both already scoped elsewhere. ML-5.3 (public API) can ship ahead of any model work if prioritised for external demand.

---

_Completed work archived to [docs/TODO-archive.md](TODO-archive.md)._
