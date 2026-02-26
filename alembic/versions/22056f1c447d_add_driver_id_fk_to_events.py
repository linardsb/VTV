"""add_driver_id_fk_to_events

Revision ID: 22056f1c447d
Revises: 37de45842dd3
Create Date: 2026-02-26 13:02:36.872540

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "22056f1c447d"
down_revision: str | Sequence[str] | None = "37de45842dd3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add driver_id FK column to operational_events table."""
    op.add_column(
        "operational_events",
        sa.Column("driver_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        op.f("ix_operational_events_driver_id"),
        "operational_events",
        ["driver_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_operational_events_driver_id_drivers",
        "operational_events",
        "drivers",
        ["driver_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Remove driver_id FK column from operational_events table."""
    op.drop_constraint(
        "fk_operational_events_driver_id_drivers",
        "operational_events",
        type_="foreignkey",
    )
    op.drop_index(
        op.f("ix_operational_events_driver_id"),
        table_name="operational_events",
    )
    op.drop_column("operational_events", "driver_id")
