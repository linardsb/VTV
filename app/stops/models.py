"""SQLAlchemy model for transit stops.

Aligns with GTFS stops.txt fields. Coordinates stored as floats (WGS84)
with a derived PostGIS geometry column (geom) for spatial queries.
A database trigger auto-syncs geom from stop_lat/stop_lon.
"""

from geoalchemy2 import Geometry  # pyright: ignore[reportMissingTypeStubs]
from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.shared.models import TimestampMixin


class Stop(Base, TimestampMixin):
    """Transit stop database model.

    Maps to GTFS stops.txt with additional operator metadata.
    Coordinates stored as floats (WGS84) with a derived PostGIS
    geometry column (geom) for spatial queries. A database trigger
    auto-syncs geom from stop_lat/stop_lon.
    """

    __tablename__ = "stops"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    gtfs_stop_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    stop_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    stop_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    stop_lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    geom = mapped_column(
        Geometry("POINT", srid=4326),  # pyright: ignore[reportUnknownArgumentType]
        nullable=True,
    )
    stop_desc: Mapped[str | None] = mapped_column(Text, nullable=True)
    location_type: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    parent_station_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("stops.id"), nullable=True
    )
    wheelchair_boarding: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
