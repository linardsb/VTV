# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportMissingTypeStubs=false, reportMissingParameterType=false, reportUnknownParameterType=false
"""Tests for ETA GBM model training and prediction (ML-2.2)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.ml.features.eta_features import ETAFeatures
from app.ml.features.tests.conftest import make_eta_features_dict
from app.ml.models.eta_gbm import ALL_FEATURES, ETAModel, compute_per_route_mae, train
from app.ml.models.schemas import ETAPrediction, TrainingMetrics


class TestTrain:
    def test_training_smoke(self, sample_training_df):
        """Train completes and returns ETAModel + metrics."""
        model, metrics = train(sample_training_df, n_estimators=10, early_stopping_rounds=5)
        assert isinstance(model, ETAModel)
        assert isinstance(metrics, TrainingMetrics)
        assert metrics.mae > 0

    def test_reproducibility(self, sample_training_df):
        """Same seed produces identical metrics."""
        _, m1 = train(sample_training_df, random_state=42, n_estimators=10, early_stopping_rounds=5)
        _, m2 = train(sample_training_df, random_state=42, n_estimators=10, early_stopping_rounds=5)
        assert m1.mae == m2.mae
        assert m1.rmse == m2.rmse

    def test_different_seeds_produce_different_results(self, sample_training_df):
        """Different seeds produce different metrics."""
        _, m1 = train(sample_training_df, random_state=42, n_estimators=10, early_stopping_rounds=5)
        _, m2 = train(sample_training_df, random_state=99, n_estimators=10, early_stopping_rounds=5)
        # With different seeds, at least one metric should differ
        assert m1.mae != m2.mae or m1.rmse != m2.rmse

    def test_metrics_have_per_route_mae(self, sample_training_df):
        """Training metrics include per-route MAE breakdown."""
        _, metrics = train(sample_training_df, n_estimators=10, early_stopping_rounds=5)
        assert isinstance(metrics.per_route_mae, dict)
        assert len(metrics.per_route_mae) > 0


class TestPredict:
    def test_single_prediction(self, trained_model):
        """predict() returns ETAPrediction with valid bounds."""
        features = ETAFeatures(**make_eta_features_dict())
        pred = trained_model.predict(features)
        assert isinstance(pred, ETAPrediction)
        assert isinstance(pred.predicted_delay_s, float)
        assert isinstance(pred.confidence_lower, float)
        assert isinstance(pred.confidence_upper, float)

    def test_batch_prediction(self, trained_model, sample_training_df):
        """predict_batch() returns DataFrame with prediction columns."""
        result = trained_model.predict_batch(sample_training_df)
        assert "predicted_delay_s" in result.columns
        assert "confidence_lower" in result.columns
        assert "confidence_upper" in result.columns
        assert len(result) == len(sample_training_df)

    def test_prediction_deterministic(self, trained_model):
        """Same input produces same output."""
        features = ETAFeatures(**make_eta_features_dict())
        pred1 = trained_model.predict(features)
        pred2 = trained_model.predict(features)
        assert pred1 == pred2


class TestQuantileInterval:
    def test_quantile_ordering(self, trained_model, sample_training_df):
        """q10 <= q50 <= q90 for all predictions."""
        result = trained_model.predict_batch(sample_training_df)
        assert (result["confidence_lower"] <= result["predicted_delay_s"]).all()
        assert (result["predicted_delay_s"] <= result["confidence_upper"]).all()

    def test_interval_coverage(self, trained_model, sample_training_df):
        """80% interval should cover a reasonable fraction of actuals."""
        result = trained_model.predict_batch(sample_training_df)
        target = sample_training_df["actual_arrival_delay_seconds"]
        in_interval = (
            (target >= result["confidence_lower"]) & (target <= result["confidence_upper"])
        ).mean()
        # Relaxed bound for small sample
        assert in_interval > 0.5


class TestSaveLoad:
    def test_save_load_roundtrip(self, trained_model, tmp_path):
        """Model survives serialization roundtrip."""
        path = tmp_path / "model.pkl"
        trained_model.save(path)
        loaded = ETAModel.load(path)
        features = ETAFeatures(**make_eta_features_dict())
        assert trained_model.predict(features) == loaded.predict(features)

    def test_feature_version_preserved(self, trained_model, tmp_path):
        """Feature version string survives save/load."""
        path = tmp_path / "model.pkl"
        trained_model.save(path)
        loaded = ETAModel.load(path)
        assert loaded.feature_version == trained_model.feature_version

    def test_save_creates_file(self, trained_model, tmp_path):
        """save() creates a file at the specified path."""
        path = tmp_path / "test_model.pkl"
        assert not path.exists()
        trained_model.save(path)
        assert path.exists()
        assert path.stat().st_size > 0


class TestPerRouteMAE:
    def test_per_route_mae_computation(self, trained_model, sample_training_df):
        """Per-route MAE returns dict with route_type keys."""
        result = trained_model.predict_batch(sample_training_df)
        per_route = compute_per_route_mae(
            sample_training_df,
            result["predicted_delay_s"],
            sample_training_df["actual_arrival_delay_seconds"],
        )
        assert isinstance(per_route, dict)
        assert len(per_route) > 0
        assert all(isinstance(v, float) for v in per_route.values())

    def test_per_route_mae_missing_column(self):
        """Returns empty dict when route_type column is missing."""
        df = pd.DataFrame({"x": [1, 2, 3]})
        preds = pd.Series([1.0, 2.0, 3.0])
        target = pd.Series([1.5, 2.5, 3.5])
        result = compute_per_route_mae(df, preds, target)
        assert result == {}


class TestSHAP:
    def test_shap_values_computable(self, trained_model, sample_training_df):
        """SHAP values can be computed for the median model."""
        import shap

        x = sample_training_df[ALL_FEATURES]
        x_transformed = trained_model.transformer.transform(x)
        explainer = shap.TreeExplainer(trained_model.models["q50"])
        values = explainer.shap_values(x_transformed[:5])
        assert np.asarray(values).shape[1] == len(ALL_FEATURES)
