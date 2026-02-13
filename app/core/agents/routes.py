"""Agent API routes following OpenAI-compatible format.

Endpoints:
- POST /v1/chat/completions — Send messages and receive agent responses
- GET /v1/models — List available models
"""

from typing import Any

from fastapi import APIRouter, Depends

from app.core.agents.schemas import ChatCompletionRequest, ChatCompletionResponse
from app.core.agents.service import AgentService, get_agent_service
from app.core.config import get_settings

router = APIRouter(prefix="/v1", tags=["agent"])


@router.post("/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(
    request: ChatCompletionRequest,
    service: AgentService = Depends(get_agent_service),
) -> ChatCompletionResponse:
    """Create a chat completion.

    Accepts a list of messages and returns the agent's response
    in OpenAI-compatible format.

    Args:
        request: Chat completion request with messages.
        service: Agent service instance (injected).

    Returns:
        Chat completion response with the agent's message.
    """
    return await service.chat(request)


@router.get("/models")
async def list_models() -> dict[str, Any]:
    """List available models.

    Returns the currently configured LLM model information.

    Returns:
        Dictionary with model list in OpenAI-compatible format.
    """
    settings = get_settings()
    model_id = f"{settings.llm_provider}:{settings.llm_model}"

    return {
        "object": "list",
        "data": [
            {
                "id": model_id,
                "object": "model",
            }
        ],
    }
