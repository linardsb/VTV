"""add alert_rules and alert_instances tables

Revision ID: c1d2e3f4a5b6
Revises: b7c8d9e0f1a2
Create Date: 2026-03-08 07:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c1d2e3f4a5b6"
down_revision: str | Sequence[str] | None = "b7c8d9e0f1a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create alert_rules and alert_instances tables."""
    op.create_table(
        "alert_rules",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("rule_type", sa.String(length=30), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False, server_default="medium"),
        sa.Column("threshold_config", JSONB(), nullable=False, server_default="{}"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
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
        sa.CheckConstraint(
            "rule_type IN ('delay_threshold', 'maintenance_due', 'registration_expiry', 'manual')",
            name="ck_alert_rules_rule_type",
        ),
        sa.CheckConstraint(
            "severity IN ('critical', 'high', 'medium', 'low', 'info')",
            name="ck_alert_rules_severity",
        ),
    )
    op.create_index(op.f("ix_alert_rules_id"), "alert_rules", ["id"], unique=False)

    op.create_table(
        "alert_instances",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False, server_default="medium"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("alert_type", sa.String(length=30), nullable=False),
        sa.Column(
            "rule_id",
            sa.Integer(),
            sa.ForeignKey("alert_rules.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("source_entity_type", sa.String(length=20), nullable=True),
        sa.Column("source_entity_id", sa.String(length=100), nullable=True),
        sa.Column("details", JSONB(), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "acknowledged_by_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint(
            "status IN ('active', 'acknowledged', 'resolved')",
            name="ck_alert_instances_status",
        ),
    )
    op.create_index(op.f("ix_alert_instances_id"), "alert_instances", ["id"], unique=False)
    op.create_index(op.f("ix_alert_instances_status"), "alert_instances", ["status"], unique=False)
    op.create_index(
        op.f("ix_alert_instances_rule_id"), "alert_instances", ["rule_id"], unique=False
    )
    op.create_index(
        op.f("ix_alert_instances_source_entity_id"),
        "alert_instances",
        ["source_entity_id"],
        unique=False,
    )
    # Partial unique index for deduplication: only one active alert per rule+entity combo
    op.create_index(
        "ix_alert_dedup",
        "alert_instances",
        ["rule_id", "source_entity_type", "source_entity_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )


def downgrade() -> None:
    """Drop alert_instances and alert_rules tables."""
    op.drop_index("ix_alert_dedup", table_name="alert_instances")
    op.drop_index(op.f("ix_alert_instances_source_entity_id"), table_name="alert_instances")
    op.drop_index(op.f("ix_alert_instances_rule_id"), table_name="alert_instances")
    op.drop_index(op.f("ix_alert_instances_status"), table_name="alert_instances")
    op.drop_index(op.f("ix_alert_instances_id"), table_name="alert_instances")
    op.drop_table("alert_instances")
    op.drop_index(op.f("ix_alert_rules_id"), table_name="alert_rules")
    op.drop_table("alert_rules")
