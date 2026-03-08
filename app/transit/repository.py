"""Repository for historical vehicle position storage and queries.

Handles batch inserts from the poller and time-range queries for
the REST API. All queries use parameterized SQLAlchemy expressions.
"""

import datetime
from typing import TypedDict

from sqlalchemy import insert, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.transit.models import VehiclePositionRecord

logger = get_logger(__name__)


class DelayTrendBucket(TypedDict):
    """A single time-bucketed delay aggregation result."""

    time_bucket: str
    avg_delay: float
    min_delay: int
    max_delay: int
    sample_count: int


async def batch_insert_positions(
    db: AsyncSession,
    records: list[dict[str, object]],
) -> int:
    """Batch insert vehicle position records.

    Commits immediately — designed for independent poller writes,
    not for use within a larger transaction.

    Args:
        db: Async database session.
        records: List of position dicts matching VehiclePositionRecord columns.

    Returns:
        Number of records inserted.
    """
    if not records:
        return 0

    stmt = insert(VehiclePositionRecord)
    await db.execute(stmt, records)
    await db.commit()
    return len(records)


async def get_vehicle_history(
    db: AsyncSession,
    vehicle_id: str,
    from_time: datetime.datetime,
    to_time: datetime.datetime,
    limit: int = 1000,
) -> list[VehiclePositionRecord]:
    """Get position history for a single vehicle within a time range.

    Args:
        db: Async database session.
        vehicle_id: Fleet vehicle identifier.
        from_time: Start of time range (inclusive).
        to_time: End of time range (inclusive).
        limit: Maximum records to return.

    Returns:
        List of VehiclePositionRecord ordered by recorded_at ASC.
    """
    stmt = (
        select(VehiclePositionRecord)
        .where(
            VehiclePositionRecord.vehicle_id == vehicle_id,
            VehiclePositionRecord.recorded_at >= from_time,
            VehiclePositionRecord.recorded_at <= to_time,
        )
        .order_by(VehiclePositionRecord.recorded_at.asc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_route_delay_trend(
    db: AsyncSession,
    route_id: str,
    from_time: datetime.datetime,
    to_time: datetime.datetime,
    interval_minutes: int = 60,
) -> list[DelayTrendBucket]:
    """Get aggregated delay trend for a route using time_bucket.

    Uses TimescaleDB's time_bucket function for efficient time-series
    aggregation.

    Args:
        db: Async database session.
        route_id: GTFS route identifier.
        from_time: Start of time range.
        to_time: End of time range.
        interval_minutes: Bucket size in minutes (default 60).

    Returns:
        List of dicts with time_bucket, avg/min/max delay, sample_count.
    """
    interval_str = f"{interval_minutes} minutes"
    stmt = text(
        "SELECT "
        "  time_bucket(:interval, recorded_at) AS time_bucket, "
        "  AVG(delay_seconds)::float AS avg_delay, "
        "  MIN(delay_seconds)::int AS min_delay, "
        "  MAX(delay_seconds)::int AS max_delay, "
        "  COUNT(*)::int AS sample_count "
        "FROM vehicle_positions "
        "WHERE route_id = :route_id "
        "  AND recorded_at >= :from_time "
        "  AND recorded_at <= :to_time "
        "GROUP BY time_bucket "
        "ORDER BY time_bucket ASC"
    ).bindparams(
        interval=interval_str,
        route_id=route_id,
        from_time=from_time,
        to_time=to_time,
    )
    result = await db.execute(stmt)
    rows = result.all()
    return [
        DelayTrendBucket(
            time_bucket=row[0].isoformat() if row[0] else "",
            avg_delay=round(float(row[1]), 1) if row[1] is not None else 0.0,
            min_delay=int(row[2]) if row[2] is not None else 0,
            max_delay=int(row[3]) if row[3] is not None else 0,
            sample_count=int(row[4]) if row[4] is not None else 0,
        )
        for row in rows
    ]
