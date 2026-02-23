"""add_operational_events_table

Revision ID: 227fa3f158e1
Revises: c7f9d2b03e58
Create Date: 2026-02-23 07:41:11.415600

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "227fa3f158e1"
down_revision: str | Sequence[str] | None = "c7f9d2b03e58"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "operational_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("start_datetime", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_datetime", sa.DateTime(timezone=True), nullable=False),
        sa.Column("priority", sa.String(length=20), nullable=False),
        sa.Column("category", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_operational_events_id"), "operational_events", ["id"], unique=False)
    op.create_index(
        op.f("ix_operational_events_start_datetime"),
        "operational_events",
        ["start_datetime"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_operational_events_start_datetime"), table_name="operational_events")
    op.drop_index(op.f("ix_operational_events_id"), table_name="operational_events")
    op.drop_table("operational_events")
