"""OpenAI-compatible request/response schemas for the agent API.

These schemas follow the OpenAI Chat Completions API format, making
the VTV agent compatible with any OpenAI client library.
"""

import datetime
import time
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


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

    messages: list[ChatMessage] = Field(min_length=1, max_length=20)
    model: str | None = None

    @field_validator("messages")
    @classmethod
    def validate_message_content_length(
        cls,
        v: list[ChatMessage],
    ) -> list[ChatMessage]:
        """Reject messages with content exceeding 4000 characters."""
        max_content_length = 4000
        for msg in v:
            if len(msg.content) > max_content_length:
                msg_text = f"Message content exceeds {max_content_length} characters"
                raise ValueError(msg_text)
        return v


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


# --- AI-5.3: Self-correction metrics ---


class CorrectionCheckSnapshot(BaseModel):
    """Per-check correction counters for the current UTC day.

    Attributes:
        check_name: Validator check identifier (e.g. ``route_existence``).
        triggered: Correction events whose initial failure set included
            this check.
        resolved: Of the triggered set, how many ended cleanly.
        exhausted: Of the triggered set, how many ran out of retries.
        success_rate: ``resolved / (resolved + exhausted)`` or 0.0 if
            no completed events yet.
        avg_latency_ms: Mean wall-clock latency for completed events
            involving this check, or 0.0 if none.
    """

    model_config = ConfigDict(strict=True)

    check_name: str
    triggered: int
    resolved: int
    exhausted: int
    success_rate: float
    avg_latency_ms: float


class CorrectionTotals(BaseModel):
    """Aggregate counters across all check names."""

    model_config = ConfigDict(strict=True)

    triggered: int
    resolved: int
    exhausted: int
    success_rate: float
    avg_latency_ms: float


class CorrectionMetricsResponse(BaseModel):
    """Response for ``GET /v1/chat/metrics``.

    Attributes:
        period_start: UTC midnight at which the current daily window began.
        generated_at: When this snapshot was rendered.
        checks: Per-check breakdown.
        totals: Aggregate across all checks.
    """

    model_config = ConfigDict(strict=True)

    period_start: datetime.datetime
    generated_at: datetime.datetime
    checks: list[CorrectionCheckSnapshot]
    totals: CorrectionTotals
