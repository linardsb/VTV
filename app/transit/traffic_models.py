"""SQLAlchemy models for traffic count and accident storage (ML-1.3).

Regular tables (not hypertables) — traffic counts are updated daily/annually,
not at high frequency like vehicle positions.
"""

import datetime

from geoalchemy2 import Geography  # pyright: ignore[reportMissingTypeStubs]
from sqlalchemy import Date, DateTime, Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.shared.models import TimestampMixin


class TrafficCount(Base, TimestampMixin):
    """Aggregated traffic count at a measurement point over a time period.

    Upserted from data.lvceli.lv traffic census data (daily cadence).
    """

    __tablename__ = "traffic_counts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    point_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    period_start: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    period_end: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    avg_count_per_day: Mapped[float] = mapped_column(Float, nullable=False)
    vehicle_class: Mapped[str | None] = mapped_column(String(50), nullable=True)
    location = mapped_column(
        Geography("POINT", srid=4326),  # pyright: ignore[reportUnknownArgumentType]
        nullable=True,
    )

    __table_args__ = (
        UniqueConstraint(
            "point_id",
            "period_start",
            "period_end",
            "vehicle_class",
            name="uq_traffic_count_key",
        ),
    )


class TrafficAccident(Base, TimestampMixin):
    """A traffic accident record with location and severity.

    Upserted from CAIS (Road Accident Information System) dataset (annual cadence).
    """

    __tablename__ = "traffic_accidents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    occurred_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    severity: Mapped[str] = mapped_column(String(50), nullable=False)
    fatalities: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    injuries: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    location = mapped_column(
        Geography("POINT", srid=4326),  # pyright: ignore[reportUnknownArgumentType]
        nullable=True,
    )
