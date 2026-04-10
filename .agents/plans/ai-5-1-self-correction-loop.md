# Plan: AI-5.1 Self-Correction Loop

## Context

After `agent.run()` returns, `AgentService.chat()` runs `validate_transit_response()` (deterministic QA: route plausibility, delay range, stale data, Latvian diacritics). Today, validation issues are appended to the response as ⚠️ footnotes — but the *incorrect* content is still shown to dispatchers.

AI-5.1 introduces one bounded retry: when validation fails, re-run the agent once with the failure context injected as a new user turn. If the second attempt is clean, return the corrected response. If it still fails, fall back to current behavior (response + footnotes). Transit needs fast responses, so the loop is capped at exactly 1 retry.

The infrastructure already exists: `validate_transit_response()` works, `agent.run()` is centralized, structured logging conventions are established, and `TestModel`-based unit tests can fake first/second attempt outputs. This task is a thin orchestration layer around what's already there.

## Security Context Assessment

**Active contexts:** CTX-AGENT, CTX-INPUT (mild)

- **CTX-AGENT** — Core agent path. Concerns:
  - **Output sanitization** — corrected output still flows through `validate_transit_response()`; same anti-hallucination treatment as before.
  - **No credential exposure** — correction prompt embeds the *failed agent response* and the *validation warnings* (both already logged); no secrets.
  - **Tool permission unchanged** — same `Agent[UnifiedDeps, str]`, same deps, same RBAC surface. Retry uses identical model/instructions/deps.
  - **Bounded loop** — hard cap `MAX_SELF_CORRECTION_ROUNDS = 1` prevents prompt-injection from forcing unbounded retries / token amplification attacks.
  - **Fail-open on validator exception** — if `validate_transit_response()` itself throws, log and return original response (do NOT block dispatchers from getting an answer).
- **CTX-INPUT (mild)** — No new HTTP params. Correction prompt is server-constructed from already-validated input; no fresh user surface.

**Not active:** CTX-AUTH, CTX-RBAC (no new endpoints), CTX-FILE, CTX-INFRA.

## Research Summary

### Current `agent.run()` callsites (`app/core/agents/service.py`)

- **Standard tier (lines 214–222):** `result = await agent.run(current_prompt, deps=..., message_history=..., instructions=..., model=tier_model)` → `response_content = result.output`
- **Complex tier (lines 195–202):** `pipeline_result = await pipeline.run(current_prompt, message_history=..., instructions=..., model=tier_model)` → `response_content = pipeline_result.output`. The pipeline is its own multi-phase orchestrator (`app/core/agents/pipeline.py`).
- **Memory persistence (lines 224–230):** Standard-tier only. `persist_agent_episode(messages=result.all_messages())` — must use the *final* (corrected) attempt's `all_messages()`.
- **Validation + footnote append (lines 240–249):** Reused as the post-loop fallback path.

### Existing validator (`app/core/agents/validation.py`)

- `validate_transit_response(response: str) -> ValidationResult` (line 80)
- `ValidationResult.is_valid` is set to `False` whenever `warnings` is non-empty (line 102).
- Trigger condition for retry: `validation.warnings` non-empty (i.e. `not validation.is_valid`).
- Pure function — no DB / HTTP, safe to call repeatedly.
- One stateful gotcha: `_check_stale_data` reads module-global `last_stale_data_timestamp`. The same warning will reappear on retry → must NOT count "stale data" as a retryable failure (the agent can't fix it). **Filter stale-data warnings from the retry trigger** but still pass them to footnotes.

### Config patterns (`app/core/config.py`)

Existing fields are flat snake_case (e.g. `memory_enabled`, `memory_max_recall_results` at lines 260–275). No `__` nesting. The task spec wrote `AGENT__SELF_CORRECTION_ENABLED`; we'll match the codebase convention as `agent_self_correction_enabled` and `agent_max_correction_rounds` — env vars will be `AGENT_SELF_CORRECTION_ENABLED` / `AGENT_MAX_CORRECTION_ROUNDS` (single underscore, BaseSettings auto-uppercase).

### Logging conventions (`app/core/agents/service.py:129–149`)

```python
logger.info("agent.chat_started", message_count=..., user_prompt_length=...)
logger.info("agent.chat_completed", response_id=..., output_length=...)
logger.warning("agent.response_validation_warning", warning=...)
```

Format: `agent.<component>.<action>_<state>`. Our events: `agent.correction.triggered`, `agent.correction.resolved`, `agent.correction.exhausted`, `agent.correction.failed`.

### Test patterns (`app/core/agents/tests/test_service.py`)

```python
from pydantic_ai.models.test import TestModel
from app.core.agents.agent import agent

with patch("app.core.agents.service.create_unified_deps") as mock_deps:
    mock_deps.return_value.transit_http_client = AsyncMock()
    mock_deps.return_value.obsidian_http_client = AsyncMock()
    service = AgentService()

with agent.override(model=TestModel()):
    with patch("app.core.agents.service.logger"):
        response = await service.chat(request)
```

`TestModel` returns canned strings; for two-attempt sequences we'll mock `agent.run()` directly with `AsyncMock(side_effect=[first_result, second_result])` rather than `TestModel`, since we need different outputs per attempt.

## Test Landscape

- **Existing agent tests:** `app/core/agents/tests/test_service.py` (10+ tests, `_create_service()` helper, `TestModel` + logger patches).
- **Validation tests:** `app/core/agents/tests/test_validation.py` exists — covers `validate_transit_response()` directly. Reuse the same fixture inputs (route 9999, "5 minutes late") to keep correction tests deterministic.
- **Conftest:** root `/conftest.py` clears auth cache + patches `LLM_PROVIDER` env for unit tests; no agent-specific fixtures needed.
- **Async marker:** `@pytest.mark.asyncio`. Unit tests only — no `@pytest.mark.integration`.
- **Logger assertions:** `mock_logger.info.assert_any_call("agent.correction.triggered", round=1, ...)`.
- **Mock idiom for two-call sequences:**
  ```python
  fake_first = MagicMock(output="Take route 9999 from Brivibas iela.", all_messages=lambda: [])
  fake_second = MagicMock(output="Take route 5 from Brīvības iela.", all_messages=lambda: [])
  with patch("app.core.agents.correction.agent.run", new=AsyncMock(side_effect=[fake_first, fake_second])):
      ...
  ```

## Type-Check Baseline (`app/core/agents/`)

**Pyright:** 6 errors, 0 warnings — pre-existing, unrelated to AI-5.1:
- `pipeline.py:49` (list[Unknown]), `pipeline.py:136` (×2 model arg-type), `tools/transit/client.py:193` (possibly unbound), `validation.py:76` (list[Unknown])

**Mypy:** 3 errors — pre-existing:
- `tools/transit/static_store.py:149`, `:150` (AsyncResult/aiter mismatch), `pipeline.py:136` (model arg-type)

**AI-5.1 acceptance:** Pyright ≤ 6 errors, mypy ≤ 3 errors after implementation. New file `correction.py` must be 0 errors. We will NOT touch `validation.py:76` even though it shows up — out of scope.

## Files to Create/Modify

| Action | File | Purpose |
|--------|------|---------|
| CREATE | `app/core/agents/correction.py` | `SelfCorrectionLoop` class + `CorrectedResult` dataclass + correction prompt builder |
| CREATE | `app/core/agents/tests/test_correction.py` | 12 unit tests covering happy path, retry, exhaustion, disabled flag, edge cases |
| UPDATE | `app/core/config.py` | Add `agent_self_correction_enabled: bool = True`, `agent_max_correction_rounds: int = 1` (after `memory_*` fields, before `model_validator` at line 277) |
| UPDATE | `app/core/agents/service.py` | Replace standard-tier `agent.run()` block (lines 214–230) with `SelfCorrectionLoop.run_with_correction()` call; keep complex-tier path UNCHANGED for now (pipeline already has its own retry layer) |
| UPDATE | `.env.example` | Document `AGENT_SELF_CORRECTION_ENABLED=true`, `AGENT_MAX_CORRECTION_ROUNDS=1` |

**Out of scope:** Wrapping the complex-tier pipeline. The pipeline (`app/core/agents/pipeline.py`) is multi-phase and already has `max_retries` per phase. Adding correction there is AI-5.2 territory.

## Implementation Steps

### Step 1 — Add config fields

`app/core/config.py`, after line 275 (`memory_promotion_cron_hour`), before the `@model_validator` at line 277:

```python
    # Self-correction loop (AI-5.1)
    agent_self_correction_enabled: bool = True
    agent_max_correction_rounds: int = 1  # Transit needs fast responses; 1 retry only
```

**Validation:** `uv run ruff format app/core/config.py && uv run ruff check app/core/config.py && uv run pyright app/core/config.py && uv run mypy app/core/config.py`

### Step 2 — Create `correction.py`

`app/core/agents/correction.py`:

```python
"""Bounded self-correction loop for agent responses (AI-5.1).

Wraps `agent.run()` with one deterministic QA check + at most one retry.
If validation fails on first attempt, the loop re-invokes the agent with
the failed response and warnings injected as a corrective user turn.
If the retry also fails, returns the (still-failed) response with the
warnings preserved for footnote rendering — same fallback as before.

The loop ONLY targets the standard tier. Complex-tier pipeline runs are
handled by `pipeline.py` and will get their own correction in AI-5.2.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)

from app.core.agents.validation import ValidationResult, validate_transit_response
from app.core.logging import get_logger

if TYPE_CHECKING:
    from pydantic_ai import Agent
    from pydantic_ai.models import KnownModelName, Model

    from app.core.agents.tools.transit.deps import UnifiedDeps

logger = get_logger(__name__)

# Validator warnings whose root cause the agent CANNOT fix by retrying.
# Stale-data warnings come from the cache circuit-breaker, not the LLM
# response — retrying just burns tokens. These still get appended as
# footnotes; they just don't trigger a retry.
_NON_RETRYABLE_PREFIXES: tuple[str, ...] = (
    "This response may be based on cached data",
)


@dataclass
class CorrectedResult:
    """Outcome of a self-correction loop run.

    Attributes:
        output: Final response text (corrected or original).
        warnings: Validation warnings remaining after the loop. Empty if
            the loop produced a clean response. Otherwise the same list
            the caller would render as footnotes.
        rounds_used: Total number of `agent.run()` invocations (1 = no
            retry, 2 = one retry).
        all_messages: `result.all_messages()` from the *final* attempt —
            used by `persist_agent_episode()` for memory persistence.
        corrected: True iff a retry happened AND it produced a clean
            response.
    """

    output: str
    warnings: list[str] = field(default_factory=list)
    rounds_used: int = 1
    all_messages: list[ModelMessage] = field(default_factory=list)
    corrected: bool = False


def _retryable_warnings(warnings: list[str]) -> list[str]:
    """Filter out warnings the agent cannot fix by retrying.

    Args:
        warnings: All validation warnings from `ValidationResult`.

    Returns:
        Subset of warnings that justify a retry. Empty list means the
        loop should stop and return the current response.
    """
    return [w for w in warnings if not w.startswith(_NON_RETRYABLE_PREFIXES)]


def _build_correction_turn(
    failed_response: str,
    warnings: list[str],
) -> ModelMessage:
    """Build the corrective user turn appended to message history on retry.

    The turn explicitly tells the agent what went wrong and asks it to
    re-answer the original question with the issues corrected.

    Args:
        failed_response: The agent's first-attempt output.
        warnings: Retryable validation warnings to surface.

    Returns:
        A `ModelRequest` containing a `UserPromptPart` with the
        correction instructions.
    """
    bullet_list = "\n".join(f"- {w}" for w in warnings)
    correction_text = (
        "Your previous answer contained the following validation issues:\n"
        f"{bullet_list}\n\n"
        "Previous answer for reference:\n"
        f"---\n{failed_response}\n---\n\n"
        "Please re-answer the original question. Use only real route "
        "numbers, plausible delay values, and correct Latvian diacritics. "
        "Do not repeat the same mistakes."
    )
    return ModelRequest(parts=[UserPromptPart(content=correction_text)])


class SelfCorrectionLoop:
    """Runs `agent.run()` with one deterministic QA + bounded retry.

    Usage:
        loop = SelfCorrectionLoop(max_rounds=1)
        result = await loop.run_with_correction(
            agent_instance, prompt, deps, history, instructions, model,
        )
        response = result.output

    The loop is intentionally stateless beyond construction: a single
    instance is safe to share across requests. All per-call context is
    passed to `run_with_correction()`.
    """

    def __init__(self, max_rounds: int = 1) -> None:
        """Construct a correction loop.

        Args:
            max_rounds: Number of *retries* allowed (NOT total attempts).
                `max_rounds=1` → up to 2 `agent.run()` calls. Capped at
                3 for safety.
        """
        if max_rounds < 0:
            max_rounds = 0
        if max_rounds > 3:
            max_rounds = 3
        self._max_rounds = max_rounds

    async def run_with_correction(
        self,
        agent_instance: "Agent[UnifiedDeps, str]",
        prompt: str,
        *,
        deps: "UnifiedDeps",
        message_history: list[ModelMessage] | None,
        instructions: str | None,
        model: "Model | KnownModelName | str | None",
    ) -> CorrectedResult:
        """Run the agent with up to one corrective retry.

        Args:
            agent_instance: The Pydantic AI agent singleton.
            prompt: The user's current prompt (last message content).
            deps: Unified deps for transit + vault tools.
            message_history: Prior conversation history (or None).
            instructions: System instructions including skills + memory.
            model: Tier-resolved model override (or None).

        Returns:
            `CorrectedResult` containing final output, residual warnings,
            rounds used, final-attempt messages, and a `corrected` flag.

        Raises:
            Whatever `agent.run()` raises — caller wraps in
            `AgentExecutionError`. Validator exceptions are caught
            internally and treated as "no warnings".
        """
        history: list[ModelMessage] = list(message_history) if message_history else []
        current_prompt = prompt
        last_warnings: list[str] = []
        last_output = ""
        last_messages: list[ModelMessage] = []

        for attempt in range(self._max_rounds + 1):
            result = await agent_instance.run(
                current_prompt,
                deps=deps,
                message_history=history if history else None,
                instructions=instructions,
                model=model,
            )
            last_output = result.output
            last_messages = list(result.all_messages())

            validation = self._safe_validate(last_output)
            last_warnings = list(validation.warnings)

            retryable = _retryable_warnings(last_warnings)
            if not retryable:
                # Either fully clean OR only non-retryable warnings (e.g.
                # stale data). Done.
                if attempt > 0:
                    logger.info(
                        "agent.correction.resolved",
                        round=attempt,
                        residual_warnings=len(last_warnings),
                    )
                return CorrectedResult(
                    output=last_output,
                    warnings=last_warnings,
                    rounds_used=attempt + 1,
                    all_messages=last_messages,
                    corrected=attempt > 0,
                )

            if attempt >= self._max_rounds:
                # Out of retries. Fall through to exhausted branch.
                break

            logger.info(
                "agent.correction.triggered",
                round=attempt + 1,
                warning_count=len(retryable),
                first_warning=retryable[0][:120],
            )

            # Append the failed assistant turn + corrective user turn to
            # history, then re-prompt with an empty current_prompt? No —
            # Pydantic AI requires a non-empty prompt argument. Use the
            # correction text AS the prompt and pass the original
            # history (we don't double-add the failed exchange because
            # `result.all_messages()` already includes it for the next
            # call's history if we wanted, but we want a fresh framing).
            failed_assistant_turn = ModelResponse(parts=[TextPart(content=last_output)])
            history = [
                *(message_history or []),
                ModelRequest(parts=[UserPromptPart(content=prompt)]),
                failed_assistant_turn,
            ]
            current_prompt = self._build_correction_prompt_text(last_output, retryable)

        logger.warning(
            "agent.correction.exhausted",
            rounds=self._max_rounds + 1,
            final_warning_count=len(last_warnings),
        )
        return CorrectedResult(
            output=last_output,
            warnings=last_warnings,
            rounds_used=self._max_rounds + 1,
            all_messages=last_messages,
            corrected=False,
        )

    @staticmethod
    def _safe_validate(response: str) -> ValidationResult:
        """Run the validator, swallowing exceptions as "no warnings".

        A crashing validator must NEVER prevent dispatchers from getting
        an answer. The original response is returned as-is.
        """
        try:
            return validate_transit_response(response)
        except Exception:
            logger.error("agent.correction.failed", exc_info=True)
            return ValidationResult(is_valid=True, warnings=[], sanitized_response=response)

    @staticmethod
    def _build_correction_prompt_text(failed_response: str, warnings: list[str]) -> str:
        """Construct the corrective prompt text for the retry attempt."""
        bullet_list = "\n".join(f"- {w}" for w in warnings)
        return (
            "Your previous answer contained the following validation issues:\n"
            f"{bullet_list}\n\n"
            "Previous answer for reference:\n"
            f"---\n{failed_response}\n---\n\n"
            "Please re-answer the original question with these issues corrected. "
            "Use only real route numbers (1-999), plausible delay values "
            "(0-1440 minutes), and correct Latvian diacritics. Do not repeat "
            "the same mistakes."
        )


__all__ = ["CorrectedResult", "SelfCorrectionLoop"]
```

**Anti-pattern checks:**
- #2 No `object` hints — uses `ModelMessage`, `ValidationResult`, etc.
- #5 No unused imports — `time` was originally imported but is unused; **remove** before saving.
- #7 Test helpers will need `-> ReturnType` annotations (covered in Step 4).
- #8 No EN DASH — uses `-`, `---` (three hyphens) only.
- #18 Every parameter is used.
- #28 No bare `[]` — all list literals annotated or constructed via `field(default_factory=list)`.
- #54 Constrained strings — N/A here.

**Validation:** `uv run ruff format app/core/agents/correction.py && uv run ruff check app/core/agents/correction.py && uv run pyright app/core/agents/correction.py && uv run mypy app/core/agents/correction.py`

> **Note for executor:** I retained `time` in the imports during drafting but never used it. Drop the `import time` line before the first ruff run, or F401 will fire. Same for `_build_correction_turn` — it's unused (I inlined the prompt-text builder as a static method instead). Delete `_build_correction_turn` before the first ruff run.

### Step 3 — Wire `SelfCorrectionLoop` into `AgentService.chat()`

`app/core/agents/service.py`:

1. Add import near line 23:
   ```python
   from app.core.agents.correction import CorrectedResult, SelfCorrectionLoop
   ```

2. In `AgentService.__init__` (line 98), construct the loop once:
   ```python
   def __init__(self) -> None:
       """Initialize with unified dependencies for agent tool execution."""
       self._deps: UnifiedDeps = create_unified_deps()
       settings = get_settings()
       self._correction_loop: SelfCorrectionLoop | None = (
           SelfCorrectionLoop(max_rounds=settings.agent_max_correction_rounds)
           if settings.agent_self_correction_enabled
           else None
       )
   ```

3. Replace the standard-tier `else` block (lines 214–230) with:
   ```python
   else:
       if self._correction_loop is not None:
           corrected: CorrectedResult = await self._correction_loop.run_with_correction(
               agent,
               current_prompt,
               deps=self._deps,
               message_history=message_history,
               instructions=instructions,
               model=tier_model,
           )
           response_content = corrected.output
           # Memory persistence uses the FINAL attempt's messages.
           persist_agent_episode(
               agent_name="transit_agent",
               prompt=current_prompt,
               response=response_content,
               messages=corrected.all_messages,
           )
           # Pre-populate validation result so the post-loop block below
           # doesn't re-run validation. We'll skip the redundant call.
           _correction_warnings = corrected.warnings
       else:
           result = await agent.run(
               current_prompt,
               deps=self._deps,
               message_history=message_history,
               instructions=instructions,
               model=tier_model,
           )
           response_content = result.output
           persist_agent_episode(
               agent_name="transit_agent",
               prompt=current_prompt,
               response=response_content,
               messages=result.all_messages(),
           )
           _correction_warnings = None  # Fall through to fresh validate
   ```

4. Update the post-loop validation block (lines 240–249) to skip re-validation when the correction loop already validated. Replace with:
   ```python
   # Reuse correction loop's validation when available; otherwise validate now.
   if tier == "complex" or _correction_warnings is None:
       validation = validate_transit_response(response_content)
       warnings_to_render = list(validation.warnings)
   else:
       warnings_to_render = _correction_warnings

   if warnings_to_render:
       for warning in warnings_to_render:
           logger.warning("agent.response_validation_warning", warning=warning)
       footnotes = "\n".join(f"\u26a0\ufe0f {w}" for w in warnings_to_render)
       response_content = f"{response_content}\n\n---\n{footnotes}"
   ```

5. **Initialize `_correction_warnings = None` at the top of the `try` block** so the complex-tier path doesn't hit `NameError` when it skips the standard-tier branch. Place `_correction_warnings: list[str] | None = None` right before `if tier == "complex":` at line 195.

**Anti-pattern checks:**
- #11 Schema field additions — `CorrectedResult` is new; nothing else consumes it.
- #29 Optional fields on existing schemas — none.
- #59 Removed/renamed response fields — none.
- The `tier_model` arg-type warning at `pipeline.py:136` is pre-existing; do not "fix" it.

**Validation:**
```bash
uv run ruff format app/core/agents/service.py app/core/agents/correction.py app/core/config.py
uv run ruff check app/core/agents/service.py app/core/agents/correction.py app/core/config.py
uv run pyright app/core/agents/service.py app/core/agents/correction.py app/core/config.py
uv run mypy app/core/agents/service.py app/core/agents/correction.py app/core/config.py
```

### Step 4 — Tests

`app/core/agents/tests/test_correction.py`:

```python
"""Unit tests for the AI-5.1 self-correction loop."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.agents.correction import (
    CorrectedResult,
    SelfCorrectionLoop,
    _retryable_warnings,
)
from app.core.agents.validation import ValidationResult


def _fake_run_result(output: str) -> MagicMock:
    """Build a MagicMock matching pydantic_ai.RunResult shape."""
    mock = MagicMock()
    mock.output = output
    mock.all_messages = lambda: []
    return mock


def _fake_agent(*outputs: str) -> MagicMock:
    """Build a MagicMock agent whose `run` returns the given outputs in order."""
    agent_mock = MagicMock()
    agent_mock.run = AsyncMock(
        side_effect=[_fake_run_result(o) for o in outputs]
    )
    return agent_mock


@pytest.mark.asyncio
async def test_clean_first_attempt_no_retry() -> None:
    """A response with zero warnings should not trigger a retry."""
    loop = SelfCorrectionLoop(max_rounds=1)
    fake_agent = _fake_agent("Take route 5 from Brīvības iela.")

    result = await loop.run_with_correction(
        fake_agent,
        "Where is bus 5?",
        deps=MagicMock(),
        message_history=None,
        instructions=None,
        model=None,
    )

    assert result.rounds_used == 1
    assert result.corrected is False
    assert result.warnings == []
    assert fake_agent.run.await_count == 1


@pytest.mark.asyncio
async def test_invalid_route_triggers_one_retry_and_succeeds() -> None:
    """First answer mentions implausible route 9999; retry produces a clean answer."""
    loop = SelfCorrectionLoop(max_rounds=1)
    fake_agent = _fake_agent(
        "Take route 9999 from the central station.",
        "Take route 5 from the central station.",
    )

    result = await loop.run_with_correction(
        fake_agent,
        "Best route to airport?",
        deps=MagicMock(),
        message_history=None,
        instructions=None,
        model=None,
    )

    assert result.rounds_used == 2
    assert result.corrected is True
    assert result.warnings == []
    assert "9999" not in result.output
    assert fake_agent.run.await_count == 2


@pytest.mark.asyncio
async def test_retry_exhausted_returns_final_with_warnings() -> None:
    """Both attempts fail validation; loop returns last response + warnings."""
    loop = SelfCorrectionLoop(max_rounds=1)
    fake_agent = _fake_agent(
        "Take route 9999.",
        "Take route 8888.",
    )

    result = await loop.run_with_correction(
        fake_agent,
        "Best route?",
        deps=MagicMock(),
        message_history=None,
        instructions=None,
        model=None,
    )

    assert result.rounds_used == 2
    assert result.corrected is False
    assert any("8888" in w for w in result.warnings)
    assert fake_agent.run.await_count == 2


@pytest.mark.asyncio
async def test_disabled_loop_zero_rounds_runs_once() -> None:
    """max_rounds=0 means one attempt and no retry, regardless of validation."""
    loop = SelfCorrectionLoop(max_rounds=0)
    fake_agent = _fake_agent("Take route 9999.")

    result = await loop.run_with_correction(
        fake_agent,
        "Test",
        deps=MagicMock(),
        message_history=None,
        instructions=None,
        model=None,
    )

    assert result.rounds_used == 1
    assert result.corrected is False
    assert fake_agent.run.await_count == 1


@pytest.mark.asyncio
async def test_max_rounds_clamped_to_three() -> None:
    """Constructor clamps max_rounds to 3 to bound token cost."""
    loop = SelfCorrectionLoop(max_rounds=99)
    # Implementation detail: read private attr (test only).
    assert loop._max_rounds == 3  # noqa: SLF001


@pytest.mark.asyncio
async def test_negative_max_rounds_clamped_to_zero() -> None:
    loop = SelfCorrectionLoop(max_rounds=-5)
    assert loop._max_rounds == 0  # noqa: SLF001


@pytest.mark.asyncio
async def test_correction_prompt_includes_failed_response_and_warnings() -> None:
    """The retry prompt must contain the failed response and the warning text."""
    loop = SelfCorrectionLoop(max_rounds=1)
    fake_agent = _fake_agent(
        "Take route 9999 from Centrs.",
        "Take route 5 from Centrs.",
    )

    await loop.run_with_correction(
        fake_agent,
        "Best route?",
        deps=MagicMock(),
        message_history=None,
        instructions=None,
        model=None,
    )

    # Second call's prompt should mention the failed route + a warning.
    second_call_prompt = fake_agent.run.await_args_list[1].args[0]
    assert "9999" in second_call_prompt
    assert "implausible" in second_call_prompt.lower()


@pytest.mark.asyncio
async def test_message_history_preserved_across_retry() -> None:
    """Original message_history is included on the retry call's history."""
    loop = SelfCorrectionLoop(max_rounds=1)
    fake_agent = _fake_agent("Take route 9999.", "Take route 5.")
    sentinel_history: list[Any] = [MagicMock(name="prior_message")]

    await loop.run_with_correction(
        fake_agent,
        "Where?",
        deps=MagicMock(),
        message_history=sentinel_history,
        instructions=None,
        model=None,
    )

    second_call_history = fake_agent.run.await_args_list[1].kwargs["message_history"]
    assert sentinel_history[0] in second_call_history


@pytest.mark.asyncio
async def test_stale_data_warning_does_not_trigger_retry() -> None:
    """Non-retryable warnings (stale cache) should not consume a retry round."""
    loop = SelfCorrectionLoop(max_rounds=1)
    fake_agent = _fake_agent("All buses on time.")

    with patch(
        "app.core.agents.correction.validate_transit_response",
        return_value=ValidationResult(
            is_valid=False,
            warnings=["This response may be based on cached data. Live feed was temporarily unavailable."],
            sanitized_response="All buses on time.",
        ),
    ):
        result = await loop.run_with_correction(
            fake_agent,
            "Status?",
            deps=MagicMock(),
            message_history=None,
            instructions=None,
            model=None,
        )

    assert result.rounds_used == 1
    assert result.corrected is False
    assert len(result.warnings) == 1
    assert fake_agent.run.await_count == 1


@pytest.mark.asyncio
async def test_validator_exception_returns_unvalidated_response() -> None:
    """If the validator itself crashes, return the original response cleanly."""
    loop = SelfCorrectionLoop(max_rounds=1)
    fake_agent = _fake_agent("Take route 5.")

    with patch(
        "app.core.agents.correction.validate_transit_response",
        side_effect=RuntimeError("validator boom"),
    ):
        result = await loop.run_with_correction(
            fake_agent,
            "Test",
            deps=MagicMock(),
            message_history=None,
            instructions=None,
            model=None,
        )

    assert result.output == "Take route 5."
    assert result.warnings == []
    assert result.rounds_used == 1


@pytest.mark.asyncio
async def test_logs_correction_triggered_and_resolved() -> None:
    """Verify structured log events fire on retry + success."""
    loop = SelfCorrectionLoop(max_rounds=1)
    fake_agent = _fake_agent("Take route 9999.", "Take route 5.")

    with patch("app.core.agents.correction.logger") as mock_logger:
        await loop.run_with_correction(
            fake_agent,
            "Where?",
            deps=MagicMock(),
            message_history=None,
            instructions=None,
            model=None,
        )

    event_names = [call.args[0] for call in mock_logger.info.call_args_list]
    assert "agent.correction.triggered" in event_names
    assert "agent.correction.resolved" in event_names


@pytest.mark.asyncio
async def test_logs_correction_exhausted_when_retry_fails() -> None:
    loop = SelfCorrectionLoop(max_rounds=1)
    fake_agent = _fake_agent("Take route 9999.", "Take route 8888.")

    with patch("app.core.agents.correction.logger") as mock_logger:
        await loop.run_with_correction(
            fake_agent,
            "Where?",
            deps=MagicMock(),
            message_history=None,
            instructions=None,
            model=None,
        )

    warning_event_names = [call.args[0] for call in mock_logger.warning.call_args_list]
    assert "agent.correction.exhausted" in warning_event_names


def test_retryable_warnings_filters_stale_data() -> None:
    warnings = [
        "Route number 9999 seems implausible (expected 1-999).",
        "This response may be based on cached data. Live feed was temporarily unavailable.",
    ]
    filtered = _retryable_warnings(warnings)
    assert len(filtered) == 1
    assert "9999" in filtered[0]


def test_retryable_warnings_empty_when_only_non_retryable() -> None:
    warnings = ["This response may be based on cached data. Live feed was temporarily unavailable."]
    assert _retryable_warnings(warnings) == []


def test_corrected_result_dataclass_defaults() -> None:
    r = CorrectedResult(output="hi")
    assert r.output == "hi"
    assert r.warnings == []
    assert r.rounds_used == 1
    assert r.corrected is False
    assert r.all_messages == []
```

That's 14 tests (plan target was 10+).

**Anti-pattern checks specific to tests:**
- #7 All test functions return `-> None` (and helper `_fake_run_result` / `_fake_agent` have `-> MagicMock`).
- #14 No `# type: ignore` in test files.
- #22 `sentinel_history` annotated as `list[Any]`.
- #28 No bare `[]` literals (the `list[Any] = [MagicMock(...)]` is annotated).
- `# noqa: SLF001` justified — testing constructor clamping requires reading private attr.

**Validation:**
```bash
uv run ruff format app/core/agents/tests/test_correction.py
uv run ruff check app/core/agents/tests/test_correction.py
uv run pyright app/core/agents/tests/test_correction.py
uv run mypy app/core/agents/tests/test_correction.py
uv run pytest app/core/agents/tests/test_correction.py -v
```

### Step 5 — Update `.env.example`

Append after the memory block:

```
# Self-correction loop (AI-5.1)
AGENT_SELF_CORRECTION_ENABLED=true
AGENT_MAX_CORRECTION_ROUNDS=1
```

**Validation:** `cat .env.example | grep AGENT_` (no formatter needed).

### Step 6 — Full validation suite

```bash
make lint
make types
uv run pytest app/core/agents/tests/test_correction.py app/core/agents/tests/test_service.py -v
make test  # all 1128+ unit tests
```

## Preflight Warnings

- **`pipeline.py:136`** — pre-existing pyright/mypy `model` arg-type error. Do NOT touch; AI-5.1 is scoped to standard tier only.
- **`validation.py:76`** — pre-existing pyright `list[Unknown]`. Do NOT touch.
- **`tools/transit/static_store.py:149-150`** — pre-existing mypy issues. Do NOT touch.
- **Module-global state in `validation.py`** — `last_stale_data_timestamp` persists across calls and across tests. Tests for the correction loop should NOT touch this global; instead `patch("app.core.agents.correction.validate_transit_response", ...)` to inject deterministic `ValidationResult` values.
- **`agent.run()` is patched at the import site (`app.core.agents.correction.agent.run`?)** — NO. Tests use a `MagicMock` agent passed as the `agent_instance` parameter. We do not import the global `agent` singleton inside `correction.py` at runtime — the loop is dependency-injected. This avoids the lazy-import / patch-target trap (anti-pattern #36).
- **Singleton service caches the loop** — `AgentService.__init__` reads settings ONCE. If tests need to toggle `agent_self_correction_enabled`, they must construct a fresh `AgentService()` after patching `get_settings`. The existing `_create_service()` helper in `test_service.py` already does this pattern.
- **`current_prompt` shadowing on retry** — On retry the loop sends the corrective text AS the prompt, with the original prompt + failed answer encoded in `message_history`. This avoids the empty-prompt error from Pydantic AI.

## Security Checklist

For this feature (no new HTTP endpoints):
- [x] No new endpoint → no `get_current_user` / `require_role` / rate limit needed
- [x] Input validation: corrective prompt is server-constructed from already-validated server state
- [x] Error responses: validator exceptions handled internally; `agent.run()` exceptions propagate to existing `AgentExecutionError` mapping
- [x] No `escape_like()` needed (no DB queries)
- [x] Output sanitization: corrected output flows through the same validator + footnote rendering as before
- [x] Bounded retry (`max_rounds` clamped to ≤3) prevents prompt-injection-driven token amplification
- [x] No credential exposure: corrective prompt embeds only the failed agent output + validator warnings (both already at INFO/WARN log level)

## Verification

- [ ] `make lint` passes
- [ ] `make types` passes — pyright errors ≤ 6, mypy errors ≤ 3 (baseline preserved)
- [ ] `uv run pytest app/core/agents/tests/test_correction.py -v` — 14 tests pass
- [ ] `uv run pytest app/core/agents/tests/test_service.py -v` — existing service tests still pass (none should regress; the standard-tier path now goes through `SelfCorrectionLoop` but `TestModel` returns clean output → no retry, identical observable behavior)
- [ ] `make test` — full unit suite passes
- [ ] `make security-audit-quick` passes
- [ ] Manual smoke check after `make dev`: POST to `/v1/chat/completions` with a normal prompt — observe `agent.chat_completed` event, no `agent.correction.*` events. Then craft a prompt that elicits a route number > 999 (e.g., "what's route 9999?") and observe `agent.correction.triggered` then either `.resolved` or `.exhausted` in logs.
- [ ] Pyright errors in `app/core/agents/correction.py` = 0
- [ ] Pyright errors in `app/core/agents/tests/test_correction.py` = 0
