"""Create schema_examples table and vtv_analytics_readonly role (ML-5.4).

Revision ID: m6n7o8p9q0r1
Revises: 312c77d4ccb0
Create Date: 2026-04-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "m6n7o8p9q0r1"
down_revision: str = "312c77d4ccb0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "schema_examples",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("question_text", sa.Text(), nullable=False, unique=True),
        sa.Column("sql_query", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tags", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # Add vector column via raw SQL (pgvector type not directly supported by alembic)
    op.execute("ALTER TABLE schema_examples ADD COLUMN question_embedding vector(1024)")

    # IVFFlat index for cosine similarity search
    op.execute(
        "CREATE INDEX ix_schema_examples_embedding ON schema_examples "
        "USING ivfflat (question_embedding vector_cosine_ops) WITH (lists = 50)"
    )

    # Read-only DB role for defense-in-depth
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'vtv_analytics_readonly') THEN
                CREATE ROLE vtv_analytics_readonly NOLOGIN;
            END IF;
        END
        $$;
        GRANT USAGE ON SCHEMA public TO vtv_analytics_readonly;
        GRANT SELECT ON ALL TABLES IN SCHEMA public TO vtv_analytics_readonly;
        ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO vtv_analytics_readonly;
        """
    )


def downgrade() -> None:
    op.drop_table("schema_examples")
    op.execute("DROP ROLE IF EXISTS vtv_analytics_readonly")
