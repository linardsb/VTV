"""Data structures for ETA prediction model (ML-2.2).

Frozen dataclasses for internal ML pipeline use — not Pydantic API schemas.
"""

from __future__ import annotations

from dataclasses import dataclass


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
