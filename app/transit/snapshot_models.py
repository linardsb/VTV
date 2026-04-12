"""SQLAlchemy models for GTFS historical snapshot archive.

Shadow tables store denormalized GTFS string IDs for ML training.
They are NOT FK-joined to the main schedule tables -- each snapshot
is a self-contained point-in-time copy of the feed.
"""

import datetime
from typing import Literal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.shared.models import TimestampMixin

SnapshotStatus = Literal["pending", "complete", "failed"]


class GtfsSnapshot(Base, TimestampMixin):
    """Metadata for a single GTFS static feed snapshot.

    Each row represents one downloaded ZIP from data.gov.lv,
    identified by its CKAN resource_id and content SHA-256.
    """

    __tablename__ = "gtfs_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    feed_name: Mapped[str] = mapped_column(String(50), nullable=False)
    snapshot_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    resource_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    row_counts_json: Mapped[dict[str, int] | None] = mapped_column(JSONB, nullable=True)
    imported_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[SnapshotStatus] = mapped_column(String(20), nullable=False, default="pending")

    __table_args__ = (Index("ix_gtfs_snapshots_date", "snapshot_date"),)


class GtfsSnapshotTrip(Base):
    """Denormalized trip record within a snapshot.

    Uses GTFS string IDs (not DB FKs) for ML training portability.
    No TimestampMixin -- append-only archive data.
    """

    __tablename__ = "gtfs_snapshot_trips"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("gtfs_snapshots.id", ondelete="CASCADE"), nullable=False
    )
    gtfs_trip_id: Mapped[str] = mapped_column(String(200), nullable=False)
    gtfs_route_id: Mapped[str] = mapped_column(String(100), nullable=False)
    gtfs_service_id: Mapped[str] = mapped_column(String(100), nullable=False)
    direction_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    trip_headsign: Mapped[str | None] = mapped_column(String(200), nullable=True)
    shape_id: Mapped[str | None] = mapped_column(String(200), nullable=True)

    __table_args__ = (
        UniqueConstraint("snapshot_id", "gtfs_trip_id", name="uq_snapshot_trip"),
        Index("ix_snapshot_trips_snapshot_id", "snapshot_id"),
    )


class GtfsSnapshotStopTime(Base):
    """Denormalized stop time record within a snapshot."""

    __tablename__ = "gtfs_snapshot_stop_times"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("gtfs_snapshots.id", ondelete="CASCADE"), nullable=False
    )
    gtfs_trip_id: Mapped[str] = mapped_column(String(200), nullable=False)
    gtfs_stop_id: Mapped[str] = mapped_column(String(100), nullable=False)
    stop_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    arrival_time: Mapped[str] = mapped_column(String(8), nullable=False)
    departure_time: Mapped[str] = mapped_column(String(8), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "snapshot_id", "gtfs_trip_id", "stop_sequence", name="uq_snapshot_stop_time"
        ),
        Index("ix_snapshot_stop_times_snapshot_id", "snapshot_id"),
    )


class GtfsSnapshotCalendar(Base):
    """Denormalized calendar record within a snapshot."""

    __tablename__ = "gtfs_snapshot_calendars"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("gtfs_snapshots.id", ondelete="CASCADE"), nullable=False
    )
    gtfs_service_id: Mapped[str] = mapped_column(String(100), nullable=False)
    monday: Mapped[bool] = mapped_column(Boolean, nullable=False)
    tuesday: Mapped[bool] = mapped_column(Boolean, nullable=False)
    wednesday: Mapped[bool] = mapped_column(Boolean, nullable=False)
    thursday: Mapped[bool] = mapped_column(Boolean, nullable=False)
    friday: Mapped[bool] = mapped_column(Boolean, nullable=False)
    saturday: Mapped[bool] = mapped_column(Boolean, nullable=False)
    sunday: Mapped[bool] = mapped_column(Boolean, nullable=False)
    start_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    end_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)

    __table_args__ = (
        UniqueConstraint("snapshot_id", "gtfs_service_id", name="uq_snapshot_calendar"),
        Index("ix_snapshot_calendars_snapshot_id", "snapshot_id"),
    )
