# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""CLI for training load prediction gradient boosting model (ML-3.2).

Usage:
    uv run python scripts/train_load_model.py --training-window 60 --target-mae 12
    uv run python scripts/train_load_model.py --training-window 60 --target-mae 12 --promote
    uv run python scripts/train_load_model.py --training-window 60 --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import datetime
import sys
from pathlib import Path

from app.core.config import get_settings
from app.core.database import get_db_context
from app.core.logging import get_logger, setup_logging
from app.ml.features.load_features import extract_load_features
from app.ml.models.load_gbm import FEATURE_VERSION, TARGET_COL, train
from app.ml.models.schemas import ModelMetadata
from app.ml.registry import ModelRegistry
from app.shared.models import utcnow

logger = get_logger(__name__)

MODEL_NAME = "load_gbm"


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for model training.

    Args:
        argv: Argument list (defaults to sys.argv[1:]).

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(
        description="Train load prediction gradient boosting model (ML-3.2).",
    )
    parser.add_argument(
        "--training-window",
        type=int,
        required=True,
        help="Days of training data (e.g., 60)",
    )
    parser.add_argument(
        "--target-mae",
        type=float,
        default=12.0,
        help="Max acceptable MAE in passengers (default: 12)",
    )
    parser.add_argument(
        "--target-f1",
        type=float,
        default=0.75,
        help="Min acceptable bucket F1-macro (default: 0.75)",
    )
    parser.add_argument(
        "--promote",
        action="store_true",
        help="Auto-promote model to production if targets met",
    )
    parser.add_argument(
        "--random-state",
        type=int,
        default=42,
        help="Reproducibility seed (default: 42)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log extraction plan without training",
    )
    return parser.parse_args(argv)


async def _main(argv: list[str] | None = None) -> int:
    """Run load model training pipeline.

    Args:
        argv: CLI argument list (for testing).

    Returns:
        Exit code (0 = success, 1 = targets not met).
    """
    args = _parse_args(argv)
    settings = get_settings()

    setup_logging()

    now = utcnow()
    from_ts = now - datetime.timedelta(days=args.training_window)
    to_ts = now

    logger.info(
        "ml.load_training.cli_started",
        training_window=args.training_window,
        target_mae=args.target_mae,
        target_f1=args.target_f1,
        from_ts=str(from_ts),
        to_ts=str(to_ts),
        dry_run=args.dry_run,
    )

    if args.dry_run:
        print(f"DRY RUN: Would extract load features from {from_ts} to {to_ts}")
        print(f"  Training window: {args.training_window} days")
        print(f"  Target MAE: {args.target_mae} passengers")
        print(f"  Target F1-macro: {args.target_f1}")
        return 0

    # Extract features
    async with get_db_context() as db:
        df = await extract_load_features(db, from_ts, to_ts, settings)

    if len(df) == 0:
        print("ERROR: No training data found in the specified window.")
        logger.error(
            "ml.load_training.no_data",
            from_ts=str(from_ts),
            to_ts=str(to_ts),
        )
        return 1

    # Verify target column exists
    if TARGET_COL not in df.columns:
        print(f"ERROR: Target column '{TARGET_COL}' not found in extracted features.")
        logger.error("ml.load_training.missing_target_column", target_col=TARGET_COL)
        return 1

    print(f"Extracted {len(df)} training rows")

    # Train model
    model, metrics = train(df, target_col=TARGET_COL, random_state=args.random_state)

    print(f"  Count MAE:    {metrics.count_mae:.1f} passengers")
    print(f"  Count RMSE:   {metrics.count_rmse:.1f} passengers")
    print(f"  Count P90:    {metrics.count_p90_error:.1f} passengers")
    print(f"  Bucket F1:    {metrics.bucket_f1_macro:.3f}")

    # Check targets
    mae_ok = metrics.count_mae <= args.target_mae
    f1_ok = metrics.bucket_f1_macro >= args.target_f1
    targets_met = mae_ok and f1_ok

    if not mae_ok:
        print(f"WARNING: MAE {metrics.count_mae:.1f} exceeds target {args.target_mae}")
    if not f1_ok:
        print(f"WARNING: F1 {metrics.bucket_f1_macro:.3f} below target {args.target_f1}")

    # Register in registry — use TrainingMetrics-compatible metadata
    # LoadTrainingMetrics doesn't match ModelMetadata.metrics type, so we
    # store count metrics in the standard TrainingMetrics format
    from app.ml.models.schemas import TrainingMetrics

    registry = ModelRegistry()
    version = registry.next_version(MODEL_NAME)
    artifact_path = Path(f"models/{MODEL_NAME}_v{version}.pkl")
    model.save(artifact_path)

    compat_metrics = TrainingMetrics(
        mae=metrics.count_mae,
        rmse=metrics.count_rmse,
        p90_error=metrics.count_p90_error,
        per_route_mae=metrics.per_route_mae,
    )
    metadata = ModelMetadata(
        version=version,
        model_name=MODEL_NAME,
        trained_at=now.isoformat(),
        training_window_days=args.training_window,
        training_rows=len(df),
        feature_version=FEATURE_VERSION,
        metrics=compat_metrics,
    )
    registry.register(MODEL_NAME, version, metadata, artifact_path)
    print(f"Registered as {MODEL_NAME} v{version} -> {artifact_path}")

    # Promote if requested and targets met
    if args.promote and targets_met:
        registry.promote(MODEL_NAME, version)
        print(f"Promoted {MODEL_NAME} v{version} to production")
    elif args.promote and not targets_met:
        print("Skipping promotion: targets not met")

    return 0 if targets_met else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
