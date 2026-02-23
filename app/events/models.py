"""SQLAlchemy model for operational events.

Stores calendar events such as maintenance windows, route changes,
driver shifts, and service alerts for the operations dashboard.
"""

import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.shared.models import TimestampMixin


class OperationalEvent(Base, TimestampMixin):
    """Operational event database model.

    Represents a time-bounded operational event displayed on the dashboard calendar.
    """

    __tablename__ = "operational_events"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_datetime: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    end_datetime: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    category: Mapped[str] = mapped_column(String(30), nullable=False, default="maintenance")
