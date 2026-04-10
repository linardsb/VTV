# Plan: AI-6.1 — BaseAgentService Shared Pipeline (Full Harness)

## Context

Extract the orchestration pipeline currently inside `AgentService.chat()` into a new abstract base class `BaseAgentService` at `app/core/agents/base.py`. The base owns the 9-phase flow (tier routing → skill detection → memory recall → prompt building → execution → post-processing → confidence → self-correction → memory bridge → response build) and exposes 9 hook points subclasses can override. `AgentService` becomes a thin subclass that wires the existing transit-domain hooks.

This is a **pure refactor** — zero behavior change. Every existing test in `app/core/agents/tests/` and `app/memory/tests/test_bridge.py` must continue to pass. The harness is the foundation for future domain agents (AI-6.2+) that will reuse the pipeline with different tools/prompts/QA.

The reference is email-hub's `app/ai/agents/base.py` (468 lines, 9 hooks). That file is NOT in this repo; only `app/core/agents/service.py` (380 lines) is the source of truth for VTV behavior. We adapt the email-hub pattern to VTV's actual pipeline (which adds: multi-tier routing, complex pipeline orchestrator, RAG router, GTFS static cache preload — none mentioned in the email-hub pattern).

## Security Context Assessment

**CTX-AGENT (active)** — This refactors the AI agent orchestration pipeline. Requirements that apply:
- Prompt injection detection must remain in place (currently `service.py:137-138`, log-only). Hook layout must keep this call wired.
- Memory bridge / skill loader must continue to fail-open without exposing credentials.
- No new tool wiring; pure plumbing refactor.

**CTX-RBAC (passive)** — `app/core/agents/routes.py` is unchanged. The route still depends on `get_agent_service()` and `service.chat()`. No new endpoints. Existing rate limiting (`10/min`) and quota (`agent_daily_quota`) untouched.

**CTX-INPUT (passive)** — `ChatCompletionRequest` schema unchanged. No new user-input surface.

CTX-AUTH / CTX-FILE / CTX-INFRA — N/A.

## Research Summary

### Current `AgentService.chat()` pipeline (`app/core/agents/service.py:117-338`)

| Phase | Lines | Behavior | Hook Target |
|-------|-------|----------|-------------|
| 1. Extract prompt + history | 133-135 | last user msg → `current_prompt`; `prior_history` from earlier msgs | base |
| 2. Prompt injection check | 137-138 | log-only warning, never blocks | base |
| 3. Tier classification | 140-142 | `classify_prompt()` + `resolve_tier_model()` | `_get_model_tier()` |
| 4. RAG routing decision | 154-166 | toggles `deps.rag_enabled` from `knowledge_router_enabled` setting | base (uses `self._deps`) |
| 5. Skill detection + load | 168-176 | `SkillService(db).get_active_skills_content()`, fail-open | `detect_relevant_skills()` |
| 6. Memory recall + format | 177-205 | `MemoryService.recall_by_query()` → format `RELEVANT MEMORIES (from prior...)` block with `[score]` lines truncated to 300 chars | base — formatting must be byte-identical |
| 7. Build instructions | 207 | `build_instructions_with_skills(skills, memory_ctx)` | `build_system_prompt()` (or composed in base) |
| 8. GTFS static cache preload | 209-219 | fail-open populate for validation context | base |
| 9a. Complex tier path | 224-242 | `get_complex_pipeline(agent, deps).run(...)` | base, gated by hook tier |
| 9b. Self-correction path | 243-261 | `SelfCorrectionLoop.run_with_correction(...)` for standard tier when `agent_self_correction_enabled` | `_should_run_qa()` + `_run_qa()` (loop owns this) |
| 9c. Direct fallback | 262-279 | `agent.run(...)`, plain | base |
| 10. Validation footnotes | 289-308 | `validate_transit_response(...)` when no correction loop ran; appends `⚠️` lines under `---` | `_post_process()` |
| 11. Response construction | 310-337 | `chatcmpl-{uuid}` id, `time.time()`, `ChatCompletionResponse` | `_build_response()` |
| 12. Memory bridge persist | 255-260, 274-279 | `persist_agent_episode(agent_name="transit_agent", ..., messages=...)` fire-and-forget | `_persist_episode()` |

### Supporting modules (unchanged)

| Module | Path | Role |
|--------|------|------|
| Self-correction | `app/core/agents/correction.py` (305L) | `SelfCorrectionLoop.run_with_correction(...)` returns `CorrectedResult(output, warnings, issues, rounds_used, all_messages, corrected)` |
| Memory bridge | `app/memory/bridge.py:98-139` | `persist_agent_episode(agent_name, prompt, response, messages, min_tools=2)` — fires `asyncio.create_task` only if `memory_enabled` and ≥2 distinct tools |
| Skill loader | `app/skills/service.py:103-135` | `SkillService(db).get_active_skills_content()` returns formatted markdown bounded by `TOKEN_BUDGET_CHARS` (8000) |
| Validation | `app/core/agents/validation.py` | `validate_transit_response(text, ValidationContext)` → `ValidationResult(is_valid, issues, warnings, sanitized_response)` |
| Tier routing | `app/core/agents/routing.py:65`, `config.py:113-172` | `classify_prompt(prompt) -> ModelTier`; `resolve_tier_model(tier) -> str|Model|None` |
| Complex pipeline | `app/core/agents/pipeline.py` | `get_complex_pipeline(agent, deps).run(...)` for `tier=="complex"` |
| Singleton + agent | `app/core/agents/agent.py:121` (`create_agent`), `service.py:357-379` (`get_agent_service`/`close_agent_service`) | unchanged |

### Settings used (`app/core/config.py`)

- `llm_{fast,standard,complex}_{provider,model}` — tier overrides
- `agent_self_correction_enabled: bool`, `agent_max_correction_rounds: int` (clamped ≤3 in loop)
- `memory_enabled`, `memory_max_recall_results`, `memory_recall_min_score`, `memory_context_injection_limit`
- `knowledge_router_enabled`
- `agent_daily_quota`
- `llm_provider`, `llm_model` (used in `_build_response` fallback model name)

### Callsites of `AgentService`

- `app/core/agents/routes.py:25` import; line 40 `Depends(get_agent_service)`; line 67 `await service.chat(body)`. Untouched by this refactor.
- `app/core/agents/tests/test_service.py:22` `_create_service()` patches `app.core.agents.service.create_unified_deps`.
- `app/tests/test_security.py:1165` convention test asserts `_get_client_ip` is referenced inside the `chat_completions` source. Not affected.

### Schemas

`ChatCompletionRequest`, `ChatCompletionResponse`, `ChatCompletionChoice`, `ChatMessage`, `UsageInfo`, `CorrectionMetricsResponse` all live in `app/core/agents/schemas.py`. **Unchanged.**

## Test Landscape

Existing tests in `app/core/agents/tests/` (10 files, ~122 tests) plus `app/memory/tests/test_bridge.py` (12 tests). The refactor must keep them green.

### High-fragility patterns we must preserve verbatim

| Test file:line | Brittle assumption | Mitigation |
|----------------|-------------------|------------|
| `test_service.py:22` | Patches `app.core.agents.service.create_unified_deps` | `AgentService.__init__` must continue to call `create_unified_deps` from `app.core.agents.service` namespace (re-export OK) |
| `test_service.py:94, 111` | `service._deps.rag_enabled` direct access | Keep `self._deps` as a public-ish instance attribute on subclass; the base must allow subclass to set `self._deps` in `__init__` |
| `test_service.py:173, 219, 235, 274` | `patch("app.core.agents.service.MemoryService", ...)` | Memory recall must still call `MemoryService` looked up via `app.core.agents.service` module (re-export `MemoryService` from `service.py`) |
| `test_service.py:175` | `patch("app.core.agents.service.build_instructions_with_skills", ...)` | Re-export `build_instructions_with_skills` in `service.py` even if base imports it from elsewhere |
| `test_service.py:124, 197, 264` | `patch("app.core.agents.service.get_settings", ...)` | `get_settings` must remain importable AND called via the `service` module namespace |
| `test_service.py:186-187, 195` | Hardcoded memory-context format: prefix `RELEVANT MEMORIES`, `[0.90]`, content truncation 300 | Memory formatting helper produces byte-identical output |
| `test_correction.py:126` | `assert loop._max_rounds == 3` | Loop module untouched |
| `test_bridge.py:190-218` | Hardcoded `[transit_agent] Dispatcher asked:` prefix | Bridge module untouched; agent_name still `"transit_agent"` |
| `test_metrics.py:225-235` | Per-check JSON keys | Metrics module untouched |
| `app/tests/test_security.py:1165` | `inspect.getsource(chat_completions)` contains `_get_client_ip` | Routes file untouched |

### Existing fixtures we will reuse

- Root `conftest.py`: `client`, `mock_settings`
- `app/core/agents/tests/`: per-file `_reset_singleton`, `_admin_override`, `_setup_auth_override` autouse fixtures
- `_fake_agent`, `_fake_run_result`, `_make_recall_responses` factory helpers in `test_correction.py:18`, `test_metrics.py:124`, `test_service.py`
- `pydantic_ai.models.ALLOW_MODEL_REQUESTS = False` set at module top of `test_service.py`/`test_routes.py`

### New tests to add (`app/core/agents/tests/test_base.py`)

Hook-point unit tests against a minimal `_FakeAgentService(BaseAgentService)`:
1. `_get_model_tier` default returns `(classify_prompt(prompt), resolve_tier_model(tier))`; subclass override is honored
2. `detect_relevant_skills` default returns `""` if skill loader fails; otherwise the loader output
3. `_build_user_message` default returns the raw prompt; subclass override honored
4. `_post_process` default appends `⚠️` footnotes only when warnings present; idempotent on empty
5. `_run_qa` default delegates to `validate_transit_response`
6. `_should_run_qa` default returns `agent_self_correction_enabled and not is_complex_tier`
7. `_build_response` default returns a `ChatCompletionResponse` with `chatcmpl-` id and `time.time()` createdAt
8. `_persist_episode` default delegates to `persist_agent_episode("transit_agent" by default, …)` and is fire-and-forget (uses `asyncio.create_task` indirectly via bridge)
9. `build_system_prompt` default raises `NotImplementedError` to prove subclass MUST override

## Type Check Baseline

Run on `app/core/agents/` at HEAD before any edit (record exactly):

- **Pyright:** `5 errors, 0 warnings, 0 informations`
  - `pipeline.py:47, 49` — partially-unknown lists
  - `pipeline.py:136` — `model` arg `object | None` vs `Model | str | None` (×2)
  - `tools/transit/client.py:193` — `response` possibly unbound
- **Mypy:** `Found 3 errors in 2 files (checked 65 source files)`
  - `tools/transit/static_store.py:149-150` — async result typing
  - `pipeline.py:136` — same `model` arg mismatch

**None of these are in `service.py` or any file we will edit.** Acceptance: pyright/mypy counts on `app/core/agents/` must be **≤ baseline** after the refactor (5 pyright errors, 3 mypy errors). New `base.py` and updated `service.py` must add **zero** new errors.

## Files to Create / Modify

| Action | File | Purpose |
|--------|------|---------|
| CREATE | `app/core/agents/base.py` | `BaseAgentService` with 9 hooks + pipeline orchestrator |
| UPDATE | `app/core/agents/service.py` | `AgentService(BaseAgentService)`; thin subclass overriding hooks; keep all existing module-level imports/symbols re-exported: **`create_unified_deps`, `MemoryService`, `build_instructions_with_skills`, `get_settings`, `SelfCorrectionLoop`, `persist_agent_episode`, `classify_prompt`, `resolve_tier_model`, `validate_transit_response`, `SkillService`, `AsyncSessionLocal`, `get_complex_pipeline`, `needs_rag` (from `app.knowledge.router`), `agent` (from `app.core.agents.agent`), `logger`** |
| CREATE | `app/core/agents/tests/test_base.py` | Hook-point unit tests (9 tests) |
| UPDATE | `app/core/agents/CLAUDE.md` (if exists) | Note new layered architecture, line refs |

No migrations. No new dependencies. No router/main.py changes.

## Implementation Steps

### Step 1 — Read source of truth
Open and study:
- `app/core/agents/service.py` (full)
- `app/core/agents/correction.py:94-247` (`SelfCorrectionLoop.run_with_correction` signature)
- `app/core/agents/validation.py` (`validate_transit_response`, `ValidationContext`, `ValidationResult`, `Issue`)
- `app/memory/bridge.py:98-139` (`persist_agent_episode`)
- `app/core/agents/agent.py` (the singleton `agent` and `build_instructions_with_skills`)
- `app/core/agents/tests/test_service.py` (every patch path is a contract)

**No edits in this step.**

### Step 2 — CREATE `app/core/agents/base.py`

Layout (target ~350-450 lines):

```python
"""Reusable agent harness — extracts AgentService.chat() into 9 hook points.

Subclasses override hook methods; the base owns the pipeline so future domain
agents (AI-6.2+) reuse the same flow with different tools/prompts/QA.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from app.core.agents.agent import agent as _default_agent, build_instructions_with_skills
from app.core.agents.config import resolve_tier_model
from app.core.agents.correction import CorrectedResult, SelfCorrectionLoop
from app.core.agents.exceptions import AgentExecutionError
from app.core.agents.pipeline import get_complex_pipeline
from app.core.agents.routing import ModelTier, classify_prompt
from app.core.agents.schemas import (
    ChatCompletionChoice,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    UsageInfo,
)
from app.core.agents.validation import ValidationContext, validate_transit_response
from app.core.config import get_settings
from app.core.logging import get_logger

if TYPE_CHECKING:
    from pydantic_ai import Agent
    from pydantic_ai.models import Model

logger = get_logger(__name__)


@dataclass(slots=True)
class _PipelineOutcome:
    response_text: str
    warnings: list[str] | None  # None = no QA ran here, defer to _post_process
    messages: list[Any]
    tier: ModelTier
    tier_model: str | Model | None
    correction_rounds_used: int
    corrected: bool


class BaseAgentService:
    """Abstract harness — subclasses MUST override `build_system_prompt`
    and `_build_user_message`. All other hooks have sensible defaults.
    """

    # ---- class-level config (subclasses override) -------------------------
    agent_name: str = "base_agent"
    pydantic_agent: Agent[Any, str] = _default_agent  # subclasses can swap

    def __init__(self) -> None:
        # Subclass __init__ is responsible for `self._deps` and any
        # additional state (e.g. self._correction_loop). The base never
        # touches `self._deps` directly — it accesses it via `self.deps`
        # so subclasses can rebind freely.
        ...

    # ---- public entry point -----------------------------------------------
    async def chat(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        # Phase 1: extract current prompt + history (mirrors service.py:133-135)
        ...
        # Phase 2: prompt injection check (log-only)
        ...
        # Phase 3: tier
        tier, tier_model = self._get_model_tier(current_prompt)
        # Phase 4: RAG routing toggle on self.deps
        ...
        # Phase 5: skills
        skills_instructions = await self.detect_relevant_skills(current_prompt)
        # Phase 6: memory recall + format (must produce byte-identical block)
        memory_context = await self._recall_memories_block(current_prompt)
        # Phase 7: instructions (subclass system prompt + skills + memory)
        instructions = self.build_system_prompt(skills_instructions, memory_context)
        # Phase 8: GTFS static cache preload (fail-open)
        ...
        # Phase 9: build user message (subclass shapes it)
        user_message = self._build_user_message(request, current_prompt)
        # Phase 10: tier-routed execution → _PipelineOutcome
        outcome = await self._execute(
            user_message=user_message,
            instructions=instructions,
            history=prior_history,
            tier=tier,
            tier_model=tier_model,
            current_prompt=current_prompt,
        )
        # Phase 11: post-process (validation footnotes if needed)
        final_text = await self._post_process(
            response=outcome.response_text,
            current_prompt=current_prompt,
            warnings=outcome.warnings,
            messages=outcome.messages,
        )
        # Phase 12: memory bridge fire-and-forget
        await self._persist_episode(
            prompt=current_prompt,
            response=final_text,
            messages=outcome.messages,
        )
        # Phase 13: build response
        return self._build_response(
            content=final_text,
            tier_model=outcome.tier_model,
        )

    # ---- 9 hook points ----------------------------------------------------

    def build_system_prompt(self, skills: str, memory_context: str) -> str:
        """MUST override. Compose the system prompt; default delegates to
        ``build_instructions_with_skills`` from the agent module."""
        return build_instructions_with_skills(skills, memory_context)

    async def detect_relevant_skills(self, prompt: str) -> str:
        """Default: load all active skills from the DB; fail-open to ''."""
        ...

    def _build_user_message(self, request: ChatCompletionRequest, current_prompt: str) -> str:
        """Default: return the raw current prompt unchanged."""
        return current_prompt

    async def _post_process(
        self,
        *,
        response: str,
        current_prompt: str,
        warnings: list[str] | None,
        messages: list[Any],
    ) -> str:
        """Default: if `warnings is None`, run validate_transit_response with
        a fallback ValidationContext built from current_prompt + static cache;
        otherwise use provided warnings. Append ``⚠️`` footnotes under ``---``.
        Mirrors service.py:289-308 byte-for-byte."""
        ...

    async def _run_qa(
        self,
        *,
        response: str,
        context: ValidationContext,
    ) -> Any:
        """Default delegate to validate_transit_response — used by self-
        correction loop indirectly. Hook exists so subclasses can plug
        domain-specific QA validators."""
        return validate_transit_response(response, context)

    def _should_run_qa(self, tier: ModelTier) -> bool:
        """Default: enable for non-complex tier when correction is enabled."""
        settings = get_settings()
        return bool(getattr(settings, "agent_self_correction_enabled", False)) and tier != "complex"

    def _get_model_tier(self, prompt: str) -> tuple[ModelTier, str | Model | None]:
        tier = classify_prompt(prompt)
        return tier, resolve_tier_model(tier)

    def _build_response(
        self,
        *,
        content: str,
        tier_model: str | Model | None,
    ) -> ChatCompletionResponse:
        """Mirrors service.py:310-337."""
        settings = get_settings()
        response_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
        model_name = str(tier_model) if tier_model else f"{settings.llm_provider}:{settings.llm_model}"
        return ChatCompletionResponse(
            id=response_id,
            created=int(time.time()),
            model=model_name,
            choices=[ChatCompletionChoice(message=ChatMessage(role="assistant", content=content))],
            usage=UsageInfo(),
        )

    async def _persist_episode(
        self,
        *,
        prompt: str,
        response: str,
        messages: list[Any],
    ) -> None:
        """Default: fire-and-forget via app.memory.bridge.persist_agent_episode."""
        from app.memory.bridge import persist_agent_episode

        persist_agent_episode(
            agent_name=self.agent_name,
            prompt=prompt,
            response=response,
            messages=messages,
        )

    # ---- internal helpers (NOT hooks; private) ----------------------------

    async def _recall_memories_block(self, current_prompt: str) -> str:
        """Replicates service.py:177-205 — produces the RELEVANT MEMORIES block."""
        ...

    async def _execute(
        self,
        *,
        user_message: str,
        instructions: str,
        history: list[Any],
        tier: ModelTier,
        tier_model: str | Model | None,
        current_prompt: str,
    ) -> _PipelineOutcome:
        """Routes to complex pipeline / self-correction loop / direct run.
        Mirrors service.py:223-287."""
        ...
```

**Validation per file:**
`uv run ruff format app/core/agents/base.py && uv run ruff check --fix app/core/agents/base.py && uv run pyright app/core/agents/base.py && uv run mypy app/core/agents/base.py`

### Step 3 — UPDATE `app/core/agents/service.py`

Reduce `AgentService` to a thin subclass. **Critical**: keep all module-level imports the test files patch against.

```python
"""Transit-domain agent service — wires the BaseAgentService harness."""
from __future__ import annotations

# These imports MUST stay top-level so existing test patches keep working:
#   patch("app.core.agents.service.create_unified_deps")
#   patch("app.core.agents.service.MemoryService")
#   patch("app.core.agents.service.build_instructions_with_skills")
#   patch("app.core.agents.service.get_settings")
from app.core.agents.agent import agent, build_instructions_with_skills  # noqa: F401
from app.core.agents.base import BaseAgentService
from app.core.agents.correction import SelfCorrectionLoop
from app.core.agents.deps import create_unified_deps  # current import path
from app.core.agents.pipeline import get_complex_pipeline  # noqa: F401
from app.core.agents.routing import classify_prompt  # noqa: F401
from app.core.agents.config import resolve_tier_model  # noqa: F401
from app.core.agents.validation import validate_transit_response  # noqa: F401
from app.core.config import get_settings
from app.core.database import AsyncSessionLocal  # noqa: F401
from app.core.logging import get_logger
from app.knowledge.router import needs_rag  # noqa: F401  — patched by tests
from app.memory.bridge import persist_agent_episode  # noqa: F401
from app.memory.service import MemoryService  # noqa: F401
from app.skills.service import SkillService  # noqa: F401

logger = get_logger(__name__)


class AgentService(BaseAgentService):
    agent_name = "transit_agent"
    pydantic_agent = agent

    def __init__(self) -> None:
        super().__init__()
        self._deps = create_unified_deps()
        settings = get_settings()
        self._correction_loop: SelfCorrectionLoop | None = (
            SelfCorrectionLoop(max_rounds=settings.agent_max_correction_rounds)
            if getattr(settings, "agent_self_correction_enabled", False)
            else None
        )

    # The hooks AgentService overrides today are exactly what the base
    # already does for the transit agent — no further overrides needed
    # because the defaults above mirror service.py behavior. Subclasses
    # for new domains (AI-6.2+) will override build_system_prompt /
    # _build_user_message / detect_relevant_skills.

    async def close(self) -> None:
        if self._deps.transit_http_client is not None:
            await self._deps.transit_http_client.aclose()
        if self._deps.obsidian_http_client is not None:
            await self._deps.obsidian_http_client.aclose()


# Module-level singleton helpers — UNCHANGED from current service.py
_agent_service: AgentService | None = None


def get_agent_service() -> AgentService:
    global _agent_service
    if _agent_service is None:
        _agent_service = AgentService()
    return _agent_service


async def close_agent_service() -> None:
    global _agent_service
    if _agent_service is not None:
        await _agent_service.close()
        _agent_service = None
```

**Validation per file:**
`uv run ruff format app/core/agents/service.py && uv run ruff check --fix app/core/agents/service.py && uv run pyright app/core/agents/service.py && uv run mypy app/core/agents/service.py && uv run pytest app/core/agents/tests/test_service.py -x`

**If `test_service.py` fails:** the failure is the contract violation. Common fixes:
- A patch path stopped resolving → add explicit re-import in `service.py`
- The format of the memory block drifted → diff against current `service.py:177-205` and copy verbatim into `BaseAgentService._recall_memories_block`
- A private attribute test broke (`_deps`, `_correction_loop`) → make sure subclass `__init__` sets it on `self` directly, not on the base

### Step 4 — CREATE `app/core/agents/tests/test_base.py`

Add 9 hook-point unit tests + 1 happy-path end-to-end test using the `_FakeAgentService` pattern. Each test exercises a single hook in isolation by overriding it on a tiny subclass and asserting the base calls it with the expected args.

Patterns to copy from existing tests:
- Module top: `from pydantic_ai import models; models.ALLOW_MODEL_REQUESTS = False`
- Use `agent.override(model=TestModel())` for the happy-path test
- Mock `MemoryService`, `SkillService`, `persist_agent_episode` via `patch("app.core.agents.base.persist_agent_episode")`

**Validation per file:**
`uv run ruff format app/core/agents/tests/test_base.py && uv run ruff check --fix app/core/agents/tests/test_base.py && uv run pytest app/core/agents/tests/test_base.py -x`

### Step 5 — Full agent test sweep

`uv run pytest app/core/agents/tests/ app/memory/tests/test_bridge.py -x`

If anything fails, fix the divergence in `base.py` — never weaken a test assertion.

### Step 6 — Type-check parity check

`uv run pyright app/core/agents/ 2>&1 | tail -5`
`uv run mypy app/core/agents/ 2>&1 | tail -5`

Both counts MUST be ≤ baseline (5 pyright, 3 mypy). New `base.py` should report 0 errors.

### Step 7 — Full validation suite

`make check` then `make security-audit-quick`.

## Preflight Warnings

These patterns in the existing test corpus will bite if violated. Treat them as immutable contracts during the refactor:

1. **`test_service.py:22, 24, 37, 71, 73, 86, 104, 122-127, 172-175, 196-218, 238-274`** — every patch path against `app.core.agents.service.X` must keep resolving. Concrete patch targets observed in the test file:
   - `app.core.agents.service.create_unified_deps` (line 24)
   - `app.core.agents.service.logger` (lines 37, 59, 73, 86, 104, 122, 172, 196, 218, 238, 263)
   - `app.core.agents.service.agent` (line 71)
   - `app.core.agents.service.get_settings` (lines 123, 197, 264)
   - `app.core.agents.service.needs_rag` (line 127) — **easy to miss; lives in `app.knowledge.router`**
   - `app.core.agents.service.MemoryService` (lines 173, 204, 219, 239, 274)
   - `app.core.agents.service.build_instructions_with_skills` (lines 174, 240)
   The new `service.py` must re-import all of these at module level. Also re-export the rest for forward compatibility: `SkillService`, `AsyncSessionLocal`, `SelfCorrectionLoop`, `persist_agent_episode`, `classify_prompt`, `resolve_tier_model`, `validate_transit_response`, `get_complex_pipeline`. Use `# noqa: F401` for re-exports.
2. **`test_service.py:94, 111`** — `service._deps.rag_enabled` direct attribute access → `_deps` must be a real attribute on the subclass instance, set in `AgentService.__init__`, not a `@property` on the base.
3. **`test_correction.py:126`** — `loop._max_rounds == 3` private access → do NOT touch `correction.py`.
4. **`test_bridge.py:190-218`** — hardcoded `[transit_agent] Dispatcher asked:` prefix → bridge module must remain untouched, and `agent_name` for `AgentService` must stay `"transit_agent"`.
5. **`test_service.py:186-187`** — memory context format `RELEVANT MEMORIES` + `[0.90]` style + 300-char content truncation must be **byte-identical**. Copy the lines from current `service.py:177-205` verbatim into `_recall_memories_block`.
6. **`test_metrics.py`** — metrics tracker singleton, autouse `_reset_singleton` fixture; metrics module must NOT be touched.
7. **`app/tests/test_security.py:1165`** — convention test inspects `chat_completions` source for `_get_client_ip`. Routes file untouched.
8. **`test_service.py:283`** range — number of tests in `test_service.py` may be hardcoded somewhere; if an assertion like `assert len(...) == N` exists in any test referencing the `chat()` flow, do not delete tests.
9. **`pydantic_ai.models.ALLOW_MODEL_REQUESTS = False`** is set at module top of `test_service.py`, `test_routes.py`, `test_metrics.py`. New `test_base.py` MUST set this too or risk live-LLM accidents.
10. **GTFS static cache preload (service.py:209-219)** is fail-open and silent. Keep the same try/except None-pass shape so its absence in tests still produces the same `static_cache=None` `ValidationContext`.

## Security Checklist

(CTX-AGENT — pure refactor, no new attack surface)

- [ ] Prompt injection logging at `service.py:137-138` is preserved by `BaseAgentService.chat()` (Phase 2)
- [ ] Skill loader fail-open path still logs `agent.skills_load_failed` with `exc_info=True`
- [ ] Memory recall fail-open path still logs at the same level (do not regress to `error`)
- [ ] `persist_agent_episode` is still called fire-and-forget — never `await` it directly
- [ ] No tool list, prompt, or model name leaks into exception messages (`AgentExecutionError` continues to wrap raw exceptions)
- [ ] No new endpoints → CTX-RBAC unchanged → no new `require_role` audits needed
- [ ] No new file uploads, no new SQL, no new env vars → CTX-FILE/INPUT/INFRA n/a

## Verification

- [ ] `uv run pytest app/core/agents/tests/ app/memory/tests/test_bridge.py -x` — all green
- [ ] `make check` — passes (lint + types + full test suite)
- [ ] `make security-audit-quick` — passes
- [ ] `uv run pyright app/core/agents/ 2>&1 | tail -1` reports **≤ 5 errors** (baseline)
- [ ] `uv run mypy app/core/agents/ 2>&1 | tail -1` reports **≤ 3 errors** (baseline)
- [ ] `service.py` line count drops substantially (≈380 → ≈80-120 lines), `base.py` ≈350-450 lines
- [ ] No file outside `app/core/agents/base.py`, `app/core/agents/service.py`, `app/core/agents/tests/test_base.py` is modified
- [ ] No behavior change observable from `routes.py` consumers (chat completions test in `test_routes.py` passes unchanged)
- [ ] `git diff --stat` shows the expected 2-file change + 1 new test file
