# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportMissingTypeStubs=false, reportMissingParameterType=false, reportUnknownParameterType=false
"""Test fixtures for ML GBM models (ML-2.2 ETA, ML-3.2 Load)."""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from app.ml.features.tests.conftest import make_eta_features_df
from app.ml.models.eta_gbm import ETAModel, train
from app.ml.models.load_gbm import LoadModel
from app.ml.models.load_gbm import train as train_load
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


# --- Load model fixtures (ML-3.2) ---


def make_load_training_df(n: int = 200) -> pd.DataFrame:
    """Generate n rows of load feature data + target for training.

    Args:
        n: Number of rows.

    Returns:
        DataFrame with load feature columns and cumulative_load target.
    """
    rng = np.random.default_rng(42)
    route_codes: list[str] = ["1", "3", "22", "47"]
    transport_types: list[str] = ["bus", "tram"]

    data: dict[str, Any] = {
        "gtfs_trip_id": [f"trip_{i}" for i in range(n)],
        "stop_sequence": rng.integers(1, 30, size=n).astype(float),
        "stop_id": rng.integers(1000, 9999, size=n).astype(float),
        "date": [
            datetime.date(2026, 1, 1) + datetime.timedelta(days=int(d))
            for d in rng.integers(0, 60, size=n)
        ],
        "hour": rng.integers(0, 24, size=n),
        "route_code": rng.choice(route_codes, size=n),
        "transport_type": rng.choice(transport_types, size=n),
        "tap_count": rng.integers(1, 15, size=n),
        "capacity": rng.choice([60, 80, 100, 200], size=n),
    }

    # Derive cumulative_load from tap_count with noise
    base_load = data["tap_count"] * rng.integers(1, 4, size=n)
    data["cumulative_load"] = np.clip(base_load, 1, None).astype(int)

    # load_factor_pct = (cumulative_load / capacity) * 100, capped at 100
    data["load_factor_pct"] = np.clip(
        (data["cumulative_load"] / data["capacity"]) * 100.0, 0.0, 100.0
    )

    return pd.DataFrame(data)


@pytest.fixture()
def sample_load_training_df() -> pd.DataFrame:
    """200-row DataFrame with load features + target column."""
    return make_load_training_df(200)


@pytest.fixture(scope="session")
def trained_load_model() -> LoadModel:
    """Pre-trained LoadModel on sample data (session-scoped for speed)."""
    df = make_load_training_df(200)
    model, _metrics = train_load(df, n_estimators=10, early_stopping_rounds=5)
    return model
