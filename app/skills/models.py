"""SQLAlchemy model for agent skills.

Stores reusable knowledge packages (procedures, protocols, glossaries)
that are injected into the AI agent's system context on every request.
"""

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.shared.models import TimestampMixin


class AgentSkill(Base, TimestampMixin):
    """Agent skill database model.

    Represents a reusable knowledge package for the AI agent.
    Skills are loaded by priority (DESC) and injected into agent context.
    """

    __tablename__ = "agent_skills"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False, default="transit_ops")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
