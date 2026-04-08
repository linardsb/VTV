# VTV Agent Intelligence Improvement Plan

> Patterns adapted from merkle-email-hub's production agentic architecture, tailored for transit operations.
> Created: 2026-04-08

## Executive Summary

VTV currently runs a **single stateless Pydantic AI agent with 11 tools**. This plan proposes 8 major improvements drawn from email-hub's mature multi-agent system, prioritized for a transportation operations platform:

1. **Persistent Agent Memory** (procedural/episodic/semantic) with memory bridge — learn from usage
2. **Multi-Agent with Router** — domain-specialized agents for better tool selection
3. **Full BaseAgentService Harness** — 9 hook points, confidence extraction, per-agent context budgets
4. **Progressive L3 Skill System** — on-demand skill loading with token budgets and priority gating
5. **RAG Architecture Upgrade** — agentic RAG with query routing, HyDE, parent-child retrieval
6. **Bounded Self-Correction** — QA gate with recovery loops
7. **Memory Bridge** — auto-persist agent results as episodic memories (fire-and-forget, failure-safe)
8. **Evaluation Framework** — synthetic test cases + LLM judges

**Why NOT CRAG**: VTV's knowledge base contains curated internal documents (SOPs, regulations, shift notes), not web content. CRAG's "search the web if retrieval quality is low" pattern doesn't apply. The retrieval confidence problem CRAG solves is better addressed by always-on reranking + query routing for VTV's domain.

---

## Table of Contents

- [1. Persistent Agent Memory](#1-persistent-agent-memory)
- [2. Multi-Agent Architecture](#2-multi-agent-architecture)
- [3. RAG Architecture for Transit](#3-rag-architecture-for-transit)
- [4. Bounded Self-Correction](#4-bounded-self-correction)
- [5. Evaluation Framework](#5-evaluation-framework)
- [6. Implementation Phases](#6-implementation-phases)
- [7. Cost & Effort Estimates](#7-cost--effort-estimates)

---

## 1. Persistent Agent Memory

### What email-hub does

Email-hub's `app/memory/` implements a 3-tier memory system:
- **Procedural** — learned patterns ("Samsung Mail needs inline styles for dark mode")
- **Episodic** — session logs ("Fixed VML background in Outlook 2016 build")
- **Semantic** — durable facts ("Gmail clips emails over 102KB")

Each memory entry has: pgvector embedding (1024-dim), decay_weight, project scope, is_evergreen flag, and metadata JSONB. Compaction runs periodically with phase-aware decay (active: 60d, maintenance: 14d, archived: 3d).

### What VTV needs (adapted)

VTV's memory should track **transit operations knowledge** that the agent learns from repeated usage:

| Memory Type | Transit Examples | Decay |
|-------------|-----------------|-------|
| **Procedural** | "When dispatcher asks about Route 22 delays, always check Brivibas iela construction status first" | 90 days (transit patterns are seasonal) |
| **Episodic** | "2026-04-05 17:30 — Route 3 had 15min delays due to accident on Valdemara. Dispatcher rerouted via Tallinas." | 30 days (shift-relevant) |
| **Semantic** | "Route 22 serves 3 hospitals — delay impact is always high priority" | Evergreen |
| **Query Pattern** | "Dispatchers ask about Route 1, 3, 22 most frequently during morning rush" | 60 days |

### Implementation

#### Database Model

```python
# app/memory/models.py
class MemoryEntry(Base, TimestampMixin):
    __tablename__ = "memory_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_type: Mapped[str]           # "transit" | "knowledge" | "vault" | "unified"
    memory_type: Mapped[str]          # "procedural" | "episodic" | "semantic" | "query_pattern"
    content: Mapped[str]
    embedding: Mapped[Vector] = mapped_column(Vector(1024))
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    decay_weight: Mapped[float] = mapped_column(default=1.0)
    is_evergreen: Mapped[bool] = mapped_column(default=False)
    source: Mapped[str]              # "agent" | "dispatcher" | "compaction"
    recalled_count: Mapped[int] = mapped_column(default=0)  # Track usefulness
```

#### Memory Service

```python
# app/memory/service.py
class MemoryService:
    async def store(self, content: str, memory_type: str, agent_type: str, metadata: dict) -> MemoryEntry:
        """Embed content, store with metadata."""

    async def recall(self, query: str, agent_type: str | None, limit: int = 5) -> list[MemoryEntry]:
        """Similarity search via pgvector + metadata filtering. Increment recalled_count."""

    async def compact(self) -> int:
        """Merge similar memories, apply decay, delete low-weight entries."""

    async def promote_from_episode(self, episode: MemoryEntry) -> MemoryEntry | None:
        """If an episodic memory is recalled 3+ times, promote to procedural."""
```

#### Integration Points

1. **Before agent.run()** — recall top 5 relevant memories, inject as context (like email-hub's node context injection, max 10 entries)
2. **After agent.run()** — if the agent used 2+ tools successfully, store an episodic memory of the tool sequence
3. **Background task** — run compaction daily at 03:00 UTC (low traffic)
4. **Auto-promotion** — episodic memories recalled 3+ times → procedural

#### Key Differences from Email-Hub

| Aspect | Email-Hub | VTV |
|--------|-----------|-----|
| Scope | Per-project | Global (one transit network) |
| Decay phases | active/maintenance/archived project | Seasonal (longer cycles) |
| Promotion | DCG notes → memory | Episodic → procedural auto-promotion |
| New type | — | `query_pattern` (tracks frequent queries for prefetching) |

### Effort: 4-5 days

---

## 2. Multi-Agent Architecture

### What email-hub does

9 specialized agents orchestrated by a **blueprint state machine** (`BlueprintEngine`). Each agent:
- Extends `BaseAgentService` (shared pipeline: LLM routing, PII sanitization, output validation)
- Has its own system prompt, skills, and tools
- Communicates via `AgentHandoff` frozen dataclass (decisions, warnings, confidence, learnings)
- Receives scoped `NodeContext` (only relevant data — progressive context hydration)

### What VTV needs (adapted)

VTV does NOT need 9 agents or a full state machine. Transit queries are typically single-domain. The improvement is **splitting the monolithic agent into 3 domain specialists + 1 router**.

#### Proposed Architecture

```
User Query
    │
    ▼
┌──────────────┐
│ Router Agent │  ← Lightweight classifier (heuristic + optional LLM)
│  (no tools)  │     Replaces current routing.py tier classifier
└──────┬───────┘
       │
       ├── transit query ──► Transit Agent (5 transit tools)
       │                     System prompt: Latvian transit terminology,
       │                     GTFS data interpretation, delay analysis
       │
       ├── knowledge query ─► Knowledge Agent (search_knowledge_base + enhanced RAG)
       │                      System prompt: citation rules, document grounding,
       │                      "I don't know" when no relevant docs found
       │
       ├── vault query ─────► Vault Agent (4 obsidian tools)
       │                      System prompt: note organization, frontmatter,
       │                      safe deletion patterns
       │
       └── cross-domain ───► Unified Agent (all 11 tools, current behavior)
                             Fallback for queries spanning multiple domains
```

#### Router Implementation

```python
# app/core/agents/router.py
class AgentRouter:
    """Routes queries to domain-specific agents.

    Extends the existing routing.py tier classifier with domain detection.
    """
    TRANSIT_SIGNALS = {"maršrut", "pietura", "autobus", "kavē", "route", "stop", "delay", "bus",
                       "schedule", "departure", "brauci", "reiss", "grafik"}
    KNOWLEDGE_SIGNALS = {"dokument", "noteikum", "procedūr", "SOP", "regul", "policy",
                         "document", "procedure", "regulation", "knowledge"}
    VAULT_SIGNALS = {"vault", "obsidian", "piezīm", "note", "folder", "tag"}

    def route(self, prompt: str) -> AgentDomain:
        scores = {
            AgentDomain.TRANSIT: self._score(prompt, self.TRANSIT_SIGNALS),
            AgentDomain.KNOWLEDGE: self._score(prompt, self.KNOWLEDGE_SIGNALS),
            AgentDomain.VAULT: self._score(prompt, self.VAULT_SIGNALS),
        }
        top = max(scores, key=scores.get)
        if scores[top] == 0 or sum(1 for v in scores.values() if v > 0) > 1:
            return AgentDomain.UNIFIED  # Cross-domain or unclassifiable
        return top
```

#### Shared Base (from email-hub's BaseAgentService pattern)

```python
# app/core/agents/base.py
class BaseAgentService:
    """Shared pipeline for all domain agents.

    Handles: memory recall → skill injection → agent.run() → memory store → validation.
    Subclasses override: build_system_prompt(), get_tools(), detect_relevant_skills().
    """
    async def chat(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        # 1. Route to tier (fast/standard/complex)
        tier = self.routing.classify(prompt)
        # 2. Recall relevant memories
        memories = await self.memory.recall(prompt, agent_type=self.domain)
        # 3. Load active skills
        skills = await self.skills.get_active_skills_content()
        # 4. Build context
        context = self._build_context(memories, skills)
        # 5. Run agent
        result = await self.agent.run(prompt, message_history=history, deps=deps)
        # 6. Store episodic memory if multi-tool
        await self._maybe_store_episode(prompt, result)
        # 7. Validate response
        validated = await self.validator.validate(result)
        return validated
```

#### Progressive Context Hydration

The key insight from email-hub: **each agent gets only the context it needs**. Currently VTV's unified agent loads all 11 tool docstrings (~3000 tokens) into every request. With domain agents:

| Agent | Tools Loaded | System Prompt Focus | Token Savings |
|-------|-------------|-------------------|---------------|
| Transit | 5 transit tools | GTFS interpretation, Latvian transit glossary | ~40% fewer tool tokens |
| Knowledge | 1 RAG tool | Citation rules, grounding, "I don't know" | ~80% fewer tool tokens |
| Vault | 4 vault tools | Note organization, safety | ~60% fewer tool tokens |
| Unified | All 11 | Current system prompt | No savings (fallback) |

#### Handoff Protocol (simplified from email-hub)

VTV doesn't need the full `AgentHandoff` frozen dataclass since queries rarely chain between agents. But a lightweight version enables:
- **Confidence scoring** — route low-confidence responses to more capable model
- **Decision logging** — audit trail for dispatcher queries
- **Warning propagation** — "data is 5 minutes stale" warnings

```python
@dataclass(frozen=True)
class AgentResult:
    content: str
    confidence: float | None        # 0.0-1.0
    warnings: tuple[str, ...]       # Stale data, partial results, etc.
    tools_used: tuple[str, ...]     # For episodic memory
    domain: AgentDomain
```

### Effort: 6-8 days

---

## 2b. Progressive Skill System (L3 Skills)

### What email-hub does

Email-hub implements a **3-tier progressive skill disclosure** system that "teaches on demand":

- **L1**: Front matter in `SKILL.md` — metadata (name, version, eval_criteria, confidence_rules, references)
- **L2**: Body of `SKILL.md` — core instructions always loaded for every agent invocation
- **L3**: Individual skill files in `agent/skills/*.md` — **loaded on-demand** based on request content

**Key mechanism**: Each agent overrides `detect_relevant_skills(request) -> list[str]` with keyword/pattern detection. The `skill_loader.py` then loads L3 files within a **per-agent token budget**:

```python
# email-hub: app/ai/agents/context_budget.py
@dataclass(frozen=True)
class ContextBudget:
    system_prompt_max: int = 4000      # L1+L2 SKILL.md
    skill_docs_max: int = 2000         # L3 files total
    handoff_summary_max: int = 1000    # Previous agent handoffs
    user_message_max: int = 4000       # Input request
    total_max: int = 12000             # Grand total
```

Each L3 file has front matter with `token_cost` and `priority` (1=critical/always, 2=standard, 3=supplementary). Priority 3 skills are skipped when capacity < 70%, priority 2 when < 30%. This means ~4 skills max per agent before budget pressure.

### What VTV needs (adapted)

VTV currently has a **flat skill system** (`app/skills/`) — all active skills injected into every request regardless of relevance. This wastes context tokens on irrelevant skills.

**Adapted for transit operations:**

| Agent | L2 (Always Loaded) | L3 (On-Demand) | Detection Signal |
|-------|-------------------|----------------|-----------------|
| **Transit** | Latvian glossary, GTFS data interpretation, delay reporting rules | `delay_analysis.md`, `schedule_interpretation.md`, `route_comparison.md`, `driver_availability.md`, `adherence_reporting.md` | Query contains delay terms → load delay_analysis; schedule terms → load schedule_interpretation |
| **Knowledge** | Citation rules, grounding requirements, "I don't know" policy | `sop_retrieval.md`, `regulation_interpretation.md`, `shift_handover.md`, `incident_response.md` | Query about procedures → load sop_retrieval; legal questions → load regulation_interpretation |
| **Vault** | Frontmatter conventions, safe deletion | `search_patterns.md`, `bulk_operations.md`, `folder_organization.md` | Bulk/delete operations → load bulk_operations |

#### Implementation

```python
# app/core/agents/context_budget.py
@dataclass(frozen=True)
class ContextBudget:
    system_prompt_max: int = 3000   # L2 base instructions
    skill_docs_max: int = 2000     # L3 on-demand skills
    memory_max: int = 1500         # Recalled memories
    user_message_max: int = 3000   # Query + history
    total_max: int = 10000         # Grand total

# Per-agent budgets (transit needs more skill context)
AGENT_BUDGETS = {
    "transit": ContextBudget(skill_docs_max=2500),
    "knowledge": ContextBudget(skill_docs_max=2000),
    "vault": ContextBudget(skill_docs_max=1500),
    "unified": ContextBudget(skill_docs_max=3000),
}
```

```python
# app/core/agents/skill_loader.py
@dataclass(frozen=True)
class SkillMeta:
    token_cost: int = 500
    priority: int = 2  # 1=always, 2=standard, 3=supplementary

def load_skills_within_budget(
    skill_names: list[str],
    budget: ContextBudget,
    skill_dir: Path,
) -> str:
    """Load L3 skill files respecting token budget.

    Priority 1 always loaded. Priority 2 skipped when <30% capacity.
    Priority 3 skipped when <70% capacity.
    """
    cumulative = 0
    parts = []
    for name in skill_names:
        meta, body = parse_skill_file(skill_dir / f"{name}.md")
        remaining = budget.skill_docs_max - cumulative
        capacity = remaining / budget.skill_docs_max

        if meta.priority == 1:
            pass  # Always load
        elif meta.priority == 2 and capacity < 0.3:
            continue
        elif meta.priority == 3 and capacity < 0.7:
            continue

        if cumulative + meta.token_cost > budget.skill_docs_max:
            break

        cumulative += meta.token_cost
        parts.append(f"\n--- SKILL: {name} ---\n{body}")

    return "\n".join(parts)
```

```python
# app/core/agents/agents/transit.py (example)
class TransitAgent(BaseAgentService):
    agent_name = "transit"

    def detect_relevant_skills(self, prompt: str) -> list[str]:
        skills = []
        prompt_lower = prompt.lower()
        if any(s in prompt_lower for s in ("kavē", "delay", "aizkavē", "late")):
            skills.append("delay_analysis")
        if any(s in prompt_lower for s in ("grafik", "schedule", "laik", "departure")):
            skills.append("schedule_interpretation")
        if any(s in prompt_lower for s in ("salīdzin", "compare", "vs", "labāk")):
            skills.append("route_comparison")
        if any(s in prompt_lower for s in ("vadītāj", "driver", "pieejam", "available")):
            skills.append("driver_availability")
        return list(dict.fromkeys(skills))  # Deduplicate preserving order
```

#### L3 Skill File Format

```markdown
# app/core/agents/skills/transit/delay_analysis.md
---
token_cost: 450
priority: 2
version: "1.0.0"
---

## Delay Analysis Patterns

When analyzing delays, follow this hierarchy:
1. Check GTFS-RT feed freshness — if data >5min old, warn dispatcher
2. Categorize delay severity: <3min minor, 3-10min moderate, >10min severe
3. For severe delays, check adjacent routes for cascading effects
4. Report headway gaps (>2x scheduled interval = service gap)

## Common LLM Mistakes
- Reporting absolute delay instead of delay relative to schedule
- Not distinguishing between "delayed" and "cancelled"
- Mixing up direction_id 0/1 (inbound vs outbound)
```

### Effort: 3 days (within Phase 6 multi-agent implementation)

---

## 2c. Agent Harness — Full BaseAgentService Pattern

### What email-hub does

Email-hub's `BaseAgentService` (`app/ai/agents/base.py`, 468 lines) provides a **complete agent pipeline** with 9 hook points that subclasses override. This eliminates ~80% code duplication while preserving full extensibility:

**Pipeline flow** (8 phases):
```
Phase 0: Route to structured output mode (if supported)
Phase 1: Model resolution (tier → provider → model)
Phase 2: Skill detection + prompt building (L2 + L3 + confidence instruction)
Phase 3: Message construction (multimodal-aware)
Phase 4: LLM call (with fallback chain)
Phase 5: Post-processing (extract HTML + sanitize + agent-specific validation)
Phase 6: Optional CRAG validation loop
Phase 7: QA checks (deterministic, agent-specific)
Phase 8: Response construction (agent-specific schema)
```

**9 Hook points**:

| # | Method | Required | Purpose |
|---|--------|----------|---------|
| 1 | `build_system_prompt()` | MUST | Agent-specific system prompt with L3 skills |
| 2 | `detect_relevant_skills()` | Optional | Keyword → L3 skill file detection |
| 3 | `_build_user_message()` | MUST | Transform request → LLM user message |
| 4 | `_post_process()` | Optional | Agent-specific output validation (default: extract HTML + sanitize) |
| 5 | `_run_qa()` | Optional | Agent-specific QA checks (default: all checks) |
| 6 | `_should_run_qa()` | Optional | Whether to run QA at all |
| 7 | `_build_response()` | MUST | Construct agent-specific response schema |
| 8 | `_get_model_tier()` | Optional | Per-request model tier override |
| 9 | `_process_structured()` | Optional | Structured output mode pipeline |

**Confidence extraction**: Every agent's system prompt ends with `CONFIDENCE_INSTRUCTION` — the LLM appends `<!-- CONFIDENCE: X.XX -->` to its response. Base class extracts this via regex and passes it to response builder.

### What VTV needs (adapted)

The current plan's AI-6.1 `BaseAgentService` is too thin. Here's the full version adapted for VTV:

```python
# app/core/agents/base.py
class BaseAgentService(ABC):
    """Shared pipeline for all VTV domain agents.

    Adapted from email-hub's BaseAgentService.
    Subclasses override hook methods; base handles the pipeline.
    """
    # --- Class-level config (override in subclass) ---
    agent_name: str = ""
    model_tier: str = "standard"      # fast | standard | complex
    max_tokens: int = 4096
    run_qa_default: bool = True
    context_budget: ContextBudget = ContextBudget()

    # --- MUST override ---
    @abstractmethod
    def build_system_prompt(self, relevant_skills: list[str]) -> str: ...

    @abstractmethod
    def _build_user_message(self, request: ChatCompletionRequest) -> str: ...

    # --- CAN override ---
    def detect_relevant_skills(self, prompt: str) -> list[str]:
        """Return L3 skill file names relevant to this prompt."""
        return []

    async def _post_process(self, content: str) -> str:
        """Agent-specific output validation. Default: strip raw JSON, validate format."""
        return content

    async def _run_qa(self, response: str) -> list[ValidationIssue]:
        """Agent-specific QA checks. Default: route/stop existence, language match."""
        return self.validator.validate(response)

    def _should_run_qa(self) -> bool:
        """Whether to run QA checks. Default: self.run_qa_default."""
        return self.run_qa_default

    def _get_model_tier(self, prompt: str) -> str:
        """Per-request tier override. Default: class-level model_tier."""
        return self.model_tier

    # --- Pipeline (DO NOT override) ---
    async def chat(self, request: ChatCompletionRequest, session, redis) -> ChatCompletionResponse:
        prompt = request.messages[-1].content
        prior = request.messages[:-1]

        # Phase 1: Model resolution
        tier = self._get_model_tier(prompt)
        model = resolve_tier_model(tier)

        # Phase 2: Skill detection + prompt building
        relevant_skills = self.detect_relevant_skills(prompt)
        skill_content = load_skills_within_budget(
            relevant_skills, self.context_budget,
            skill_dir=SKILL_DIRS[self.agent_name],
        )
        system_prompt = self.build_system_prompt(relevant_skills)
        system_prompt += f"\n\n{skill_content}" if skill_content else ""
        system_prompt += CONFIDENCE_INSTRUCTION

        # Phase 3: Memory recall + injection
        memory_context = ""
        if settings.memory.enabled:
            memories = await self.memory_service.recall(prompt, agent_type=self.agent_name, limit=5)
            if memories:
                memory_context = self._format_memories(memories)

        # Phase 4: Build full context
        instructions = "\n\n".join(filter(None, [
            skill_content,           # L3 skills (on-demand)
            memory_context,          # Recalled memories
            await self._get_active_skills(),  # Flat skills (existing system, backwards compat)
        ]))

        # Phase 5: Run agent
        history = _build_message_history(prior)
        result = await self.agent.run(
            prompt, message_history=history, deps=self.deps,
            model=model, instructions=instructions,
        )

        # Phase 6: Post-process + confidence extraction
        content = await self._post_process(result.data)
        confidence = extract_confidence(content)

        # Phase 7: Self-correction loop (if enabled)
        if settings.agent.self_correction_enabled and self._should_run_qa():
            corrected = await self.correction_loop.run_with_correction(
                self.agent, prompt, history, self.deps,
            )
            content = corrected.content
            warnings = corrected.warnings
        else:
            warnings = ()

        # Phase 8: Memory bridge — persist episodic memory
        if settings.memory.enabled:
            await self._persist_episode(prompt, content, result)

        # Phase 9: Build response
        return self._build_response(content, model, confidence, warnings)

    async def _persist_episode(self, prompt, response, result):
        """Fire-and-forget: store episodic memory if agent used 2+ tools.

        Adapted from email-hub's HandoffMemoryBridge pattern.
        """
        tool_calls = [tc.tool_name for tc in result.all_messages() if hasattr(tc, 'tool_name')]
        if len(set(tool_calls)) >= 2:
            summary = f"[{self.agent_name}] Query: {prompt[:100]}. Tools: {', '.join(tool_calls)}. Response: {response[:200]}"
            try:
                await self.memory_service.store(
                    content=summary,
                    memory_type="episodic",
                    agent_type=self.agent_name,
                    metadata={"tools": tool_calls, "confidence": extract_confidence(response)},
                )
            except Exception:
                logger.warning("memory.persist_episode_failed", agent=self.agent_name)
```

### Key Differences from Email-Hub

| Aspect | Email-Hub | VTV |
|--------|-----------|-----|
| Framework | Direct LLM calls via provider registry | Pydantic AI Agent (wraps LLM calls) |
| Skills | L3 files in `agent/skills/*.md` | L3 files + existing flat skill system (backwards compat) |
| Streaming | Separate `stream_process()` method | Handled by Pydantic AI's streaming mode |
| QA | 14 domain checks (HTML/CSS/accessibility) | Transit-specific checks (route existence, time, language) |
| CRAG | CRAGMixin for CSS correction loop | Not needed (closed corpus) |
| Sanitization | Per-agent XSS profiles via nh3 | Not needed (text responses, not HTML) |
| Multimodal | Image/audio blocks in messages | Not needed (text-only dispatch queries) |

### Effort: Included in Phase 6 (7 days)

---

## 2d. Memory Bridge — Auto-Persist from Agent Results

### What email-hub does

Email-hub's `HandoffMemoryBridge` (`app/ai/blueprints/handoff_memory.py`) automatically persists agent results as episodic memories:

1. **`format_handoff_content(handoff, run_id)`** — structures the handoff into memory-friendly text: `"[blueprint:run_xyz] Agent 'scaffolder' completed. Decisions: ...; Warnings: ...; Confidence: 0.92"`
2. **`persist_handoff_to_memory(handoff, run_id, project_id)`** — fire-and-forget storage as episodic memory with embedding
3. **Wired as callback** in `BlueprintEngine` constructor — called after every agentic node completes
4. **Failure-safe** — exceptions caught, logged, never crash the pipeline

The bridge also enables **LLM-based intent merging** during compaction: instead of just cosine similarity, similar memories are compared by a lightweight LLM judge that confirms functional equivalence before merging.

### What VTV needs (adapted)

VTV's memory bridge is simpler (no blueprint engine, no inter-agent handoffs), but the core pattern is the same: **auto-persist successful agent interactions as episodic memories, fire-and-forget, failure-safe**.

```python
# app/memory/bridge.py
async def persist_agent_episode(
    agent_name: str,
    prompt: str,
    response: str,
    tools_used: list[str],
    confidence: float | None,
) -> None:
    """Fire-and-forget: store agent interaction as episodic memory.

    Adapted from email-hub's HandoffMemoryBridge.
    Called after successful multi-tool agent runs.
    Never crashes the agent pipeline.
    """
    if len(set(tools_used)) < 2:
        return  # Only persist multi-tool interactions (more valuable)

    content = (
        f"[{agent_name}] Dispatcher asked: {prompt[:150]}. "
        f"Agent used: {', '.join(tools_used)}. "
        f"Response summary: {response[:300]}"
    )
    metadata = {
        "source": "agent",
        "agent_name": agent_name,
        "tools": tools_used,
        "confidence": confidence,
    }

    try:
        async with get_db_context() as session:
            memory_service = MemoryService(session)
            await memory_service.store(
                content=content,
                memory_type="episodic",
                agent_type=agent_name,
                metadata=metadata,
            )
    except Exception:
        logger.warning("memory.bridge.persist_failed", agent=agent_name)
        # Never crash the pipeline
```

**LLM-based intent merging** in compaction (from email-hub):

```python
# app/memory/service.py — enhanced compaction
async def compact(self) -> CompactionResult:
    # Phase 1: Apply decay weights (existing)
    decayed = await self._apply_decay()

    # Phase 2: Intent-aware merging (from email-hub)
    # Find candidates with cosine > 0.85
    candidates = await self.repository.find_similar_pairs(threshold=0.85)
    merged = 0
    for mem_a, mem_b in candidates:
        # Lightweight LLM judge: are these functionally equivalent?
        if await self._judge_equivalence(mem_a.content[:500], mem_b.content[:500]):
            # Keep the one with higher recalled_count (more useful)
            keep = mem_a if mem_a.recalled_count >= mem_b.recalled_count else mem_b
            delete = mem_b if keep == mem_a else mem_a
            await self.repository.delete(delete.id)
            merged += 1

    # Phase 3: Delete low-weight entries
    deleted = await self.repository.delete_below_weight(threshold=0.1)

    return CompactionResult(decayed=decayed, merged=merged, deleted=deleted)
```

### Effort: 1 day (within Phase AI-3)

---

## 3. RAG Architecture for Transit

### Why NOT CRAG

**CRAG** (Corrective RAG) adds a "retrieval evaluator" that grades retrieved documents and falls back to web search if quality is low. This doesn't fit VTV because:

1. **Closed corpus** — VTV's knowledge base is curated internal documents (SOPs, regulations, maintenance bulletins). There's no "web" to fall back to.
2. **Domain specificity** — Transit operations knowledge isn't on the general web. A web search for "Route 22 detour protocol" returns nothing useful.
3. **Latency sensitivity** — Dispatchers need answers in seconds. CRAG's evaluate-then-maybe-search adds 2-4s.
4. **Already addressed** — CRAG's core value (detecting bad retrievals) is better solved by always-on reranking + confidence thresholds for VTV's domain.

### Best RAG Approach for Transit: Agentic RAG with Specialized Retrieval

Transit operations have unique retrieval requirements:
- **Temporal sensitivity** — shift handover notes from yesterday matter, from last month don't
- **Hierarchical documents** — SOPs have sections/subsections that must stay coherent
- **Bilingual** — Latvian + English documents, queries in either language
- **Mixed query types** — some need RAG (SOPs), most don't (transit status)

#### Architecture: 4-Layer RAG Pipeline

```
Query ─── Layer 1: Query Router ──► Skip RAG (transit/vault queries)
              │
              ▼
          Layer 2: Query Enhancement
              ├── HyDE (hypothetical answer → embed)
              ├── Multi-query (rephrase 2-3 ways)
              └── Language detection (LV→EN expansion)
              │
              ▼
          Layer 3: Hybrid Retrieval
              ├── Vector search (pgvector, cosine)
              ├── Fulltext search (tsvector)
              ├── Temporal boost (recent docs weighted higher)
              └── RRF fusion + cross-encoder reranking
              │
              ▼
          Layer 4: Context Assembly
              ├── Parent-child expansion (return parent chunk for context)
              ├── Citation metadata (section headers, page numbers)
              └── Confidence threshold (< 0.3 → "no relevant documents found")
```

#### Layer 1: Query Router (saves ~60% of embedding API calls)

Most VTV queries are transit operations ("which routes are delayed?", "schedule for route 3"). These never need RAG. Only knowledge/policy queries do.

```python
# app/knowledge/router.py
class QueryRouter:
    """Determines if a query needs RAG retrieval.

    Transit status, schedule, and vault queries skip RAG entirely.
    Knowledge, policy, SOP, and procedural queries use RAG.
    """
    RAG_SIGNALS = {"SOP", "procedure", "protocol", "regulation", "policy",
                   "document", "noteikum", "kārtīb", "instrukcij", "reglament"}

    SKIP_SIGNALS = {"route", "maršrut", "delay", "kavē", "schedule", "grafik",
                    "stop", "pietura", "bus", "autobus", "vault", "note"}

    def needs_rag(self, query: str) -> bool:
        rag_score = sum(1 for s in self.RAG_SIGNALS if s.lower() in query.lower())
        skip_score = sum(1 for s in self.SKIP_SIGNALS if s.lower() in query.lower())
        return rag_score > skip_score
```

#### Layer 2: Query Enhancement

**HyDE (Hypothetical Document Embeddings)** — The single highest-impact RAG improvement for VTV. Latvian queries embed poorly with current models (even Jina v3). HyDE generates a hypothetical answer in the document's language, then embeds that instead.

```python
# app/knowledge/hyde.py
class HyDEExpander:
    """Generate hypothetical document for better embedding alignment.

    Especially valuable for Latvian queries where embedding models
    have weaker coverage. Uses fast-tier LLM (cheap, 100-200 tokens).
    """
    HYDE_PROMPT = """Given this question about transit operations, write a short
    paragraph that would appear in an internal document answering it.
    Write in the same language as the question. Be specific and factual.

    Question: {query}
    Hypothetical document paragraph:"""

    async def expand(self, query: str) -> str:
        response = await self.llm.complete(
            self.HYDE_PROMPT.format(query=query),
            model=self.fast_model,  # Cheap model, ~100 tokens
            max_tokens=200,
        )
        return response.text
```

**Cost**: ~$0.001 per query (fast model, 200 tokens). For 50 queries/day = ~$1.50/month.

**Multi-query expansion** (alternative to HyDE for simple queries):
```python
async def multi_query(self, query: str) -> list[str]:
    """Rephrase query 2-3 ways, search all, merge results via RRF."""
    # Only for complex queries. Simple queries use HyDE.
```

#### Layer 3: Retrieval Improvements

**Always-on reranking** (already planned in TODO.md — implement first):
```python
# app/knowledge/service.py — change default
rerank_enabled: bool = True  # Was False. Quality jump is significant.
```

**Temporal boosting** — transit documents decay in relevance:
```python
# app/knowledge/repository.py — add to hybrid_search()
def _temporal_boost(self, doc_created_at: datetime, query_time: datetime) -> float:
    """Boost recent documents. Shift handover notes from today >> last month."""
    age_days = (query_time - doc_created_at).days
    if age_days <= 1:
        return 1.5    # Today's documents boosted 50%
    elif age_days <= 7:
        return 1.2    # This week boosted 20%
    elif age_days <= 30:
        return 1.0    # Normal weight
    else:
        return 0.8    # Older docs slightly penalized (unless evergreen)
```

**RRF weight tuning** — VTV TODO already mentions this. Recommended defaults:
- Keyword-heavy queries (contains stop names, route numbers): fulltext weight 0.7, vector 0.3
- Semantic queries (policy questions, "how do I..."): vector weight 0.7, fulltext 0.3
- Mixed: equal weights (current default)

#### Layer 4: Parent-Child Retrieval

SOPs and regulations have hierarchical structure. When a chunk matches, the surrounding context is critical.

```python
# Changes to app/knowledge/models.py
class DocumentChunk(Base, TimestampMixin):
    # Existing fields...
    parent_chunk_id: Mapped[int | None] = mapped_column(ForeignKey("document_chunks.id"))
    heading_path: Mapped[str | None]     # "SOP > Emergency Procedures > Route Deviation"
    section_type: Mapped[str | None]     # "heading" | "body" | "list" | "table"
```

```python
# Changes to app/knowledge/chunking.py
class SemanticChunker:
    """Replace fixed 512-char splitting with heading-aware chunking.

    - Detects headings (markdown #, PDF section headers, DOCX styles)
    - Creates parent chunks (full section) + child chunks (paragraphs)
    - Child chunks store parent_chunk_id for context expansion
    - Adaptive sizing: 512 for dense tables, 1024 for narrative
    """
```

When a child chunk matches, return the parent chunk as context (larger window, coherent section). This is especially valuable for SOPs where a single paragraph references procedures defined earlier in the same section.

#### Confidence Threshold

```python
# app/knowledge/service.py
CONFIDENCE_THRESHOLD = 0.3  # Below this, return "no relevant documents found"

async def search(self, query: str, ...) -> SearchResult:
    results = await self._hybrid_search(query, ...)
    if not results or results[0].score < self.CONFIDENCE_THRESHOLD:
        return SearchResult(
            chunks=[],
            message="No relevant documents found for this query.",
            confidence=0.0,
        )
    return SearchResult(chunks=results, confidence=results[0].score)
```

### Summary: RAG Approach Comparison for Transit

| Approach | Fit for VTV | Reasoning |
|----------|-------------|-----------|
| **Naive RAG** | Current state | Works but misses context, weak on Latvian |
| **CRAG** | Not needed | No web fallback makes sense; closed corpus |
| **Agentic RAG** | Best fit | Query routing skips RAG for transit queries, HyDE fixes Latvian embedding gap |
| **GraphRAG** | Overkill | Transit docs don't have complex entity relationships |
| **Self-RAG** | Partial fit | Confidence thresholding is useful, full self-reflection adds latency |
| **Raptor/RAPTOR** | Interesting but premature | Recursive abstractive tree useful for large doc collections; VTV's corpus is manageable |

**Recommended: Agentic RAG (query routing + HyDE + always-on reranking + parent-child + temporal boost)**

### Effort: 8-10 days

---

## 4. Bounded Self-Correction

### What email-hub does

Blueprint engine runs QA checks after each agentic node. If QA fails:
1. Increment iteration counter
2. Route to appropriate fixer agent with QA failure context injected
3. Max 2 self-correction rounds
4. If still failing → route to `needs_review` (human escalation)
5. Hard limit: MAX_TOTAL_STEPS = 25

### What VTV needs (adapted)

VTV already has `validation.py` that checks response plausibility (route numbers, delays, diacritics). The missing piece is **recovery**: when validation fails, the agent currently returns the response anyway with a footnote warning. Instead, it should retry with the validation failure injected as context.

#### Implementation

```python
# app/core/agents/correction.py
MAX_SELF_CORRECTION_ROUNDS = 1  # Transit needs fast responses; 1 retry max

class SelfCorrectionLoop:
    """Bounded self-correction for agent responses.

    After agent.run(), run deterministic QA checks. If checks fail,
    retry once with failure context injected. If still failing,
    return response with warnings (current behavior).
    """
    async def run_with_correction(
        self,
        agent: Agent,
        prompt: str,
        history: list[ModelMessage],
        deps: UnifiedDeps,
    ) -> CorrectedResult:
        for iteration in range(MAX_SELF_CORRECTION_ROUNDS + 1):
            result = await agent.run(prompt, message_history=history, deps=deps)

            issues = self.validator.validate(result.data)
            if not issues:
                return CorrectedResult(content=result.data, issues=[], iteration=iteration)

            if iteration < MAX_SELF_CORRECTION_ROUNDS:
                # Inject failure context and retry
                correction_prompt = self._build_correction_prompt(prompt, result.data, issues)
                history = history + [
                    ModelMessage.user(prompt),
                    ModelMessage.assistant(result.data),
                    ModelMessage.user(correction_prompt),
                ]
                prompt = correction_prompt
            else:
                # Max retries reached — return with warnings (current behavior)
                return CorrectedResult(
                    content=result.data,
                    issues=issues,
                    iteration=iteration,
                    warnings=[f"Validation issue: {i.description}" for i in issues],
                )

    def _build_correction_prompt(self, original: str, response: str, issues: list[Issue]) -> str:
        issue_text = "\n".join(f"- {i.description}" for i in issues)
        return (
            f"Your previous response had these issues:\n{issue_text}\n\n"
            f"Please correct your response to the original question. "
            f"Original question: {original}"
        )
```

#### QA Checks to Add (beyond current validation.py)

| Check | What it catches | Deterministic? |
|-------|----------------|----------------|
| Route existence | Agent mentions route 99 (doesn't exist in Riga) | Yes — check against GTFS static cache |
| Stop existence | Agent mentions stop that's not in DB | Yes — check against stop cache |
| Time consistency | "Departures at 25:30" or past times for future queries | Yes — regex + time parsing |
| Citation grounding | Agent cites document that wasn't in search results | Yes — check tool call results |
| Language match | Query in Latvian, response in English | Yes — simple heuristic |
| Stale data warning | GTFS-RT data older than cache TTL | Yes — check feed timestamps |

### Effort: 3-4 days

---

## 5. Evaluation Framework

### What email-hub does

Per-agent evaluation pipeline:
1. **Synthetic data** — 10-14 test cases per agent, targeting failure-prone dimensions
2. **LLM judge** — Binary pass/fail + 5 quality criteria per agent
3. **Traces** — JSONL: input, output, timing, errors
4. **Calibration** — TPR/TNR alignment (target >= 0.85 / >= 0.80)
5. **Regression** — Per-criterion tolerance (+/-3pp allowed between runs)

### What VTV needs (adapted)

#### Synthetic Test Cases per Domain

**Transit Agent (15 cases)**:
```yaml
# app/core/agents/evals/cases/transit.yaml
- id: transit_simple_status
  prompt: "Kuri maršruti kavējas?"
  expected_tools: ["query_bus_status"]
  criteria:
    - uses_latvian_response: true
    - mentions_specific_routes: true
    - includes_delay_duration: true

- id: transit_diacriticless
  prompt: "marsruti kas kaveejas"
  expected_tools: ["query_bus_status"]
  criteria:
    - understands_diacriticless_input: true  # Must not fail on missing diacritics

- id: transit_cross_tool
  prompt: "Which stops on route 22 have the worst delays this week?"
  expected_tools: ["query_bus_status", "search_stops"]
  criteria:
    - combines_data_sources: true
    - provides_specific_stops: true

- id: transit_nonexistent_route
  prompt: "What's the schedule for route 999?"
  expected_tools: ["get_route_schedule"]
  criteria:
    - handles_not_found_gracefully: true
    - does_not_hallucinate_schedule: true
```

**Knowledge Agent (10 cases)**:
```yaml
- id: knowledge_sop_query
  prompt: "What's the procedure when a bus breaks down on route?"
  expected_tools: ["search_knowledge_base"]
  criteria:
    - cites_source_document: true
    - provides_actionable_steps: true

- id: knowledge_no_docs
  prompt: "What's the company's policy on employee pets?"
  expected_tools: ["search_knowledge_base"]
  criteria:
    - admits_no_relevant_docs: true   # Must say "I don't have information" not hallucinate
    - does_not_hallucinate_policy: true
```

#### LLM Judge

```python
# app/core/agents/evals/judge.py
TRANSIT_JUDGE_PROMPT = """You are evaluating a transit operations AI assistant response.

Rate the response on these 5 criteria (pass/fail):

1. **Factual accuracy** — Route numbers, stop names, and times match the tool call results
2. **Language correctness** — Response is in the correct language with proper Latvian diacritics
3. **Actionability** — Response gives the dispatcher enough information to act
4. **Citation quality** — Sources are cited when using knowledge base documents
5. **Completeness** — All parts of the question are addressed

User query: {query}
Tool calls made: {tool_calls}
Tool results: {tool_results}
Agent response: {response}

For each criterion, respond with PASS or FAIL and a one-line explanation.
"""
```

#### Eval Runner

```python
# app/core/agents/evals/runner.py
class EvalRunner:
    """Run synthetic test cases against agent, collect traces, judge results."""

    async def run_suite(self, suite: str = "transit") -> EvalReport:
        cases = self._load_cases(suite)
        traces = []
        for case in cases:
            trace = await self._run_case(case)
            traces.append(trace)

        # Write traces for judge
        self._write_traces(traces, f"evals/traces/{suite}_{datetime.now().isoformat()}.jsonl")

        # Run LLM judge
        judgments = await self._judge_traces(traces, suite)

        return EvalReport(
            suite=suite,
            total=len(cases),
            passed=sum(1 for j in judgments if j.overall_pass),
            criteria_breakdown=self._aggregate_criteria(judgments),
        )
```

#### Integration with CI

```bash
# Makefile addition
eval:           ## Run agent evaluation suite (requires LLM API key)
	python -m app.core.agents.evals.runner --suite transit --suite knowledge
eval-judge:     ## Judge most recent eval traces
	python -m app.core.agents.evals.judge_runner --traces evals/traces/latest/
```

### Effort: 5-6 days

---

## 6. Implementation Phases

### Phase 1: RAG Quick Wins + Always-On Reranking (3 days)

**Why first**: Immediate quality improvement, no architectural changes, already planned in TODO.md.

- [x] Increase chunk overlap 50 → 100 chars
- [x] Expand search result truncation 500 → 1500 chars
- [ ] Make cross-encoder reranking default (`rerank_enabled=True`)
- [ ] Add temporal boost to hybrid search scoring
- [ ] Add confidence threshold (< 0.3 → "no relevant docs")
- [ ] Tune RRF weights by query type

**Files**: `app/knowledge/service.py`, `app/knowledge/repository.py`, `app/knowledge/chunking.py`

### Phase 2: Query Router + HyDE (4 days)

**Why second**: Query routing saves 60% of unnecessary embedding calls. HyDE fixes the biggest RAG quality issue (Latvian embedding weakness).

- [ ] Implement `QueryRouter` — detect if query needs RAG
- [ ] Implement `HyDEExpander` — hypothetical document generation for Latvian queries
- [ ] Add language detection for bilingual query expansion
- [ ] Integrate router into `AgentService.chat()` flow
- [ ] Add metrics: queries routed to RAG vs skipped

**Files**: `app/knowledge/router.py` (new), `app/knowledge/hyde.py` (new), `app/core/agents/service.py`

### Phase 3: Persistent Memory (5 days)

**Why third**: Enables the agent to learn from usage. Foundation for multi-agent (agents share memory).

- [ ] Create `app/memory/` vertical slice (models, repository, service, schemas, routes)
- [ ] Alembic migration for `memory_entries` table with pgvector index
- [ ] Memory recall before agent.run() (top 5 relevant memories injected as context)
- [ ] Episodic memory storage after successful multi-tool queries
- [ ] Background compaction task (daily, 03:00 UTC)
- [ ] Auto-promotion: episodic → procedural after 3+ recalls
- [ ] REST endpoints for memory inspection (admin-only)

**Files**: `app/memory/` (new vertical slice), `app/core/agents/service.py`

### Phase 4: Semantic Chunking + Parent-Child Retrieval (4 days)

**Why fourth**: Builds on Phase 1-2 RAG improvements. Requires migration to re-chunk existing documents.

- [ ] Implement heading-aware semantic chunker (replace recursive splitter)
- [ ] Add `parent_chunk_id`, `heading_path`, `section_type` to DocumentChunk
- [ ] Parent-child retrieval: matched child → return parent for context
- [ ] Re-chunk existing documents (migration script)
- [ ] Adaptive chunk sizing (512 for tables/lists, 1024 for narrative)

**Files**: `app/knowledge/chunking.py`, `app/knowledge/models.py`, `app/knowledge/repository.py`

### Phase 5: Bounded Self-Correction (3 days)

**Why fifth**: Requires stable RAG and memory to be meaningful. Catches factual errors before they reach dispatchers.

- [ ] Implement `SelfCorrectionLoop` (max 1 retry for transit, latency-sensitive)
- [ ] Add QA checks: route/stop existence, time consistency, citation grounding
- [ ] Inject failure context on retry
- [ ] Metrics: correction rate, retry success rate

**Files**: `app/core/agents/correction.py` (new), `app/core/agents/service.py`, `app/core/agents/validation.py`

### Phase 6: Multi-Agent with Router (7 days)

**Why sixth**: Biggest architectural change. Requires memory (Phase 3) for shared context between agents. Requires stable RAG (Phases 1-4) for knowledge agent.

- [ ] Implement `BaseAgentService` shared pipeline
- [ ] Create `TransitAgent` (5 tools, transit-focused system prompt)
- [ ] Create `KnowledgeAgent` (1 tool, citation-focused system prompt)
- [ ] Create `VaultAgent` (4 tools, note-management system prompt)
- [ ] Implement `AgentRouter` (heuristic + signals)
- [ ] Keep `UnifiedAgent` as fallback for cross-domain queries
- [ ] Integrate with existing tier routing (fast/standard/complex per domain)
- [ ] Update CMS chat to handle agent metadata in responses

**Files**: `app/core/agents/base.py` (refactor), `app/core/agents/router.py` (new), `app/core/agents/agents/` (new directory with transit.py, knowledge.py, vault.py)

### Phase 7: Evaluation Framework (5 days)

**Why last**: Needs all other systems stable to produce meaningful evaluations. Creates regression baselines for future changes.

- [ ] Create synthetic test cases (15 transit, 10 knowledge, 5 vault)
- [ ] Implement eval runner with trace collection
- [ ] Implement LLM judge with domain-specific criteria
- [ ] Add `make eval` and `make eval-judge` commands
- [ ] Generate initial baselines
- [ ] Document evaluation methodology

**Files**: `app/core/agents/evals/` (new directory), `Makefile`

---

## 7. Cost & Effort Estimates

### Development Effort

| Phase | Days | Dependencies |
|-------|------|-------------|
| 1. RAG Quick Wins | 3 | None |
| 2. Query Router + HyDE | 4 | None (can parallel with Phase 1) |
| 3. Persistent Memory + Bridge | 6 | None (can parallel with Phases 1-2) |
| 4. Semantic Chunking | 4 | Phase 1 |
| 5. Self-Correction | 3 | Phases 1-2 |
| 6. Multi-Agent + L3 Skills + Harness | 9 | Phase 3 |
| 7. Evaluation | 5 | Phases 1-6 |
| **Total** | **~34 days** | Phases 1-3 can run in parallel |

### Infrastructure Cost (monthly, at 50 queries/day)

| Component | Current | After Changes | Delta |
|-----------|---------|--------------|-------|
| Embedding API (query) | ~$2/mo | ~$1.50/mo (query routing skips 60%) | -$0.50 |
| HyDE LLM calls | $0 | ~$1.50/mo (fast model, 200 tokens/query) | +$1.50 |
| Reranking (cross-encoder) | $0 (optional) | ~$0 (local model) | $0 |
| Memory storage (pgvector) | $0 | ~$0.10/mo (shared DB) | +$0.10 |
| Self-correction retries | $0 | ~$1.50/mo (est. 15% retry rate) | +$1.50 |
| **Total** | ~$2/mo | ~$4.60/mo | +$2.60/mo |

### Quality Impact (expected)

| Metric | Current (est.) | After (target) |
|--------|---------------|----------------|
| RAG retrieval relevance | ~65% | ~85% (HyDE + reranking + parent-child) |
| Latvian query accuracy | ~70% | ~88% (HyDE + diacritics handling) |
| Tool selection accuracy | ~80% | ~92% (domain-specific agents) |
| Response correction rate | 0% (no retry) | ~15% caught and fixed |
| Knowledge "I don't know" accuracy | ~50% (hallucination risk) | ~90% (confidence threshold) |

---

## Appendix A: What NOT to Port from Email-Hub

| Email-Hub Feature | Why Not for VTV |
|-------------------|----------------|
| **Full BlueprintEngine state machine** | VTV queries don't chain between agents. Simple router is sufficient. |
| **AgentHandoff with full metadata** | Overkill for single-turn Q&A. Lightweight `AgentResult` is enough. |
| ~~**L1/L2/L3 skill hierarchy**~~ | **ADOPTED** — see Section 6 below. Progressive skill loading with token budgets is valuable for VTV's domain agents. |
| **CRAG (web fallback)** | Closed corpus, no web content to fall back to. |
| **Cognee knowledge graph** | Transit docs don't have complex entity relationships worth graphing. |
| **PII redaction pipeline** | VTV handles internal ops data, not customer PII. Standard logging controls suffice. |
| **Multimodal agent context** | No image/audio inputs needed for transit dispatch queries. |
| **Design-sync / Figma integration** | Email-specific, not relevant. |
| **Visual QA (ODiff + VLM)** | Email-specific rendering validation, not applicable. |

## Appendix B: VTV-Specific RAG Considerations

### Why Temporal Awareness Matters for Transit

Transit documents have dramatically different relevance lifecycles:

| Document Type | Relevance Window | Treatment |
|---------------|-----------------|-----------|
| Shift handover notes | 24 hours | Aggressive temporal boost, fast decay |
| Incident reports | 1-2 weeks | Moderate boost when recent |
| Construction alerts | Duration of construction | Boost during active period |
| Seasonal schedules | 3-4 months | Boost during active season |
| SOPs | Years | Evergreen, no decay |
| Regulations | Until superseded | Evergreen, version-tracked |

### Why HyDE is the #1 RAG Improvement for VTV

Latvian is a low-resource language for embedding models. Even Jina v3 (best multilingual option) has weaker coverage for Latvian than for English or German. HyDE sidesteps this by:

1. Dispatcher asks in Latvian: "Ko darīt, ja autobuss sabojājas maršrutā?"
2. LLM generates hypothetical answer (in Latvian): "Ja autobuss sabojājas maršrutā, dispečeram jāsazinās ar depo..."
3. This hypothetical answer is embedded — it's closer to actual document language than the raw question
4. Retrieval quality improves because we're matching document-like text against documents

The cost is minimal ($0.001/query with fast model) and the quality improvement for Latvian queries is expected to be 15-20%.

## Appendix C: File Path Reference

### New Files to Create

```
app/memory/                          # Phase 3: Persistent memory
├── __init__.py
├── models.py                        # MemoryEntry SQLAlchemy model
├── schemas.py                       # Pydantic request/response
├── repository.py                    # DB operations
├── service.py                       # Store, recall, compact (with LLM intent merging), promote
├── bridge.py                        # Phase 3: Memory bridge (auto-persist, fire-and-forget)
├── routes.py                        # Admin endpoints
└── tests/

app/knowledge/router.py              # Phase 2: Query router
app/knowledge/hyde.py                 # Phase 2: HyDE expander

app/core/agents/correction.py        # Phase 5: Self-correction loop
app/core/agents/base.py              # Phase 6: Full BaseAgentService harness (9 hook points)
app/core/agents/context_budget.py    # Phase 6: Per-agent token budgets (from email-hub)
app/core/agents/skill_loader.py      # Phase 6: L3 skill loader with priority gating
app/core/agents/router.py            # Phase 6: Domain agent router
app/core/agents/agents/              # Phase 6: Domain-specific agents
├── __init__.py
├── transit.py
├── knowledge.py
└── vault.py
app/core/agents/skills/              # Phase 6: L3 skill files per agent
├── transit/
│   ├── delay_analysis.md            # P2, 450 tokens
│   ├── schedule_interpretation.md   # P2, 400 tokens
│   ├── route_comparison.md          # P3, 350 tokens
│   ├── driver_availability.md       # P3, 300 tokens
│   └── adherence_reporting.md       # P3, 350 tokens
├── knowledge/
│   ├── sop_retrieval.md             # P1, 500 tokens (always loaded)
│   ├── regulation_interpretation.md # P2, 450 tokens
│   ├── shift_handover.md            # P3, 300 tokens
│   └── incident_response.md         # P2, 400 tokens
└── vault/
    ├── search_patterns.md           # P2, 300 tokens
    ├── bulk_operations.md           # P3, 250 tokens
    └── folder_organization.md       # P3, 250 tokens

app/core/agents/evals/               # Phase 7: Evaluation
├── __init__.py
├── runner.py
├── judge.py
├── judge_runner.py
├── regression.py
├── cases/
│   ├── transit.yaml
│   ├── knowledge.yaml
│   └── vault.yaml
└── judges/
    ├── transit_judge.py
    └── knowledge_judge.py
```

### Existing Files to Modify

```
app/knowledge/service.py             # Phases 1-2: Reranking default, confidence threshold, HyDE integration
app/knowledge/repository.py          # Phase 1: Temporal boost, RRF tuning
app/knowledge/chunking.py            # Phase 4: Semantic chunker
app/knowledge/models.py              # Phase 4: Parent-child fields
app/core/agents/service.py           # Phases 2-3, 5-6: Memory injection, correction loop, agent routing
app/core/agents/validation.py        # Phase 5: Additional QA checks
app/core/agents/agent.py             # Phase 6: Refactor to domain agents
Makefile                             # Phase 7: eval commands
```
