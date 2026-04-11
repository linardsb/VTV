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
Testing           ████████████████████░░░░  90%  (1128 unit tests, 106 security tests, 81 e2e tests, CI pipeline live with security gates)
Infrastructure    ██████████████████████░░  97%  (Docker, nginx+Brotli, Gunicorn multi-worker, Redis rate limiting, Makefile, 25 slash commands, CI/CD, 6 security audits, SDLC security framework, context-triggered security SDC)
Latvia Platform   ████████░░░░░░░░░░░░░░░  35%  (Riga GTFS + PostGIS + WebSocket + multi-feed GTFS-RT + TimescaleDB historical storage, no multi-city yet)
Agent Intelligence ████████████████░░░░░░░  80%  (Multi-tier routing done. AI-1.1 reranking done. AI-1.2 date filtering done. AI-1.3 temporal boost + RRF tuning done. AI-2.1 query router done. AI-2.2 HyDE done. AI-2.3 embedding cache done. AI-3.1 memory vertical slice done. AI-3.2 memory lifecycle done. AI-3.3 memory bridge done. AI-3.4 memory agent integration done. AI-4.1 semantic chunker done. AI-4.2 parent-child chunk model done. AI-4.3 parent-child retrieval + context expansion done. AI-4.4 re-chunk migration done. AI-5.1 bounded self-correction loop done (standard tier). AI-5.2 extended QA checks with severity tiers done. AI-5.3 correction metrics + admin endpoint done. AI-6.1 BaseAgentService harness done (9 hook points, pure refactor). AI-6.2 domain-specific agents done (TransitAgent + KnowledgeAgent + VaultAgent + registry + `agent` selector). AI-6.3 heuristic auto-router done (keyword signals + flag-gated rollout). AI-6.4 progressive L3 skill system done (12 in-repo skill packs, priority-gated loader, per-agent budgets). AI-6.5 AgentResult + confidence re-route gate done (single retry to complex tier on low confidence). AI-7.1 synthetic eval cases done (30 cases + fail-open YAML loader). AI-7.2 eval runner done (`EvalRunner` CLI + `EvalTrace` JSONL writer + `chat_with_trace()` on `BaseAgentService`). Remaining: AI-7.3 LLM judges, AI-7.4 regression baselines)
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

#### AI-2.3 Embedding Cache ✅
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

#### AI-3.1 Memory Vertical Slice — Models + Repository + Service + Routes ✅
**What:** Create `app/memory/` vertical slice with `MemoryEntry` SQLAlchemy model backed by pgvector. 4 memory types: procedural (learned patterns), episodic (session logs), semantic (durable facts), query_pattern (frequent queries). Includes full service layer, 5 REST endpoints with RBAC, and 29 unit tests.
**Status:** Implemented 2026-04-09. Plan: `.agents/plans/ai-3.1-memory-vertical-slice.md`. 13 files created, 29 tests passing. Merged AI-3.1 + AI-3.2 schemas/routes/service into a single slice.
**Implementation:**
- `app/memory/models.py` — `MemoryEntry(Base, TimestampMixin)` with pgvector `Vector(1024)`, JSONB metadata, decay weight, evergreen flag
- `app/memory/repository.py` — store, get, recall (cosine similarity), get_by_type, increment_recalled_count, delete_decayed
- `app/memory/service.py` — business logic orchestration with structured logging
- `app/memory/routes.py` — 5 endpoints: POST store, GET by ID, POST recall, GET by type, DELETE decayed
- `app/memory/schemas.py` — `MemoryEntryCreate`, `MemoryRecallRequest`, `MemoryEntryResponse`, `MemoryRecallResponse` with `Literal[...]` types
- `alembic/versions/a1b2c3d4e5f6_create_memory_entries.py` — table + ivfflat index
**Verify:** 29 unit tests (14 repository + 8 service + 7 route). All type checkers pass (0 new mypy/pyright errors). 106 security tests pass.

#### AI-3.2 Memory Service — Store, Recall, Compact ✅
**Status:** Implemented 2026-04-09. Plan: `.agents/plans/ai-3.2-memory-service-lifecycle.md`.
**What:** Full memory lifecycle management added to existing `app/memory/` vertical slice: embed-on-store (auto-generates embeddings via `EmbeddingProvider` singleton), duplicate detection (cosine > 0.95 = skip), text-based recall (`POST /recall/query`), time-based decay, compaction (merge similar entries with cosine > 0.92), and episodic-to-procedural auto-promotion after 3+ recalls.
**Implementation:**
- `app/core/config.py` — 9 `memory_*` config fields: enabled, procedural_decay_days (90), episodic_decay_days (30), query_pattern_decay_days (60), promotion_threshold (3), max_recall_results (5), duplicate_threshold (0.95), merge_threshold (0.92), decay_min_weight (0.1)
- `app/memory/service.py` — `_get_embedding()` lazy singleton (reuses knowledge module's embedding infra), `store()` with auto-embed + dedup, `recall_by_query()` with server-side embedding, `compact()` (decay per type + delete + merge + promote), `promote_episodes()`
- `app/memory/repository.py` — 6 new methods: `find_similar()`, `apply_decay()`, `merge_entries()`, `find_similar_pairs()` (raw SQL cosine self-join), `find_promotable()`, `update_memory_type()`
- `app/memory/schemas.py` — `MemoryRecallByQueryRequest`, `CompactionResult`, `PromotionResult`
- `app/memory/routes.py` — 2 new endpoints: `POST /compact` (admin-only, 2/min), `POST /recall/query` (admin+agent, 10/min). Route ordering: compact and recall/query placed before `/{entry_id}` to avoid path collision.
- 55 total tests (up from 29): 24 repository + 19 service + 11 route + 1 conftest. All type checkers pass (0 new errors). 106 security tests pass.
**Verify:** Store memory without embedding — auto-generated. Store duplicate — skipped. POST `/recall/query` with text — results returned. POST `/compact` — decay applied, entries merged, episodes promoted. 55 tests green.

#### AI-3.3 Memory Bridge — Auto-Persist from Agent Results ✅
**What:** Create `app/memory/bridge.py` — fire-and-forget callback that auto-persists successful multi-tool agent interactions as episodic memories. Adapted from email-hub's `HandoffMemoryBridge` pattern.
**Status:** Implemented 2026-04-09. Plan: `.agents/plans/ai-3.3-memory-bridge.md`. 3 files (1 created, 1 modified, 1 test file created), 10 tests passing.
**Implementation:**
- `app/memory/bridge.py` — `extract_tool_names()` (pure function, deduplicates tool names from message history), `_persist_episode()` (async worker with exception safety, own DB session via `get_db_context()`), `persist_agent_episode()` (sync entry point, spawns background `asyncio.create_task`, gated by `memory_enabled` config and `min_tools=2` threshold)
- `app/core/agents/service.py` — Wired `persist_agent_episode()` after standard tier `agent.run()` response (line 193-198). Complex tier (pipeline) skipped — `PipelineResult` doesn't expose message history.
- `app/memory/tests/test_bridge.py` — 10 tests: tool extraction (3), gating logic (3: single tool skip, multi-tool fire, memory disabled), async storage (1), error resilience (1), content format (1), truncation (1)
- Content format: `"[{agent_name}] Dispatcher asked: {prompt[:150]}. Agent used: {tools}. Response: {response[:300]}"`
- Metadata: `{source: "agent", agent_name, tools, confidence}`
**Verify:** 10 unit tests. 65 total memory tests pass (up from 55). 69 agent tests pass. 1114 unit tests pass. 106 security tests pass. All type checkers pass (0 new errors).

#### AI-3.4 Memory Integration into Agent Pipeline ✅
**What:** Integrate memory recall before `agent.run()` and inject as context alongside skills. Add LLM-based intent merging to compaction. Daily background compaction and promotion tasks.
**Status:** Implemented 2026-04-09. Plan: `.agents/plans/ai-3.4-memory-agent-integration.md`. 2 files created, 7 files modified, 14 new tests (5 agent service + 4 memory service + 5 lifecycle).
**Implementation:**
- `app/core/config.py` — 5 new `memory_*` settings: `recall_min_score` (0.3), `context_injection_limit` (10), `llm_merge_enabled` (False), `compaction_cron_hour` (3), `promotion_cron_hour` (3)
- `app/core/agents/agent.py` — `build_instructions_with_skills()` extended with `memory_context` parameter
- `app/core/agents/service.py` — Memory recall before `agent.run()`: `MemoryService.recall_by_query(prompt[:2000])`, filtered by `min_score`, formatted as `"- [{score}] {content[:300]}"`, injected via `build_instructions_with_skills(skills, memory_context)`. Graceful degradation on failure.
- `app/memory/service.py` — `_llm_merge()` method using `resolve_tier_model("fast")` for lightweight LLM-based intent summarization. `compact()` conditionally uses LLM merge when `memory_llm_merge_enabled=True`, falls back to concatenation.
- `app/memory/lifecycle.py` — `start_memory_tasks()` / `stop_memory_tasks()` with `_run_at_hour()` utility for daily scheduled compaction + promotion. Gated by `memory_enabled`.
- `app/main.py` — Memory lifecycle tasks registered in lifespan (startup + shutdown)
**Verify:** 1128 unit tests pass (+14 new). 106 security tests pass. All type checkers pass (0 new errors). Memory recall injected on each chat when `memory_enabled=True`. LLM merge off by default (safe rollout).

---

### Phase AI-4: Semantic Chunking + Parent-Child Retrieval (4 days)

> **Sprint deliverable:** Documents chunked by meaning boundaries, not character count. Matched chunks return full parent section for context. Re-chunk existing documents via migration script.

#### AI-4.1 Heading-Aware Semantic Chunker ✅
**What:** Replace the fixed 512-char recursive splitter in `chunking.py` with a heading-aware chunker that respects document structure. Creates chunks at heading/section boundaries with adaptive sizing.
**Why:** Fixed-size splitting breaks mid-sentence, mid-paragraph, and mid-SOP-step. A "What to do when bus breaks down" SOP gets split into fragments that individually make no sense. Heading-aware chunking keeps each section coherent.
**Status:** Implemented 2026-04-09. Plan: `.agents/plans/ai-4.1-semantic-chunker.md`.
**Implementation:**
- `app/knowledge/chunking.py` — added `chunk_text_semantic()` function with `_extract_sections()`, `_merge_small_sections()`, `_split_large_sections()` helpers and `_Section` dataclass
  - Parses markdown `#` headings (already produced by PDF/DOCX extractors) via regex
  - Builds heading hierarchy as a stack, producing `heading_path` metadata (e.g. "Safety > Emergency Procedures")
  - Adaptive sizing: min 256 chars, target 800, max 1500 (configurable)
  - Falls back to recursive `chunk_text()` when no headings detected (< 2 sections)
- `app/knowledge/service.py` — `ingest_document()` uses semantic chunker when enabled, stores heading metadata as JSON in `DocumentChunk.metadata_json`
- `app/core/config.py` — 4 new settings: `knowledge_semantic_chunking_enabled` (True), `knowledge_chunk_target_size` (800), `knowledge_chunk_min_size` (256), `knowledge_chunk_max_size` (1500)
- No schema/model/migration changes — metadata stored in existing `metadata_json` column
- 11 new tests in `app/knowledge/tests/test_chunking.py` (18 total chunking tests)

#### AI-4.2 Parent-Child Chunk Model ✅
**What:** Extend `DocumentChunk` model with `parent_chunk_id`, `heading_path`, and `section_type` fields. Multi-paragraph sections emit one parent (full section) + N child paragraphs linked via self-referential foreign key.
**Why:** When a paragraph chunk matches, the dispatcher often needs the surrounding section context. Parent-child enables "return the full section when a paragraph matches" retrieval, critical for SOPs where steps reference earlier context.
**Status:** Implemented 2026-04-10. Plan: `.agents/plans/ai-4.2-parent-child-chunks.md`. 6 files modified, 1 migration created, 10 new tests (9 chunker + 1 repository). Search-time parent expansion deferred to AI-4.3.
**Implementation:**
- `app/knowledge/models.py` — added to `DocumentChunk`:
  - `parent_chunk_id: Mapped[int | None]` — `ForeignKey("document_chunks.id", ondelete="CASCADE")`, indexed
  - `heading_path: Mapped[str | None]` — `String(500)`, e.g., "Emergency Procedures > Route Deviation"
  - `section_type: Mapped[str | None]` — `String(20)`, `"heading" | "body" | "list" | "table"`
- `alembic/versions/g5h6i7j8k9l0_add_parent_child_to_chunks.py` — adds 3 columns + self-referential FK + index on `parent_chunk_id`
- `app/knowledge/chunking.py` — `ChunkResult` extended with `heading_path`, `section_type`, `is_parent`, `parent_index` fields. New `_classify_section_type()` helper detects markdown tables, bulleted/numbered lists (≥60% of lines), and short single-line headings. `chunk_text_semantic()` emission loop rewritten: multi-paragraph sections emit one parent + N children; single-paragraph sections stay as leaf chunks.
- `app/knowledge/repository.py` — `bulk_create_chunks(chunks, *, flush_only: bool = False)` — when `flush_only=True`, calls `db.flush()` instead of `db.commit()` so caller can read newly assigned parent ids before constructing children.
- `app/knowledge/service.py` — two-phase insert in `ingest_document()`: partition results into parent/child/leaf groups, flush parents to obtain ids, build children with resolved `parent_chunk_id`, commit children + leaves (parents commit with same transaction).
- 10 new tests: 9 chunker tests (leaf path, parent+child emission, parent content, heading_path field, list/table/body classification, fallback path, child_count metadata) + 1 repository test for `flush_only` semantics. 27 total chunking tests (18 existing + 9 new). 175/175 knowledge tests pass. Pyright 0 errors, mypy 0 errors in `app/knowledge/`.
**Verify:** Apply migration via `make db && make db-migrate`. Upload a multi-section SOP, then `SELECT id, parent_chunk_id, heading_path, section_type FROM document_chunks WHERE document_id = (SELECT max(id) FROM documents) ORDER BY chunk_index;` — expect parent rows with `parent_chunk_id IS NULL` followed by child rows pointing to that parent.

#### AI-4.3 Parent-Child Retrieval + Context Expansion ✅

**Status:** Implemented 2026-04-10. Plan: `.agents/plans/ai-4.3-parent-child-retrieval.md`. 8 files modified, 0 migrations (AI-4.2 columns reused), 5 new tests (2 repository + 3 agent tool). Pyright 0 errors, mypy 0 new errors in `app/knowledge/` and `app/core/agents/tools/knowledge/`. 189/189 knowledge tests pass.

**What:** When hybrid search returns a child chunk match, automatically fetch and include the parent chunk content in the agent's context. Deduplicate when multiple children from the same parent match.

**Why:** A child chunk matching "call depot X" is useless without the parent context "When bus breaks down on route 22, follow these steps: 1. call depot X, 2. reroute via Y, 3. notify dispatcher Z."

**Files modified:**
- `app/core/config.py` — added `knowledge_parent_context_enabled: bool = True` and `knowledge_parent_context_max_chars: int = 3000`
- `app/knowledge/repository.py` — added `get_chunks_by_ids(chunk_ids)` batch fetch helper with empty-list short-circuit
- `app/knowledge/schemas.py` — added 3 optional fields to `SearchResult`: `parent_chunk_id`, `parent_content`, `heading_path` (all `None`-default, non-breaking)
- `app/knowledge/service.py` — inserted parent expansion block in `KnowledgeService.search()` after confidence filter: collect unique `parent_chunk_id`s, batch-fetch via `get_chunks_by_ids()`, attach parent fields to each `SearchResult`. Emits `knowledge.search.parent_context_attached` log event with `result_count`/`parent_count`/`unique_parents`
- `app/core/agents/tools/knowledge/schemas.py` — added `parent_content`, `heading_path` to `KnowledgeSearchResult`
- `app/core/agents/tools/knowledge/search_knowledge.py` — added `_MAX_PARENT_CHARS = 3000`; rewrote formatter loop to render `[Section: {heading_path}]\n{parent_content}\n\n[Matched passage:]\n{child_content}` markers when parent is present; agent completion log includes `parent_contexts_count`
- `app/knowledge/tests/test_repository.py` — 2 new tests for `get_chunks_by_ids` (returns matched chunks; empty input short-circuits)
- `app/core/agents/tools/knowledge/tests/test_search_knowledge.py` — 3 new tests for the formatter (parent + heading markers, no-parent leaf back-compat, parent truncation to 3000 chars)

**Architecture:** Parent expansion lives in `KnowledgeService.search()` (not the repository) so it runs after RRF/rerank/confidence filtering — only surviving results trigger parent fetches. Single batch SELECT with deduplication keeps the round-trip count at 1 regardless of how many children match the same parent.

**Security (CTX-AGENT):** Token budget enforced via `_MAX_PARENT_CHARS=3000` (agent tool) + `knowledge_parent_context_max_chars=3000` (service truncation). Feature gate `knowledge_parent_context_enabled` (default `True`, can disable via env var `KNOWLEDGE_PARENT_CONTEXT_ENABLED=false`). Parent content originates from the same trusted server-side chunker output already in the DB — no new untrusted input surface.

**Verify:** Upload multi-section SOP. Search for specific step mentioned in section 3. Result should include full section 3 as context, not just the matched paragraph. Toggle `KNOWLEDGE_PARENT_CONTEXT_ENABLED=false` to revert to pre-AI-4.3 behavior.

#### AI-4.4 Re-Chunk Existing Documents ✅
**What:** Migration script to re-chunk all existing documents using the new semantic chunker. Preserves document metadata, regenerates chunks and embeddings.
**Why:** Existing documents were chunked with the old 512-char recursive splitter. They need to be re-chunked to benefit from semantic boundaries and parent-child structure.
**Status:** Implemented 2026-04-10. Plan: `.agents/plans/ai-4.4-rechunk-existing-documents.md`. 5 files touched (`app/knowledge/repository.py`, `app/knowledge/service.py`, `scripts/rechunk_documents.py`, `app/knowledge/tests/test_rechunk.py`, `Makefile`), 0 migrations, 6 new tests. Pyright 0 errors, mypy 0 errors in `app/knowledge/`. 167/167 knowledge tests pass.
**Implementation:**
- `app/knowledge/repository.py` — added `delete_chunks_by_document(document_id) -> int` (bulk DELETE on chunks only, keeps the Document row).
- `app/knowledge/service.py` — extracted the two-phase parent/child store algorithm out of `ingest_document` into a private `_chunk_embed_store(document_id, text)` helper. Added public `rechunk_document(document_id) -> int` that resolves the document, re-extracts text from `file_path` via `processing.extract_text`, deletes old chunks, re-runs the helper, and updates `chunk_count` + `ocr_applied`. On any error the document is marked `failed` with the error message and the exception re-raises so the script's outer loop can record + skip. **Does NOT** call `_auto_tag_document` (would clobber human-curated tags).
- `scripts/rechunk_documents.py` — argparse CLI with `--dry-run`, `--batch-size` (default 10, min 1), `--document-id`, `--limit`. Pages through `list_documents` in 500-row chunks, processes per-`batch_size` group sequentially, per-doc `try/except` records failed ids, exits 1 on any failure. Logs prefixed `[rechunk]`. Reads DB via `get_db_context()` (no env-var leak; CTX-INFRA clean).
- `Makefile` — added `rechunk` and `rechunk-dry-run` targets, registered in `.PHONY`, both visible via `make help`.
- `app/knowledge/tests/test_rechunk.py` — 6 unit tests (happy path, OCR flag propagation, missing file_path raises, document not found raises, failure marks status & re-raises, metadata-preservation regression guard). All mock the embedding singleton via `monkeypatch.setattr` to avoid singleton leakage.
**Verify:** `make rechunk-dry-run` against a dev DB prints a per-document preview, exits 0, and does not mutate `document_chunks`. `make rechunk` re-chunks all documents using the current semantic chunker config; existing chunks are deleted before re-creation. Search quality spot-check: pick 5 production queries, run `make rechunk` on a staging copy, confirm parent-context expansion now activates for the migrated documents.

---

### Phase AI-5: Bounded Self-Correction (3 days)

> **Sprint deliverable:** Agent validates its own responses before returning to dispatchers. Factual errors (wrong route numbers, impossible times) caught and corrected via 1 retry round.

#### AI-5.1 Self-Correction Loop ✅
**Status:** Done — `app/core/agents/correction.py` created with `SelfCorrectionLoop` + `CorrectedResult` dataclass. Wraps standard-tier `agent.run()` only (complex-tier pipeline has its own retry layer, deferred to AI-5.2). Stale-data warnings filtered as non-retryable. Validator exceptions handled fail-open. Logs `agent.correction.triggered/resolved/exhausted/failed`. `max_rounds` clamped to ≤3 to bound token cost. Configurable via `agent_self_correction_enabled: bool = True` and `agent_max_correction_rounds: int = 1` in `app/core/config.py`. Single-validation pass — `service.py` reuses correction-loop validation result rather than re-running. 15 unit tests in `app/core/agents/tests/test_correction.py`. Plan: `.agents/plans/ai-5-1-self-correction-loop.md`.

**Original spec:**
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

#### AI-5.3 Correction Metrics + Dashboard ✅
**Status:** Done — `app/core/agents/metrics.py` created with `CorrectionMetricsTracker` singleton + `CheckMetrics` dataclass. Per-check counters (`triggered`, `resolved`, `exhausted`, `total_latency_ms`) with lazy 00:00 UTC daily reset (no background task). `correction.py` instrumented at three points: `triggering_check_names` captured on first error-severity hit, `record_resolved` called on the corrected branch with monotonic loop latency, `record_exhausted` called after the for-loop break. New admin-only `GET /v1/chat/metrics` endpoint in `routes.py` (`require_role("admin")` + `30/minute` rate limit) returns `CorrectionMetricsResponse` with per-check breakdown + aggregate totals (success_rate, avg_latency_ms). Per-correction `agent.correction.metric` log line emitted on every resolved/exhausted event. In-process only (no Redis) — per-worker drift acceptable for observability dashboard. Tracker stores only `check_name` strings + integer counters (no PII, no prompts). 10 unit tests in `app/core/agents/tests/test_metrics.py` (5 tracker, 2 loop integration, 3 endpoint). Plan: `.agents/plans/ai-5-3-correction-metrics.md`.

---

### Phase AI-6: Multi-Agent + Harness + L3 Skills (9 days)

> **Sprint deliverable:** Monolithic 11-tool agent split into 3 domain specialists + router. Full BaseAgentService harness (9 hook points, confidence extraction, context budgets). Progressive L3 skill loading with token budgets and priority gating. Token usage drops ~40%. Tool selection accuracy improves.
> **Depends on:** Phase AI-3 (memory — shared across agents)

#### AI-6.1 BaseAgentService Shared Pipeline (Full Harness) ✅
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

#### AI-6.2 Domain-Specific Agents ✅
**What:** 3 domain-agent subclasses of `BaseAgentService`, selected via `agent: 'unified'|'transit'|'knowledge'|'vault'` field on `ChatCompletionRequest` (default `unified` preserves the all-11-tool fallback).
**Why:** The unified agent loaded all 11 tool docstrings (~3000 tokens) for every query. A vault rename didn't need transit tools in context. Domain-specific prompts are shorter and more focused, improving tool selection accuracy and cutting per-request token footprint.
**Implementation:**
- `app/core/agents/agents/transit.py` — `TransitAgent` with the 5 transit tools, `TRANSIT_SYSTEM_PROMPT` (Latvian glossary + response format, no KB/vault sections), full QA + self-correction loop + complex-tier pipeline dispatch. `agent_name="transit_agent_v2"` to avoid memory-store collision with unified.
- `app/core/agents/agents/knowledge.py` — `KnowledgeAgent` with the single `search_knowledge_base` tool, `KNOWLEDGE_SYSTEM_PROMPT` enforcing citation format (`[title](/lv/documents/{id})`), "I don't know" instruction, and `Sources` list. RAG always-on, no QA, single-branch `_execute`.
- `app/core/agents/agents/vault.py` — `VaultAgent` with the 4 obsidian tools, `VAULT_SYSTEM_PROMPT` enforcing frontmatter conventions, `dry_run=true`-first bulk ops, and the confirm-before-destructive safe-delete clause (defense-in-depth on top of tool-level `confirm` enforcement).
- `app/core/agents/agents/registry.py` — `get_agent_by_name(AgentName)` returns per-domain singletons; `close_all_agents()` wired into the lifespan shutdown handler next to `close_agent_service()`.
- `app/core/agents/schemas.py` — `AgentName = Literal["unified","transit","knowledge","vault"]` + `agent: AgentName = "unified"` field on `ChatCompletionRequest` (Pydantic strict mode → 422 for bogus values before service layer).
- `app/core/agents/routes.py` — `chat_completions` resolves the service via `get_agent_by_name(body.agent)` instead of hardcoded `Depends(get_agent_service)`; logs `agent.chat.selected` on every request.
- Skills tool (`manage_agent_skills`) stays **only** on unified — domain agents can't create artifacts that need human activation.
- The three `_recall_memories_block` copies carry `# NOTE: duplicated from AgentService; extract on AI-6.2.1` — three-feature rule threshold reached, extraction deferred to a follow-up task to keep this diff focused.
**Verify:** ✅ 48 new tests (16 transit + 15 knowledge + 15 vault + 3 route regressions including the 422-on-bogus-agent assertion). Pyright baseline preserved (5 errors, all pre-existing). Mypy baseline preserved (3 errors, all pre-existing). 1288 unit tests + 106 security convention tests green. Plan: `.agents/plans/ai-6.2-domain-specific-agents.md`.

#### AI-6.3 Agent Router ✅
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

#### AI-6.4 Progressive Skill System (L3 Skills) ✅
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

#### AI-6.5 Lightweight AgentResult Protocol ✅
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

#### AI-7.1 Synthetic Test Cases ✅
**Status:** Done — `app/core/agents/evals/` package created with frozen `EvalCase` + `QualityCriterion` dataclasses (`schemas.py`), fail-open path-sandboxed YAML loader (`loader.py`, mirrors `skill_loader.py` security posture: `yaml.safe_load` only, `Path.is_relative_to` after `.resolve()` on both sides, never raises into callers). 30 hand-authored cases under `cases/`: 15 transit (LV/EN/diacriticless/mixed code-switching, all 5 transit tools, cross-tool composition, non-existent route handling), 10 knowledge (LV+EN policy lookups, cross-lingual retrieval, "no relevant docs" honesty, citation format, multi-doc synthesis), 5 vault (tag search, note creation, safe deletion with `confirm: true`, bulk dry-run preview, folder organisation). Every case has exactly 5 `quality_criteria` validated by `__post_init__`; loader rejects unknown tools/languages/domains and detects duplicate IDs across the suite. All 10 unique tool function names referenced at least once. 30 new tests in `app/core/agents/tests/test_eval_loader.py` (schema validation, parser edge cases, path-traversal block, duplicate-id detection, production-suite integrity). `make_eval_case` + `make_quality_criterion` factories added to `conftest.py`. Pyright/mypy baseline preserved (5/3 pre-existing errors). All 286 agent tests + 106 security convention tests green. Plan: [.agents/plans/ai-7.1-synthetic-test-cases.md](../.agents/plans/ai-7.1-synthetic-test-cases.md).

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

#### AI-7.2 Eval Runner + Trace Collection ✅
**Status:** Done — `app/core/agents/evals/runner.py` implements `EvalRunner` class + `EvalTrace` frozen dataclass + CLI entrypoint (`python -m app.core.agents.evals.runner --suite transit|knowledge|vault|all`). Fail-open per case: one exception writes an error trace and the suite continues, mirroring AI-7.1 loader semantics. Path-sandboxed output directory via `Path.resolve().is_relative_to()`. `--suite` validated against a closed argparse `choices` set. Never logs raw prompts or responses — only case IDs, domains, counts, and latencies (new event taxonomy: `agent.evals.runner.suite_started/case_started/case_completed/case_failed/suite_completed/path_escaped/close_failed/aborted`). Traces written as JSONL to `evals/traces/{suite}_{YYYYMMDDTHHMMSSZ}.jsonl` (git-ignored via new `.gitignore` entry). Non-behavioral refactor of `BaseAgentService`: new public `chat_with_trace()` returning `(ChatCompletionResponse, AgentResult, tuple[ToolReturnRecord, ...])`; existing `chat()` is now a thin shim that returns only the envelope — retry-path-aware `final_outcome` tracking ensures tool returns come from the winning pipeline hop (confidence re-route preserved). Runner calls `close_all_agents()` in `try/finally` so per-domain HTTP clients are released on both success and error paths. New `make eval SUITE=transit` / `make eval-all` Makefile targets. 14 new runner unit tests + 2 new `chat_with_trace` regression tests in `test_base.py` — all mock the pipeline via a concrete `BaseAgentService` test double, no DB / HTTP / Docker needed. `app/core/agents/evals/` pyright + mypy clean (0/0). Wider agent module baseline preserved (pyright 5, mypy 3 — all pre-existing, unrelated files). 302 agent tests + 1396 unit tests + 106 security convention tests green. (2026-04-11)
  - Plan: [.agents/plans/ai-7-2-eval-runner.md](../.agents/plans/ai-7-2-eval-runner.md)

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

- [x] **AI-6.1 BaseAgentService Harness** — Extracted `AgentService.chat()` orchestration into a reusable `BaseAgentService` base class in `app/core/agents/base.py` (~430 lines) with 11 hook points (tier classification, RAG routing, skill detection, memory recall, system prompt assembly, user message shaping, validation cache preload, agent execution, post-process / QA / should-run-QA, response assembly, memory persist). `AgentService` is now a thin transit-specific subclass that overrides hooks touching service-module globals (preserving all `test_service.py` patch contracts). Pure refactor — zero behavior change, all 132 agent+bridge tests and 106 security convention tests pass unchanged. Added 23 new hook-point unit tests in `app/core/agents/tests/test_base.py`. Type-check baseline preserved (pyright 5, mypy 3 errors — all pre-existing). Foundation for AI-6.2 domain-specific agents. (2026-04-10)
  - Plan: [.agents/plans/ai-6.1-base-agent-service.md](../.agents/plans/ai-6.1-base-agent-service.md)

- [x] **AI-6.2 Domain-Specific Agents** — Three `BaseAgentService` subclasses under `app/core/agents/agents/`: `TransitAgent` (5 transit tools, `agent_name="transit_agent_v2"`, full QA + self-correction loop + complex-tier pipeline dispatch, new `TRANSIT_SYSTEM_PROMPT` stripped of KB/vault sections), `KnowledgeAgent` (single `search_knowledge_base` tool, RAG always-on, citation-enforcing `KNOWLEDGE_SYSTEM_PROMPT` with "I don't know" grounding clause and `Sources` list), `VaultAgent` (4 obsidian tools, `VAULT_SYSTEM_PROMPT` with frontmatter conventions + confirm-before-destructive safe-delete clause). Selection via `agent: 'unified'|'transit'|'knowledge'|'vault'` `Literal` field on `ChatCompletionRequest` (default `unified` keeps the all-11-tool fallback bit-identical). Per-domain singletons in `app/core/agents/agents/registry.py` via `get_agent_by_name()`; `close_all_agents()` wired into the lifespan shutdown next to `close_agent_service()`. `manage_agent_skills` stays only on unified. Three `_recall_memories_block` duplicates carry `# NOTE: duplicated from AgentService; extract on AI-6.2.1` comments — three-feature-rule threshold reached, shared extraction deferred. 48 new tests: 16 transit + 15 knowledge + 15 vault + 3 route regressions (422-on-bogus-agent, unified default, explicit transit selector). Also retroactively fixed a latent `test_routes.py` quota-tracker pollution bug (Redis-backed counter leaking across runs) via new `_bypass_quota_tracker` autouse fixture. Pyright/mypy baseline preserved (5/3 pre-existing errors). 1288 unit tests + 106 security convention tests green. Foundation for AI-6.3 auto-router. (2026-04-10)
  - Plan: [.agents/plans/ai-6.2-domain-specific-agents.md](../.agents/plans/ai-6.2-domain-specific-agents.md)

- [x] **AI-6.3 Agent Router (Heuristic Auto-Selection)** — Server-side keyword router in `app/core/agents/router.py` that classifies prompts into transit/knowledge/vault domains (Latvian + English signal sets with diacritic variants, regex-based, microsecond latency, no LLM call). `AgentRouter.classify(prompt) -> RoutingDecision` returns the chosen `AgentName` plus per-domain scores; tied or zero-score prompts fall back to `"unified"`. Wired into `chat_completions` (`app/core/agents/routes.py`) only when `body.agent == "unified"` AND the new `agent_multi_agent_enabled` config flag is on — explicit `agent="transit"` requests are never overridden. New structured-log event `agent.router.decision` carries `prompt_hash` (12-char SHA-256, never raw prompt), `prompt_length`, chosen `domain`, and per-domain scores; expanded `agent.chat.selected` gains `requested_agent` + `auto_routed` fields for A/B analysis. Default-off flag (`AGENT_MULTI_AGENT_ENABLED=false`) preserves current behavior bit-identically for safe rollout. 27 new tests: 24 router unit (Latvian + diacritic variants, English, ties, empty/whitespace, scores, NamedTuple shape, structured logging contract, sentinel-leak protection, singleton) + 3 endpoint integration tests (flag-off honors `body.agent`, flag-on routes transit prompt, flag-on cross-domain falls back to unified). Pyright/mypy baseline preserved (5/3 pre-existing errors). All 1315 unit tests + 106 security convention tests green. Foundation for downstream A/B routing tuning. (2026-04-10)
  - Plan: [.agents/plans/ai-6.3-agent-router.md](../.agents/plans/ai-6.3-agent-router.md)

- [x] **AI-6.4 Progressive L3 Skill System** — Per-agent, on-demand, priority-gated skill loader replacing flat DB skill injection. New `app/core/agents/context_budget.py` defines frozen `ContextBudget` dataclass + `AGENT_BUDGETS` per-agent dict (transit 2500 / knowledge 2000 / vault 1500 / unified 3000 skill-doc tokens) + `agent_budget_for()` lookup. New `app/core/agents/skill_loader.py` parses in-repo markdown skill files with YAML front matter (`yaml.safe_load` only, never `yaml.load`), sandboxes paths via `Path.is_relative_to` against `skills/<domain>/` (rejects traversal with `agent.skill_loader.path_escaped` log), applies priority gating (P1 always, P3 dropped when remaining capacity < 70%, P2 dropped when < 30%), enforces per-agent token budget, matches keywords as substring against lowercased prompt (never compiled as regex). 12 in-repo skill files under `app/core/agents/skills/{transit,knowledge,vault}/`: 5 transit (delay_analysis, schedule_interpretation, route_comparison, driver_availability, adherence_reporting), 4 knowledge (sop_retrieval P1 always-on, regulation_interpretation, shift_handover, incident_response), 3 vault (search_patterns, bulk_operations, folder_organization). Domain agents override `detect_relevant_skills()`: `TransitAgent` + unified `AgentService` compose flat DB skills (existing behavior, unchanged) + L3 pack; `KnowledgeAgent` + `VaultAgent` load L3-only (they did not previously load flat DB skills). Unified agent unions all three L3 packs at 1/3 sub-budget each. New settings `agent_progressive_skills_enabled` (default True) gates the loader; fail-open on every error path (logs `agent.l3_skills_load_failed` / `agent.skill_loader.*`, returns `""`). Module-level cache with threading lock; `clear_cache()` test helper. Added `pyyaml>=6.0` to dependencies. 25 new tests (6 context_budget + 19 skill_loader covering front-matter parsing, discovery, keyword matching, priority gating, budget enforcement, integration with real in-repo files). Pyright/mypy baseline preserved (5/3 pre-existing errors). All 1350 unit tests + 106 security convention tests green. (2026-04-10)
  - Plan: [.agents/plans/ai-6.4-6.5-progressive-skills-and-agent-result.md](../.agents/plans/ai-6.4-6.5-progressive-skills-and-agent-result.md)

- [x] **AI-7.1 Synthetic Eval Cases + Loader** — Foundation of the agent eval framework. New `app/core/agents/evals/` package with frozen `EvalCase` + `QualityCriterion` dataclasses (`schemas.py`, validates `id`/`prompt`/`language`/`expected_domain`/`expected_tools` against `KNOWN_TOOLS` frozenset of all 10 unique tool function names + exact `quality_criteria` count of 5 in `__post_init__`) and a fail-open path-sandboxed YAML loader (`loader.py`) that mirrors `skill_loader.py` exactly: `yaml.safe_load` only, `Path.is_relative_to` after `.resolve()` on both sides, never raises into callers — every error path logs `agent.evals.loader.<reason>` and returns `None`/`[]`. 30 hand-authored cases under `evals/cases/`: 15 `transit.yaml` (LV baseline + EN mirror + diacriticless variant + specific-route + name + proximity stop search + cross-tool composition + schedule by date/direction + adherence + multi-route comparison + driver headcount + cross-tool driver+schedule + non-existent route handling + mixed LV/EN code-switching), 10 `knowledge.yaml` (SOP retrieval, EU regulation, out-of-domain "no relevant docs" honesty, cross-lingual LV↔EN retrieval, temporal SOP relevance, multi-doc synthesis, diacriticless query, EN policy lookup, citation format compliance), 5 `vault.yaml` (tag search, note creation with frontmatter, safe deletion requiring `confirm: true`, bulk operation with `dry_run` preview first, folder organisation). Production-suite integrity asserted by tests: exactly 15/10/5 cases per file, all 30 IDs globally unique, every one of the 10 known tool names referenced at least once, every case's `expected_domain` matches its file. 30 new tests in `app/core/agents/tests/test_eval_loader.py` (schema valid+rejects-empty/unknown/wrong-count, frozen invariant, parser missing/malformed/top-level-not-dict/missing-cases-key/cases-not-list, partial-skip-keeps-valid, missing-file, path-traversal blocked, three-domain load, duplicate-ID detection, production integrity). `make_eval_case` + `make_quality_criterion` factories + `tmp_eval_dir` fixture added to `conftest.py`. No new endpoints, no models, no migrations, no auth surface. Pyright/mypy baseline preserved (5/3 pre-existing errors). 286 agent tests + 1376 unit tests + 106 security convention tests green. Foundation for AI-7.2 eval runner. (2026-04-10)
  - Plan: [.agents/plans/ai-7.1-synthetic-test-cases.md](../.agents/plans/ai-7.1-synthetic-test-cases.md)

- [x] **AI-7.2 Eval Runner + Trace Collection** — CLI that runs AI-7.1 synthetic cases against the live per-domain agents and writes JSONL traces. New `app/core/agents/evals/runner.py` defines `EvalRunner` class (path-sandboxed output dir, fail-open per-case, fail-open finally-close of per-domain HTTP clients via `close_all_agents()`), `EvalTrace(frozen=True)` dataclass (case_id, domain, prompt, response, tools_used, tool_returns, confidence, warnings, latency_ms, error, timestamp — `asdict` serialization, non-JSON-safe tool payloads coerced via `default=str`), and CLI entrypoint (`python -m app.core.agents.evals.runner --suite transit|knowledge|vault|all [--output-dir PATH]`). `--suite` validated by argparse `choices` closed set; output directory enforced via `Path.resolve().is_relative_to()` with `agent.evals.runner.path_escaped` warning on violation. Non-behavioral refactor of `BaseAgentService`: new public `chat_with_trace(request) -> (ChatCompletionResponse, AgentResult, tuple[ToolReturnRecord, ...])` captures the parsed tool return records from the winning pipeline hop (retry-path-aware `final_outcome` tracking preserves AI-6.5 confidence re-route semantics); existing `chat()` is now a thin shim returning only the envelope — zero HTTP-layer behavior change. New structured log taxonomy: `agent.evals.runner.suite_started/case_started/case_completed/case_failed/suite_completed/path_escaped/close_failed/aborted` — runner NEVER logs raw prompts or responses, only IDs, counts, and latencies (CTX-AGENT compliance). `make eval SUITE=...` + `make eval-all` Makefile targets; `evals/traces/*.jsonl` added to `.gitignore` (trace payloads may contain PII). 14 new runner unit tests + 2 new `chat_with_trace` regression tests in `test_base.py` — all mock the pipeline via a concrete `BaseAgentService` test double (no DB, HTTP, or Docker needed). `app/core/agents/evals/` pyright + mypy clean (0/0); wider agent module baseline preserved (pyright 5, mypy 3 — all pre-existing in unrelated files). 302 agent tests + 1396 unit tests + 106 security convention tests green. Foundation for AI-7.3 LLM judges. (2026-04-11)
  - Plan: [.agents/plans/ai-7-2-eval-runner.md](../.agents/plans/ai-7-2-eval-runner.md)

- [x] **AI-6.5 AgentResult + Confidence Re-Route Gate** — Lightweight `AgentResult(frozen=True)` metadata wrapper in new `app/core/agents/agent_result.py` (fields: `content`, `confidence: float | None`, `warnings: tuple[str, ...]`, `tools_used: tuple[str, ...]`, `domain` — `__post_init__` validates domain ∈ `VALID_DOMAINS = {transit, knowledge, vault, unified}` and confidence ∈ `[0.0, 1.0] | None`). `_PipelineOutcome` extended with optional `confidence: float | None = None` + `tools_used: tuple[str, ...] = ()` (additive, non-breaking — all existing kwargs-only constructor sites work unchanged). `BaseAgentService.chat()` rewired to build `AgentResult` after `_post_process()`, then run the confidence re-route gate: when `agent_confidence_reroute_enabled` AND `result.confidence < agent_confidence_reroute_threshold` (default 0.3) AND current tier != complex AND `resolve_tier_model("complex")` is non-None, call `_execute()` exactly once more with `tier="complex"` and the complex model. Hard-capped at 1 extra LLM call per chat — no recursion, no escalation loop. Warnings are metadata only and NOT re-rendered into content (they're already appended as `⚠️` footnotes in `_post_process` earlier in the pipeline) — preflight design note preserved to avoid double-rendering. Per-domain confidence heuristics: transit (1.0 clean / 0.6 warnings / 0.3 errors via `_transit_confidence_from_warnings`), knowledge (0.7 when RAG tool ran / None otherwise), vault (1.0 baseline — deterministic file ops). `tools_used` extracted via `extract_tool_returns(messages)`. New settings: `agent_confidence_reroute_enabled` (default True) + `agent_confidence_reroute_threshold` (default 0.3). `agent.chat.confidence_reroute` / `.confidence_reroute_failed` log events. 10 new tests: frozen-ness, valid construction, invalid domain/confidence raises, None confidence allowed, `VALID_DOMAINS` content, re-route triggers retry with complex model, no re-route on confidence=None, no re-route on flag off, graceful skip when no complex model available. HTTP contract unchanged (`chat()` still returns `ChatCompletionResponse` via existing `_build_response()`). Pyright/mypy baseline preserved (5/3 pre-existing errors). (2026-04-10)
  - Plan: [.agents/plans/ai-6.4-6.5-progressive-skills-and-agent-result.md](../.agents/plans/ai-6.4-6.5-progressive-skills-and-agent-result.md)

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
