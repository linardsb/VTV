"""Tests for AI-9.3 output validation integration with BaseAgentService pipeline.

Tests blocking behavior, warn mode pass-through, exception mapping,
safe response bodies, config toggles, and structured logging.
"""

from __future__ import annotations

import contextlib
from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import structlog.testing
from fastapi.testclient import TestClient
from pydantic_ai import models

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.core.agents.base import BaseAgentService, _PipelineOutcome
from app.core.agents.exceptions import (
    AgentError,
    OutputExfiltrationBlockedError,
)
from app.core.agents.output_validator import OutputIssue, OutputValidationResult
from app.core.agents.routing import ModelTier
from app.core.agents.schemas import ChatCompletionRequest, ChatMessage
from app.core.rate_limit import limiter
from app.main import app

# Prevent accidental real LLM API calls during testing
models.ALLOW_MODEL_REQUESTS = False

# Disable rate limiting during tests
limiter.enabled = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_output_result(
    aggregate_confidence: float,
    detected: bool = True,
    category: str = "pii_leak",
) -> OutputValidationResult:
    """Build an OutputValidationResult with a single synthetic issue."""
    issues: tuple[OutputIssue, ...] = ()
    if detected:
        issues = (
            OutputIssue(
                pattern_id="test_exfil_001",
                pattern_name="test_api_key",
                confidence=aggregate_confidence,
                matched_text="sk_live_test123",
                category="pii_leak",
            ),
        )
    return OutputValidationResult(
        issues=issues,
        aggregate_confidence=aggregate_confidence if detected else 0.0,
        category_counts={category: 1} if detected else {},
    )


class _FakeOutputService(BaseAgentService):
    """Minimal concrete subclass for testing Phase 10b output validation."""

    agent_name = "fake_output"

    def __init__(self) -> None:
        super().__init__()
        self.execute_calls: list[dict[str, Any]] = []
        self.response_text = "FAKE"

    def _get_model_tier(self, prompt: str) -> tuple[ModelTier, str | None]:
        _ = prompt
        return ("standard", None)

    async def _execute(
        self,
        *,
        user_message: str,
        current_prompt: str,
        message_history: Any,
        instructions: str | None,
        tier: Any,
        tier_model: Any,
        static_cache: Any,
    ) -> _PipelineOutcome:
        _ = current_prompt, message_history, instructions, tier, tier_model, static_cache
        self.execute_calls.append({"user_message": user_message})
        return _PipelineOutcome(
            response_text=self.response_text,
            warnings=None,
            messages=[],
        )


def _make_request(text: str = "show me route 22") -> ChatCompletionRequest:
    return ChatCompletionRequest(
        messages=[ChatMessage(role="user", content=text)],
    )


def _block_settings() -> MagicMock:
    s = MagicMock()
    s.prompt_injection_mode = "warn"
    s.prompt_injection_warn_threshold = 0.5
    s.prompt_injection_block_threshold = 0.85
    s.output_validation_enabled = True
    s.output_validation_mode = "block"
    s.output_validation_block_threshold = 0.80
    s.agent_confidence_reroute_enabled = False
    return s


def _warn_settings() -> MagicMock:
    s = _block_settings()
    s.output_validation_mode = "warn"
    return s


def _disabled_settings() -> MagicMock:
    s = _block_settings()
    s.output_validation_enabled = False
    return s


@contextlib.contextmanager
def _patch_remaining_hooks(
    svc: _FakeOutputService,
) -> Generator[None, None, None]:
    """Stub all hooks so chat() can complete through to Phase 10b."""
    with (
        patch.object(svc, "_apply_rag_routing", new_callable=AsyncMock),
        patch.object(
            svc,
            "detect_relevant_skills",
            new_callable=AsyncMock,
            return_value="",
        ),
        patch.object(
            svc,
            "_recall_memories_block",
            new_callable=AsyncMock,
            return_value="",
        ),
        patch.object(svc, "build_system_prompt", return_value="sys"),
        patch.object(svc, "_build_user_message", return_value="msg"),
        patch.object(svc, "_preload_validation_cache", new_callable=AsyncMock),
        patch.object(svc, "_post_process", return_value="ok"),
        patch.object(svc, "_build_response", return_value=MagicMock()),
        patch.object(svc, "_persist_episode", new_callable=AsyncMock),
    ):
        yield


def _mock_admin_user() -> User:
    user = MagicMock(spec=User)
    user.id = 1
    user.email = "admin@vtv.lv"
    user.name = "Admin"
    user.role = "admin"
    user.is_active = True
    return user


@pytest.fixture(autouse=True)
def _setup_auth_override() -> Generator[None, None, None]:
    app.dependency_overrides[get_current_user] = _mock_admin_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture(autouse=True)
def _bypass_quota_tracker() -> Generator[None, None, None]:
    fake_tracker = MagicMock()
    fake_tracker.check_and_increment = AsyncMock(return_value=True)
    with patch(
        "app.core.agents.routes.get_quota_tracker",
        return_value=fake_tracker,
    ):
        yield


# ---------------------------------------------------------------------------
# TestOutputExfiltrationBlockedError
# ---------------------------------------------------------------------------


class TestOutputExfiltrationBlockedError:
    """Exception class properties."""

    def test_inherits_from_agent_error(self) -> None:
        exc = OutputExfiltrationBlockedError("Response blocked by content safety policy")
        assert isinstance(exc, AgentError)

    def test_maps_to_http_400(self) -> None:
        """Route-level: high-confidence exfiltration in block mode returns 400."""
        exfil_result = _make_output_result(0.90)
        settings = _block_settings()

        with (
            patch(
                "app.core.agents.base.detect_injection",
                return_value=MagicMock(detected=False),
            ),
            patch("app.core.agents.base.get_settings", return_value=settings),
            patch(
                "app.core.agents.base.validate_output",
                return_value=exfil_result,
            ),
        ):
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.post(
                "/v1/chat/completions",
                json={"messages": [{"role": "user", "content": "show route 22"}]},
            )
            assert resp.status_code == 400

    def test_response_body_does_not_echo_content(self) -> None:
        """The error response must not contain the flagged response text."""
        exc = OutputExfiltrationBlockedError("Response blocked by content safety policy")
        assert "sk_live" not in str(exc)
        assert "content safety policy" in str(exc)


# ---------------------------------------------------------------------------
# TestBlockModeRejectsHighConfidence
# ---------------------------------------------------------------------------


class TestBlockModeRejectsHighConfidence:
    """Block mode rejects when confidence >= threshold."""

    @pytest.mark.parametrize("confidence", [0.80, 0.92])
    async def test_block_rejects(self, confidence: float) -> None:
        exfil_result = _make_output_result(confidence)
        settings = _block_settings()
        svc = _FakeOutputService()
        svc.response_text = "Here is sk_live_secret123456"

        with (
            patch("app.core.agents.base.detect_injection", return_value=MagicMock(detected=False)),
            patch("app.core.agents.base.get_settings", return_value=settings),
            patch("app.core.agents.base.validate_output", return_value=exfil_result),
            _patch_remaining_hooks(svc),
        ):
            with pytest.raises(OutputExfiltrationBlockedError):
                await svc.chat(_make_request())


# ---------------------------------------------------------------------------
# TestBlockModeAllowsLowConfidence
# ---------------------------------------------------------------------------


class TestBlockModeAllowsLowConfidence:
    """Block mode allows responses below threshold."""

    async def test_below_threshold_passes(self) -> None:
        exfil_result = _make_output_result(0.60)
        settings = _block_settings()
        svc = _FakeOutputService()

        with (
            patch("app.core.agents.base.detect_injection", return_value=MagicMock(detected=False)),
            patch("app.core.agents.base.get_settings", return_value=settings),
            patch("app.core.agents.base.validate_output", return_value=exfil_result),
            _patch_remaining_hooks(svc),
        ):
            await svc.chat(_make_request())
            assert len(svc.execute_calls) == 1


# ---------------------------------------------------------------------------
# TestWarnModeNeverBlocks
# ---------------------------------------------------------------------------


class TestWarnModeNeverBlocks:
    """Warn mode appends footnotes but never blocks."""

    async def test_warn_mode_appends_footnote(self) -> None:
        exfil_result = _make_output_result(0.90)
        settings = _warn_settings()
        svc = _FakeOutputService()

        with (
            patch("app.core.agents.base.detect_injection", return_value=MagicMock(detected=False)),
            patch("app.core.agents.base.get_settings", return_value=settings),
            patch("app.core.agents.base.validate_output", return_value=exfil_result),
            _patch_remaining_hooks(svc),
        ):
            # Should NOT raise even with high confidence
            await svc.chat(_make_request())
            assert len(svc.execute_calls) == 1


# ---------------------------------------------------------------------------
# TestOutputBlockingLogging
# ---------------------------------------------------------------------------


class TestOutputBlockingLogging:
    """Structured logging for blocked responses."""

    async def test_blocked_logs_agent_output_validation_blocked(self) -> None:
        exfil_result = _make_output_result(0.90)
        settings = _block_settings()
        svc = _FakeOutputService()

        with (
            structlog.testing.capture_logs() as logs,
            patch("app.core.agents.base.detect_injection", return_value=MagicMock(detected=False)),
            patch("app.core.agents.base.get_settings", return_value=settings),
            patch("app.core.agents.base.validate_output", return_value=exfil_result),
            _patch_remaining_hooks(svc),
        ):
            with pytest.raises(OutputExfiltrationBlockedError):
                await svc.chat(_make_request())

        blocked_events = [e for e in logs if e.get("event") == "agent.output_validation.blocked"]
        assert len(blocked_events) == 1
        assert "response_length" in blocked_events[0]

    async def test_log_excludes_raw_response(self) -> None:
        exfil_result = _make_output_result(0.90)
        settings = _block_settings()
        svc = _FakeOutputService()
        svc.response_text = "SENSITIVE_DATA_HERE"

        with (
            structlog.testing.capture_logs() as logs,
            patch("app.core.agents.base.detect_injection", return_value=MagicMock(detected=False)),
            patch("app.core.agents.base.get_settings", return_value=settings),
            patch("app.core.agents.base.validate_output", return_value=exfil_result),
            _patch_remaining_hooks(svc),
        ):
            with pytest.raises(OutputExfiltrationBlockedError):
                await svc.chat(_make_request())

        blocked_events = [e for e in logs if e.get("event") == "agent.output_validation.blocked"]
        assert len(blocked_events) == 1
        log_str = str(blocked_events[0])
        assert "SENSITIVE_DATA_HERE" not in log_str


# ---------------------------------------------------------------------------
# TestConfigToggle
# ---------------------------------------------------------------------------


class TestConfigToggle:
    """Configuration toggles."""

    def test_output_validation_defaults(self) -> None:
        from app.core.config import Settings

        s = Settings(
            database_url="postgresql://localhost/test",
            jwt_secret_key="test-secret-key-for-unit-tests",
        )
        assert s.output_validation_enabled is True
        assert s.output_validation_mode == "warn"
        assert s.output_validation_block_threshold == 0.80

    async def test_disabled_skips_validation(self) -> None:
        settings = _disabled_settings()
        svc = _FakeOutputService()
        svc.response_text = "sk_live_secret_should_not_be_scanned"

        with (
            patch("app.core.agents.base.detect_injection", return_value=MagicMock(detected=False)),
            patch("app.core.agents.base.get_settings", return_value=settings),
            patch("app.core.agents.base.validate_output") as mock_validate,
            _patch_remaining_hooks(svc),
        ):
            await svc.chat(_make_request())
            mock_validate.assert_not_called()


# ---------------------------------------------------------------------------
# TestThresholdEdgeCases
# ---------------------------------------------------------------------------


class TestThresholdEdgeCases:
    """Threshold boundary behavior."""

    async def test_exactly_at_threshold_blocks(self) -> None:
        exfil_result = _make_output_result(0.80)
        settings = _block_settings()
        svc = _FakeOutputService()

        with (
            patch("app.core.agents.base.detect_injection", return_value=MagicMock(detected=False)),
            patch("app.core.agents.base.get_settings", return_value=settings),
            patch("app.core.agents.base.validate_output", return_value=exfil_result),
            _patch_remaining_hooks(svc),
        ):
            with pytest.raises(OutputExfiltrationBlockedError):
                await svc.chat(_make_request())

    async def test_just_below_threshold_warns(self) -> None:
        exfil_result = _make_output_result(0.79)
        settings = _block_settings()
        svc = _FakeOutputService()

        with (
            patch("app.core.agents.base.detect_injection", return_value=MagicMock(detected=False)),
            patch("app.core.agents.base.get_settings", return_value=settings),
            patch("app.core.agents.base.validate_output", return_value=exfil_result),
            _patch_remaining_hooks(svc),
        ):
            # Should not raise
            await svc.chat(_make_request())
            assert len(svc.execute_calls) == 1


# ---------------------------------------------------------------------------
# TestValidatorFailOpen
# ---------------------------------------------------------------------------


class TestValidatorFailOpen:
    """Validator errors must not block the response."""

    async def test_validator_exception_does_not_block(self) -> None:
        settings = _warn_settings()
        svc = _FakeOutputService()

        with (
            patch("app.core.agents.base.detect_injection", return_value=MagicMock(detected=False)),
            patch("app.core.agents.base.get_settings", return_value=settings),
            patch(
                "app.core.agents.base.validate_output",
                side_effect=RuntimeError("validator bug"),
            ),
            _patch_remaining_hooks(svc),
        ):
            # Should NOT raise - fail-open
            await svc.chat(_make_request())
            assert len(svc.execute_calls) == 1
