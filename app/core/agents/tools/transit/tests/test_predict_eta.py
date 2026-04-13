# pyright: reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Tests for predict_eta agent tool (ML-2.3)."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import structlog.testing

from app.core.agents.tools.transit.predict_eta import predict_eta
from app.core.config import get_settings


def _make_ctx(db_session_factory: Any = None) -> MagicMock:
    """Create a mock RunContext[UnifiedDeps]."""
    ctx = MagicMock()
    ctx.deps.settings = get_settings()
    ctx.deps.db_session_factory = db_session_factory
    return ctx


def _make_eta_result(fallback: bool = False) -> dict[str, Any]:
    """Create a sample ETA prediction result."""
    return {
        "vehicle_id": "4521",
        "stop_id": "a0072",
        "predicted_arrival_at": "08:35:00",
        "delay_s": 120,
        "confidence_lower_s": 60,
        "confidence_upper_s": 200,
        "scheduled_arrival_at": "08:30:00",
        "model_version": None if fallback else "1",
        "fallback": fallback,
        "source": "fallback" if fallback else "model",
    }


class TestPredictEta:
    @pytest.mark.asyncio
    @patch("app.core.agents.tools.transit.predict_eta.get_eta_service")
    async def test_predict_eta_returns_json(self, mock_get_service: MagicMock) -> None:
        """Tool returns valid JSON with prediction fields."""
        mock_service = MagicMock()
        mock_service.predict = AsyncMock(return_value=_make_eta_result())
        mock_get_service.return_value = mock_service

        mock_db = AsyncMock()
        mock_factory = MagicMock()
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        ctx = _make_ctx(db_session_factory=mock_factory)
        result = await predict_eta(ctx, "4521", "a0072")

        parsed = json.loads(result)
        assert parsed["vehicle_id"] == "4521"
        assert parsed["delay_s"] == 120
        assert parsed["fallback"] is False

    @pytest.mark.asyncio
    @patch("app.core.agents.tools.transit.predict_eta.get_eta_service")
    async def test_predict_eta_fallback_in_response(self, mock_get_service: MagicMock) -> None:
        """When model fails, tool returns JSON with fallback=true."""
        mock_service = MagicMock()
        mock_service.predict = AsyncMock(return_value=_make_eta_result(fallback=True))
        mock_get_service.return_value = mock_service

        mock_db = AsyncMock()
        mock_factory = MagicMock()
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        ctx = _make_ctx(db_session_factory=mock_factory)
        result = await predict_eta(ctx, "4521", "a0072")

        parsed = json.loads(result)
        assert parsed["fallback"] is True
        assert parsed["source"] == "fallback"

    @pytest.mark.asyncio
    @patch("app.core.agents.tools.transit.predict_eta.get_eta_service")
    async def test_predict_eta_logs_started_completed(self, mock_get_service: MagicMock) -> None:
        """Structured log events are emitted for started and completed."""
        mock_service = MagicMock()
        mock_service.predict = AsyncMock(return_value=_make_eta_result())
        mock_get_service.return_value = mock_service

        mock_db = AsyncMock()
        mock_factory = MagicMock()
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        ctx = _make_ctx(db_session_factory=mock_factory)

        with structlog.testing.capture_logs() as cap_logs:
            await predict_eta(ctx, "4521", "a0072")

        events = [log["event"] for log in cap_logs]
        assert "agent.predict_eta.started" in events
        assert "agent.predict_eta.completed" in events

    @pytest.mark.asyncio
    @patch("app.core.agents.tools.transit.predict_eta.get_eta_service")
    async def test_predict_eta_handles_db_error(self, mock_get_service: MagicMock) -> None:
        """DB failure returns an error string, not an exception."""
        mock_service = MagicMock()
        mock_service.predict = AsyncMock(side_effect=RuntimeError("Connection refused"))
        mock_get_service.return_value = mock_service

        mock_db = AsyncMock()
        mock_factory = MagicMock()
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        ctx = _make_ctx(db_session_factory=mock_factory)
        result = await predict_eta(ctx, "4521", "a0072")

        assert isinstance(result, str)
        assert "error" in result.lower() or "Error" in result

    @pytest.mark.asyncio
    async def test_predict_eta_missing_db_session_factory(self) -> None:
        """When db_session_factory is None, returns graceful error."""
        ctx = _make_ctx(db_session_factory=None)
        result = await predict_eta(ctx, "4521", "a0072")

        assert isinstance(result, str)
        assert "database" in result.lower()
