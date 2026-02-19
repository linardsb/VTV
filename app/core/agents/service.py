"""Agent service layer for orchestrating chat interactions.

This module provides the AgentService class that handles the full
lifecycle of a chat request: extracting user messages, running the
agent, and constructing OpenAI-compatible responses.
"""

import time
import uuid

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)

from app.core.agents.agent import agent
from app.core.agents.exceptions import AgentExecutionError
from app.core.agents.schemas import (
    ChatCompletionChoice,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    UsageInfo,
)
from app.core.agents.tools.transit.deps import UnifiedDeps, create_unified_deps
from app.core.config import get_settings
from app.core.logging import get_logger

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


class AgentService:
    """Orchestrates agent chat interactions.

    Handles message extraction, agent execution, and response formatting
    following the OpenAI Chat Completions API format.
    """

    def __init__(self) -> None:
        """Initialize with unified dependencies for agent tool execution."""
        self._deps: UnifiedDeps = create_unified_deps()

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

        logger.info(
            "agent.chat_started",
            message_count=len(request.messages),
            history_count=len(prior_messages),
            user_prompt_length=len(current_prompt),
        )

        try:
            result = await agent.run(
                current_prompt,
                deps=self._deps,
                message_history=message_history,
            )
        except Exception as e:
            logger.error(
                "agent.chat_failed",
                exc_info=True,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise AgentExecutionError(f"Agent execution failed: {e}") from e

        response_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
        settings = get_settings()
        model_name = f"{settings.llm_provider}:{settings.llm_model}"

        response = ChatCompletionResponse(
            id=response_id,
            created=int(time.time()),
            model=model_name,
            choices=[
                ChatCompletionChoice(
                    index=0,
                    message=ChatMessage(role="assistant", content=result.output),
                    finish_reason="stop",
                )
            ],
            usage=UsageInfo(),
        )

        logger.info(
            "agent.chat_completed",
            response_id=response_id,
            output_length=len(result.output),
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
