"""add created_by_id to calendars

Revision ID: 6aed7d0b568d
Revises: 96fe33fb032c
Create Date: 2026-02-25 12:25:59.933620

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6aed7d0b568d"
down_revision: str | Sequence[str] | None = "96fe33fb032c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add created_by_id column to calendars table."""
    op.add_column("calendars", sa.Column("created_by_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_calendars_created_by_id",
        "calendars",
        "users",
        ["created_by_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Remove created_by_id column from calendars table."""
    op.drop_constraint("fk_calendars_created_by_id", "calendars", type_="foreignkey")
    op.drop_column("calendars", "created_by_id")
