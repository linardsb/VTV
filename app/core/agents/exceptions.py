"""Agent-specific exceptions and exception handlers.

Exception hierarchy:
- AgentError (base)
  - AgentConfigurationError (invalid LLM config) → 500
  - AgentExecutionError (LLM call failed) → 502
  - TransitDataError (transit feed fetch/parse failed) → 503
  - ObsidianError (vault operation failed) → 503
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
    if isinstance(exc, AgentExecutionError):
        status_code = status.HTTP_502_BAD_GATEWAY
    elif isinstance(exc, (TransitDataError, ObsidianError)):
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
    app.add_exception_handler(TransitDataError, handler)
    app.add_exception_handler(ObsidianError, handler)
