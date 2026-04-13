"""Add route_id to tracked_devices.

Revision ID: u5v6w7x8y9z0
Revises: t4u5v6w7x8y9
Create Date: 2026-04-13
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "u5v6w7x8y9z0"
down_revision = "t4u5v6w7x8y9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tracked_devices",
        sa.Column("route_id", sa.Integer(), nullable=True),
    )
    op.create_index("ix_tracked_devices_route_id", "tracked_devices", ["route_id"])
    op.create_foreign_key(
        "fk_tracked_devices_route_id",
        "tracked_devices",
        "routes",
        ["route_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_tracked_devices_route_id", "tracked_devices", type_="foreignkey")
    op.drop_index("ix_tracked_devices_route_id", table_name="tracked_devices")
    op.drop_column("tracked_devices", "route_id")
