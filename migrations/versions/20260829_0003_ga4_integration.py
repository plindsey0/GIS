"""Add Google Analytics 4 typed observations.

Revision ID: 20260829_0003
Revises: 20260829_0002
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260829_0003"
down_revision: str | None = "20260829_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CORE = "gis_core"
RAW = "gis_raw"


def _common_columns() -> list[sa.Column]:
    return [
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("data_source_connection_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ingestion_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "rights_policy_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{CORE}.data_rights_policy.id"),
            nullable=False,
        ),
        sa.Column("source_record_id", sa.String(512)),
        sa.Column("observation_key", sa.String(64), nullable=False),
        sa.Column("observed_date", sa.Date(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "ingested_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("effective_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_end", sa.DateTime(timezone=True)),
        sa.Column("confidence", sa.Float()),
        sa.Column(
            "quality_flag",
            postgresql.ENUM(
                "VALID",
                "SUSPECT",
                "INVALID",
                "UNKNOWN",
                name="quality_flag",
                schema=CORE,
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("raw_payload_reference", sa.Text()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def _common_constraints(prefix: str) -> list[sa.Constraint]:
    return [
        sa.ForeignKeyConstraint(
            ["tenant_id", "site_id"],
            [f"{CORE}.site.tenant_id", f"{CORE}.site.id"],
            name=f"fk_{prefix}_site_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "data_source_connection_id"],
            [f"{CORE}.data_source_connection.tenant_id", f"{CORE}.data_source_connection.id"],
            name=f"fk_{prefix}_connection_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "site_id", "ingestion_run_id"],
            [
                f"{CORE}.ingestion_run.tenant_id",
                f"{CORE}.ingestion_run.site_id",
                f"{CORE}.ingestion_run.id",
            ],
            name=f"fk_{prefix}_run_tenant_site",
        ),
        sa.CheckConstraint(
            "effective_end IS NULL OR effective_end >= effective_start",
            name=f"ck_{prefix}_effective_window",
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name=f"ck_{prefix}_confidence",
        ),
    ]


def _create_common_indexes(table: str, prefix: str) -> None:
    op.create_index(
        f"ix_{prefix}_tenant_site_date",
        table,
        ["tenant_id", "site_id", "observed_date"],
        schema=RAW,
    )
    op.create_index(
        f"ix_{prefix}_connection_date",
        table,
        ["data_source_connection_id", "observed_date"],
        schema=RAW,
    )
    op.create_index(f"ix_{prefix}_observation_key", table, ["observation_key"], schema=RAW)
    op.create_index(f"ix_{prefix}_ingestion_run", table, ["ingestion_run_id"], schema=RAW)
    op.create_index(
        f"uq_{prefix}_current_observation",
        table,
        ["observation_key"],
        unique=True,
        schema=RAW,
        postgresql_where=sa.text("effective_end IS NULL"),
    )


def upgrade() -> None:
    op.create_table(
        "ga4_landing_page_observation",
        *_common_columns(),
        sa.Column("landing_page", sa.Text(), nullable=False),
        sa.Column("landing_page_hash", sa.String(64), nullable=False),
        sa.Column("session_default_channel_group", sa.String(255), nullable=False),
        sa.Column("session_source", sa.Text(), nullable=False),
        sa.Column("session_medium", sa.Text(), nullable=False),
        sa.Column("device_category", sa.String(64), nullable=False),
        sa.Column("country", sa.String(255), nullable=False),
        sa.Column("sessions", sa.Numeric(20, 6), nullable=False),
        sa.Column("active_users", sa.Numeric(20, 6), nullable=False),
        sa.Column("new_users", sa.Numeric(20, 6), nullable=False),
        sa.Column("engaged_sessions", sa.Numeric(20, 6), nullable=False),
        sa.Column("engagement_rate", sa.Numeric(20, 12), nullable=False),
        sa.Column("average_session_duration", sa.Numeric(20, 12), nullable=False),
        sa.Column("event_count", sa.Numeric(20, 6), nullable=False),
        sa.Column("key_events", sa.Numeric(20, 6), nullable=False),
        *_common_constraints("ga4_landing"),
        *[
            sa.CheckConstraint(f"{name} >= 0", name=f"ck_ga4_landing_{name}_nonnegative")
            for name in (
                "sessions",
                "active_users",
                "new_users",
                "engaged_sessions",
                "engagement_rate",
                "average_session_duration",
                "event_count",
                "key_events",
            )
        ],
        sa.CheckConstraint("engagement_rate <= 1", name="ck_ga4_landing_engagement_rate_max"),
        schema=RAW,
    )
    _create_common_indexes("ga4_landing_page_observation", "ga4_landing")
    op.create_index(
        "ix_ga4_landing_page_hash",
        "ga4_landing_page_observation",
        ["landing_page_hash"],
        schema=RAW,
    )

    op.create_table(
        "ga4_acquisition_observation",
        *_common_columns(),
        sa.Column("session_default_channel_group", sa.String(255), nullable=False),
        sa.Column("session_source", sa.Text(), nullable=False),
        sa.Column("source_hash", sa.String(64), nullable=False),
        sa.Column("session_medium", sa.Text(), nullable=False),
        sa.Column("medium_hash", sa.String(64), nullable=False),
        sa.Column("session_campaign", sa.Text(), nullable=False),
        sa.Column("device_category", sa.String(64), nullable=False),
        sa.Column("country", sa.String(255), nullable=False),
        sa.Column("sessions", sa.Numeric(20, 6), nullable=False),
        sa.Column("active_users", sa.Numeric(20, 6), nullable=False),
        sa.Column("new_users", sa.Numeric(20, 6), nullable=False),
        sa.Column("engaged_sessions", sa.Numeric(20, 6), nullable=False),
        sa.Column("engagement_rate", sa.Numeric(20, 12), nullable=False),
        sa.Column("event_count", sa.Numeric(20, 6), nullable=False),
        sa.Column("key_events", sa.Numeric(20, 6), nullable=False),
        *_common_constraints("ga4_acquisition"),
        *[
            sa.CheckConstraint(f"{name} >= 0", name=f"ck_ga4_acquisition_{name}_nonnegative")
            for name in (
                "sessions",
                "active_users",
                "new_users",
                "engaged_sessions",
                "engagement_rate",
                "event_count",
                "key_events",
            )
        ],
        sa.CheckConstraint("engagement_rate <= 1", name="ck_ga4_acquisition_engagement_rate_max"),
        schema=RAW,
    )
    _create_common_indexes("ga4_acquisition_observation", "ga4_acquisition")
    op.create_index(
        "ix_ga4_acquisition_channel",
        "ga4_acquisition_observation",
        ["session_default_channel_group"],
        schema=RAW,
    )
    op.create_index(
        "ix_ga4_acquisition_source_hash",
        "ga4_acquisition_observation",
        ["source_hash"],
        schema=RAW,
    )
    op.create_index(
        "ix_ga4_acquisition_medium_hash",
        "ga4_acquisition_observation",
        ["medium_hash"],
        schema=RAW,
    )

    op.create_table(
        "ga4_event_observation",
        *_common_columns(),
        sa.Column("event_name", sa.Text(), nullable=False),
        sa.Column("event_name_hash", sa.String(64), nullable=False),
        sa.Column("landing_page", sa.Text(), nullable=False),
        sa.Column("page_path", sa.Text(), nullable=False),
        sa.Column("session_default_channel_group", sa.String(255), nullable=False),
        sa.Column("device_category", sa.String(64), nullable=False),
        sa.Column("country", sa.String(255), nullable=False),
        sa.Column("event_count", sa.Numeric(20, 6), nullable=False),
        sa.Column("total_users", sa.Numeric(20, 6), nullable=False),
        sa.Column("event_count_per_active_user", sa.Numeric(20, 12), nullable=False),
        sa.Column("key_events", sa.Numeric(20, 6), nullable=False),
        *_common_constraints("ga4_event"),
        *[
            sa.CheckConstraint(f"{name} >= 0", name=f"ck_ga4_event_{name}_nonnegative")
            for name in (
                "event_count",
                "total_users",
                "event_count_per_active_user",
                "key_events",
            )
        ],
        schema=RAW,
    )
    _create_common_indexes("ga4_event_observation", "ga4_event")
    op.create_index(
        "ix_ga4_event_name_hash",
        "ga4_event_observation",
        ["event_name_hash"],
        schema=RAW,
    )


def downgrade() -> None:
    op.drop_table("ga4_event_observation", schema=RAW)
    op.drop_table("ga4_acquisition_observation", schema=RAW)
    op.drop_table("ga4_landing_page_observation", schema=RAW)
