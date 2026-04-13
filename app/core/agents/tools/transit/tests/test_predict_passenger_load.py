# pyright: reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Tests for predict_passenger_load agent tool (ML-3.3)."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import structlog.testing

from app.core.agents.tools.transit.predict_passenger_load import predict_passenger_load
from app.core.config import get_settings


def _make_ctx(db_session_factory: Any = None) -> MagicMock:
    """Create a mock RunContext[UnifiedDeps]."""
    ctx = MagicMock()
    ctx.deps.settings = get_settings()
    ctx.deps.db_session_factory = db_session_factory
    return ctx


def _make_load_result(fallback: bool = False) -> dict[str, Any]:
    """Create a sample load prediction result."""
    return {
        "vehicle_id": "4521",
        "stop_id": "a0072",
        "predicted_passenger_count": None if fallback else 45,
        "confidence_lower": None if fallback else 30,
        "confidence_upper": None if fallback else 60,
        "crowding_bucket": None if fallback else "moderate",
        "load_factor_pct": None,
        "model_version": None if fallback else "1",
        "fallback": fallback,
    }


class TestPredictPassengerLoad:
    @pytest.mark.asyncio
    @patch("app.core.agents.tools.transit.predict_passenger_load.get_load_service")
    async def test_predict_load_returns_json(self, mock_get_service: MagicMock) -> None:
        """Tool returns valid JSON with prediction fields."""
        mock_service = MagicMock()
        mock_service.predict = AsyncMock(return_value=_make_load_result())
        mock_get_service.return_value = mock_service

        mock_db = AsyncMock()
        mock_factory = MagicMock()
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        ctx = _make_ctx(db_session_factory=mock_factory)
        result = await predict_passenger_load(ctx, "4521", "a0072")

        parsed = json.loads(result)
        assert parsed["vehicle_id"] == "4521"
        assert parsed["crowding_bucket"] == "moderate"
        assert parsed["predicted_passenger_count"] == 45
        assert parsed["fallback"] is False

    @pytest.mark.asyncio
    @patch("app.core.agents.tools.transit.predict_passenger_load.get_load_service")
    async def test_predict_load_fallback_in_response(self, mock_get_service: MagicMock) -> None:
        """When model fails, tool returns JSON with fallback=true."""
        mock_service = MagicMock()
        mock_service.predict = AsyncMock(return_value=_make_load_result(fallback=True))
        mock_get_service.return_value = mock_service

        mock_db = AsyncMock()
        mock_factory = MagicMock()
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        ctx = _make_ctx(db_session_factory=mock_factory)
        result = await predict_passenger_load(ctx, "4521", "a0072")

        parsed = json.loads(result)
        assert parsed["fallback"] is True
        assert parsed["crowding_bucket"] is None

    @pytest.mark.asyncio
    @patch("app.core.agents.tools.transit.predict_passenger_load.get_load_service")
    async def test_predict_load_logs_started_completed(self, mock_get_service: MagicMock) -> None:
        """Structured log events are emitted for started and completed."""
        mock_service = MagicMock()
        mock_service.predict = AsyncMock(return_value=_make_load_result())
        mock_get_service.return_value = mock_service

        mock_db = AsyncMock()
        mock_factory = MagicMock()
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        ctx = _make_ctx(db_session_factory=mock_factory)

        with structlog.testing.capture_logs() as cap_logs:
            await predict_passenger_load(ctx, "4521", "a0072")

        events = [log["event"] for log in cap_logs]
        assert "agent.predict_passenger_load.started" in events
        assert "agent.predict_passenger_load.completed" in events

    @pytest.mark.asyncio
    @patch("app.core.agents.tools.transit.predict_passenger_load.get_load_service")
    async def test_predict_load_handles_service_error(self, mock_get_service: MagicMock) -> None:
        """Service error returns an error string, not an exception."""
        mock_service = MagicMock()
        mock_service.predict = AsyncMock(side_effect=RuntimeError("Connection refused"))
        mock_get_service.return_value = mock_service

        mock_db = AsyncMock()
        mock_factory = MagicMock()
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        ctx = _make_ctx(db_session_factory=mock_factory)
        result = await predict_passenger_load(ctx, "4521", "a0072")

        assert isinstance(result, str)
        assert "error" in result.lower() or "Error" in result

    @pytest.mark.asyncio
    async def test_predict_load_missing_db_session_factory(self) -> None:
        """When db_session_factory is None, returns graceful error."""
        ctx = _make_ctx(db_session_factory=None)
        result = await predict_passenger_load(ctx, "4521", "a0072")

        assert isinstance(result, str)
        assert "database" in result.lower()
