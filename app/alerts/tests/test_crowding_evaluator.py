# pyright: reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Tests for crowding evaluator background task (ML-3.3)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import structlog.testing

from app.alerts.crowding_evaluator import (
    evaluate_crowding_once,
    start_crowding_evaluator,
    stop_crowding_evaluator,
)
from app.core.config import get_settings
from app.transit.schemas import VehiclePosition, VehiclePositionsResponse


def _make_vehicle(vehicle_id: str = "4521", route_short_name: str = "22") -> VehiclePosition:
    """Create a sample VehiclePosition."""
    return VehiclePosition(
        vehicle_id=vehicle_id,
        route_id="route_22",
        route_short_name=route_short_name,
        route_type=3,
        latitude=56.95,
        longitude=24.10,
        delay_seconds=0,
        current_status="IN_TRANSIT_TO",
        timestamp="2026-04-13T10:00:00Z",
    )


def _make_response(vehicles: list[VehiclePosition] | None = None) -> VehiclePositionsResponse:
    """Create a sample VehiclePositionsResponse."""
    veh = vehicles or []
    return VehiclePositionsResponse(
        count=len(veh),
        vehicles=veh,
        fetched_at="2026-04-13T10:00:00Z",
    )


def _make_prediction(crowding: str = "moderate", fallback: bool = False) -> dict[str, Any]:
    """Create a sample load prediction result."""
    return {
        "vehicle_id": "4521",
        "stop_id": "",
        "predicted_passenger_count": 80 if crowding == "overcrowded" else 40,
        "confidence_lower": 30,
        "confidence_upper": 90,
        "crowding_bucket": crowding if not fallback else None,
        "load_factor_pct": None,
        "model_version": None if fallback else "1",
        "fallback": fallback,
    }


class TestEvaluateCrowdingOnce:
    @pytest.mark.asyncio
    @patch("app.alerts.crowding_evaluator.get_vehicles_from_redis")
    @patch("app.alerts.crowding_evaluator.record_poller_tick")
    async def test_no_vehicles_returns_zero(
        self,
        mock_tick: MagicMock,
        mock_get_vehicles: AsyncMock,
    ) -> None:
        """Empty Redis scan returns 0 alerts."""
        mock_get_vehicles.return_value = _make_response([])
        settings = get_settings()
        count = await evaluate_crowding_once(settings)
        assert count == 0
        mock_tick.assert_called_once_with("crowding_evaluator")

    @pytest.mark.asyncio
    @patch("app.alerts.crowding_evaluator.get_vehicles_from_redis")
    @patch("app.alerts.crowding_evaluator.get_db_context")
    @patch("app.alerts.crowding_evaluator.get_load_service")
    @patch("app.alerts.crowding_evaluator.record_poller_tick")
    async def test_creates_alert_for_overcrowded(
        self,
        mock_tick: MagicMock,
        mock_get_service: MagicMock,
        mock_db_ctx: MagicMock,
        mock_get_vehicles: AsyncMock,
    ) -> None:
        """Overcrowded prediction creates an alert."""
        _ = mock_tick  # injected by @patch
        mock_get_vehicles.return_value = _make_response([_make_vehicle()])

        mock_service = MagicMock()
        mock_service.predict = AsyncMock(return_value=_make_prediction(crowding="overcrowded"))
        mock_get_service.return_value = mock_service

        mock_db = AsyncMock()
        mock_repo = MagicMock()
        mock_repo.find_active_duplicate = AsyncMock(return_value=None)
        mock_repo.create = AsyncMock()

        mock_db_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "app.alerts.crowding_evaluator.AlertInstanceRepository",
            return_value=mock_repo,
        ):
            settings = get_settings()
            count = await evaluate_crowding_once(settings)

        assert count == 1
        mock_repo.create.assert_called_once()
        created_alert = mock_repo.create.call_args[0][0]
        assert created_alert.alert_type == "crowding_prediction"
        assert created_alert.severity == "critical"

    @pytest.mark.asyncio
    @patch("app.alerts.crowding_evaluator.get_vehicles_from_redis")
    @patch("app.alerts.crowding_evaluator.get_db_context")
    @patch("app.alerts.crowding_evaluator.get_load_service")
    @patch("app.alerts.crowding_evaluator.record_poller_tick")
    async def test_deduplicates_alerts(
        self,
        mock_tick: MagicMock,
        mock_get_service: MagicMock,
        mock_db_ctx: MagicMock,
        mock_get_vehicles: AsyncMock,
    ) -> None:
        """Existing active alert prevents duplicate creation."""
        _ = mock_tick  # injected by @patch
        mock_get_vehicles.return_value = _make_response([_make_vehicle()])

        mock_service = MagicMock()
        mock_service.predict = AsyncMock(return_value=_make_prediction(crowding="overcrowded"))
        mock_get_service.return_value = mock_service

        mock_db = AsyncMock()
        mock_repo = MagicMock()
        mock_repo.find_active_duplicate = AsyncMock(return_value=MagicMock())  # existing
        mock_repo.create = AsyncMock()

        mock_db_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "app.alerts.crowding_evaluator.AlertInstanceRepository",
            return_value=mock_repo,
        ):
            settings = get_settings()
            count = await evaluate_crowding_once(settings)

        assert count == 0
        mock_repo.create.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.alerts.crowding_evaluator.get_vehicles_from_redis")
    @patch("app.alerts.crowding_evaluator.get_db_context")
    @patch("app.alerts.crowding_evaluator.get_load_service")
    @patch("app.alerts.crowding_evaluator.record_poller_tick")
    async def test_skips_non_overcrowded(
        self,
        mock_tick: MagicMock,
        mock_get_service: MagicMock,
        mock_db_ctx: MagicMock,
        mock_get_vehicles: AsyncMock,
    ) -> None:
        """Non-overcrowded predictions do not create alerts."""
        _ = mock_tick  # injected by @patch
        mock_get_vehicles.return_value = _make_response([_make_vehicle()])

        mock_service = MagicMock()
        mock_service.predict = AsyncMock(return_value=_make_prediction(crowding="moderate"))
        mock_get_service.return_value = mock_service

        mock_db = AsyncMock()
        mock_db_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "app.alerts.crowding_evaluator.AlertInstanceRepository",
            return_value=MagicMock(),
        ):
            settings = get_settings()
            count = await evaluate_crowding_once(settings)

        assert count == 0

    @pytest.mark.asyncio
    @patch("app.alerts.crowding_evaluator.get_vehicles_from_redis")
    @patch("app.alerts.crowding_evaluator.get_db_context")
    @patch("app.alerts.crowding_evaluator.get_load_service")
    @patch("app.alerts.crowding_evaluator.record_poller_tick")
    async def test_handles_model_unavailable(
        self,
        mock_tick: MagicMock,
        mock_get_service: MagicMock,
        mock_db_ctx: MagicMock,
        mock_get_vehicles: AsyncMock,
    ) -> None:
        """Fallback predictions are skipped (no alerts created)."""
        _ = mock_tick  # injected by @patch
        mock_get_vehicles.return_value = _make_response([_make_vehicle()])

        mock_service = MagicMock()
        mock_service.predict = AsyncMock(return_value=_make_prediction(fallback=True))
        mock_get_service.return_value = mock_service

        mock_db = AsyncMock()
        mock_db_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "app.alerts.crowding_evaluator.AlertInstanceRepository",
            return_value=MagicMock(),
        ):
            settings = get_settings()
            count = await evaluate_crowding_once(settings)

        assert count == 0


class TestLifecycle:
    @pytest.mark.asyncio
    async def test_start_stop_lifecycle(self) -> None:
        """Start and stop create and cancel the background task."""
        import app.alerts.crowding_evaluator as mod

        settings = get_settings()
        await start_crowding_evaluator(settings)
        assert mod._crowding_task is not None

        await stop_crowding_evaluator()
        assert mod._crowding_task is None

    @pytest.mark.asyncio
    async def test_lifecycle_skips_when_disabled(self) -> None:
        """Task is not created when alerts_crowding_enabled is False."""
        import app.alerts.crowding_evaluator as mod

        settings = get_settings()
        original = settings.alerts_crowding_enabled
        try:
            settings.alerts_crowding_enabled = False
            with structlog.testing.capture_logs() as cap_logs:
                await start_crowding_evaluator(settings)
            assert mod._crowding_task is None
            events = [log["event"] for log in cap_logs]
            assert "alerts.crowding_evaluator.lifecycle_skipped" in events
        finally:
            settings.alerts_crowding_enabled = original
            # Ensure cleanup
            await stop_crowding_evaluator()
