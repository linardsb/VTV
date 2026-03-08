"""SQLAlchemy models for historical vehicle position storage.

The vehicle_positions table is converted to a TimescaleDB hypertable
in the Alembic migration, enabling automatic time-based partitioning,
compression policies, and continuous aggregates.
"""

import datetime
from typing import Any

from sqlalchemy import DateTime, Float, Index, Integer, SmallInteger, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class VehiclePositionRecord(Base):
    """A single historical vehicle position record.

    Stored in a TimescaleDB hypertable partitioned by recorded_at.
    Each row represents one position update from a GTFS-RT poll cycle.

    Note: Does not use TimestampMixin. The hypertable is partitioned by
    recorded_at (GTFS-RT measurement time), not DB insert time. Adding
    created_at/updated_at would increase row size on a high-volume table
    without operational benefit.

    Attributes:
        id: Auto-incrementing primary key.
        recorded_at: Timestamp when the position was measured (UTC, from GTFS-RT).
        feed_id: Source feed identifier (e.g., "riga").
        vehicle_id: Fleet vehicle identifier (e.g., "4521").
        route_id: GTFS route identifier.
        route_short_name: Human-readable route number (e.g., "22").
        trip_id: GTFS trip identifier, if available.
        latitude: WGS84 latitude.
        longitude: WGS84 longitude.
        bearing: Compass heading in degrees (0-360).
        speed_kmh: Speed in km/h.
        delay_seconds: Schedule deviation in seconds (positive=late).
        current_status: GTFS-RT vehicle stop status.
    """

    __tablename__ = "vehicle_positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recorded_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    feed_id: Mapped[str] = mapped_column(String(50), nullable=False)
    vehicle_id: Mapped[str] = mapped_column(String(100), nullable=False)
    route_id: Mapped[str] = mapped_column(String(100), nullable=False, server_default="")
    route_short_name: Mapped[str] = mapped_column(String(50), nullable=False, server_default="")
    trip_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    bearing: Mapped[float | None] = mapped_column(Float, nullable=True)
    speed_kmh: Mapped[float | None] = mapped_column(Float, nullable=True)
    delay_seconds: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")
    current_status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="IN_TRANSIT_TO"
    )
    source: Mapped[str] = mapped_column(String(20), nullable=False, server_default="gtfs-rt")
    obd_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        Index("ix_vehicle_positions_vehicle_time", "vehicle_id", "recorded_at"),
        Index("ix_vehicle_positions_route_time", "route_id", "recorded_at"),
        Index("ix_vehicle_positions_feed_time", "feed_id", "recorded_at"),
        Index("ix_vehicle_positions_source", "source"),
    )
