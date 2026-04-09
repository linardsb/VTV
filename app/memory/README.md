# Memory

Pgvector-backed long-term memory for AI agents with full lifecycle management. Stores learned patterns, session logs, durable facts, and frequent query patterns with vector embeddings for similarity-based recall. Supports embed-on-store (auto-generates embeddings), duplicate detection (cosine > 0.95 = skip), text-based recall, time-based decay, compaction (merge similar entries), and episodic-to-procedural auto-promotion after repeated recall.

## Key Flows

### Store Memory (with embedding + dedup)

1. Validate input via `MemoryEntryCreate` schema (agent_type, memory_type, content, optional embedding)
2. If no embedding provided, auto-generate via `EmbeddingProvider` singleton (reuses knowledge module's embedding infrastructure)
3. Check for duplicates: cosine similarity > 0.95 against existing entries = skip and return existing
4. Create `MemoryEntry` model instance with generated/provided embedding
5. Persist to database via repository
6. Log `memory.service.store_completed` or `memory.service.store_duplicate_skipped`

### Recall by Similarity (vector)

1. Validate 1024-dim embedding vector via `MemoryRecallRequest`
2. Execute cosine distance query against pgvector (`1 - distance = score`)
3. Filter results by optional agent_type, memory_type, and min_score
4. Increment `recalled_count` on each returned entry
5. Return scored results as `MemoryRecallResponse` list

### Recall by Text Query

1. Validate text query via `MemoryRecallByQueryRequest` (max 2000 chars)
2. Embed the query text via `EmbeddingProvider` singleton
3. Delegate to existing similarity recall with generated embedding
4. Increment `recalled_count` on results
5. Return scored results

### Compact (decay + delete + merge + promote)

1. **Apply decay** per memory type: procedural (90d), episodic (30d), query_pattern (60d). Semantic entries are evergreen and skipped.
2. **Delete** entries with `decay_weight` below configurable threshold (default 0.1)
3. **Merge** similar entry pairs (cosine > 0.92): keep entry with higher `recalled_count`, merge content via LLM intent summarization (if `memory_llm_merge_enabled=True`) or concatenation (default), re-embed merged content, set source to "compaction"
4. **Promote** episodic entries with `recalled_count >= 3` to procedural
5. Return `CompactionResult` with counts of each operation

### Promote Episodes

1. Find episodic entries with `recalled_count >= promotion_threshold` (default 3)
2. Update `memory_type` from "episodic" to "procedural"
3. Log `memory.service.promote_completed` with count

### Auto-Persist from Agent (Bridge)

1. After `agent.run()` in `AgentService.chat()`, call `persist_agent_episode()` synchronously
2. Extract unique tool names from message history via `extract_tool_names()`
3. Gate: skip if `memory_enabled=False` or fewer than 2 distinct tools used
4. Spawn background `asyncio.create_task` with `_persist_episode()` (fire-and-forget)
5. Build content: `"[agent_name] Dispatcher asked: {prompt[:150]}. Agent used: {tools}. Response: {response[:300]}"`
6. Store as episodic memory via `MemoryService.store()` (own DB session via `get_db_context()`)
7. All exceptions caught and logged as warnings — never blocks the response pipeline

### Memory Recall Injection (Agent Context)

1. In `AgentService.chat()`, after skills loading and before `agent.run()`
2. If `memory_enabled=True`, create `MemoryRecallByQueryRequest` from user prompt (truncated to 2000 chars)
3. Call `MemoryService.recall_by_query()` with `min_score` from config (default 0.3)
4. Format recalled memories as `"- [{score}] {content[:300]}"` lines
5. Prefix with "RELEVANT MEMORIES (from prior interactions - use as context, not as authoritative facts)"
6. Inject via `build_instructions_with_skills(skills_instructions, memory_context)`
7. All exceptions caught — agent continues without memory on failure (graceful degradation)

### Background Lifecycle Tasks

1. `start_memory_tasks()` registered in `app/main.py` lifespan (startup)
2. Two daily tasks scheduled at configurable UTC hours (default 03:00):
   - **Compaction**: `_run_compaction()` — calls `service.compact()` (decay + delete + merge + promote)
   - **Promotion**: `_run_promotion()` — calls `service.promote_episodes()`
3. Tasks use `_run_at_hour()` utility that sleeps until next target hour, runs, then loops
4. `stop_memory_tasks()` cancels both tasks during shutdown (handles `CancelledError`)
5. Gated by `memory_enabled` config — tasks not started when disabled

### Delete Decayed

1. Admin-only endpoint with configurable decay threshold (default 0.1)
2. Delete entries where `decay_weight < threshold` AND `is_evergreen = false`
3. Return count of deleted entries

## Database Schema

Table: `memory_entries`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | Integer | PK, indexed | Primary key |
| `agent_type` | String(50) | Not null, indexed | Agent identifier (e.g., "transit") |
| `memory_type` | String(20) | Not null, indexed | One of: procedural, episodic, semantic, query_pattern |
| `content` | Text | Not null | Memory content text |
| `embedding` | Vector(1024) | Nullable, ivfflat indexed | Pgvector embedding for similarity search |
| `metadata_json` | JSONB | Nullable | Arbitrary metadata (route IDs, confidence scores, etc.) |
| `decay_weight` | Float | Not null, default 1.0 | Weight for decay-based cleanup (0.0-1.0) |
| `is_evergreen` | Boolean | Not null, default false | Protected from decay-based deletion |
| `source` | String(20) | Not null, indexed | Origin: agent, dispatcher, or compaction |
| `recalled_count` | Integer | Not null, default 0 | Times this memory has been recalled |
| `created_at` | DateTime | Not null | Auto-set on create (TimestampMixin) |
| `updated_at` | DateTime | Not null | Auto-set on update (TimestampMixin) |

## Configuration

Settings in `app/core/config.py` (env var overridable):

| Setting | Default | Description |
|---------|---------|-------------|
| `memory_enabled` | `True` | Enable/disable memory system |
| `memory_procedural_decay_days` | `90` | Days before procedural decay applies |
| `memory_episodic_decay_days` | `30` | Days before episodic decay applies |
| `memory_query_pattern_decay_days` | `60` | Days before query_pattern decay applies |
| `memory_promotion_threshold` | `3` | Recalled count required for episodic-to-procedural promotion |
| `memory_max_recall_results` | `5` | Max results for text-based recall |
| `memory_duplicate_threshold` | `0.95` | Cosine similarity threshold for duplicate detection |
| `memory_merge_threshold` | `0.92` | Cosine similarity threshold for merging during compaction |
| `memory_decay_min_weight` | `0.1` | Minimum decay_weight before entry is deleted |
| `memory_recall_min_score` | `0.3` | Minimum similarity score for context injection |
| `memory_context_injection_limit` | `10` | Max memories injected into agent context |
| `memory_llm_merge_enabled` | `False` | Enable LLM-based intent merging during compaction |
| `memory_compaction_cron_hour` | `3` | UTC hour for daily compaction (0-23) |
| `memory_promotion_cron_hour` | `3` | UTC hour for daily promotion (0-23) |

## Business Rules

1. Memory types are constrained to `Literal["procedural", "episodic", "semantic", "query_pattern"]`
2. Memory sources are constrained to `Literal["agent", "dispatcher", "compaction"]`
3. Evergreen memories (`is_evergreen=true`) are never deleted by decay cleanup
4. Recall automatically increments `recalled_count` on each returned entry
5. Embedding vectors must be exactly 1024 dimensions (matching project `embedding_dimension` config)
6. Content is capped at 10,000 characters via Pydantic schema validation
7. Store auto-generates embeddings when none provided (reuses knowledge module's `EmbeddingProvider`)
8. Duplicate detection: entries with cosine similarity > 0.95 are skipped on store
9. Compaction merges entries with cosine > 0.92, keeping the one with higher `recalled_count`
10. Episodic entries auto-promote to procedural after 3+ recalls (configurable)
11. Semantic entries are evergreen by design and skip decay during compaction

## Integration Points

- **auth**: All endpoints require `require_role("admin", "agent")`, compact/delete require `require_role("admin")`
- **knowledge**: Reuses `EmbeddingProvider` singleton + `CachedEmbeddingProvider` for embed-on-store and text-based recall. Shares pgvector patterns (Vector(1024), cosine distance queries, ivfflat indexing)
- **core/config**: 14 `memory_*` config fields for lifecycle tuning (9 base + 5 agent integration)
- **core/agents**: `AgentService.chat()` calls `persist_agent_episode()` from `bridge.py` after standard tier `agent.run()` — fire-and-forget episodic memory storage for multi-tool interactions (AI-3.3). Memory recall injected as context before `agent.run()` via `build_instructions_with_skills(skills_instructions, memory_context)` (AI-3.4)
- **core/agents/config**: `resolve_tier_model("fast")` used by `_llm_merge()` for lightweight LLM merge calls
- **main.py**: `start_memory_tasks()` / `stop_memory_tasks()` registered in lifespan for daily background compaction + promotion

## API Endpoints

| Method | Path | Auth | Rate Limit | Description |
|--------|------|------|------------|-------------|
| POST | `/api/v1/memory/` | admin, agent | 10/min | Store a new memory entry (auto-embeds, dedup checks) |
| POST | `/api/v1/memory/compact` | admin | 2/min | Trigger compaction: decay, delete, merge, promote |
| POST | `/api/v1/memory/recall` | admin, agent | 10/min | Recall memories by vector similarity |
| POST | `/api/v1/memory/recall/query` | admin, agent | 10/min | Recall memories by text query (server-side embedding) |
| GET | `/api/v1/memory/{id}` | admin, agent | 30/min | Get memory entry by ID |
| GET | `/api/v1/memory/type/{type}` | admin, agent | 30/min | List memories by type (Literal path param) |
| DELETE | `/api/v1/memory/decayed` | admin | 5/min | Delete decayed non-evergreen entries |
