"""add data obligation control plane

Revision ID: 20260902_0023
Revises: 20260831_0022
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260902_0023"
down_revision: Union[str, None] = "20260831_0022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE gis_core.trigger_type ADD VALUE IF NOT EXISTS 'CATCH_UP'")
    op.execute("ALTER TYPE gis_core.trigger_type ADD VALUE IF NOT EXISTS 'RECONCILIATION'")
    obligation_status = postgresql.ENUM(
        "PENDING",
        "RUNNING",
        "RETRY_WAIT",
        "PROVIDER_DATA_PENDING",
        "SATISFIED",
        "EXPIRED",
        "BLOCKED",
        "FAILED",
        name="obligation_status",
        schema="gis_core",
        create_type=False,
    )
    completion_outcome = postgresql.ENUM(
        "SUCCEEDED_COMPLETE",
        "SUCCEEDED_NO_DATA_EXPECTED",
        "PROVIDER_DATA_PENDING",
        "PARTIAL",
        "FAILED_RETRYABLE",
        "FAILED_TERMINAL",
        "BLOCKED_RIGHTS",
        "BLOCKED_BUDGET",
        "BLOCKED_CONFIGURATION",
        "ABANDONED",
        name="completion_outcome",
        schema="gis_core",
        create_type=False,
    )
    failure_category = postgresql.ENUM(
        "TRANSIENT_NETWORK",
        "PROVIDER_429",
        "PROVIDER_5XX",
        "PROVIDER_DATA_PENDING",
        "AUTHENTICATION_FAILED",
        "AUTHORIZATION_FAILED",
        "CONFIGURATION_ERROR",
        "RIGHTS_BLOCKED",
        "BUDGET_BLOCKED",
        "INVALID_REQUEST",
        "INTERNAL_PROCESSING_ERROR",
        "ABANDONED_EXECUTION",
        "UNKNOWN_RETRYABLE",
        "UNKNOWN_TERMINAL",
        name="failure_category",
        schema="gis_core",
        create_type=False,
    )
    executor_role = postgresql.ENUM(
        "SCHEDULER", "WORKER", name="executor_role", schema="gis_core", create_type=False
    )
    readiness_state = postgresql.ENUM(
        "READY",
        "READY_WITH_STALE_INPUT",
        "DEGRADED",
        "BLOCKED",
        name="readiness_state",
        schema="gis_core",
        create_type=False,
    )
    for enum in (
        obligation_status,
        completion_outcome,
        failure_category,
        executor_role,
        readiness_state,
    ):
        enum.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "schedule_definition",
        sa.Column(
            "automatic_catchup_seconds", sa.Integer(), server_default="172800", nullable=False
        ),
        schema="gis_core",
    )
    op.add_column(
        "schedule_definition",
        sa.Column(
            "terminal_horizon_seconds", sa.Integer(), server_default="604800", nullable=False
        ),
        schema="gis_core",
    )
    op.add_column(
        "schedule_definition",
        sa.Column(
            "retry_profile", sa.String(50), server_default="LOCAL_DETERMINISTIC", nullable=False
        ),
        schema="gis_core",
    )
    op.add_column(
        "schedule_definition",
        sa.Column("reconciliation_window_days", sa.Integer(), server_default="0", nullable=False),
        schema="gis_core",
    )
    op.add_column(
        "schedule_definition",
        sa.Column("policy_version", sa.String(50), server_default="1", nullable=False),
        schema="gis_core",
    )
    op.create_check_constraint(
        "ck_schedule_catchup_positive",
        "schedule_definition",
        "automatic_catchup_seconds >= 0",
        schema="gis_core",
    )
    op.create_check_constraint(
        "ck_schedule_terminal_horizon",
        "schedule_definition",
        "terminal_horizon_seconds > 0",
        schema="gis_core",
    )
    op.create_check_constraint(
        "ck_schedule_reconciliation_window",
        "schedule_definition",
        "reconciliation_window_days >= 0",
        schema="gis_core",
    )

    op.create_table(
        "orchestration_obligation",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("site_id", sa.UUID(), nullable=True),
        sa.Column("pipeline_id", sa.UUID(), nullable=False),
        sa.Column("schedule_id", sa.UUID(), nullable=False),
        sa.Column("target_id", sa.UUID(), nullable=True),
        sa.Column("data_source_connection_id", sa.UUID(), nullable=True),
        sa.Column("policy_version", sa.String(50), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", obligation_status, nullable=False),
        sa.Column("completion_outcome", completion_outcome, nullable=True),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("satisfied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ingestion_run_id", sa.UUID(), nullable=True),
        sa.Column("failure_category", failure_category, nullable=True),
        sa.Column("status_reason", sa.Text(), nullable=True),
        sa.Column(
            "metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
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
        sa.CheckConstraint("window_end > window_start", name="ck_obligation_window"),
        sa.CheckConstraint("attempt_count >= 0", name="ck_obligation_attempt_count"),
        sa.ForeignKeyConstraint(["tenant_id"], ["gis_core.tenant.id"]),
        sa.ForeignKeyConstraint(["pipeline_id"], ["gis_core.pipeline_definition.id"]),
        sa.ForeignKeyConstraint(["schedule_id"], ["gis_core.schedule_definition.id"]),
        sa.ForeignKeyConstraint(["target_id"], ["gis_core.scheduled_target.id"]),
        sa.ForeignKeyConstraint(
            ["data_source_connection_id"], ["gis_core.data_source_connection.id"]
        ),
        sa.ForeignKeyConstraint(["ingestion_run_id"], ["gis_core.ingestion_run.id"]),
        sa.PrimaryKeyConstraint("id"),
        schema="gis_core",
    )
    op.create_index(
        "uq_obligation_identity",
        "orchestration_obligation",
        ["schedule_id", "target_id", "window_start", "window_end", "policy_version"],
        unique=True,
        schema="gis_core",
        postgresql_nulls_not_distinct=True,
    )
    op.create_index(
        "ix_obligation_queue",
        "orchestration_obligation",
        ["status", "next_attempt_at", "due_at"],
        schema="gis_core",
    )
    op.create_index(
        "ix_obligation_scope",
        "orchestration_obligation",
        ["tenant_id", "site_id", "pipeline_id", "due_at"],
        schema="gis_core",
    )

    op.create_table(
        "executor_heartbeat",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("executor_id", sa.String(255), nullable=False),
        sa.Column("role", executor_role, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("executor_id", "role", name="uq_executor_heartbeat_identity"),
        schema="gis_core",
    )
    op.create_index(
        "ix_executor_heartbeat_liveness",
        "executor_heartbeat",
        ["role", "last_heartbeat_at"],
        schema="gis_core",
    )

    op.add_column(
        "orchestration_run", sa.Column("obligation_id", sa.UUID(), nullable=True), schema="gis_core"
    )
    op.add_column(
        "orchestration_run",
        sa.Column("completion_outcome", completion_outcome, nullable=True),
        schema="gis_core",
    )
    op.add_column(
        "orchestration_run",
        sa.Column("readiness_state", readiness_state, server_default="READY", nullable=False),
        schema="gis_core",
    )
    op.add_column(
        "orchestration_run",
        sa.Column(
            "readiness_detail",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        schema="gis_core",
    )
    op.create_foreign_key(
        "fk_orchestration_run_obligation",
        "orchestration_run",
        "orchestration_obligation",
        ["obligation_id"],
        ["id"],
        source_schema="gis_core",
        referent_schema="gis_core",
    )
    op.create_index(
        "ix_orchestration_run_obligation", "orchestration_run", ["obligation_id"], schema="gis_core"
    )

    op.add_column(
        "execution_attempt",
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        schema="gis_core",
    )
    op.add_column(
        "execution_attempt",
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        schema="gis_core",
    )
    op.add_column(
        "execution_attempt",
        sa.Column("failure_category", failure_category, nullable=True),
        schema="gis_core",
    )
    op.add_column(
        "execution_attempt",
        sa.Column("retry_after_at", sa.DateTime(timezone=True), nullable=True),
        schema="gis_core",
    )


def downgrade() -> None:
    op.drop_column("execution_attempt", "retry_after_at", schema="gis_core")
    op.drop_column("execution_attempt", "failure_category", schema="gis_core")
    op.drop_column("execution_attempt", "lease_expires_at", schema="gis_core")
    op.drop_column("execution_attempt", "heartbeat_at", schema="gis_core")
    op.drop_index(
        "ix_orchestration_run_obligation", table_name="orchestration_run", schema="gis_core"
    )
    op.drop_constraint(
        "fk_orchestration_run_obligation",
        "orchestration_run",
        schema="gis_core",
        type_="foreignkey",
    )
    for column in ("readiness_detail", "readiness_state", "completion_outcome", "obligation_id"):
        op.drop_column("orchestration_run", column, schema="gis_core")
    op.drop_table("executor_heartbeat", schema="gis_core")
    op.drop_table("orchestration_obligation", schema="gis_core")
    for constraint in (
        "ck_schedule_reconciliation_window",
        "ck_schedule_terminal_horizon",
        "ck_schedule_catchup_positive",
    ):
        op.drop_constraint(constraint, "schedule_definition", schema="gis_core", type_="check")
    for column in (
        "policy_version",
        "reconciliation_window_days",
        "retry_profile",
        "terminal_horizon_seconds",
        "automatic_catchup_seconds",
    ):
        op.drop_column("schedule_definition", column, schema="gis_core")
    for name in (
        "readiness_state",
        "executor_role",
        "failure_category",
        "completion_outcome",
        "obligation_status",
    ):
        postgresql.ENUM(name=name, schema="gis_core").drop(op.get_bind(), checkfirst=True)
