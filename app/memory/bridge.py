"""Memory bridge - fire-and-forget auto-persistence of agent episodes.

Captures multi-tool agent interactions as episodic memories without
blocking the response pipeline. All exceptions are caught and logged.
"""

import asyncio
from typing import Any

from pydantic_ai.messages import ModelMessage, ModelResponse, ToolCallPart

from app.core.config import get_settings
from app.core.database import get_db_context
from app.core.logging import get_logger
from app.memory.schemas import MemoryEntryCreate
from app.memory.service import MemoryService

logger = get_logger(__name__)


def extract_tool_names(messages: list[ModelMessage]) -> list[str]:
    """Extract unique tool names from agent message history.

    Args:
        messages: Full message history from agent.run().all_messages().

    Returns:
        Deduplicated list of tool names in call order.
    """
    seen: set[str] = set()
    tools: list[str] = []
    for msg in messages:
        if isinstance(msg, ModelResponse):
            for part in msg.parts:
                if isinstance(part, ToolCallPart) and part.tool_name not in seen:
                    seen.add(part.tool_name)
                    tools.append(part.tool_name)
    return tools


async def _persist_episode(
    agent_name: str,
    prompt: str,
    response: str,
    tools_used: list[str],
    confidence: float | None = None,
) -> None:
    """Store an episodic memory entry for a multi-tool interaction.

    Opens its own DB session via get_db_context() for isolation.
    Never raises - all exceptions caught and logged as warnings.

    Args:
        agent_name: Name of the agent that processed the request.
        prompt: Original user prompt (truncated to 150 chars in content).
        response: Agent's final response (truncated to 300 chars in content).
        tools_used: List of distinct tool names used.
        confidence: Optional confidence score for metadata.
    """
    try:
        content = (
            f"[{agent_name}] Dispatcher asked: {prompt[:150]}. "
            f"Agent used: {', '.join(tools_used)}. "
            f"Response: {response[:300]}"
        )

        metadata: dict[str, Any] = {
            "source": "agent",
            "agent_name": agent_name,
            "tools": tools_used,
        }
        if confidence is not None:
            metadata["confidence"] = confidence

        data = MemoryEntryCreate(
            agent_type=agent_name,
            memory_type="episodic",
            content=content,
            metadata_json=metadata,
            source="agent",
        )

        async with get_db_context() as db:
            service = MemoryService(db)
            entry = await service.store(data)

        logger.info(
            "memory.bridge.episode_stored",
            memory_id=entry.id,
            agent_name=agent_name,
            tools_used=tools_used,
            tool_count=len(tools_used),
        )
    except Exception:
        logger.warning("memory.bridge.storage_failed", exc_info=True)


def persist_agent_episode(
    agent_name: str,
    prompt: str,
    response: str,
    messages: list[ModelMessage],
    min_tools: int = 2,
) -> None:
    """Fire-and-forget: persist a multi-tool agent interaction as episodic memory.

    Only persists when the interaction used >= min_tools distinct tools.
    Spawns a background asyncio task - does not block the caller.

    Args:
        agent_name: Name of the agent (e.g. "transit_agent").
        prompt: Original user prompt.
        response: Agent's final response text.
        messages: Full message history from agent run.
        min_tools: Minimum distinct tools required to persist (default 2).
    """
    settings = get_settings()
    if not settings.memory_enabled:
        return

    tools_used = extract_tool_names(messages)
    if len(tools_used) < min_tools:
        return

    logger.info(
        "memory.bridge.episode_persisting",
        agent_name=agent_name,
        tool_count=len(tools_used),
        tools=tools_used,
    )

    asyncio.create_task(  # noqa: RUF006
        _persist_episode(
            agent_name=agent_name,
            prompt=prompt,
            response=response,
            tools_used=tools_used,
        )
    )
