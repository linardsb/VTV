"""Agent-specific exceptions and exception handlers.

Exception hierarchy:
- AgentError (base)
  - AgentConfigurationError (invalid LLM config) → 500
  - AgentExecutionError (LLM call failed) → 502
  - PromptInjectionBlockedError (high-confidence injection) → 400
  - OutputExfiltrationBlockedError (output exfiltration detected) → 400
  - TransitDataError (transit feed fetch/parse failed) → 503
  - ObsidianError (vault operation failed) → 503
  - CircuitBreakerOpenError (LLM provider breaker tripped) → 503
  - AllProvidersUnavailableError (entire provider chain exhausted) → 503
"""

from typing import Any, cast

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.core.logging import get_logger

logger = get_logger(__name__)


class AgentError(Exception):
    """Base exception for all agent errors."""

    pass


class AgentConfigurationError(AgentError):
    """Invalid LLM configuration (wrong provider, missing key)."""

    pass


class AgentExecutionError(AgentError):
    """Agent execution failed (LLM timeout, rate limit, etc.)."""

    pass


class TransitDataError(AgentError):
    """Transit data fetch or parse failed (feed unavailable, invalid protobuf)."""

    pass


class ObsidianError(AgentError):
    """Obsidian vault operation failed (vault unreachable, auth failed, note not found)."""

    pass


class CircuitBreakerOpenError(AgentError):
    """Raised when an LLM provider circuit breaker is OPEN and rejects a call.

    Maps to HTTP 503 (Service Unavailable) via the agent exception handler.
    The breaker opens after consecutive failures or sliding-window rate
    threshold is exceeded; it auto-recovers via HALF_OPEN probes.
    """

    pass


class PromptInjectionBlockedError(AgentError):
    """Raised when prompt injection confidence exceeds blocking threshold.

    Maps to HTTP 400. Response body uses a generic message -
    never echoes the injection text back to the caller.
    """

    pass


class OutputExfiltrationBlockedError(AgentError):
    """Raised when output validation detects high-confidence data exfiltration.

    Maps to HTTP 400. Response body uses a generic message -
    never echoes the flagged content back to the caller.
    """

    pass


class AllProvidersUnavailableError(AgentError):
    """Raised when every LLM provider in the fallback chain is unavailable.

    Either all breakers are OPEN or every attempted call raised. Maps to
    HTTP 503 so clients can retry after the configured ``recovery_timeout_s``.
    The service layer typically catches this and returns a degraded
    ``AgentResult`` instead of letting it propagate to HTTP — see
    ``app.core.agents.service.AgentService._execute``.
    """

    def __init__(self, providers_tried: list[str]) -> None:
        self.providers_tried = providers_tried
        super().__init__(f"All LLM providers unavailable: {', '.join(providers_tried)}")


async def agent_exception_handler(request: Request, exc: AgentError) -> JSONResponse:
    """Handle agent exceptions globally.

    Args:
        request: The incoming request.
        exc: The agent exception that was raised.

    Returns:
        JSONResponse with error details.
    """
    logger.error(
        "agent.error",
        extra={
            "error_type": type(exc).__name__,
            "error_message": str(exc),
            "path": request.url.path,
            "method": request.method,
        },
        exc_info=True,
    )

    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    if isinstance(exc, (PromptInjectionBlockedError, OutputExfiltrationBlockedError)):
        status_code = status.HTTP_400_BAD_REQUEST
    elif isinstance(exc, AgentExecutionError):
        status_code = status.HTTP_502_BAD_GATEWAY
    elif isinstance(
        exc,
        (
            TransitDataError,
            ObsidianError,
            CircuitBreakerOpenError,
            AllProvidersUnavailableError,
        ),
    ):
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return JSONResponse(
        status_code=status_code,
        content={
            "error": str(exc),
            "type": type(exc).__name__,
        },
    )


def setup_agent_exception_handlers(app: FastAPI) -> None:
    """Register agent exception handlers with the FastAPI application.

    Args:
        app: The FastAPI application instance.
    """
    handler: Any = cast(Any, agent_exception_handler)

    app.add_exception_handler(AgentError, handler)
    app.add_exception_handler(AgentConfigurationError, handler)
    app.add_exception_handler(AgentExecutionError, handler)
    app.add_exception_handler(PromptInjectionBlockedError, handler)
    app.add_exception_handler(OutputExfiltrationBlockedError, handler)
    app.add_exception_handler(TransitDataError, handler)
    app.add_exception_handler(ObsidianError, handler)
    app.add_exception_handler(CircuitBreakerOpenError, handler)
    app.add_exception_handler(AllProvidersUnavailableError, handler)
