# Plan: ML-2.2 Baseline Gradient Boosting Model

## Context

Train a LightGBM regression model predicting `actual_arrival_delay_seconds` from ML-2.1's 18-field ETAFeatures. Target MAE < 120s (vs ~300s naive baseline). Track versions, metrics, and artifacts via a lightweight in-repo model registry.

LightGBM is the right first model: fast on tabular data, native categorical support, interpretable via SHAP. No REST endpoints — this is an offline training pipeline + inference library consumed by future ML-2.3 online serving.

## Security Context Assessment

**No active security contexts.** This feature:
- Adds no REST endpoints (no CTX-RBAC, CTX-INPUT)
- Handles no file uploads (no CTX-FILE)
- Touches no auth flows (no CTX-AUTH)
- Is not an agent tool (no CTX-AGENT)
- Does not modify Docker/nginx/config infrastructure (no CTX-INFRA)

The only infrastructure change is adding dependencies to `pyproject.toml` and a config entry.

## Research Summary

### Existing ML Infrastructure
- **ETAFeatures dataclass:** `app/ml/features/eta_features.py:41-76` — 18-field frozen dataclass (8 categorical + 10 numeric)
- **Batch extraction:** `extract_features_batch(db, from_ts, to_ts) -> pd.DataFrame` — produces validated training matrix
- **Pandera validation:** `app/ml/features/validation.py` — `ETA_FEATURES_SCHEMA` + `validate_features()` + `detect_outliers()`
- **Feature CLI:** `app/ml/features/__main__.py` — reference pattern for training CLI
- **Anomaly module:** `app/ml/anomaly/` — reference for module structure, evaluator lifecycle, config pattern

### Directory State
- `app/ml/models/` — **does not exist** (to be created)
- `models/` at repo root — **does not exist** (to be created for artifacts)
- `models/registry.json` — **does not exist** (to be created)

### Dependencies Needed (not yet in pyproject.toml)
- `lightgbm>=4.0.0` — gradient boosting
- `scikit-learn>=1.4.0` — preprocessing, train/test split, metrics
- `shap>=0.46.0` — model interpretability (optional, for SHAP integration test)
- `joblib>=1.4.0` — model serialization (may already come as sklearn transitive dep)

### Config Pattern (from `app/core/config.py:267-273`)
ML settings use `ml_` prefix with boolean enable flags + numeric thresholds.

### Test Fixtures Available (from `app/ml/features/tests/conftest.py`)
- `make_eta_features_dict(**overrides)` — factory with 18 fields + defaults
- `make_eta_features_df(n=10, **overrides)` — DataFrame factory
- `make_mapping_result(rows)` — mock SQLAlchemy result proxy
- `sample_features_df` fixture — 5-row DataFrame

## Type Check Baseline

- **Pyright:** 0 errors on `app/ml/` (23 source files)
- **Mypy:** 0 errors on `app/ml/` (23 source files)
- **Existing mypy overrides:** `pandera.*` → `ignore_missing_imports`, `app.ml.features.validation` → `disallow_untyped_calls = false`

## Files to Create/Modify

| Action | File | Purpose |
|--------|------|---------|
| CREATE | `app/ml/models/__init__.py` | Package init, export public API |
| CREATE | `app/ml/models/eta_gbm.py` | LightGBM trainer + ETAModel with quantile predict |
| CREATE | `app/ml/models/schemas.py` | ETAPrediction dataclass, TrainingMetrics, ModelMetadata |
| CREATE | `app/ml/registry.py` | ModelRegistry class — JSON-based version tracking |
| CREATE | `app/ml/models/tests/__init__.py` | Test package |
| CREATE | `app/ml/models/tests/conftest.py` | Model-specific fixtures |
| CREATE | `app/ml/models/tests/test_eta_gbm.py` | Training + prediction tests |
| CREATE | `app/ml/models/tests/test_registry.py` | Registry promote/rollback/load tests |
| CREATE | `scripts/train_eta_model.py` | CLI: `--training-window`, `--target-mae`, `--promote` |
| CREATE | `models/.gitkeep` | Artifact directory (git-tracked but contents ignored) |
| UPDATE | `pyproject.toml` | Add lightgbm, scikit-learn, shap deps + mypy overrides |
| UPDATE | `.gitignore` | Add `models/*.pkl` pattern |
| UPDATE | `Makefile` | Add `ml-train-eta` target |

## Implementation Steps

### Step 1: Add dependencies and type checker config
**File:** `pyproject.toml`

Add to `dependencies`:
```
"lightgbm>=4.0.0",
"scikit-learn>=1.4.0",
"shap>=0.46.0",
"joblib>=1.4.0",
```

Add mypy overrides:
```toml
[[tool.mypy.overrides]]
module = "lightgbm.*"
ignore_missing_imports = true

[[tool.mypy.overrides]]
module = "sklearn.*"
ignore_missing_imports = true

[[tool.mypy.overrides]]
module = "shap.*"
ignore_missing_imports = true

[[tool.mypy.overrides]]
module = "joblib.*"
ignore_missing_imports = true
```

**Validation:** `uv sync && uv run python -c "import lightgbm; import sklearn; import shap; import joblib; print('OK')"`

### Step 2: Create artifact directory + gitignore
**File:** `models/.gitkeep` (empty file), `.gitignore`

Add to `.gitignore`:
```
# ML model artifacts (tracked via models/registry.json)
models/*.pkl
models/*.joblib
```

Create `models/registry.json` (committed):
```json
{
  "models": {}
}
```

**Validation:** `ls models/ && git check-ignore models/test.pkl`

### Step 3: Create schemas (`app/ml/models/schemas.py`)

Frozen dataclasses for ML-2.2 data structures:

```python
@dataclass(frozen=True)
class ETAPrediction:
    predicted_delay_s: float       # median (quantile 0.5)
    confidence_lower: float        # quantile 0.1
    confidence_upper: float        # quantile 0.9

@dataclass(frozen=True)
class TrainingMetrics:
    mae: float
    rmse: float
    p90_error: float
    per_route_mae: dict[str, float]  # route_id -> MAE

@dataclass(frozen=True)
class ModelMetadata:
    version: int
    model_name: str
    trained_at: str                # ISO 8601
    training_window_days: int
    training_rows: int
    feature_version: str           # "ml-2.1-v1"
    metrics: TrainingMetrics
```

Use `from __future__ import annotations`. All fields typed. No Pydantic (these are internal data structures, not API schemas).

**Validation:** `uv run ruff format app/ml/models/schemas.py && uv run ruff check --fix app/ml/models/schemas.py && uv run pyright app/ml/models/schemas.py`

### Step 4: Create model registry (`app/ml/registry.py`)

`ModelRegistry` class:
- `__init__(registry_path: Path = Path("models/registry.json"))` — loads JSON on init
- `register(name: str, version: int, metadata: ModelMetadata, artifact_path: Path) -> None` — writes metadata entry
- `load_latest(name: str) -> tuple[Any, ModelMetadata]` — loads most recent version's pkl + metadata. Uses `joblib.load()`. In-memory LRU cache (1 entry per model name via `@functools.lru_cache` or manual dict).
- `promote(name: str, version: int) -> None` — sets "production" pointer in registry
- `get_production(name: str) -> tuple[Any, ModelMetadata] | None` — loads promoted version
- `rollback(name: str) -> None` — removes production pointer
- `_save() -> None` — writes registry JSON atomically (write to tmp, rename)

Registry JSON structure:
```json
{
  "models": {
    "eta_gbm": {
      "versions": {
        "1": { "trained_at": "...", "metrics": {...}, "artifact": "models/eta_gbm_v1.pkl", ... },
        "2": { ... }
      },
      "production": 1
    }
  }
}
```

File-level pyright directive: `# pyright: reportUnknownMemberType=false` (joblib returns Any).

Mypy: use `Any` return for `joblib.load()` with `# noqa: ANN401` on the method.

Structured logging: `ml.registry.model_registered`, `ml.registry.model_promoted`, `ml.registry.model_loaded`.

**Validation:** `uv run ruff format app/ml/registry.py && uv run ruff check --fix app/ml/registry.py && uv run pyright app/ml/registry.py && uv run mypy app/ml/registry.py`

### Step 5: Create LightGBM trainer + model (`app/ml/models/eta_gbm.py`)

File-level pyright directives: `# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false` (lightgbm + sklearn are untyped).

#### Constants
```python
CATEGORICAL_FEATURES: list[str] = [
    "day_of_week", "month", "is_school_day", "is_holiday",
    "weather_bucket", "route_type", "direction", "operator",
]
NUMERIC_FEATURES: list[str] = [
    "time_of_day_hour", "scheduled_headway_s", "historical_avg_delay_at_stop_s",
    "prev_stop_actual_delay_s", "trip_elapsed_pct", "temp_c", "wind_mps",
    "precip_mm_last_hr", "traffic_count_rolling_7d", "accident_count_within_500m",
]
ALL_FEATURES: list[str] = CATEGORICAL_FEATURES + NUMERIC_FEATURES
TARGET_COL: str = "actual_arrival_delay_seconds"
FEATURE_VERSION: str = "ml-2.1-v1"
```

#### `train()` function
```python
def train(
    df: pd.DataFrame,
    target_col: str = TARGET_COL,
    val_split: float = 0.2,
    random_state: int = 42,
    n_estimators: int = 500,
    early_stopping_rounds: int = 50,
) -> tuple[ETAModel, TrainingMetrics]:
```

Implementation:
1. Validate features with `validate_features()` from ML-2.1
2. Split with `sklearn.model_selection.train_test_split(stratify=None)` using `random_state`
3. Build `sklearn.compose.ColumnTransformer`:
   - Numeric: `sklearn.preprocessing.StandardScaler` on `NUMERIC_FEATURES`
   - Categorical: `sklearn.preprocessing.OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1)` on `CATEGORICAL_FEATURES`
4. Train 3 LightGBM models (quantiles 0.1, 0.5, 0.9):
   - `lightgbm.LGBMRegressor(objective="quantile", alpha=q, n_estimators=n_estimators, ...)`
   - Use `callbacks=[lightgbm.early_stopping(early_stopping_rounds)]` + `eval_set=[(X_val, y_val)]`
5. Compute metrics on validation set: MAE, RMSE, P90 error, per-route MAE
6. Return `ETAModel` wrapper + `TrainingMetrics`

Structured logging: `ml.eta.training_started`, `ml.eta.training_completed`, `ml.eta.validation_metrics`.

#### `ETAModel` class
```python
@dataclass
class ETAModel:
    transformer: ColumnTransformer
    models: dict[str, LGBMRegressor]  # {"q10": ..., "q50": ..., "q90": ...}
    feature_version: str = FEATURE_VERSION

    def predict(self, features: ETAFeatures) -> ETAPrediction:
        """Single-row prediction from frozen dataclass."""
        # Convert to DataFrame row via asdict()
        # Transform + predict with all 3 quantile models
        # Return ETAPrediction(predicted_delay_s, confidence_lower, confidence_upper)

    def predict_batch(self, df: pd.DataFrame) -> pd.DataFrame:
        """Batch prediction returning DataFrame with prediction columns."""
        # Transform + predict with all 3 models
        # Return df with added columns: predicted_delay_s, confidence_lower, confidence_upper

    def save(self, path: Path) -> None:
        """Serialize model to disk via joblib."""
        joblib.dump({"transformer": self.transformer, "models": self.models, "feature_version": self.feature_version}, path)

    @classmethod
    def load(cls, path: Path) -> ETAModel:
        """Deserialize model from disk."""
        data = joblib.load(path)
        return cls(transformer=data["transformer"], models=data["models"], feature_version=data["feature_version"])
```

#### Per-route MAE fairness check
```python
def compute_per_route_mae(df: pd.DataFrame, predictions: pd.Series, target: pd.Series) -> dict[str, float]:
    """Compute MAE per route_type for fairness checking."""
```

**Validation:** `uv run ruff format app/ml/models/eta_gbm.py && uv run ruff check --fix app/ml/models/eta_gbm.py && uv run pyright app/ml/models/eta_gbm.py && uv run mypy app/ml/models/eta_gbm.py`

### Step 6: Create `app/ml/models/__init__.py`

```python
"""LightGBM ETA prediction model (ML-2.2)."""

from app.ml.models.eta_gbm import ETAModel, train
from app.ml.models.schemas import ETAPrediction, ModelMetadata, TrainingMetrics

__all__ = ["ETAModel", "ETAPrediction", "ModelMetadata", "TrainingMetrics", "train"]
```

**Validation:** `uv run pyright app/ml/models/__init__.py`

### Step 7: Create training CLI (`scripts/train_eta_model.py`)

Follow `app/ml/features/__main__.py` pattern:

```python
"""CLI for training ETA gradient boosting model (ML-2.2).

Usage:
    uv run python scripts/train_eta_model.py --training-window 60 --target-mae 120
    uv run python scripts/train_eta_model.py --training-window 60 --target-mae 120 --promote
    uv run python scripts/train_eta_model.py --training-window 60 --dry-run
"""
```

Arguments:
- `--training-window` (required): Days of training data (e.g., 60)
- `--target-mae` (default 120): Max acceptable MAE in seconds
- `--promote`: Auto-promote model to production if MAE target met
- `--random-state` (default 42): Reproducibility seed
- `--dry-run`: Log extraction plan without training

Flow:
1. Parse args, setup logging
2. Compute date range: `to_ts = utcnow()`, `from_ts = to_ts - timedelta(days=training_window)`
3. Extract features via `extract_features_batch(db, from_ts, to_ts)`
4. Validate features via `validate_features(df)`
5. Call `train(df, target_col=TARGET_COL, random_state=args.random_state)`
6. Log metrics, check MAE < target_mae
7. Determine next version from registry
8. Save model to `models/eta_gbm_v{N}.pkl`
9. Register in registry
10. If `--promote` and MAE target met, promote version
11. Exit 0 on success, 1 if MAE exceeds target

Add `scripts/train_eta_model.py` to ruff per-file-ignores (T201 for print — already covered by `scripts/**/*.py` pattern).

**Validation:** `uv run ruff format scripts/train_eta_model.py && uv run ruff check --fix scripts/train_eta_model.py && uv run pyright scripts/train_eta_model.py`

### Step 8: Add Makefile target

```makefile
ml-train-eta: ## Train ETA model (usage: make ml-train-eta WINDOW=60)
	uv run python scripts/train_eta_model.py --training-window $(or $(WINDOW),60) --target-mae $(or $(TARGET_MAE),120)
```

**Validation:** `make help | grep ml-train-eta`

### Step 9: Create test conftest (`app/ml/models/tests/conftest.py`)

Fixtures:
- `sample_training_df()` — 200-row DataFrame with all 18 features + `actual_arrival_delay_seconds` target column (realistic distribution: mean ~60s, std ~90s, some negative = early)
- `trained_model()` — pre-trained ETAModel on sample data (session-scoped for speed)
- `tmp_registry(tmp_path)` — ModelRegistry pointing at temp directory
- `tmp_model_path(tmp_path)` — temp path for model artifacts

Reuse `make_eta_features_df` from `app/ml/features/tests/conftest.py`.

**Validation:** `uv run ruff format app/ml/models/tests/conftest.py && uv run ruff check --fix app/ml/models/tests/conftest.py`

### Step 10: Create model tests (`app/ml/models/tests/test_eta_gbm.py`)

15+ tests organized by class:

```python
class TestTrain:
    def test_training_smoke(self, sample_training_df):
        """Train completes and returns ETAModel + metrics."""
        model, metrics = train(sample_training_df, n_estimators=10)
        assert isinstance(model, ETAModel)
        assert metrics.mae > 0

    def test_reproducibility(self, sample_training_df):
        """Same seed produces identical metrics."""
        _, m1 = train(sample_training_df, random_state=42, n_estimators=10)
        _, m2 = train(sample_training_df, random_state=42, n_estimators=10)
        assert m1.mae == m2.mae

class TestPredict:
    def test_single_prediction(self, trained_model):
        """predict() returns ETAPrediction with valid bounds."""
        features = ETAFeatures(**make_eta_features_dict())
        pred = trained_model.predict(features)
        assert isinstance(pred, ETAPrediction)
        assert pred.confidence_lower <= pred.predicted_delay_s <= pred.confidence_upper

    def test_batch_prediction(self, trained_model, sample_training_df):
        """predict_batch() returns DataFrame with prediction columns."""
        result = trained_model.predict_batch(sample_training_df)
        assert "predicted_delay_s" in result.columns
        assert len(result) == len(sample_training_df)

class TestQuantileInterval:
    def test_quantile_ordering(self, trained_model, sample_training_df):
        """q10 <= q50 <= q90 for all predictions."""
        result = trained_model.predict_batch(sample_training_df)
        assert (result["confidence_lower"] <= result["predicted_delay_s"]).all()
        assert (result["predicted_delay_s"] <= result["confidence_upper"]).all()

    def test_interval_coverage(self, trained_model, sample_training_df):
        """80% interval should cover ~80% of actuals (approx, on training data)."""
        result = trained_model.predict_batch(sample_training_df)
        target = sample_training_df["actual_arrival_delay_seconds"]
        in_interval = ((target >= result["confidence_lower"]) & (target <= result["confidence_upper"])).mean()
        assert in_interval > 0.5  # Relaxed bound for small sample

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

class TestPerRouteMAE:
    def test_per_route_mae_computation(self, trained_model, sample_training_df):
        """Per-route MAE returns dict with route_type keys."""
        result = trained_model.predict_batch(sample_training_df)
        per_route = compute_per_route_mae(
            sample_training_df, result["predicted_delay_s"],
            sample_training_df["actual_arrival_delay_seconds"]
        )
        assert isinstance(per_route, dict)
        assert len(per_route) > 0

class TestSHAP:
    def test_shap_values_computable(self, trained_model, sample_training_df):
        """SHAP values can be computed for the median model."""
        import shap
        X = sample_training_df[ALL_FEATURES]
        X_transformed = trained_model.transformer.transform(X)
        explainer = shap.TreeExplainer(trained_model.models["q50"])
        values = explainer.shap_values(X_transformed[:5])
        assert values.shape[1] == len(ALL_FEATURES)
```

**Validation:** `uv run pytest app/ml/models/tests/test_eta_gbm.py -v`

### Step 11: Create registry tests (`app/ml/models/tests/test_registry.py`)

```python
class TestModelRegistry:
    def test_register_model(self, tmp_registry, trained_model, tmp_model_path):
        """register() persists metadata to JSON."""

    def test_load_latest(self, tmp_registry, trained_model, tmp_model_path):
        """load_latest() returns most recent version."""

    def test_load_latest_nonexistent(self, tmp_registry):
        """load_latest() for unknown model raises KeyError."""

    def test_promote(self, tmp_registry, trained_model, tmp_model_path):
        """promote() sets production pointer."""

    def test_get_production(self, tmp_registry, trained_model, tmp_model_path):
        """get_production() returns promoted model."""

    def test_rollback(self, tmp_registry, trained_model, tmp_model_path):
        """rollback() removes production pointer."""

    def test_multiple_versions(self, tmp_registry, trained_model, tmp_path):
        """Registry tracks multiple versions independently."""

    def test_feature_version_mismatch_warning(self, tmp_registry):
        """Loading model with different feature_version logs warning."""
```

**Validation:** `uv run pytest app/ml/models/tests/test_registry.py -v`

### Step 12: Install dependencies and run full validation

```bash
uv sync
uv run ruff format app/ml/ scripts/train_eta_model.py
uv run ruff check --fix app/ml/ scripts/train_eta_model.py
uv run mypy app/ml/
uv run pyright app/ml/
uv run pytest app/ml/models/tests/ -v
uv run pytest app/ml/ -v  # Ensure existing tests still pass
```

## Preflight Warnings

- **Untyped libraries:** lightgbm, scikit-learn, shap, and joblib all lack `py.typed`. Must add mypy `[[overrides]]` for each AND use pyright file-level directives on every file importing them.
- **Anti-pattern #12:** Three-layer fix needed on FIRST PASS for all untyped libs: (a) mypy overrides, (b) pyright file-level directives, (c) ruff per-file-ignores if needed.
- **Anti-pattern #5:** No unused imports — only import lightgbm/sklearn/shap in files that use them.
- **Anti-pattern #22:** Dict literal types in tests must match function param types exactly.
- **Anti-pattern #28:** Bare `[]` list literals need type annotations.
- **Frozen dataclass fields:** Use `field(default_factory=...)` only if needed (anti-pattern #24).
- **`make_eta_features_dict()` returns `dict[str, Any]`** — reuse existing factory, don't recreate.
- **scripts/ files:** Already have `T201` (print) allowed via `scripts/**/*.py` per-file-ignores.

## Security Checklist

N/A — no REST endpoints, no user input handling, no file uploads. Internal ML training pipeline only.

## Verification

- [ ] `uv sync` installs lightgbm, scikit-learn, shap, joblib
- [ ] `uv run python -c "import lightgbm; import sklearn; import shap; import joblib"` succeeds
- [ ] `uv run ruff check app/ml/ scripts/train_eta_model.py` — 0 errors
- [ ] `uv run mypy app/ml/` — 0 errors (baseline: 0)
- [ ] `uv run pyright app/ml/` — 0 errors (baseline: 0)
- [ ] `uv run pytest app/ml/ -v` — all tests pass (existing + new)
- [ ] `uv run pytest app/ml/models/tests/ -v` — 15+ new tests pass
- [ ] `make help | grep ml-train-eta` — target visible
- [ ] `models/registry.json` exists and is valid JSON
- [ ] `git check-ignore models/test.pkl` returns the path (gitignored)
- [ ] `make security-audit-quick` passes
