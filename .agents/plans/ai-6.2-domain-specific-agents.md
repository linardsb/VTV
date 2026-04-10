# Plan: AI-6.2 Domain-Specific Agents (Transit / Knowledge / Vault)

## Context

The current `AgentService` registers **all 11 tools** at `Agent` construction time (`app/core/agents/agent.py:121-142`). Every chat request — even a pure vault rename — pays for ~3000 token tool-docstring footprint and the LLM has to discriminate across 11 unrelated tools. AI-6.1 (commit `88b4512`) extracted `BaseAgentService` (`app/core/agents/base.py`) with 11 hook points so domain agents can plug in different tool subsets without forking the orchestration pipeline.

This task creates three concrete subclasses, each with its own focused `Agent[UnifiedDeps, str]` instance, system prompt, and minimal hook overrides. The existing `AgentService` is preserved as the **unified** fallback so today's `/v1/chat/completions` stays bit-identical when no agent is selected. Auto-routing is out of scope (deferred to AI-6.3).

## Security Context Assessment

- **CTX-AGENT** — three new tool subsets, three new system prompts. Prompt-injection logging already in base. None of the new agents get `manage_agent_skills` (no agent-created artifacts).
- **CTX-RBAC** — `chat_completions` already has `Depends(get_current_user)` + `@limiter.limit("10/minute")` + daily quota. The selector must NOT widen access; same auth dep, same rate limit.
- **CTX-INPUT** — the `agent` selector value is constrained via `Literal["unified","transit","knowledge","vault"]` so Pydantic rejects arbitrary strings before reaching the service layer.

CTX-AUTH / CTX-FILE / CTX-INFRA — not applicable.

## Research Summary

### `BaseAgentService` extension contract (`app/core/agents/base.py`)

- `chat()` (line 151) owns the 12-phase pipeline. Subclasses override hooks; the base never needs to change.
- `_execute` (line 332) is the **only** hook a subclass MUST override. Returns `_PipelineOutcome(response_text, warnings, messages)`.
- `agent_name: str` class attr (line 149) — flows into `persist_agent_episode()` so each domain's memories are tagged distinctly.
- `_persist_episode()` helper (line 460) — subclasses call from `_execute` (the base does NOT call it; persist policy varies per branch).
- Hook defaults: `_apply_rag_routing` no-op, `detect_relevant_skills` returns `""`, `_recall_memories_block` returns `""`, `build_system_prompt` delegates to `build_instructions_with_skills`, `_preload_validation_cache` returns `None`, `_run_qa` runs `validate_transit_response` (transit-specific — **must override** for non-transit agents).

### Reference subclass — `AgentService` (`app/core/agents/service.py`)

- Stores `self._deps: UnifiedDeps` from `create_unified_deps()` (line 100). Same `UnifiedDeps` works for all three new agents.
- Wires `SelfCorrectionLoop` if enabled (line 102).
- Module-level `__all__` (line 64) explicitly re-exports every patched symbol — **the new modules must follow the same pattern** so per-agent tests can `patch("app.core.agents.agents.<x>.<name>")`.
- `_execute` branches on `tier`: complex → `get_complex_pipeline(agent, deps)`; standard → `SelfCorrectionLoop.run_with_correction(agent, ...)`; otherwise plain `agent.run(...)`. Each branch persists memory differently.
- `close()` swallows `RuntimeError` from already-closed event loops (anti-pattern #16).

### Tool inventory + paths

| Domain | Function | File |
|---|---|---|
| Transit | `query_bus_status` | `app/core/agents/tools/transit/query_bus_status.py:55` |
| Transit | `get_route_schedule` | `app/core/agents/tools/transit/get_route_schedule.py` |
| Transit | `search_stops` | `app/core/agents/tools/transit/search_stops.py` |
| Transit | `get_adherence_report` | `app/core/agents/tools/transit/get_adherence_report.py` |
| Transit | `check_driver_availability` | `app/core/agents/tools/transit/check_driver_availability.py:32` |
| Knowledge | `search_knowledge_base` | `app/core/agents/tools/knowledge/search_knowledge.py:31` |
| Vault | `obsidian_query_vault` | `app/core/agents/tools/obsidian/query_vault.py:68` |
| Vault | `obsidian_manage_notes` | `app/core/agents/tools/obsidian/manage_notes.py:169` |
| Vault | `obsidian_manage_folders` | `app/core/agents/tools/obsidian/manage_folders.py:75` |
| Vault | `obsidian_bulk_operations` | `app/core/agents/tools/obsidian/bulk_operations.py:128` |
| Skills | `manage_agent_skills` | `app/core/agents/tools/skills/manage_skills.py:24` |

The **skills tool stays in unified `AgentService` only** — none of the three domain agents get it (per user spec).

### Routes & DI

- `app/core/agents/routes.py:35-67` — `chat_completions` calls `service.chat(body)` after quota check. `service` is injected via `Depends(get_agent_service)` returning the singleton `AgentService`.
- `app/main.py:30,185` — single `agent_router` registered. We do NOT add new routers; we reuse this one.
- `app/main.py` — `close_agent_service()` is called from the lifespan shutdown handler (find via grep, add `close_all_agents()` next to it).

### Configuration

All settings the new agents need are already on `app.core.config.Settings`: `memory_enabled`, `memory_max_recall_results`, `memory_recall_min_score`, `memory_context_injection_limit`, `knowledge_router_enabled`, `agent_self_correction_enabled`, `agent_max_correction_rounds`, `llm_*`. **No new settings.**

### Reusable building blocks

- **Memory recall** — `service.py:144-183` is the canonical impl. `TransitAgent`/`KnowledgeAgent`/`VaultAgent` will each duplicate it with a `# NOTE: shared with X; extract on AI-6.2.1` comment. Three-Feature Rule says extract on the third use, but we are deferring that to a follow-up to keep this diff focused.
- **Skills loader** — `service.py:130-139`. Same NOTE pattern.
- **GTFS validation cache** — only `TransitAgent` overrides `_preload_validation_cache` and `_run_qa`. Knowledge / Vault inherit base defaults (None / no QA — but they MUST override `_run_qa` to return `[]`, otherwise the base default calls `validate_transit_response` on non-transit responses).

## Test Landscape

### Existing structure (`app/core/agents/tests/`)

- **`test_base.py`** (382 lines) — **reference** for new domain agents. `_FakeAgentService(BaseAgentService)` (line 38) overrides only `_execute`; tests drive `chat()` via `_make_request("...")`. Pattern to follow: subclass directly, override only what's tested.
- **`test_service.py`** (281 lines) — **reference** for testing a concrete agent with mocked deps. `_create_service()` helper (line 22) patches `create_unified_deps` with `AsyncMock` HTTP clients. Each new agent test file should have an analogous `_create_<x>_agent_service()` helper.
- **`test_correction.py`**, **`test_metrics.py`** — `_fake_agent()` MagicMock pattern for `agent.run` mocking; reuse for TransitAgent's correction-loop branch.

### Fixtures available

- Root `conftest.py`: `client`, `mock_settings`, `_clear_auth_cache` (autouse).
- **No agent-specific conftest.** Use plain helper functions, not pytest fixtures.

### LLM mocking

- `pydantic_ai.models.test.TestModel` for tests that exercise real `agent.run`.
- **Required at top of every new test file:** `from pydantic_ai import models; models.ALLOW_MODEL_REQUESTS = False` — prevents accidental real API calls in CI.
- For unit tests of `_execute`, mock the module-level singleton via `patch("app.core.agents.agents.<x>.<x>_agent.run", new=AsyncMock(...))`.

## Type Check Baseline (pre-AI-6.2)

| Tool | Errors | Notes |
|---|---|---|
| **Pyright** | 5 | All in `pipeline.py:47,49,136 (×2)` and `tools/transit/client.py:193`. `base.py` and `service.py` are clean. |
| **Mypy** | 3 | All in `tools/transit/static_store.py:149,150` and `pipeline.py:136`. |
| **Ruff** | 0 | Clean. |
| **Tests** | **340 passed** in ~12.7s. |

**Acceptance:** pyright ≤ 5, mypy ≤ 3, ruff clean, all 340 existing tests still pass + ~45 new tests added (15 per domain agent + 3 route regressions = 48).

## Files to Create / Modify

| Action | File | Purpose |
|---|---|---|
| CREATE | `app/core/agents/agents/__init__.py` | Package marker. |
| CREATE | `app/core/agents/agents/transit.py` | `TransitAgent(BaseAgentService)` + `transit_agent` Pydantic AI singleton + `TRANSIT_SYSTEM_PROMPT` + `__all__`. |
| CREATE | `app/core/agents/agents/knowledge.py` | `KnowledgeAgent(BaseAgentService)` + `knowledge_agent` singleton + `KNOWLEDGE_SYSTEM_PROMPT` + `__all__`. |
| CREATE | `app/core/agents/agents/vault.py` | `VaultAgent(BaseAgentService)` + `vault_agent` singleton + `VAULT_SYSTEM_PROMPT` + `__all__`. |
| CREATE | `app/core/agents/agents/registry.py` | `get_agent_by_name(name) -> BaseAgentService`, `close_all_agents()`. Owns per-name singletons. |
| CREATE | `app/core/agents/tests/test_transit_agent.py` | 15 tests. |
| CREATE | `app/core/agents/tests/test_knowledge_agent.py` | 15 tests. |
| CREATE | `app/core/agents/tests/test_vault_agent.py` | 15 tests. |
| UPDATE | `app/core/agents/schemas.py` | Add `AgentName = Literal[...]` and `agent: AgentName = "unified"` field on `ChatCompletionRequest`. |
| UPDATE | `app/core/agents/routes.py` | Resolve agent via `get_agent_by_name(body.agent)` instead of hardcoded `Depends(get_agent_service)`. |
| UPDATE | `app/core/agents/tests/test_routes.py` | Add 3 selector regression tests. |
| UPDATE | `app/main.py` | Add `await close_all_agents()` to shutdown lifespan handler. |
| UPDATE | `app/core/agents/CLAUDE.md` | Mark AI-6.2 done in Planned Improvements; document the `agent` selector. |

## Implementation Steps

### Step 1 — Add `AgentName` and `agent` selector to schemas

**File:** `app/core/agents/schemas.py`. Add at module top after `from typing import Literal`:

```python
AgentName = Literal["unified", "transit", "knowledge", "vault"]
```

Extend `ChatCompletionRequest` with `agent: AgentName = "unified"` after the `model` field. Strict mode (`ConfigDict(strict=True)`) is already on the class — Pydantic will reject any other string with 422 before reaching the service layer (CTX-INPUT satisfied).

**Validation:** `uv run ruff format app/core/agents/schemas.py && uv run ruff check app/core/agents/schemas.py && uv run pyright app/core/agents/schemas.py && uv run mypy app/core/agents/schemas.py`

### Step 2 — Create the `agents/` package

`app/core/agents/agents/__init__.py` — single docstring line, nothing else.

**Validation:** `uv run ruff check app/core/agents/agents/`

### Step 3 — Create `TransitAgent`

**File:** `app/core/agents/agents/transit.py`

This subclass mirrors `AgentService` (`app/core/agents/service.py`) **structure verbatim** but with:
- A new module-level `transit_agent: Agent[UnifiedDeps, str]` factory that registers ONLY the 5 transit tools.
- A new `TRANSIT_SYSTEM_PROMPT` constant. Lift the LANGUAGE RULES, LATVIAN TRANSIT GLOSSARY, LATVIAN INPUT UNDERSTANDING, and RESPONSE FORMAT RULES sections from `agent.py:28-103`. **Drop** the KNOWLEDGE BASE BEHAVIOR and CITATION RULES sections (transit agent has no knowledge tool). **Drop** vault references.
- `agent_name: str = "transit_agent_v2"` (NOT `"transit_agent"` — that name is owned by `AgentService` to avoid memory store contamination).
- `_apply_rag_routing` overridden to set `self._deps.rag_enabled = False` (no RAG without the knowledge tool).
- `detect_relevant_skills`, `_recall_memories_block`, `build_system_prompt` — **lifted verbatim from `service.py:130-194`** with `# NOTE: duplicated from AgentService; extract on AI-6.2.1` comments.
- `_preload_validation_cache` overridden — same as `service.py:199-208`.
- `_execute` overridden — same three-branch dispatch as `service.py:213-298` but invokes `transit_agent` (the new module-level singleton), not the all-tools `agent` from `app/core/agents/agent.py`.
- `_run_qa` overridden — same as `service.py:303-323`.
- `close()` overridden — same as `service.py:356-365` with `try/except RuntimeError: pass` (anti-pattern #16).

`__all__` MUST re-export every symbol the test suite will patch:
```python
__all__ = [
    "TRANSIT_SYSTEM_PROMPT", "TransitAgent", "AsyncSessionLocal",
    "MemoryService", "SelfCorrectionLoop", "build_instructions_with_skills",
    "get_settings", "logger", "needs_rag", "persist_agent_episode",
    "transit_agent", "validate_transit_response",
]
```

Imports come from the same modules as `service.py` (`app.core.agents.agent` → `build_instructions_with_skills`, `app.core.agents.correction`, `app.core.agents.pipeline`, `app.core.agents.tools.transit.deps`, `app.core.agents.tools.transit.static_store`, `app.core.agents.validation`, `app.knowledge.router`, `app.memory.bridge`, `app.memory.schemas`, `app.memory.service`, `app.skills.service`, `app.core.database`).

**Validation:** `uv run ruff format app/core/agents/agents/transit.py && uv run ruff check app/core/agents/agents/transit.py && uv run pyright app/core/agents/agents/transit.py && uv run mypy app/core/agents/agents/transit.py`

### Step 4 — Create `KnowledgeAgent`

**File:** `app/core/agents/agents/knowledge.py`

Much simpler than `TransitAgent` — only one tool, no GTFS cache, no correction loop, no complex-tier branching.

- Module-level `knowledge_agent: Agent[UnifiedDeps, str]` factory registering `[search_knowledge_base]` only.
- `KNOWLEDGE_SYSTEM_PROMPT`: ~30 lines covering tool usage, grounding rules ("If search returns 'No relevant documents found', say so honestly. Do NOT fabricate. If you don't know, say 'I don't know' explicitly"), citation format (`[title](/lv/documents/{id})` and `/en/...`), 'Sources' list at end of every cited response, language defaults (Latvian first).
- `agent_name: str = "knowledge_agent"`.
- `__init__` constructs `UnifiedDeps` via `create_unified_deps()`. **No** `SelfCorrectionLoop`.
- `_apply_rag_routing` — always sets `self._deps.rag_enabled = True`.
- `_recall_memories_block` — duplicated from `service.py:144-183` with `# NOTE` comment.
- `build_system_prompt` — delegates to `build_instructions_with_skills` (so tests can patch via `patch("app.core.agents.agents.knowledge.build_instructions_with_skills")`).
- `_execute` — single branch: `result = await knowledge_agent.run(...)`, then `persist_agent_episode(agent_name=self.agent_name, ...)`. Returns `_PipelineOutcome(response_text=result.output, warnings=[], messages=msgs)`. Note `warnings=[]` (NOT `None`) so `_post_process` does NOT call `_run_qa`.
- `_run_qa` — explicit override returning `[]` (defensive in case future base changes alter `_post_process` flow).
- `_preload_validation_cache` — inherits base default (`None`).
- `close()` — same RuntimeError-swallowing pattern as `TransitAgent`.

`__all__`: `["KNOWLEDGE_SYSTEM_PROMPT", "KnowledgeAgent", "AsyncSessionLocal", "MemoryService", "build_instructions_with_skills", "get_settings", "knowledge_agent", "logger", "persist_agent_episode"]`

**Validation:** as Step 3.

### Step 5 — Create `VaultAgent`

**File:** `app/core/agents/agents/vault.py`

Structurally identical to `KnowledgeAgent` with these substitutions:

- `vault_agent` factory registers `[obsidian_query_vault, obsidian_manage_notes, obsidian_manage_folders, obsidian_bulk_operations]`.
- `agent_name: str = "vault_agent"`.
- `_apply_rag_routing` — sets `self._deps.rag_enabled = False`.
- `VAULT_SYSTEM_PROMPT` MUST cover:
  - Tool usage hints (use `obsidian_query_vault` first to find notes; `obsidian_bulk_operations` always with `dry_run=True` first).
  - Frontmatter conventions: YAML on every note, fields `title`/`tags`/`created`/`updated`, tags in kebab-case (e.g. `transit-ops`).
  - **Safe deletion clause:** "For ANY destructive operation (delete folder, bulk delete, bulk move), respond with a plain-text preview and ask 'Confirm deletion? (yes/no)' before passing `confirm=true`. Never delete on the first turn unless the user already used 'confirm' or 'yes'." This is the security-critical text that test #13 will assert on.
  - Language defaults (Latvian first).

`__all__`: `["VAULT_SYSTEM_PROMPT", "VaultAgent", "AsyncSessionLocal", "MemoryService", "build_instructions_with_skills", "get_settings", "vault_agent", "logger", "persist_agent_episode"]`

**Validation:** as Step 3.

### Step 6 — Create the registry

**File:** `app/core/agents/agents/registry.py`

```python
"""Per-agent singleton registry for the agent selector."""
from __future__ import annotations

from app.core.agents.agents.knowledge import KnowledgeAgent
from app.core.agents.agents.transit import TransitAgent
from app.core.agents.agents.vault import VaultAgent
from app.core.agents.base import BaseAgentService
from app.core.agents.schemas import AgentName
from app.core.agents.service import get_agent_service
from app.core.logging import get_logger

logger = get_logger(__name__)

_transit: TransitAgent | None = None
_knowledge: KnowledgeAgent | None = None
_vault: VaultAgent | None = None


def get_agent_by_name(name: AgentName) -> BaseAgentService:
    """Resolve a per-domain agent singleton; ``unified`` returns AgentService."""
    global _transit, _knowledge, _vault
    if name == "unified":
        return get_agent_service()
    if name == "transit":
        if _transit is None:
            _transit = TransitAgent()
        return _transit
    if name == "knowledge":
        if _knowledge is None:
            _knowledge = KnowledgeAgent()
        return _knowledge
    if name == "vault":
        if _vault is None:
            _vault = VaultAgent()
        return _vault
    msg = f"Unknown agent name: {name}"  # unreachable: Literal-validated
    raise ValueError(msg)


async def close_all_agents() -> None:
    """Close per-domain agent HTTP clients on shutdown.

    Does NOT touch the unified ``AgentService`` — that is handled by
    ``close_agent_service()``. Avoids double-close.
    """
    global _transit, _knowledge, _vault
    for label, instance in (
        ("transit", _transit), ("knowledge", _knowledge), ("vault", _vault),
    ):
        if instance is None:
            continue
        try:
            await instance.close()
        except Exception:
            logger.warning("agent.registry.close_failed", agent=label, exc_info=True)
    _transit = None
    _knowledge = None
    _vault = None


__all__ = ["close_all_agents", "get_agent_by_name", "logger"]
```

**Validation:** `uv run ruff format app/core/agents/agents/registry.py && uv run ruff check app/core/agents/agents/registry.py && uv run pyright app/core/agents/agents/registry.py && uv run mypy app/core/agents/agents/registry.py`

### Step 7 — Wire the selector into routes

**File:** `app/core/agents/routes.py`. Add import: `from app.core.agents.agents.registry import get_agent_by_name`. Modify `chat_completions` (lines 35-67):

- Drop `service: AgentService = Depends(get_agent_service)` from the signature.
- After the quota check, add:
  ```python
  service = get_agent_by_name(body.agent)
  logger.info("agent.chat.selected", agent=body.agent)
  return await service.chat(body)
  ```
- Keep the existing `from app.core.agents.service import AgentService, get_agent_service` import — the metrics endpoint still references types from there, and existing tests may patch it.

**Validation:** `uv run ruff format app/core/agents/routes.py && uv run ruff check app/core/agents/routes.py && uv run pyright app/core/agents/routes.py && uv run mypy app/core/agents/routes.py`

### Step 8 — Wire shutdown into `app/main.py`

Grep for `close_agent_service` in `app/main.py`. Add `from app.core.agents.agents.registry import close_all_agents` to the imports, then add `await close_all_agents()` directly after the existing `await close_agent_service()` call in the lifespan shutdown handler.

**Validation:** `uv run ruff format app/main.py && uv run ruff check app/main.py && uv run pyright app/main.py && uv run mypy app/main.py`

### Step 9 — Tests: `test_transit_agent.py` (15 tests)

Pattern follows `test_service.py`. Helper:

```python
def _create_transit_agent_service() -> TransitAgent:
    """Build a TransitAgent with mocked HTTP deps."""
    with patch("app.core.agents.agents.transit.create_unified_deps") as mock_deps:
        mock_deps.return_value = UnifiedDeps(
            transit_http_client=AsyncMock(spec=httpx.AsyncClient),
            obsidian_http_client=AsyncMock(spec=httpx.AsyncClient),
            settings=get_settings(),
            db_session_factory=None,
            rag_enabled=True,
        )
        return TransitAgent()
```

Tests (each named `test_*` and returning `-> None`):

1. `agent_name_is_transit_agent_v2`
2. `tool_set_has_only_5_transit_tools` — inspect `transit_agent` registered tools (use whatever public attribute Pydantic AI exposes; if private `_function_tools`, add `# pyright: ignore[reportPrivateUsage]` per-line)
3. `apply_rag_routing_disables_rag` — assert `_deps.rag_enabled is False` after call
4. `recall_memories_block_when_memory_disabled_returns_empty` — patch `get_settings().memory_enabled = False`
5. `recall_memories_block_returns_formatted_block` — patch `MemoryService.recall_by_query` to return one fake recalled memory; assert string starts with `RELEVANT MEMORIES`
6. `execute_fallback_branch_calls_persist_agent_episode` — patch `transit_agent.run` + `persist_agent_episode`; assert called with `agent_name="transit_agent_v2"`
7. `execute_correction_branch_used_when_loop_enabled` — set settings flag; patch `SelfCorrectionLoop.run_with_correction`; assert called instead of bare run
8. `execute_complex_branch_uses_pipeline` — patch `get_complex_pipeline`; pass `tier="complex"`; assert pipeline.run called
9. `run_qa_delegates_to_validate_transit_response` — patch `validate_transit_response`; assert called with right `ValidationContext`
10. `preload_validation_cache_returns_none_when_no_db_factory`
11. `chat_full_pipeline_routes_to_execute` — drive `await svc.chat(_make_request("Kuri marsruti kavejas?"))`; assert `_execute` was hit (capture via subclass)
12. `chat_logs_chat_started_and_completed` — caplog assertion
13. `chat_wraps_execute_exceptions_as_AgentExecutionError` — `_execute` raises `RuntimeError` → expect `AgentExecutionError`
14. `close_swallows_runtime_error_on_closed_loop` — `aclose.side_effect = RuntimeError`; expect no exception
15. `system_prompt_excludes_vault_and_knowledge_sections` — `assert "obsidian" not in TRANSIT_SYSTEM_PROMPT.lower()` AND `assert "knowledge base" not in TRANSIT_SYSTEM_PROMPT.lower()` (proves prompt is shorter than unified)

Top of file: `from pydantic_ai import models; models.ALLOW_MODEL_REQUESTS = False`.

**Validation:** `uv run ruff format app/core/agents/tests/test_transit_agent.py && uv run ruff check app/core/agents/tests/test_transit_agent.py && uv run pyright app/core/agents/tests/test_transit_agent.py && uv run pytest app/core/agents/tests/test_transit_agent.py -v`

### Step 10 — Tests: `test_knowledge_agent.py` (15 tests)

1. `agent_name_is_knowledge_agent`
2. `tool_set_has_only_search_knowledge_base`
3. `apply_rag_routing_always_enables_rag`
4. `run_qa_returns_empty_list`
5. `post_process_does_not_append_warning_footnotes` — drive `chat()`; assert `⚠️` not in response
6. `recall_memories_block_when_memory_enabled` (mock recall returns one memory)
7. `recall_memories_block_when_memory_disabled` (returns empty)
8. `execute_calls_persist_agent_episode_with_knowledge_tag`
9. `execute_uses_fallback_path_for_complex_tier` — KnowledgeAgent does NOT branch on tier; assert `knowledge_agent.run` called regardless
10. `complex_tier_does_not_invoke_get_complex_pipeline` — patch + assert NOT called
11. `chat_wraps_execute_exceptions_as_AgentExecutionError`
12. `chat_logs_chat_started_and_completed`
13. `system_prompt_contains_citation_marker` — `assert "Sources" in KNOWLEDGE_SYSTEM_PROMPT` and `"document_id" in KNOWLEDGE_SYSTEM_PROMPT`
14. `system_prompt_contains_no_results_instruction` — assert `"I don't know"` or `"No relevant documents"` in prompt
15. `close_swallows_runtime_error_on_closed_loop`

**Validation:** as Step 9.

### Step 11 — Tests: `test_vault_agent.py` (15 tests)

1. `agent_name_is_vault_agent`
2. `tool_set_has_4_obsidian_tools`
3. `tool_set_excludes_manage_skills`
4. `tool_set_excludes_search_knowledge_base`
5. `apply_rag_routing_disables_rag`
6. `run_qa_returns_empty_list`
7. `recall_memories_block_when_memory_enabled`
8. `recall_memories_block_when_memory_disabled`
9. `execute_calls_persist_agent_episode_with_vault_tag`
10. `execute_uses_fallback_path_for_complex_tier`
11. `chat_wraps_execute_exceptions_as_AgentExecutionError`
12. `chat_logs_chat_started_and_completed`
13. `system_prompt_requires_confirmation_for_destructive_ops` — `assert "confirm" in VAULT_SYSTEM_PROMPT.lower()` AND `"dry_run" in VAULT_SYSTEM_PROMPT.lower()`
14. `system_prompt_describes_frontmatter_conventions` — `assert "frontmatter" in VAULT_SYSTEM_PROMPT.lower()`
15. `close_swallows_runtime_error_on_closed_loop`

**Validation:** as Step 9.

### Step 12 — Add 3 selector regression tests to `test_routes.py`

**File:** `app/core/agents/tests/test_routes.py` (do NOT create a new file).

- `test_chat_completions_unknown_agent_returns_422` — POST with `"agent": "bogus"`, expect 422 (Pydantic Literal rejection).
- `test_chat_completions_default_agent_is_unified` — POST without `agent`; patch `app.core.agents.routes.get_agent_by_name`; assert called with `"unified"`.
- `test_chat_completions_routes_to_transit_agent` — POST with `"agent": "transit"`; patch the registry call; assert the right instance's `chat()` was awaited.

**Validation:** `uv run pytest app/core/agents/tests/test_routes.py -v`

### Step 13 — Update `app/core/agents/CLAUDE.md`

Edit the "Planned Improvements" section #4 (Multi-agent splitting) to mark AI-6.2 done. Add: "✅ AI-6.2: domain-specific agents — `TransitAgent` (5 transit tools, full QA + correction pipeline), `KnowledgeAgent` (1 RAG tool, citation-enforced prompt), `VaultAgent` (4 obsidian tools, safe-delete prompt). Selected via `agent: 'unified'|'transit'|'knowledge'|'vault'` field on `ChatCompletionRequest` (default `unified` preserves all-11-tool fallback). Per-agent singletons in `agents/registry.py`. ~45 new tests. Foundation for AI-6.3 router."

### Step 14 — Run the full validation suite

```bash
uv run ruff format app/
uv run ruff check app/ --fix
uv run pyright app/core/agents/
uv run mypy app/core/agents/
uv run pytest app/core/agents/ -v
make check
```

Acceptance: pyright ≤ 5, mypy ≤ 3, ruff clean, **388+ tests pass** (340 baseline + 45 new agent tests + 3 route regression tests).

## Preflight Warnings

1. **Three-Feature Rule deferred** — `_recall_memories_block` will exist in 4 modules after this. Don't extract here; file follow-up "AI-6.2.1: extract memory recall + skills loader to `app/core/agents/hooks_shared.py`". Each duplicate gets `# NOTE: shared with X; extract on AI-6.2.1`.
2. **`AgentService` keeps `agent_name = "transit_agent"`**; `TransitAgent` uses `"transit_agent_v2"` to avoid memory store contamination between the unified fallback and the new domain agent. Don't reuse the tag.
3. **`models.ALLOW_MODEL_REQUESTS = False`** — must be at top of every new test file (else CI may make real LLM calls).
4. **Test helper return annotations** — `_create_*_agent_service()` helpers must declare `-> TransitAgent` etc. (anti-pattern #26).
5. **`Any` in `_execute` static_cache parameter** — keep `# noqa: ANN401` matching `base.py` / `service.py` (anti-pattern #23).
6. **Don't `replace_all`** to remove end-of-line comments in `service.py` (anti-pattern #20).
7. **`KnowledgeAgent._run_qa` / `VaultAgent._run_qa`** — use full named-param signature matching the base, NOT `**_: Any`, to keep pyright happy.
8. **`Literal` not `str`** for the `agent` field — anti-pattern #54.
9. **`get_settings()` is cached** — tests that flip `agent_self_correction_enabled` must patch the loop construction directly OR clear the cache (`get_settings.cache_clear()`).
10. **Pyright `_function_tools` access in tests** — use per-line `# pyright: ignore[reportPrivateUsage]`, NOT a file-level directive (anti-pattern #14 — file directives cascade and hide real errors).
11. **`ChatCompletionRequest` model is in strict mode** — confirm Step 1 doesn't break test_schemas.py constructors that omit `agent` (default `"unified"` should keep them passing).
12. **Single-router constraint** — `app/main.py:185` already does `app.include_router(agent_router)` once. Do NOT add a second router; the new selector reuses the same `POST /v1/chat/completions`.

## Security Checklist (route changes)

- [x] `get_current_user` dependency preserved (CTX-RBAC).
- [x] `@limiter.limit("10/minute")` preserved (CTX-RBAC).
- [x] Daily quota check preserved (CTX-RBAC).
- [x] `agent` selector typed `Literal[...]` so 422 fires before service-layer dispatch (CTX-INPUT).
- [x] No new endpoints — existing `TestAllEndpointsRequireAuth` convention test still covers `/v1/chat/completions`.
- [x] Domain agents do NOT receive `manage_agent_skills` (CTX-AGENT — no agent-created artifacts that need human activation).
- [x] Prompt-injection logging via `_check_prompt_injection` runs in base `chat()` for all subclasses (CTX-AGENT).
- [x] No credentials in tool responses — none of the tool implementations changed.
- [x] `VaultAgent` system prompt explicitly requires user confirmation before destructive ops (CTX-AGENT — defense-in-depth on top of the tool-level `confirm: true` enforcement).

## Verification

- [ ] `make lint` clean.
- [ ] `make types` ≤ baseline (pyright ≤ 5, mypy ≤ 3, all in pre-existing files).
- [ ] `uv run pytest app/core/agents/ -v` — at least **388 tests pass** (340 + 48).
- [ ] `make security-audit-quick` passes.
- [ ] `uv run pytest app/tests/test_security.py -v` passes.
- [ ] Manual smoke: `curl -X POST .../v1/chat/completions -d '{"messages":[...], "agent":"transit"}'` → 200.
- [ ] Manual smoke: `'{"agent":"bogus"}'` → 422.
- [ ] Memory store contains episodes tagged `transit_agent_v2`, `knowledge_agent`, `vault_agent` after smoke tests.
- [ ] `agent_router` registered exactly once in `app/main.py`.
- [ ] Both `close_agent_service()` AND `close_all_agents()` fire on shutdown.
