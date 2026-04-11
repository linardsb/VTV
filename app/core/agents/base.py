"""Reusable agent harness — extracts AgentService.chat() into hook points.

Subclasses override hook methods; the base owns the pipeline order so future
domain agents (AI-6.2+) reuse the same flow with different tools / prompts /
QA validators. The transit-specific concrete implementation lives in
``app.core.agents.service.AgentService``.

The base handles:
    - Prompt extraction + history splitting
    - Prompt injection detection (log-only)
    - Tier classification
    - Hook orchestration (RAG routing, skills, memory, instructions)
    - Uniform ``AgentExecutionError`` wrapping
    - Post-processing (validation footnotes)
    - OpenAI-compatible response assembly
    - ``agent.chat_started`` / ``agent.chat_completed`` logging

Hook points (override in subclasses):
    ``_get_model_tier``, ``_apply_rag_routing``, ``detect_relevant_skills``,
    ``_recall_memories_block``, ``build_system_prompt``, ``_build_user_message``,
    ``_preload_validation_cache``, ``_execute`` (must override),
    ``_post_process`` / ``_run_qa`` / ``_should_run_qa``, ``_build_response``,
    ``_persist_episode``.
"""

from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)

from app.core.agents.agent import build_instructions_with_skills
from app.core.agents.agent_result import VALID_DOMAINS, AgentResult
from app.core.agents.config import resolve_tier_model
from app.core.agents.exceptions import AgentExecutionError
from app.core.agents.routing import ModelTier, classify_prompt
from app.core.agents.schemas import (
    ChatCompletionChoice,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    UsageInfo,
)
from app.core.agents.validation import (
    ToolReturnRecord,
    ValidationContext,
    extract_tool_returns,
    validate_transit_response,
)
from app.core.config import get_settings
from app.core.logging import get_logger
from app.memory.bridge import persist_agent_episode

if TYPE_CHECKING:
    from pydantic_ai.models import Model

logger = get_logger(__name__)


# --- Prompt injection helpers (module-level to ease unit testing) -----------

_INJECTION_PATTERNS = (
    re.compile(r"ignore\s+(previous|all|above)\s+(instructions|prompts)", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(?:a|an)\s+", re.IGNORECASE),
    re.compile(r"<\s*system\s*>", re.IGNORECASE),
)


def _check_prompt_injection(text: str) -> None:
    """Log a warning if common prompt injection patterns are detected.

    Does not block the message — only logs for operator awareness. Blocking
    legitimate messages is a worse outcome than logging false positives.
    """
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            logger.warning(
                "agent.prompt_injection_detected",
                pattern=pattern.pattern,
                prompt_length=len(text),
            )
            return


def _build_message_history(messages: list[ChatMessage]) -> list[ModelMessage]:
    """Convert OpenAI-format chat messages to Pydantic AI ``ModelMessage``.

    Args:
        messages: Prior messages to include as history (user + assistant).

    Returns:
        List of ``ModelMessage`` objects consumed by ``agent.run``.
    """
    history: list[ModelMessage] = []
    for msg in messages:
        if msg.role == "user":
            history.append(ModelRequest(parts=[UserPromptPart(content=msg.content)]))
        elif msg.role == "assistant":
            history.append(ModelResponse(parts=[TextPart(content=msg.content)]))
        # system messages are handled by the agent's system_prompt config
    return history


# --- Pipeline outcome carrier -----------------------------------------------


@dataclass(slots=True)
class _PipelineOutcome:
    """Return value of ``BaseAgentService._execute``.

    Attributes:
        response_text: The agent's final response text for the user.
        warnings: Validation warnings to render as footnotes, or ``None`` to
            tell ``_post_process`` to run QA itself (e.g. fallback path where
            the self-correction loop did not execute).
        messages: Full ``all_messages()`` slice from the final agent attempt,
            used by ``_run_qa`` to extract tool-return grounding.
        confidence: Optional per-domain confidence in ``[0.0, 1.0]``. When
            ``None`` the AI-6.5 re-route gate in ``chat()`` is skipped.
        tools_used: Tool names invoked during the execute call, for
            observability and forming ``AgentResult.tools_used``.
    """

    response_text: str
    warnings: list[str] | None
    messages: list[ModelMessage] = field(default_factory=lambda: list[ModelMessage]())
    confidence: float | None = None
    tools_used: tuple[str, ...] = ()


# --- Base service -----------------------------------------------------------


class BaseAgentService:
    """Abstract agent harness with hook points + a pipeline orchestrator.

    Subclasses override hooks; the base owns the pipeline order and ensures
    cross-cutting concerns (prompt injection check, logging, exception
    wrapping, validation footnotes, response assembly) happen exactly once
    per ``chat()`` call.

    Concrete subclasses MUST override ``_execute`` (no sensible default for
    agent invocation). Everything else has a safe no-op or best-effort
    default.
    """

    agent_name: str = "base_agent"

    async def chat(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        """Run the full chat pipeline for one request.

        Returns only the OpenAI-compatible envelope. For pipeline metadata
        (confidence, tools_used, warnings, tool return records) call
        :meth:`chat_with_trace`.

        Args:
            request: Parsed ``ChatCompletionRequest`` from the HTTP layer.

        Returns:
            An OpenAI-compatible ``ChatCompletionResponse``.

        Raises:
            AgentExecutionError: If ``_execute`` raises anything. The original
                exception is preserved as ``__cause__``.
        """
        response, _result, _tool_returns = await self.chat_with_trace(request)
        return response

    async def chat_with_trace(
        self,
        request: ChatCompletionRequest,
    ) -> tuple[ChatCompletionResponse, AgentResult, tuple[ToolReturnRecord, ...]]:
        """Run the full chat pipeline and return envelope + trace metadata.

        Identical semantics to :meth:`chat` — this is the implementation that
        ``chat`` delegates to. Returning the internal ``AgentResult`` and the
        parsed tool return records exposes ``confidence``, ``warnings``,
        ``tools_used``, and per-tool payloads to observability consumers
        (AI-7.2 eval runner, future audit tooling).

        Args:
            request: Parsed ``ChatCompletionRequest`` from the HTTP layer or
                a script.

        Returns:
            ``(response, result, tool_returns)`` — the OpenAI-compatible
            envelope, the frozen ``AgentResult`` built after any confidence
            re-route, and the tuple of ``ToolReturnRecord`` extracted from
            the final pipeline outcome's message history.

        Raises:
            AgentExecutionError: If ``_execute`` raises anything. The original
                exception is preserved as ``__cause__``.
        """
        # Phase 1: extract current prompt + prior history.
        current_prompt = request.messages[-1].content
        prior_messages = request.messages[:-1]
        message_history = _build_message_history(prior_messages) if prior_messages else None

        # Phase 2: prompt injection check (log-only, does not block).
        _check_prompt_injection(current_prompt)

        # Phase 3: tier classification.
        tier, tier_model = self._get_model_tier(current_prompt)

        logger.info(
            "agent.chat_started",
            message_count=len(request.messages),
            history_count=len(prior_messages),
            user_prompt_length=len(current_prompt),
            model_tier=tier,
            tier_override=tier_model is not None,
        )

        # Phase 4: RAG routing decision (toggles self.deps.rag_enabled).
        await self._apply_rag_routing(current_prompt, tier)

        # Phase 5: skill detection + load (fail-open).
        skills_instructions = await self.detect_relevant_skills(current_prompt)

        # Phase 6: memory recall block (fail-open).
        memory_context = await self._recall_memories_block(current_prompt)

        # Phase 7: compose system instructions.
        instructions = self.build_system_prompt(skills_instructions, memory_context) or None

        # Phase 8: optional validation cache preload (fail-open).
        static_cache = await self._preload_validation_cache()

        # Phase 9: build user message turn.
        user_message = self._build_user_message(request, current_prompt)

        # Phase 10: execute → one of {complex pipeline, correction loop, fallback}.
        try:
            outcome = await self._execute(
                user_message=user_message,
                current_prompt=current_prompt,
                message_history=message_history,
                instructions=instructions,
                tier=tier,
                tier_model=tier_model,
                static_cache=static_cache,
            )
        except Exception as e:
            logger.error(
                "agent.chat_failed",
                exc_info=True,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise AgentExecutionError(f"Agent execution failed: {e}") from e

        # Phase 11: post-process → append validation warning footnotes.
        final_text = self._post_process(
            response=outcome.response_text,
            current_prompt=current_prompt,
            warnings=outcome.warnings,
            messages=outcome.messages,
            static_cache=static_cache,
        )

        # Phase 11b: build AgentResult wrapper (AI-6.5 — metadata only).
        result_domain = self.agent_name if self.agent_name in VALID_DOMAINS else "unified"
        result = AgentResult(
            content=final_text,
            confidence=outcome.confidence,
            warnings=tuple(outcome.warnings or ()),
            tools_used=outcome.tools_used,
            domain=result_domain,
        )
        final_outcome = outcome

        # Phase 11c: AI-6.5 confidence re-route gate (single retry, hard cap).
        settings = get_settings()
        reroute_enabled = bool(getattr(settings, "agent_confidence_reroute_enabled", False))
        reroute_threshold = float(
            getattr(settings, "agent_confidence_reroute_threshold", 0.3),
        )
        if (
            reroute_enabled
            and result.confidence is not None
            and result.confidence < reroute_threshold
            and tier != "complex"
        ):
            complex_model = resolve_tier_model("complex")
            if complex_model is not None:
                logger.info(
                    "agent.chat.confidence_reroute",
                    domain=result.domain,
                    confidence=result.confidence,
                    threshold=reroute_threshold,
                    original_tier=tier,
                )
                try:
                    retry_outcome = await self._execute(
                        user_message=user_message,
                        current_prompt=current_prompt,
                        message_history=message_history,
                        instructions=instructions,
                        tier="complex",
                        tier_model=complex_model,
                        static_cache=static_cache,
                    )
                except Exception as e:
                    logger.error(
                        "agent.chat.confidence_reroute_failed",
                        exc_info=True,
                        error=str(e),
                        error_type=type(e).__name__,
                    )
                    raise AgentExecutionError(f"Agent execution failed: {e}") from e

                retry_final_text = self._post_process(
                    response=retry_outcome.response_text,
                    current_prompt=current_prompt,
                    warnings=retry_outcome.warnings,
                    messages=retry_outcome.messages,
                    static_cache=static_cache,
                )
                result = AgentResult(
                    content=retry_final_text,
                    confidence=retry_outcome.confidence,
                    warnings=tuple(retry_outcome.warnings or ()),
                    tools_used=retry_outcome.tools_used,
                    domain=result_domain,
                )
                final_outcome = retry_outcome
                tier_model = complex_model

        # Phase 12: build OpenAI-compatible response envelope.
        response = self._build_response(content=result.content, tier_model=tier_model)

        # Phase 12b: capture parsed tool returns from the final pipeline
        # outcome's message history. Consumed by AI-7.2 eval runner via
        # ``chat_with_trace``; ``chat`` discards this tuple.
        tool_returns = tuple(extract_tool_returns(final_outcome.messages))

        logger.info(
            "agent.chat_completed",
            response_id=response.id,
            output_length=len(result.content),
            confidence=result.confidence,
            tools_used=list(result.tools_used),
        )

        return response, result, tool_returns

    # ------------------------------------------------------------------
    # Hook 1 — tier classification
    # ------------------------------------------------------------------
    def _get_model_tier(self, prompt: str) -> tuple[ModelTier, str | Model | None]:
        """Classify a prompt into a model routing tier.

        Default: ``classify_prompt(prompt)`` + ``resolve_tier_model(tier)``.
        Subclasses may override to plug in a learned classifier.
        """
        tier = classify_prompt(prompt)
        return tier, resolve_tier_model(tier)

    # ------------------------------------------------------------------
    # Hook 2 — RAG routing
    # ------------------------------------------------------------------
    async def _apply_rag_routing(self, prompt: str, tier: ModelTier) -> None:
        """Decide whether to enable RAG for this request.

        Default: no-op. Subclasses override to wire a domain-specific RAG
        router and toggle ``self._deps.rag_enabled``.
        """
        _ = prompt, tier  # hook signature preserved for subclass overrides
        return None

    # ------------------------------------------------------------------
    # Hook 3 — skill detection
    # ------------------------------------------------------------------
    async def detect_relevant_skills(self, prompt: str) -> str:
        """Return active-skills text to inject into the system prompt.

        Default: empty string. Domain subclasses (AI-6.4) typically delegate
        to ``app.core.agents.skill_loader.load_skills_within_budget`` —
        gated by the ``agent_progressive_skills_enabled`` setting — and
        must fail-open on error (return '').
        """
        _ = prompt  # hook signature preserved for subclass overrides
        return ""

    # ------------------------------------------------------------------
    # Hook 4 — memory recall
    # ------------------------------------------------------------------
    async def _recall_memories_block(self, prompt: str) -> str:
        """Return a formatted memory-context block for system instructions.

        Default: empty string. Subclasses override to run semantic recall
        and format a ``RELEVANT MEMORIES`` block. Must fail-open on error.
        """
        _ = prompt  # hook signature preserved for subclass overrides
        return ""

    # ------------------------------------------------------------------
    # Hook 5 — system prompt assembly
    # ------------------------------------------------------------------
    def build_system_prompt(self, skills: str, memory_context: str) -> str:
        """Compose skills + memory into the final instructions string.

        Default: delegate to ``build_instructions_with_skills``. Subclasses
        override to inject domain-specific preamble or reorder sections.
        """
        return build_instructions_with_skills(skills, memory_context)

    # ------------------------------------------------------------------
    # Hook 6 — user message shaping
    # ------------------------------------------------------------------
    def _build_user_message(
        self,
        request: ChatCompletionRequest,
        current_prompt: str,
    ) -> str:
        """Shape the user turn that will be sent to ``agent.run``.

        Default: return the current prompt unchanged. Subclasses override to
        inject structured context (e.g. attach a fetched document preview).
        """
        _ = request  # hook signature preserved for subclass overrides
        return current_prompt

    # ------------------------------------------------------------------
    # Hook 7 — validation cache preload
    # ------------------------------------------------------------------
    async def _preload_validation_cache(self) -> Any:  # noqa: ANN401 — GTFSStaticStore | domain-specific | None
        """Pre-load whatever cache ``_run_qa`` needs.

        Default: return ``None``. Subclasses override to populate a domain
        cache (e.g. GTFS static data) that will flow into ``_run_qa`` via
        ``ValidationContext``. Must fail-open.
        """
        return None

    # ------------------------------------------------------------------
    # Hook 8 — agent execution (MUST override)
    # ------------------------------------------------------------------
    async def _execute(
        self,
        *,
        user_message: str,
        current_prompt: str,
        message_history: list[ModelMessage] | None,
        instructions: str | None,
        tier: ModelTier,
        tier_model: str | Model | None,
        static_cache: Any,  # noqa: ANN401 — forwarded verbatim to _run_qa / correction loop
    ) -> _PipelineOutcome:
        """Invoke the agent and return a ``_PipelineOutcome``.

        Subclasses MUST override. This is the only hook without a sensible
        default — agent invocation is inherently domain-specific (which
        agent? which tools? which retry strategy?).
        """
        raise NotImplementedError(
            "BaseAgentService._execute must be overridden by concrete subclasses",
        )

    # ------------------------------------------------------------------
    # Hook 9 — post-processing (validation footnotes)
    # ------------------------------------------------------------------
    def _post_process(
        self,
        *,
        response: str,
        current_prompt: str,
        warnings: list[str] | None,
        messages: list[ModelMessage],
        static_cache: Any,  # noqa: ANN401
    ) -> str:
        """Append validation warnings as ``⚠️`` footnotes under ``---``.

        ``warnings is None`` means no QA has run yet; fall back to ``_run_qa``.
        Non-None (including empty list) means ``_execute`` already ran QA —
        skip re-validation.
        """
        if warnings is None:
            warnings_to_render = self._run_qa(
                response=response,
                current_prompt=current_prompt,
                messages=messages,
                static_cache=static_cache,
            )
        else:
            warnings_to_render = list(warnings)

        if warnings_to_render:
            for warning in warnings_to_render:
                logger.warning(
                    "agent.response_validation_warning",
                    warning=warning,
                )
            footnotes = "\n".join(f"\u26a0\ufe0f {w}" for w in warnings_to_render)
            return f"{response}\n\n---\n{footnotes}"
        return response

    def _run_qa(
        self,
        *,
        response: str,
        current_prompt: str,
        messages: list[ModelMessage],
        static_cache: Any,  # noqa: ANN401
    ) -> list[str]:
        """Run the domain QA validator and return a list of warning strings.

        Default: delegate to ``validate_transit_response`` with a
        ``ValidationContext`` built from the current prompt, static cache,
        and tool returns. Subclasses override for non-transit QA.
        """
        ctx = ValidationContext(
            user_message=current_prompt,
            static_cache=static_cache,
            tool_returns=extract_tool_returns(messages),
        )
        result = validate_transit_response(response, ctx)
        return list(result.warnings)

    def _should_run_qa(self, tier: ModelTier) -> bool:
        """Return True iff QA / self-correction should run for this tier.

        Default: run QA when self-correction is enabled and tier is not
        complex (complex tier has its own pipeline-layer retry).
        """
        settings = get_settings()
        return bool(getattr(settings, "agent_self_correction_enabled", False)) and tier != "complex"

    # ------------------------------------------------------------------
    # Response assembly
    # ------------------------------------------------------------------
    def _build_response(
        self,
        *,
        content: str,
        tier_model: str | Model | None,
    ) -> ChatCompletionResponse:
        """Assemble the OpenAI-compatible response envelope.

        Uses the tier-resolved model name when present, else falls back to
        the application-default ``llm_provider:llm_model``.
        """
        settings = get_settings()
        response_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
        model_name = (
            str(tier_model)
            if tier_model is not None
            else f"{settings.llm_provider}:{settings.llm_model}"
        )
        return ChatCompletionResponse(
            id=response_id,
            created=int(time.time()),
            model=model_name,
            choices=[
                ChatCompletionChoice(
                    index=0,
                    message=ChatMessage(role="assistant", content=content),
                    finish_reason="stop",
                )
            ],
            usage=UsageInfo(),
        )

    # ------------------------------------------------------------------
    # Memory persistence helper
    # ------------------------------------------------------------------
    async def _persist_episode(
        self,
        *,
        prompt: str,
        response: str,
        messages: list[ModelMessage],
    ) -> None:
        """Fire-and-forget memory persistence via ``persist_agent_episode``.

        Helper for subclasses — the pipeline does not call this itself
        because persist policy varies per execution branch (e.g. complex
        tier does not persist today). Subclasses invoke this from within
        ``_execute`` at the appropriate point.
        """
        persist_agent_episode(
            agent_name=self.agent_name,
            prompt=prompt,
            response=response,
            messages=messages,
        )


__all__ = [
    "BaseAgentService",
    "_PipelineOutcome",
    "_build_message_history",
    "_check_prompt_injection",
]
