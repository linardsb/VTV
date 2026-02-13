"""Tests for agent service layer."""

from unittest.mock import patch

import pytest
from pydantic_ai import models
from pydantic_ai.models.test import TestModel

from app.core.agents.agent import agent
from app.core.agents.exceptions import AgentExecutionError
from app.core.agents.schemas import ChatCompletionRequest, ChatMessage
from app.core.agents.service import AgentService

# Prevent accidental real LLM API calls during testing
models.ALLOW_MODEL_REQUESTS = False


@pytest.mark.asyncio
async def test_chat_success():
    service = AgentService()
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
    service = AgentService()
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
    service = AgentService()
    request = ChatCompletionRequest(messages=[ChatMessage(role="user", content="Hello")])

    with patch("app.core.agents.service.agent") as mock_agent:
        mock_agent.run.side_effect = RuntimeError("LLM connection failed")
        with patch("app.core.agents.service.logger"):
            with pytest.raises(AgentExecutionError, match="Agent execution failed"):
                await service.chat(request)
