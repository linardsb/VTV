"""SQLAlchemy models for RBAC dispatcher assignments and auth audit events."""

import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base
from app.shared.models import TimestampMixin


class DispatcherAssignment(Base, TimestampMixin):
    """Maps a dispatcher user to an assigned route for RBAC scoping.

    Dispatchers only see data for routes they are assigned to.
    Admin users manage these assignments via the admin API.
    """

    __tablename__ = "dispatcher_assignments"
    __table_args__ = (UniqueConstraint("user_id", "route_id", name="uq_dispatcher_assignment"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    route_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("routes.id", ondelete="CASCADE"),
        nullable=False,
    )
    assigned_by: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )


class AuthAuditEvent(Base):
    """Persisted authorization denial event for compliance audit trail.

    Immutable append-only table backed by a TimescaleDB hypertable.
    No TimestampMixin — uses ``recorded_at`` as time column and audit
    events are never updated.
    """

    __tablename__ = "auth_audit_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    recorded_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True, server_default=func.now()
    )
    request_id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    path: Mapped[str] = mapped_column(String(512), nullable=False)
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    status_code: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    enforcement_layer: Mapped[str] = mapped_column(String(50), nullable=False)
    client_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_role: Mapped[str | None] = mapped_column(String(20), nullable=True)
    extra: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
