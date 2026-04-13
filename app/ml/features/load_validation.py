# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownVariableType=false
"""Pandera schema validation for load feature DataFrames (ML-3.1).

Validates the passenger load training matrix produced by extract_load_features().
Catches data quality issues before they propagate to model training.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
from pandera import Check, Column, DataFrameSchema

LOAD_FEATURES_SCHEMA = DataFrameSchema(  # type: ignore[no-untyped-call]
    {
        "gtfs_trip_id": Column(str, nullable=True, coerce=True),
        # Nullable int columns use coerce=True because pandas stores
        # int-with-None as object dtype
        "stop_sequence": Column(float, Check.ge(0), nullable=True, coerce=True),
        "stop_id": Column(float, nullable=True, coerce=True),
        "date": Column("object", nullable=False),  # datetime.date objects
        "hour": Column(int, Check.in_range(0, 23), nullable=False),
        "route_code": Column(str, nullable=False),
        "transport_type": Column(str, nullable=False),
        "tap_count": Column(int, Check.ge(1), nullable=False),
        "cumulative_load": Column(int, Check.ge(1), nullable=False),
        "capacity": Column(int, Check.ge(1), nullable=False),
        "load_factor_pct": Column(float, Check.in_range(0.0, 100.0), nullable=False),
    },
    strict=False,  # Allow extra columns
)


def validate_load_features(df: pd.DataFrame) -> pd.DataFrame:
    """Validate a load features DataFrame against the schema.

    Args:
        df: DataFrame with load feature columns.

    Returns:
        The validated DataFrame (unchanged if valid).

    Raises:
        pandera.errors.SchemaError: If validation fails.
    """
    result: Any = LOAD_FEATURES_SCHEMA.validate(df)
    return pd.DataFrame(result)
