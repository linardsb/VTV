"""Tests for the memory bridge - fire-and-forget agent episode persistence."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    UserPromptPart,
)

from app.memory.bridge import (
    _persist_episode,
    extract_tool_names,
    persist_agent_episode,
)

# --- extract_tool_names ---


def test_extract_tool_names_from_messages() -> None:
    """Extracts unique tool names in call order."""
    messages: list[ModelMessage] = [
        ModelRequest(parts=[UserPromptPart(content="hello")]),
        ModelResponse(
            parts=[
                ToolCallPart(tool_name="tool_a", args="{}"),
                ToolCallPart(tool_name="tool_b", args="{}"),
            ]
        ),
        ModelResponse(
            parts=[
                ToolCallPart(tool_name="tool_a", args="{}"),  # duplicate
            ]
        ),
    ]
    result = extract_tool_names(messages)
    assert result == ["tool_a", "tool_b"]


def test_extract_tool_names_empty_messages() -> None:
    """Empty message list returns empty tool list."""
    assert extract_tool_names([]) == []


def test_extract_tool_names_no_tool_calls() -> None:
    """Messages with only text parts return empty tool list."""
    messages: list[ModelMessage] = [
        ModelResponse(parts=[TextPart(content="Just text")]),
        ModelRequest(parts=[UserPromptPart(content="A question")]),
    ]
    assert extract_tool_names(messages) == []


# --- persist_agent_episode ---


def _make_multi_tool_messages() -> list[ModelMessage]:
    """Build messages with 2 distinct tools for testing."""
    return [
        ModelRequest(parts=[UserPromptPart(content="test prompt")]),
        ModelResponse(
            parts=[
                ToolCallPart(tool_name="tool_a", args="{}"),
                ToolCallPart(tool_name="tool_b", args="{}"),
            ]
        ),
    ]


def _make_single_tool_messages() -> list[ModelMessage]:
    """Build messages with only 1 tool."""
    return [
        ModelResponse(parts=[ToolCallPart(tool_name="tool_a", args="{}")]),
    ]


@patch("app.memory.bridge.asyncio.create_task")
@patch("app.memory.bridge.get_settings")
def test_persist_agent_episode_skips_single_tool(
    mock_settings: MagicMock,
    mock_create_task: MagicMock,
) -> None:
    """Single tool usage does not trigger persistence."""
    mock_settings.return_value.memory_enabled = True
    persist_agent_episode(
        agent_name="transit_agent",
        prompt="test",
        response="response",
        messages=_make_single_tool_messages(),
    )
    mock_create_task.assert_not_called()


@patch("app.memory.bridge.asyncio.create_task")
@patch("app.memory.bridge.get_settings")
def test_persist_agent_episode_fires_for_multi_tool(
    mock_settings: MagicMock,
    mock_create_task: MagicMock,
) -> None:
    """Multi-tool usage triggers background task creation."""
    mock_settings.return_value.memory_enabled = True
    persist_agent_episode(
        agent_name="transit_agent",
        prompt="test",
        response="response",
        messages=_make_multi_tool_messages(),
    )
    mock_create_task.assert_called_once()


@patch("app.memory.bridge.asyncio.create_task")
@patch("app.memory.bridge.get_settings")
def test_persist_agent_episode_skips_when_memory_disabled(
    mock_settings: MagicMock,
    mock_create_task: MagicMock,
) -> None:
    """Memory disabled in settings prevents task creation."""
    mock_settings.return_value.memory_enabled = False
    persist_agent_episode(
        agent_name="transit_agent",
        prompt="test",
        response="response",
        messages=_make_multi_tool_messages(),
    )
    mock_create_task.assert_not_called()


# --- _persist_episode ---


@pytest.mark.asyncio
@patch("app.memory.bridge.get_db_context")
async def test_persist_episode_stores_memory(
    mock_db_ctx: MagicMock,
) -> None:
    """_persist_episode stores an episodic memory entry."""
    mock_session = AsyncMock()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    mock_db_ctx.return_value = ctx

    mock_entry = MagicMock()
    mock_entry.id = 42

    with patch("app.memory.bridge.MemoryService") as mock_svc_cls:
        mock_svc = AsyncMock()
        mock_svc.store.return_value = mock_entry
        mock_svc_cls.return_value = mock_svc

        await _persist_episode(
            agent_name="transit_agent",
            prompt="What buses are near stop X?",
            response="Bus 5 is 2 minutes away.",
            tools_used=["query_bus_status", "search_stops"],
        )

        mock_svc.store.assert_called_once()
        call_data = mock_svc.store.call_args[0][0]
        assert call_data.memory_type == "episodic"
        assert call_data.source == "agent"
        assert call_data.agent_type == "transit_agent"
        assert "query_bus_status" in call_data.content
        assert "search_stops" in call_data.content


@pytest.mark.asyncio
@patch("app.memory.bridge.get_db_context")
async def test_persist_episode_catches_db_error(
    mock_db_ctx: MagicMock,
) -> None:
    """DB errors are caught and logged, never propagate."""
    mock_db_ctx.side_effect = Exception("DB connection failed")

    # Should not raise
    await _persist_episode(
        agent_name="transit_agent",
        prompt="test",
        response="response",
        tools_used=["tool_a", "tool_b"],
    )


@pytest.mark.asyncio
@patch("app.memory.bridge.get_db_context")
async def test_persist_episode_content_format(
    mock_db_ctx: MagicMock,
) -> None:
    """Content string matches the expected format."""
    mock_session = AsyncMock()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    mock_db_ctx.return_value = ctx

    mock_entry = MagicMock()
    mock_entry.id = 1

    with patch("app.memory.bridge.MemoryService") as mock_svc_cls:
        mock_svc = AsyncMock()
        mock_svc.store.return_value = mock_entry
        mock_svc_cls.return_value = mock_svc

        await _persist_episode(
            agent_name="transit_agent",
            prompt="Where is bus 5?",
            response="Bus 5 is at stop Central.",
            tools_used=["query_bus_status"],
        )

        call_data = mock_svc.store.call_args[0][0]
        assert call_data.content.startswith("[transit_agent] Dispatcher asked:")
        assert "Agent used: query_bus_status" in call_data.content
        assert "Response: Bus 5 is at stop Central." in call_data.content


@pytest.mark.asyncio
@patch("app.memory.bridge.get_db_context")
async def test_persist_episode_truncates_long_input(
    mock_db_ctx: MagicMock,
) -> None:
    """Long prompts and responses are truncated in content."""
    mock_session = AsyncMock()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    mock_db_ctx.return_value = ctx

    mock_entry = MagicMock()
    mock_entry.id = 1

    long_prompt = "x" * 500
    long_response = "y" * 1000

    with patch("app.memory.bridge.MemoryService") as mock_svc_cls:
        mock_svc = AsyncMock()
        mock_svc.store.return_value = mock_entry
        mock_svc_cls.return_value = mock_svc

        await _persist_episode(
            agent_name="transit_agent",
            prompt=long_prompt,
            response=long_response,
            tools_used=["tool_a"],
        )

        call_data = mock_svc.store.call_args[0][0]
        # Prompt truncated to 150, response to 300
        assert "x" * 150 in call_data.content
        assert "x" * 151 not in call_data.content
        assert "y" * 300 in call_data.content
        assert "y" * 301 not in call_data.content
