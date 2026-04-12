"""One-shot historical weather observation backfill (ML-1.3).

Fetches archive weather data from data.gov.lv and upserts into
the weather_observations table.

Usage:
    uv run python scripts/weather_backfill.py --dry-run
    uv run python scripts/weather_backfill.py
    uv run python scripts/weather_backfill.py --days 30
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
        description="Backfill historical weather observations from data.gov.lv"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=365,
        help="Number of days of history to fetch (default: 365)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be fetched without writing to the database",
    )
    return parser.parse_args()


async def _main() -> None:
    """Run the weather backfill."""
    args = _parse_args()

    from app.core.config import get_settings

    settings = get_settings()

    if not settings.weather_observations_url:
        print("ERROR: WEATHER_OBSERVATIONS_URL not configured")
        sys.exit(1)

    if args.dry_run:
        print(f"DRY RUN: Would backfill {args.days} days of weather observations")
        print(f"  Observations URL: {settings.weather_observations_url}")
        print(f"  Phenomena URL: {settings.weather_phenomena_url or '(not set)'}")
        return

    from app.transit.weather_etl import backfill_weather

    count = await backfill_weather(days=args.days)
    print(f"Backfill complete: {count} records upserted")


if __name__ == "__main__":
    asyncio.run(_main())
