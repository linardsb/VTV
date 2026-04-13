# Plan: ML-3.2 Load Prediction Model

## Context

Train a LightGBM gradient-boosted model predicting `expected_passenger_count` at (trip_id, stop_sequence) from load features produced by ML-3.1. Output includes a crowding bucket classification (empty/light/moderate/full/overcrowded). Same model architecture as ML-2.2 ETA (quantile regression + registry), but with load-specific features and a dual-head output: regression (passenger count) + classification (crowding bucket).

**Why:** Re-uses registry + training infra from ML-2.2, so ~2 days of 6-day budget is model-specific, not plumbing.

## Security Context Assessment

**No security contexts active.** This feature is entirely offline ML — no REST endpoints, no user input, no file uploads, no auth. CLI training script only.

## Research Summary

### Reference Pattern: `app/ml/models/eta_gbm.py` (300 lines)
- Feature lists (`CATEGORICAL_FEATURES`, `NUMERIC_FEATURES`, `ALL_FEATURES`) at lines 33-57
- `_build_transformer()` at line 60 — ColumnTransformer with StandardScaler + OrdinalEncoder
- `train()` at line 82 — main function, returns `(ETAModel, TrainingMetrics)`
- Three quantile regressors (q10, q50, q90) at lines 131-151
- `compute_per_route_mae()` at line 198 — fairness check
- `ETAModel` dataclass at line 225 — predict(), predict_batch(), save(), load()

### Load Feature Pipeline (ML-3.1, already implemented)
- `app/ml/features/load_features.py:134` — `extract_load_features(db, from_ts, to_ts, settings)` -> DataFrame
- Output columns: `gtfs_trip_id, stop_sequence, stop_id, date, hour, route_code, transport_type, tap_count, cumulative_load, capacity, load_factor_pct`
- `app/ml/features/load_validation.py` — Pandera schema for the DataFrame
- `app/ml/features/vehicle_capacity.py` — capacity lookup (bus=60, tram=200, trolleybus=80, articulated=100)

### Training CLI Pattern: `scripts/train_eta_model.py` (172 lines)
- argparse: `--training-window`, `--target-mae`, `--promote`, `--random-state`, `--dry-run`
- `_main()`: extract features -> train -> register -> optionally promote

### Registry: `app/ml/registry.py` (271 lines)
- `ModelRegistry.register()` at line 64, `.promote()` at line 131, `.next_version()` at line 255
- JSON-backed with atomic writes. Register as `"load_gbm"` model name.

### Existing Schemas: `app/ml/models/schemas.py` (41 lines)
- `TrainingMetrics(mae, rmse, p90_error, per_route_mae)` — reusable for count head
- `ModelMetadata(version, model_name, trained_at, ...)` — reusable as-is
- Need new: `LoadPrediction`, `LoadTrainingMetrics` (adds bucket F1)

## Test Landscape

### Existing ML Model Tests (`app/ml/models/tests/`)
- `conftest.py` — `sample_training_df` (200 rows), `trained_model` (session-scoped), `tmp_registry`, `registered_model`
- `test_eta_gbm.py` — 6 test classes: TestTrain (4), TestPredict (3), TestQuantileInterval (2), TestSaveLoad (3), TestPerRouteMAE (2), TestSHAP (1)
- `test_registry.py` — 13 test methods for register/load/promote/rollback

### Patterns to Mirror
- Factory: `make_eta_features_df(n)` from `app/ml/features/tests/conftest.py`
- Session-scoped `trained_model` fixture for speed
- `tmp_registry` fixture for isolated registry tests
- No `@pytest.mark.integration` in ML model tests — all pure unit tests with mocked deps

### Known Pre-existing Issues
- Missing test conftest factories: `make_correlated_tap`, `make_load_features_df` (referenced but undefined in `app/ml/features/tests/conftest.py`)
- These are ML-3.1 test gaps, NOT caused by this feature

## Type Check Baseline

| Tool | Errors | Files |
|------|--------|-------|
| **Pyright** | **25** | 43 |
| **Mypy** | **13** | 43 |

**Root causes (pre-existing, not caused by ML-3.2):**
1. Missing `Settings` attributes: `ml_load_time_window_seconds`, `ml_load_distance_threshold_m`, `ml_load_min_correlation_pct`, `anomaly_recent_window_hours`, `anomaly_cooldown_*` (~16 pyright / ~8 mypy errors)
2. Missing conftest factories: `make_correlated_tap`, `make_load_features_df` (~8 pyright / 2 mypy errors)
3. Pandera untyped call (1 each)

**Target:** New files must introduce 0 new pyright/mypy errors.

## Files to Create/Modify

| Action | File | Purpose |
|--------|------|---------|
| CREATE | `app/ml/models/load_gbm.py` | LightGBM load prediction model (mirror of eta_gbm.py) |
| CREATE | `scripts/train_load_model.py` | CLI for training load model |
| CREATE | `app/ml/models/tests/test_load_gbm.py` | 12+ unit tests |
| UPDATE | `app/ml/models/schemas.py` | Add `LoadPrediction`, `LoadTrainingMetrics`, `CrowdingBucket` |
| UPDATE | `app/ml/models/__init__.py` | Export new symbols |
| UPDATE | `app/ml/models/tests/conftest.py` | Add load model fixtures |
| UPDATE | `Makefile` | Add `ml-train-load` target |

## Implementation Steps

### Step 1: Add Load-Specific Schemas (`app/ml/models/schemas.py`)

Add after existing dataclasses:

```python
from typing import Literal

CrowdingBucket = Literal["empty", "light", "moderate", "full", "overcrowded"]


def crowding_bucket(load_factor_pct: float) -> CrowdingBucket:
    """Classify load factor into crowding bucket.

    Thresholds: <20% empty, 20-40% light, 40-70% moderate, 70-95% full, >95% overcrowded.
    """
    if load_factor_pct < 20.0:
        return "empty"
    if load_factor_pct < 40.0:
        return "light"
    if load_factor_pct < 70.0:
        return "moderate"
    if load_factor_pct < 95.0:
        return "full"
    return "overcrowded"


@dataclass(frozen=True)
class LoadTrainingMetrics:
    """Metrics from a load model training run (dual-head)."""

    count_mae: float          # MAE for passenger count regression
    count_rmse: float
    count_p90_error: float
    bucket_f1_macro: float    # F1-macro for crowding bucket classification
    per_route_mae: dict[str, float]  # route_code -> count MAE


@dataclass(frozen=True)
class LoadPrediction:
    """Single load prediction with confidence interval and crowding bucket."""

    predicted_passenger_count: float  # median (q50)
    confidence_lower: float           # q10
    confidence_upper: float           # q90
    crowding_bucket: CrowdingBucket
```

**Validation:** `uv run ruff format app/ml/models/schemas.py && uv run ruff check --fix app/ml/models/schemas.py && uv run pyright app/ml/models/schemas.py`

### Step 2: Create Load GBM Model (`app/ml/models/load_gbm.py`)

Mirror `eta_gbm.py` structure. Key differences:
- **Features:** Use load feature columns from ML-3.1 output (route_code, transport_type, hour, etc.)
- **Target:** `cumulative_load` (regression) + derived `crowding_bucket` (classification)
- **Dual-head:** Three quantile regressors for count (q10, q50, q90) + one LGBMClassifier for bucket
- **Metrics:** `LoadTrainingMetrics` with count MAE + bucket F1-macro

Feature lists:
```python
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
```

`train()` function:
1. Validate features using `load_validation.validate_load_features(df)` (create wrapper)
2. Derive `crowding_bucket` column from `load_factor_pct` using `crowding_bucket()`
3. Train 3 quantile regressors on `cumulative_load` (same as ETA)
4. Train 1 LGBMClassifier on `crowding_bucket` (5-class)
5. Compute dual-head metrics: count MAE/RMSE/P90 + bucket F1-macro
6. Per-route MAE via `compute_per_route_mae()` keyed on `route_code`
7. Return `(LoadModel, LoadTrainingMetrics)`

`LoadModel` dataclass:
- `transformer: Any` (ColumnTransformer)
- `models: dict[str, Any]` (q10, q50, q90 regressors)
- `classifier: Any` (LGBMClassifier)
- `feature_version: str`
- `predict(row_dict) -> LoadPrediction`
- `predict_batch(df) -> pd.DataFrame`
- `save(path) / load(path)` via joblib

**Validation:** `uv run ruff format app/ml/models/load_gbm.py && uv run ruff check --fix app/ml/models/load_gbm.py && uv run pyright app/ml/models/load_gbm.py`

### Step 3: Add Load Validation Wrapper

In `app/ml/features/load_validation.py`, add a `validate_load_features()` function parallel to `validate_features()` in `app/ml/features/validation.py`:

```python
def validate_load_features(df: pd.DataFrame) -> pd.DataFrame:
    """Validate load features DataFrame against schema."""
    result: Any = LOAD_FEATURES_SCHEMA.validate(df)
    return pd.DataFrame(result)
```

**Validation:** `uv run pyright app/ml/features/load_validation.py`

### Step 4: Create Training CLI (`scripts/train_load_model.py`)

Mirror `scripts/train_eta_model.py` exactly. Differences:
- `MODEL_NAME = "load_gbm"`
- Import `extract_load_features` from `app.ml.features.load_features`
- Import `train` from `app.ml.models.load_gbm`
- Import `FEATURE_VERSION, TARGET_COL` from `app.ml.models.load_gbm`
- `--target-mae` default: 12.0 (passengers, not seconds)
- Add `--target-f1` argument with default 0.75 (bucket F1-macro gate)
- Pass `settings` to `extract_load_features(db, from_ts, to_ts, settings)`
- Check both MAE and F1 targets for pass/fail

**Validation:** `uv run ruff format scripts/train_load_model.py && uv run ruff check --fix scripts/train_load_model.py && uv run pyright scripts/train_load_model.py`

### Step 5: Update `__init__.py` Exports (`app/ml/models/__init__.py`)

Add:
```python
from app.ml.models.load_gbm import LoadModel, train as train_load
from app.ml.models.schemas import CrowdingBucket, LoadPrediction, LoadTrainingMetrics
```

Update `__all__` list.

**Validation:** `uv run pyright app/ml/models/__init__.py`

### Step 6: Add Test Fixtures (`app/ml/models/tests/conftest.py`)

Add fixtures:
```python
def make_load_training_df(n: int = 200) -> pd.DataFrame:
    """Generate n rows of load feature data + target for training."""
    # Random but realistic: route_code from ["1", "3", "22", "47"], transport_type from ["bus", "tram"],
    # hour 0-23, stop_sequence 1-30, tap_count 1-15, capacity 60-200, load_factor_pct 0-100
    ...

@pytest.fixture()
def sample_load_training_df() -> pd.DataFrame:
    return make_load_training_df(200)

@pytest.fixture(scope="session")
def trained_load_model() -> LoadModel:
    df = make_load_training_df(200)
    model, _metrics = train_load(df, n_estimators=10, early_stopping_rounds=5)
    return model
```

**Validation:** `uv run pyright app/ml/models/tests/conftest.py`

### Step 7: Create Tests (`app/ml/models/tests/test_load_gbm.py`)

12+ tests across 6 test classes, mirroring `test_eta_gbm.py`:

```
TestTrain (4 tests):
  - test_training_smoke: train() returns (LoadModel, LoadTrainingMetrics)
  - test_reproducibility: same seed -> identical metrics
  - test_different_seeds: different results with different seeds
  - test_metrics_have_per_route_mae: per_route_mae is populated

TestPredict (3 tests):
  - test_single_prediction: returns LoadPrediction with valid fields
  - test_batch_prediction: returns DataFrame with expected columns
  - test_prediction_deterministic: same input -> same output

TestCrowdingBucket (5 tests):
  - test_bucket_empty: load_factor_pct < 20 -> "empty"
  - test_bucket_light: 20-40 -> "light"
  - test_bucket_moderate: 40-70 -> "moderate"
  - test_bucket_full: 70-95 -> "full"
  - test_bucket_overcrowded: >95 -> "overcrowded"

TestQuantileInterval (2 tests):
  - test_quantile_ordering: q10 <= q50 <= q90
  - test_interval_coverage: >50% of actuals fall within interval

TestSaveLoad (3 tests):
  - test_save_load_roundtrip
  - test_feature_version_preserved
  - test_save_creates_file

TestPerRouteFairness (2 tests):
  - test_per_route_mae_populated: different route_codes get entries
  - test_no_systematic_bias: no single route >3x overall MAE
```

**Validation:** `uv run pytest app/ml/models/tests/test_load_gbm.py -v`

### Step 8: Update Makefile

Add after `ml-train-eta` target (line 135):

```makefile
ml-train-load: ## Train load prediction model (usage: make ml-train-load WINDOW=60)
	uv run python scripts/train_load_model.py --training-window $(or $(WINDOW),60) --target-mae $(or $(TARGET_MAE),12) --target-f1 $(or $(TARGET_F1),0.75)
```

Add `ml-train-load` to `.PHONY` line.

**Validation:** `make -n ml-train-load` (dry run to verify target exists)

## Preflight Warnings

1. **Session-scoped fixture collision:** `trained_model` in conftest.py is session-scoped for ETA. `trained_load_model` must also be session-scoped but separate. Name conflict not possible since they return different types.
2. **Pre-existing type errors:** 25 pyright errors in `app/ml/` are NOT from this feature. Don't try to fix them.
3. **`make_eta_features_df` import path:** Test conftest imports from `app.ml.features.tests.conftest` — load fixtures should follow the same cross-conftest import pattern if needed, or be self-contained.
4. **Pandera untyped call:** `validate_load_features()` will need `# noqa: ANN401` on return type or explicit `Any` handling, same as ETA's `validate_features()`.

## Anti-Pattern Checklist (from python-anti-patterns.md)

- [ ] #1: No `assert` in production code
- [ ] #5: No unused imports
- [ ] #7: Test helpers have return type annotations
- [ ] #12: Untyped lib (lightgbm, sklearn) needs 3-layer fix: pyright directive, mypy override (already in pyproject.toml), ruff per-file-ignores
- [ ] #22: Dict literal types in tests need explicit annotation
- [ ] #28: Bare `[]` annotated as `list[type] = []`
- [ ] #33: `dict[str, Any]` not `dict[str, object]` for kwargs unpacking

## Verification

- [ ] `uv run ruff format app/ml/models/load_gbm.py app/ml/models/schemas.py scripts/train_load_model.py` passes
- [ ] `uv run ruff check app/ml/models/ scripts/train_load_model.py` passes
- [ ] `uv run pyright app/ml/models/load_gbm.py app/ml/models/schemas.py scripts/train_load_model.py` — 0 errors
- [ ] `uv run mypy app/ml/models/load_gbm.py app/ml/models/schemas.py scripts/train_load_model.py` — 0 errors
- [ ] `uv run pytest app/ml/models/tests/test_load_gbm.py -v` — all 12+ tests pass
- [ ] `uv run pytest app/ml/models/tests/ -v` — existing ETA tests still pass (no regression)
- [ ] Pyright errors in `app/ml/` <= 25 (baseline)
- [ ] `make -n ml-train-load` prints the correct command
- [ ] `make check` passes (full suite)
