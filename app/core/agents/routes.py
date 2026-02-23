# pyright: reportUnknownMemberType=false, reportUntypedFunctionDecorator=false
"""Agent API routes following OpenAI-compatible format.

Endpoints:
- POST /v1/chat/completions — Send messages and receive agent responses
- GET /v1/models — List available models
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.core.agents.quota import get_quota_tracker
from app.core.agents.schemas import ChatCompletionRequest, ChatCompletionResponse
from app.core.agents.service import AgentService, get_agent_service
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.rate_limit import limiter

logger = get_logger(__name__)

router = APIRouter(prefix="/v1", tags=["agent"])


@router.post("/chat/completions", response_model=ChatCompletionResponse)
@limiter.limit("10/minute")
async def chat_completions(
    request: Request,
    body: ChatCompletionRequest,
    service: AgentService = Depends(get_agent_service),
    _current_user: User = Depends(get_current_user),
) -> ChatCompletionResponse:
    """Create a chat completion.

    Accepts a list of messages and returns the agent's response
    in OpenAI-compatible format.

    Args:
        request: The incoming HTTP request (used for rate limiting).
        body: Chat completion request with messages.
        service: Agent service instance (injected).

    Returns:
        Chat completion response with the agent's message.
    """
    # Check daily quota before expensive LLM call
    client_ip = request.client.host if request.client else "unknown"
    tracker = get_quota_tracker()
    if not await tracker.check_and_increment(client_ip):
        remaining = await tracker.get_remaining(client_ip)
        logger.warning("agent.quota_exceeded_http", client_ip=client_ip, remaining=remaining)
        raise HTTPException(
            status_code=429,
            detail=f"Daily query quota exceeded. Remaining: {remaining}. Resets in 24 hours.",
        )

    return await service.chat(body)


@router.get("/models")
@limiter.limit("60/minute")
async def list_models(
    request: Request,
    _current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
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
