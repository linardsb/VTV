"""Tests for agent schemas."""

import time

import pytest
from pydantic import ValidationError

from app.core.agents.schemas import (
    ChatCompletionChoice,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    UsageInfo,
)


def test_chat_message_creation():
    msg = ChatMessage(role="user", content="Hello")
    assert msg.role == "user"
    assert msg.content == "Hello"


def test_chat_message_invalid_role():
    with pytest.raises(ValidationError):
        ChatMessage(role="invalid", content="Hello")  # type: ignore[arg-type]


def test_chat_completion_request_requires_messages():
    with pytest.raises(ValidationError):
        ChatCompletionRequest(messages=[])


def test_chat_completion_request_valid():
    msg = ChatMessage(role="user", content="Hello")
    request = ChatCompletionRequest(messages=[msg])
    assert len(request.messages) == 1
    assert request.model is None


def test_chat_completion_request_with_model_override():
    msg = ChatMessage(role="user", content="Hello")
    request = ChatCompletionRequest(messages=[msg], model="gpt-4")
    assert request.model == "gpt-4"


def test_chat_completion_response_structure():
    response = ChatCompletionResponse(
        id="chatcmpl-test123",
        created=int(time.time()),
        model="test:test-model",
        choices=[
            ChatCompletionChoice(
                index=0,
                message=ChatMessage(role="assistant", content="Hi there!"),
                finish_reason="stop",
            )
        ],
        usage=UsageInfo(prompt_tokens=10, completion_tokens=5, total_tokens=15),
    )
    assert response.object == "chat.completion"
    assert response.id == "chatcmpl-test123"
    assert len(response.choices) == 1
    assert response.choices[0].message.role == "assistant"
    assert response.choices[0].message.content == "Hi there!"
    assert response.usage.total_tokens == 15


def test_chat_completion_response_defaults():
    response = ChatCompletionResponse(
        model="test:test-model",
        choices=[
            ChatCompletionChoice(
                message=ChatMessage(role="assistant", content="test"),
            )
        ],
    )
    assert response.id.startswith("chatcmpl-")
    assert response.object == "chat.completion"
    assert response.usage.total_tokens == 0
