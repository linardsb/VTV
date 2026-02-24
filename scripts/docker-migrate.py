"""Docker migration entrypoint with self-healing.

Runs alembic upgrade head, then verifies tables actually exist.
If tables are missing (stale alembic_version stamp), resets and re-runs.
Optionally auto-imports GTFS data if the routes table is empty.

NOTE: This script avoids importing from `app.*` for table checks because
the app package may not be installed in the migrate container's virtualenv.
Only the GTFS import path needs `app` (it uses the ScheduleService).
"""

import asyncio
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


def _get_database_url() -> str:
    """Get async database URL from environment."""
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        print("[migrate] FATAL: DATABASE_URL not set")
        sys.exit(1)
    # Ensure async driver
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def run_alembic_upgrade() -> int:
    """Run alembic upgrade head and return exit code."""
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        capture_output=False,
    )
    return result.returncode


def run_alembic_stamp_base() -> int:
    """Reset alembic version to base."""
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "alembic", "stamp", "base"],
        capture_output=False,
    )
    return result.returncode


async def check_tables_exist() -> bool:
    """Check if core tables exist in the database."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(_get_database_url())
    required_tables = {"agencies", "routes", "stops", "calendars", "trips"}
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT tablename FROM pg_tables "
                    "WHERE schemaname='public' AND tablename != 'alembic_version'"
                )
            )
            existing = {row[0] for row in result}
    finally:
        await engine.dispose()

    return required_tables.issubset(existing)


async def check_routes_empty() -> bool:
    """Check if routes table has zero rows."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(_get_database_url())
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT count(*) FROM routes"))
            count = result.scalar()
    finally:
        await engine.dispose()
    return count == 0


async def auto_import_gtfs() -> None:
    """Download and import Riga GTFS data."""
    gtfs_url = "https://saraksti.rigassatiksme.lv/riga/gtfs.zip"
    gtfs_path = Path("/tmp/gtfs.zip")  # noqa: S108

    print(f"[migrate] Downloading GTFS from {gtfs_url}...")
    start = time.time()
    try:
        urllib.request.urlretrieve(gtfs_url, gtfs_path, timeout=120)  # noqa: S310
    except Exception as e:
        print(f"[migrate] ERROR: GTFS download failed: {e}")
        print("[migrate] Continuing without GTFS data - import manually later")
        return
    elapsed = time.time() - start
    print(f"[migrate] Downloaded {gtfs_path.stat().st_size:,} bytes in {elapsed:.1f}s")

    print("[migrate] Importing GTFS data...")
    start = time.time()

    # Add parent dir to sys.path so `app` package is importable
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.schedules.service import ScheduleService

    engine = create_async_engine(_get_database_url())
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as session:
            service = ScheduleService(session)
            result = await service.import_gtfs(gtfs_path.read_bytes())
    finally:
        await engine.dispose()

    elapsed = time.time() - start
    print(
        f"[migrate] GTFS imported in {elapsed:.1f}s: "
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
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(_get_database_url())
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT count(*) FROM users"))
            count = result.scalar()
    finally:
        await engine.dispose()

    if count == 0:
        print("[migrate] Seeding default users...")
        req = urllib.request.Request(
            "http://localhost:8123/api/v1/auth/seed",
            method="POST",
        )
        try:
            urllib.request.urlopen(req, timeout=10)  # noqa: S310
            print("[migrate] Users seeded")
        except Exception:
            print("[migrate] Skipping user seed (app not running yet)")


def main() -> None:
    """Run migrations with self-healing."""
    total_start = time.time()

    # Step 1: Run alembic upgrade head
    print("[migrate] Running alembic upgrade head...")
    start = time.time()
    exit_code = run_alembic_upgrade()
    print(f"[migrate] Alembic completed in {time.time() - start:.1f}s")
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
            print("[migrate] Routes table is empty - auto-importing GTFS...")
            asyncio.run(auto_import_gtfs())
        else:
            print("[migrate] Routes table has data - skipping GTFS import")
    else:
        print("[migrate] AUTO_IMPORT_GTFS=false - skipping")

    total_elapsed = time.time() - total_start
    print(f"[migrate] Done in {total_elapsed:.1f}s")


if __name__ == "__main__":
    main()
