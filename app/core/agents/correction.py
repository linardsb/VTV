"""Bounded self-correction loop for agent responses (AI-5.1).

Wraps `agent.run()` with one deterministic QA check + at most one retry.
If validation fails on first attempt, the loop re-invokes the agent with
the failed response and warnings injected as a corrective user turn.
If the retry also fails, returns the (still-failed) response with the
warnings preserved for footnote rendering -- same fallback as before.

The loop ONLY targets the standard tier. Complex-tier pipeline runs are
handled by `pipeline.py` and will get their own correction in AI-5.2.
"""

from __future__ import annotations

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
    from pydantic_ai.models import Model

    from app.core.agents.tools.transit.deps import UnifiedDeps

logger = get_logger(__name__)

# Validator warnings whose root cause the agent CANNOT fix by retrying.
# Stale-data warnings come from the cache circuit-breaker, not the LLM
# response -- retrying just burns tokens. These still get appended as
# footnotes; they just don't trigger a retry.
_NON_RETRYABLE_PREFIXES: tuple[str, ...] = ("This response may be based on cached data",)


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
        all_messages: `result.all_messages()` from the *final* attempt --
            used by `persist_agent_episode()` for memory persistence.
        corrected: True iff a retry happened AND it produced a clean
            response.
    """

    output: str
    warnings: list[str] = field(default_factory=lambda: list[str]())
    rounds_used: int = 1
    all_messages: list[ModelMessage] = field(default_factory=lambda: list[ModelMessage]())
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


class SelfCorrectionLoop:
    """Runs `agent.run()` with one deterministic QA + bounded retry.

    Usage:
        loop = SelfCorrectionLoop(max_rounds=1)
        result = await loop.run_with_correction(
            agent_instance, prompt, deps=..., message_history=...,
            instructions=..., model=...,
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
                `max_rounds=1` then up to 2 `agent.run()` calls. Capped
                at 3 for safety. Negative values are clamped to 0.
        """
        if max_rounds < 0:
            max_rounds = 0
        if max_rounds > 3:
            max_rounds = 3
        self._max_rounds = max_rounds

    async def run_with_correction(
        self,
        agent_instance: Agent[UnifiedDeps, str],
        prompt: str,
        *,
        deps: UnifiedDeps,
        message_history: list[ModelMessage] | None,
        instructions: str | None,
        model: str | Model | None,
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
            Whatever `agent.run()` raises -- caller wraps in
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

            # Build a fresh history for the retry: original prior turns +
            # the user's original prompt + the failed assistant turn.
            # The retry's `current_prompt` becomes the corrective text.
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

        Args:
            response: The agent's text output to validate.

        Returns:
            A `ValidationResult`. On validator exception, returns a
            clean (no-warnings) result so the loop terminates.
        """
        try:
            return validate_transit_response(response)
        except Exception:
            logger.error("agent.correction.failed", exc_info=True)
            return ValidationResult(is_valid=True, warnings=[], sanitized_response=response)

    @staticmethod
    def _build_correction_prompt_text(failed_response: str, warnings: list[str]) -> str:
        """Construct the corrective prompt text for the retry attempt.

        Args:
            failed_response: The agent's failed first-attempt output.
            warnings: Retryable validation warnings to surface.

        Returns:
            A prompt string instructing the agent to re-answer the
            original question, citing the specific issues to fix.
        """
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
