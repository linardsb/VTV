# Plan: AI-3.4 Memory Integration into Agent Pipeline

## Context

Memory is useless if it's not in the agent's context window. This ticket integrates memory recall before `agent.run()` and enhances compaction with LLM-based intent merging. Memory context is injected as system-level instructions alongside skills. Background tasks run compaction and promotion on a daily schedule.

**Depends on:** AI-3.1 (vertical slice), AI-3.2 (service lifecycle), AI-3.3 (bridge — already calling `persist_agent_episode()` post-response in `service.py:193-198`).

## Security Context Assessment

- **CTX-AGENT** — Modifies agent tool pipeline, injects memory into LLM context. Memory content could contain prior user queries — ensure no credential leakage in recalled memories.
- **CTX-INPUT** — Memory recall query comes from user prompt; already embedded via pgvector (no raw SQL).
- **CTX-INFRA** — Adds background tasks to lifespan, new config settings.

## Research Summary

### Agent Service (`app/core/agents/service.py`)
- `chat()` method at lines 100-247 is the main orchestration point
- Skills loaded at lines 152-158: `AsyncSessionLocal() → SkillService → get_active_skills_content()`
- Instructions built at line 160: `build_instructions_with_skills(skills_instructions) or None`
- Agent runs at lines 183-189 (standard tier) or 162-181 (complex pipeline)
- Bridge called at lines 192-198: `persist_agent_episode(...)` — fire-and-forget

### Agent Definition (`app/core/agents/agent.py`)
- `build_instructions_with_skills(skills_content: str) -> str` at lines 146-159 — currently a pass-through
- Must extend to accept memory context parameter

### Memory Service (`app/memory/service.py`)
- `recall()` at lines 102-126 — takes embedding, returns `list[MemoryRecallResponse]`
- `recall_by_query()` at lines 128-154 — embeds text first, then calls `recall()`
- `compact()` at lines 166-223 — step 3 merges via concatenation at line 199
- `promote_episodes()` at lines 225-237
- Embedding singleton at lines 29-44: `_get_embedding()`

### Config (`app/core/config.py`)
- Memory settings at lines 249-258: `memory_enabled`, `memory_max_recall_results=5`, `memory_merge_threshold=0.92`
- Need to add: `memory_recall_min_score`, `memory_context_injection_limit`, `memory_compaction_cron_hour`, `memory_promotion_cron_hour`, `memory_llm_merge_enabled`

### Lifespan (`app/main.py`)
- Background tasks registered at lines 107-129 (startup) and 133-147 (shutdown)
- Pattern: `await start_X()` / `await stop_X()` with structured logging
- No existing `app/core/lifespan.py` — tasks are in `main.py` directly

## Test Landscape

| File | Tests | Key patterns |
|------|-------|-------------|
| `app/memory/tests/test_bridge.py` | 10 | `@patch("app.memory.bridge.asyncio.create_task")`, `@patch("app.memory.bridge.get_db_context")` |
| `app/memory/tests/test_service.py` | 20 | `svc.repository = AsyncMock()`, `patch("app.memory.service._get_embedding")` |
| `app/memory/tests/test_repository.py` | 24 | Vector ops, decay/merge mock patterns |
| `app/memory/tests/test_routes.py` | 11 | FastAPI TestClient, auth override |
| `app/core/agents/tests/test_service.py` | 6 | `agent.override(model=TestModel())`, `patch("app.core.agents.service.logger")` |

**Fixtures** (`app/memory/tests/conftest.py`): `make_memory()`, `make_embedding()`, `mock_db`, `repo`, `service`, `sample_memories`

## Type Check Baseline

| Target | Pyright | Mypy |
|--------|---------|------|
| `app/memory/` | 0 errors | 0 own errors |
| `app/core/agents/` | 6 errors (pre-existing) | 3 errors (pre-existing) |
| `app/core/config.py` | 0 | 0 |

## Files to Create/Modify

| Action | File | Purpose |
|--------|------|---------|
| UPDATE | `app/core/config.py` | Add 5 new memory integration settings |
| UPDATE | `app/core/agents/agent.py` | Extend `build_instructions_with_skills()` to accept memory context |
| UPDATE | `app/core/agents/service.py` | Add memory recall before `agent.run()`, format + inject context |
| UPDATE | `app/memory/service.py` | Add LLM-based intent merging in `compact()` |
| CREATE | `app/memory/lifecycle.py` | Background tasks: `start_memory_tasks()` / `stop_memory_tasks()` |
| UPDATE | `app/main.py` | Register memory background tasks in lifespan |
| CREATE | `app/memory/tests/test_lifecycle.py` | Tests for background compaction/promotion tasks |
| UPDATE | `app/memory/tests/test_service.py` | Tests for LLM intent merging in compact |
| UPDATE | `app/core/agents/tests/test_service.py` | Tests for memory recall injection in chat() |

## Implementation Steps

### Step 1: Add config settings (`app/core/config.py`)

Add after line 258 (after `memory_decay_min_weight`):

```python
# Memory agent integration (AI-3.4)
memory_recall_min_score: float = 0.3
memory_context_injection_limit: int = 10
memory_llm_merge_enabled: bool = False
memory_compaction_cron_hour: int = 3   # UTC hour for daily compaction (0-23)
memory_promotion_cron_hour: int = 3    # UTC hour for daily promotion (0-23)
```

**Notes:**
- `memory_recall_min_score=0.3` — similarity threshold from email-hub pattern
- `memory_context_injection_limit=10` — max memories injected; `recall()` uses `memory_max_recall_results=5` by default
- `memory_llm_merge_enabled=False` — LLM merging off by default (safe rollout)
- Reuse existing `memory_enabled` as the master gate

**Validation:** `uv run ruff check app/core/config.py && uv run pyright app/core/config.py`

### Step 2: Extend `build_instructions_with_skills()` (`app/core/agents/agent.py`)

Update function signature and body at lines 146-159:

```python
def build_instructions_with_skills(
    skills_content: str, memory_context: str = ""
) -> str:
    """Build additional instructions with active skills and memory context.

    Called by AgentService before each agent.run() to inject active skills
    and recalled memory context as additional instructions.

    Args:
        skills_content: Formatted skills text from SkillService.get_active_skills_content().
            Empty string if no active skills.
        memory_context: Formatted memory context from recalled memories.
            Empty string if no memories recalled or memory disabled.

    Returns:
        Combined instructions string, or empty string if both inputs empty.
    """
    parts: list[str] = []
    if skills_content:
        parts.append(skills_content)
    if memory_context:
        parts.append(memory_context)
    return "\n\n".join(parts)
```

**Validation:** `uv run ruff check app/core/agents/agent.py && uv run pyright app/core/agents/agent.py`

### Step 3: Add memory recall + context injection in `AgentService.chat()` (`app/core/agents/service.py`)

Between skills loading (line 158) and instruction building (line 160), add memory recall:

```python
# After skills loading block (line 158), before instruction building (line 160):

# Recall relevant memories for context injection
memory_context = ""
if settings.memory_enabled:
    try:
        async with AsyncSessionLocal() as memory_db:
            memory_service = MemoryService(memory_db)
            recall_request = MemoryRecallByQueryRequest(
                query=current_prompt[:2000],  # Schema max_length
                limit=settings.memory_max_recall_results,
                min_score=settings.memory_recall_min_score,
            )
            recalled = await memory_service.recall_by_query(recall_request)

        if recalled:
            memory_lines = [
                f"- [{r.score:.2f}] {r.memory.content[:300]}"
                for r in recalled[:settings.memory_context_injection_limit]
            ]
            memory_context = (
                "RELEVANT MEMORIES (from prior interactions — use as context, "
                "not as authoritative facts):\n" + "\n".join(memory_lines)
            )
            logger.info(
                "agent.memory.recall_injected",
                count=len(recalled),
                top_score=recalled[0].score if recalled else 0.0,
            )
    except Exception:
        logger.warning("agent.memory.recall_failed", exc_info=True)

instructions = build_instructions_with_skills(skills_instructions, memory_context) or None
```

**New imports** at top of file:
```python
from app.memory.service import MemoryService
from app.memory.schemas import MemoryRecallByQueryRequest
```

**Key design decisions:**
- Uses `recall_by_query()` which embeds the prompt internally — no separate embedding call needed
- Truncates prompt to 2000 chars (schema max_length)
- Limits injected content to 300 chars per memory + score prefix
- Graceful degradation: if recall fails, continues with empty memory context
- Memory context labeled as "not authoritative facts" to prevent hallucination

**Validation:** `uv run ruff check app/core/agents/service.py && uv run pyright app/core/agents/service.py`

### Step 4: Add LLM-based intent merging to `compact()` (`app/memory/service.py`)

Replace the simple concatenation at line 199 with conditional LLM merging:

```python
# In compact() method, replace lines 193-208 with:

for entry_a, entry_b, _score in pairs:
    if entry_a.recalled_count >= entry_b.recalled_count:
        keep, remove = entry_a, entry_b
    else:
        keep, remove = entry_b, entry_a

    # LLM-based intent merging or simple concatenation
    if settings.memory_llm_merge_enabled:
        merged_content = await self._llm_merge(keep.content, remove.content)
    else:
        merged_content = f"{keep.content}\n---\n{remove.content}"

    merged_embedding = (await _get_embedding().embed([merged_content]))[0]
    await self.repository.merge_entries(
        keep_id=keep.id,
        remove_id=remove.id,
        merged_content=merged_content,
        merged_embedding=merged_embedding,
    )
    merged += 1
```

Add `_llm_merge()` method to `MemoryService`:

```python
async def _llm_merge(self, content_a: str, content_b: str) -> str:
    """Merge two memory entries using LLM-based intent summarization.

    Uses a lightweight LLM call to produce a single coherent memory from
    two similar entries. Falls back to concatenation on failure.

    Args:
        content_a: Content of the higher-recall entry (kept).
        content_b: Content of the lower-recall entry (removed).

    Returns:
        Merged content string.
    """
    from app.core.agents.config import get_llm_settings

    llm_settings = get_llm_settings()
    try:
        from pydantic_ai import Agent as PydanticAgent
        from pydantic_ai.models import KnownModelName

        merge_agent: PydanticAgent[None, str] = PydanticAgent(
            model=cast("KnownModelName", llm_settings.fast_model),
            system_prompt=(
                "Merge these two transit operations memory entries into one "
                "concise summary. Preserve all factual content. Output only "
                "the merged text, no explanation."
            ),
        )
        result = await merge_agent.run(
            f"Entry A:\n{content_a[:500]}\n\nEntry B:\n{content_b[:500]}"
        )
        logger.info("memory.service.llm_merge_completed")
        return result.output
    except Exception:
        logger.warning("memory.service.llm_merge_failed", exc_info=True)
        return f"{content_a}\n---\n{content_b}"
```

**New import** at top of file:
```python
from typing import cast
```

**Validation:** `uv run ruff check app/memory/service.py && uv run pyright app/memory/service.py`

### Step 5: Create background lifecycle tasks (`app/memory/lifecycle.py`)

```python
"""Memory background tasks: periodic compaction and promotion.

Registers as lifespan tasks in app/main.py. Follows the same
start_*/stop_* pattern as transit pollers and evaluators.
"""

from __future__ import annotations

import asyncio
import datetime

from app.core.config import get_settings
from app.core.database import get_db_context
from app.core.logging import get_logger
from app.memory.service import MemoryService

logger = get_logger(__name__)

_compaction_task: asyncio.Task[None] | None = None
_promotion_task: asyncio.Task[None] | None = None


async def _run_at_hour(hour: int, name: str, coro_factory: Callable[[], Awaitable[None]]) -> None:
    """Run a coroutine daily at a specific UTC hour."""
    while True:
        now = datetime.datetime.now(datetime.UTC)
        target = now.replace(hour=hour, minute=0, second=0, microsecond=0)
        if target <= now:
            target += datetime.timedelta(days=1)
        wait_seconds = (target - now).total_seconds()
        logger.info(f"memory.{name}.next_run", wait_seconds=int(wait_seconds), target_hour=hour)
        await asyncio.sleep(wait_seconds)
        try:
            await coro_factory()
        except Exception:
            logger.warning(f"memory.{name}.run_failed", exc_info=True)


async def _run_compaction() -> None:
    """Execute one compaction cycle."""
    async with get_db_context() as db:
        service = MemoryService(db)
        result = await service.compact()
    logger.info(
        "memory.lifecycle.compaction_completed",
        decayed_deleted=result.decayed_deleted,
        merged=result.merged,
        promoted=result.promoted,
    )


async def _run_promotion() -> None:
    """Execute one promotion cycle."""
    async with get_db_context() as db:
        service = MemoryService(db)
        promoted = await service.promote_episodes()
    logger.info("memory.lifecycle.promotion_completed", promoted_count=promoted)


async def start_memory_tasks() -> None:
    """Start periodic memory compaction and promotion tasks."""
    global _compaction_task, _promotion_task  # noqa: PLW0603
    settings = get_settings()

    if not settings.memory_enabled:
        logger.info("memory.lifecycle.disabled")
        return

    _compaction_task = asyncio.create_task(
        _run_at_hour(settings.memory_compaction_cron_hour, "compaction", _run_compaction)
    )
    _promotion_task = asyncio.create_task(
        _run_at_hour(settings.memory_promotion_cron_hour, "promotion", _run_promotion)
    )
    logger.info(
        "memory.lifecycle.tasks_started",
        compaction_hour=settings.memory_compaction_cron_hour,
        promotion_hour=settings.memory_promotion_cron_hour,
    )


async def stop_memory_tasks() -> None:
    """Cancel and clean up memory background tasks."""
    global _compaction_task, _promotion_task  # noqa: PLW0603

    for task, name in [(_compaction_task, "compaction"), (_promotion_task, "promotion")]:
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.warning(f"memory.lifecycle.{name}_stop_failed", exc_info=True)

    _compaction_task = None
    _promotion_task = None
    logger.info("memory.lifecycle.tasks_stopped")
```

**Note:** Add `from collections.abc import Awaitable, Callable` import. The `_run_at_hour` utility calculates sleep until next target hour, then runs the task, then loops for next day.

**Validation:** `uv run ruff check app/memory/lifecycle.py && uv run pyright app/memory/lifecycle.py`

### Step 6: Register memory tasks in lifespan (`app/main.py`)

Add to startup section (after geofence evaluator, line 115):

```python
# Start memory background tasks (compaction + promotion)
from app.memory.lifecycle import start_memory_tasks, stop_memory_tasks
await start_memory_tasks()
```

Add to shutdown section (before `stop_geofence_evaluator()`, line 134):

```python
await stop_memory_tasks()
```

**Validation:** `uv run ruff check app/main.py && uv run pyright app/main.py`

### Step 7: Add tests for memory recall injection (`app/core/agents/tests/test_service.py`)

Add tests covering:

1. **`test_chat_injects_recalled_memories`** — Mock `MemoryService.recall_by_query()` to return 2 memories with scores 0.9/0.5. Verify `build_instructions_with_skills` is called with non-empty memory_context containing both scores. Use `agent.override(model=TestModel())`.

2. **`test_chat_skips_memory_when_disabled`** — Set `memory_enabled=False` via `patch("app.core.agents.service.get_settings")`. Verify `MemoryService` is never instantiated.

3. **`test_chat_continues_on_memory_recall_failure`** — Mock `recall_by_query()` to raise `RuntimeError`. Verify `agent.run()` still executes (graceful degradation). Check logger.warning called with "agent.memory.recall_failed".

4. **`test_chat_memory_context_format`** — Verify the injected memory context string starts with "RELEVANT MEMORIES" and contains score brackets like `[0.90]`.

5. **`test_chat_respects_min_score_setting`** — Set `memory_recall_min_score=0.5`. Mock recall to return memories. Verify `MemoryRecallByQueryRequest` constructed with `min_score=0.5`.

**Mock patterns** (from existing tests):
- `patch("app.core.agents.service.get_settings")` for config
- `patch("app.core.agents.service.AsyncSessionLocal")` for DB session
- `patch("app.core.agents.service.MemoryService")` for service class
- `agent.override(model=TestModel())` for agent execution

**Validation:** `uv run pytest app/core/agents/tests/test_service.py -v --tb=short`

### Step 8: Add tests for LLM intent merging (`app/memory/tests/test_service.py`)

Add tests covering:

1. **`test_compact_uses_llm_merge_when_enabled`** — Set `memory_llm_merge_enabled=True`. Mock `_llm_merge()` to return "merged text". Verify `merge_entries` called with LLM output, not concatenation.

2. **`test_compact_falls_back_on_llm_failure`** — Set `memory_llm_merge_enabled=True`. Mock `_llm_merge()` to raise. Verify merge uses concatenation fallback.

3. **`test_compact_uses_concatenation_when_llm_disabled`** — Default settings (`memory_llm_merge_enabled=False`). Verify merge uses `f"{keep.content}\n---\n{remove.content}"`.

4. **`test_llm_merge_truncates_content`** — Verify content_a and content_b are truncated to 500 chars in the prompt.

**Validation:** `uv run pytest app/memory/tests/test_service.py -v --tb=short`

### Step 9: Add tests for lifecycle tasks (`app/memory/tests/test_lifecycle.py`)

Add tests covering:

1. **`test_start_memory_tasks_creates_tasks_when_enabled`** — Mock settings with `memory_enabled=True`. Call `start_memory_tasks()`. Verify two asyncio tasks created. Clean up with `stop_memory_tasks()`.

2. **`test_start_memory_tasks_skips_when_disabled`** — Set `memory_enabled=False`. Verify no tasks created.

3. **`test_stop_memory_tasks_cancels_running_tasks`** — Start tasks, then stop. Verify both tasks are cancelled.

4. **`test_run_compaction_calls_service`** — Mock `get_db_context()` and `MemoryService`. Call `_run_compaction()`. Verify `service.compact()` called.

5. **`test_run_promotion_calls_service`** — Mock `get_db_context()` and `MemoryService`. Call `_run_promotion()`. Verify `service.promote_episodes()` called.

**Validation:** `uv run pytest app/memory/tests/test_lifecycle.py -v --tb=short`

## Preflight Warnings

- `app/core/agents/tests/test_service.py` has only 6 tests and uses `agent.override(model=TestModel())` — ensure new tests follow same pattern
- `app/memory/tests/test_service.py` uses `svc.repository = AsyncMock()` pattern — compact test mocks must set up all 4 steps (decay, delete_decayed, find_similar_pairs, find_promotable)
- `build_instructions_with_skills()` currently has no tests — adding memory_context param must not break existing callers (default `""` ensures backwards compatibility)

## Security Checklist

- [x] No new endpoints added (integration is internal to agent pipeline)
- [x] Memory content truncated to 300 chars in context injection (prevents token overflow)
- [x] User prompt truncated to 2000 chars for recall query (schema max_length)
- [x] LLM merge content truncated to 500 chars per entry
- [x] Memory context labeled "not authoritative facts" (anti-hallucination)
- [x] All new config settings have safe defaults (`memory_llm_merge_enabled=False`)
- [x] Background tasks gated on `memory_enabled` setting
- [x] All exceptions caught with warning-level logging (no crash paths)

## Verification

- [ ] `make lint` passes (ruff format + check)
- [ ] `make types` passes (mypy + pyright)
- [ ] `make test` passes (all unit tests including new ones)
- [ ] Pyright errors for `app/core/agents/` <= 6 (pre-existing baseline)
- [ ] Pyright errors for `app/memory/` = 0 (clean baseline)
- [ ] Mypy errors for `app/core/agents/` <= 3 (pre-existing baseline)
- [ ] New test count: 12+ tests across 3 test files
- [ ] `make security-audit-quick` passes
