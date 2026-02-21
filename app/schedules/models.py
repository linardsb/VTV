"""SQLAlchemy models for schedule management.

Aligns with GTFS specification: agencies own routes, routes contain trips,
trips belong to service calendars, and each trip has ordered stop times.
Stop times reference the stops table via foreign key.
"""

import datetime

from sqlalchemy import Boolean, Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.shared.models import TimestampMixin


class Agency(Base, TimestampMixin):
    """Transit agency database model (GTFS agency.txt)."""

    __tablename__ = "agencies"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    gtfs_agency_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    agency_name: Mapped[str] = mapped_column(String(200), nullable=False)
    agency_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    agency_timezone: Mapped[str] = mapped_column(String(50), nullable=False, default="Europe/Riga")
    agency_lang: Mapped[str | None] = mapped_column(String(5), nullable=True)


class Route(Base, TimestampMixin):
    """Transit route database model (GTFS routes.txt)."""

    __tablename__ = "routes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    gtfs_route_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    agency_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("agencies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    route_short_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    route_long_name: Mapped[str] = mapped_column(String(200), nullable=False)
    route_type: Mapped[int] = mapped_column(Integer, nullable=False)
    route_color: Mapped[str | None] = mapped_column(String(6), nullable=True)
    route_text_color: Mapped[str | None] = mapped_column(String(6), nullable=True)
    route_sort_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Calendar(Base, TimestampMixin):
    """Service calendar database model (GTFS calendar.txt)."""

    __tablename__ = "calendars"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    gtfs_service_id: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )
    monday: Mapped[bool] = mapped_column(Boolean, nullable=False)
    tuesday: Mapped[bool] = mapped_column(Boolean, nullable=False)
    wednesday: Mapped[bool] = mapped_column(Boolean, nullable=False)
    thursday: Mapped[bool] = mapped_column(Boolean, nullable=False)
    friday: Mapped[bool] = mapped_column(Boolean, nullable=False)
    saturday: Mapped[bool] = mapped_column(Boolean, nullable=False)
    sunday: Mapped[bool] = mapped_column(Boolean, nullable=False)
    start_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    end_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)


class CalendarDate(Base, TimestampMixin):
    """Calendar date exception database model (GTFS calendar_dates.txt)."""

    __tablename__ = "calendar_dates"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    calendar_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("calendars.id", ondelete="CASCADE"), nullable=False, index=True
    )
    date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    exception_type: Mapped[int] = mapped_column(Integer, nullable=False)


class Trip(Base, TimestampMixin):
    """Trip database model (GTFS trips.txt)."""

    __tablename__ = "trips"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    gtfs_trip_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    route_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("routes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    calendar_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("calendars.id", ondelete="CASCADE"), nullable=False, index=True
    )
    direction_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    trip_headsign: Mapped[str | None] = mapped_column(String(200), nullable=True)
    block_id: Mapped[str | None] = mapped_column(String(50), nullable=True)


class StopTime(Base, TimestampMixin):
    """Stop time database model (GTFS stop_times.txt).

    Times are stored as String(8) in HH:MM:SS format because GTFS allows
    times exceeding 24:00:00 for overnight trips (e.g., "25:30:00").
    """

    __tablename__ = "stop_times"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    trip_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("trips.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stop_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("stops.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stop_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    arrival_time: Mapped[str] = mapped_column(String(8), nullable=False)
    departure_time: Mapped[str] = mapped_column(String(8), nullable=False)
    pickup_type: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    drop_off_type: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
