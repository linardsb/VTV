"""Docker migration entrypoint with self-healing.

Runs alembic upgrade head, then verifies tables actually exist.
If tables are missing (stale alembic_version stamp), resets and re-runs.
Optionally auto-imports GTFS data if the routes table is empty.
"""

import asyncio
import os
import subprocess
import sys
import urllib.request
from pathlib import Path


def run_alembic_upgrade() -> int:
    """Run alembic upgrade head and return exit code."""
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        capture_output=False,
    )
    return result.returncode


def run_alembic_stamp_base() -> int:
    """Reset alembic version to base."""
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "stamp", "base"],
        capture_output=False,
    )
    return result.returncode


async def check_tables_exist() -> bool:
    """Check if core tables exist in the database."""
    from app.core.database import engine
    from sqlalchemy import text

    required_tables = {"agencies", "routes", "stops", "calendars", "trips"}
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT tablename FROM pg_tables "
                "WHERE schemaname='public' AND tablename != 'alembic_version'"
            )
        )
        existing = {row[0] for row in result}

    return required_tables.issubset(existing)


async def check_routes_empty() -> bool:
    """Check if routes table has zero rows."""
    from app.core.database import engine
    from sqlalchemy import text

    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT count(*) FROM routes"))
        count = result.scalar()
    return count == 0


async def auto_import_gtfs() -> None:
    """Download and import Riga GTFS data."""
    gtfs_url = "https://saraksti.rigassatiksme.lv/riga/gtfs.zip"
    gtfs_path = Path("/tmp/gtfs.zip")

    print(f"[migrate] Downloading GTFS from {gtfs_url}...")
    urllib.request.urlretrieve(gtfs_url, gtfs_path)  # noqa: S310
    print(f"[migrate] Downloaded {gtfs_path.stat().st_size:,} bytes")

    print("[migrate] Importing GTFS data...")
    from app.core.database import engine
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from app.schedules.service import ScheduleService

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        service = ScheduleService(session)
        result = await service.import_gtfs(gtfs_path.read_bytes())

    print(
        f"[migrate] GTFS imported: "
        f"{result.agencies_count} agencies, "
        f"{result.routes_count} routes, "
        f"{result.calendars_count} calendars, "
        f"{result.trips_count} trips, "
        f"{result.stop_times_count} stop_times"
    )
    if result.warnings:
        for w in result.warnings:
            print(f"[migrate] Warning: {w}")


async def seed_users() -> None:
    """Seed default users if none exist."""
    from app.core.database import engine
    from sqlalchemy import text

    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT count(*) FROM users"))
        count = result.scalar()

    if count == 0:
        print("[migrate] Seeding default users...")
        import urllib.request

        req = urllib.request.Request(  # noqa: S310
            "http://localhost:8123/api/v1/auth/seed",
            method="POST",
        )
        try:
            urllib.request.urlopen(req, timeout=10)  # noqa: S310
            print("[migrate] Users seeded")
        except Exception:
            # Auth seed endpoint may not be available in migrate container
            # Users will be seeded on first app startup via /auth/seed
            print("[migrate] Skipping user seed (app not running yet)")


def main() -> None:
    """Run migrations with self-healing."""
    # Step 1: Run alembic upgrade head
    print("[migrate] Running alembic upgrade head...")
    exit_code = run_alembic_upgrade()
    if exit_code != 0:
        print(f"[migrate] Alembic failed with exit code {exit_code}")
        sys.exit(exit_code)

    # Step 2: Verify tables actually exist
    tables_ok = asyncio.run(check_tables_exist())
    if not tables_ok:
        print("[migrate] WARNING: Tables missing despite alembic at head!")
        print("[migrate] Resetting alembic stamp to base and re-running...")
        run_alembic_stamp_base()
        exit_code = run_alembic_upgrade()
        if exit_code != 0:
            print(f"[migrate] Re-run failed with exit code {exit_code}")
            sys.exit(exit_code)

        tables_ok = asyncio.run(check_tables_exist())
        if not tables_ok:
            print("[migrate] FATAL: Tables still missing after re-run")
            sys.exit(1)
        print("[migrate] Tables restored successfully")

    # Step 3: Auto-import GTFS if routes table is empty
    auto_import = os.environ.get("AUTO_IMPORT_GTFS", "true").lower() == "true"
    if auto_import:
        routes_empty = asyncio.run(check_routes_empty())
        if routes_empty:
            print("[migrate] Routes table is empty — auto-importing GTFS...")
            asyncio.run(auto_import_gtfs())
        else:
            print("[migrate] Routes table has data — skipping GTFS import")
    else:
        print("[migrate] AUTO_IMPORT_GTFS=false — skipping")

    print("[migrate] Done")


if __name__ == "__main__":
    main()
