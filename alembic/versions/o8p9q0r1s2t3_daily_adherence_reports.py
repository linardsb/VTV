"""Add daily_adherence_reports table + schedule_adherence alert type (ML-5.2).

Revision ID: o8p9q0r1s2t3
Revises: n7o8p9q0r1s2
Create Date: 2026-04-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "o8p9q0r1s2t3"
down_revision: str = "n7o8p9q0r1s2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_RULE_TYPES = (
    "'delay_threshold', 'maintenance_due', 'registration_expiry', 'manual', "
    "'geofence_enter', 'geofence_exit', 'geofence_dwell', "
    "'stuck_vehicle', 'gps_gap', 'feed_outage', 'off_route'"
)
_NEW_RULE_TYPES = (
    "'delay_threshold', 'maintenance_due', 'registration_expiry', 'manual', "
    "'geofence_enter', 'geofence_exit', 'geofence_dwell', "
    "'stuck_vehicle', 'gps_gap', 'feed_outage', 'off_route', 'schedule_adherence'"
)


def upgrade() -> None:
    """Create daily_adherence_reports table and update alert rule_type CHECK."""
    op.create_table(
        "daily_adherence_reports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("overall_pct", sa.Float(), nullable=False),
        sa.Column("total_trips", sa.Integer(), nullable=False),
        sa.Column("on_time_trips", sa.Integer(), nullable=False),
        sa.Column("late_trips", sa.Integer(), nullable=False),
        sa.Column("early_trips", sa.Integer(), nullable=False),
        sa.Column("per_route_json", postgresql.JSONB(), nullable=False),
        sa.Column("per_hour_json", postgresql.JSONB(), nullable=False),
        sa.Column("anomaly_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("alert_triggered", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("report_date", name="uq_daily_adherence_reports_date"),
    )
    op.create_index(
        "ix_daily_adherence_reports_report_date",
        "daily_adherence_reports",
        ["report_date"],
    )

    # Update CHECK constraint to include 'schedule_adherence'
    op.drop_constraint("ck_alert_rules_rule_type", "alert_rules", type_="check")
    op.create_check_constraint(
        "ck_alert_rules_rule_type",
        "alert_rules",
        f"rule_type IN ({_NEW_RULE_TYPES})",
    )


def downgrade() -> None:
    """Drop daily_adherence_reports table and restore old CHECK."""
    op.drop_constraint("ck_alert_rules_rule_type", "alert_rules", type_="check")
    op.create_check_constraint(
        "ck_alert_rules_rule_type",
        "alert_rules",
        f"rule_type IN ({_OLD_RULE_TYPES})",
    )
    op.drop_index("ix_daily_adherence_reports_report_date", "daily_adherence_reports")
    op.drop_table("daily_adherence_reports")
