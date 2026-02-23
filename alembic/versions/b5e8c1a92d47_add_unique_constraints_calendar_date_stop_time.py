"""add unique constraints for calendar_date and stop_time

Revision ID: b5e8c1a92d47
Revises: a3f7d2e81b4c
Create Date: 2026-02-23 06:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b5e8c1a92d47"
down_revision: str | None = "a3f7d2e81b4c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add unique constraints for GTFS composite natural keys.

    - calendar_dates: (calendar_id, date) prevents duplicate exceptions
    - stop_times: (trip_id, stop_sequence) prevents duplicate stop ordering
    """
    op.create_unique_constraint("uq_calendar_date", "calendar_dates", ["calendar_id", "date"])
    op.create_unique_constraint("uq_stop_time_trip_seq", "stop_times", ["trip_id", "stop_sequence"])


def downgrade() -> None:
    """Remove unique constraints."""
    op.drop_constraint("uq_stop_time_trip_seq", "stop_times", type_="unique")
    op.drop_constraint("uq_calendar_date", "calendar_dates", type_="unique")
