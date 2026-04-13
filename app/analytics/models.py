"""SQLAlchemy models for analytics feature (ML-5.2)."""

from __future__ import annotations

import datetime

from sqlalchemy import Boolean, Date, Float, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.shared.models import TimestampMixin


class DailyAdherenceReport(TimestampMixin, Base):
    """Daily fleet-wide schedule adherence summary.

    One row per calendar date, containing overall on-time %, trip counts,
    per-route breakdowns (JSONB), and per-hour breakdowns (JSONB).
    """

    __tablename__ = "daily_adherence_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_date: Mapped[datetime.date] = mapped_column(Date, unique=True, nullable=False)
    overall_pct: Mapped[float] = mapped_column(Float, nullable=False)
    total_trips: Mapped[int] = mapped_column(Integer, nullable=False)
    on_time_trips: Mapped[int] = mapped_column(Integer, nullable=False)
    late_trips: Mapped[int] = mapped_column(Integer, nullable=False)
    early_trips: Mapped[int] = mapped_column(Integer, nullable=False)
    per_route_json: Mapped[list[dict[str, object]]] = mapped_column(JSONB, nullable=False)
    per_hour_json: Mapped[list[dict[str, object]]] = mapped_column(JSONB, nullable=False)
    anomaly_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    alert_triggered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
