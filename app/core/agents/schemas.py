"""OpenAI-compatible request/response schemas for the agent API.

These schemas follow the OpenAI Chat Completions API format, making
the VTV agent compatible with any OpenAI client library.
"""

import time
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ChatMessage(BaseModel):
    """A single message in a chat conversation.

    Attributes:
        role: The role of the message sender.
        content: The text content of the message.
    """

    model_config = ConfigDict(strict=True)

    role: Literal["user", "assistant", "system"]
    content: str


class ChatCompletionRequest(BaseModel):
    """Request body for the chat completions endpoint.

    Attributes:
        messages: List of messages in the conversation (at least one required).
        model: Optional model override (ignored in MVP, uses server config).
    """

    model_config = ConfigDict(strict=True)

    messages: list[ChatMessage] = Field(min_length=1)
    model: str | None = None


class ChatCompletionChoice(BaseModel):
    """A single completion choice in the response.

    Attributes:
        index: The index of this choice in the list.
        message: The assistant's response message.
        finish_reason: Why the completion stopped.
    """

    index: int = 0
    message: ChatMessage
    finish_reason: str = "stop"


class UsageInfo(BaseModel):
    """Token usage information for the completion.

    Attributes:
        prompt_tokens: Tokens used in the prompt.
        completion_tokens: Tokens generated in the response.
        total_tokens: Total tokens used.
    """

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatCompletionResponse(BaseModel):
    """Response from the chat completions endpoint.

    Follows the OpenAI Chat Completions API response format.

    Attributes:
        id: Unique identifier for this completion.
        object: Object type (always "chat.completion").
        created: Unix timestamp when the completion was created.
        model: The model used for the completion.
        choices: List of completion choices.
        usage: Token usage information.
    """

    id: str = Field(default_factory=lambda: f"chatcmpl-{uuid.uuid4().hex[:12]}")
    object: Literal["chat.completion"] = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: list[ChatCompletionChoice]
    usage: UsageInfo = Field(default_factory=UsageInfo)
