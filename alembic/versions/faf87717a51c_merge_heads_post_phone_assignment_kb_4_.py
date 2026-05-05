"""merge heads post phone-assignment + kb-4/kb-5/lv-3-4

Revision ID: faf87717a51c
Revises: 4863b96d1d30, y9z0a1b2c3d4
Create Date: 2026-05-05 16:45:33.287100

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "faf87717a51c"  # pragma: allowlist secret
down_revision: str | Sequence[str] | None = (
    "4863b96d1d30",  # pragma: allowlist secret
    "y9z0a1b2c3d4",  # pragma: allowlist secret
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
