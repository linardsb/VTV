"""Tests for Pandera schema validation of ETA features (ML-2.1)."""

from __future__ import annotations

import pandas as pd
import pytest

from app.ml.features.tests.conftest import make_eta_features_df
from app.ml.features.validation import detect_outliers, validate_features


class TestValidateFeatures:
    def test_valid_features_pass(self):
        df = make_eta_features_df(5)
        result = validate_features(df)
        assert len(result) == 5

    def test_invalid_day_of_week_rejected(self):
        df = make_eta_features_df(1, day_of_week=7)  # Must be 0-6
        with pytest.raises(Exception):  # noqa: B017
            validate_features(df)

    def test_negative_headway_rejected(self):
        df = make_eta_features_df(1, scheduled_headway_s=-100.0)
        with pytest.raises(Exception):  # noqa: B017
            validate_features(df)

    def test_invalid_weather_bucket_rejected(self):
        df = make_eta_features_df(1, weather_bucket="tornado")
        with pytest.raises(Exception):  # noqa: B017
            validate_features(df)

    def test_trip_elapsed_pct_out_of_range_rejected(self):
        df = make_eta_features_df(1, trip_elapsed_pct=1.5)
        with pytest.raises(Exception):  # noqa: B017
            validate_features(df)

    def test_temp_c_extreme_rejected(self):
        df = make_eta_features_df(1, temp_c=100.0)  # Max 60.0
        with pytest.raises(Exception):  # noqa: B017
            validate_features(df)


class TestDetectOutliers:
    def test_no_outliers_in_normal_data(self):
        df = make_eta_features_df(20)
        outliers = detect_outliers(df)
        assert len(outliers) == 0

    def test_extreme_value_flagged(self):
        df = make_eta_features_df(20)
        # Add one row with extreme temp_c
        extreme_row = df.iloc[0].copy()
        extreme_row["temp_c"] = 999.0  # Way beyond 3 sigma
        extreme_df = pd.concat([df, pd.DataFrame([extreme_row])], ignore_index=True)
        outliers = detect_outliers(extreme_df)
        assert len(outliers) >= 1

    def test_empty_df_returns_empty(self):
        df = make_eta_features_df(0)
        outliers = detect_outliers(df)
        assert len(outliers) == 0
