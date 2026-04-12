"""SQLAlchemy models for weather observation storage (ML-1.3).

weather_observations is a TimescaleDB hypertable partitioned by observed_at.
Does not use TimestampMixin (same rationale as VehiclePositionRecord).
"""

import datetime
from typing import Any

from geoalchemy2 import Geography  # pyright: ignore[reportMissingTypeStubs]
from sqlalchemy import DateTime, Float, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class WeatherStation(Base):
    """A meteorological station with a fixed geographic position.

    Stations are upserted from data.gov.lv metadata.
    """

    __tablename__ = "weather_stations"

    station_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    location = mapped_column(
        Geography("POINT", srid=4326),  # pyright: ignore[reportUnknownArgumentType]
        nullable=False,
    )


class WeatherObservation(Base):
    """A single weather measurement from one station at one point in time.

    Stored in a TimescaleDB hypertable partitioned by observed_at.
    Does not use TimestampMixin: the partition column is observed_at
    (measurement time), not DB insert time.
    """

    __tablename__ = "weather_observations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    station_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    observed_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    temp_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    wind_mps: Mapped[float | None] = mapped_column(Float, nullable=True)
    precip_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    phenomena: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    location = mapped_column(
        Geography("POINT", srid=4326),  # pyright: ignore[reportUnknownArgumentType]
        nullable=True,
    )

    __table_args__ = (
        UniqueConstraint("station_id", "observed_at", name="uq_weather_obs_station_time"),
        Index("ix_weather_obs_station_time", "station_id", "observed_at"),
    )
