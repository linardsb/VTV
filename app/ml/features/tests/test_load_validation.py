# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportMissingTypeStubs=false
"""Tests for load features Pandera validation schema (ML-3.1)."""

from __future__ import annotations

import datetime

import pandas as pd
import pytest
from pandera.errors import SchemaError

from app.ml.features.load_validation import validate_load_features
from app.ml.features.tests.conftest import make_load_features_df


class TestLoadValidation:
    def test_valid_load_features_pass(self) -> None:
        df = make_load_features_df(3)
        result = validate_load_features(df)
        assert len(result) == 3

    def test_negative_tap_count_fails(self) -> None:
        df = make_load_features_df(1, tap_count=-1)
        with pytest.raises(SchemaError):
            validate_load_features(df)

    def test_load_factor_out_of_range_fails(self) -> None:
        df = make_load_features_df(1, load_factor_pct=150.0)
        with pytest.raises(SchemaError):
            validate_load_features(df)

    def test_hour_out_of_range_fails(self) -> None:
        df = make_load_features_df(1, hour=25)
        with pytest.raises(SchemaError):
            validate_load_features(df)

    def test_zero_capacity_fails(self) -> None:
        df = make_load_features_df(1, capacity=0)
        with pytest.raises(SchemaError):
            validate_load_features(df)

    def test_nullable_trip_id_passes(self) -> None:
        df = make_load_features_df(1, gtfs_trip_id=None)
        result = validate_load_features(df)
        assert len(result) == 1

    def test_nullable_stop_sequence_passes(self) -> None:
        df = pd.DataFrame(
            [
                {
                    "gtfs_trip_id": "trip_001",
                    "stop_sequence": None,
                    "stop_id": None,
                    "date": datetime.date(2026, 3, 15),
                    "hour": 8,
                    "route_code": "22",
                    "transport_type": "bus",
                    "tap_count": 5,
                    "cumulative_load": 5,
                    "capacity": 60,
                    "load_factor_pct": 8.3,
                }
            ]
        )
        result = validate_load_features(df)
        assert len(result) == 1
