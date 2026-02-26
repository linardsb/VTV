"""add_goals_jsonb_to_events

Revision ID: 37de45842dd3
Revises: 6aed7d0b568d
Create Date: 2026-02-26 09:46:13.676654

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "37de45842dd3"
down_revision: str | Sequence[str] | None = "6aed7d0b568d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add goals JSONB column to operational_events table."""
    op.add_column(
        "operational_events",
        sa.Column("goals", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    """Remove goals column from operational_events table."""
    op.drop_column("operational_events", "goals")
