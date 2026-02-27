"""add check constraints for vehicle and maintenance type columns

Revision ID: 4f10502b5ce8
Revises: a74dcc53a4df
Create Date: 2026-02-27 14:09:42.514397

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4f10502b5ce8"
down_revision: str | Sequence[str] | None = "a74dcc53a4df"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add check constraints for vehicle_type, status, and maintenance_type."""
    op.create_check_constraint(
        "ck_vehicles_vehicle_type",
        "vehicles",
        "vehicle_type IN ('bus', 'trolleybus', 'tram')",
    )
    op.create_check_constraint(
        "ck_vehicles_status",
        "vehicles",
        "status IN ('active', 'inactive', 'maintenance')",
    )
    op.create_check_constraint(
        "ck_maintenance_records_type",
        "maintenance_records",
        "maintenance_type IN ('scheduled', 'unscheduled', 'inspection', 'repair')",
    )


def downgrade() -> None:
    """Remove check constraints."""
    op.drop_constraint("ck_maintenance_records_type", "maintenance_records", type_="check")
    op.drop_constraint("ck_vehicles_status", "vehicles", type_="check")
    op.drop_constraint("ck_vehicles_vehicle_type", "vehicles", type_="check")
