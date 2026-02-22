"""SQLAlchemy model for driver management.

Stores driver HR profiles including personal info, licensing,
shift assignments, and route qualifications.
"""

import datetime

from sqlalchemy import Boolean, Date, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.shared.models import TimestampMixin


class Driver(Base, TimestampMixin):
    """Driver database model.

    Stores driver profiles with employment, licensing, and qualification data.
    License categories and qualified route IDs are stored as comma-separated
    strings for MVP simplicity.
    """

    __tablename__ = "drivers"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    employee_number: Mapped[str] = mapped_column(
        String(20), unique=True, nullable=False, index=True
    )
    first_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    date_of_birth: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    emergency_contact_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    emergency_contact_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    photo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    hire_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    license_categories: Mapped[str | None] = mapped_column(String(50), nullable=True)
    license_expiry_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    medical_cert_expiry: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    qualified_route_ids: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_shift: Mapped[str] = mapped_column(String(20), nullable=False, default="morning")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="available")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    training_records: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
