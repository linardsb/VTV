"""One-shot traffic count and accident backfill (ML-1.3).

Fetches traffic census and accident data from Latvian open data
and upserts into the traffic_counts / traffic_accidents tables.

Usage:
    uv run python scripts/traffic_backfill.py --dry-run
    uv run python scripts/traffic_backfill.py
    uv run python scripts/traffic_backfill.py --type counts
    uv run python scripts/traffic_backfill.py --type accidents
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Allow `from app.*` imports when run via `uv run python scripts/...`
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Backfill traffic counts and accidents from open data"
    )
    parser.add_argument(
        "--type",
        choices=["counts", "accidents", "all"],
        default="all",
        help="Which dataset to backfill (default: all)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be fetched without writing to the database",
    )
    return parser.parse_args()


async def _main() -> None:
    """Run the traffic backfill."""
    args = _parse_args()

    from app.core.config import get_settings

    settings = get_settings()

    if args.dry_run:
        print(f"DRY RUN: Would backfill traffic data (type={args.type})")
        if args.type in ("counts", "all"):
            print(f"  Counts URL: {settings.traffic_counts_url or '(not set)'}")
        if args.type in ("accidents", "all"):
            print(f"  Accidents URL: {settings.traffic_accidents_url or '(not set)'}")
        return

    from app.transit.traffic_etl import backfill_traffic_accidents, backfill_traffic_counts

    total = 0
    if args.type in ("counts", "all"):
        count = await backfill_traffic_counts()
        print(f"Traffic counts: {count} records upserted")
        total += count

    if args.type in ("accidents", "all"):
        count = await backfill_traffic_accidents()
        print(f"Traffic accidents: {count} records upserted")
        total += count

    print(f"Backfill complete: {total} total records upserted")


if __name__ == "__main__":
    asyncio.run(_main())
