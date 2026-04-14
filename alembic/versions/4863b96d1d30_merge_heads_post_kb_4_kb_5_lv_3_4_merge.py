"""merge heads post KB-4+KB-5+LV-3.4 merge

Revision ID: 4863b96d1d30
Revises: 1f0fc7681339, e5n6t6k6b6, v6w7x8y9z0a1
Create Date: 2026-04-14 16:01:05.329401

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4863b96d1d30'
down_revision: Union[str, Sequence[str], None] = ('1f0fc7681339', 'e5n6t6k6b6', 'v6w7x8y9z0a1')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
