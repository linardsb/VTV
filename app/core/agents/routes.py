# pyright: reportUnknownMemberType=false, reportUntypedFunctionDecorator=false
"""Agent API routes following OpenAI-compatible format.

Endpoints:
- POST /v1/chat/completions — Send messages and receive agent responses
- GET /v1/models — List available models
"""

import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth.dependencies import get_current_user, require_role
from app.auth.models import User
from app.core.agents.agents.registry import get_agent_by_name
from app.core.agents.metrics import get_metrics_tracker
from app.core.agents.quota import get_quota_tracker
from app.core.agents.router import get_agent_router
from app.core.agents.schemas import (
    AgentName,
    ChatCompletionRequest,
    ChatCompletionResponse,
    CorrectionCheckSnapshot,
    CorrectionMetricsResponse,
    CorrectionTotals,
)
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.rate_limit import _get_client_ip, limiter

logger = get_logger(__name__)

router = APIRouter(prefix="/v1", tags=["agent"])


@router.post("/chat/completions", response_model=ChatCompletionResponse)
@limiter.limit("10/minute")
async def chat_completions(
    request: Request,
    body: ChatCompletionRequest,
    _current_user: User = Depends(get_current_user),
) -> ChatCompletionResponse:
    """Create a chat completion.

    Accepts a list of messages and returns the agent's response
    in OpenAI-compatible format. The concrete agent used is resolved from
    ``body.agent`` (defaults to ``"unified"`` for the all-tools ``AgentService``).

    Args:
        request: The incoming HTTP request (used for rate limiting).
        body: Chat completion request with messages and agent selector.

    Returns:
        Chat completion response with the agent's message.
    """
    # Check daily quota before expensive LLM call
    client_ip = _get_client_ip(request)
    tracker = get_quota_tracker()
    if not await tracker.check_and_increment(client_ip):
        remaining = await tracker.get_remaining(client_ip)
        logger.warning("agent.quota_exceeded_http", client_ip=client_ip, remaining=remaining)
        raise HTTPException(
            status_code=429,
            detail=f"Daily query quota exceeded. Remaining: {remaining}. Resets in 24 hours.",
        )

    selected_agent: AgentName = body.agent
    if body.agent == "unified" and get_settings().agent_multi_agent_enabled:
        last_user_message = next(
            (msg.content for msg in reversed(body.messages) if msg.role == "user"),
            "",
        )
        selected_agent = get_agent_router().route(last_user_message)

    service = get_agent_by_name(selected_agent)
    logger.info(
        "agent.chat.selected",
        agent=selected_agent,
        requested_agent=body.agent,
        auto_routed=selected_agent != body.agent,
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


@router.get("/chat/metrics", response_model=CorrectionMetricsResponse)
@limiter.limit("30/minute")
async def get_correction_metrics(
    request: Request,
    _admin: User = Depends(require_role("admin")),
) -> CorrectionMetricsResponse:
    """Return self-correction metrics for the current UTC day.

    Admin-only. Counters reset at 00:00 UTC. Use this to monitor whether
    the bounded self-correction loop in ``correction.py`` is improving
    response quality (high resolved/triggered ratio) or just adding
    latency (high exhausted/triggered ratio).

    Args:
        request: The incoming HTTP request (used for rate limiting).
        _admin: Injected admin user (RBAC enforcement only).

    Returns:
        Per-check counters plus aggregate totals.
    """
    tracker = get_metrics_tracker()
    snapshot = tracker.snapshot()

    checks: list[CorrectionCheckSnapshot] = []
    total_triggered = 0
    total_resolved = 0
    total_exhausted = 0
    total_latency_ms = 0

    for check_name, metrics in sorted(snapshot.items()):
        completed = metrics.resolved + metrics.exhausted
        success_rate = metrics.resolved / completed if completed else 0.0
        avg_latency = metrics.total_latency_ms / completed if completed else 0.0
        checks.append(
            CorrectionCheckSnapshot(
                check_name=check_name,
                triggered=metrics.triggered,
                resolved=metrics.resolved,
                exhausted=metrics.exhausted,
                success_rate=success_rate,
                avg_latency_ms=avg_latency,
            )
        )
        total_triggered += metrics.triggered
        total_resolved += metrics.resolved
        total_exhausted += metrics.exhausted
        total_latency_ms += metrics.total_latency_ms

    completed_total = total_resolved + total_exhausted
    totals = CorrectionTotals(
        triggered=total_triggered,
        resolved=total_resolved,
        exhausted=total_exhausted,
        success_rate=(total_resolved / completed_total) if completed_total else 0.0,
        avg_latency_ms=(total_latency_ms / completed_total) if completed_total else 0.0,
    )

    return CorrectionMetricsResponse(
        period_start=tracker.period_start(),
        generated_at=datetime.datetime.now(datetime.UTC),
        checks=checks,
        totals=totals,
    )
