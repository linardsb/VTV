"""Backfill e-ticket validation data from Rigas Satiksme monthly archives.

Imports semicolon-delimited TXT files from ZIP archives into the
eticket_validations TimescaleDB hypertable. Supports single-month
or full backfill (2018-01 to present). Resume-safe via tracking table.

Usage:
    uv run python scripts/backfill_eticket_data.py --month 2026-01
    uv run python scripts/backfill_eticket_data.py --all
    uv run python scripts/backfill_eticket_data.py --all --dry-run
    uv run python scripts/backfill_eticket_data.py --month 2026-01 --batch-size 10000
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
import time
from pathlib import Path

# Allow `from app.*` imports when run via `uv run python scripts/...`
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_settings
from app.core.database import get_db_context
from app.transit.eticket_importer import (
    backfill_all,
    build_archive_url,
    import_monthly_archive,
)

_MONTH_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def _parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Backfill e-ticket validation data from Rigas Satiksme archives. "
            "Use --month for a single month or --all for full backfill (2018-01 to present)."
        ),
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--month",
        type=str,
        help="Single month to import (YYYY-MM format, e.g., 2026-01).",
    )
    group.add_argument(
        "--all",
        action="store_true",
        help="Import all months from 2018-01 to current month.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and count records without inserting into the database.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help="Override the default batch size for bulk inserts.",
    )
    return parser.parse_args()


async def main(args: argparse.Namespace) -> int:
    """Run the e-ticket backfill pipeline.

    Returns:
        Exit code: 0 on success, 1 on error.
    """
    settings = get_settings()

    if args.batch_size is not None:
        settings.eticket_batch_size = args.batch_size

    start = time.monotonic()
    total_records = 0

    try:
        async with get_db_context() as db:
            if args.all:
                total_records = await backfill_all(
                    db=db,
                    settings=settings,
                    dry_run=args.dry_run,
                )
            else:
                if not _MONTH_PATTERN.match(args.month):
                    print(f"ERROR: Invalid month format: {args.month!r} (expected YYYY-MM)")
                    return 1

                url = build_archive_url(
                    settings.eticket_archive_base_url,
                    args.month,
                )
                total_records = await import_monthly_archive(
                    url,
                    args.month,
                    db=db,
                    settings=settings,
                    dry_run=args.dry_run,
                )
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1

    elapsed = time.monotonic() - start
    mode = "DRY RUN" if args.dry_run else "IMPORTED"
    print(f"\n{mode}: {total_records:,} records in {elapsed:.1f}s")
    return 0


if __name__ == "__main__":
    parsed_args = _parse_args()
    raise SystemExit(asyncio.run(main(parsed_args)))
