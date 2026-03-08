"""SQLAlchemy models for the notification/alerts feature."""

import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.shared.models import TimestampMixin


class AlertRule(Base, TimestampMixin):
    """Alert rule configuration - defines what conditions to monitor."""

    __tablename__ = "alert_rules"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    rule_type: Mapped[str] = mapped_column(String(30), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    threshold_config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    enabled: Mapped[bool] = mapped_column(default=True, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "rule_type IN ('delay_threshold', 'maintenance_due', 'registration_expiry', 'manual', 'geofence_enter', 'geofence_exit', 'geofence_dwell')",
            name="ck_alert_rules_rule_type",
        ),
        CheckConstraint(
            "severity IN ('critical', 'high', 'medium', 'low', 'info')",
            name="ck_alert_rules_severity",
        ),
    )


class AlertInstance(Base, TimestampMixin):
    """Alert instance - a concrete alert occurrence with lifecycle management."""

    __tablename__ = "alert_instances"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", index=True)
    alert_type: Mapped[str] = mapped_column(String(30), nullable=False)
    rule_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("alert_rules.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_entity_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    source_entity_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True, default=None)
    acknowledged_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    acknowledged_by_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    resolved_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'acknowledged', 'resolved')",
            name="ck_alert_instances_status",
        ),
        Index(
            "ix_alert_dedup",
            "rule_id",
            "source_entity_type",
            "source_entity_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )
