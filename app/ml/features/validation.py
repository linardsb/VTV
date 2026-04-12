# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownVariableType=false
"""Pandera schema validation for ETA feature DataFrames (ML-2.1).

Validates the 18-feature training matrix produced by extract_features_batch().
Catches data quality issues (nulls, range violations, type mismatches) before
they propagate to model training.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
from pandera import Check, Column, DataFrameSchema

ETA_FEATURES_SCHEMA = DataFrameSchema(
    {
        "day_of_week": Column(int, Check.in_range(0, 6), nullable=False),
        "month": Column(int, Check.in_range(1, 12), nullable=False),
        "is_school_day": Column(bool, nullable=False),
        "is_holiday": Column(bool, nullable=False),
        "weather_bucket": Column(
            str,
            Check.isin(["clear", "rain", "snow", "fog", "other"]),
            nullable=False,
        ),
        "route_type": Column(int, Check.in_range(0, 12), nullable=False),
        "direction": Column(int, Check.isin([0, 1]), nullable=False),
        "operator": Column(str, nullable=False),
        "time_of_day_hour": Column(float, Check.in_range(0.0, 48.0), nullable=False),
        "scheduled_headway_s": Column(float, Check.ge(0), nullable=False),
        "historical_avg_delay_at_stop_s": Column(float, nullable=False),
        "prev_stop_actual_delay_s": Column(float, nullable=False),
        "trip_elapsed_pct": Column(float, Check.in_range(0.0, 1.0), nullable=False),
        "temp_c": Column(float, Check.in_range(-60.0, 60.0), nullable=False),
        "wind_mps": Column(float, Check.ge(0), nullable=False),
        "precip_mm_last_hr": Column(float, Check.ge(0), nullable=False),
        "traffic_count_rolling_7d": Column(float, Check.ge(0), nullable=False),
        "accident_count_within_500m": Column(int, Check.ge(0), nullable=False),
    },
    strict=False,  # Allow extra columns (trip_id, stop_sequence)
)


def validate_features(df: pd.DataFrame) -> pd.DataFrame:
    """Validate a feature DataFrame against the ETA schema.

    Args:
        df: DataFrame with the 18 ETA feature columns.

    Returns:
        The validated DataFrame (unchanged if valid).

    Raises:
        pandera.errors.SchemaError: If validation fails.
    """
    result: Any = ETA_FEATURES_SCHEMA.validate(df)
    return pd.DataFrame(result)


def detect_outliers(df: pd.DataFrame) -> pd.DataFrame:
    """Flag rows where any numeric feature exceeds 3 sigma from mean.

    Args:
        df: Validated feature DataFrame.

    Returns:
        Subset of rows containing at least one outlier value.
    """
    numeric_cols = [
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
    existing_cols = [c for c in numeric_cols if c in df.columns]
    if not existing_cols:
        return df.iloc[0:0]

    numeric_df = df[existing_cols].apply(pd.to_numeric, errors="coerce")
    means = numeric_df.mean()
    stds = numeric_df.std()

    # Avoid division by zero for constant columns
    stds = stds.replace(0, float("inf"))
    z_scores = ((numeric_df - means) / stds).abs()
    outlier_mask = (z_scores > 3).any(axis=1)
    return pd.DataFrame(df[outlier_mask])
