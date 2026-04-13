# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportMissingTypeStubs=false, reportMissingParameterType=false, reportUnknownParameterType=false
"""Test fixtures for ETA GBM model (ML-2.2)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from app.ml.features.tests.conftest import make_eta_features_df
from app.ml.models.eta_gbm import ETAModel, train
from app.ml.registry import ModelRegistry


@pytest.fixture()
def sample_training_df() -> pd.DataFrame:
    """200-row DataFrame with all 18 features + target column."""
    rng = np.random.default_rng(42)
    df = make_eta_features_df(200)
    # Realistic delay distribution: mean ~60s, std ~90s, some negative (early)
    df["actual_arrival_delay_seconds"] = rng.normal(60, 90, size=200)
    return df


@pytest.fixture(scope="session")
def trained_model() -> ETAModel:
    """Pre-trained ETAModel on sample data (session-scoped for speed)."""
    rng = np.random.default_rng(42)
    df = make_eta_features_df(200)
    df["actual_arrival_delay_seconds"] = rng.normal(60, 90, size=200)
    model, _metrics = train(df, n_estimators=10, early_stopping_rounds=5)
    return model


@pytest.fixture()
def tmp_registry(tmp_path: Path) -> ModelRegistry:
    """ModelRegistry pointing at a temp directory."""
    registry_path = tmp_path / "registry.json"
    registry_path.write_text('{"models": {}}')
    return ModelRegistry(registry_path=registry_path)


@pytest.fixture()
def tmp_model_path(tmp_path: Path) -> Path:
    """Temp path for model artifacts."""
    return tmp_path / "model.pkl"


@pytest.fixture()
def registered_model(
    tmp_registry: ModelRegistry,
    trained_model: ETAModel,
    tmp_path: Path,
) -> tuple[ModelRegistry, ETAModel, Path, dict[str, Any]]:
    """A trained model registered in the tmp registry."""
    from app.ml.models.schemas import ModelMetadata, TrainingMetrics

    artifact_path = tmp_path / "eta_gbm_v1.pkl"
    trained_model.save(artifact_path)

    metrics = TrainingMetrics(mae=50.0, rmse=70.0, p90_error=120.0, per_route_mae={"3": 45.0})
    metadata = ModelMetadata(
        version=1,
        model_name="eta_gbm",
        trained_at="2026-04-13T00:00:00+00:00",
        training_window_days=60,
        training_rows=200,
        feature_version="ml-2.1-v1",
        metrics=metrics,
    )
    tmp_registry.register("eta_gbm", 1, metadata, artifact_path)
    return tmp_registry, trained_model, artifact_path, {"metadata": metadata}
