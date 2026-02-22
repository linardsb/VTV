"""add_drivers_table

Revision ID: a3f7d2e81b4c
Revises: 9ce2b394eec6
Create Date: 2026-02-22 10:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3f7d2e81b4c"
down_revision: str | Sequence[str] | None = "9ce2b394eec6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "drivers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("employee_number", sa.String(length=20), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("phone", sa.String(length=30), nullable=True),
        sa.Column("email", sa.String(length=200), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("emergency_contact_name", sa.String(length=200), nullable=True),
        sa.Column("emergency_contact_phone", sa.String(length=30), nullable=True),
        sa.Column("photo_url", sa.String(length=500), nullable=True),
        sa.Column("hire_date", sa.Date(), nullable=True),
        sa.Column("license_categories", sa.String(length=50), nullable=True),
        sa.Column("license_expiry_date", sa.Date(), nullable=True),
        sa.Column("medical_cert_expiry", sa.Date(), nullable=True),
        sa.Column("qualified_route_ids", sa.Text(), nullable=True),
        sa.Column("default_shift", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("training_records", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("employee_number"),
    )
    op.create_index(op.f("ix_drivers_id"), "drivers", ["id"], unique=False)
    op.create_index(op.f("ix_drivers_employee_number"), "drivers", ["employee_number"], unique=True)
    op.create_index(op.f("ix_drivers_first_name"), "drivers", ["first_name"], unique=False)
    op.create_index(op.f("ix_drivers_last_name"), "drivers", ["last_name"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_drivers_last_name"), table_name="drivers")
    op.drop_index(op.f("ix_drivers_first_name"), table_name="drivers")
    op.drop_index(op.f("ix_drivers_employee_number"), table_name="drivers")
    op.drop_index(op.f("ix_drivers_id"), table_name="drivers")
    op.drop_table("drivers")
