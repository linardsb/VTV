"""Tests for agent service layer."""

from unittest.mock import AsyncMock, patch

import pytest
from pydantic_ai import models
from pydantic_ai.models.test import TestModel

from app.core.agents.agent import agent
from app.core.agents.exceptions import AgentExecutionError
from app.core.agents.schemas import ChatCompletionRequest, ChatMessage
from app.core.agents.service import AgentService
from app.knowledge.router import RoutingDecision

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
