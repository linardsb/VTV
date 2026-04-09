"""Tests for agent service layer."""

# pyright: reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownMemberType=false

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic_ai import models
from pydantic_ai.models.test import TestModel

from app.core.agents.agent import agent
from app.core.agents.exceptions import AgentExecutionError
from app.core.agents.schemas import ChatCompletionRequest, ChatMessage
from app.core.agents.service import AgentService
from app.knowledge.router import RoutingDecision
from app.memory.schemas import MemoryEntryResponse, MemoryRecallResponse

# Prevent accidental real LLM API calls during testing
models.ALLOW_MODEL_REQUESTS = False


def _create_service() -> AgentService:
    """Create an AgentService with mocked unified deps."""
    with patch("app.core.agents.service.create_unified_deps") as mock_deps:
        mock_deps.return_value.transit_http_client = AsyncMock()
        mock_deps.return_value.obsidian_http_client = AsyncMock()
        service = AgentService()
    return service


@pytest.mark.asyncio
async def test_chat_success():
    service = _create_service()
    request = ChatCompletionRequest(messages=[ChatMessage(role="user", content="Hello")])

    with agent.override(model=TestModel()):
        with patch("app.core.agents.service.logger"):
            response = await service.chat(request)

    assert response.object == "chat.completion"
    assert len(response.choices) == 1
    assert response.choices[0].message.role == "assistant"
    assert response.choices[0].message.content != ""


@pytest.mark.asyncio
async def test_chat_extracts_last_user_message():
    service = _create_service()
    request = ChatCompletionRequest(
        messages=[
            ChatMessage(role="system", content="You are helpful."),
            ChatMessage(role="user", content="First question"),
            ChatMessage(role="assistant", content="First answer"),
            ChatMessage(role="user", content="Second question"),
        ]
    )

    with agent.override(model=TestModel()):
        with patch("app.core.agents.service.logger"):
            response = await service.chat(request)

    assert response.object == "chat.completion"
    assert len(response.choices) == 1


@pytest.mark.asyncio
async def test_chat_failure_raises_agent_execution_error():
    service = _create_service()
    request = ChatCompletionRequest(messages=[ChatMessage(role="user", content="Hello")])

    with patch("app.core.agents.service.agent") as mock_agent:
        mock_agent.run.side_effect = RuntimeError("LLM connection failed")
        with patch("app.core.agents.service.logger"):
            with pytest.raises(AgentExecutionError, match="Agent execution failed"):
                await service.chat(request)


@pytest.mark.asyncio
async def test_rag_router_skips_for_transit_query():
    service = _create_service()
    request = ChatCompletionRequest(
        messages=[ChatMessage(role="user", content="Which routes are delayed?")]
    )

    with agent.override(model=TestModel()):
        with patch("app.core.agents.service.logger"):
            with patch(
                "app.core.agents.service.needs_rag",
                return_value=RoutingDecision(needs_rag=False, rag_score=0, skip_score=3),
            ):
                await service.chat(request)

    assert service._deps.rag_enabled is False


@pytest.mark.asyncio
async def test_rag_router_enables_for_knowledge_query():
    service = _create_service()
    request = ChatCompletionRequest(
        messages=[ChatMessage(role="user", content="What is the overtime policy?")]
    )

    with agent.override(model=TestModel()):
        with patch("app.core.agents.service.logger"):
            with patch(
                "app.core.agents.service.needs_rag",
                return_value=RoutingDecision(needs_rag=True, rag_score=2, skip_score=0),
            ):
                await service.chat(request)

    assert service._deps.rag_enabled is True


@pytest.mark.asyncio
async def test_rag_router_disabled_by_config():
    service = _create_service()
    request = ChatCompletionRequest(
        messages=[ChatMessage(role="user", content="What is the overtime policy?")]
    )

    with agent.override(model=TestModel()):
        with patch("app.core.agents.service.logger"):
            with patch("app.core.agents.service.get_settings") as mock_settings:
                mock_settings.return_value.knowledge_router_enabled = False
                mock_settings.return_value.llm_provider = "test"
                mock_settings.return_value.llm_model = "test-model"
                with patch("app.core.agents.service.needs_rag") as mock_needs_rag:
                    await service.chat(request)
                    mock_needs_rag.assert_not_called()

    assert service._deps.rag_enabled is True


# --- Memory recall injection tests ---


def _make_recall_responses(count: int = 2) -> list[MemoryRecallResponse]:
    """Create mock MemoryRecallResponse objects for testing."""
    from app.shared.models import utcnow

    now = utcnow()
    responses: list[MemoryRecallResponse] = []
    for i in range(count):
        entry = MemoryEntryResponse(
            id=i + 1,
            agent_type="transit",
            memory_type="semantic",
            content=f"Memory content {i + 1}",
            metadata_json=None,
            decay_weight=1.0,
            is_evergreen=False,
            source="agent",
            recalled_count=i,
            created_at=now,
            updated_at=now,
        )
        score = 0.9 - (i * 0.4)
        responses.append(MemoryRecallResponse(memory=entry, score=score))
    return responses


@pytest.mark.asyncio
async def test_chat_injects_recalled_memories() -> None:
    service = _create_service()
    request = ChatCompletionRequest(messages=[ChatMessage(role="user", content="Hello")])
    recalled = _make_recall_responses(2)

    mock_memory_svc = AsyncMock()
    mock_memory_svc.recall_by_query.return_value = recalled

    with agent.override(model=TestModel()):
        with patch("app.core.agents.service.logger"):
            with patch("app.core.agents.service.MemoryService", return_value=mock_memory_svc):
                with patch("app.core.agents.service.build_instructions_with_skills") as mock_build:
                    mock_build.return_value = "instructions"
                    await service.chat(request)

    # Verify build_instructions_with_skills called with non-empty memory_context
    _ = mock_build
    call_args = mock_build.call_args
    assert call_args is not None
    memory_ctx = (
        call_args.args[1] if len(call_args.args) > 1 else call_args.kwargs.get("memory_context", "")
    )
    assert "RELEVANT MEMORIES" in memory_ctx
    assert "[0.90]" in memory_ctx
    assert "[0.50]" in memory_ctx


@pytest.mark.asyncio
async def test_chat_skips_memory_when_disabled() -> None:
    service = _create_service()
    request = ChatCompletionRequest(messages=[ChatMessage(role="user", content="Hello")])

    with agent.override(model=TestModel()):
        with patch("app.core.agents.service.logger"):
            with patch("app.core.agents.service.get_settings") as mock_settings:
                settings_obj = MagicMock()
                settings_obj.memory_enabled = False
                settings_obj.knowledge_router_enabled = False
                settings_obj.llm_provider = "test"
                settings_obj.llm_model = "test-model"
                mock_settings.return_value = settings_obj
                with patch("app.core.agents.service.MemoryService") as mock_mem_cls:
                    await service.chat(request)
                    mock_mem_cls.assert_not_called()


@pytest.mark.asyncio
async def test_chat_continues_on_memory_recall_failure() -> None:
    service = _create_service()
    request = ChatCompletionRequest(messages=[ChatMessage(role="user", content="Hello")])

    mock_memory_svc = AsyncMock()
    mock_memory_svc.recall_by_query.side_effect = RuntimeError("Embedding failed")

    with agent.override(model=TestModel()):
        with patch("app.core.agents.service.logger") as mock_logger:
            with patch("app.core.agents.service.MemoryService", return_value=mock_memory_svc):
                response = await service.chat(request)

    # Agent should still return a response (graceful degradation)
    assert response.object == "chat.completion"
    assert len(response.choices) == 1
    mock_logger.warning.assert_any_call("agent.memory.recall_failed", exc_info=True)


@pytest.mark.asyncio
async def test_chat_memory_context_format() -> None:
    service = _create_service()
    request = ChatCompletionRequest(messages=[ChatMessage(role="user", content="Hello")])
    recalled = _make_recall_responses(1)

    mock_memory_svc = AsyncMock()
    mock_memory_svc.recall_by_query.return_value = recalled

    with agent.override(model=TestModel()):
        with patch("app.core.agents.service.logger"):
            with patch("app.core.agents.service.MemoryService", return_value=mock_memory_svc):
                with patch("app.core.agents.service.build_instructions_with_skills") as mock_build:
                    mock_build.return_value = "instructions"
                    await service.chat(request)

    _ = mock_build
    call_args = mock_build.call_args
    assert call_args is not None
    memory_ctx = (
        call_args.args[1] if len(call_args.args) > 1 else call_args.kwargs.get("memory_context", "")
    )
    assert memory_ctx.startswith("RELEVANT MEMORIES")
    assert "- [0.90]" in memory_ctx


@pytest.mark.asyncio
async def test_chat_respects_min_score_setting() -> None:
    service = _create_service()
    request = ChatCompletionRequest(messages=[ChatMessage(role="user", content="Hello")])

    mock_memory_svc = AsyncMock()
    mock_memory_svc.recall_by_query.return_value = []

    with agent.override(model=TestModel()):
        with patch("app.core.agents.service.logger"):
            with patch("app.core.agents.service.get_settings") as mock_settings:
                settings_obj = MagicMock()
                settings_obj.memory_enabled = True
                settings_obj.memory_recall_min_score = 0.5
                settings_obj.memory_max_recall_results = 5
                settings_obj.memory_context_injection_limit = 10
                settings_obj.knowledge_router_enabled = False
                settings_obj.llm_provider = "test"
                settings_obj.llm_model = "test-model"
                mock_settings.return_value = settings_obj
                with patch("app.core.agents.service.MemoryService", return_value=mock_memory_svc):
                    await service.chat(request)

    # Verify recall_by_query was called with min_score=0.5
    call_args = mock_memory_svc.recall_by_query.call_args
    assert call_args is not None
    recall_req = call_args.args[0]
    assert recall_req.min_score == 0.5
