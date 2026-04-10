"""Tests for ``AgentResult`` + confidence re-route gate (AI-6.5)."""

# pyright: reportPrivateUsage=false, reportAttributeAccessIssue=false

from __future__ import annotations

import dataclasses
from typing import Any
from unittest.mock import patch

import pytest
from pydantic_ai import models
from pydantic_ai.messages import ModelMessage

from app.core.agents.agent_result import VALID_DOMAINS, AgentResult
from app.core.agents.base import BaseAgentService, _PipelineOutcome
from app.core.agents.routing import ModelTier
from app.core.agents.schemas import ChatCompletionRequest, ChatMessage

# Prevent accidental real LLM API calls during testing.
models.ALLOW_MODEL_REQUESTS = False


# --- AgentResult dataclass -------------------------------------------------


def test_agent_result_is_frozen() -> None:
    result = AgentResult(
        content="hi",
        confidence=0.9,
        warnings=(),
        tools_used=(),
        domain="unified",
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.content = "other"  # type: ignore[misc]


def test_agent_result_accepts_valid_construction() -> None:
    result = AgentResult(
        content="hi",
        confidence=0.5,
        warnings=("w1", "w2"),
        tools_used=("query_bus_status",),
        domain="transit",
    )
    assert result.content == "hi"
    assert result.confidence == 0.5
    assert result.warnings == ("w1", "w2")
    assert result.tools_used == ("query_bus_status",)
    assert result.domain == "transit"


def test_agent_result_rejects_invalid_domain() -> None:
    with pytest.raises(ValueError, match="domain"):
        AgentResult(
            content="x",
            confidence=0.9,
            warnings=(),
            tools_used=(),
            domain="bogus",
        )


def test_agent_result_rejects_out_of_range_confidence() -> None:
    with pytest.raises(ValueError, match="confidence"):
        AgentResult(
            content="x",
            confidence=1.5,
            warnings=(),
            tools_used=(),
            domain="unified",
        )


def test_agent_result_allows_none_confidence() -> None:
    result = AgentResult(
        content="x",
        confidence=None,
        warnings=(),
        tools_used=(),
        domain="unified",
    )
    assert result.confidence is None


def test_valid_domains_covers_expected_set() -> None:
    assert VALID_DOMAINS == frozenset({"transit", "knowledge", "vault", "unified"})


# --- Re-route integration via BaseAgentService.chat() ----------------------


class _FakeBudgetAgent(BaseAgentService):
    """Minimal agent that returns pre-canned outcomes per call.

    Used to drive ``chat()`` through the confidence re-route gate without
    touching a real LLM.
    """

    agent_name = "transit"

    def __init__(
        self,
        *,
        outcomes: list[_PipelineOutcome],
    ) -> None:
        super().__init__()
        self._outcomes = outcomes
        self.execute_calls: list[dict[str, Any]] = []

    async def _execute(
        self,
        *,
        user_message: str,
        current_prompt: str,
        message_history: list[ModelMessage] | None,
        instructions: str | None,
        tier: ModelTier,
        tier_model: Any,
        static_cache: Any,
    ) -> _PipelineOutcome:
        self.execute_calls.append(
            {
                "user_message": user_message,
                "current_prompt": current_prompt,
                "message_history": message_history,
                "instructions": instructions,
                "tier": tier,
                "tier_model": tier_model,
                "static_cache": static_cache,
            }
        )
        return self._outcomes[len(self.execute_calls) - 1]


def _make_request(text: str = "Hello") -> ChatCompletionRequest:
    return ChatCompletionRequest(messages=[ChatMessage(role="user", content=text)])


@pytest.mark.asyncio
async def test_chat_reroutes_on_low_confidence_and_uses_retry_content() -> None:
    """When confidence < threshold and tier != complex, re-route once."""
    outcomes = [
        _PipelineOutcome(
            response_text="LOW-CONF-ANSWER",
            warnings=[],
            messages=[],
            confidence=0.2,
            tools_used=("t1",),
        ),
        _PipelineOutcome(
            response_text="HIGH-CONF-ANSWER",
            warnings=[],
            messages=[],
            confidence=0.9,
            tools_used=("t1", "t2"),
        ),
    ]
    svc = _FakeBudgetAgent(outcomes=outcomes)

    with (
        patch("app.core.agents.base.logger"),
        patch("app.core.agents.base.resolve_tier_model", return_value="test-complex-model"),
        patch("app.core.agents.base.get_settings") as mock_settings,
    ):
        mock_settings.return_value.agent_confidence_reroute_enabled = True
        mock_settings.return_value.agent_confidence_reroute_threshold = 0.3
        mock_settings.return_value.agent_self_correction_enabled = False
        mock_settings.return_value.llm_provider = "test"
        mock_settings.return_value.llm_model = "x"
        response = await svc.chat(_make_request("delay query"))

    assert response.choices[0].message.content == "HIGH-CONF-ANSWER"
    assert len(svc.execute_calls) == 2
    # Retry ran with tier=complex and the complex model.
    assert svc.execute_calls[1]["tier"] == "complex"
    assert svc.execute_calls[1]["tier_model"] == "test-complex-model"


@pytest.mark.asyncio
async def test_chat_does_not_reroute_when_confidence_none() -> None:
    outcomes = [
        _PipelineOutcome(
            response_text="ONLY-ANSWER",
            warnings=[],
            messages=[],
            confidence=None,
            tools_used=(),
        ),
    ]
    svc = _FakeBudgetAgent(outcomes=outcomes)

    with (
        patch("app.core.agents.base.logger"),
        patch("app.core.agents.base.get_settings") as mock_settings,
    ):
        mock_settings.return_value.agent_confidence_reroute_enabled = True
        mock_settings.return_value.agent_confidence_reroute_threshold = 0.3
        mock_settings.return_value.agent_self_correction_enabled = False
        mock_settings.return_value.llm_provider = "test"
        mock_settings.return_value.llm_model = "x"
        response = await svc.chat(_make_request("q"))

    assert response.choices[0].message.content == "ONLY-ANSWER"
    assert len(svc.execute_calls) == 1


@pytest.mark.asyncio
async def test_chat_does_not_reroute_when_flag_disabled() -> None:
    outcomes = [
        _PipelineOutcome(
            response_text="LOW-ANSWER",
            warnings=[],
            messages=[],
            confidence=0.1,
            tools_used=(),
        ),
    ]
    svc = _FakeBudgetAgent(outcomes=outcomes)

    with (
        patch("app.core.agents.base.logger"),
        patch("app.core.agents.base.get_settings") as mock_settings,
    ):
        mock_settings.return_value.agent_confidence_reroute_enabled = False
        mock_settings.return_value.agent_confidence_reroute_threshold = 0.3
        mock_settings.return_value.agent_self_correction_enabled = False
        mock_settings.return_value.llm_provider = "test"
        mock_settings.return_value.llm_model = "x"
        response = await svc.chat(_make_request("q"))

    assert response.choices[0].message.content == "LOW-ANSWER"
    assert len(svc.execute_calls) == 1


@pytest.mark.asyncio
async def test_chat_reroute_skipped_when_no_complex_model_available() -> None:
    outcomes = [
        _PipelineOutcome(
            response_text="LOW-ANSWER",
            warnings=[],
            messages=[],
            confidence=0.2,
            tools_used=(),
        ),
    ]
    svc = _FakeBudgetAgent(outcomes=outcomes)

    with (
        patch("app.core.agents.base.logger"),
        patch("app.core.agents.base.resolve_tier_model", return_value=None),
        patch("app.core.agents.base.get_settings") as mock_settings,
    ):
        mock_settings.return_value.agent_confidence_reroute_enabled = True
        mock_settings.return_value.agent_confidence_reroute_threshold = 0.3
        mock_settings.return_value.agent_self_correction_enabled = False
        mock_settings.return_value.llm_provider = "test"
        mock_settings.return_value.llm_model = "x"
        response = await svc.chat(_make_request("q"))

    assert response.choices[0].message.content == "LOW-ANSWER"
    assert len(svc.execute_calls) == 1
