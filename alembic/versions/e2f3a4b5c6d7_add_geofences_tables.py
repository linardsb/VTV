"""Add geofences and geofence_events tables.

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-03-08
"""

from collections.abc import Sequence

import geoalchemy2
import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e2f3a4b5c6d7"
down_revision: str | None = "d1e2f3a4b5c6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(name: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = :name)"
        ),
        {"name": name},
    ).scalar()
    return bool(result)


def _index_exists(name: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(
        sa.text("SELECT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = :name)"),
        {"name": name},
    ).scalar()
    return bool(result)


def _constraint_exists(name: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.table_constraints "
            "WHERE constraint_name = :name)"
        ),
        {"name": name},
    ).scalar()
    return bool(result)


def upgrade() -> None:
    """Create geofences and geofence_events tables, update alert_rules constraint."""
    # Create geofences table with PostGIS geometry
    if not _table_exists("geofences"):
        op.create_table(
            "geofences",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("zone_type", sa.String(20), nullable=False),
            sa.Column(
                "geometry",
                geoalchemy2.types.Geometry(  # type: ignore[attr-defined]
                    geometry_type="POLYGON", srid=4326
                ),
                nullable=False,
            ),
            sa.Column("color", sa.String(7), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("alert_on_enter", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("alert_on_exit", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("alert_on_dwell", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("dwell_threshold_minutes", sa.Integer(), nullable=True),
            sa.Column(
                "alert_severity", sa.String(20), nullable=False, server_default=sa.text("'medium'")
            ),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.CheckConstraint(
                "zone_type IN ('depot', 'terminal', 'restricted', 'customer', 'custom')",
                name="ck_geofences_zone_type",
            ),
            sa.CheckConstraint(
                "alert_severity IN ('critical', 'high', 'medium', 'low', 'info')",
                name="ck_geofences_alert_severity",
            ),
        )

    if not _index_exists("ix_geofences_id"):
        op.create_index("ix_geofences_id", "geofences", ["id"])
    if not _index_exists("ix_geofences_name"):
        op.create_index("ix_geofences_name", "geofences", ["name"])
    if not _index_exists("ix_geofences_geometry_active"):
        op.create_index(
            "ix_geofences_geometry_active",
            "geofences",
            ["geometry"],
            postgresql_using="gist",
            postgresql_where=sa.text("is_active = true"),
        )

    # Create geofence_events table
    if not _table_exists("geofence_events"):
        op.create_table(
            "geofence_events",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column(
                "geofence_id",
                sa.Integer(),
                nullable=False,
            ),
            sa.Column("vehicle_id", sa.String(100), nullable=False),
            sa.Column("event_type", sa.String(20), nullable=False),
            sa.Column("entered_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("exited_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("dwell_seconds", sa.Integer(), nullable=True),
            sa.Column("latitude", sa.Float(), nullable=False),
            sa.Column("longitude", sa.Float(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(
                ["geofence_id"],
                ["geofences.id"],
                ondelete="CASCADE",
            ),
            sa.CheckConstraint(
                "event_type IN ('enter', 'exit', 'dwell_exceeded')",
                name="ck_geofence_events_event_type",
            ),
        )

    if not _index_exists("ix_geofence_events_id"):
        op.create_index("ix_geofence_events_id", "geofence_events", ["id"])
    if not _index_exists("ix_geofence_events_geofence_id"):
        op.create_index("ix_geofence_events_geofence_id", "geofence_events", ["geofence_id"])
    if not _index_exists("ix_geofence_events_vehicle_id"):
        op.create_index("ix_geofence_events_vehicle_id", "geofence_events", ["vehicle_id"])
    if not _index_exists("ix_geofence_events_geofence_entered"):
        op.create_index(
            "ix_geofence_events_geofence_entered",
            "geofence_events",
            ["geofence_id", "entered_at"],
        )

    # Update alert_rules CHECK constraint to include geofence types
    if _constraint_exists("ck_alert_rules_rule_type"):
        op.drop_constraint("ck_alert_rules_rule_type", "alert_rules", type_="check")
    op.create_check_constraint(
        "ck_alert_rules_rule_type",
        "alert_rules",
        "rule_type IN ('delay_threshold', 'maintenance_due', 'registration_expiry', 'manual', 'geofence_enter', 'geofence_exit', 'geofence_dwell')",
    )


def downgrade() -> None:
    """Drop geofence tables and restore original alert_rules constraint."""
    # Restore original alert_rules CHECK constraint
    op.drop_constraint("ck_alert_rules_rule_type", "alert_rules", type_="check")
    op.create_check_constraint(
        "ck_alert_rules_rule_type",
        "alert_rules",
        "rule_type IN ('delay_threshold', 'maintenance_due', 'registration_expiry', 'manual')",
    )

    op.drop_index("ix_geofence_events_geofence_entered", table_name="geofence_events")
    op.drop_index("ix_geofence_events_vehicle_id", table_name="geofence_events")
    op.drop_index("ix_geofence_events_geofence_id", table_name="geofence_events")
    op.drop_index("ix_geofence_events_id", table_name="geofence_events")
    op.drop_table("geofence_events")

    op.drop_index("ix_geofences_geometry_active", table_name="geofences")
    op.drop_index("ix_geofences_name", table_name="geofences")
    op.drop_index("ix_geofences_id", table_name="geofences")
    op.drop_table("geofences")
