# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportMissingTypeStubs=false
"""LightGBM gradient boosting model for passenger load prediction (ML-3.2).

Trains three quantile regressors (q10, q50, q90) for passenger count and one
classifier for crowding bucket. Uses load features from ML-3.1.

No REST endpoints — consumed by training CLI and future ML-3.3 online serving.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import lightgbm
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.metrics import f1_score, mean_absolute_error, root_mean_squared_error
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, OrdinalEncoder, StandardScaler

from app.core.logging import get_logger
from app.ml.features.load_validation import validate_load_features
from app.ml.models.schemas import (
    LoadPrediction,
    LoadTrainingMetrics,
    crowding_bucket,
)

logger = get_logger(__name__)

CATEGORICAL_FEATURES: list[str] = [
    "route_code",
    "transport_type",
]
NUMERIC_FEATURES: list[str] = [
    "hour",
    "stop_sequence",
    "tap_count",
    "capacity",
    "load_factor_pct",
]
ALL_FEATURES: list[str] = CATEGORICAL_FEATURES + NUMERIC_FEATURES
TARGET_COL: str = "cumulative_load"
BUCKET_COL: str = "crowding_bucket"
FEATURE_VERSION: str = "ml-3.1-v1"

BUCKET_CLASSES: list[str] = ["empty", "light", "moderate", "full", "overcrowded"]


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


def _build_label_encoder() -> LabelEncoder:
    """Build a label encoder pre-fitted on the 5 crowding bucket classes.

    Returns:
        LabelEncoder fitted on BUCKET_CLASSES.
    """
    le = LabelEncoder()
    le.fit(BUCKET_CLASSES)
    return le


def train(
    df: pd.DataFrame,
    target_col: str = TARGET_COL,
    val_split: float = 0.2,
    random_state: int = 42,
    n_estimators: int = 500,
    early_stopping_rounds: int = 50,
) -> tuple[LoadModel, LoadTrainingMetrics]:
    """Train a LightGBM load prediction model with dual-head output.

    Head 1: Three quantile regressors (q10, q50, q90) for passenger count.
    Head 2: One classifier for crowding bucket (5-class).

    Args:
        df: Training DataFrame with load feature columns + target column.
        target_col: Name of the regression target column.
        val_split: Fraction of data for validation (early stopping).
        random_state: Random seed for reproducibility.
        n_estimators: Maximum boosting rounds.
        early_stopping_rounds: Stop after N rounds without improvement.

    Returns:
        Tuple of (trained LoadModel, validation LoadTrainingMetrics).
    """
    logger.info(
        "ml.load.training_started",
        rows=len(df),
        n_estimators=n_estimators,
        val_split=val_split,
    )

    # Validate features
    validate_load_features(df)

    # Derive crowding bucket from load_factor_pct
    df = df.copy()
    df[BUCKET_COL] = df["load_factor_pct"].apply(crowding_bucket)

    x_all = df[ALL_FEATURES]
    y_count = df[target_col]
    y_bucket = df[BUCKET_COL]

    # Train/validation split (stratify on bucket to ensure all classes in both sets)
    split_result: Any = train_test_split(
        x_all,
        y_count,
        y_bucket,
        test_size=val_split,
        random_state=random_state,
        stratify=y_bucket,
    )
    x_train: pd.DataFrame = split_result[0]
    x_val: pd.DataFrame = split_result[1]
    y_count_train: pd.Series[float] = split_result[2]
    y_count_val: pd.Series[float] = split_result[3]
    y_bucket_train: pd.Series[str] = split_result[4]
    y_bucket_val: pd.Series[str] = split_result[5]

    # Fit transformer on training data
    transformer = _build_transformer()
    x_train_t = transformer.fit_transform(x_train)
    x_val_t = transformer.transform(x_val)

    # Train 3 quantile models for passenger count
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
            y_count_train,
            eval_set=[(x_val_t, y_count_val)],
            callbacks=[
                lightgbm.early_stopping(stopping_rounds=early_stopping_rounds),
                lightgbm.log_evaluation(0),
            ],
        )
        models[name] = model

    # Train classifier for crowding bucket
    label_encoder = _build_label_encoder()
    y_bucket_train_encoded: Any = label_encoder.transform(y_bucket_train)
    y_bucket_val_encoded: Any = label_encoder.transform(y_bucket_val)

    classifier = lightgbm.LGBMClassifier(
        n_estimators=n_estimators,
        random_state=random_state,
        verbosity=-1,
        num_class=len(BUCKET_CLASSES),
    )
    classifier.fit(
        x_train_t,
        y_bucket_train_encoded,
        eval_set=[(x_val_t, y_bucket_val_encoded)],
        callbacks=[
            lightgbm.early_stopping(stopping_rounds=early_stopping_rounds),
            lightgbm.log_evaluation(0),
        ],
    )

    # Compute regression metrics using median model
    val_preds: Any = models["q50"].predict(x_val_t)
    count_mae = float(mean_absolute_error(y_count_val, val_preds))
    count_rmse = float(root_mean_squared_error(y_count_val, val_preds))
    errors = np.abs(np.asarray(y_count_val) - np.asarray(val_preds))
    count_p90_error = float(np.percentile(errors, 90))

    # Compute classification metrics
    bucket_preds_encoded: Any = classifier.predict(x_val_t)
    bucket_f1 = float(f1_score(y_bucket_val_encoded, bucket_preds_encoded, average="macro"))

    # Per-route MAE
    per_route = compute_per_route_mae(
        x_val.assign(**{target_col: y_count_val}),
        pd.Series(val_preds, index=y_count_val.index),
        y_count_val,
    )

    metrics = LoadTrainingMetrics(
        count_mae=count_mae,
        count_rmse=count_rmse,
        count_p90_error=count_p90_error,
        bucket_f1_macro=bucket_f1,
        per_route_mae=per_route,
    )

    logger.info(
        "ml.load.training_completed",
        count_mae=count_mae,
        count_rmse=count_rmse,
        count_p90_error=count_p90_error,
        bucket_f1_macro=bucket_f1,
        routes_evaluated=len(per_route),
    )

    load_model = LoadModel(
        transformer=transformer,
        models=models,
        classifier=classifier,
        label_encoder=label_encoder,
        feature_version=FEATURE_VERSION,
    )
    return load_model, metrics


def compute_per_route_mae(
    df: pd.DataFrame,
    predictions: pd.Series[float],
    target: pd.Series[float],
) -> dict[str, float]:
    """Compute MAE per route_code for fairness checking.

    Args:
        df: DataFrame containing a 'route_code' column.
        predictions: Predicted passenger count values.
        target: Actual passenger count values.

    Returns:
        Dict mapping route_code to MAE.
    """
    result: dict[str, float] = {}
    if "route_code" not in df.columns:
        return result

    for route_code in df["route_code"].unique():
        mask = df["route_code"] == route_code
        if mask.sum() > 0:
            route_mae = float(mean_absolute_error(target[mask], predictions[mask]))
            result[str(route_code)] = route_mae
    return result


@dataclass
class LoadModel:
    """Wrapper around trained LightGBM load prediction models.

    Attributes:
        transformer: Fitted sklearn ColumnTransformer.
        models: Dict of quantile name to fitted LGBMRegressor.
        classifier: Fitted LGBMClassifier for crowding bucket.
        label_encoder: Fitted LabelEncoder for bucket classes.
        feature_version: Feature schema version string.
    """

    transformer: Any  # ColumnTransformer (untyped lib)
    models: dict[str, Any]  # {"q10": LGBMRegressor, "q50": ..., "q90": ...}
    classifier: Any  # LGBMClassifier (untyped lib)
    label_encoder: Any  # LabelEncoder (untyped lib)
    feature_version: str = FEATURE_VERSION

    def predict(self, row_dict: dict[str, Any]) -> LoadPrediction:
        """Single-row prediction from a feature dictionary.

        Args:
            row_dict: Dict with feature column names as keys.

        Returns:
            LoadPrediction with count, confidence interval, and crowding bucket.
        """
        row_df = pd.DataFrame([row_dict])
        row_t = self.transformer.transform(row_df[ALL_FEATURES])

        q10 = float(self.models["q10"].predict(row_t)[0])
        q50 = float(self.models["q50"].predict(row_t)[0])
        q90 = float(self.models["q90"].predict(row_t)[0])

        bucket_encoded: Any = self.classifier.predict(row_t)[0]
        bucket_label: str = str(self.label_encoder.inverse_transform([bucket_encoded])[0])

        return LoadPrediction(
            predicted_passenger_count=q50,
            confidence_lower=q10,
            confidence_upper=q90,
            crowding_bucket=bucket_label,  # type: ignore[arg-type]
        )

    def predict_batch(self, df: pd.DataFrame) -> pd.DataFrame:
        """Batch prediction returning DataFrame with prediction columns.

        Args:
            df: DataFrame with the feature columns.

        Returns:
            Copy of input with added columns: predicted_passenger_count,
            confidence_lower, confidence_upper, crowding_bucket.
        """
        x_t = self.transformer.transform(df[ALL_FEATURES])
        result = df.copy()
        result["confidence_lower"] = self.models["q10"].predict(x_t)
        result["predicted_passenger_count"] = self.models["q50"].predict(x_t)
        result["confidence_upper"] = self.models["q90"].predict(x_t)

        bucket_encoded: Any = self.classifier.predict(x_t)
        result["crowding_bucket"] = self.label_encoder.inverse_transform(bucket_encoded)
        return result

    def save(self, path: Path) -> None:
        """Serialize model to disk via joblib.

        Args:
            path: Destination file path.
        """
        joblib.dump(self, path)
        logger.info("ml.load.model_saved", path=str(path))

    @classmethod
    def load(cls, path: Path) -> LoadModel:
        """Deserialize model from disk.

        Args:
            path: Path to a joblib-serialized model file.

        Returns:
            Reconstructed LoadModel instance.
        """
        model: LoadModel = joblib.load(path)
        logger.info("ml.load.model_loaded", path=str(path))
        return model
