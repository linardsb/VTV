# Agent Module

Pydantic AI agent (`Agent[UnifiedDeps, str]`) with 11 tools across 4 domains. Follows vertical slice pattern with `tools/` subdirectory.

## Directory Structure

```
app/core/agents/
├── agent.py           # Agent creation, 11 tool registrations + build_instructions_with_skills()
├── routes.py          # /v1/chat/completions, /v1/models, /v1/chat/metrics (admin-only correction metrics, AI-5.3) — rate limited + quota. AI-6.3: when `agent_multi_agent_enabled` flag is on and incoming `body.agent == "unified"`, the most-recent user message is fed through `AgentRouter.route()` to upgrade `"unified"` to a domain-specific agent before resolution
├── router.py          # AI-6.3: heuristic AgentRouter — keyword-regex scoring of prompts against transit/knowledge/vault signal sets. Returns `RoutingDecision(domain, transit_score, knowledge_score, vault_score)`. Tied or zero-score prompts fall back to `"unified"`. LLM-free, microsecond classification, mirrors `routing.py` design. Logs `agent.router.decision` with `prompt_hash` (12-char SHA-256, never raw prompt). Singleton via `get_agent_router()`. Gated by `agent_multi_agent_enabled` config flag (default off)
├── base.py            # AI-6.1: BaseAgentService harness — shared pipeline orchestrator owning the order: tier → prompt injection check → RAG routing → skills → memory → system prompt → validation cache preload → execute → post-process (QA footnotes) → **AgentResult wrapper (AI-6.5)** → **confidence re-route gate (AI-6.5, single retry to complex tier when confidence < threshold)** → response assembly → chat_started/completed logging → AgentExecutionError wrapping. Exposes 11 hook points (_get_model_tier, _apply_rag_routing, detect_relevant_skills, _recall_memories_block, build_system_prompt, _build_user_message, _preload_validation_cache, _execute [MUST override], _post_process/_run_qa/_should_run_qa, _build_response, _persist_episode). `_PipelineOutcome` extended with optional `confidence: float | None` + `tools_used: tuple[str, ...]`. Abstract for concrete subclasses.
├── service.py         # AgentService(BaseAgentService) — transit-domain concrete subclass. Overrides hooks that touch test-patched service-module globals (needs_rag, MemoryService, SkillService, agent, get_settings, build_instructions_with_skills, validate_transit_response, persist_agent_episode). Owns UnifiedDeps injection, SelfCorrectionLoop wiring, complex-pipeline dispatch, and the singleton lifecycle (get_agent_service / close_agent_service). Module-level __all__ explicitly re-exports every patched symbol.
├── schemas.py         # OpenAI-compatible request/response schemas
├── config.py          # LLM provider settings (model names, tokens, timeouts)
├── routing.py         # Multi-tier model routing (fast/standard/complex classification)
├── quota.py           # Daily per-IP quota tracker (50/day, auto-reset)
├── exceptions.py      # TransitDataError, ObsidianError → HTTP 503
├── validation.py      # Deterministic QA with severity-tagged Issues: route/stop plausibility + existence, delays, stale data, Latvian diacritics, time consistency, citation grounding, language match (AI-5.2)
├── correction.py      # AI-5.1/5.2 self-correction loop — bounded retry on error-severity validation failures (standard tier), instrumented with per-check metrics (AI-5.3)
├── metrics.py         # AI-5.3 in-process self-correction metrics tracker — per-check counters with lazy daily UTC reset
├── pipeline.py        # Multi-phase orchestrator for complex tier (own retry layer)
├── circuit_breaker.py # AI-8.1: async 3-state LLM provider breaker — `CircuitState` enum (CLOSED/OPEN/HALF_OPEN), frozen `BreakerConfig` (failure_threshold=5, recovery_timeout_s=30.0, success_threshold=2, window_size=20, failure_rate_threshold=0.5 — all env-var-backed via `Settings`), `CircuitBreaker.call(fn, /, *args, **kwargs) -> T` wrapper. Trips on consecutive-failure count OR sliding-window rate (rate trigger only arms once the window is full). Pluggable `time_fn` for `ManualClock` deterministic tests. `asyncio.Lock` guards state reads/writes; lock never held across the awaited `fn` call (3 separate acquisitions, mirrors `app/core/resilience.py`). Raises `CircuitBreakerOpenError(AgentError)` (HTTP 503). 7 log events under `agent.circuit_breaker.*` (opened/half_opened/closed/reopened/rejected/probe_success/probe_failure) — provider name + counters only, no credentials. Agent-module-local (not `app/shared/`) per three-feature rule. Kept separate from the GTFS-RT breaker at `app/core/resilience.py`. `_execute()` wiring is deferred to AI-8.2 follow-up behind the `circuit_breaker_enabled` kill switch.
├── context_budget.py  # AI-6.4: `ContextBudget(frozen=True)` dataclass + per-agent `AGENT_BUDGETS` dict + `agent_budget_for()` lookup. Default `skill_docs_max` 2000 tokens; transit=2500, knowledge=2000, vault=1500, unified=3000.
├── skill_loader.py    # AI-6.4: progressive L3 skill loader. Parses markdown files with YAML front matter (`yaml.safe_load` only), path-sandboxed via `Path.is_relative_to`, priority-gated (P1 always, P3 drops when remaining <70%, P2 drops when remaining <30%), token-budget-aware, keyword-filtered against lowercased prompt (never regex). Module-level cache keyed by domain; fail-open on every error path (logs `agent.skill_loader.*` and returns None/""). Public API: `SkillMeta`, `parse_skill_file()`, `discover_skills()`, `load_skills_within_budget()`, `clear_cache()`.
├── agent_result.py    # AI-6.5: `AgentResult(frozen=True)` dataclass — metadata-only wrapper built inside `BaseAgentService.chat()` from `_PipelineOutcome` + active domain. Fields: content (post _post_process), confidence (0..1 or None), warnings (metadata only — NOT rendered into content, that happens in _post_process earlier), tools_used, domain. `__post_init__` validates domain ∈ VALID_DOMAINS and confidence range.
├── skills/            # AI-6.4: in-repo L3 skill packs (markdown + YAML front matter, priority + token_cost + keywords). 5 transit (delay_analysis P2, schedule_interpretation P2, route_comparison P3, driver_availability P3, adherence_reporting P3), 4 knowledge (sop_retrieval P1 always-on, regulation_interpretation P2, shift_handover P3, incident_response P2), 3 vault (search_patterns P2, bulk_operations P3, folder_organization P3).
├── evals/             # AI-7.1: synthetic eval cases (YAML) + loader. 15 transit + 10 knowledge + 5 vault cases. Frozen `EvalCase` dataclass with `__post_init__` validation; loader is fail-open and path-sandboxed (mirrors skill_loader.py). AI-7.2: `runner.py` CLI + `EvalTrace` JSONL writer under `evals/traces/` (fail-open per case, path-sandboxed output, never logs prompts; `chat_with_trace()` on `BaseAgentService` exposes trace metadata). AI-7.3: `judge.py` Pydantic AI one-shot judge — grades each case across its 5 per-criterion descriptions (PASS/FAIL + ≤280-char reasoning). Fail-open per case, path-sandboxed JSONL under `evals/verdicts/`, never logs raw prompt/response. AI-7.4: `regression.py` per-criterion pass-rate baselines under `evals/baselines/{suite}_baseline.json` (committed), `check_regression()` with 3pp default tolerance, `make eval-judge` / `make eval-baseline` / `make eval-check` for CI gating, `--update-baseline` for intentional drift.
├── tools/
│   ├── transit/       # 5 read-only tools (GTFS-RT + static data, DB-backed)
│   │   ├── schemas.py, deps.py, client.py, static_cache.py, static_store.py
│   │   ├── query_bus_status.py      # Tool 1: status/route_overview/stop_departures
│   │   ├── get_route_schedule.py    # Tool 2: timetable by route/date/direction
│   │   ├── search_stops.py          # Tool 3: search by name or proximity
│   │   ├── get_adherence_report.py  # Tool 4: on-time performance metrics
│   │   ├── check_driver_availability.py # Tool 5: driver staffing queries
│   │   └── tests/                   # 104 tests
│   ├── obsidian/      # 4 read-write tools (Obsidian Local REST API)
│   │   ├── schemas.py, client.py
│   │   ├── query_vault.py           # Tool 6: search/tags/list/recent/glob
│   │   ├── manage_notes.py          # Tool 7: CRUD + frontmatter/section editing
│   │   ├── manage_folders.py        # Tool 8: folder CRUD (delete requires confirm)
│   │   ├── bulk_operations.py       # Tool 9: batch ops with dry_run preview
│   │   └── tests/                   # 68 tests
│   ├── knowledge/     # 1 read-only RAG search tool (with query router short-circuit)
│   │   ├── search_knowledge.py      # Tool 10: hybrid vector+fulltext, citations, confidence threshold, RAG router gate
│   │   └── tests/                   # 9 tests
│   └── skills/        # 1 skills management tool
│       └── manage_skills.py         # Tool 11: list/create operational skills
└── tests/             # 356 agent-level tests (incl. routing, config tier, self-correction loop, severity-tier QA, correction metrics + admin endpoint, BaseAgentService hook-point tests in test_base.py, AI-6.4 context_budget/skill_loader, AI-6.5 AgentResult + confidence re-route gate, AI-8.1 circuit breaker transitions + concurrency + invariants in test_circuit_breaker.py)
```

## Planned Improvements

See `docs/TODO.md` → "Agent Architecture Improvements" for the full roadmap. Key priorities:

1. **Multi-tier model routing** - Heuristic prompt classifier in `routing.py`, tier model resolution via `resolve_tier_model()` in `config.py`, integrated into `AgentService.chat()`. Configure via `LLM_FAST_*`/`LLM_STANDARD_*`/`LLM_COMPLEX_*` env vars.
2. **RAG retrieval** — ✅ Chunk overlap 50→100, ✅ result truncation 500→1500 chars, ✅ always-on reranking (AI-1.1), ✅ created_at date filtering (AI-1.2), ✅ temporal boost + query-adaptive RRF weights + evergreen flag (AI-1.3), ✅ confidence threshold 0.3 + "no results" response + anti-hallucination prompt (AI-1.4), ✅ query routing - signal-based RAG router skips knowledge search for transit/schedule/vault queries (AI-2.1), ✅ markdown-aware document extraction - PDF/DOCX/XLSX/CSV/email/image produce structured markdown chunks (AI-2.1), ✅ HyDE query expansion (AI-2.2), ✅ Redis embedding cache (AI-2.3), ✅ heading-aware semantic chunker (AI-4.1), ✅ parent-child chunk model (AI-4.2), ✅ parent-child retrieval + context expansion - search-time parent fetch with `[Section: ...]`/`[Matched passage:]` markers, batch-deduped, feature-gated (AI-4.3)
3. **Server-side memory** — pgvector-backed semantic memory with temporal decay (procedural/episodic/semantic types). Fire-and-forget bridge (`app/memory/bridge.py`) auto-persists multi-tool episodes after standard tier `agent.run()` (AI-3.3). Memory recall injected as context before each `agent.run()` via `build_instructions_with_skills()` (AI-3.4). LLM-based intent merging during compaction (configurable, off by default). Daily background compaction + promotion tasks via `app/memory/lifecycle.py`
4. **Multi-agent splitting** — ✅ AI-6.1: `BaseAgentService` harness extracted from `AgentService.chat()` into `base.py`. Pipeline orchestration + 11 hook points in the base; `AgentService` is a thin transit-specific subclass. Pure refactor, zero behavior change, 23 new hook-point tests. ✅ AI-6.2: domain-specific agents under `agents/` — `TransitAgent` (5 transit tools, full QA + correction + complex pipeline, `agent_name="transit_agent_v2"`), `KnowledgeAgent` (1 RAG tool, citation-enforced prompt, RAG always on), `VaultAgent` (4 obsidian tools, safe-delete prompt). Selected via `agent: 'unified'|'transit'|'knowledge'|'vault'` field on `ChatCompletionRequest` — default `unified` preserves the all-11-tool fallback so existing clients are unchanged. Per-agent singletons live in `agents/registry.py`; `close_all_agents()` wired into the lifespan shutdown next to `close_agent_service()`. 48 new tests (15 transit + 15 knowledge + 15 vault + 3 route regressions). ✅ AI-6.3: server-side heuristic auto-router in `router.py` — `AgentRouter` scores prompts against transit/knowledge/vault keyword signal sets (Latvian + English with diacritic variants), tied/zero-score prompts fall back to `"unified"`. Wired into `chat_completions` only when incoming `body.agent == "unified"` AND `agent_multi_agent_enabled` flag is on; explicit `agent="transit"` requests are never overridden. New `agent.router.decision` log event with `prompt_hash` (never raw prompt); expanded `agent.chat.selected` event with `requested_agent` + `auto_routed` fields for A/B analysis. 27 new tests (24 router unit + 3 endpoint integration). Default-off flag preserves current behavior for safe rollout. ✅ AI-6.4: progressive L3 skill system in `skill_loader.py` + `context_budget.py` — per-agent markdown skill packs with YAML front matter (`yaml.safe_load` only), path-sandboxed loader, priority-gated (P1 always, P2 <30%, P3 <70%), token-budget-aware (per-agent `ContextBudget`: transit 2500 / knowledge 2000 / vault 1500 / unified 3000), keyword-matched against lowercased prompt (no regex). 12 in-repo skill files (5 transit + 4 knowledge + 3 vault). Domain agents inject L3 skills via `detect_relevant_skills()` override; unified `AgentService` unions all three packs at 1/3 sub-budget. Flat DB-backed skills coexist unchanged. Gated by `agent_progressive_skills_enabled` (default True). 25 new tests (6 context_budget + 19 skill_loader). ✅ AI-6.5: `AgentResult(frozen=True)` metadata wrapper in `agent_result.py` (content, confidence, warnings, tools_used, domain — `__post_init__` validates domain + confidence range). Built inside `BaseAgentService.chat()` from extended `_PipelineOutcome` (now carries optional `confidence` + `tools_used`). Warnings are metadata only — rendered into content earlier in `_post_process` as before, never double-rendered. Confidence-based re-route gate: single retry to complex tier when `confidence < agent_confidence_reroute_threshold` (default 0.3) and current tier != complex; hard-capped at 1 extra LLM call per chat. Per-domain confidence heuristics: transit (1.0 clean / 0.6 warnings / 0.3 errors), knowledge (0.7 when tool ran / None otherwise), vault (1.0 baseline). Gated by `agent_confidence_reroute_enabled`. 10 new tests. Complex-tier pipeline retry semantics preserved.
5. **Bounded self-correction** — ✅ AI-5.1: `correction.py` wraps standard-tier `agent.run()` with deterministic QA + 1 retry. Stale-data warnings filtered as non-retryable. Validator exceptions fail-open. Logs `agent.correction.triggered/resolved/exhausted/failed`. Configurable via `agent_self_correction_enabled`/`agent_max_correction_rounds` (clamped ≤3). ✅ AI-5.2: severity-tagged `Issue` objects + 6 extended checks (route existence, stop existence, time consistency, citation grounding, language match, stale data). Error severity triggers retry; warning severity is footnote-only. ✅ AI-5.3: in-process per-check metrics tracker (`metrics.py`) with lazy 00:00 UTC daily reset; admin-only `GET /v1/chat/metrics` endpoint exposes triggered/resolved/exhausted counts + success rate + avg latency per check_name. Per-correction `agent.correction.metric` log line emitted on every resolved/exhausted event. Complex-tier pipeline retry still pending AI-6.x.
6. **Eval framework** — ✅ AI-7.1: 30 synthetic cases (15 transit + 10 knowledge + 5 vault) under `evals/cases/`, fail-open YAML loader with `EvalCase` schema validation. ✅ AI-7.2: `runner.py` CLI + `EvalTrace` JSONL writer under `evals/traces/`, `chat_with_trace()` on `BaseAgentService` exposes trace metadata (response envelope, `AgentResult`, parsed tool returns); fail-open per case, path-sandboxed output, no raw prompt logging; `make eval` / `make eval-all` targets. ✅ AI-7.3: `judge.py` one-shot Pydantic AI judge with `_CriterionJudgement` structured output (`output_type` parsing — no manual regex), grades each case across its 5 per-criterion descriptions (PASS/FAIL + ≤280-char reasoning). Fail-open per case, path-sandboxed JSONL under `evals/verdicts/`, judge prompt wraps trace content in `<<<BEGIN>>>`/`<<<END>>>` delimiters and instructs the model to treat it as data, never logs raw prompt/response (only case_id + criterion_name + counts + error_type). `make eval-judge SUITE=...` target. ✅ AI-7.4: `regression.py` aggregates `SuiteJudgement` into per-criterion pass rates, persists `BaselineReport` as committed JSON under `evals/baselines/{suite}_baseline.json`, `check_regression()` flags any criterion whose pass-rate drops more than `eval_baseline_tolerance_pct` (default 3pp). Errored verdicts excluded from baseline denominator. `regression.py` CLI has `baseline` (refuses overwrite without `--force`) and `check` (`--update-baseline` for intentional drift) subcommands. `make eval-baseline` / `make eval-check` targets. Exit codes: 0 pass, 1 regression, 2 infra failure.
7. **Provider resilience** — ✅ AI-8.1: async 3-state circuit breaker primitive in `circuit_breaker.py` — `CircuitState` enum, frozen `BreakerConfig` with `__post_init__` validation of all 5 knobs (failure_threshold=5, recovery_timeout_s=30.0, success_threshold=2, window_size=20, failure_rate_threshold=0.5), `CircuitBreaker.call(fn, /, *args, **kwargs) -> T` wrapper. `asyncio.Lock` guards state reads/writes in 3 separate acquisitions so the lock is never held across the awaited `fn` call (mirrors `app/core/resilience.py`). Sliding-window failure rate via `collections.deque(maxlen=window_size)`; rate trigger only arms once the window is full. `HALF_OPEN` uses a dedicated `success_threshold` probe counter; any probe failure immediately returns to OPEN with `trigger="probe_failure"`. Pluggable `time_fn` for `ManualClock` deterministic tests. `CircuitBreakerOpenError(AgentError)` wired into the agent exception handler → HTTP 503. 5 new pydantic-settings env-var-backed settings (`circuit_breaker_enabled` + 4 threshold knobs). 7 structured log events under `agent.circuit_breaker.*` (opened/half_opened/closed/reopened/rejected/probe_success/probe_failure) — fields restricted to provider name, state, counters, `elapsed_s`, `trigger` — no credentials / endpoints / raw exception repr (CTX-AGENT compliance). Agent-module-local primitive (three-feature rule) — kept separate from the GTFS-RT breaker at `app/core/resilience.py`. 19 unit tests cover all 6 transitions, recovery-timeout boundary (just-below vs exactly-at), sliding-window invariants, concurrent fast-fail after trip, config-validation errors, exception-type propagation, and structlog event assertion via `structlog.testing.capture_logs`. **Out of scope (AI-8.2 follow-up):** wiring into `_execute()` + per-provider registry, gated by the `circuit_breaker_enabled` kill switch.

Techniques derived from merkle-email-hub's blueprint engine architecture (state machine orchestration, `AgentHandoff` protocol, circuit breakers, comprehensive eval pipeline).

## Safety Constraints

- Transit tools: read-only, no write operations
- Vault deletes: require `confirm: true`
- Bulk operations: `dry_run` preview before execution
- Path sandboxing: prevents `../` directory traversal
- Rate limiting: 10 req/min chat, 30/min transit, 60/min health
- Request limits: 100KB body, 20 messages max, 4000 char/message
- Daily quota: 50 queries/IP (in-memory tracker)
- Monthly Claude API cap: EUR 100

## Tool Docstring Guidelines

Tool docstrings differ from standard Google-style — they're read by LLMs during tool selection and must guide the agent to choose the RIGHT tool efficiently.

**Key Principles:**
1. **Guide Tool Selection** — help agent choose this tool over alternatives
2. **Prevent Token Waste** — steer toward efficient parameter choices
3. **Enable Composition** — show how tool fits multi-step workflows
4. **Set Expectations** — performance characteristics and limitations
5. **Provide Examples** — concrete usage with realistic data

## Documentation Style

Use **Google-style docstrings** for all functions. Agent tools use the enhanced format above. Example:

```python
def process_request(user_id: str, query: str) -> dict[str, Any]:
    """Process a user request and return results.

    Args:
        user_id: Unique identifier for the user.
        query: The search query string.

    Returns:
        Dictionary containing results and metadata.

    Raises:
        ValueError: If query is empty or invalid.
    """
```


<claude-mem-context>
# Recent Activity

<!-- This section is auto-generated by claude-mem. Edit content outside the tags. -->

### Feb 21, 2026

| ID | Time | T | Title | Read |
|----|------|---|-------|------|
| #16621 | 12:30 PM | 🔵 | Documentation Structure Audit Reveals 75 Redundant Files | ~502 |
| #16617 | 12:23 PM | 🔄 | Agent Module Documentation Extracted to Scoped File | ~319 |

### Feb 24, 2026

| ID | Time | T | Title | Read |
|----|------|---|-------|------|
| #16775 | 5:07 PM | 🔵 | Data privacy and GDPR compliance features searched | ~347 |

### Feb 25, 2026

| ID | Time | T | Title | Read |
|----|------|---|-------|------|
| #16918 | 6:15 AM | ⚖️ | Agent Skills System implementation plan completed | ~1484 |
| #16875 | 5:58 AM | 🔵 | VTV Background Task & Lifespan Architecture Analysis | ~1313 |
| #16874 | 5:56 AM | 🔵 | VTV Architecture Deep Dive - Complete Transit Management Platform Analysis | ~738 |

### Feb 26, 2026

| ID | Time | T | Title | Read |
|----|------|---|-------|------|
| #17522 | 1:21 PM | 🔵 | VTV Slash Command System Architecture Documented | ~1163 |
</claude-mem-context>