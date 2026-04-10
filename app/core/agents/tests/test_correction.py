"""Unit tests for the AI-5.1/AI-5.2 self-correction loop."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.agents.correction import (
    CorrectedResult,
    SelfCorrectionLoop,
    _retryable_issues,
)
from app.core.agents.validation import Issue, ValidationResult


def _fake_run_result(output: str) -> MagicMock:
    """Build a MagicMock matching pydantic_ai.RunResult shape."""
    mock = MagicMock()
    mock.output = output
    mock.all_messages = lambda: []
    return mock


def _fake_agent(*outputs: str) -> MagicMock:
    """Build a MagicMock agent whose `run` returns the given outputs in order."""
    agent_mock = MagicMock()
    agent_mock.run = AsyncMock(side_effect=[_fake_run_result(o) for o in outputs])
    return agent_mock


@pytest.mark.asyncio
async def test_clean_first_attempt_no_retry() -> None:
    """A response with zero warnings should not trigger a retry."""
    loop = SelfCorrectionLoop(max_rounds=1)
    fake_agent = _fake_agent("Take route 5 to the central station.")

    result = await loop.run_with_correction(
        fake_agent,
        "Where is the bus to the airport?",
        deps=MagicMock(),
        message_history=None,
        instructions=None,
        model=None,
    )

    assert result.rounds_used == 1
    assert result.corrected is False
    assert result.warnings == []
    assert fake_agent.run.await_count == 1


@pytest.mark.asyncio
async def test_invalid_route_triggers_one_retry_and_succeeds() -> None:
    """First answer mentions implausible route 9999; retry produces a clean answer."""
    loop = SelfCorrectionLoop(max_rounds=1)
    fake_agent = _fake_agent(
        "Take route 9999 from the central station.",
        "Take route 5 from the central station.",
    )

    result = await loop.run_with_correction(
        fake_agent,
        "Best route to airport?",
        deps=MagicMock(),
        message_history=None,
        instructions=None,
        model=None,
    )

    assert result.rounds_used == 2
    assert result.corrected is True
    assert result.warnings == []
    assert "9999" not in result.output
    assert fake_agent.run.await_count == 2


@pytest.mark.asyncio
async def test_retry_exhausted_returns_final_with_warnings() -> None:
    """Both attempts fail validation; loop returns last response + warnings."""
    loop = SelfCorrectionLoop(max_rounds=1)
    fake_agent = _fake_agent(
        "Take route 9999.",
        "Take route 8888.",
    )

    result = await loop.run_with_correction(
        fake_agent,
        "Best route?",
        deps=MagicMock(),
        message_history=None,
        instructions=None,
        model=None,
    )

    assert result.rounds_used == 2
    assert result.corrected is False
    assert any("8888" in w for w in result.warnings)
    assert fake_agent.run.await_count == 2


@pytest.mark.asyncio
async def test_disabled_loop_zero_rounds_runs_once() -> None:
    """max_rounds=0 means one attempt and no retry, regardless of validation."""
    loop = SelfCorrectionLoop(max_rounds=0)
    fake_agent = _fake_agent("Take route 9999.")

    result = await loop.run_with_correction(
        fake_agent,
        "Test",
        deps=MagicMock(),
        message_history=None,
        instructions=None,
        model=None,
    )

    assert result.rounds_used == 1
    assert result.corrected is False
    assert fake_agent.run.await_count == 1


def test_max_rounds_clamped_to_three() -> None:
    """Constructor clamps max_rounds to 3 to bound token cost."""
    loop = SelfCorrectionLoop(max_rounds=99)
    assert loop._max_rounds == 3


def test_negative_max_rounds_clamped_to_zero() -> None:
    """Constructor clamps negative max_rounds to 0."""
    loop = SelfCorrectionLoop(max_rounds=-5)
    assert loop._max_rounds == 0


@pytest.mark.asyncio
async def test_correction_prompt_includes_failed_response_and_warnings() -> None:
    """The retry prompt must contain the failed response and the warning text."""
    loop = SelfCorrectionLoop(max_rounds=1)
    fake_agent = _fake_agent(
        "Take route 9999 from Centrs.",
        "Take route 5 from Centrs.",
    )

    await loop.run_with_correction(
        fake_agent,
        "Best route?",
        deps=MagicMock(),
        message_history=None,
        instructions=None,
        model=None,
    )

    # Second call's prompt should mention the failed route + a warning.
    second_call_prompt = fake_agent.run.await_args_list[1].args[0]
    assert "9999" in second_call_prompt
    assert "implausible" in second_call_prompt.lower()


@pytest.mark.asyncio
async def test_message_history_preserved_across_retry() -> None:
    """Original message_history is included on the retry call's history."""
    loop = SelfCorrectionLoop(max_rounds=1)
    fake_agent = _fake_agent("Take route 9999.", "Take route 5.")
    sentinel_history: list[Any] = [MagicMock(name="prior_message")]

    await loop.run_with_correction(
        fake_agent,
        "Where?",
        deps=MagicMock(),
        message_history=sentinel_history,
        instructions=None,
        model=None,
    )

    second_call_history = fake_agent.run.await_args_list[1].kwargs["message_history"]
    assert sentinel_history[0] in second_call_history


@pytest.mark.asyncio
async def test_stale_data_warning_does_not_trigger_retry() -> None:
    """Non-retryable warnings (stale cache) should not consume a retry round."""
    loop = SelfCorrectionLoop(max_rounds=1)
    fake_agent = _fake_agent("All buses on time.")

    stale_issue = Issue(
        check_name="stale_data",
        description=(
            "This response may be based on cached data. Live feed was temporarily unavailable."
        ),
        severity="warning",
    )
    with patch(
        "app.core.agents.correction.validate_transit_response",
        return_value=ValidationResult(
            is_valid=False,
            issues=[stale_issue],
            warnings=[stale_issue.description],
            sanitized_response="All buses on time.",
        ),
    ):
        result = await loop.run_with_correction(
            fake_agent,
            "Status?",
            deps=MagicMock(),
            message_history=None,
            instructions=None,
            model=None,
        )

    assert result.rounds_used == 1
    assert result.corrected is False
    assert len(result.warnings) == 1
    assert fake_agent.run.await_count == 1


@pytest.mark.asyncio
async def test_validator_exception_returns_unvalidated_response() -> None:
    """If the validator itself crashes, return the original response cleanly."""
    loop = SelfCorrectionLoop(max_rounds=1)
    fake_agent = _fake_agent("Take route 5.")

    with patch(
        "app.core.agents.correction.validate_transit_response",
        side_effect=RuntimeError("validator boom"),
    ):
        result = await loop.run_with_correction(
            fake_agent,
            "Test",
            deps=MagicMock(),
            message_history=None,
            instructions=None,
            model=None,
        )

    assert result.output == "Take route 5."
    assert result.warnings == []
    assert result.rounds_used == 1


@pytest.mark.asyncio
async def test_logs_correction_triggered_and_resolved() -> None:
    """Verify structured log events fire on retry + success."""
    loop = SelfCorrectionLoop(max_rounds=1)
    fake_agent = _fake_agent("Take route 9999.", "Take route 5.")

    with patch("app.core.agents.correction.logger") as mock_logger:
        await loop.run_with_correction(
            fake_agent,
            "Where?",
            deps=MagicMock(),
            message_history=None,
            instructions=None,
            model=None,
        )

    event_names = [call.args[0] for call in mock_logger.info.call_args_list]
    assert "agent.correction.triggered" in event_names
    assert "agent.correction.resolved" in event_names


@pytest.mark.asyncio
async def test_logs_correction_exhausted_when_retry_fails() -> None:
    """Verify exhaustion warning fires when retry also fails."""
    loop = SelfCorrectionLoop(max_rounds=1)
    fake_agent = _fake_agent("Take route 9999.", "Take route 8888.")

    with patch("app.core.agents.correction.logger") as mock_logger:
        await loop.run_with_correction(
            fake_agent,
            "Where?",
            deps=MagicMock(),
            message_history=None,
            instructions=None,
            model=None,
        )

    warning_event_names = [call.args[0] for call in mock_logger.warning.call_args_list]
    assert "agent.correction.exhausted" in warning_event_names


def test_retryable_issues_filters_warning_severity() -> None:
    """Warning-severity issues should be filtered out from retryable set."""
    issues = [
        Issue(
            check_name="route_plausibility",
            description="Route number 9999 seems implausible (expected 1-999).",
            severity="error",
        ),
        Issue(
            check_name="stale_data",
            description=(
                "This response may be based on cached data. Live feed was temporarily unavailable."
            ),
            severity="warning",
        ),
    ]
    filtered = _retryable_issues(issues)
    assert len(filtered) == 1
    assert filtered[0].check_name == "route_plausibility"


def test_retryable_issues_empty_when_only_warnings() -> None:
    """When only warning-severity issues are present, retryable set is empty."""
    issues = [
        Issue(
            check_name="stale_data",
            description="Stale data.",
            severity="warning",
        )
    ]
    assert _retryable_issues(issues) == []


def test_corrected_result_dataclass_defaults() -> None:
    """CorrectedResult should have sensible defaults."""
    r = CorrectedResult(output="hi")
    assert r.output == "hi"
    assert r.warnings == []
    assert r.issues == []
    assert r.rounds_used == 1
    assert r.corrected is False
    assert r.all_messages == []


# --- AI-5.2: severity-based retry semantics ---


def _validation_result(*issues: Issue) -> ValidationResult:
    """Build a ValidationResult mirroring validate_transit_response output."""
    return ValidationResult(
        is_valid=not issues,
        issues=list(issues),
        warnings=[i.description for i in issues],
        sanitized_response="",
    )


@pytest.mark.asyncio
async def test_error_severity_issue_triggers_retry() -> None:
    """An error-severity issue on first attempt should trigger one retry."""
    loop = SelfCorrectionLoop(max_rounds=1)
    fake_agent = _fake_agent("first answer", "clean answer")

    error_issue = Issue(
        check_name="route_existence",
        description="Route 999 not found in GTFS data.",
        severity="error",
    )
    with patch(
        "app.core.agents.correction.validate_transit_response",
        side_effect=[
            _validation_result(error_issue),
            _validation_result(),
        ],
    ):
        result = await loop.run_with_correction(
            fake_agent,
            "Where?",
            deps=MagicMock(),
            message_history=None,
            instructions=None,
            model=None,
        )

    assert result.rounds_used == 2
    assert result.corrected is True
    assert result.warnings == []
    assert fake_agent.run.await_count == 2


@pytest.mark.asyncio
async def test_warning_severity_issue_does_not_retry() -> None:
    """A warning-only issue should not consume a retry round."""
    loop = SelfCorrectionLoop(max_rounds=1)
    fake_agent = _fake_agent("All buses on time.")

    warn_issue = Issue(
        check_name="stale_data",
        description="GTFS-RT data is 600s old.",
        severity="warning",
    )
    with patch(
        "app.core.agents.correction.validate_transit_response",
        return_value=_validation_result(warn_issue),
    ):
        result = await loop.run_with_correction(
            fake_agent,
            "Status?",
            deps=MagicMock(),
            message_history=None,
            instructions=None,
            model=None,
        )

    assert result.rounds_used == 1
    assert result.corrected is False
    assert len(result.warnings) == 1
    assert "600s" in result.warnings[0]
    assert fake_agent.run.await_count == 1


@pytest.mark.asyncio
async def test_mixed_severity_only_errors_block_first_attempt() -> None:
    """Mixed error+warning on first attempt retries; clean second attempt resolves."""
    loop = SelfCorrectionLoop(max_rounds=1)
    fake_agent = _fake_agent("first", "second")

    error_issue = Issue(
        check_name="route_plausibility",
        description="Route 9999 implausible.",
        severity="error",
    )
    warn_issue = Issue(
        check_name="stale_data",
        description="Stale data.",
        severity="warning",
    )
    with patch(
        "app.core.agents.correction.validate_transit_response",
        side_effect=[
            _validation_result(error_issue, warn_issue),
            _validation_result(),
        ],
    ):
        result = await loop.run_with_correction(
            fake_agent,
            "Where?",
            deps=MagicMock(),
            message_history=None,
            instructions=None,
            model=None,
        )

    assert result.rounds_used == 2
    assert result.corrected is True
    assert fake_agent.run.await_count == 2
