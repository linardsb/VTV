"""SQLAlchemy models for geofence zone management and event tracking."""

import datetime

from geoalchemy2 import Geometry  # pyright: ignore[reportMissingTypeStubs]
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.shared.models import TimestampMixin


class Geofence(Base, TimestampMixin):
    """Geographic zone for vehicle containment detection.

    Stores PostGIS Polygon geometry with alert configuration for
    enter/exit/dwell events. Active geofences are checked by the
    background evaluator against live vehicle positions.
    """

    __tablename__ = "geofences"
    __table_args__ = (
        CheckConstraint(
            "zone_type IN ('depot', 'terminal', 'restricted', 'customer', 'custom')",
            name="ck_geofences_zone_type",
        ),
        CheckConstraint(
            "alert_severity IN ('critical', 'high', 'medium', 'low', 'info')",
            name="ck_geofences_alert_severity",
        ),
        Index(
            "ix_geofences_geometry_active",
            "geometry",
            postgresql_using="gist",
            postgresql_where=text("is_active = true"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    zone_type: Mapped[str] = mapped_column(String(20), nullable=False)
    geometry = mapped_column(
        Geometry("POLYGON", srid=4326),  # pyright: ignore[reportUnknownArgumentType]
        nullable=False,
    )
    color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    alert_on_enter: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    alert_on_exit: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    alert_on_dwell: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    dwell_threshold_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    alert_severity: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class GeofenceEvent(Base, TimestampMixin):
    """Record of a vehicle entering, exiting, or dwelling in a geofence.

    Events track state transitions detected by the background evaluator.
    Enter events remain open (exited_at=NULL) until an exit is detected,
    at which point dwell_seconds is calculated.
    """

    __tablename__ = "geofence_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('enter', 'exit', 'dwell_exceeded')",
            name="ck_geofence_events_event_type",
        ),
        Index("ix_geofence_events_geofence_entered", "geofence_id", "entered_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    geofence_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("geofences.id", ondelete="CASCADE"), nullable=False, index=True
    )
    vehicle_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(20), nullable=False)
    entered_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    exited_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    dwell_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
