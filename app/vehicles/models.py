"""SQLAlchemy models for vehicle management.

Stores fleet vehicle metadata, operational status, driver assignments,
and maintenance history records.
"""

import datetime

from sqlalchemy import Boolean, CheckConstraint, Date, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.shared.models import TimestampMixin


class Vehicle(Base, TimestampMixin):
    """Vehicle database model.

    Stores fleet vehicles with metadata, status, driver assignment,
    and route qualification. Fleet number maps to GTFS-RT vehicle_id.
    """

    __tablename__ = "vehicles"
    __table_args__ = (
        CheckConstraint(
            "vehicle_type IN ('bus', 'trolleybus', 'tram')",
            name="ck_vehicles_vehicle_type",
        ),
        CheckConstraint(
            "status IN ('active', 'inactive', 'maintenance')",
            name="ck_vehicles_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    fleet_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    vehicle_type: Mapped[str] = mapped_column(String(20), nullable=False)
    license_plate: Mapped[str] = mapped_column(String(20), nullable=False)
    manufacturer: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    current_driver_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("drivers.id", ondelete="SET NULL"), nullable=True
    )
    mileage_km: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    qualified_route_ids: Mapped[str | None] = mapped_column(String(500), nullable=True)
    registration_expiry: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    next_maintenance_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class MaintenanceRecord(Base, TimestampMixin):
    """Maintenance record database model.

    Stores service history linked to a vehicle. Cascades on vehicle deletion.
    """

    __tablename__ = "maintenance_records"
    __table_args__ = (
        CheckConstraint(
            "maintenance_type IN ('scheduled', 'unscheduled', 'inspection', 'repair')",
            name="ck_maintenance_records_type",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    vehicle_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    maintenance_type: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    performed_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    mileage_at_service: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_eur: Mapped[float | None] = mapped_column(Float, nullable=True)
    next_scheduled_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    performed_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
