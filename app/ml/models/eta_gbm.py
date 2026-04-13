# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportMissingTypeStubs=false
"""LightGBM gradient boosting model for ETA prediction (ML-2.2).

Trains three quantile regressors (q10, q50, q90) on the 18-field ETAFeatures
matrix from ML-2.1. Provides single-row and batch prediction with confidence
intervals.

No REST endpoints — consumed by training CLI and future ML-2.3 online serving.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import joblib
import lightgbm
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.metrics import mean_absolute_error, root_mean_squared_error
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import OrdinalEncoder, StandardScaler

from app.core.logging import get_logger
from app.ml.features.eta_features import ETAFeatures
from app.ml.features.validation import validate_features
from app.ml.models.schemas import ETAPrediction, TrainingMetrics

logger = get_logger(__name__)

CATEGORICAL_FEATURES: list[str] = [
    "day_of_week",
    "month",
    "is_school_day",
    "is_holiday",
    "weather_bucket",
    "route_type",
    "direction",
    "operator",
]
NUMERIC_FEATURES: list[str] = [
    "time_of_day_hour",
    "scheduled_headway_s",
    "historical_avg_delay_at_stop_s",
    "prev_stop_actual_delay_s",
    "trip_elapsed_pct",
    "temp_c",
    "wind_mps",
    "precip_mm_last_hr",
    "traffic_count_rolling_7d",
    "accident_count_within_500m",
]
ALL_FEATURES: list[str] = CATEGORICAL_FEATURES + NUMERIC_FEATURES
TARGET_COL: str = "actual_arrival_delay_seconds"
FEATURE_VERSION: str = "ml-2.1-v1"


def _build_transformer() -> ColumnTransformer:
    """Build the feature preprocessing pipeline.

    Returns:
        ColumnTransformer with numeric scaling and categorical encoding.
    """
    return ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), NUMERIC_FEATURES),
            (
                "cat",
                OrdinalEncoder(
                    handle_unknown="use_encoded_value",
                    unknown_value=-1,
                ),
                CATEGORICAL_FEATURES,
            ),
        ],
        remainder="drop",
    )


def train(
    df: pd.DataFrame,
    target_col: str = TARGET_COL,
    val_split: float = 0.2,
    random_state: int = 42,
    n_estimators: int = 500,
    early_stopping_rounds: int = 50,
) -> tuple[ETAModel, TrainingMetrics]:
    """Train a LightGBM ETA prediction model with quantile regression.

    Args:
        df: Training DataFrame with 18 feature columns + target column.
        target_col: Name of the target column.
        val_split: Fraction of data for validation (early stopping).
        random_state: Random seed for reproducibility.
        n_estimators: Maximum boosting rounds.
        early_stopping_rounds: Stop after N rounds without improvement.

    Returns:
        Tuple of (trained ETAModel, validation TrainingMetrics).
    """
    logger.info(
        "ml.eta.training_started",
        rows=len(df),
        n_estimators=n_estimators,
        val_split=val_split,
    )

    # Validate features
    validate_features(df)

    x_all = df[ALL_FEATURES]
    y_all = df[target_col]

    # Train/validation split (sklearn is untyped, cast results)
    split_result: Any = train_test_split(
        x_all, y_all, test_size=val_split, random_state=random_state
    )
    x_train: pd.DataFrame = split_result[0]
    x_val: pd.DataFrame = split_result[1]
    y_train: pd.Series[float] = split_result[2]
    y_val: pd.Series[float] = split_result[3]

    # Fit transformer on training data
    transformer = _build_transformer()
    x_train_t = transformer.fit_transform(x_train)
    x_val_t = transformer.transform(x_val)

    # Train 3 quantile models
    quantiles: dict[str, float] = {"q10": 0.1, "q50": 0.5, "q90": 0.9}
    models: dict[str, Any] = {}

    for name, alpha in quantiles.items():
        model = lightgbm.LGBMRegressor(
            objective="quantile",
            alpha=alpha,
            n_estimators=n_estimators,
            random_state=random_state,
            verbosity=-1,
        )
        model.fit(
            x_train_t,
            y_train,
            eval_set=[(x_val_t, y_val)],
            callbacks=[
                lightgbm.early_stopping(stopping_rounds=early_stopping_rounds),
                lightgbm.log_evaluation(0),
            ],
        )
        models[name] = model

    # Compute validation metrics using median model
    val_preds: Any = models["q50"].predict(x_val_t)
    mae = float(mean_absolute_error(y_val, val_preds))
    rmse = float(root_mean_squared_error(y_val, val_preds))
    errors = np.abs(np.asarray(y_val) - np.asarray(val_preds))
    p90_error = float(np.percentile(errors, 90))

    # Per-route MAE
    per_route = compute_per_route_mae(
        x_val.assign(**{target_col: y_val}),
        pd.Series(val_preds, index=y_val.index),
        y_val,
    )

    metrics = TrainingMetrics(
        mae=mae,
        rmse=rmse,
        p90_error=p90_error,
        per_route_mae=per_route,
    )

    logger.info(
        "ml.eta.training_completed",
        mae=mae,
        rmse=rmse,
        p90_error=p90_error,
        routes_evaluated=len(per_route),
    )

    logger.info(
        "ml.eta.validation_metrics",
        mae=mae,
        rmse=rmse,
        p90_error=p90_error,
        per_route_mae=per_route,
    )

    eta_model = ETAModel(
        transformer=transformer,
        models=models,
        feature_version=FEATURE_VERSION,
    )
    return eta_model, metrics


def compute_per_route_mae(
    df: pd.DataFrame,
    predictions: pd.Series[float],
    target: pd.Series[float],
) -> dict[str, float]:
    """Compute MAE per route_type for fairness checking.

    Args:
        df: DataFrame containing a 'route_type' column.
        predictions: Predicted delay values.
        target: Actual delay values.

    Returns:
        Dict mapping route_type (as string) to MAE.
    """
    result: dict[str, float] = {}
    if "route_type" not in df.columns:
        return result

    for route_type in df["route_type"].unique():
        mask = df["route_type"] == route_type
        if mask.sum() > 0:
            route_mae = float(mean_absolute_error(target[mask], predictions[mask]))
            result[str(route_type)] = route_mae
    return result


@dataclass
class ETAModel:
    """Wrapper around trained LightGBM quantile models with preprocessing.

    Attributes:
        transformer: Fitted sklearn ColumnTransformer.
        models: Dict of quantile name to fitted LGBMRegressor.
        feature_version: Feature schema version string.
    """

    transformer: Any  # ColumnTransformer (untyped lib)
    models: dict[str, Any]  # {"q10": LGBMRegressor, "q50": ..., "q90": ...}
    feature_version: str = FEATURE_VERSION

    def predict(self, features: ETAFeatures) -> ETAPrediction:
        """Single-row prediction from a frozen ETAFeatures dataclass.

        Args:
            features: Single observation features.

        Returns:
            ETAPrediction with median, lower, and upper bounds.
        """
        row_df = pd.DataFrame([asdict(features)])
        row_t = self.transformer.transform(row_df[ALL_FEATURES])

        q10 = float(self.models["q10"].predict(row_t)[0])
        q50 = float(self.models["q50"].predict(row_t)[0])
        q90 = float(self.models["q90"].predict(row_t)[0])

        return ETAPrediction(
            predicted_delay_s=q50,
            confidence_lower=q10,
            confidence_upper=q90,
        )

    def predict_batch(self, df: pd.DataFrame) -> pd.DataFrame:
        """Batch prediction returning DataFrame with prediction columns.

        Args:
            df: DataFrame with the 18 feature columns.

        Returns:
            Copy of input with added columns: predicted_delay_s,
            confidence_lower, confidence_upper.
        """
        x_t = self.transformer.transform(df[ALL_FEATURES])
        result = df.copy()
        result["confidence_lower"] = self.models["q10"].predict(x_t)
        result["predicted_delay_s"] = self.models["q50"].predict(x_t)
        result["confidence_upper"] = self.models["q90"].predict(x_t)
        return result

    def save(self, path: Path) -> None:
        """Serialize model to disk via joblib.

        Args:
            path: Destination file path.
        """
        joblib.dump(self, path)
        logger.info("ml.eta.model_saved", path=str(path))

    @classmethod
    def load(cls, path: Path) -> ETAModel:
        """Deserialize model from disk.

        Args:
            path: Path to a joblib-serialized model file.

        Returns:
            Reconstructed ETAModel instance.
        """
        model: ETAModel = joblib.load(path)
        logger.info("ml.eta.model_loaded", path=str(path))
        return model
