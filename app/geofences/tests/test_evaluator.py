# pyright: reportCallIssue=false, reportUnknownMemberType=false, reportUnknownVariableType=false
"""Unit tests for the geofence evaluator background task."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.geofences.evaluator import (
    evaluate_geofences_once,
    start_geofence_evaluator,
    stop_geofence_evaluator,
)
from app.geofences.models import Geofence


def _make_geofence(
    geofence_id: int = 1,
    name: str = "Test Zone",
    alert_on_enter: bool = True,
    alert_on_exit: bool = True,
    alert_on_dwell: bool = False,
    dwell_threshold_minutes: int | None = None,
    alert_severity: str = "medium",
    zone_type: str = "depot",
) -> MagicMock:
    """Create a mock Geofence model."""
    geo = MagicMock(spec=Geofence)
    geo.id = geofence_id
    geo.name = name
    geo.alert_on_enter = alert_on_enter
    geo.alert_on_exit = alert_on_exit
    geo.alert_on_dwell = alert_on_dwell
    geo.dwell_threshold_minutes = dwell_threshold_minutes
    geo.alert_severity = alert_severity
    geo.zone_type = zone_type
    return geo


class TestEvaluateGeofencesOnce:
    """Tests for evaluate_geofences_once."""

    @pytest.mark.asyncio
    async def test_evaluate_no_vehicles(self) -> None:
        """Return 0 when no vehicles in Redis."""
        mock_redis = AsyncMock()
        mock_redis.scan_iter.return_value = AsyncMock()
        mock_redis.scan_iter.return_value.__aiter__ = AsyncMock(return_value=iter([]))

        with patch("app.geofences.evaluator.get_redis", return_value=mock_redis):
            result = await evaluate_geofences_once()

        assert result == 0

    @pytest.mark.asyncio
    async def test_evaluate_vehicle_enters_geofence(self) -> None:
        """Create enter event when vehicle inside zone with no previous state."""
        mock_redis = AsyncMock()
        vehicle_data = json.dumps({"latitude": 56.95, "longitude": 24.11, "vehicle_id": "V100"})

        # Simulate scan_iter yielding one key
        async def scan_iter_mock(pattern: str) -> AsyncIterator[str]:
            _ = pattern
            for key in ["vehicle:V100"]:
                yield key

        mock_redis.scan_iter = scan_iter_mock
        mock_redis.get = AsyncMock(side_effect=lambda k: vehicle_data if "vehicle:" in k else None)
        mock_redis.set = AsyncMock()

        mock_geofence = _make_geofence()
        mock_db = AsyncMock()
        mock_event_repo = AsyncMock()
        mock_event_repo.create = AsyncMock()
        mock_event_repo.get_open_entry = AsyncMock(return_value=None)
        mock_geofence_repo = AsyncMock()
        mock_geofence_repo.check_containment = AsyncMock(return_value=[mock_geofence])
        mock_alert_repo = AsyncMock()
        mock_alert_repo.find_active_duplicate = AsyncMock(return_value=None)
        mock_alert_repo.create = AsyncMock()

        with (
            patch("app.geofences.evaluator.get_redis", return_value=mock_redis),
            patch(
                "app.geofences.evaluator.get_db_context",
                return_value=AsyncMock(
                    __aenter__=AsyncMock(return_value=mock_db),
                    __aexit__=AsyncMock(return_value=False),
                ),
            ),
            patch("app.geofences.evaluator.GeofenceRepository", return_value=mock_geofence_repo),
            patch("app.geofences.evaluator.GeofenceEventRepository", return_value=mock_event_repo),
            patch("app.geofences.evaluator.AlertInstanceRepository", return_value=mock_alert_repo),
        ):
            result = await evaluate_geofences_once()

        assert result >= 1
        mock_event_repo.create.assert_called()

    @pytest.mark.asyncio
    async def test_evaluate_vehicle_exits_geofence(self) -> None:
        """Create exit event when vehicle was inside but now outside."""
        mock_redis = AsyncMock()
        vehicle_data = json.dumps({"latitude": 57.00, "longitude": 25.00, "vehicle_id": "V200"})

        async def scan_iter_mock(pattern: str) -> AsyncIterator[str]:
            _ = pattern
            for key in ["vehicle:V200"]:
                yield key

        mock_redis.scan_iter = scan_iter_mock
        # First get returns vehicle data, second returns previous geofence state
        mock_redis.get = AsyncMock(
            side_effect=lambda k: vehicle_data
            if "vehicle:" in k
            else json.dumps([1])
            if "geofence_state:" in k
            else None
        )
        mock_redis.set = AsyncMock()

        mock_geofence = _make_geofence()
        mock_db = AsyncMock()
        mock_event_repo = AsyncMock()
        mock_event_repo.create = AsyncMock()
        mock_event_repo.get_open_entry = AsyncMock(return_value=MagicMock())
        mock_event_repo.close_entry = AsyncMock()
        mock_geofence_repo = AsyncMock()
        mock_geofence_repo.check_containment = AsyncMock(return_value=[])
        mock_geofence_repo.get = AsyncMock(return_value=mock_geofence)
        mock_alert_repo = AsyncMock()
        mock_alert_repo.find_active_duplicate = AsyncMock(return_value=None)
        mock_alert_repo.create = AsyncMock()

        with (
            patch("app.geofences.evaluator.get_redis", return_value=mock_redis),
            patch(
                "app.geofences.evaluator.get_db_context",
                return_value=AsyncMock(
                    __aenter__=AsyncMock(return_value=mock_db),
                    __aexit__=AsyncMock(return_value=False),
                ),
            ),
            patch("app.geofences.evaluator.GeofenceRepository", return_value=mock_geofence_repo),
            patch("app.geofences.evaluator.GeofenceEventRepository", return_value=mock_event_repo),
            patch("app.geofences.evaluator.AlertInstanceRepository", return_value=mock_alert_repo),
        ):
            result = await evaluate_geofences_once()

        assert result >= 1
        mock_event_repo.close_entry.assert_called()

    @pytest.mark.asyncio
    async def test_evaluate_no_alert_when_disabled(self) -> None:
        """No alert created when alert_on_enter is False."""
        mock_redis = AsyncMock()
        vehicle_data = json.dumps({"latitude": 56.95, "longitude": 24.11, "vehicle_id": "V300"})

        async def scan_iter_mock(pattern: str) -> AsyncIterator[str]:
            _ = pattern
            for key in ["vehicle:V300"]:
                yield key

        mock_redis.scan_iter = scan_iter_mock
        mock_redis.get = AsyncMock(side_effect=lambda k: vehicle_data if "vehicle:" in k else None)
        mock_redis.set = AsyncMock()

        mock_geofence = _make_geofence(alert_on_enter=False)
        mock_db = AsyncMock()
        mock_event_repo = AsyncMock()
        mock_event_repo.create = AsyncMock()
        mock_geofence_repo = AsyncMock()
        mock_geofence_repo.check_containment = AsyncMock(return_value=[mock_geofence])
        mock_alert_repo = AsyncMock()

        with (
            patch("app.geofences.evaluator.get_redis", return_value=mock_redis),
            patch(
                "app.geofences.evaluator.get_db_context",
                return_value=AsyncMock(
                    __aenter__=AsyncMock(return_value=mock_db),
                    __aexit__=AsyncMock(return_value=False),
                ),
            ),
            patch("app.geofences.evaluator.GeofenceRepository", return_value=mock_geofence_repo),
            patch("app.geofences.evaluator.GeofenceEventRepository", return_value=mock_event_repo),
            patch("app.geofences.evaluator.AlertInstanceRepository", return_value=mock_alert_repo),
        ):
            await evaluate_geofences_once()

        # Alert repo should not have been called to create
        mock_alert_repo.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_evaluate_deduplicates_alerts(self) -> None:
        """No new alert when active duplicate exists."""
        mock_redis = AsyncMock()
        vehicle_data = json.dumps({"latitude": 56.95, "longitude": 24.11, "vehicle_id": "V400"})

        async def scan_iter_mock(pattern: str) -> AsyncIterator[str]:
            _ = pattern
            for key in ["vehicle:V400"]:
                yield key

        mock_redis.scan_iter = scan_iter_mock
        mock_redis.get = AsyncMock(side_effect=lambda k: vehicle_data if "vehicle:" in k else None)
        mock_redis.set = AsyncMock()

        mock_geofence = _make_geofence()
        mock_db = AsyncMock()
        mock_event_repo = AsyncMock()
        mock_event_repo.create = AsyncMock()
        mock_geofence_repo = AsyncMock()
        mock_geofence_repo.check_containment = AsyncMock(return_value=[mock_geofence])
        mock_alert_repo = AsyncMock()
        mock_alert_repo.find_active_duplicate = AsyncMock(return_value=MagicMock())

        with (
            patch("app.geofences.evaluator.get_redis", return_value=mock_redis),
            patch(
                "app.geofences.evaluator.get_db_context",
                return_value=AsyncMock(
                    __aenter__=AsyncMock(return_value=mock_db),
                    __aexit__=AsyncMock(return_value=False),
                ),
            ),
            patch("app.geofences.evaluator.GeofenceRepository", return_value=mock_geofence_repo),
            patch("app.geofences.evaluator.GeofenceEventRepository", return_value=mock_event_repo),
            patch("app.geofences.evaluator.AlertInstanceRepository", return_value=mock_alert_repo),
        ):
            await evaluate_geofences_once()

        mock_alert_repo.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_evaluate_handles_redis_error(self) -> None:
        """Return 0 and log warning when Redis is unavailable."""
        with patch(
            "app.geofences.evaluator.get_redis",
            side_effect=ConnectionError("Redis unavailable"),
        ):
            result = await evaluate_geofences_once()

        assert result == 0


class TestEvaluatorLifecycle:
    """Tests for start/stop lifecycle."""

    @pytest.mark.asyncio
    async def test_start_stop_lifecycle(self) -> None:
        """Evaluator starts and stops cleanly."""
        mock_settings = MagicMock()
        mock_settings.geofence_evaluator_enabled = True
        mock_settings.geofence_check_interval_seconds = 1

        await start_geofence_evaluator(mock_settings)

        # Give it a moment to start
        await asyncio.sleep(0.1)

        await stop_geofence_evaluator()

    @pytest.mark.asyncio
    async def test_start_skips_when_disabled(self) -> None:
        """Evaluator does not start when disabled."""
        mock_settings = MagicMock()
        mock_settings.geofence_evaluator_enabled = False

        await start_geofence_evaluator(mock_settings)
        await stop_geofence_evaluator()
