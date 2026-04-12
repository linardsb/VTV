"""merge_all_heads

Revision ID: 312c77d4ccb0
Revises: 91178ed23fd4, l5m6n7o8p9q0
Create Date: 2026-04-12 17:57:46.182040

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "312c77d4ccb0"
down_revision: str | Sequence[str] | None = ("91178ed23fd4", "l5m6n7o8p9q0")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
