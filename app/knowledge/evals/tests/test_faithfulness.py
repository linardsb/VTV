# pyright: reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false
# pyright: reportPrivateUsage=false

"""Tests for FaithfulnessJudge (AI-11.3)."""

from __future__ import annotations

import logging
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.knowledge.evals.faithfulness import (
    FaithfulnessJudge,
    _build_user_prompt,
)
from app.knowledge.evals.tests.conftest import make_search_result


def _make_judgement_output(
    *, grounded: bool = True, accurate: bool = True, complete: bool = True
) -> MagicMock:
    """Build a mock _FaithfulnessJudgement output."""
    output = MagicMock()
    output.grounded = grounded
    output.accurate = accurate
    output.complete = complete
    output.reasoning = "Looks good"
    return output


def _make_agent_run_result(output: Any) -> MagicMock:
    """Build a mock Agent.run() result."""
    result = MagicMock()
    result.output = output
    return result


class TestFaithfulnessJudge:
    """Tests for FaithfulnessJudge."""

    @pytest.mark.anyio
    async def test_judge_returns_pass_when_all_criteria_true(self) -> None:
        """All three criteria True -> passed=True."""
        output = _make_judgement_output(grounded=True, accurate=True, complete=True)
        mock_run = AsyncMock(return_value=_make_agent_run_result(output))

        with patch("app.knowledge.evals.faithfulness.Agent") as mock_agent_cls:
            mock_agent_cls.return_value.run = mock_run
            judge = FaithfulnessJudge(model="test:test-model")

        judge._agent.run = mock_run  # type: ignore[method-assign]
        results = [make_search_result()]
        result = await judge.judge("test question", results, "source text", pair_id=1)

        assert result.passed is True
        assert result.grounded is True
        assert result.accurate is True
        assert result.complete is True
        assert result.error is None

    @pytest.mark.anyio
    async def test_judge_returns_fail_when_any_criterion_false(self) -> None:
        """One criterion False -> passed=False."""
        output = _make_judgement_output(grounded=True, accurate=False, complete=True)
        mock_run = AsyncMock(return_value=_make_agent_run_result(output))

        with patch("app.knowledge.evals.faithfulness.Agent") as mock_agent_cls:
            mock_agent_cls.return_value.run = mock_run
            judge = FaithfulnessJudge(model="test:test-model")

        judge._agent.run = mock_run  # type: ignore[method-assign]
        results = [make_search_result()]
        result = await judge.judge("test question", results, "source text")

        assert result.passed is False
        assert result.accurate is False

    @pytest.mark.anyio
    async def test_judge_fail_open_on_llm_error(self) -> None:
        """LLM error -> FaithfulnessResult(passed=None, error=...)."""
        mock_run = AsyncMock(side_effect=RuntimeError("LLM down"))

        with patch("app.knowledge.evals.faithfulness.Agent") as mock_agent_cls:
            mock_agent_cls.return_value.run = mock_run
            judge = FaithfulnessJudge(model="test:test-model")

        judge._agent.run = mock_run  # type: ignore[method-assign]
        results = [make_search_result()]
        result = await judge.judge("test question", results, "source text")

        assert result.passed is None
        assert result.error is not None
        assert "RuntimeError" in result.error

    @pytest.mark.anyio
    async def test_judge_does_not_log_raw_question_or_content(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Logs must not contain question text or chunk content."""
        output = _make_judgement_output()
        mock_run = AsyncMock(return_value=_make_agent_run_result(output))

        with patch("app.knowledge.evals.faithfulness.Agent") as mock_agent_cls:
            mock_agent_cls.return_value.run = mock_run
            judge = FaithfulnessJudge(model="test:test-model")

        judge._agent.run = mock_run  # type: ignore[method-assign]
        secret_question = "SUPER_SECRET_QUESTION_12345"
        secret_content = "SUPER_SECRET_CONTENT_67890"
        results = [make_search_result(chunk_content=secret_content)]

        with caplog.at_level(logging.DEBUG):
            await judge.judge(secret_question, results, secret_content, pair_id=99)

        log_text = caplog.text
        assert secret_question not in log_text
        assert secret_content not in log_text

    def test_judge_wraps_chunks_in_data_delimiters(self) -> None:
        """User prompt must wrap chunk content in <<<BEGIN>>>/<<<END>>>."""
        results = [make_search_result(chunk_content="test chunk data")]
        prompt = _build_user_prompt("test question", results, "source text")

        assert "<<<BEGIN>>>" in prompt
        assert "<<<END>>>" in prompt
        assert "test chunk data" in prompt
        assert "source text" in prompt

    def test_judge_uses_fast_tier_model(self) -> None:
        """Constructor calls resolve_tier_model('fast')."""
        with (
            patch("app.knowledge.evals.faithfulness.resolve_tier_model") as mock_resolve,
            patch("app.knowledge.evals.faithfulness.Agent"),
        ):
            mock_resolve.return_value = "test:fast-model"
            judge = FaithfulnessJudge()
            _ = judge  # ARG001

        mock_resolve.assert_called_once_with("fast")
