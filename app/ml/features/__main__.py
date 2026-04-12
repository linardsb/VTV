# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false
"""CLI entry point for ETA feature extraction (ML-2.1).

Usage:
    python -m app.ml.features --from 2026-03-01 --to 2026-03-31 --out /tmp/features.parquet
    python -m app.ml.features --from 2026-03-01 --to 2026-03-31 --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import datetime
import sys

from app.core.config import get_settings
from app.core.database import get_db_context
from app.core.logging import get_logger, setup_logging
from app.ml.features.eta_features import extract_features_batch

logger = get_logger(__name__)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for feature extraction.

    Args:
        argv: Argument list (defaults to sys.argv[1:]).

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(
        description="Extract ETA features from vehicle position data (ML-2.1).",
    )
    parser.add_argument(
        "--from",
        dest="from_date",
        required=True,
        help="Start date (YYYY-MM-DD, inclusive)",
    )
    parser.add_argument(
        "--to",
        dest="to_date",
        required=True,
        help="End date (YYYY-MM-DD, exclusive)",
    )
    parser.add_argument(
        "--out",
        dest="output_path",
        default=None,
        help="Output Parquet file path (default: print summary only)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log extraction plan without executing",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Run Pandera schema validation after extraction",
    )
    return parser.parse_args(argv)


async def _main(argv: list[str] | None = None) -> int:
    """Run ETA feature extraction pipeline.

    Args:
        argv: CLI argument list (for testing).

    Returns:
        Exit code (0 = success, 1 = error).
    """
    args = _parse_args(argv)
    settings = get_settings()
    _ = settings  # referenced for setup_logging context

    setup_logging()

    from_ts = datetime.datetime.strptime(args.from_date, "%Y-%m-%d").replace(tzinfo=datetime.UTC)
    to_ts = datetime.datetime.strptime(args.to_date, "%Y-%m-%d").replace(tzinfo=datetime.UTC)

    logger.info(
        "ml.features.cli_started",
        from_ts=str(from_ts),
        to_ts=str(to_ts),
        output_path=args.output_path,
        dry_run=args.dry_run,
        validate=args.validate,
    )

    if args.dry_run:
        logger.info(
            "ml.features.cli_dry_run",
            from_ts=str(from_ts),
            to_ts=str(to_ts),
            message="Would extract features for this date range",
        )
        return 0

    async with get_db_context() as db:
        df = await extract_features_batch(db, from_ts, to_ts)

    logger.info("ml.features.cli_extraction_done", row_count=len(df))

    if args.validate and len(df) > 0:
        from app.ml.features.validation import validate_features

        validate_features(df)
        logger.info("ml.features.cli_validation_passed", row_count=len(df))

    if args.output_path and len(df) > 0:
        df.to_parquet(args.output_path, index=False)
        logger.info("ml.features.cli_parquet_written", path=args.output_path, row_count=len(df))
    elif len(df) > 0:
        logger.info(
            "ml.features.cli_summary",
            row_count=len(df),
            columns=list(df.columns),
            dtypes={col: str(dtype) for col, dtype in df.dtypes.items()},
        )
    else:
        logger.warning("ml.features.cli_no_data", from_ts=str(from_ts), to_ts=str(to_ts))

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
