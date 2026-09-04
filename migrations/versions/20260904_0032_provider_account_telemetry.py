"""Add minimal provider account telemetry; no provider configuration or rights changes."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260904_0032"
down_revision = "20260904_0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "provider_account_telemetry",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("connection_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("failure_category", sa.String(100)),
        sa.Column("actor", sa.String(255), nullable=False),
        sa.Column("normalized", postgresql.JSONB(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "connection_id"],
            ["gis_core.data_source_connection.tenant_id", "gis_core.data_source_connection.id"],
            name="fk_account_telemetry_connection_scope",
        ),
        sa.CheckConstraint(
            "status IN ('CURRENT', 'UNAVAILABLE')", name="ck_account_telemetry_status"
        ),
        schema="gis_core",
    )
    op.create_index(
        "ix_account_telemetry_latest",
        "provider_account_telemetry",
        ["connection_id", "checked_at"],
        schema="gis_core",
    )


def downgrade() -> None:
    op.drop_table("provider_account_telemetry", schema="gis_core")
