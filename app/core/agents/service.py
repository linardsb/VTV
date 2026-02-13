"""Agent service layer for orchestrating chat interactions.

This module provides the AgentService class that handles the full
lifecycle of a chat request: extracting user messages, running the
agent, and constructing OpenAI-compatible responses.
"""

import time
import uuid

from app.core.agents.agent import agent
from app.core.agents.exceptions import AgentExecutionError
from app.core.agents.schemas import (
    ChatCompletionChoice,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    UsageInfo,
)
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class AgentService:
    """Orchestrates agent chat interactions.

    Handles message extraction, agent execution, and response formatting
    following the OpenAI Chat Completions API format.
    """

    async def chat(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        """Process a chat completion request.

        Extracts the last user message, runs the agent, and returns
        an OpenAI-compatible response.

        Args:
            request: The chat completion request with messages.

        Returns:
            ChatCompletionResponse with the agent's response.

        Raises:
            AgentExecutionError: If the agent fails to generate a response.
        """
        # Extract last user message
        user_messages = [m for m in request.messages if m.role == "user"]
        user_prompt = user_messages[-1].content if user_messages else request.messages[-1].content

        logger.info(
            "agent.chat_started",
            message_count=len(request.messages),
            user_prompt_length=len(user_prompt),
        )

        try:
            result = await agent.run(user_prompt)
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


def get_agent_service() -> AgentService:
    """Factory function for FastAPI dependency injection.

    Returns:
        AgentService instance.
    """
    return AgentService()
