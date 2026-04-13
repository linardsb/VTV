# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportMissingTypeStubs=false, reportMissingParameterType=false, reportUnknownParameterType=false
"""Tests for load GBM model training and prediction (ML-3.2)."""

from __future__ import annotations

from typing import Any

import pandas as pd

from app.ml.models.load_gbm import LoadModel, compute_per_route_mae, train
from app.ml.models.schemas import (
    LoadPrediction,
    LoadTrainingMetrics,
    crowding_bucket,
)
from app.ml.models.tests.conftest import make_load_training_df


def _make_row_dict() -> dict[str, Any]:
    """Create a single feature row dict for prediction tests."""
    row: dict[str, Any] = dict(make_load_training_df(1).iloc[0])
    return row


class TestTrain:
    def test_training_smoke(self, sample_load_training_df):
        """Train completes and returns LoadModel + metrics."""
        model, metrics = train(sample_load_training_df, n_estimators=10, early_stopping_rounds=5)
        assert isinstance(model, LoadModel)
        assert isinstance(metrics, LoadTrainingMetrics)
        assert metrics.count_mae > 0

    def test_reproducibility(self, sample_load_training_df):
        """Same seed produces identical metrics."""
        _, m1 = train(
            sample_load_training_df,
            random_state=42,
            n_estimators=10,
            early_stopping_rounds=5,
        )
        _, m2 = train(
            sample_load_training_df,
            random_state=42,
            n_estimators=10,
            early_stopping_rounds=5,
        )
        assert m1.count_mae == m2.count_mae
        assert m1.count_rmse == m2.count_rmse

    def test_different_seeds_produce_different_results(self, sample_load_training_df):
        """Different seeds produce different metrics."""
        _, m1 = train(
            sample_load_training_df,
            random_state=42,
            n_estimators=10,
            early_stopping_rounds=5,
        )
        _, m2 = train(
            sample_load_training_df,
            random_state=99,
            n_estimators=10,
            early_stopping_rounds=5,
        )
        assert m1.count_mae != m2.count_mae or m1.count_rmse != m2.count_rmse

    def test_metrics_have_per_route_mae(self, sample_load_training_df):
        """Training metrics include per-route MAE breakdown."""
        _, metrics = train(sample_load_training_df, n_estimators=10, early_stopping_rounds=5)
        assert isinstance(metrics.per_route_mae, dict)
        assert len(metrics.per_route_mae) > 0


class TestPredict:
    def test_single_prediction(self, trained_load_model):
        """predict() returns LoadPrediction with valid fields."""
        row = _make_row_dict()
        pred = trained_load_model.predict(row)
        assert isinstance(pred, LoadPrediction)
        assert isinstance(pred.predicted_passenger_count, float)
        assert isinstance(pred.confidence_lower, float)
        assert isinstance(pred.confidence_upper, float)
        assert pred.crowding_bucket in (
            "empty",
            "light",
            "moderate",
            "full",
            "overcrowded",
        )

    def test_batch_prediction(self, trained_load_model, sample_load_training_df):
        """predict_batch() returns DataFrame with prediction columns."""
        result = trained_load_model.predict_batch(sample_load_training_df)
        assert "predicted_passenger_count" in result.columns
        assert "confidence_lower" in result.columns
        assert "confidence_upper" in result.columns
        assert "crowding_bucket" in result.columns
        assert len(result) == len(sample_load_training_df)

    def test_prediction_deterministic(self, trained_load_model):
        """Same input produces same output."""
        row = _make_row_dict()
        pred1 = trained_load_model.predict(row)
        pred2 = trained_load_model.predict(row)
        assert pred1 == pred2


class TestCrowdingBucket:
    def test_bucket_empty(self) -> None:
        assert crowding_bucket(10.0) == "empty"

    def test_bucket_light(self) -> None:
        assert crowding_bucket(30.0) == "light"

    def test_bucket_moderate(self) -> None:
        assert crowding_bucket(55.0) == "moderate"

    def test_bucket_full(self) -> None:
        assert crowding_bucket(85.0) == "full"

    def test_bucket_overcrowded(self) -> None:
        assert crowding_bucket(98.0) == "overcrowded"


class TestQuantileInterval:
    def test_quantile_ordering(self, trained_load_model, sample_load_training_df):
        """q10 <= q50 <= q90 for all predictions."""
        result = trained_load_model.predict_batch(sample_load_training_df)
        assert (result["confidence_lower"] <= result["predicted_passenger_count"]).all()
        assert (result["predicted_passenger_count"] <= result["confidence_upper"]).all()

    def test_interval_coverage(self, trained_load_model, sample_load_training_df):
        """80% interval should cover a reasonable fraction of actuals."""
        result = trained_load_model.predict_batch(sample_load_training_df)
        target = sample_load_training_df["cumulative_load"]
        in_interval = (
            (target >= result["confidence_lower"]) & (target <= result["confidence_upper"])
        ).mean()
        assert in_interval > 0.5


class TestSaveLoad:
    def test_save_load_roundtrip(self, trained_load_model, tmp_path):
        """Model survives serialization roundtrip."""
        path = tmp_path / "model.pkl"
        trained_load_model.save(path)
        loaded = LoadModel.load(path)
        row = _make_row_dict()
        assert trained_load_model.predict(row) == loaded.predict(row)

    def test_feature_version_preserved(self, trained_load_model, tmp_path):
        """Feature version string survives save/load."""
        path = tmp_path / "model.pkl"
        trained_load_model.save(path)
        loaded = LoadModel.load(path)
        assert loaded.feature_version == trained_load_model.feature_version

    def test_save_creates_file(self, trained_load_model, tmp_path):
        """save() creates a file at the specified path."""
        path = tmp_path / "test_model.pkl"
        assert not path.exists()
        trained_load_model.save(path)
        assert path.exists()
        assert path.stat().st_size > 0


class TestPerRouteFairness:
    def test_per_route_mae_populated(self, trained_load_model, sample_load_training_df):
        """Different route_codes get entries."""
        result = trained_load_model.predict_batch(sample_load_training_df)
        per_route = compute_per_route_mae(
            sample_load_training_df,
            result["predicted_passenger_count"],
            sample_load_training_df["cumulative_load"],
        )
        assert isinstance(per_route, dict)
        assert len(per_route) > 0
        assert all(isinstance(v, float) for v in per_route.values())

    def test_no_systematic_bias(self, trained_load_model, sample_load_training_df):
        """No single route should have >3x overall MAE."""
        result = trained_load_model.predict_batch(sample_load_training_df)
        preds = result["predicted_passenger_count"]
        target = sample_load_training_df["cumulative_load"]
        per_route = compute_per_route_mae(sample_load_training_df, preds, target)
        if not per_route:
            return
        overall_mae = float((target - preds).abs().mean())
        if overall_mae == 0:
            return
        for route_code, route_mae in per_route.items():
            assert route_mae <= overall_mae * 3, (
                f"Route {route_code} MAE {route_mae:.1f} > 3x overall {overall_mae:.1f}"
            )


class TestPerRouteMissing:
    def test_per_route_mae_missing_column(self) -> None:
        """Returns empty dict when route_code column is missing."""
        df = pd.DataFrame({"x": [1, 2, 3]})
        preds = pd.Series([1.0, 2.0, 3.0])
        target = pd.Series([1.5, 2.5, 3.5])
        result = compute_per_route_mae(df, preds, target)
        assert result == {}
