# pyright: reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Tests for LoadPredictionService (ML-3.3)."""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import get_settings
from app.ml.load_service import LoadPredictionService, get_load_service, reset_load_service
from app.ml.models.schemas import LoadPrediction, ModelMetadata, TrainingMetrics


def _make_metadata(version: int = 1) -> ModelMetadata:
    """Create a sample ModelMetadata for load model."""
    return ModelMetadata(
        version=version,
        model_name="load_gbm",
        trained_at="2026-01-01T00:00:00Z",
        training_window_days=90,
        training_rows=10000,
        feature_version="ml-3.1-v1",
        metrics=TrainingMetrics(mae=5.0, rmse=8.0, p90_error=15.0, per_route_mae={"22": 4.5}),
    )


def _make_load_prediction() -> LoadPrediction:
    """Create a sample LoadPrediction."""
    return LoadPrediction(
        predicted_passenger_count=45.0,
        confidence_lower=30.0,
        confidence_upper=60.0,
        crowding_bucket="moderate",
    )


@pytest.fixture(autouse=True)
def _reset_singleton() -> None:
    """Reset LoadPredictionService singleton between tests."""
    reset_load_service()


class TestEnsureModelLoaded:
    @patch("app.ml.load_service.ModelRegistry")
    def test_lazy_load_model(self, mock_registry_cls: MagicMock) -> None:
        """First call loads model from registry."""
        mock_registry = MagicMock()
        mock_registry.get_production.return_value = (MagicMock(), _make_metadata())
        mock_registry_cls.return_value = mock_registry

        settings = get_settings()
        service = LoadPredictionService(settings)

        assert service._model is None
        loaded = service._ensure_model_loaded()

        assert loaded is True
        assert service._model is not None
        assert service._model_version == 1

    @patch("app.ml.load_service.ModelRegistry")
    def test_hot_reload_on_version_change(self, mock_registry_cls: MagicMock) -> None:
        """Model reloads when registry version changes."""
        mock_registry = MagicMock()
        mock_model_v1 = MagicMock()
        mock_model_v2 = MagicMock()
        mock_registry.get_production.side_effect = [
            (mock_model_v1, _make_metadata(version=1)),
            (mock_model_v2, _make_metadata(version=2)),
        ]
        mock_registry_cls.return_value = mock_registry

        settings = get_settings()
        service = LoadPredictionService(settings)
        service._ensure_model_loaded()

        assert service._model is mock_model_v1
        assert service._model_version == 1

        # Force reload check by resetting the last check time
        service._last_reload_check = time.monotonic() - 9999
        service._maybe_reload()

        assert service._model is mock_model_v2
        assert service._model_version == 2

    @patch("app.ml.load_service.ModelRegistry")
    def test_fallback_when_model_missing(self, mock_registry_cls: MagicMock) -> None:
        """Returns False when registry has no model."""
        mock_registry = MagicMock()
        mock_registry.get_production.return_value = None
        mock_registry.load_latest.side_effect = KeyError("No versions")
        mock_registry_cls.return_value = mock_registry

        settings = get_settings()
        service = LoadPredictionService(settings)

        loaded = service._ensure_model_loaded()
        assert loaded is False
        assert service._model is None


class TestSingleton:
    def test_singleton_getter(self) -> None:
        """get_load_service() returns same instance, reset clears it."""
        s1 = get_load_service()
        s2 = get_load_service()
        assert s1 is s2

        reset_load_service()
        s3 = get_load_service()
        assert s3 is not s1


class TestPredict:
    @pytest.mark.asyncio
    @patch("app.ml.load_service.get_static_store")
    async def test_predict_returns_expected_fields(
        self,
        mock_get_static: AsyncMock,
    ) -> None:
        """Successful prediction returns all expected fields."""
        settings = get_settings()
        service = LoadPredictionService(settings)

        # Mock model
        mock_model = MagicMock()
        mock_model.predict.return_value = _make_load_prediction()
        service._model = mock_model
        service._model_version = 1

        # Mock DB session
        db = AsyncMock()
        # vehicle_positions lookup returns trip_id
        trip_result = MagicMock()
        trip_result.first.return_value = ("trip_22_1",)
        # route info lookup
        route_result = MagicMock()
        route_result.first.return_value = ("22", 3)
        # capacity lookup
        capacity_result = MagicMock()
        capacity_result.first.return_value = (80,)
        db.execute = AsyncMock(side_effect=[trip_result, route_result, capacity_result])

        # Mock static store with stop_sequence
        mock_entry = MagicMock()
        mock_entry.stop_id = "a0072"
        mock_entry.stop_sequence = 5
        mock_static = MagicMock()
        mock_static.trip_stop_times = {"trip_22_1": [mock_entry]}
        mock_get_static.return_value = mock_static

        result: dict[str, Any] = await service.predict(db, "4521", "a0072")

        assert result["fallback"] is False
        assert result["vehicle_id"] == "4521"
        assert result["stop_id"] == "a0072"
        assert result["crowding_bucket"] == "moderate"
        assert result["predicted_passenger_count"] == 45
        assert result["model_version"] == "1"

    @pytest.mark.asyncio
    async def test_predict_fallback_vehicle_not_tracked(self) -> None:
        """Returns fallback when vehicle has no active trip."""
        settings = get_settings()
        service = LoadPredictionService(settings)

        db = AsyncMock()
        no_trip = MagicMock()
        no_trip.first.return_value = None
        db.execute = AsyncMock(return_value=no_trip)

        result: dict[str, Any] = await service.predict(db, "unknown", "a0072")

        assert result["fallback"] is True
        assert result["crowding_bucket"] is None
