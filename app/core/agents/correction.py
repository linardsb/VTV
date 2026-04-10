"""Bounded self-correction loop for agent responses (AI-5.1, extended in AI-5.2).

Wraps `agent.run()` with one deterministic QA check + at most one retry.
If validation fails on first attempt, the loop re-invokes the agent with
the failed response and warnings injected as a corrective user turn.
If the retry also fails, returns the (still-failed) response with the
warnings preserved for footnote rendering -- same fallback as before.

The loop ONLY targets the standard tier. Complex-tier pipeline runs are
handled by `pipeline.py` and will get their own correction in AI-5.3.

AI-5.2 changes:
- Validation now produces severity-tagged ``Issue`` objects.
- Retry filtering is severity-based (`error` retries, `warning` doesn't)
  rather than prefix-based.
- A ``ValidationContext`` carrying the original user message, the GTFS
  static cache, and parsed tool returns is built before each validation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)

from app.core.agents.validation import (
    Issue,
    ValidationContext,
    ValidationResult,
    extract_tool_returns,
    validate_transit_response,
)
from app.core.logging import get_logger

if TYPE_CHECKING:
    from pydantic_ai import Agent
    from pydantic_ai.models import Model

    from app.core.agents.tools.transit.deps import UnifiedDeps

logger = get_logger(__name__)


@dataclass
class CorrectedResult:
    """Outcome of a self-correction loop run.

    Attributes:
        output: Final response text (corrected or original).
        warnings: Validation issue descriptions remaining after the loop.
            Empty if the loop produced a clean response. Otherwise the
            same list the caller would render as footnotes.
        issues: Full ``Issue`` objects backing ``warnings``. Carried for
            downstream metrics in AI-5.3 — ``warnings`` stays as the
            simple-string view consumed by ``service.py``.
        rounds_used: Total number of `agent.run()` invocations (1 = no
            retry, 2 = one retry).
        all_messages: `result.all_messages()` from the *final* attempt --
            used by `persist_agent_episode()` for memory persistence.
        corrected: True iff a retry happened AND it produced a clean
            response.
    """

    output: str
    warnings: list[str] = field(default_factory=lambda: list[str]())
    issues: list[Issue] = field(default_factory=lambda: list[Issue]())
    rounds_used: int = 1
    all_messages: list[ModelMessage] = field(default_factory=lambda: list[ModelMessage]())
    corrected: bool = False


def _retryable_issues(issues: list[Issue]) -> list[Issue]:
    """Return only error-severity issues. Warnings are footnote-only.

    Args:
        issues: All issues from a ``ValidationResult``.

    Returns:
        Subset whose ``severity == "error"``. An empty list means the
        loop should stop.
    """
    return [i for i in issues if i.severity == "error"]


class SelfCorrectionLoop:
    """Runs `agent.run()` with one deterministic QA + bounded retry.

    Usage:
        loop = SelfCorrectionLoop(max_rounds=1)
        result = await loop.run_with_correction(
            agent_instance, prompt, deps=..., message_history=...,
            instructions=..., model=..., static_cache=...,
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
        static_cache: Any | None = None,  # noqa: ANN401 — GTFSStaticCache typed via TYPE_CHECKING in validation.py
    ) -> CorrectedResult:
        """Run the agent with up to one corrective retry.

        Args:
            agent_instance: The Pydantic AI agent singleton.
            prompt: The user's current prompt (last message content).
            deps: Unified deps for transit + vault tools.
            message_history: Prior conversation history (or None).
            instructions: System instructions including skills + memory.
            model: Tier-resolved model override (or None).
            static_cache: Optional pre-loaded GTFS static cache used by
                existence checks. ``None`` makes existence checks no-op
                (fail-open).

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
        last_issues: list[Issue] = []
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

            ctx = ValidationContext(
                user_message=prompt,
                static_cache=static_cache,
                tool_returns=extract_tool_returns(last_messages),
            )
            validation = self._safe_validate(last_output, ctx)
            last_issues = list(validation.issues)
            last_warnings = list(validation.warnings)

            retryable = _retryable_issues(last_issues)
            if not retryable:
                # Either fully clean OR only warning-severity issues.
                if attempt > 0:
                    logger.info(
                        "agent.correction.resolved",
                        round=attempt,
                        residual_warnings=len(last_warnings),
                    )
                return CorrectedResult(
                    output=last_output,
                    warnings=last_warnings,
                    issues=last_issues,
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
                first_warning=retryable[0].description[:120],
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
            issues=last_issues,
            rounds_used=self._max_rounds + 1,
            all_messages=last_messages,
            corrected=False,
        )

    @staticmethod
    def _safe_validate(response: str, ctx: ValidationContext) -> ValidationResult:
        """Run the validator, swallowing exceptions as "no warnings".

        A crashing validator must NEVER prevent dispatchers from getting
        an answer. The original response is returned as-is.

        Args:
            response: The agent's text output to validate.
            ctx: ``ValidationContext`` forwarded to the validator.

        Returns:
            A `ValidationResult`. On validator exception, returns a
            clean (no-issues) result so the loop terminates.
        """
        try:
            return validate_transit_response(response, ctx)
        except Exception:
            logger.error("agent.correction.failed", exc_info=True)
            return ValidationResult(
                is_valid=True,
                issues=[],
                warnings=[],
                sanitized_response=response,
            )

    @staticmethod
    def _build_correction_prompt_text(
        failed_response: str,
        retryable_issues: list[Issue],
    ) -> str:
        """Construct the corrective prompt text for the retry attempt.

        Args:
            failed_response: The agent's failed first-attempt output.
            retryable_issues: Error-severity issues to surface to the
                agent.

        Returns:
            A prompt string instructing the agent to re-answer the
            original question, citing the specific issues to fix.
        """
        bullet_list = "\n".join(f"- {i.description}" for i in retryable_issues)
        return (
            "Your previous answer contained the following validation issues:\n"
            f"{bullet_list}\n\n"
            "Previous answer for reference:\n"
            f"---\n{failed_response}\n---\n\n"
            "Please re-answer the original question with these issues corrected. "
            "Use only real route numbers (1-999), plausible delay values "
            "(0-1440 minutes), correct Latvian diacritics, plausible times "
            "(00:00-23:59), and only cite documents that were returned by "
            "search_knowledge. Do not repeat the same mistakes."
        )


__all__ = ["CorrectedResult", "SelfCorrectionLoop"]
