# Plan: AI-3.3 Memory Bridge — Auto-Persist from Agent Results

## Context

Create `app/memory/bridge.py` — a fire-and-forget callback that auto-persists successful multi-tool agent interactions as episodic memories. The bridge captures what the agent learned without manual intervention. Failure-safe: exceptions caught, logged, never crash pipeline. This is the mechanism that makes memory actually accumulate over time.

Adapted from email-hub's `HandoffMemoryBridge` pattern and VTV's existing fire-and-forget patterns (`app/alerts/evaluator.py`, `app/geofences/evaluator.py`).

## Security Context Assessment

**Active contexts:**
- **CTX-AGENT** — Bridge interacts with agent results and stores LLM-derived content. Must sanitize output, verify no credential exposure in stored memories.
- **CTX-INPUT** — Content from agent responses stored in DB. Must respect `max_length=10000` on `MemoryEntryCreate.content`.

**Not active:** CTX-AUTH (no auth changes), CTX-RBAC (no new endpoints), CTX-FILE (no file handling), CTX-INFRA (no config changes).

## Research Summary

### Integration Point: `AgentService.chat()` (`app/core/agents/service.py:99-238`)
- Standard tier: `result = await agent.run(...)` at line 182-188, `result.output` at line 189
- Complex tier: `pipeline_result = await pipeline.run(...)` at line 164-169, `.output` at line 170
- Both paths produce `response_content: str` before response construction (line 210+)
- Bridge must handle BOTH paths — extract tool names from `result` (standard) or `pipeline_result` (complex)

### Pydantic AI Message Types (already imported in service.py:12-18)
- `ModelResponse` has `.parts: list[ModelResponsePart]`
- `ToolCallPart` has `.tool_name: str`, `.args`, `.tool_call_id`
- Need to add `ToolCallPart` to imports

### Memory Service API (`app/memory/service.py:53-93`)
```python
async def store(self, data: MemoryEntryCreate) -> MemoryEntry:
    # Auto-generates embedding if None
    # Checks for duplicates (threshold 0.95)
    # Returns stored MemoryEntry
```

### MemoryEntryCreate Schema (`app/memory/schemas.py:12-22`)
```python
MemoryEntryCreate(
    agent_type="transit",           # str, max_length=50
    memory_type="episodic",         # Literal["procedural","episodic","semantic","query_pattern"]
    content="...",                  # str, max_length=10000
    metadata_json={...},           # dict[str, Any] | None
    source="agent",                # Literal["agent","dispatcher","compaction"]
)
```

### Standalone DB Session (`app/core/database.py:46-59`)
```python
async with get_db_context() as db:
    service = MemoryService(db)
    await service.store(data)
```

### Config (`app/core/config.py:249-258`)
- `memory_enabled: bool = True` — gate for bridge
- No bridge-specific settings needed yet (min_tools threshold hardcoded to 2)

### Existing Bridge Pattern: `app/fleet/bridge.py`
- `TraccarBridge` — webhook receiver → normalization → async storage
- Logs at multiple stages, returns success/failure boolean

## Test Landscape

### Memory Test Fixtures (`app/memory/tests/conftest.py`)
- `make_memory(**overrides)` — factory with sensible defaults
- `make_embedding(dim=1024)` — dummy embedding `[0.1] * dim`
- `mock_db` — `AsyncMock` session
- `service` — `MemoryService` with mocked repository

### Agent Test Patterns (`app/core/agents/tests/test_service.py`)
- `_create_service()` — creates `AgentService` with mocked deps
- Uses `agent.override(model=TestModel())` for deterministic responses
- `models.ALLOW_MODEL_REQUESTS = False` prevents real LLM calls

### get_db_context Mock Pattern (from alerts/tests)
```python
ctx = AsyncMock()
ctx.__aenter__ = AsyncMock(return_value=mock_session)
ctx.__aexit__ = AsyncMock(return_value=False)
mock_db_ctx.return_value = ctx
```

## Type Check Baseline

| Target | Pyright | Mypy |
|--------|---------|------|
| `app/memory/` | 0 errors | 0 errors (3 leaked from agents) |
| `app/core/agents/` | 6 errors | 3 errors |

All pre-existing. Bridge must not increase these counts.

## Files to Create/Modify

| Action | File | Purpose |
|--------|------|---------|
| CREATE | `app/memory/bridge.py` | Fire-and-forget memory persistence callback |
| UPDATE | `app/core/agents/service.py` | Wire bridge after `agent.run()` / `pipeline.run()` |
| CREATE | `app/memory/tests/test_bridge.py` | 8+ unit tests for bridge logic |

## Implementation Steps

### Step 1: Create `app/memory/bridge.py`

CREATE `app/memory/bridge.py` with:

```python
"""Memory bridge — fire-and-forget auto-persistence of agent episodes.

Captures multi-tool agent interactions as episodic memories without
blocking the response pipeline. All exceptions are caught and logged.
"""

import asyncio
from typing import Any

from pydantic_ai.messages import ModelMessage, ModelResponse, ToolCallPart

from app.core.config import get_settings
from app.core.database import get_db_context
from app.core.logging import get_logger
from app.memory.schemas import MemoryEntryCreate
from app.memory.service import MemoryService

logger = get_logger(__name__)


def extract_tool_names(messages: list[ModelMessage]) -> list[str]:
    """Extract unique tool names from agent message history.

    Args:
        messages: Full message history from agent.run().all_messages().

    Returns:
        Deduplicated list of tool names in call order.
    """
    seen: set[str] = set()
    tools: list[str] = []
    for msg in messages:
        if isinstance(msg, ModelResponse):
            for part in msg.parts:
                if isinstance(part, ToolCallPart) and part.tool_name not in seen:
                    seen.add(part.tool_name)
                    tools.append(part.tool_name)
    return tools


async def _persist_episode(
    agent_name: str,
    prompt: str,
    response: str,
    tools_used: list[str],
    confidence: float | None = None,
) -> None:
    """Store an episodic memory entry for a multi-tool interaction.

    Opens its own DB session via get_db_context() for isolation.
    Never raises — all exceptions caught and logged as warnings.

    Args:
        agent_name: Name of the agent that processed the request.
        prompt: Original user prompt (truncated to 150 chars in content).
        response: Agent's final response (truncated to 300 chars in content).
        tools_used: List of distinct tool names used.
        confidence: Optional confidence score for metadata.
    """
    try:
        content = (
            f"[{agent_name}] Dispatcher asked: {prompt[:150]}. "
            f"Agent used: {', '.join(tools_used)}. "
            f"Response: {response[:300]}"
        )

        metadata: dict[str, Any] = {
            "source": "agent",
            "agent_name": agent_name,
            "tools": tools_used,
        }
        if confidence is not None:
            metadata["confidence"] = confidence

        data = MemoryEntryCreate(
            agent_type=agent_name,
            memory_type="episodic",
            content=content,
            metadata_json=metadata,
            source="agent",
        )

        async with get_db_context() as db:
            service = MemoryService(db)
            entry = await service.store(data)

        logger.info(
            "memory.bridge.episode_stored",
            memory_id=entry.id,
            agent_name=agent_name,
            tools_used=tools_used,
            tool_count=len(tools_used),
        )
    except Exception:
        logger.warning("memory.bridge.storage_failed", exc_info=True)


def persist_agent_episode(
    agent_name: str,
    prompt: str,
    response: str,
    messages: list[ModelMessage],
    min_tools: int = 2,
) -> None:
    """Fire-and-forget: persist a multi-tool agent interaction as episodic memory.

    Only persists when the interaction used >= min_tools distinct tools.
    Spawns a background asyncio task — does not block the caller.

    Args:
        agent_name: Name of the agent (e.g. "transit_agent").
        prompt: Original user prompt.
        response: Agent's final response text.
        messages: Full message history from agent run.
        min_tools: Minimum distinct tools required to persist (default 2).
    """
    settings = get_settings()
    if not settings.memory_enabled:
        return

    tools_used = extract_tool_names(messages)
    if len(tools_used) < min_tools:
        return

    logger.info(
        "memory.bridge.episode_persisting",
        agent_name=agent_name,
        tool_count=len(tools_used),
        tools=tools_used,
    )

    asyncio.create_task(_persist_episode(  # noqa: RUF006
        agent_name=agent_name,
        prompt=prompt,
        response=response,
        tools_used=tools_used,
    ))
```

Notes:
- `noqa: RUF006` on `asyncio.create_task` — fire-and-forget is intentional, we don't await
- `extract_tool_names` is a pure function (easy to test)
- `persist_agent_episode` is sync (returns immediately), spawns async task
- `_persist_episode` is the actual async worker with exception safety
- Content respects `max_length=10000` — truncation of prompt (150) + tools + response (300) keeps it well under

**Validation:** `uv run ruff format app/memory/bridge.py && uv run ruff check --fix app/memory/bridge.py && uv run pyright app/memory/bridge.py && uv run mypy app/memory/bridge.py`

### Step 2: Wire bridge into `AgentService.chat()`

UPDATE `app/core/agents/service.py`:

1. Add import at top (after existing pydantic_ai.messages import):
   ```python
   from pydantic_ai.messages import ToolCallPart  # add to existing import block
   from app.memory.bridge import persist_agent_episode
   ```

2. After standard tier execution (line 189, after `response_content = result.output`), add:
   ```python
   # Fire-and-forget: persist multi-tool episodes as memory
   persist_agent_episode(
       agent_name="transit_agent",
       prompt=current_prompt,
       response=response_content,
       messages=result.all_messages(),
   )
   ```

3. **Skip complex tier path** — `PipelineResult` is a custom dataclass (`pipeline.py:42-49`) with only `output`, `phases_completed`, `total_duration_ms`, `phase_details`. It does NOT expose message history. The internal `agent_result` per-phase has `all_messages()` but is scoped to one phase and not surfaced. Wiring the bridge into the complex path would require changing `PipelineResult` to collect messages — out of scope for AI-3.3. Only standard tier gets the bridge.

**Validation:** `uv run ruff format app/core/agents/service.py && uv run ruff check --fix app/core/agents/service.py && uv run pyright app/core/agents/service.py`

### Step 3: Create tests

CREATE `app/memory/tests/test_bridge.py` with these test cases:

1. **`test_extract_tool_names_from_messages`** — Build a message list with 3 `ToolCallPart` entries (2 distinct tools). Assert returns `["tool_a", "tool_b"]` in order, deduplicated.

2. **`test_extract_tool_names_empty_messages`** — Empty message list → empty tool list.

3. **`test_extract_tool_names_no_tool_calls`** — Messages with only `TextPart` → empty tool list.

4. **`test_persist_agent_episode_skips_single_tool`** — Call `persist_agent_episode` with messages containing only 1 tool. Assert `asyncio.create_task` NOT called.

5. **`test_persist_agent_episode_fires_for_multi_tool`** — Call with 2+ tools. Assert `asyncio.create_task` IS called.

6. **`test_persist_agent_episode_skips_when_memory_disabled`** — Mock `get_settings().memory_enabled = False`. Assert task NOT created.

7. **`test_persist_episode_stores_memory`** — Call `_persist_episode` directly. Mock `get_db_context` + `MemoryService.store`. Assert `store` called with correct `MemoryEntryCreate` (memory_type="episodic", source="agent", content contains prompt/tools/response).

8. **`test_persist_episode_catches_db_error`** — Mock `get_db_context` to raise `Exception`. Assert no exception propagates, warning logged.

9. **`test_persist_episode_content_format`** — Verify content string matches format: `"[agent_name] Dispatcher asked: {prompt}. Agent used: {tools}. Response: {response}"`.

10. **`test_persist_episode_truncates_long_input`** — Pass 500-char prompt + 1000-char response. Verify content uses truncated versions (150 + 300 chars).

Mock patterns to use:
- `@patch("app.memory.bridge.get_db_context")` for DB isolation
- `@patch("app.memory.bridge.get_settings")` for memory_enabled toggle
- `@patch("app.memory.bridge.asyncio.create_task")` for fire-and-forget verification
- Build `ModelResponse` with `ToolCallPart` instances for realistic message data
- Use `AsyncMock` for `MemoryService.store`

**Validation:** `uv run ruff format app/memory/tests/test_bridge.py && uv run ruff check --fix app/memory/tests/test_bridge.py && uv run pytest app/memory/tests/test_bridge.py -v`

## Preflight Warnings

- `app/core/agents/service.py` has 2 execution paths (standard + complex tier). Bridge only wired into standard tier — `PipelineResult` (complex tier, `pipeline.py:42-49`) is a plain dataclass without message history. Surfacing messages from the pipeline is a separate task.
- Standard tier `result` from `agent.run()` (line 182-188) is a pydantic_ai `RunResult` with `.all_messages()` — confirmed available.
- `asyncio.create_task` without storing the reference triggers `RUF006` — suppress with `# noqa: RUF006`.
- `ToolCallPart` import must be added to the existing `from pydantic_ai.messages import (...)` block in service.py — NOT as a separate import (Ruff I001 isort).

## Security Checklist

- [x] No new endpoints — bridge is internal only
- [x] No auth changes needed
- [x] Content truncated to prevent oversized memory entries
- [x] No credentials stored — content is agent prompts/responses only
- [x] All exceptions caught in `_persist_episode` — pipeline never blocked
- [x] Uses `get_db_context()` for session isolation (no request-scoped session leak)
- [x] Logging follows `memory.bridge.*` domain pattern

## Anti-Pattern Checklist

- [x] AP-5: No unused imports — only import what's used
- [x] AP-7: All functions have return type annotations
- [x] AP-9: No unused function params (ARG001)
- [x] AP-37: Bare `except: pass` forbidden — we log in except blocks
- [x] AP-38: Background tasks handle exceptions properly

## Verification

- [ ] `uv run ruff format app/memory/bridge.py app/core/agents/service.py app/memory/tests/test_bridge.py`
- [ ] `uv run ruff check --fix app/memory/ app/core/agents/service.py`
- [ ] `uv run pyright app/memory/ app/core/agents/service.py` — errors <= baseline (0 for memory, 6 for agents)
- [ ] `uv run mypy app/memory/ app/core/agents/service.py` — errors <= baseline
- [ ] `uv run pytest app/memory/tests/test_bridge.py -v` — all pass
- [ ] `uv run pytest app/memory/tests/ -v` — existing memory tests still pass
- [ ] `uv run pytest app/core/agents/tests/ -v` — existing agent tests still pass
- [ ] `make check` passes (lint + types + tests)
