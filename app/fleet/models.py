"""SQLAlchemy models for fleet device management."""

import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.shared.models import TimestampMixin


class TrackedDevice(Base, TimestampMixin):
    """GPS tracking device linked to a fleet vehicle.

    Stores device metadata (IMEI, SIM, protocol) and links to VTV vehicles
    for position correlation. Traccar forwards events via webhook using
    traccar_device_id for correlation.
    """

    __tablename__ = "tracked_devices"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'inactive', 'offline')",
            name="ck_tracked_devices_status",
        ),
        CheckConstraint(
            "protocol_type IN ('teltonika', 'queclink', 'general', 'osmand', 'other')",
            name="ck_tracked_devices_protocol",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    imei: Mapped[str] = mapped_column(String(15), unique=True, nullable=False, index=True)
    device_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    sim_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    protocol_type: Mapped[str] = mapped_column(String(20), nullable=False, default="teltonika")
    firmware_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    vehicle_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("vehicles.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    last_seen_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    traccar_device_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
