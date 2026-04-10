"""Agent service layer for orchestrating chat interactions.

This module provides the AgentService class that handles the full
lifecycle of a chat request: extracting user messages, running the
agent, and constructing OpenAI-compatible responses.
"""

import re
import time
import uuid

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)

from app.core.agents.agent import agent, build_instructions_with_skills
from app.core.agents.config import resolve_tier_model
from app.core.agents.correction import CorrectedResult, SelfCorrectionLoop
from app.core.agents.exceptions import AgentExecutionError
from app.core.agents.pipeline import get_complex_pipeline
from app.core.agents.routing import classify_prompt
from app.core.agents.schemas import (
    ChatCompletionChoice,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    UsageInfo,
)
from app.core.agents.tools.transit.deps import UnifiedDeps, create_unified_deps
from app.core.agents.validation import validate_transit_response
from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.core.logging import get_logger
from app.knowledge.router import needs_rag
from app.memory.bridge import persist_agent_episode
from app.memory.schemas import MemoryRecallByQueryRequest
from app.memory.service import MemoryService
from app.skills.service import SkillService

logger = get_logger(__name__)


def _build_message_history(messages: list[ChatMessage]) -> list[ModelMessage]:
    """Convert OpenAI-format chat messages to Pydantic AI ModelMessage objects.

    Converts prior conversation messages (excluding the final user message)
    into the format expected by agent.run(message_history=...).

    Args:
        messages: Prior messages to include as history (user + assistant).

    Returns:
        List of ModelMessage objects for Pydantic AI.
    """
    history: list[ModelMessage] = []
    for msg in messages:
        if msg.role == "user":
            history.append(ModelRequest(parts=[UserPromptPart(content=msg.content)]))
        elif msg.role == "assistant":
            history.append(ModelResponse(parts=[TextPart(content=msg.content)]))
        # system messages are handled by the agent's system_prompt config
    return history


_INJECTION_PATTERNS = (
    re.compile(r"ignore\s+(previous|all|above)\s+(instructions|prompts)", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(?:a|an)\s+", re.IGNORECASE),
    re.compile(r"<\s*system\s*>", re.IGNORECASE),
)


def _check_prompt_injection(text: str) -> None:
    """Log a warning if common prompt injection patterns are detected.

    Does not block the message — only logs for operator awareness.
    Blocking legitimate messages is a worse outcome than logging false positives.
    """
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            logger.warning(
                "agent.prompt_injection_detected",
                pattern=pattern.pattern,
                prompt_length=len(text),
            )
            return


class AgentService:
    """Orchestrates agent chat interactions.

    Handles message extraction, agent execution, and response formatting
    following the OpenAI Chat Completions API format.
    """

    def __init__(self) -> None:
        """Initialize with unified dependencies for agent tool execution."""
        self._deps: UnifiedDeps = create_unified_deps()
        init_settings = get_settings()
        self._correction_loop: SelfCorrectionLoop | None = (
            SelfCorrectionLoop(max_rounds=init_settings.agent_max_correction_rounds)
            if init_settings.agent_self_correction_enabled
            else None
        )

    async def chat(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        """Process a chat completion request.

        Extracts the last user message, runs the agent with transit deps,
        and returns an OpenAI-compatible response.

        Args:
            request: The chat completion request with messages.

        Returns:
            ChatCompletionResponse with the agent's response.

        Raises:
            AgentExecutionError: If the agent fails to generate a response.
        """
        # Split into history (all but last) and current user prompt (last message)
        current_prompt = request.messages[-1].content
        prior_messages = request.messages[:-1]
        message_history = _build_message_history(prior_messages) if prior_messages else None

        # Check for prompt injection patterns (log-only, does not block)
        _check_prompt_injection(current_prompt)

        # Classify prompt complexity for model routing
        tier = classify_prompt(current_prompt)
        tier_model = resolve_tier_model(tier)

        logger.info(
            "agent.chat_started",
            message_count=len(request.messages),
            history_count=len(prior_messages),
            user_prompt_length=len(current_prompt),
            model_tier=tier,
            tier_override=tier_model is not None,
        )

        # RAG query router - skip knowledge search for transit/schedule/vault queries
        settings = get_settings()
        if settings.knowledge_router_enabled:
            rag_decision = needs_rag(current_prompt)
            self._deps.rag_enabled = rag_decision.needs_rag
            logger.info(
                "agent.rag_routing",
                needs_rag=rag_decision.needs_rag,
                rag_score=rag_decision.rag_score,
                skip_score=rag_decision.skip_score,
                tier=tier,
            )
        else:
            self._deps.rag_enabled = True

        # Load active skills for dynamic instructions
        skills_instructions = ""
        try:
            async with AsyncSessionLocal() as db:
                skill_service = SkillService(db)
                skills_instructions = await skill_service.get_active_skills_content()
        except Exception:
            logger.warning("agent.skills_load_failed", exc_info=True)

        # Recall relevant memories for context injection
        memory_context = ""
        if settings.memory_enabled:
            try:
                async with AsyncSessionLocal() as memory_db:
                    memory_service = MemoryService(memory_db)
                    recall_request = MemoryRecallByQueryRequest(
                        query=current_prompt[:2000],
                        limit=settings.memory_max_recall_results,
                        min_score=settings.memory_recall_min_score,
                    )
                    recalled = await memory_service.recall_by_query(recall_request)

                if recalled:
                    memory_lines = [
                        f"- [{r.score:.2f}] {r.memory.content[:300]}"
                        for r in recalled[: settings.memory_context_injection_limit]
                    ]
                    memory_context = (
                        "RELEVANT MEMORIES (from prior interactions - use as context, "
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

        correction_warnings: list[str] | None = None
        try:
            if tier == "complex":
                pipeline = get_complex_pipeline(agent, self._deps)
                pipeline_result = await pipeline.run(
                    current_prompt,
                    message_history=message_history,
                    instructions=instructions,
                    model=tier_model,
                )
                response_content = pipeline_result.output

                logger.info(
                    "agent.pipeline.summary",
                    phases_completed=pipeline_result.phases_completed,
                    total_duration_ms=pipeline_result.total_duration_ms,
                    phase_details=[
                        {"name": pd.name, "duration_ms": pd.duration_ms, "status": pd.status}
                        for pd in pipeline_result.phase_details
                    ],
                )
            elif self._correction_loop is not None:
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
                correction_warnings = corrected.warnings
            else:
                result = await agent.run(
                    current_prompt,
                    deps=self._deps,
                    message_history=message_history,
                    instructions=instructions,
                    model=tier_model,
                )
                response_content = result.output

                # Fire-and-forget: persist multi-tool episodes as memory
                persist_agent_episode(
                    agent_name="transit_agent",
                    prompt=current_prompt,
                    response=response_content,
                    messages=result.all_messages(),
                )
        except Exception as e:
            logger.error(
                "agent.chat_failed",
                exc_info=True,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise AgentExecutionError(f"Agent execution failed: {e}") from e

        # Reuse correction loop's validation when available; otherwise validate now.
        if correction_warnings is None:
            validation = validate_transit_response(response_content)
            warnings_to_render = list(validation.warnings)
        else:
            warnings_to_render = correction_warnings

        if warnings_to_render:
            for warning in warnings_to_render:
                logger.warning(
                    "agent.response_validation_warning",
                    warning=warning,
                )
            footnotes = "\n".join(f"\u26a0\ufe0f {w}" for w in warnings_to_render)
            response_content = f"{response_content}\n\n---\n{footnotes}"

        response_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
        settings = get_settings()
        model_name = (
            str(tier_model)
            if tier_model is not None
            else f"{settings.llm_provider}:{settings.llm_model}"
        )

        response = ChatCompletionResponse(
            id=response_id,
            created=int(time.time()),
            model=model_name,
            choices=[
                ChatCompletionChoice(
                    index=0,
                    message=ChatMessage(role="assistant", content=response_content),
                    finish_reason="stop",
                )
            ],
            usage=UsageInfo(),
        )

        logger.info(
            "agent.chat_completed",
            response_id=response_id,
            output_length=len(response_content),
        )

        return response

    async def close(self) -> None:
        """Close HTTP clients used by agent tools."""
        try:
            await self._deps.transit_http_client.aclose()
        except RuntimeError:
            pass  # Event loop already closed during shutdown
        try:
            await self._deps.obsidian_http_client.aclose()
        except RuntimeError:
            pass  # Event loop already closed during shutdown


# --- Module-level singleton ---

_agent_service: AgentService | None = None


def get_agent_service() -> AgentService:
    """Get or create the agent service singleton.

    Reuses the same httpx.AsyncClient across requests for connection pooling.

    Returns:
        Singleton AgentService instance.
    """
    global _agent_service
    if _agent_service is None:
        _agent_service = AgentService()
    return _agent_service


async def close_agent_service() -> None:
    """Close the singleton agent service and its HTTP client.

    Called during application shutdown.
    """
    global _agent_service
    if _agent_service is not None:
        await _agent_service.close()
        _agent_service = None
