# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""CLI for training ETA gradient boosting model (ML-2.2).

Usage:
    uv run python scripts/train_eta_model.py --training-window 60 --target-mae 120
    uv run python scripts/train_eta_model.py --training-window 60 --target-mae 120 --promote
    uv run python scripts/train_eta_model.py --training-window 60 --dry-run
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
from app.ml.features.eta_features import extract_features_batch
from app.ml.models.eta_gbm import FEATURE_VERSION, TARGET_COL, train
from app.ml.models.schemas import ModelMetadata
from app.ml.registry import ModelRegistry
from app.shared.models import utcnow

logger = get_logger(__name__)

MODEL_NAME = "eta_gbm"


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for model training.

    Args:
        argv: Argument list (defaults to sys.argv[1:]).

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(
        description="Train ETA gradient boosting model (ML-2.2).",
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
        default=120.0,
        help="Max acceptable MAE in seconds (default: 120)",
    )
    parser.add_argument(
        "--promote",
        action="store_true",
        help="Auto-promote model to production if MAE target met",
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
    """Run ETA model training pipeline.

    Args:
        argv: CLI argument list (for testing).

    Returns:
        Exit code (0 = success, 1 = MAE exceeds target).
    """
    args = _parse_args(argv)
    settings = get_settings()
    _ = settings  # referenced for setup_logging context

    setup_logging()

    now = utcnow()
    from_ts = now - datetime.timedelta(days=args.training_window)
    to_ts = now

    logger.info(
        "ml.training.cli_started",
        training_window=args.training_window,
        target_mae=args.target_mae,
        from_ts=str(from_ts),
        to_ts=str(to_ts),
        dry_run=args.dry_run,
    )

    if args.dry_run:
        print(f"DRY RUN: Would extract features from {from_ts} to {to_ts}")
        print(f"  Training window: {args.training_window} days")
        print(f"  Target MAE: {args.target_mae}s")
        return 0

    # Extract features
    async with get_db_context() as db:
        df = await extract_features_batch(db, from_ts, to_ts)

    if len(df) == 0:
        print("ERROR: No training data found in the specified window.")
        logger.error(
            "ml.training.no_data",
            from_ts=str(from_ts),
            to_ts=str(to_ts),
        )
        return 1

    # Verify target column exists
    if TARGET_COL not in df.columns:
        print(f"ERROR: Target column '{TARGET_COL}' not found in extracted features.")
        logger.error("ml.training.missing_target_column", target_col=TARGET_COL)
        return 1

    print(f"Extracted {len(df)} training rows")

    # Train model
    model, metrics = train(df, target_col=TARGET_COL, random_state=args.random_state)

    print(f"  MAE:  {metrics.mae:.1f}s")
    print(f"  RMSE: {metrics.rmse:.1f}s")
    print(f"  P90:  {metrics.p90_error:.1f}s")

    # Check MAE target
    mae_ok = metrics.mae <= args.target_mae
    if not mae_ok:
        print(f"WARNING: MAE {metrics.mae:.1f}s exceeds target {args.target_mae}s")

    # Register in registry
    registry = ModelRegistry()
    version = registry.next_version(MODEL_NAME)
    artifact_path = Path(f"models/{MODEL_NAME}_v{version}.pkl")
    model.save(artifact_path)

    metadata = ModelMetadata(
        version=version,
        model_name=MODEL_NAME,
        trained_at=now.isoformat(),
        training_window_days=args.training_window,
        training_rows=len(df),
        feature_version=FEATURE_VERSION,
        metrics=metrics,
    )
    registry.register(MODEL_NAME, version, metadata, artifact_path)
    print(f"Registered as {MODEL_NAME} v{version} -> {artifact_path}")

    # Promote if requested and MAE target met
    if args.promote and mae_ok:
        registry.promote(MODEL_NAME, version)
        print(f"Promoted {MODEL_NAME} v{version} to production")
    elif args.promote and not mae_ok:
        print("Skipping promotion: MAE target not met")

    return 0 if mae_ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
