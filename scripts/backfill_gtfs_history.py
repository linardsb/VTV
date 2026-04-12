"""CLI entrypoint for historical GTFS archive backfill.

Downloads all available GTFS snapshots from data.gov.lv, deduplicates
via SHA-256, and stores each in snapshot-scoped shadow tables for ML
training. Resumable -- skips already-imported resources.

Usage:
    uv run python scripts/backfill_gtfs_history.py --dry-run
    uv run python scripts/backfill_gtfs_history.py --since 2024-01
    uv run python scripts/backfill_gtfs_history.py --since 2020-01 --until 2023-12
"""

from __future__ import annotations

import argparse
import asyncio
import datetime
import sys
from pathlib import Path

# Allow `from app.*` imports when run via `uv run python scripts/...`
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_settings
from app.core.logging import get_logger
from app.transit.historical_gtfs_importer import HistoricalGtfsImporter

logger = get_logger(__name__)


def _parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Backfill historical GTFS snapshots from data.gov.lv"
    )
    parser.add_argument(
        "--since",
        type=str,
        default=None,
        help="Only import snapshots from this month onward (YYYY-MM)",
    )
    parser.add_argument(
        "--until",
        type=str,
        default=None,
        help="Only import snapshots up to this month (YYYY-MM)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List available snapshots without importing",
    )
    return parser.parse_args()


def _parse_month(value: str) -> datetime.date:
    """Parse YYYY-MM to the first day of that month.

    Args:
        value: Month string in YYYY-MM format.

    Returns:
        First day of the specified month.

    Raises:
        ValueError: If format is invalid.
    """
    parts = value.split("-")
    if len(parts) != 2:
        msg = f"Expected YYYY-MM format, got: {value}"
        raise ValueError(msg)
    return datetime.date(int(parts[0]), int(parts[1]), 1)


async def _main() -> int:
    """Run the backfill and return exit code."""
    args = _parse_args()
    settings = get_settings()

    since_date: datetime.date | None = None
    until_date: datetime.date | None = None

    if args.since:
        since_date = _parse_month(args.since)
    if args.until:
        until_date = _parse_month(args.until)

    importer = HistoricalGtfsImporter(settings)
    try:
        progress = await importer.backfill(
            since_date=since_date,
            until_date=until_date,
            dry_run=args.dry_run,
        )
    finally:
        await importer.close()

    logger.info(
        "transit.backfill_cli.completed",
        total=progress.total_available,
        imported=progress.imported,
        skipped=progress.skipped_duplicate,
        failed=progress.failed,
        dry_run=args.dry_run,
    )

    if progress.failed > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
