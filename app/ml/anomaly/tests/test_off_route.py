# pyright: reportUnknownMemberType=false, reportMissingTypeStubs=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Tests for the off-route anomaly evaluator (ML-4.1)."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ml.anomaly.off_route import (
    _corridor_cache,
    evaluate_off_route_once,
    start_off_route_evaluator,
    stop_off_route_evaluator,
)
from app.ml.anomaly.tests.conftest import make_vehicle_data


def _make_scan_iter(keys: list[str]) -> MagicMock:
    """Create a mock scan_iter that yields the given keys."""

    async def _iter(pattern: str) -> Any:
        for k in keys:
            yield k

    mock = MagicMock(side_effect=_iter)
    return mock


def _make_settings(**overrides: Any) -> MagicMock:
    """Build a mock Settings with off-route defaults."""
    s = MagicMock()
    s.anomaly_offroute_enabled = overrides.get("enabled", True)
    s.anomaly_offroute_check_interval_seconds = overrides.get("interval", 60)
    s.anomaly_offroute_buffer_meters = overrides.get("buffer_meters", 50)
    s.anomaly_offroute_consecutive_hits = overrides.get("consecutive_hits", 3)
    return s


class TestEvaluateOffRouteOnce:
    """Tests for evaluate_off_route_once()."""

    @pytest.mark.asyncio
    async def test_vehicle_inside_corridor_no_alert(
        self, mock_redis: AsyncMock, mock_db: AsyncMock, mock_db_context: Any
    ) -> None:
        """Vehicle inside corridor should not fire an alert."""
        vehicle_data = make_vehicle_data()
        mock_redis.scan_iter = _make_scan_iter(["vehicle:v1"])
        mock_redis.get = AsyncMock(
            side_effect=lambda k: json.dumps(vehicle_data) if k == "vehicle:v1" else None
        )

        # Corridor exists, vehicle is inside
        corridor_mock = MagicMock()
        containment_result = MagicMock()
        containment_result.scalar.return_value = True
        corridor_result = MagicMock()
        corridor_result.first.return_value = (corridor_mock,)
        mock_db.execute = AsyncMock(side_effect=[corridor_result, containment_result])

        with (
            patch("app.ml.anomaly.off_route.get_redis", return_value=mock_redis),
            patch("app.ml.anomaly.off_route.get_db_context", mock_db_context),
            patch("app.ml.anomaly.off_route.get_settings", return_value=_make_settings()),
            patch("app.ml.anomaly.off_route.record_poller_tick"),
        ):
            _corridor_cache.clear()
            result = await evaluate_off_route_once()

        assert result == 0
        mock_redis.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_vehicle_outside_corridor_increments_count(
        self, mock_redis: AsyncMock, mock_db: AsyncMock, mock_db_context: Any
    ) -> None:
        """Vehicle outside corridor should increment count but not alert below threshold."""
        vehicle_data = make_vehicle_data()
        mock_redis.scan_iter = _make_scan_iter(["vehicle:v1"])
        mock_redis.get = AsyncMock(
            side_effect=lambda k: json.dumps(vehicle_data)
            if k == "vehicle:v1"
            else "1"
            if k == "off_route_state:v1"
            else None
        )

        corridor_mock = MagicMock()
        containment_result = MagicMock()
        containment_result.scalar.return_value = False  # Outside
        corridor_result = MagicMock()
        corridor_result.first.return_value = (corridor_mock,)
        mock_db.execute = AsyncMock(side_effect=[corridor_result, containment_result])

        with (
            patch("app.ml.anomaly.off_route.get_redis", return_value=mock_redis),
            patch("app.ml.anomaly.off_route.get_db_context", mock_db_context),
            patch("app.ml.anomaly.off_route.get_settings", return_value=_make_settings()),
            patch("app.ml.anomaly.off_route.record_poller_tick"),
        ):
            _corridor_cache.clear()
            result = await evaluate_off_route_once()

        assert result == 0
        # Count incremented from 1 to 2, stored back
        mock_redis.set.assert_called_once()
        call_args = mock_redis.set.call_args
        assert call_args[0][1] == "2"

    @pytest.mark.asyncio
    async def test_vehicle_outside_fires_at_threshold(
        self, mock_redis: AsyncMock, mock_db: AsyncMock, mock_db_context: Any
    ) -> None:
        """Vehicle reaching consecutive threshold should fire alert."""
        vehicle_data = make_vehicle_data()
        mock_redis.scan_iter = _make_scan_iter(["vehicle:v1"])
        # Count is already at 2, will become 3 (threshold)
        mock_redis.get = AsyncMock(
            side_effect=lambda k: json.dumps(vehicle_data)
            if k == "vehicle:v1"
            else "2"
            if k == "off_route_state:v1"
            else None
        )

        corridor_mock = MagicMock()
        containment_result = MagicMock()
        containment_result.scalar.return_value = False
        corridor_result = MagicMock()
        corridor_result.first.return_value = (corridor_mock,)

        # Third execute call: dedup query returns no existing alert
        dedup_result = MagicMock()
        dedup_result.scalar_one_or_none.return_value = None

        mock_db.execute = AsyncMock(side_effect=[corridor_result, containment_result, dedup_result])

        mock_alert_repo = AsyncMock()

        with (
            patch("app.ml.anomaly.off_route.get_redis", return_value=mock_redis),
            patch("app.ml.anomaly.off_route.get_db_context", mock_db_context),
            patch("app.ml.anomaly.off_route.get_settings", return_value=_make_settings()),
            patch("app.ml.anomaly.off_route.record_poller_tick"),
            patch(
                "app.ml.anomaly.off_route.AlertInstanceRepository",
                return_value=mock_alert_repo,
            ),
        ):
            _corridor_cache.clear()
            result = await evaluate_off_route_once()

        assert result == 1
        mock_alert_repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_vehicle_returns_to_corridor_resets_count(
        self, mock_redis: AsyncMock, mock_db: AsyncMock, mock_db_context: Any
    ) -> None:
        """Vehicle returning to corridor should reset the consecutive count."""
        vehicle_data = make_vehicle_data()
        mock_redis.scan_iter = _make_scan_iter(["vehicle:v1"])
        mock_redis.get = AsyncMock(
            side_effect=lambda k: json.dumps(vehicle_data)
            if k == "vehicle:v1"
            else "2"
            if k == "off_route_state:v1"
            else None
        )

        corridor_mock = MagicMock()
        containment_result = MagicMock()
        containment_result.scalar.return_value = True  # Back inside
        corridor_result = MagicMock()
        corridor_result.first.return_value = (corridor_mock,)
        mock_db.execute = AsyncMock(side_effect=[corridor_result, containment_result])

        with (
            patch("app.ml.anomaly.off_route.get_redis", return_value=mock_redis),
            patch("app.ml.anomaly.off_route.get_db_context", mock_db_context),
            patch("app.ml.anomaly.off_route.get_settings", return_value=_make_settings()),
            patch("app.ml.anomaly.off_route.record_poller_tick"),
        ):
            _corridor_cache.clear()
            result = await evaluate_off_route_once()

        assert result == 0
        mock_redis.delete.assert_called_once_with("off_route_state:v1")

    @pytest.mark.asyncio
    async def test_no_vehicles_returns_zero(self, mock_redis: AsyncMock) -> None:
        """Empty Redis scan should return 0."""
        mock_redis.scan_iter = _make_scan_iter([])

        with (
            patch("app.ml.anomaly.off_route.get_redis", return_value=mock_redis),
            patch(
                "app.ml.anomaly.off_route.get_settings",
                return_value=_make_settings(),
            ),
        ):
            result = await evaluate_off_route_once()

        assert result == 0

    @pytest.mark.asyncio
    async def test_vehicle_without_route_id_skipped(
        self, mock_redis: AsyncMock, mock_db_context: Any
    ) -> None:
        """Vehicle missing route_id should be skipped."""
        vehicle_data = make_vehicle_data()
        del vehicle_data["route_id"]
        mock_redis.scan_iter = _make_scan_iter(["vehicle:v1"])
        mock_redis.get = AsyncMock(return_value=json.dumps(vehicle_data))

        with (
            patch("app.ml.anomaly.off_route.get_redis", return_value=mock_redis),
            patch("app.ml.anomaly.off_route.get_db_context", mock_db_context),
            patch("app.ml.anomaly.off_route.get_settings", return_value=_make_settings()),
            patch("app.ml.anomaly.off_route.record_poller_tick"),
        ):
            result = await evaluate_off_route_once()

        assert result == 0

    @pytest.mark.asyncio
    async def test_no_shape_data_skips_route(
        self, mock_redis: AsyncMock, mock_db: AsyncMock, mock_db_context: Any
    ) -> None:
        """Route with no shape data should be skipped."""
        vehicle_data = make_vehicle_data()
        mock_redis.scan_iter = _make_scan_iter(["vehicle:v1"])
        mock_redis.get = AsyncMock(
            side_effect=lambda k: json.dumps(vehicle_data) if k == "vehicle:v1" else None
        )

        # Corridor query returns None
        corridor_result = MagicMock()
        corridor_result.first.return_value = None
        mock_db.execute = AsyncMock(return_value=corridor_result)

        with (
            patch("app.ml.anomaly.off_route.get_redis", return_value=mock_redis),
            patch("app.ml.anomaly.off_route.get_db_context", mock_db_context),
            patch("app.ml.anomaly.off_route.get_settings", return_value=_make_settings()),
            patch("app.ml.anomaly.off_route.record_poller_tick"),
        ):
            _corridor_cache.clear()
            result = await evaluate_off_route_once()

        assert result == 0

    @pytest.mark.asyncio
    async def test_alert_deduplication(
        self, mock_redis: AsyncMock, mock_db: AsyncMock, mock_db_context: Any
    ) -> None:
        """Active alert already exists — no duplicate should be created."""
        vehicle_data = make_vehicle_data()
        mock_redis.scan_iter = _make_scan_iter(["vehicle:v1"])
        mock_redis.get = AsyncMock(
            side_effect=lambda k: json.dumps(vehicle_data)
            if k == "vehicle:v1"
            else "2"
            if k == "off_route_state:v1"
            else None
        )

        corridor_mock = MagicMock()
        containment_result = MagicMock()
        containment_result.scalar.return_value = False
        corridor_result = MagicMock()
        corridor_result.first.return_value = (corridor_mock,)

        # Dedup query returns existing alert
        existing_alert = MagicMock()
        dedup_result = MagicMock()
        dedup_result.scalar_one_or_none.return_value = existing_alert

        mock_db.execute = AsyncMock(side_effect=[corridor_result, containment_result, dedup_result])

        mock_alert_repo = AsyncMock()

        with (
            patch("app.ml.anomaly.off_route.get_redis", return_value=mock_redis),
            patch("app.ml.anomaly.off_route.get_db_context", mock_db_context),
            patch("app.ml.anomaly.off_route.get_settings", return_value=_make_settings()),
            patch("app.ml.anomaly.off_route.record_poller_tick"),
            patch(
                "app.ml.anomaly.off_route.AlertInstanceRepository",
                return_value=mock_alert_repo,
            ),
        ):
            _corridor_cache.clear()
            await evaluate_off_route_once()

        # Alert was deduplicated — create not called
        mock_alert_repo.create.assert_not_called()


class TestCorridorCache:
    """Tests for corridor caching behavior."""

    @pytest.mark.asyncio
    async def test_corridor_cached_across_cycles(
        self, mock_redis: AsyncMock, mock_db: AsyncMock, mock_db_context: Any
    ) -> None:
        """Corridor should be queried from DB once, then cached."""
        vehicle_data = make_vehicle_data()
        mock_redis.scan_iter = _make_scan_iter(["vehicle:v1"])
        mock_redis.get = AsyncMock(
            side_effect=lambda k: json.dumps(vehicle_data) if k == "vehicle:v1" else None
        )

        corridor_mock = MagicMock()
        containment_result = MagicMock()
        containment_result.scalar.return_value = True
        corridor_result = MagicMock()
        corridor_result.first.return_value = (corridor_mock,)

        call_count = 0

        async def _execute_side_effect(*args: Any, **kwargs: Any) -> MagicMock:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return corridor_result
            return containment_result

        mock_db.execute = AsyncMock(side_effect=_execute_side_effect)

        with (
            patch("app.ml.anomaly.off_route.get_redis", return_value=mock_redis),
            patch("app.ml.anomaly.off_route.get_db_context", mock_db_context),
            patch("app.ml.anomaly.off_route.get_settings", return_value=_make_settings()),
            patch("app.ml.anomaly.off_route.record_poller_tick"),
        ):
            _corridor_cache.clear()
            await evaluate_off_route_once()

            # Reset DB call count, run again — should use cache
            call_count = 0
            mock_redis.scan_iter = _make_scan_iter(["vehicle:v1"])
            containment_result2 = MagicMock()
            containment_result2.scalar.return_value = True
            mock_db.execute = AsyncMock(return_value=containment_result2)

            await evaluate_off_route_once()

        # Second cycle should only call execute once (containment), not twice (corridor + containment)
        assert mock_db.execute.call_count == 1

    @pytest.mark.asyncio
    async def test_config_buffer_meters_used(
        self, mock_redis: AsyncMock, mock_db: AsyncMock, mock_db_context: Any
    ) -> None:
        """Custom buffer_meters should be passed to corridor query."""
        vehicle_data = make_vehicle_data()
        mock_redis.scan_iter = _make_scan_iter(["vehicle:v1"])
        mock_redis.get = AsyncMock(
            side_effect=lambda k: json.dumps(vehicle_data) if k == "vehicle:v1" else None
        )

        corridor_result = MagicMock()
        corridor_result.first.return_value = None  # No corridor
        mock_db.execute = AsyncMock(return_value=corridor_result)

        with (
            patch("app.ml.anomaly.off_route.get_redis", return_value=mock_redis),
            patch("app.ml.anomaly.off_route.get_db_context", mock_db_context),
            patch(
                "app.ml.anomaly.off_route.get_settings",
                return_value=_make_settings(buffer_meters=100),
            ),
            patch("app.ml.anomaly.off_route.record_poller_tick"),
        ):
            _corridor_cache.clear()
            await evaluate_off_route_once()

        # Verify the buffer_m=100 was passed in the SQL params
        execute_call = mock_db.execute.call_args_list[0]
        params = execute_call[0][1] if len(execute_call[0]) > 1 else execute_call[1].get("params")
        assert params["buffer_m"] == 100


class TestEvaluatorLifecycle:
    """Tests for start/stop lifecycle."""

    @pytest.mark.asyncio
    async def test_start_stop_lifecycle(self) -> None:
        """Evaluator should start a task and stop cleanly."""
        import app.ml.anomaly.off_route as module

        settings = _make_settings()
        original_task = module._evaluator_task

        with patch("app.ml.anomaly.off_route._evaluator_loop", new_callable=AsyncMock) as mock_loop:
            mock_loop.return_value = None
            await start_off_route_evaluator(settings)
            assert module._evaluator_task is not None

            await stop_off_route_evaluator()
            assert module._evaluator_task is None

        module._evaluator_task = original_task

    @pytest.mark.asyncio
    async def test_start_skips_when_disabled(self) -> None:
        """Disabled evaluator should not create a task."""
        import app.ml.anomaly.off_route as module

        settings = _make_settings(enabled=False)
        original_task = module._evaluator_task
        module._evaluator_task = None

        await start_off_route_evaluator(settings)
        assert module._evaluator_task is None

        module._evaluator_task = original_task
