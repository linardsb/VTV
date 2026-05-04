"""Convert phone_identifier unique constraint to partial unique index.

Soft-delete fix (T-002): the application implements soft-delete via
``active=False`` in ``app/transit/routes.py:366``, but the original full
unique constraint on ``phone_identifier`` blocks any re-create after
deactivation, causing 500s on legitimate phone reassignment. Replace the
full unique constraint with a partial unique index that only enforces
uniqueness among active rows.

Revision ID: y9z0a1b2c3d4
Revises: x8y9z0a1b2c3
Create Date: 2026-05-04
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "y9z0a1b2c3d4"
down_revision: str | None = "x8y9z0a1b2c3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_UNIQUE = "vehicle_phone_assignments_phone_identifier_key"
_NEW_INDEX = "uq_phone_assignments_active_phone_identifier"


def upgrade() -> None:
    op.drop_constraint(_OLD_UNIQUE, "vehicle_phone_assignments", type_="unique")
    op.create_index(
        _NEW_INDEX,
        "vehicle_phone_assignments",
        ["phone_identifier"],
        unique=True,
        postgresql_where=sa.text("active = true"),
    )


def downgrade() -> None:
    op.drop_index(_NEW_INDEX, table_name="vehicle_phone_assignments")
    op.create_unique_constraint(
        _OLD_UNIQUE,
        "vehicle_phone_assignments",
        ["phone_identifier"],
    )
