# Agent Module

Pydantic AI agent (`Agent[UnifiedDeps, str]`) with 11 tools across 4 domains. Follows vertical slice pattern with `tools/` subdirectory.

## Directory Structure

```
app/core/agents/
├── agent.py           # Agent creation, 11 tool registrations + build_instructions_with_skills()
├── routes.py          # /v1/chat/completions, /v1/models (rate limited + quota)
├── service.py         # Orchestration, deps injection, model building (singleton), skills injection via instructions param
├── schemas.py         # OpenAI-compatible request/response schemas
├── config.py          # LLM provider settings (model names, tokens, timeouts)
├── routing.py         # Multi-tier model routing (fast/standard/complex classification)
├── quota.py           # Daily per-IP quota tracker (50/day, auto-reset)
├── exceptions.py      # TransitDataError, ObsidianError → HTTP 503
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
└── tests/             # 66 agent-level tests (incl. routing + config tier tests)
```

## Planned Improvements

See `docs/TODO.md` → "Agent Architecture Improvements" for the full roadmap. Key priorities:

1. **Multi-tier model routing** - Heuristic prompt classifier in `routing.py`, tier model resolution via `resolve_tier_model()` in `config.py`, integrated into `AgentService.chat()`. Configure via `LLM_FAST_*`/`LLM_STANDARD_*`/`LLM_COMPLEX_*` env vars.
2. **RAG retrieval** — ✅ Chunk overlap 50→100, ✅ result truncation 500→1500 chars, ✅ always-on reranking (AI-1.1), ✅ created_at date filtering (AI-1.2), ✅ temporal boost + query-adaptive RRF weights + evergreen flag (AI-1.3), ✅ confidence threshold 0.3 + "no results" response + anti-hallucination prompt (AI-1.4), ✅ query routing - signal-based RAG router skips knowledge search for transit/schedule/vault queries (AI-2.1), ✅ markdown-aware document extraction - PDF/DOCX/XLSX/CSV/email/image produce structured markdown chunks (AI-2.1), ✅ HyDE query expansion (AI-2.2), ✅ Redis embedding cache (AI-2.3), ✅ heading-aware semantic chunker (AI-4.1), ✅ parent-child chunk model (AI-4.2), ✅ parent-child retrieval + context expansion - search-time parent fetch with `[Section: ...]`/`[Matched passage:]` markers, batch-deduped, feature-gated (AI-4.3)
3. **Server-side memory** — pgvector-backed semantic memory with temporal decay (procedural/episodic/semantic types). Fire-and-forget bridge (`app/memory/bridge.py`) auto-persists multi-tool episodes after standard tier `agent.run()` (AI-3.3). Memory recall injected as context before each `agent.run()` via `build_instructions_with_skills()` (AI-3.4). LLM-based intent merging during compaction (configurable, off by default). Daily background compaction + promotion tasks via `app/memory/lifecycle.py`
4. **Multi-agent splitting** — Separate transit/vault/knowledge agents with router for better tool selection
5. **Bounded self-correction** — QA validation + recovery routing (max 2 rounds)
6. **Eval framework** — Synthetic test cases, binary LLM judges, TPR/TNR calibration, regression baselines

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