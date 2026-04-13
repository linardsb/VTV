"""Tests for ``app.core.agents.agents.transit.TransitAgent`` (AI-6.2)."""

# pyright: reportPrivateUsage=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownMemberType=false

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from pydantic_ai import models
from pydantic_ai.models.test import TestModel

from app.core.agents.agents.transit import (
    TRANSIT_SYSTEM_PROMPT,
    TransitAgent,
    transit_agent,
)
from app.core.agents.exceptions import AgentExecutionError
from app.core.agents.schemas import ChatCompletionRequest, ChatMessage
from app.core.agents.tools.transit.deps import UnifiedDeps
from app.core.config import get_settings
from app.knowledge.router import RoutingDecision
from app.memory.schemas import MemoryEntryResponse, MemoryRecallResponse
from app.shared.models import utcnow

# Prevent accidental real LLM API calls during testing.
models.ALLOW_MODEL_REQUESTS = False


def _make_request(text: str = "Kuri marsruti kavejas?") -> ChatCompletionRequest:
    """Build a minimal chat request targeting the transit agent."""
    return ChatCompletionRequest(messages=[ChatMessage(role="user", content=text)])


def _create_transit_agent_service() -> TransitAgent:
    """Build a TransitAgent with mocked HTTP deps."""
    with patch("app.core.agents.agents.transit.create_unified_deps") as mock_deps:
        mock_deps.return_value = UnifiedDeps(
            transit_http_client=AsyncMock(spec=httpx.AsyncClient),
            obsidian_http_client=AsyncMock(spec=httpx.AsyncClient),
            settings=get_settings(),
            db_session_factory=None,
            rag_enabled=True,
        )
        return TransitAgent()


def _make_recall_responses(count: int = 1) -> list[MemoryRecallResponse]:
    """Build mock MemoryRecallResponse objects."""
    now = utcnow()
    out: list[MemoryRecallResponse] = []
    for i in range(count):
        entry = MemoryEntryResponse(
            id=i + 1,
            agent_type="transit",
            memory_type="semantic",
            content=f"Transit memory {i + 1}",
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


# --- 1. agent_name is pinned to transit_agent_v2 ----------------------------


def test_agent_name_is_transit_agent_v2() -> None:
    svc = _create_transit_agent_service()
    assert svc.agent_name == "transit_agent_v2"


# --- 2. Tool set contains the expected transit tools -------------------------


def test_tool_set_has_transit_tools() -> None:
    tools = transit_agent._function_toolset.tools
    expected = {
        "query_bus_status",
        "get_route_schedule",
        "search_stops",
        "get_adherence_report",
        "check_driver_availability",
        "predict_eta",
    }
    assert expected.issubset(set(tools.keys()))
    assert "search_knowledge_base" not in tools
    assert "obsidian_query_vault" not in tools
    assert "manage_agent_skills" not in tools


# --- 3. RAG routing disables RAG flag ---------------------------------------


@pytest.mark.asyncio
async def test_apply_rag_routing_disables_rag() -> None:
    svc = _create_transit_agent_service()
    svc._deps.rag_enabled = True
    await svc._apply_rag_routing("any prompt", "standard")
    assert svc._deps.rag_enabled is False


# --- 4. Memory disabled returns empty ---------------------------------------


@pytest.mark.asyncio
async def test_recall_memories_block_when_memory_disabled_returns_empty() -> None:
    svc = _create_transit_agent_service()
    with patch("app.core.agents.agents.transit.get_settings") as mock_settings:
        settings_obj = MagicMock()
        settings_obj.memory_enabled = False
        mock_settings.return_value = settings_obj
        result = await svc._recall_memories_block("prompt")
    assert result == ""


# --- 5. Memory enabled returns formatted RELEVANT MEMORIES block ------------


@pytest.mark.asyncio
async def test_recall_memories_block_returns_formatted_block() -> None:
    svc = _create_transit_agent_service()
    mock_memory_svc = AsyncMock()
    mock_memory_svc.recall_by_query.return_value = _make_recall_responses(1)

    with patch("app.core.agents.agents.transit.MemoryService", return_value=mock_memory_svc):
        with patch("app.core.agents.agents.transit.get_settings") as mock_settings:
            settings_obj = MagicMock()
            settings_obj.memory_enabled = True
            settings_obj.memory_max_recall_results = 5
            settings_obj.memory_recall_min_score = 0.5
            settings_obj.memory_context_injection_limit = 10
            mock_settings.return_value = settings_obj
            result = await svc._recall_memories_block("Kuri marsruti kavejas?")

    assert result.startswith("RELEVANT MEMORIES")
    assert "[0.90]" in result
    assert "Transit memory 1" in result


# --- 6. Fallback _execute persists episode with agent_name ------------------


@pytest.mark.asyncio
async def test_execute_fallback_branch_calls_persist_agent_episode() -> None:
    svc = _create_transit_agent_service()
    svc._correction_loop = None  # force fallback branch

    fake_result = MagicMock()
    fake_result.output = "fallback response"
    fake_result.all_messages.return_value = []

    with patch(
        "app.core.agents.agents.transit.transit_agent.run",
        new=AsyncMock(return_value=fake_result),
    ):
        with patch("app.core.agents.agents.transit.persist_agent_episode") as mock_persist:
            outcome = await svc._execute(
                user_message="m",
                current_prompt="m",
                message_history=None,
                instructions=None,
                tier="standard",
                tier_model=None,
                static_cache=None,
            )

    assert outcome.response_text == "fallback response"
    assert outcome.warnings is None  # signals base to run QA
    mock_persist.assert_called_once()
    assert mock_persist.call_args.kwargs["agent_name"] == "transit_agent_v2"


# --- 7. Correction loop branch used when correction loop is set ------------


@pytest.mark.asyncio
async def test_execute_correction_branch_used_when_loop_enabled() -> None:
    svc = _create_transit_agent_service()

    fake_corrected = MagicMock()
    fake_corrected.output = "corrected"
    fake_corrected.warnings = []
    fake_corrected.all_messages = []

    mock_loop = MagicMock()
    mock_loop.run_with_correction = AsyncMock(return_value=fake_corrected)
    svc._correction_loop = mock_loop

    with patch("app.core.agents.agents.transit.persist_agent_episode") as mock_persist:
        outcome = await svc._execute(
            user_message="m",
            current_prompt="m",
            message_history=None,
            instructions=None,
            tier="standard",
            tier_model=None,
            static_cache=None,
        )

    mock_loop.run_with_correction.assert_awaited_once()
    assert outcome.response_text == "corrected"
    mock_persist.assert_called_once()


# --- 8. Complex-tier branch delegates to pipeline ---------------------------


@pytest.mark.asyncio
async def test_execute_complex_branch_uses_pipeline() -> None:
    svc = _create_transit_agent_service()

    fake_pipeline_result = MagicMock()
    fake_pipeline_result.output = "complex-output"
    fake_pipeline_result.phases_completed = 2
    fake_pipeline_result.total_duration_ms = 123
    fake_pipeline_result.phase_details = []

    mock_pipeline = MagicMock()
    mock_pipeline.run = AsyncMock(return_value=fake_pipeline_result)

    with patch(
        "app.core.agents.agents.transit.get_complex_pipeline", return_value=mock_pipeline
    ) as mock_factory:
        outcome = await svc._execute(
            user_message="complex",
            current_prompt="complex",
            message_history=None,
            instructions=None,
            tier="complex",
            tier_model=None,
            static_cache=None,
        )

    mock_factory.assert_called_once()
    mock_pipeline.run.assert_awaited_once()
    assert outcome.response_text == "complex-output"
    assert outcome.warnings == []


# --- 9. _run_qa delegates to validate_transit_response ----------------------


def test_run_qa_delegates_to_validate_transit_response() -> None:
    svc = _create_transit_agent_service()
    fake_validation = MagicMock()
    fake_validation.warnings = ["warning-1"]
    with patch(
        "app.core.agents.agents.transit.validate_transit_response",
        return_value=fake_validation,
    ) as mock_validate:
        result = svc._run_qa(
            response="response",
            current_prompt="prompt",
            messages=[],
            static_cache=None,
        )
    mock_validate.assert_called_once()
    assert result == ["warning-1"]


# --- 10. Preload validation cache returns None without db factory ----------


@pytest.mark.asyncio
async def test_preload_validation_cache_returns_none_when_no_db_factory() -> None:
    svc = _create_transit_agent_service()
    assert svc._deps.db_session_factory is None
    cache = await svc._preload_validation_cache()
    assert cache is None


# --- 11. Full chat() pipeline runs _execute via TestModel -------------------


@pytest.mark.asyncio
async def test_chat_full_pipeline_routes_to_execute() -> None:
    svc = _create_transit_agent_service()

    with transit_agent.override(model=TestModel()):
        with patch("app.core.agents.agents.transit.get_settings") as mock_settings:
            settings_obj = MagicMock()
            settings_obj.memory_enabled = False
            settings_obj.agent_self_correction_enabled = False
            settings_obj.llm_provider = "test"
            settings_obj.llm_model = "test-model"
            mock_settings.return_value = settings_obj
            with patch("app.core.agents.agents.transit.logger"):
                response = await svc.chat(_make_request("Kuri marsruti kavejas?"))

    assert response.object == "chat.completion"
    assert response.choices[0].message.role == "assistant"


# --- 12. chat() logs chat_started and chat_completed (via base logger) -----


@pytest.mark.asyncio
async def test_chat_logs_chat_started_and_completed() -> None:
    svc = _create_transit_agent_service()

    with transit_agent.override(model=TestModel()):
        with patch("app.core.agents.agents.transit.get_settings") as mock_settings:
            settings_obj = MagicMock()
            settings_obj.memory_enabled = False
            settings_obj.agent_self_correction_enabled = False
            settings_obj.llm_provider = "test"
            settings_obj.llm_model = "test-model"
            mock_settings.return_value = settings_obj
            with patch("app.core.agents.base.logger") as mock_logger:
                await svc.chat(_make_request("Hello"))

    event_names = [call.args[0] for call in mock_logger.info.call_args_list if call.args]
    assert "agent.chat_started" in event_names
    assert "agent.chat_completed" in event_names


# --- 13. _execute exceptions wrap as AgentExecutionError --------------------


@pytest.mark.asyncio
async def test_chat_wraps_execute_exceptions_as_agent_execution_error() -> None:
    svc = _create_transit_agent_service()

    async def _boom(**_kwargs: Any) -> None:
        raise RuntimeError("LLM exploded")

    with patch.object(TransitAgent, "_execute", new=_boom):
        with pytest.raises(AgentExecutionError, match="Agent execution failed"):
            await svc.chat(_make_request("Hello"))


# --- 14. close() swallows RuntimeError from closed event loops -------------


@pytest.mark.asyncio
async def test_close_swallows_runtime_error_on_closed_loop() -> None:
    svc = _create_transit_agent_service()
    failing_client = AsyncMock()
    failing_client.aclose.side_effect = RuntimeError("closed")
    svc._deps.transit_http_client = failing_client
    svc._deps.obsidian_http_client = failing_client
    # Must not raise.
    await svc.close()


# --- 15. System prompt excludes vault and knowledge sections ---------------


def test_system_prompt_excludes_vault_and_knowledge_sections() -> None:
    prompt_lower = TRANSIT_SYSTEM_PROMPT.lower()
    assert "obsidian" not in prompt_lower
    assert "knowledge base" not in prompt_lower
    assert "citation rules" not in prompt_lower
    # And it SHOULD still contain the transit-specific sections.
    assert "transit" in prompt_lower
    assert "latvian" in prompt_lower


# --- Supplementary: RAG routing via chat() uses the disabled override ------


@pytest.mark.asyncio
async def test_chat_rag_routing_disables_rag_unconditionally() -> None:
    svc = _create_transit_agent_service()
    svc._deps.rag_enabled = True
    with transit_agent.override(model=TestModel()):
        with patch("app.core.agents.agents.transit.get_settings") as mock_settings:
            settings_obj = MagicMock()
            settings_obj.memory_enabled = False
            settings_obj.agent_self_correction_enabled = False
            settings_obj.llm_provider = "test"
            settings_obj.llm_model = "test-model"
            mock_settings.return_value = settings_obj
            with patch("app.core.agents.agents.transit.logger"):
                with patch(
                    "app.core.agents.agents.transit.needs_rag",
                    return_value=RoutingDecision(needs_rag=True, rag_score=5, skip_score=0),
                ):
                    await svc.chat(_make_request("Hello"))
    assert svc._deps.rag_enabled is False
