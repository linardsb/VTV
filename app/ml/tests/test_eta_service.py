# pyright: reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Tests for ETAService (ML-2.3)."""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import structlog.testing

from app.core.config import get_settings
from app.ml.eta_service import ETAService, reset_eta_service
from app.ml.models.schemas import ETAPrediction, ModelMetadata, TrainingMetrics


def _make_metadata(version: int = 1) -> ModelMetadata:
    """Create a sample ModelMetadata."""
    return ModelMetadata(
        version=version,
        model_name="eta_gbm",
        trained_at="2026-01-01T00:00:00Z",
        training_window_days=90,
        training_rows=10000,
        feature_version="ml-2.1-v1",
        metrics=TrainingMetrics(mae=30.0, rmse=45.0, p90_error=90.0, per_route_mae={"3": 28.0}),
    )


def _make_prediction() -> ETAPrediction:
    """Create a sample ETAPrediction."""
    return ETAPrediction(
        predicted_delay_s=120.0,
        confidence_lower=60.0,
        confidence_upper=200.0,
    )


def _make_stop_time_entry(stop_id: str, stop_sequence: int) -> Any:
    """Create a mock StopTimeEntry."""
    entry = MagicMock()
    entry.stop_id = stop_id
    entry.stop_sequence = stop_sequence
    entry.arrival_time = "08:30:00"
    entry.departure_time = "08:31:00"
    return entry


@pytest.fixture(autouse=True)
def _reset_singleton() -> None:
    """Reset ETAService singleton between tests."""
    reset_eta_service()


class TestPredict:
    @pytest.mark.asyncio
    @patch("app.ml.eta_service.get_static_store")
    @patch("app.ml.eta_service.extract_features")
    async def test_predict_happy_path(
        self,
        mock_extract: AsyncMock,
        mock_get_static: AsyncMock,
    ) -> None:
        """Full prediction returns correct fields when model and features available."""
        settings = get_settings()
        service = ETAService(settings)

        # Mock model
        mock_model = MagicMock()
        mock_model.predict.return_value = _make_prediction()
        service._model = mock_model
        service._model_version = 1

        # Mock DB session
        db = AsyncMock()
        # vehicle_positions lookup returns trip_id
        trip_result = MagicMock()
        trip_result.first.return_value = ("trip_22_1",)
        # trips PK lookup
        pk_result = MagicMock()
        pk_result.first.return_value = (42,)
        db.execute = AsyncMock(side_effect=[trip_result, pk_result])

        # Mock static store
        mock_static = MagicMock()
        mock_static.trip_stop_times = {
            "trip_22_1": [_make_stop_time_entry("a0072", 5)],
        }
        mock_get_static.return_value = mock_static

        # Mock feature extraction
        mock_features = MagicMock()
        mock_extract.return_value = mock_features

        result = await service.predict(db, "4521", "a0072")

        assert result["vehicle_id"] == "4521"
        assert result["stop_id"] == "a0072"
        assert result["delay_s"] == 120
        assert result["confidence_lower_s"] == 60
        assert result["confidence_upper_s"] == 200
        assert result["fallback"] is False
        assert result["source"] == "model"
        assert result["model_version"] == "1"
        # predicted_arrival_at = scheduled (08:30:00) + 120s delay = 08:32:00
        assert result["predicted_arrival_at"] == "08:32:00"
        assert result["scheduled_arrival_at"] == "08:30:00"

    @pytest.mark.asyncio
    @patch("app.ml.eta_service.get_static_store")
    @patch("app.ml.eta_service.extract_features")
    async def test_predict_returns_confidence_interval(
        self,
        mock_extract: AsyncMock,
        mock_get_static: AsyncMock,
    ) -> None:
        """Confidence interval bounds are correctly mapped from ETAPrediction."""
        settings = get_settings()
        service = ETAService(settings)

        mock_model = MagicMock()
        mock_model.predict.return_value = ETAPrediction(
            predicted_delay_s=90.0,
            confidence_lower=30.0,
            confidence_upper=150.0,
        )
        service._model = mock_model
        service._model_version = 2

        db = AsyncMock()
        trip_result = MagicMock()
        trip_result.first.return_value = ("trip_22_1",)
        pk_result = MagicMock()
        pk_result.first.return_value = (42,)
        db.execute = AsyncMock(side_effect=[trip_result, pk_result])

        mock_static = MagicMock()
        mock_static.trip_stop_times = {
            "trip_22_1": [_make_stop_time_entry("a0072", 3)],
        }
        mock_get_static.return_value = mock_static
        mock_extract.return_value = MagicMock()

        result = await service.predict(db, "4521", "a0072")

        assert result["confidence_lower_s"] == 30
        assert result["confidence_upper_s"] == 150
        assert result["delay_s"] == 90

    @pytest.mark.asyncio
    async def test_fallback_on_model_load_failure(self) -> None:
        """When model cannot be loaded, returns fallback result."""
        settings = get_settings()
        service = ETAService(settings)

        db = AsyncMock()
        trip_result = MagicMock()
        trip_result.first.return_value = ("trip_22_1",)
        pk_result = MagicMock()
        pk_result.first.return_value = (42,)
        db.execute = AsyncMock(side_effect=[trip_result, pk_result])

        with patch("app.ml.eta_service.get_static_store") as mock_static:
            mock_store = MagicMock()
            mock_store.trip_stop_times = {
                "trip_22_1": [_make_stop_time_entry("a0072", 5)],
            }
            mock_static.return_value = mock_store

            # Model not loaded and registry fails
            with patch.object(service, "_registry") as mock_registry:
                mock_registry.get_production.return_value = None
                mock_registry.load_latest.side_effect = KeyError("no model")

                result = await service.predict(db, "4521", "a0072")

        assert result["fallback"] is True
        assert result["source"] == "fallback"
        assert result["model_version"] is None

    @pytest.mark.asyncio
    @patch("app.ml.eta_service.get_static_store")
    @patch("app.ml.eta_service.extract_features")
    async def test_fallback_on_feature_extraction_failure(
        self,
        mock_extract: AsyncMock,
        mock_get_static: AsyncMock,
    ) -> None:
        """When feature extraction raises, returns fallback."""
        settings = get_settings()
        service = ETAService(settings)

        mock_model = MagicMock()
        service._model = mock_model
        service._model_version = 1

        db = AsyncMock()
        trip_result = MagicMock()
        trip_result.first.return_value = ("trip_22_1",)
        pk_result = MagicMock()
        pk_result.first.return_value = (42,)
        db.execute = AsyncMock(side_effect=[trip_result, pk_result])

        mock_static = MagicMock()
        mock_static.trip_stop_times = {
            "trip_22_1": [_make_stop_time_entry("a0072", 5)],
        }
        mock_get_static.return_value = mock_static

        mock_extract.side_effect = RuntimeError("DB query failed")

        result = await service.predict(db, "4521", "a0072")

        assert result["fallback"] is True
        assert result["source"] == "fallback"


class TestHotReload:
    def test_hot_reload_detects_version_change(self) -> None:
        """When registry has a newer version, model is reloaded."""
        settings = get_settings()
        service = ETAService(settings)
        service._model = MagicMock()
        service._model_version = 1
        # Force a check: place the last-check far enough in the past that the
        # reload interval has elapsed regardless of the absolute monotonic clock.
        # (0.0 only works when time.monotonic() already exceeds the interval,
        # which fails on freshly-booted CI runners where monotonic() is small.)
        service._last_reload_check = (
            time.monotonic() - settings.eta_model_reload_interval_seconds - 1
        )

        new_model = MagicMock()
        new_metadata = _make_metadata(version=2)

        with patch.object(service, "_registry") as mock_registry:
            mock_registry.get_production.return_value = (new_model, new_metadata)
            service._maybe_reload()

        assert service._model is new_model
        assert service._model_version == 2

    def test_hot_reload_skips_when_interval_not_elapsed(self) -> None:
        """Reload is skipped if interval hasn't elapsed."""
        settings = get_settings()
        service = ETAService(settings)
        service._model = MagicMock()
        service._model_version = 1
        service._last_reload_check = time.monotonic()  # Just checked

        with patch.object(service, "_registry") as mock_registry:
            service._maybe_reload()
            mock_registry.get_production.assert_not_called()

        assert service._model_version == 1


class TestSingleton:
    def test_get_eta_service_singleton(self) -> None:
        """Same instance returned on repeated calls."""
        from app.ml.eta_service import get_eta_service

        s1 = get_eta_service()
        s2 = get_eta_service()
        assert s1 is s2


class TestLogging:
    @pytest.mark.asyncio
    @patch("app.ml.eta_service.get_static_store")
    @patch("app.ml.eta_service.extract_features")
    async def test_predict_logs_structured_event(
        self,
        mock_extract: AsyncMock,
        mock_get_static: AsyncMock,
    ) -> None:
        """Verify ml.eta_service.prediction_completed is logged."""
        settings = get_settings()
        service = ETAService(settings)

        mock_model = MagicMock()
        mock_model.predict.return_value = _make_prediction()
        service._model = mock_model
        service._model_version = 1

        db = AsyncMock()
        trip_result = MagicMock()
        trip_result.first.return_value = ("trip_22_1",)
        pk_result = MagicMock()
        pk_result.first.return_value = (42,)
        db.execute = AsyncMock(side_effect=[trip_result, pk_result])

        mock_static = MagicMock()
        mock_static.trip_stop_times = {
            "trip_22_1": [_make_stop_time_entry("a0072", 5)],
        }
        mock_get_static.return_value = mock_static
        mock_extract.return_value = MagicMock()

        with structlog.testing.capture_logs() as cap_logs:
            await service.predict(db, "4521", "a0072")

        events = [log["event"] for log in cap_logs]
        assert "ml.eta_service.prediction_completed" in events
