"""Tests for ``app.core.agents.agents.knowledge.KnowledgeAgent`` (AI-6.2)."""

# pyright: reportPrivateUsage=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownMemberType=false

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from pydantic_ai import models
from pydantic_ai.models.test import TestModel

from app.core.agents.agents.knowledge import (
    KNOWLEDGE_SYSTEM_PROMPT,
    KnowledgeAgent,
    knowledge_agent,
)
from app.core.agents.exceptions import AgentExecutionError
from app.core.agents.schemas import ChatCompletionRequest, ChatMessage
from app.core.agents.tools.transit.deps import UnifiedDeps
from app.core.config import get_settings
from app.memory.schemas import MemoryEntryResponse, MemoryRecallResponse
from app.shared.models import utcnow

# Prevent accidental real LLM API calls during testing.
models.ALLOW_MODEL_REQUESTS = False


def _make_request(text: str = "What is the overtime policy?") -> ChatCompletionRequest:
    return ChatCompletionRequest(messages=[ChatMessage(role="user", content=text)])


def _create_knowledge_agent_service() -> KnowledgeAgent:
    """Build a KnowledgeAgent with mocked HTTP deps."""
    with patch("app.core.agents.agents.knowledge.create_unified_deps") as mock_deps:
        mock_deps.return_value = UnifiedDeps(
            transit_http_client=AsyncMock(spec=httpx.AsyncClient),
            obsidian_http_client=AsyncMock(spec=httpx.AsyncClient),
            settings=get_settings(),
            db_session_factory=None,
            rag_enabled=True,
        )
        return KnowledgeAgent()


def _make_recall_responses(count: int = 1) -> list[MemoryRecallResponse]:
    now = utcnow()
    out: list[MemoryRecallResponse] = []
    for i in range(count):
        entry = MemoryEntryResponse(
            id=i + 1,
            agent_type="knowledge",
            memory_type="semantic",
            content=f"Knowledge memory {i + 1}",
            metadata_json=None,
            decay_weight=1.0,
            is_evergreen=False,
            source="agent",
            recalled_count=0,
            created_at=now,
            updated_at=now,
        )
        out.append(MemoryRecallResponse(memory=entry, score=0.9 - i * 0.1))
    return out


def _settings_mock() -> MagicMock:
    """Return a Settings MagicMock with memory OFF + test LLM metadata."""
    settings_obj = MagicMock()
    settings_obj.memory_enabled = False
    settings_obj.agent_self_correction_enabled = False
    settings_obj.llm_provider = "test"
    settings_obj.llm_model = "test-model"
    return settings_obj


# --- 1. agent_name ----------------------------------------------------------


def test_agent_name_is_knowledge_agent() -> None:
    svc = _create_knowledge_agent_service()
    assert svc.agent_name == "knowledge_agent"


# --- 2. Tool set is only search_knowledge_base -----------------------------


def test_tool_set_has_only_search_knowledge_base() -> None:
    tools = knowledge_agent._function_toolset.tools
    assert set(tools.keys()) == {"search_knowledge_base"}
    assert "query_bus_status" not in tools
    assert "obsidian_query_vault" not in tools


# --- 3. RAG routing always enables RAG -------------------------------------


@pytest.mark.asyncio
async def test_apply_rag_routing_always_enables_rag() -> None:
    svc = _create_knowledge_agent_service()
    svc._deps.rag_enabled = False
    await svc._apply_rag_routing("any", "standard")
    assert svc._deps.rag_enabled is True


# --- 4. _run_qa returns empty list -----------------------------------------


def test_run_qa_returns_empty_list() -> None:
    svc = _create_knowledge_agent_service()
    result = svc._run_qa(
        response="Hello, here are the results.",
        current_prompt="test",
        messages=[],
        static_cache=None,
    )
    assert result == []


# --- 5. post_process does NOT append warning footnotes --------------------


@pytest.mark.asyncio
async def test_post_process_does_not_append_warning_footnotes() -> None:
    svc = _create_knowledge_agent_service()
    with knowledge_agent.override(model=TestModel()):
        with patch("app.core.agents.agents.knowledge.get_settings", return_value=_settings_mock()):
            with patch("app.core.agents.agents.knowledge.logger"):
                response = await svc.chat(_make_request("What is policy X?"))
    assert "\u26a0\ufe0f" not in response.choices[0].message.content


# --- 6. Memory enabled returns formatted recall block ---------------------


@pytest.mark.asyncio
async def test_recall_memories_block_when_memory_enabled() -> None:
    svc = _create_knowledge_agent_service()
    mock_memory_svc = AsyncMock()
    mock_memory_svc.recall_by_query.return_value = _make_recall_responses(1)

    with patch("app.core.agents.agents.knowledge.MemoryService", return_value=mock_memory_svc):
        with patch("app.core.agents.agents.knowledge.get_settings") as mock_settings:
            settings_obj = MagicMock()
            settings_obj.memory_enabled = True
            settings_obj.memory_max_recall_results = 5
            settings_obj.memory_recall_min_score = 0.5
            settings_obj.memory_context_injection_limit = 10
            mock_settings.return_value = settings_obj
            result = await svc._recall_memories_block("test")

    assert result.startswith("RELEVANT MEMORIES")
    assert "[0.90]" in result


# --- 7. Memory disabled returns empty --------------------------------------


@pytest.mark.asyncio
async def test_recall_memories_block_when_memory_disabled() -> None:
    svc = _create_knowledge_agent_service()
    with patch("app.core.agents.agents.knowledge.get_settings") as mock_settings:
        settings_obj = MagicMock()
        settings_obj.memory_enabled = False
        mock_settings.return_value = settings_obj
        result = await svc._recall_memories_block("test")
    assert result == ""


# --- 8. _execute persists episode tagged knowledge_agent -----------------


@pytest.mark.asyncio
async def test_execute_calls_persist_agent_episode_with_knowledge_tag() -> None:
    svc = _create_knowledge_agent_service()

    fake_result = MagicMock()
    fake_result.output = "search output"
    fake_result.all_messages.return_value = []

    with patch(
        "app.core.agents.agents.knowledge.knowledge_agent.run",
        new=AsyncMock(return_value=fake_result),
    ):
        with patch("app.core.agents.agents.knowledge.persist_agent_episode") as mock_persist:
            await svc._execute(
                user_message="q",
                current_prompt="q",
                message_history=None,
                instructions=None,
                tier="standard",
                tier_model=None,
                static_cache=None,
            )

    mock_persist.assert_called_once()
    assert mock_persist.call_args.kwargs["agent_name"] == "knowledge_agent"


# --- 9. _execute uses fallback path for complex tier (no branching) ------


@pytest.mark.asyncio
async def test_execute_uses_fallback_path_for_complex_tier() -> None:
    svc = _create_knowledge_agent_service()

    fake_result = MagicMock()
    fake_result.output = "out"
    fake_result.all_messages.return_value = []

    with patch(
        "app.core.agents.agents.knowledge.knowledge_agent.run",
        new=AsyncMock(return_value=fake_result),
    ) as mock_run:
        with patch("app.core.agents.agents.knowledge.persist_agent_episode"):
            await svc._execute(
                user_message="q",
                current_prompt="q",
                message_history=None,
                instructions=None,
                tier="complex",
                tier_model=None,
                static_cache=None,
            )

    mock_run.assert_awaited_once()


# --- 10. complex tier does NOT invoke get_complex_pipeline ---------------


@pytest.mark.asyncio
async def test_complex_tier_does_not_invoke_get_complex_pipeline() -> None:
    svc = _create_knowledge_agent_service()

    fake_result = MagicMock()
    fake_result.output = "out"
    fake_result.all_messages.return_value = []

    with patch(
        "app.core.agents.agents.knowledge.knowledge_agent.run",
        new=AsyncMock(return_value=fake_result),
    ):
        with patch("app.core.agents.agents.knowledge.persist_agent_episode"):
            with patch("app.core.agents.pipeline.get_complex_pipeline") as mock_pipeline:
                await svc._execute(
                    user_message="q",
                    current_prompt="q",
                    message_history=None,
                    instructions=None,
                    tier="complex",
                    tier_model=None,
                    static_cache=None,
                )

    mock_pipeline.assert_not_called()


# --- 11. chat wraps _execute exceptions -----------------------------------


@pytest.mark.asyncio
async def test_chat_wraps_execute_exceptions_as_agent_execution_error() -> None:
    svc = _create_knowledge_agent_service()

    async def _boom(**_kwargs: Any) -> None:
        raise RuntimeError("LLM exploded")

    with patch.object(KnowledgeAgent, "_execute", new=_boom):
        with patch("app.core.agents.agents.knowledge.get_settings", return_value=_settings_mock()):
            with pytest.raises(AgentExecutionError, match="Agent execution failed"):
                await svc.chat(_make_request("Hello"))


# --- 12. chat logs chat_started and chat_completed ------------------------


@pytest.mark.asyncio
async def test_chat_logs_chat_started_and_completed() -> None:
    svc = _create_knowledge_agent_service()

    with knowledge_agent.override(model=TestModel()):
        with patch("app.core.agents.agents.knowledge.get_settings", return_value=_settings_mock()):
            with patch("app.core.agents.base.logger") as mock_logger:
                await svc.chat(_make_request("Hello"))

    event_names = [call.args[0] for call in mock_logger.info.call_args_list if call.args]
    assert "agent.chat_started" in event_names
    assert "agent.chat_completed" in event_names


# --- 13. System prompt contains citation marker ---------------------------


def test_system_prompt_contains_citation_marker() -> None:
    assert "Sources" in KNOWLEDGE_SYSTEM_PROMPT
    assert "document_id" in KNOWLEDGE_SYSTEM_PROMPT


# --- 14. System prompt tells the agent to say "I don't know" --------------


def test_system_prompt_contains_no_results_instruction() -> None:
    prompt = KNOWLEDGE_SYSTEM_PROMPT
    assert "I don't know" in prompt or "No relevant documents" in prompt


# --- 15. close() swallows RuntimeError on closed loop --------------------


@pytest.mark.asyncio
async def test_close_swallows_runtime_error_on_closed_loop() -> None:
    svc = _create_knowledge_agent_service()
    failing_client = AsyncMock()
    failing_client.aclose.side_effect = RuntimeError("closed")
    svc._deps.transit_http_client = failing_client
    svc._deps.obsidian_http_client = failing_client
    await svc.close()
