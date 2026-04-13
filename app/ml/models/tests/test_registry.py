# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportMissingTypeStubs=false, reportMissingParameterType=false, reportUnknownParameterType=false
"""Tests for model registry (ML-2.2)."""

from __future__ import annotations

import json

import pytest

from app.ml.features.eta_features import ETAFeatures
from app.ml.features.tests.conftest import make_eta_features_dict
from app.ml.models.schemas import ModelMetadata, TrainingMetrics


def _make_metadata(version: int = 1, feature_version: str = "ml-2.1-v1") -> ModelMetadata:
    """Create test metadata."""
    return ModelMetadata(
        version=version,
        model_name="eta_gbm",
        trained_at="2026-04-13T00:00:00+00:00",
        training_window_days=60,
        training_rows=200,
        feature_version=feature_version,
        metrics=TrainingMetrics(mae=50.0, rmse=70.0, p90_error=120.0, per_route_mae={"3": 45.0}),
    )


class TestModelRegistry:
    def test_register_model(self, tmp_registry, trained_model, tmp_model_path):
        """register() persists metadata to JSON."""
        trained_model.save(tmp_model_path)
        metadata = _make_metadata()
        tmp_registry.register("eta_gbm", 1, metadata, tmp_model_path)

        # Verify persisted
        data = json.loads(tmp_registry._path.read_text())
        assert "1" in data["models"]["eta_gbm"]["versions"]
        assert data["models"]["eta_gbm"]["versions"]["1"]["metrics"]["mae"] == 50.0

    def test_load_latest(self, registered_model):
        """load_latest() returns most recent version."""
        registry, expected_model, _, _ = registered_model
        loaded_model, metadata = registry.load_latest("eta_gbm")
        assert metadata.version == 1
        assert metadata.model_name == "eta_gbm"
        # Verify the loaded model produces same predictions
        features = ETAFeatures(**make_eta_features_dict())
        assert loaded_model.predict(features) == expected_model.predict(features)

    def test_load_latest_nonexistent(self, tmp_registry):
        """load_latest() for unknown model raises KeyError."""
        with pytest.raises(KeyError, match="No model registered"):
            tmp_registry.load_latest("nonexistent")

    def test_promote(self, registered_model):
        """promote() sets production pointer."""
        registry, _, _, _ = registered_model
        registry.promote("eta_gbm", 1)
        data = json.loads(registry._path.read_text())
        assert data["models"]["eta_gbm"]["production"] == 1

    def test_get_production(self, registered_model):
        """get_production() returns promoted model."""
        registry, expected_model, _, _ = registered_model
        registry.promote("eta_gbm", 1)
        result = registry.get_production("eta_gbm")
        assert result is not None
        loaded_model, metadata = result
        assert metadata.version == 1
        features = ETAFeatures(**make_eta_features_dict())
        assert loaded_model.predict(features) == expected_model.predict(features)

    def test_get_production_none(self, tmp_registry):
        """get_production() returns None when no production version."""
        assert tmp_registry.get_production("eta_gbm") is None

    def test_rollback(self, registered_model):
        """rollback() removes production pointer."""
        registry, _, _, _ = registered_model
        registry.promote("eta_gbm", 1)
        registry.rollback("eta_gbm")
        data = json.loads(registry._path.read_text())
        assert "production" not in data["models"]["eta_gbm"]

    def test_rollback_nonexistent(self, tmp_registry):
        """rollback() for unknown model raises KeyError."""
        with pytest.raises(KeyError, match="No model registered"):
            tmp_registry.rollback("nonexistent")

    def test_multiple_versions(self, tmp_registry, trained_model, tmp_path):
        """Registry tracks multiple versions independently."""
        for v in range(1, 4):
            path = tmp_path / f"model_v{v}.pkl"
            trained_model.save(path)
            metadata = _make_metadata(version=v)
            tmp_registry.register("eta_gbm", v, metadata, path)

        _model, metadata = tmp_registry.load_latest("eta_gbm")
        assert metadata.version == 3

    def test_next_version(self, tmp_registry, trained_model, tmp_model_path):
        """next_version() returns correct next integer."""
        assert tmp_registry.next_version("eta_gbm") == 1

        trained_model.save(tmp_model_path)
        tmp_registry.register("eta_gbm", 1, _make_metadata(), tmp_model_path)
        assert tmp_registry.next_version("eta_gbm") == 2

    def test_promote_nonexistent_version(self, registered_model):
        """promote() raises KeyError for non-existent version."""
        registry, _, _, _ = registered_model
        with pytest.raises(KeyError, match="Version 99 not found"):
            registry.promote("eta_gbm", 99)

    def test_atomic_write(self, tmp_registry, trained_model, tmp_model_path):
        """Registry file is valid JSON after write."""
        trained_model.save(tmp_model_path)
        tmp_registry.register("eta_gbm", 1, _make_metadata(), tmp_model_path)
        # Should parse without error
        data = json.loads(tmp_registry._path.read_text())
        assert "models" in data

    def test_feature_version_mismatch_loads_successfully(
        self, tmp_registry, trained_model, tmp_model_path
    ):
        """Loading model with different feature_version still succeeds."""
        trained_model.save(tmp_model_path)
        metadata = _make_metadata(feature_version="ml-2.1-v999")
        tmp_registry.register("eta_gbm", 1, metadata, tmp_model_path)
        tmp_registry._cache.clear()  # Force reload from disk
        _model, _meta = tmp_registry.load_latest("eta_gbm")
        assert _meta.feature_version == "ml-2.1-v999"
