"""SQLAlchemy models for RBAC dispatcher assignments."""

from sqlalchemy import ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

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
