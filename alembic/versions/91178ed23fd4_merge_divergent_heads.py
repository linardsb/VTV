"""merge_divergent_heads

Revision ID: 91178ed23fd4
Revises: i2j3k4l5m6n7, k4l5m6n7o8p9
Create Date: 2026-04-12 17:57:18.002442

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "91178ed23fd4"
down_revision: str | Sequence[str] | None = ("i2j3k4l5m6n7", "k4l5m6n7o8p9")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
