"""Add crowding_prediction to alert_rules rule_type CHECK constraint (ML-3.3).

Revision ID: r2s3t4u5v6w7
Revises: q1r2s3t4u5v6
Create Date: 2026-04-13
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "r2s3t4u5v6w7"
down_revision: str = "q1r2s3t4u5v6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ALL_TYPES_NEW = (
    "rule_type IN ("
    "'delay_threshold', 'maintenance_due', 'registration_expiry', 'manual', "
    "'geofence_enter', 'geofence_exit', 'geofence_dwell', "
    "'stuck_vehicle', 'gps_gap', 'feed_outage', "
    "'off_route', 'schedule_adherence', 'crowding_prediction')"
)

_ALL_TYPES_OLD = (
    "rule_type IN ("
    "'delay_threshold', 'maintenance_due', 'registration_expiry', 'manual', "
    "'geofence_enter', 'geofence_exit', 'geofence_dwell', "
    "'stuck_vehicle', 'gps_gap', 'feed_outage', "
    "'off_route', 'schedule_adherence')"
)


def upgrade() -> None:
    op.drop_constraint("ck_alert_rules_rule_type", "alert_rules")
    op.create_check_constraint("ck_alert_rules_rule_type", "alert_rules", _ALL_TYPES_NEW)


def downgrade() -> None:
    op.drop_constraint("ck_alert_rules_rule_type", "alert_rules")
    op.create_check_constraint("ck_alert_rules_rule_type", "alert_rules", _ALL_TYPES_OLD)
