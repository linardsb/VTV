"""Data structures for ML prediction models (ML-2.2 ETA, ML-3.2 Load).

Frozen dataclasses for internal ML pipeline use — not Pydantic API schemas.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

CrowdingBucket = Literal["empty", "light", "moderate", "full", "overcrowded"]


@dataclass(frozen=True)
class ETAPrediction:
    """Single ETA prediction with confidence interval."""

    predicted_delay_s: float  # median (quantile 0.5)
    confidence_lower: float  # quantile 0.1
    confidence_upper: float  # quantile 0.9


@dataclass(frozen=True)
class TrainingMetrics:
    """Metrics from a single training run."""

    mae: float
    rmse: float
    p90_error: float
    per_route_mae: dict[str, float]  # route_type -> MAE


@dataclass(frozen=True)
class ModelMetadata:
    """Metadata for a trained model version."""

    version: int
    model_name: str
    trained_at: str  # ISO 8601
    training_window_days: int
    training_rows: int
    feature_version: str  # "ml-2.1-v1"
    metrics: TrainingMetrics


def crowding_bucket(load_factor_pct: float) -> CrowdingBucket:
    """Classify load factor into crowding bucket.

    Thresholds: <20% empty, 20-40% light, 40-70% moderate, 70-95% full, >95% overcrowded.
    """
    if load_factor_pct < 20.0:
        return "empty"
    if load_factor_pct < 40.0:
        return "light"
    if load_factor_pct < 70.0:
        return "moderate"
    if load_factor_pct < 95.0:
        return "full"
    return "overcrowded"


@dataclass(frozen=True)
class LoadTrainingMetrics:
    """Metrics from a load model training run (dual-head)."""

    count_mae: float
    count_rmse: float
    count_p90_error: float
    bucket_f1_macro: float
    per_route_mae: dict[str, float]


@dataclass(frozen=True)
class LoadPrediction:
    """Single load prediction with confidence interval and crowding bucket."""

    predicted_passenger_count: float
    confidence_lower: float
    confidence_upper: float
    crowding_bucket: CrowdingBucket
