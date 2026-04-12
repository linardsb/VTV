"""Database operations for GTFS historical snapshots.

All functions are async and take an AsyncSession. Bulk inserts use
batched chunks of 1000 rows to avoid excessive memory usage.
"""

from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.transit.snapshot_models import (
    GtfsSnapshot,
    GtfsSnapshotCalendar,
    GtfsSnapshotStopTime,
    GtfsSnapshotTrip,
    SnapshotStatus,
)

_BULK_CHUNK_SIZE = 1000


async def get_snapshot_by_resource_id(db: AsyncSession, resource_id: str) -> GtfsSnapshot | None:
    """Fetch a snapshot by its CKAN resource ID."""
    result = await db.execute(select(GtfsSnapshot).where(GtfsSnapshot.resource_id == resource_id))
    return result.scalar_one_or_none()


async def get_snapshot_by_sha256(db: AsyncSession, sha256: str) -> GtfsSnapshot | None:
    """Fetch a snapshot by content hash (deduplication)."""
    result = await db.execute(select(GtfsSnapshot).where(GtfsSnapshot.sha256 == sha256))
    return result.scalar_one_or_none()


async def create_snapshot(db: AsyncSession, snapshot: GtfsSnapshot) -> GtfsSnapshot:
    """Persist a new snapshot record."""
    db.add(snapshot)
    await db.flush()
    return snapshot


async def update_snapshot_status(
    db: AsyncSession,
    snapshot_id: int,
    status: SnapshotStatus,
    row_counts: dict[str, int] | None = None,
) -> None:
    """Update snapshot status and optional row counts after import."""
    values: dict[str, object] = {"status": status}
    if row_counts is not None:
        values["row_counts_json"] = row_counts
    await db.execute(update(GtfsSnapshot).where(GtfsSnapshot.id == snapshot_id).values(**values))


async def bulk_insert_snapshot_trips(
    db: AsyncSession, snapshot_id: int, trips: list[dict[str, object]]
) -> None:
    """Bulk insert trip rows for a snapshot in batches."""
    for i in range(0, len(trips), _BULK_CHUNK_SIZE):
        chunk = trips[i : i + _BULK_CHUNK_SIZE]
        for row in chunk:
            row["snapshot_id"] = snapshot_id
        await db.execute(insert(GtfsSnapshotTrip), chunk)


async def bulk_insert_snapshot_stop_times(
    db: AsyncSession, snapshot_id: int, stop_times: list[dict[str, object]]
) -> None:
    """Bulk insert stop-time rows for a snapshot in batches."""
    for i in range(0, len(stop_times), _BULK_CHUNK_SIZE):
        chunk = stop_times[i : i + _BULK_CHUNK_SIZE]
        for row in chunk:
            row["snapshot_id"] = snapshot_id
        await db.execute(insert(GtfsSnapshotStopTime), chunk)


async def bulk_insert_snapshot_calendars(
    db: AsyncSession, snapshot_id: int, calendars: list[dict[str, object]]
) -> None:
    """Bulk insert calendar rows for a snapshot in batches."""
    for i in range(0, len(calendars), _BULK_CHUNK_SIZE):
        chunk = calendars[i : i + _BULK_CHUNK_SIZE]
        for row in chunk:
            row["snapshot_id"] = snapshot_id
        await db.execute(insert(GtfsSnapshotCalendar), chunk)


async def get_imported_resource_ids(db: AsyncSession) -> set[str]:
    """Get all resource IDs that have been imported (for fast skip)."""
    result = await db.execute(select(GtfsSnapshot.resource_id))
    return {row[0] for row in result.all()}
