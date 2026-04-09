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
Testing           ████████████████████░░░░  90%  (1049 unit tests, 106 security tests, 81 e2e tests, CI pipeline live with security gates)
Infrastructure    ██████████████████████░░  97%  (Docker, nginx+Brotli, Gunicorn multi-worker, Redis rate limiting, Makefile, 25 slash commands, CI/CD, 6 security audits, SDLC security framework, context-triggered security SDC)
Latvia Platform   ████████░░░░░░░░░░░░░░░  35%  (Riga GTFS + PostGIS + WebSocket + multi-feed GTFS-RT + TimescaleDB historical storage, no multi-city yet)
Agent Intelligence ██████░░░░░░░░░░░░░░░░░  25%  (Multi-tier routing done. AI-1.1 reranking done. AI-1.2 date filtering done. AI-1.3 temporal boost + RRF tuning done. AI-2.1 query router done. AI-2.2 HyDE done. AI-2.3 embedding cache done. 5 remaining phases: memory+bridge, chunking, self-correction, multi-agent+harness+L3 skills, eval)
Intelligence/ML   ░░░░░░░░░░░░░░░░░░░░░░░   0%  (Phase 4 — not started)
```

## In Progress

### E2E Testing Maturity

- [ ] **CRUD E2E Tests** - Tests that create/edit/delete records and verify persistence. Current 81 tests cover page loads, filters, navigation, and UI interactions but don't test full write operations (require seeded test data).

---

## Agent Intelligence — Phased Implementation

Techniques learned from merkle-email-hub's production multi-agent system. Full analysis: [docs/PLANNING/agent-intelligence-plan.md](PLANNING/agent-intelligence-plan.md).

### Phase AI-1: RAG Retrieval Quick Wins (3 days)

> **Sprint deliverable:** Immediate RAG quality boost with zero architectural changes. Reranking on by default, larger context windows, confidence gating.

#### AI-1.1 Always-On Cross-Encoder Reranking ✅
**Status:** Done — reranking was already default (`reranker_provider="local"`). Added `warm_up()` for startup preloading (eliminates 2-5s cold start), startup health log (`knowledge.reranker.loaded`), 10 unit tests for reranker providers. Route test updated to assert `reranked=True`. Plan: `.agents/plans/always-on-reranking.md`.

#### AI-1.2 Chunk Overlap + Result Truncation Expansion ✅
**Status:** Done — chunk overlap 50→100 (`chunking.py` + `config.py`), truncation 500→1500 (`search_knowledge.py`), `created_after`/`created_before` date filtering added to `SearchRequest` schema, repository (`search_vector` + `search_fulltext`), service layer, and agent tool (ISO string params). 4 new tests + 2 updated tests. Plan: `.agents/plans/ai-1.2-chunk-overlap-truncation.md`.

#### AI-1.3 Temporal Boost + RRF Weight Tuning ✅
**Status:** Done — `_detect_query_type()` classifies queries as keyword/semantic/mixed (EN + LV patterns), `_temporal_boost()` multiplies RRF scores by age (today: 1.5x, week: 1.2x, month: 1.0x, older: 0.8x), `evergreen` bool column on Document model skips decay. Both functions in `service.py` (not repository — deviation from plan, cleaner placement). 8 config settings for weights/multipliers. 13 new tests. Migration `f3a4b5c6d7e8`. Plan: `.agents/plans/ai-1.3-temporal-boost-rrf-tuning.md`.

#### AI-1.4 Confidence Threshold + "No Results" Response ✅
**Status:** Done — `knowledge_confidence_threshold: float = 0.3` in `config.py`, service filters reranked results below threshold with structured logging (`knowledge.search.confidence_filtered`), tool returns "No relevant documents found" plain string when empty, `KNOWLEDGE BASE BEHAVIOR` section added to agent system prompt preventing hallucination. 2 new tests (9 total in knowledge tool tests). Plan: `.agents/plans/ai-1.4-confidence-threshold.md`.

---

### Phase AI-2: Query Router + HyDE (4 days) ✅

> **Sprint deliverable:** Skip RAG for transit queries (60% of volume), fix Latvian embedding weakness via HyDE. Net result: faster responses + better retrieval quality.

#### AI-2.1 RAG Query Router ✅
**Status:** Implemented. Plan: `.agents/plans/ai-2.1-rag-query-router.md`
**What:** `app/knowledge/router.py` — signal-based classifier (9 RAG + 8 skip regex patterns, LV+EN). Determines if a query needs RAG retrieval. Transit/schedule/vault queries skip RAG; knowledge/policy/SOP queries trigger RAG. Also includes markdown-aware document extraction — PDF/DOCX/XLSX/CSV/email/image extractors now produce structured markdown (headings, tables, bold, blockquotes) instead of flat text. Zero runtime cost (conversion at upload time).
**Implementation:**
- `app/knowledge/router.py` — `needs_rag()` function with `RoutingDecision` NamedTuple (needs_rag, rag_score, skip_score)
- `app/core/agents/service.py` — router integrated between `classify_prompt()` and skills loading. Sets `UnifiedDeps.rag_enabled` flag.
- `app/core/agents/tools/knowledge/search_knowledge.py` — short-circuits with guidance message when `rag_enabled=False`
- `app/core/config.py` — `knowledge_router_enabled: bool = True` config flag
- `app/knowledge/processing.py` — markdown-aware extractors: PDF (font size/bold heading detection), DOCX (heading/list/table mapping), XLSX/CSV (markdown tables), image (blockquote wrapper), email (bold headers)
- 28 router tests + 3 service integration tests + 6 processing tests + 2 DMS test updates = 39 new/updated tests
**Verify:** "Kuri marsruti kavejas?" → RAG skipped. "Kada ir procedura par virsstundam?" → RAG invoked.

#### AI-2.2 HyDE (Hypothetical Document Embeddings) ✅
**Status:** Implemented. Plan: `.agents/plans/ai-2.2-hyde.md`
**What:** `app/knowledge/hyde.py` — before embedding a query for vector search, generate a hypothetical answer using a fast/cheap LLM, then embed that instead of the raw query. Improves retrieval quality for low-resource languages like Latvian (~15-20% expected improvement at ~$0.001/query).
**Implementation:**
- `app/knowledge/hyde.py` — `expand_query()` function with `_resolve_model()` helper. Model priority: `knowledge_hyde_model` > fast-tier LLM > primary LLM. Graceful degradation on LLM failure (falls back to raw query). Output truncated to `max_tokens * 4` chars.
- `app/knowledge/service.py` — in `search()`, if `knowledge_hyde_enabled`, call `hyde.expand_query()` and embed the result instead of the raw query. Raw query still used for fulltext search.
- `app/core/config.py` — `knowledge_hyde_enabled: bool = False`, `knowledge_hyde_model: str | None = None`, `knowledge_hyde_max_tokens: int = 200`
- Uses `pydantic_ai.Agent` (lazy-imported, same pattern as auto-tagging)
- 8 tests: model resolution (3), success path, LLM failure fallback, output truncation, search integration enabled/disabled
**Verify:** Compare retrieval quality for "Ko darīt, ja autobuss sabojājas maršrutā?" with HyDE on vs off. HyDE should surface SOP documents in top 3 that were previously at position 5+. Measure latency overhead — should be <500ms with fast model.

#### AI-2.3 Embedding Cache
**Status:** Implemented. Plan: `.agents/plans/ai-2.3-embedding-cache.md`
**What:** Cache query embeddings in Redis with TTL to avoid redundant embedding API calls for repeated queries. Use normalized query text as cache key (lowercase, stripped whitespace, sorted words).
**Why:** Dispatchers ask the same questions repeatedly ("route 3 status", "which routes delayed"). Caching embeddings for these saves API costs and reduces latency from ~200ms to <5ms for cached queries.
**Implementation:**
- `app/knowledge/embedding.py` — `CachedEmbeddingProvider` wrapper class with `_normalize_query()`. Decorates any `EmbeddingProvider` with Redis-backed per-text caching. Batch `mget` for cache lookup, pipeline `setex` for writes. Graceful fallback on any Redis error.
  - Key: `emb:{provider}:{blake2b(normalized_query)[:16]}`
  - Value: JSON-serialized float list
  - TTL: 1 hour (configurable via `EMBEDDING_CACHE_TTL`)
- `app/knowledge/service.py` — `_get_embedding()` singleton wraps provider with `CachedEmbeddingProvider` when `embedding_cache_enabled=True`
- `app/core/config.py` — `embedding_cache_enabled: bool = True`, `embedding_cache_ttl: int = 3600`
- Cache hit/miss logging: `knowledge.embedding_cache.hit` / `knowledge.embedding_cache.miss` / `knowledge.embedding_cache.redis_unavailable` / `knowledge.embedding_cache.read_failed` / `knowledge.embedding_cache.write_failed`
- 14 unit tests: normalization (3), cache keys (3), hit/miss (3), Redis fallback (3), service integration (2)
**Verify:** Send same query twice. First call hits embedding API (check logs). Second call hits cache (check logs, latency <5ms). Wait past TTL — next call hits API again.

---

### Phase AI-3: Persistent Agent Memory + Bridge (6 days)

> **Sprint deliverable:** Agent learns from usage. Stores successful tool sequences, dispatcher patterns, and transit domain knowledge. Memory bridge auto-persists from agent results (fire-and-forget). Recalled before each agent run and injected as context. LLM-based intent merging during compaction.

#### AI-3.1 Memory Vertical Slice — Models + Repository
**What:** Create `app/memory/` vertical slice with `MemoryEntry` SQLAlchemy model backed by pgvector. 4 memory types: procedural (learned patterns), episodic (session logs), semantic (durable facts), query_pattern (frequent queries).
**Why:** The agent is currently stateless — it can't learn from repeated usage. The same dispatcher asking the same question gets no benefit from prior interactions. Email-hub's `app/memory/` proves this pattern works at scale with pgvector + temporal decay.
**Implementation:**
- Create `app/memory/models.py`:
  - `MemoryEntry(Base, TimestampMixin)`: id, agent_type (str), memory_type (str enum), content (str), embedding (Vector(1024)), metadata_json (JSONB), decay_weight (float, default 1.0), is_evergreen (bool, default False), source (str: "agent"|"dispatcher"|"compaction"), recalled_count (int, default 0)
- Create `app/memory/repository.py`:
  - `store(entry: MemoryEntry) -> MemoryEntry`
  - `recall(embedding: list[float], agent_type: str | None, limit: int, min_score: float) -> list[MemoryEntry]` — pgvector cosine similarity + metadata filtering
  - `get_by_type(memory_type: str, limit: int) -> list[MemoryEntry]`
  - `increment_recalled_count(entry_id: int) -> None`
  - `delete_decayed(threshold: float) -> int`
- Alembic migration: `memory_entries` table with `ivfflat` index on embedding column
**Verify:** `make db-migrate` succeeds. Unit tests: store a memory, recall by similarity, verify cosine ordering. 15+ tests.

#### AI-3.2 Memory Service — Store, Recall, Compact
**What:** Create `app/memory/service.py` with memory lifecycle management: store (with embedding), recall (similarity search), compact (merge similar, apply decay), and promote (episodic → procedural after 3+ recalls).
**Why:** Raw storage isn't enough — memories need lifecycle management. Transit operations knowledge has seasonal patterns (90-day procedural decay, 30-day episodic decay). Auto-promotion captures recurring patterns without manual intervention.
**Implementation:**
- Create `app/memory/service.py`:
  ```python
  class MemoryService:
      async def store(content, memory_type, agent_type, metadata) -> MemoryEntry
          # Embed content, check for duplicates (cosine > 0.95 = skip), store
      async def recall(query, agent_type=None, limit=5) -> list[MemoryEntry]
          # Embed query, similarity search, increment recalled_count
      async def compact() -> CompactionResult
          # Apply decay: procedural 90d, episodic 30d, semantic evergreen, query_pattern 60d
          # Merge entries with cosine > 0.92 (keep higher recalled_count)
          # Delete entries with decay_weight < 0.1
      async def promote_episodes() -> int
          # Find episodic entries with recalled_count >= 3, clone as procedural
  ```
- Create `app/memory/schemas.py` — Pydantic request/response schemas
- Create `app/memory/routes.py` — admin-only: `GET /api/v1/memory` (list), `GET /api/v1/memory/{id}`, `DELETE /api/v1/memory/{id}`, `POST /api/v1/memory/compact` (trigger manual compaction)
- `app/core/config.py` — `MemoryConfig`: enabled (bool), procedural_decay_days (90), episodic_decay_days (30), query_pattern_decay_days (60), promotion_threshold (3), max_recall_results (5)
**Verify:** Store 10 memories. Recall by query — top 5 returned in cosine order. Run compact — decayed entries deleted. Recall an episodic memory 3 times — confirm auto-promoted to procedural. 20+ tests.

#### AI-3.3 Memory Bridge — Auto-Persist from Agent Results
**What:** Create `app/memory/bridge.py` — fire-and-forget callback that auto-persists successful multi-tool agent interactions as episodic memories. Adapted from email-hub's `HandoffMemoryBridge` pattern (`app/ai/blueprints/handoff_memory.py`).
**Why:** Email-hub wires this as a callback after every agentic node — the bridge captures what the agent learned without any manual intervention. Failure-safe (exceptions caught, logged, never crash pipeline). This is the mechanism that makes memory actually accumulate.
**Implementation:**
- Create `app/memory/bridge.py`:
  - `persist_agent_episode(agent_name, prompt, response, tools_used, confidence)` — fire-and-forget
  - Only persists when 2+ distinct tools used (multi-tool interactions are more valuable)
  - Content format: `"[{agent_name}] Dispatcher asked: {prompt[:150]}. Agent used: {tools}. Response: {response[:300]}"`
  - Metadata: `{source: "agent", agent_name, tools, confidence}`
  - Opens own DB session via `get_db_context()` (isolated transaction)
  - All exceptions caught and logged as warnings — never crashes pipeline
- Wire into `AgentService.chat()` — call after successful `agent.run()` response
**Verify:** Send multi-tool query ("which stops on route 22 have delays?"). Check DB — episodic memory stored. Send single-tool query — no memory stored (only multi-tool). Force DB error — pipeline continues normally, warning logged. 8+ tests.

#### AI-3.4 Memory Integration into Agent Pipeline
**What:** Integrate memory recall before `agent.run()` and episodic storage via bridge after responses. Memory context injected as system-level context alongside skills. Add LLM-based intent merging to compaction (from email-hub).
**Why:** Memory is useless if it's not in the agent's context window. Integration must happen at the service layer to work across all agent types. LLM-based intent merging (email-hub's `judge_functional_equivalence()`) prevents memory bloat better than cosine similarity alone.
**Implementation:**
- `app/core/agents/service.py` — in `AgentService.chat()`:
  1. Before `agent.run()`: `memories = await memory_service.recall(prompt, limit=5)`
  2. Filter: only results with `score > 0.3` (similarity threshold, from email-hub)
  3. Format as context: `"## Relevant memories\n" + "\n".join(m.content for m in memories)`
  4. Inject via `instructions=` parameter alongside skills
  5. After `agent.run()`: call `persist_agent_episode()` from bridge (AI-3.3)
- `app/memory/service.py` — enhance `compact()` with LLM-based intent merging:
  - Find memory pairs with cosine > 0.85
  - Lightweight LLM judge confirms functional equivalence (fast model, <100 tokens)
  - Keep entry with higher `recalled_count`, delete the other
- Background task in `app/core/lifespan.py` — run `memory_service.compact()` daily at 03:00 UTC
- Background task — run `memory_service.promote_episodes()` daily at 03:15 UTC
- Add `MEMORY__ENABLED: bool = False` config flag (default off for safe rollout)
- Add `MEMORY__CONTEXT_INJECTION_LIMIT: int = 10` (max memories to inject, recall uses limit=5)
**Verify:** Enable memory. Ask "Which routes are frequently delayed?" — agent responds. Ask again next session — confirm memory of prior interaction appears in context (check structured logs). Confirm LLM intent merging deduplicates similar memories during compaction. 12+ tests.

---

### Phase AI-4: Semantic Chunking + Parent-Child Retrieval (4 days)

> **Sprint deliverable:** Documents chunked by meaning boundaries, not character count. Matched chunks return full parent section for context. Re-chunk existing documents via migration script.

#### AI-4.1 Heading-Aware Semantic Chunker
**What:** Replace the fixed 512-char recursive splitter in `chunking.py` with a heading-aware chunker that respects document structure. Creates chunks at heading/section boundaries with adaptive sizing.
**Why:** Fixed-size splitting breaks mid-sentence, mid-paragraph, and mid-SOP-step. A "What to do when bus breaks down" SOP gets split into fragments that individually make no sense. Heading-aware chunking keeps each section coherent.
**Implementation:**
- `app/knowledge/chunking.py` — add `SemanticChunker` class:
  - Detect headings: markdown `#`, PDF section headers (bold + larger font), DOCX heading styles
  - Split at heading boundaries first, then at paragraph boundaries within sections
  - Adaptive sizing: min 256 chars, max 1500 chars, target 800 chars
  - If a section exceeds max, split at paragraph boundaries within it
  - Preserve heading text as `heading_path` metadata on each chunk
- Keep `RecursiveChunker` as fallback for unstructured documents
- `app/core/config.py` — `KNOWLEDGE__SEMANTIC_CHUNKING_ENABLED: bool = True`, `KNOWLEDGE__CHUNK_TARGET_SIZE: int = 800`
**Verify:** Upload a multi-section SOP PDF. Inspect chunks — each should align with a section, not split mid-sentence. Compare retrieval quality vs old chunking on 5 test queries.

#### AI-4.2 Parent-Child Chunk Model
**What:** Extend `DocumentChunk` model with `parent_chunk_id`, `heading_path`, and `section_type` fields. Create parent chunks (full sections) with child chunks (paragraphs) linked via foreign key.
**Why:** When a paragraph chunk matches, the dispatcher often needs the surrounding section context. Parent-child enables "return the full section when a paragraph matches" retrieval, critical for SOPs where steps reference earlier context.
**Implementation:**
- `app/knowledge/models.py` — add to `DocumentChunk`:
  - `parent_chunk_id: Mapped[int | None] = mapped_column(ForeignKey("document_chunks.id"))`
  - `heading_path: Mapped[str | None]` — e.g., "Emergency Procedures > Route Deviation"
  - `section_type: Mapped[str | None]` — "heading" | "body" | "list" | "table"
- Alembic migration for new columns + self-referential FK
- `app/knowledge/chunking.py` — `SemanticChunker` creates parent chunks (embedded, searchable) and child chunks (linked to parent)
**Verify:** `make db-migrate` succeeds. Upload SOP — inspect DB: child chunks have `parent_chunk_id` set. Query returns both child match and parent context. 10+ tests.

#### AI-4.3 Parent-Child Retrieval + Context Expansion
**What:** When hybrid search returns a child chunk match, automatically fetch and include the parent chunk content in the agent's context. Deduplicate when multiple children from the same parent match.
**Why:** A child chunk matching "call depot X" is useless without the parent context "When bus breaks down on route 22, follow these steps: 1. call depot X, 2. reroute via Y, 3. notify dispatcher Z."
**Implementation:**
- `app/knowledge/repository.py` — in `hybrid_search()`, after retrieval:
  1. For each result with `parent_chunk_id`, fetch parent chunk
  2. Deduplicate parents (same parent from multiple children = one parent)
  3. Return `SearchResult` with `chunks` (original matches) + `parent_contexts` (expanded sections)
- `app/core/agents/tools/knowledge/search_knowledge.py` — format results with parent context: `"[Section: {heading_path}]\n{parent_content}\n\n[Matched passage:]\n{child_content}"`
- `app/core/config.py` — `KNOWLEDGE__PARENT_CONTEXT_ENABLED: bool = True`
**Verify:** Upload multi-section SOP. Search for specific step mentioned in section 3. Result should include full section 3 as context, not just the matched paragraph.

#### AI-4.4 Re-Chunk Existing Documents
**What:** Migration script to re-chunk all existing documents using the new semantic chunker. Preserves document metadata, regenerates chunks and embeddings.
**Why:** Existing documents were chunked with the old 512-char recursive splitter. They need to be re-chunked to benefit from semantic boundaries and parent-child structure.
**Implementation:**
- Create `scripts/rechunk_documents.py`:
  1. Fetch all documents from DB
  2. For each: delete old chunks, re-chunk with `SemanticChunker`, re-embed, store new chunks
  3. Progress bar, batch processing (10 docs at a time to avoid memory issues)
  4. Dry-run mode: show what would change without modifying DB
- Add `make rechunk` Makefile target
- Handle edge case: documents with no raw text stored (re-extract from file)
**Verify:** Run `make rechunk --dry-run` — shows expected changes. Run `make rechunk` — all documents re-chunked. Search quality on 5 test queries should improve vs old chunking.

---

### Phase AI-5: Bounded Self-Correction (3 days)

> **Sprint deliverable:** Agent validates its own responses before returning to dispatchers. Factual errors (wrong route numbers, impossible times) caught and corrected via 1 retry round.

#### AI-5.1 Self-Correction Loop
**What:** Create `app/core/agents/correction.py` — after `agent.run()`, run deterministic QA checks. If checks fail, retry once with failure context injected. If still failing, return response with warnings (current behavior).
**Why:** Currently, validation issues are appended as footnote warnings but the incorrect content is still shown. One retry with explicit failure context lets the agent correct simple factual errors (wrong route number, impossible departure time) before dispatchers see them.
**Implementation:**
- Create `app/core/agents/correction.py`:
  ```python
  MAX_SELF_CORRECTION_ROUNDS = 1  # Transit needs fast responses

  class SelfCorrectionLoop:
      async def run_with_correction(self, agent, prompt, history, deps) -> CorrectedResult:
          for iteration in range(MAX_SELF_CORRECTION_ROUNDS + 1):
              result = await agent.run(prompt, message_history=history, deps=deps)
              issues = self.validator.validate(result.data)
              if not issues:
                  return CorrectedResult(content=result.data, issues=[], iteration=iteration)
              if iteration < MAX_SELF_CORRECTION_ROUNDS:
                  correction_prompt = self._build_correction_prompt(prompt, result.data, issues)
                  # Append as new turn, retry
              else:
                  return CorrectedResult(content=result.data, issues=issues,
                      warnings=[f"Validation: {i.description}" for i in issues])
  ```
- `app/core/config.py` — `AGENT__SELF_CORRECTION_ENABLED: bool = True`, `AGENT__MAX_CORRECTION_ROUNDS: int = 1`
- Structured logging: `agent.correction.triggered`, `agent.correction.resolved`, `agent.correction.exhausted`
**Verify:** Mock a response mentioning route 999 (doesn't exist). Confirm correction loop retries. Confirm corrected response doesn't mention route 999. Confirm `iteration=1` in logs. 10+ tests.

#### AI-5.2 Extended QA Checks
**What:** Add 6 new deterministic QA checks beyond existing `validation.py`: route existence, stop existence, time consistency, citation grounding, language match, and stale data warning.
**Why:** Current validation catches basic issues (route number range, delay magnitude). These new checks catch the most common factual errors dispatchers report: non-existent routes, impossible times, and ungrounded citations.
**Implementation:**
- `app/core/agents/validation.py` — add checks:
  1. `check_route_existence(response, static_cache)` — extract route numbers via regex, verify against GTFS static cache
  2. `check_stop_existence(response, static_cache)` — extract stop names, verify against stop DB
  3. `check_time_consistency(response)` — detect impossible times (25:30, departures in the past for future queries)
  4. `check_citation_grounding(response, tool_results)` — verify cited documents were in search results
  5. `check_language_match(prompt, response)` — detect language mismatch (query LV, response EN)
  6. `check_stale_data(tool_results, max_age_seconds)` — flag if GTFS-RT data older than cache TTL
- Each check returns `Issue(check_name, description, severity)` — severity: error (triggers retry) vs warning (footnote only)
**Verify:** Test each check with a crafted response that should trigger it. Confirm error-severity issues trigger self-correction. Confirm warning-severity issues only add footnotes. 12+ tests.

#### AI-5.3 Correction Metrics + Dashboard
**What:** Track self-correction metrics: correction rate, retry success rate, common failure types. Expose via admin endpoint for monitoring.
**Why:** Need to know if self-correction is actually improving response quality or just adding latency. High correction rates on specific checks indicate prompt engineering opportunities.
**Implementation:**
- `app/core/agents/correction.py` — add in-memory metrics counter:
  - `corrections_triggered`, `corrections_resolved`, `corrections_exhausted` (per check type)
  - Reset daily at 00:00 UTC
- `app/core/agents/routes.py` — add `GET /v1/chat/metrics` (admin-only) returning correction stats
- Structured logging on each correction: `agent.correction.metric {check_name, resolved, latency_ms}`
**Verify:** Trigger 10 corrections via test queries. Hit metrics endpoint — confirm counts match. Confirm resolved vs exhausted ratio. 5+ tests.

---

### Phase AI-6: Multi-Agent + Harness + L3 Skills (9 days)

> **Sprint deliverable:** Monolithic 11-tool agent split into 3 domain specialists + router. Full BaseAgentService harness (9 hook points, confidence extraction, context budgets). Progressive L3 skill loading with token budgets and priority gating. Token usage drops ~40%. Tool selection accuracy improves.
> **Depends on:** Phase AI-3 (memory — shared across agents)

#### AI-6.1 BaseAgentService Shared Pipeline (Full Harness)
**What:** Extract shared agent pipeline logic from `AgentService` into `app/core/agents/base.py` — full `BaseAgentService` harness adapted from email-hub's `app/ai/agents/base.py` (468 lines, 9 hook points). Handles: tier routing → skill detection → memory recall → prompt building → agent execution → post-processing → confidence extraction → self-correction → memory bridge → response construction.
**Why:** Email-hub's `BaseAgentService` eliminates ~80% code duplication across 9 agents. Each domain agent needs the same pipeline but different tools, prompts, and QA checks. The harness pattern provides 9 extensibility hook points that subclasses override while the base handles the battle-tested flow.
**Implementation:**
- Create `app/core/agents/base.py` with **9 hook points** (from email-hub):
  1. `build_system_prompt(relevant_skills) -> str` — **MUST override**. Agent-specific system prompt with L3 skills injected.
  2. `detect_relevant_skills(prompt) -> list[str]` — Optional. Keyword → L3 skill file detection (see AI-6.5).
  3. `_build_user_message(request) -> str` — **MUST override**. Transform request → user message for LLM.
  4. `_post_process(content) -> str` — Optional. Agent-specific output validation (default: strip markdown fences).
  5. `_run_qa(response) -> list[ValidationIssue]` — Optional. Agent-specific QA checks (default: route/stop existence, language match).
  6. `_should_run_qa() -> bool` — Optional. Whether to run QA at all (default: `self.run_qa_default`).
  7. `_get_model_tier(prompt) -> str` — Optional. Per-request tier override (default: class-level `self.model_tier`).
  8. `_build_response(content, model, confidence, warnings) -> ChatCompletionResponse` — Formats OpenAI-compatible response.
  9. `_persist_episode(prompt, response, result)` — Memory bridge callback (fire-and-forget, from AI-3.3).
- **Class-level config** per agent: `agent_name`, `model_tier`, `max_tokens`, `run_qa_default`, `context_budget: ContextBudget`
- **Confidence extraction** (from email-hub): append `CONFIDENCE_INSTRUCTION` to system prompt, LLM responds with `<!-- CONFIDENCE: X.XX -->`, base extracts via regex, passes to response builder and memory bridge.
- **Context budget** (from email-hub's `context_budget.py`): per-agent token limits for system prompt, skills, memories, user message. Prevents context overflow.
- **Pipeline flow** (9 phases):
  ```
  Phase 1: _get_model_tier() → resolve model
  Phase 2: detect_relevant_skills() → load_skills_within_budget()
  Phase 3: memory_service.recall() → format memories
  Phase 4: build_system_prompt() + skills + memories + CONFIDENCE_INSTRUCTION
  Phase 5: _build_user_message() → agent.run()
  Phase 6: _post_process() + extract_confidence()
  Phase 7: self-correction loop (if _should_run_qa() and enabled)
  Phase 8: _persist_episode() via memory bridge (fire-and-forget)
  Phase 9: _build_response()
  ```
- Refactor existing `AgentService` to extend `BaseAgentService`
**Verify:** Existing `AgentService` works identically after refactor. All 964 unit tests pass. No behavioral change — pure refactor. Each hook point tested independently.

#### AI-6.2 Domain-Specific Agents
**What:** Create 3 domain agents: `TransitAgent` (5 transit tools), `KnowledgeAgent` (1 RAG tool), `VaultAgent` (4 obsidian tools). Each extends `BaseAgentService` with domain-focused system prompt and tools.
**Why:** The unified agent loads all 11 tool docstrings (~3000 tokens) for every query. A transit query doesn't need vault tools in context. Domain-specific prompts can be shorter and more focused, improving tool selection accuracy.
**Implementation:**
- Create `app/core/agents/agents/transit.py`:
  - System prompt: Latvian transit glossary, GTFS data interpretation, delay analysis rules
  - Tools: query_bus_status, get_route_schedule, search_stops, get_adherence_report, check_driver_availability
- Create `app/core/agents/agents/knowledge.py`:
  - System prompt: Citation rules, document grounding, "I don't know" instruction, response synthesis
  - Tools: search_knowledge_base
- Create `app/core/agents/agents/vault.py`:
  - System prompt: Note organization, frontmatter conventions, safe deletion (require confirm)
  - Tools: obsidian_query_vault, obsidian_manage_notes, obsidian_manage_folders, obsidian_bulk_operations
- Keep existing `AgentService` as `UnifiedAgent` fallback (all 11 tools)
**Verify:** Each agent responds correctly to domain-specific queries. Transit agent can't access vault tools. Knowledge agent enforces citations. 15+ tests per agent.

#### AI-6.3 Agent Router
**What:** Create `app/core/agents/router.py` — routes incoming queries to the appropriate domain agent using keyword signals. Cross-domain or unclassifiable queries fall back to `UnifiedAgent`.
**Why:** Without routing, all queries hit the unified agent. With routing, domain-specific agents get focused context, reducing token waste and improving tool selection. The router is heuristic (zero LLM latency) like the existing tier classifier.
**Implementation:**
- Create `app/core/agents/router.py`:
  ```python
  class AgentRouter:
      TRANSIT_SIGNALS = {"maršrut", "pietura", "autobus", "kavē", "route", "stop",
                         "delay", "bus", "schedule", "departure", "reiss", "grafik"}
      KNOWLEDGE_SIGNALS = {"dokument", "noteikum", "procedūr", "SOP", "regul",
                           "policy", "document", "procedure"}
      VAULT_SIGNALS = {"vault", "obsidian", "piezīm", "note", "folder", "tag"}

      def route(self, prompt: str) -> AgentDomain:
          # Score each domain. If top score == 0 or tie → UNIFIED
  ```
- `app/core/agents/routes.py` — `POST /v1/chat/completions` uses router to select agent
- Add `AGENT__MULTI_AGENT_ENABLED: bool = False` config flag (default off, safe rollout)
- Structured logging: `agent.router.decision {domain, scores, prompt_hash}`
**Verify:** "Kuri maršruti kavējas?" → TransitAgent. "Kāda ir procedūra?" → KnowledgeAgent. "Show my vault notes" → VaultAgent. "What routes serve the hospitals mentioned in the SOP?" → UnifiedAgent (cross-domain). 20+ tests.

#### AI-6.4 Progressive Skill System (L3 Skills)
**What:** Implement email-hub's progressive skill disclosure pattern: per-agent L3 skill files loaded on-demand based on query keywords, within per-agent token budgets. Replaces current flat skill injection (all active skills → every request).
**Why:** Email-hub's skill system ("teach on demand") keeps context lean — agents only learn about patterns they'll actually use. Each L3 file has `token_cost` and `priority` front matter. Priority 3 (supplementary) skills skipped when capacity < 70%, priority 2 (standard) when < 30%. VTV's flat system injects all active skills regardless of relevance, wasting context tokens on irrelevant knowledge.
**Implementation:**
- Create `app/core/agents/context_budget.py`:
  - `ContextBudget` frozen dataclass: `system_prompt_max=3000`, `skill_docs_max=2000`, `memory_max=1500`, `user_message_max=3000`, `total_max=10000`
  - `AGENT_BUDGETS` dict: transit=2500 skills, knowledge=2000, vault=1500, unified=3000
- Create `app/core/agents/skill_loader.py`:
  - `SkillMeta` dataclass: `token_cost`, `priority` (1/2/3), `version`
  - `parse_skill_file(path) -> tuple[SkillMeta, str]` — parse YAML front matter + body
  - `load_skills_within_budget(skill_names, budget, skill_dir) -> str` — load L3 files respecting budget
  - Priority gating: P1 always, P2 skipped when <30% capacity, P3 when <70% capacity
- Create L3 skill files:
  - `app/core/agents/skills/transit/` — `delay_analysis.md` (P2, 450 tokens), `schedule_interpretation.md` (P2, 400), `route_comparison.md` (P3, 350), `driver_availability.md` (P3, 300), `adherence_reporting.md` (P3, 350)
  - `app/core/agents/skills/knowledge/` — `sop_retrieval.md` (P1, 500), `regulation_interpretation.md` (P2, 450), `shift_handover.md` (P3, 300), `incident_response.md` (P2, 400)
  - `app/core/agents/skills/vault/` — `search_patterns.md` (P2, 300), `bulk_operations.md` (P3, 250), `folder_organization.md` (P3, 250)
- Each agent's `detect_relevant_skills()` uses keyword matching (see AI-6.2)
- Backwards compat: existing flat skill system (`app/skills/`) still works alongside L3 skills
**Verify:** Transit query about delays loads `delay_analysis.md` but not `driver_availability.md`. Knowledge query about SOPs loads `sop_retrieval.md` (P1, always). Hit budget limit — confirm P3 skills skipped first. Compare token usage before/after — expect ~30% reduction for domain agents. 15+ tests.

#### AI-6.5 Lightweight AgentResult Protocol
**What:** Implement `AgentResult` frozen dataclass for structured agent responses — content, confidence, warnings, tools used, domain. Enables confidence-based routing and audit trails.
**Why:** Simplified version of email-hub's `AgentHandoff`. VTV doesn't need the full protocol (no agent chaining), but confidence scoring enables "route low-confidence to better model" and warnings enable transparent data quality communication.
**Implementation:**
- Add to `app/core/agents/base.py`:
  ```python
  @dataclass(frozen=True)
  class AgentResult:
      content: str
      confidence: float | None       # 0.0-1.0 (from reranker score or tool success rate)
      warnings: tuple[str, ...]      # Stale data, partial results, etc.
      tools_used: tuple[str, ...]    # For episodic memory
      domain: str                    # transit | knowledge | vault | unified
  ```
- `BaseAgentService.chat()` returns `AgentResult` internally, converts to `ChatCompletionResponse` at route level
- If `confidence < 0.3` and complex tier available, re-run with complex model
**Verify:** Transit query with fresh data → confidence > 0.7. Knowledge query with no relevant docs → confidence < 0.3. Low-confidence query re-routed to complex model. 8+ tests.

---

### Phase AI-7: Evaluation Framework (5 days)

> **Sprint deliverable:** Synthetic test cases per domain, LLM judges for quality assessment, regression baselines. `make eval` runs full suite. `make eval-judge` assesses traces.
> **Depends on:** Phases AI-1 through AI-6 (evaluates the full system)

#### AI-7.1 Synthetic Test Cases
**What:** Create YAML test case files for each agent domain: 15 transit cases, 10 knowledge cases, 5 vault cases. Each case specifies: prompt, expected tools, language, and 5 quality criteria.
**Why:** Without test cases, agent quality is unmeasured. Model updates, prompt changes, or RAG tweaks can silently degrade quality. Email-hub's eval framework caught 21/45 criteria with >20% flip rate during model changes.
**Implementation:**
- Create `app/core/agents/evals/cases/transit.yaml` — 15 cases covering:
  - Simple status queries (LV + EN)
  - Diacriticless Latvian input
  - Cross-tool queries (bus status + stop search)
  - Non-existent route handling
  - Schedule queries with date filtering
  - Adherence report interpretation
  - Multi-route comparison
- Create `app/core/agents/evals/cases/knowledge.yaml` — 10 cases covering:
  - SOP retrieval with citation
  - "No relevant docs" honesty
  - Regulation interpretation
  - Cross-lingual queries (LV question, EN document)
  - Temporal relevance (recent vs old docs)
- Create `app/core/agents/evals/cases/vault.yaml` — 5 cases covering:
  - Note search, creation, safe deletion
**Verify:** Cases load without errors. Each case has all required fields. Cover all agent tools across the suite.

#### AI-7.2 Eval Runner + Trace Collection
**What:** Create `app/core/agents/evals/runner.py` — CLI that runs synthetic test cases against the live agent, collects traces (input, output, tool calls, timing, errors) as JSONL.
**Why:** Traces are the foundation for both automated judging and manual review. JSONL format enables streaming, grep, and analysis scripts.
**Implementation:**
- Create `app/core/agents/evals/runner.py`:
  ```python
  class EvalRunner:
      async def run_suite(self, suite: str) -> list[EvalTrace]:
          cases = self._load_cases(suite)
          traces = []
          for case in cases:
              trace = await self._run_case(case)  # Actually calls agent
              traces.append(trace)
          self._write_traces(traces, output_path)
          return traces
  ```
- `EvalTrace` dataclass: case_id, prompt, response, tool_calls, tool_results, latency_ms, error, timestamp
- Output: `evals/traces/{suite}_{timestamp}.jsonl`
- CLI: `python -m app.core.agents.evals.runner --suite transit`
- Add `make eval` Makefile target
**Verify:** `make eval` runs 30 test cases, produces JSONL traces, reports pass/fail summary.

#### AI-7.3 LLM Judge + Quality Criteria
**What:** Create `app/core/agents/evals/judge.py` — LLM-based judge that evaluates traces against 5 domain-specific quality criteria. Binary pass/fail per criterion with one-line reasoning.
**Why:** Human review doesn't scale. LLM judges enable automated quality gates. Email-hub calibrates judges to TPR >= 0.85 / TNR >= 0.80 vs human labels.
**Implementation:**
- Create `app/core/agents/evals/judge.py`:
  - Transit criteria: factual_accuracy, language_correctness, actionability, data_freshness, completeness
  - Knowledge criteria: factual_accuracy, citation_quality, grounding, language_correctness, honesty
  - Vault criteria: operation_correctness, safety, completeness, language_correctness, formatting
- Judge prompt includes: query, tool calls, tool results, agent response, criteria definitions
- Output: `JudgeVerdict` per case with per-criterion pass/fail + reasoning
- CLI: `python -m app.core.agents.evals.judge_runner --traces evals/traces/latest/`
- Add `make eval-judge` Makefile target
**Verify:** Run judge on 30 traces. Review 10 verdicts manually — judge should agree with human assessment on 8+/10. Identify any calibration issues.

#### AI-7.4 Regression Baselines
**What:** Generate initial regression baselines from first eval run. Future runs compare against baselines — flag per-criterion regressions exceeding 3 percentage points.
**Why:** Quality regressions from model updates, prompt changes, or RAG modifications must be caught before deployment. A 3pp tolerance prevents false alarms from noise.
**Implementation:**
- Create `app/core/agents/evals/regression.py`:
  - `generate_baseline(verdicts) -> BaselineReport` — per-criterion pass rates
  - `check_regression(current, baseline, tolerance=0.03) -> list[Regression]`
  - Baseline stored as JSON: `evals/baselines/{suite}_baseline.json`
- Add `make eval-check` — runs eval + judge + regression check (CI-friendly)
- Add `--update-baseline` flag to regenerate baselines after intentional changes
**Verify:** Generate baseline. Deliberately degrade a prompt. Run eval-check — confirm regression detected and reported. 8+ tests.

---

### Additional Agent Improvements (not phased)

These items from the original roadmap are standalone improvements that don't fit neatly into the AI phases above but remain planned.

- [ ] **Circuit Breaker** — Wrap LLM providers with circuit breaker that tracks failure rates, auto-switches to fallback after N consecutive failures (currently only FallbackModel exists, no failure-rate tracking). Add per-provider health metrics. Independent of agent intelligence phases.

- [ ] **Prompt Injection Hardening** — Current detection is log-only (3 regex patterns). Add blocking mode for high-confidence injections, output validation to prevent data exfiltration via crafted responses. Can be done anytime.

- [ ] **Enhanced Citation Quality** — Track section headers during chunking for page/section-level citations instead of generic `chunk {index}`. Store heading hierarchy in chunk metadata. *Partially addressed by AI-4.2 (heading_path on chunks) — this item covers the remaining agent-side formatting (rendering heading breadcrumbs in response citations).*

- [ ] **RAG Eval Pipeline** — Measure faithfulness (is answer grounded in retrieved chunks?), relevance (right chunks retrieved?), completeness (all relevant info surfaced?). Generate synthetic QA pairs from existing documents for retrieval testing. *Separate from AI-7's agent eval — this evaluates retrieval quality independent of agent response quality.*

---

## Planned Features

### Knowledge Base

- [ ] **RAG Knowledge Base Improvements** - Expand document type support (HTML, PPTX — Excel/CSV done), add Latvian lemmatizer, parent-child chunking, temporal metadata, auto-domain tagging, cross-lingual search, document versioning, search feedback loop, and knowledge graph overlay. ~12-14 days remaining effort, ~$0.65/month added cost.
  - Plan: [docs/PLANNING/rag-improvements.md](PLANNING/rag-improvements.md)

- [ ] **SOP & File Automation** - Automated document ingestion (folder watcher, email monitor, web scraper, GTFS sync) and LLM-powered SOP generation (incident-to-SOP pipeline, regulation change detection, shift handover notes, template scaffolding). ~13 days total effort, ~$4.50/month LLM cost, saves ~47 hrs/month human time.
  - Plan: [docs/PLANNING/sop-file-automation.md](PLANNING/sop-file-automation.md)

### CMS Features

- [ ] **Route Shape Polylines** - Display route geometry on map from GTFS `shapes.txt`. Requires polyline layer in react-leaflet, shape import during GTFS ZIP processing, and route-shape association. Enhances route visualization significantly.

- [x] ~~**NeTEx/SIRI Compliance Exports**~~ — Moved to Completed (2026-03-07)

### Fleet Management & Vehicle Tracking (LocTracker-inspired)

- [x] **Phase 1A: Device Management + Telemetry Ingestion** — `app/fleet/` vertical slice: TrackedDevice CRUD (5 endpoints + RBAC), Traccar webhook bridge with OBD-II parsing, `vehicle_positions` hypertable extended with `source` + `obd_data` columns, Traccar Docker sidecar (`--profile fleet`). 17 unit tests. (commit 10ff86c, 2026-03-08)
  - Plan: [.agents/plans/fleet-core-1a.md](../.agents/plans/fleet-core-1a.md)

- [x] **Phase 1B: Geofencing (Backend)** — `app/geofences/` vertical slice: PostGIS POLYGON zones with GIST indexing, 8 REST endpoints (CRUD + event queries + dwell reports), background evaluator (30s cycle, Redis state, ST_Contains), entry/exit/dwell detection with alerts integration, 2 tables (geofences + geofence_events), 23 unit tests. (2026-03-08)
  - Plan: [.agents/plans/geofences-phase-1b.md](../.agents/plans/geofences-phase-1b.md)

- [x] **Phase 1C: CMS Fleet Pages** — 4 frontend pages: Fleet Devices CRUD (`/fleet` — table, filters, form, detail, delete), Fleet Map (`/fleet/map` — Leaflet with device markers, 15s auto-refresh, device sidebar), Telemetry Dashboard (`/fleet/telemetry` — 6 Recharts gauges: speed, RPM, fuel, coolant, engine load, battery), Geofences (`/geofences` — split table+polygon map, click-to-place editor, event history tab, dwell reports). ~160 i18n keys per locale, RBAC, responsive layouts. (2026-03-08)
  - Plan: [.agents/plans/fleet-cms-phase-1c.md](../.agents/plans/fleet-cms-phase-1c.md)

- [ ] **Phase 2: Fuel + Analytics + LocShare** — Fuel monitoring (refueling/drain detection from OBD), fuel consumption analytics, fleet distance/drive time reports, idle time detection, LocPoints dwell time, LocShare (JWT expiring public tracking links), PDF/CSV report export, speed/device-offline alerts. CMS: fuel dashboard, analytics pages, LocShare management. ~27 days effort.
  - Plan: [docs/PLANNING/fleet-management-tracking.md](PLANNING/fleet-management-tracking.md) (Phase 2)

- [ ] **Phase 3: Tachograph + Driving Hours Compliance** — `app/tachograph/` vertical slice: remote DDD file download (Teltonika Web Tacho + flespi), DDD binary parser, EU 561/2006 driving hours calculator (daily 9/10h, weekly 56h, biweekly 90h, monthly 160h), compliance status endpoints, infringement detection, driving hours alerts. CMS: compliance dashboard, activity timeline, DDD management, violation reports. ~36 days effort.
  - Plan: [docs/PLANNING/fleet-management-tracking.md](PLANNING/fleet-management-tracking.md) (Phase 3)

- [ ] **Phase 4: Routing + Maps Fallback** — OSRM self-hosted (Latvia OSM extract) as Docker sidecar, HERE Fleet Telematics API fallback, route optimization for service vehicles. CMS: route planning UI with map waypoints. ~15 days effort.
  - Plan: [docs/PLANNING/fleet-management-tracking.md](PLANNING/fleet-management-tracking.md) (Phase 4)

- [ ] **Phase 5: Driver Mobile App + Messaging** — `app/messaging/` vertical slice (dispatcher↔driver messaging, task assignment), React Native mobile app (live map, alerts, messaging, tasks), push notifications (FCM/APNs). ~28 days effort.
  - Plan: [docs/PLANNING/fleet-management-tracking.md](PLANNING/fleet-management-tracking.md) (Phase 5)

### Full Latvia Transit Platform

- [ ] **Phase 1: Foundation** - Database extensions (TimescaleDB), GTFS static importer for all Latvia, CKAN data.gov.lv bridge for immediate ATD data, full-screen transit map in CMS. ~3 weeks remaining effort. *Largely done: GTFS import, Redis cache, REST endpoints, GTFS-RT poller, PostGIS spatial queries (GeoAlchemy2 + GIST index), WebSocket live streaming (backend Pub/Sub + frontend real-time push with HTTP fallback), persistent GTFS storage (DB-backed static data for agent tools), and TimescaleDB historical position storage (hypertable, compression, 90-day retention, vehicle history + delay trend endpoints) are complete. Remaining: multi-city GTFS, CKAN bridge, full-screen map.*
  - Plan: [docs/PLANNING/Implementation-Plan.md](PLANNING/Implementation-Plan.md) (Phase 1)

- [ ] **Phase 2: Full Latvia Coverage** - Additional city feeds (Daugavpils, Jurmala, Pieriga), train positions via WebSocket, Valhalla route matching, ETA calculator, adaptive polling, circuit breakers, TimescaleDB compression, GTFS-RT publisher. ~4 weeks effort.
  - Plan: [docs/PLANNING/Implementation-Plan.md](PLANNING/Implementation-Plan.md) (Phase 2)

- [ ] **Phase 3: Intercity Gap-Fill** - OwnTracks integration for phone-based tracking, Traccar integration for hardware GPS (Teltonika FMB920), OpenTripPlanner for journey planning, shareable tracking links, historical analytics. ~8 weeks effort.
  - Plan: [docs/PLANNING/Implementation-Plan.md](PLANNING/Implementation-Plan.md) (Phase 3)

- [ ] **Phase 4: Intelligence** - ML-based ETA prediction (TimescaleDB history), weather-adjusted delays, passenger load prediction (e-ticket data), congestion factors, anomaly detection, public developer API. Ongoing.
  - Plan: [docs/PLANNING/Implementation-Plan.md](PLANNING/Implementation-Plan.md) (Phase 4)

## Completed

### Backend Features

- [x] **Schedule Management** - 23 endpoints: agencies, routes, calendars, trips CRUD. GTFS ZIP import with merge/upsert strategy, validation, stop times. Full vertical slice with async SQLAlchemy, Pydantic schemas, structured logging. (commit 37d5c70)
  - Plan: [.agents/plans/schedule-management.md](../.agents/plans/schedule-management.md)

- [x] **Multi-Feed GTFS-RT** - Background poller for multiple transit feeds, Redis caching for sub-ms reads, vehicle position enrichment with static GTFS data. Configurable via `TRANSIT_FEEDS_JSON`. (commit 37d5c70)

- [x] **DMS Backend** - Document management system: file persistence at `data/documents/{id}/`, metadata editing (PATCH), file download, content preview, domain listing, Excel/CSV extraction via openpyxl. 4 new API endpoints, 3 new Document model columns (title, description, file_path). 10 new unit tests.
  - Plan: [.agents/plans/dms-backend.md](../.agents/plans/dms-backend.md)

- [x] **Agent Document Citations** - Agent system prompt includes CITATION RULES for clickable document links (`[title](/{locale}/documents/{id})`), knowledge search tool passes `document_id` through results. 7 unit tests. (commit bf0889f)
  - Plan: [.agents/plans/agent-document-citations.md](../.agents/plans/agent-document-citations.md)

- [x] **RAG Knowledge Base** - Hybrid search (pgvector + fulltext + RRF), multi-format ingestion (PDF, DOCX, email, image OCR, text), configurable embeddings (OpenAI/Jina/local), cross-encoder reranking, agent tool integration. 20 unit tests. (commit 8544237)

- [x] **Latvian Language Support** - Rewritten agent system prompt with Latvian language rules, 30+ transit term glossary, diacriticless input understanding. LLM upgraded to Claude Sonnet 4.5, embeddings switched to Jina v3 for explicit Latvian support. Frontend i18n diacritics fixed. (commit 17ce1a9)
  - Research: [docs/PLANNING/latvian-language-and-model-research.md](PLANNING/latvian-language-and-model-research.md)

- [x] **Stop Management CRUD** - Backend vertical slice with SQLAlchemy models, Haversine proximity search (plain Float columns), Pydantic schemas, async repository, 6 REST endpoints. (commit f88efc5)

- [x] **AI Chat Page** - CMS chat page with real LLM integration via agent service /v1/chat/completions endpoint, streaming SSE responses, bilingual i18n. (commit 3dad10b)

- [x] **Obsidian Vault Tools (4)** - query_vault (5 actions), manage_notes (5 actions), manage_folders (4 actions), bulk_operations (5 actions with dry_run). 68 unit tests. (commit 0bc02c3)

- [x] **Transit Tools (5)** - query_bus_status, get_route_schedule, search_stops, get_adherence_report, check_driver_availability. 104 unit tests. (commits 3472688-b25885f)

- [x] **Transit REST API** - GET /api/v1/transit/vehicles for frontend map polling, enriches GTFS-RT with static data. 9 unit tests. (commit 032e617)

- [x] **DDoS Defense** - nginx rate limiting, connection limits, security headers, slowapi per-IP limits, body size middleware, query quota tracker. (commit 643b23e)

- [x] **JWT Auth + RBAC** - 7 endpoints: login, logout, refresh, seed, reset-password, delete-user. bcrypt with timing attack prevention, Redis brute-force tracking (5 attempts = 15min lockout), token revocation denylist, refresh token single-use, 4-role RBAC (admin/editor/dispatcher/viewer). 52 unit tests. (commit 4c34c33)

- [x] **Driver Management** - 5 endpoints: CRUD + availability. HR profiles, shift/availability tracking, agent tool integration. 27 unit tests.

- [x] **Event Management** - 5 endpoints: CRUD + date range filter. Dashboard calendar integration, operational event tracking. 18 unit tests.

- [x] **Agent Skills System** - 7 endpoints: CRUD + activation/deactivation + agent context injection. Reusable knowledge packages that dynamically extend agent capabilities. 11th agent tool. 23 unit tests. (commit ed9662f)

- [x] **PostGIS Migration** - Migrated stop proximity search from Haversine formula to PostGIS `ST_DWithin` with GeoAlchemy2, GIST-indexed Geometry(Point, 4326) column, database trigger for lat/lon→geom sync. Sub-ms spatial queries. (commit f7070b7, 2026-02-26)
  - Plan: [.agents/plans/postgis-migration.md](../.agents/plans/postgis-migration.md)

- [x] **DMS Enhancements** - Scanned PDF OCR detection, LLM auto-tagging on upload, tag CRUD endpoints (create/list/delete tags, bulk tag documents). (commit 65697a8, 2026-02-26)
  - Plan: [.agents/plans/dms-enhancements.md](../.agents/plans/dms-enhancements.md)

- [x] **WebSocket Live Streaming (Backend)** - Real-time vehicle position push via WebSocket (`/ws/transit/vehicles`). Redis Pub/Sub fan-out from GTFS-RT pollers to per-client connections. Per-client feed/route filtering via subscribe messages. JWT auth via query parameter. ConnectionManager singleton, background subscriber task. nginx WebSocket proxy with 3600s timeouts and 10/IP connection limit. 30 new unit tests (ws_manager, ws_routes, ws_subscriber, poller). (commit cdb80ca, 2026-02-27)
  - Plan: [.agents/plans/be-websocket-live-streaming.md](../.agents/plans/be-websocket-live-streaming.md)

- [x] **WebSocket Live Streaming (Frontend)** - Replaced HTTP polling with WebSocket real-time push (~100ms latency) for vehicle positions. Automatic fallback to SWR HTTP polling (10s) after 3 failed reconnects. Periodic 60s retry to switch back to WebSocket. Route filtering via subscribe message. Connection status badge (Live/Polling/Connecting) on map. JWT auth via query parameter with 60s cached token. (commit 5bf06ca, 2026-02-27)
  - Plan: [.agents/plans/fe-websocket-vehicle-positions.md](../.agents/plans/fe-websocket-vehicle-positions.md)

- [x] **Vehicle Management** - Fleet CRUD (8 endpoints), maintenance tracking with mileage/date side-effects, driver assignment with cross-feature conflict detection, database CHECK constraints, fleet_number→GTFS-RT vehicle_id linking. 30 unit tests, code review with 6/10 issues fixed. (2026-02-27)
  - Plan: [.agents/plans/vehicle-management.md](../.agents/plans/vehicle-management.md)
  - Review: [.agents/code-reviews/vehicles-review.md](../.agents/code-reviews/vehicles-review.md)

- [x] **Multi-Tier Model Routing** — Heuristic prompt classifier in `routing.py` routes simple lookups to fast tier, standard queries to default, complex analysis to premium. `resolve_tier_model()` in `config.py` resolves tier-specific models. Integrated into `AgentService.chat()`. 6 env vars (`LLM_FAST_*`/`LLM_STANDARD_*`/`LLM_COMPLEX_*`). 37 new tests. (2026-03-09)
  - Plan: [.agents/plans/agent-model-routing.md](../.agents/plans/agent-model-routing.md)

### CMS Frontend Pages

- [x] **Dashboard** - 4 metric cards (real API via SWR: vehicles + routes, 30s polling), multi-view calendar (week/month/3-month/year, real events via `useCalendarEvents` SWR hook), drag-and-drop driver scheduling (driver roster + 5 action types), live timeline, resizable panels. (commit 852ee95, updated 2026-02-25)

- [x] **Routes Page** - Real API CRUD against backend `/api/v1/schedules/routes`, server pagination, search, type/agency/status filters, route detail sheet, route form, Leaflet map with live GTFS-RT vehicle positions (WebSocket real-time push with HTTP polling fallback), connection status badge, resizable split panels, mobile tab layout. 142 i18n keys per locale.

- [x] **Stops Page** - Real API CRUD against backend `/api/v1/stops`, Leaflet map with draggable markers and terminus icons, direction display, location_type filtering, GTFS ID copy-to-clipboard, proximity search, mobile tab layout.

- [x] **Schedules Page** - Real API CRUD against backend `/api/v1/schedules` (22 endpoints). Three tabs: Calendars (service ID, operating days, date ranges, exceptions), Trips (route/calendar/direction filters, stop times), Import (GTFS ZIP drag-and-drop upload, merge/upsert, validation with error/warning display).

- [x] **Documents Page** - Real API against backend `/api/v1/knowledge`. Upload form (drag-and-drop, react-dropzone, 10 file types), filterable table (search, type, domain, status, language), document detail with lazy-loaded chunk viewer, download/delete. ~70 i18n keys per locale.
  - Plan: [.agents/plans/dms-frontend.md](../.agents/plans/dms-frontend.md)

- [x] **Login Page** - Auth.js v5 credentials provider, DB-backed via `POST /api/v1/auth/login`, brute-force protection (5 attempts = 15min lockout).

- [x] **Drivers Page** - Real API CRUD against backend `/api/v1/drivers`. Driver profiles, shift management, availability tracking, search and filters. 10 e2e tests.

- [x] **GTFS Page** - Dedicated GTFS data management page at `/[locale]/gtfs` with 3 tabs: Data Overview (5 stat cards — agencies, routes, calendars, trips, stops + GTFS-RT feed status), Import (reuses GTFSImport from Schedules), Export (agency filter + download). Semantic tokens, full i18n (30 keys per locale). Backend data from `/api/v1/schedules` + `/api/v1/transit/feeds`.

- [x] **Fleet Devices Page** - Fleet device CRUD at `/[locale]/fleet`. Table with status badges, protocol/status/vehicle-link filters, IMEI validation, device detail with OBD-II telemetry tab. Backend: `/api/v1/fleet/devices`. (2026-03-08)

- [x] **Fleet Map Page** - Live fleet map at `/[locale]/fleet/map`. Leaflet with device markers (color by source, size by selection), 15s auto-refresh, device list sidebar, connection status. Backend: `/api/v1/fleet/positions`. (2026-03-08)

- [x] **Telemetry Dashboard Page** - OBD-II telemetry at `/[locale]/fleet/telemetry`. 6 Recharts gauges (speed, RPM, fuel level, coolant temp, engine load, battery voltage), device selector, 1h/6h/24h time range. Backend: `/api/v1/fleet/history`. (2026-03-08)

- [x] **Geofences Page** - Geofence management at `/[locale]/geofences`. Desktop: split table+polygon map layout. Click-to-place polygon editor in form. Zone type colors, severity badges, event history tab, dwell time reports. Backend: `/api/v1/geofences` (8 endpoints). (2026-03-08)
  - Plan: [.agents/plans/fleet-cms-phase-1c.md](../.agents/plans/fleet-cms-phase-1c.md)

- [x] **Mobile Responsive** - All pages: tab-based Table/Map switching, collapsible filter Sheet, hamburger sidebar. (commit 032e617)

- [x] **Design Tokens** - Three-tier tokens (primitive, semantic, component), active state styling. (commit 801640d)

- [x] **Performance Fixes** - Self-hosted fonts, dashboard converted to RSC, build optimizations. (commit fcfea8a)

### Infrastructure & Tooling

- [x] **Playwright E2E Testing** - 81 tests across 10 files (dashboard, routes, stops, schedules, documents, drivers, navigation, login, smoke). Auto-detection of changed features via `detect-changed.sh`. Auth setup with session reuse. `make e2e` / `/e2e` slash command.

- [x] **Slash Commands (25)** - 8 backend + 7 frontend + 9 cross-cutting + 1 testing. Full pipeline: prime -> planning -> execute -> validate -> commit.

- [x] **Makefile** - Unified workflow: `make dev` (full stack), `make check` (lint+types+tests), `make e2e` (auto-detect), `make docker` (full deploy). 18 targets.

- [x] **Docker Compose** - PostgreSQL (pgvector/pgvector:pg18), Redis, auto-migration, FastAPI app, Next.js CMS, nginx reverse proxy. Production overlay with security headers. `make docker` / `make docker-prod`.

- [x] **Codebase Audit** - 120 findings documented in `.agents/code-reviews/AUDIT-SUMMARY.md`. (2026-02-21)

- [x] **Documentation Cleanup** - 74 redundant CLAUDE.md files removed, 5 substantive files retained. (2026-02-21)
