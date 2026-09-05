"""Record provider-control recovery and historical completeness.

Revision ID: 20260905_0033
Revises: 20260904_0032
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260905_0033"
down_revision: Union[str, None] = "20260904_0032"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "provider_control_recovery_incident",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("incident_key", sa.String(length=160), nullable=False),
        sa.Column("classification", sa.String(length=160), nullable=False),
        sa.Column("environment", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recovery_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recovery_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actor", sa.String(length=255), nullable=False),
        sa.Column("affected_tables", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("row_counts", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("history_completeness", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("exact_restoration_available", sa.Boolean(), nullable=False),
        sa.Column("historical_rows_recreated", sa.Integer(), nullable=False),
        sa.Column("backup_path", sa.Text(), nullable=False),
        sa.Column("documentation_reference", sa.Text(), nullable=False),
        sa.Column("git_branch", sa.String(length=255), nullable=False),
        sa.Column("git_sha", sa.String(length=40), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("incident_key"),
        schema="gis_core",
    )
    op.add_column(
        "provider_policy_audit_event",
        sa.Column("recovery_incident_id", postgresql.UUID(as_uuid=True), nullable=True),
        schema="gis_core",
    )
    op.create_foreign_key(
        "fk_provider_audit_recovery_incident",
        "provider_policy_audit_event",
        "provider_control_recovery_incident",
        ["recovery_incident_id"],
        ["id"],
        source_schema="gis_core",
        referent_schema="gis_core",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_provider_audit_recovery_incident",
        "provider_policy_audit_event",
        schema="gis_core",
        type_="foreignkey",
    )
    op.drop_column("provider_policy_audit_event", "recovery_incident_id", schema="gis_core")
    op.drop_table("provider_control_recovery_incident", schema="gis_core")
