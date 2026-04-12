"""Add off_route to alert_rules rule_type CHECK constraint (ML-4.1).

Revision ID: n7o8p9q0r1s2
Revises: m6n7o8p9q0r1
Create Date: 2026-04-12
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "n7o8p9q0r1s2"
down_revision: str = "m6n7o8p9q0r1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_alert_rules_rule_type", "alert_rules")
    op.create_check_constraint(
        "ck_alert_rules_rule_type",
        "alert_rules",
        "rule_type IN ('delay_threshold', 'maintenance_due', 'registration_expiry', 'manual', 'geofence_enter', 'geofence_exit', 'geofence_dwell', 'stuck_vehicle', 'gps_gap', 'feed_outage', 'off_route')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_alert_rules_rule_type", "alert_rules")
    op.create_check_constraint(
        "ck_alert_rules_rule_type",
        "alert_rules",
        "rule_type IN ('delay_threshold', 'maintenance_due', 'registration_expiry', 'manual', 'geofence_enter', 'geofence_exit', 'geofence_dwell', 'stuck_vehicle', 'gps_gap', 'feed_outage')",
    )
