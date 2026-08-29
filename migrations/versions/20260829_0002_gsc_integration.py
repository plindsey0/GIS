"""Add Google Search Console typed observations.

Revision ID: 20260829_0002
Revises: 20260829_0001
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260829_0002"
down_revision: str | None = "20260829_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CORE = "gis_core"
RAW = "gis_raw"


def upgrade() -> None:
    op.execute(sa.schema.CreateSchema(RAW))
    op.create_unique_constraint(
        "uq_ingestion_run_tenant_id", "ingestion_run", ["tenant_id", "id"], schema=CORE
    )
    op.create_unique_constraint(
        "uq_ingestion_run_tenant_site_id",
        "ingestion_run",
        ["tenant_id", "site_id", "id"],
        schema=CORE,
    )
    op.create_table(
        "gsc_search_observation",
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
        sa.Column("collection_grain", sa.String(32), nullable=False),
        sa.Column("observed_date", sa.Date(), nullable=False),
        sa.Column("query", sa.Text()),
        sa.Column("query_hash", sa.String(64)),
        sa.Column("page", sa.Text()),
        sa.Column("page_hash", sa.String(64)),
        sa.Column("country", sa.String(16)),
        sa.Column("device", sa.String(32)),
        sa.Column("search_appearance", sa.String(255)),
        sa.Column("search_type", sa.String(32), nullable=False),
        sa.Column("clicks", sa.Numeric(20, 6), nullable=False),
        sa.Column("impressions", sa.Numeric(20, 6), nullable=False),
        sa.Column("ctr", sa.Numeric(20, 12), nullable=False),
        sa.Column("position", sa.Numeric(20, 12), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["tenant_id", "site_id"],
            [f"{CORE}.site.tenant_id", f"{CORE}.site.id"],
            name="fk_gsc_observation_site_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "data_source_connection_id"],
            [f"{CORE}.data_source_connection.tenant_id", f"{CORE}.data_source_connection.id"],
            name="fk_gsc_observation_connection_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "site_id", "ingestion_run_id"],
            [
                f"{CORE}.ingestion_run.tenant_id",
                f"{CORE}.ingestion_run.site_id",
                f"{CORE}.ingestion_run.id",
            ],
            name="fk_gsc_observation_run_tenant_site",
        ),
        sa.CheckConstraint("clicks >= 0", name="ck_gsc_clicks_nonnegative"),
        sa.CheckConstraint("impressions >= 0", name="ck_gsc_impressions_nonnegative"),
        sa.CheckConstraint("ctr >= 0", name="ck_gsc_ctr_nonnegative"),
        sa.CheckConstraint("position >= 0", name="ck_gsc_position_nonnegative"),
        sa.CheckConstraint(
            "effective_end IS NULL OR effective_end >= effective_start",
            name="ck_gsc_effective_window",
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)", name="ck_gsc_confidence"
        ),
        schema=RAW,
    )
    op.create_index(
        "ix_gsc_tenant_site_date",
        "gsc_search_observation",
        ["tenant_id", "site_id", "observed_date"],
        schema=RAW,
    )
    op.create_index(
        "ix_gsc_connection_date",
        "gsc_search_observation",
        ["data_source_connection_id", "observed_date"],
        schema=RAW,
    )
    op.create_index("ix_gsc_observed_date", "gsc_search_observation", ["observed_date"], schema=RAW)
    op.create_index("ix_gsc_page_hash", "gsc_search_observation", ["page_hash"], schema=RAW)
    op.create_index("ix_gsc_query_hash", "gsc_search_observation", ["query_hash"], schema=RAW)
    op.create_index(
        "ix_gsc_observation_key", "gsc_search_observation", ["observation_key"], schema=RAW
    )
    op.create_index(
        "ix_gsc_ingestion_run", "gsc_search_observation", ["ingestion_run_id"], schema=RAW
    )
    op.create_index(
        "uq_gsc_current_observation",
        "gsc_search_observation",
        ["observation_key"],
        unique=True,
        schema=RAW,
        postgresql_where=sa.text("effective_end IS NULL"),
    )


def downgrade() -> None:
    op.drop_table("gsc_search_observation", schema=RAW)
    op.execute(sa.schema.DropSchema(RAW))
    op.drop_constraint("uq_ingestion_run_tenant_site_id", "ingestion_run", schema=CORE)
    op.drop_constraint("uq_ingestion_run_tenant_id", "ingestion_run", schema=CORE)
