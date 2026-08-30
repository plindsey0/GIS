"""add external search intelligence

Revision ID: 20260830_0009
Revises: 20260830_0008
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260830_0009"
down_revision: Union[str, None] = "20260830_0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "external_search_observation",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("site_id", sa.UUID(), nullable=False),
        sa.Column("ingestion_run_id", sa.UUID(), nullable=False),
        sa.Column("data_source_connection_id", sa.UUID(), nullable=False),
        sa.Column("rights_policy_id", sa.UUID(), nullable=False),
        sa.Column("rights_policy_version", sa.String(100), nullable=False),
        sa.Column("observation_type", sa.String(50), nullable=False),
        sa.Column("target_domain", sa.String(253), nullable=False),
        sa.Column("country_code", sa.String(2)),
        sa.Column("location_code", sa.Integer()),
        sa.Column("location_name", sa.String(255)),
        sa.Column("language_code", sa.String(16), nullable=False),
        sa.Column("device", sa.String(32)),
        sa.Column("observed_date", sa.Date(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observation_key", sa.String(64), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("provider_task_id", sa.String(255)),
        sa.Column("request_count", sa.Integer(), nullable=False),
        sa.Column("items_returned", sa.Integer(), nullable=False),
        sa.Column("provider_reported_cost", sa.Numeric(20, 8)),
        sa.Column("estimated_cost", sa.Numeric(20, 8)),
        sa.Column("cost_metadata", postgresql.JSONB(), nullable=False),
        sa.Column("provider_metadata", postgresql.JSONB(), nullable=False),
        sa.Column("effective_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_end", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "effective_end IS NULL OR effective_end >= effective_start",
            name="ck_external_search_effective_window",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "site_id"], ["gis_core.site.tenant_id", "gis_core.site.id"]
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "site_id", "ingestion_run_id"],
            [
                "gis_core.ingestion_run.tenant_id",
                "gis_core.ingestion_run.site_id",
                "gis_core.ingestion_run.id",
            ],
        ),
        sa.ForeignKeyConstraint(
            ["data_source_connection_id"], ["gis_core.data_source_connection.id"]
        ),
        sa.ForeignKeyConstraint(["rights_policy_id"], ["gis_core.data_rights_policy.id"]),
        sa.PrimaryKeyConstraint("id"),
        schema="gis_raw",
    )
    op.create_index(
        "ix_external_search_target_date",
        "external_search_observation",
        ["target_domain", "observed_date"],
        schema="gis_raw",
    )
    op.create_index(
        "ix_external_search_run",
        "external_search_observation",
        ["ingestion_run_id"],
        schema="gis_raw",
    )
    op.create_index(
        "uq_external_search_current",
        "external_search_observation",
        ["observation_key"],
        unique=True,
        schema="gis_raw",
        postgresql_where=sa.text("effective_end IS NULL"),
    )
    op.create_table(
        "external_keyword_ranking",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("external_search_observation_id", sa.UUID(), nullable=False),
        sa.Column("keyword", sa.Text(), nullable=False),
        sa.Column("normalized_keyword", sa.Text(), nullable=False),
        sa.Column("ranking_domain", sa.String(253), nullable=False),
        sa.Column("ranking_url", sa.Text()),
        sa.Column("normalized_url", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("prior_position", sa.Integer()),
        sa.Column("ranking_type", sa.String(100), nullable=False),
        sa.Column("search_volume", sa.Integer()),
        sa.Column("cpc", sa.Numeric(20, 8)),
        sa.Column("paid_competition", sa.Numeric(20, 8)),
        sa.Column("competition_index", sa.Integer()),
        sa.Column("search_intent", sa.String(100)),
        sa.Column("keyword_difficulty", sa.Numeric(20, 8)),
        sa.Column("estimated_traffic", sa.Numeric(20, 8)),
        sa.Column("estimated_traffic_share", sa.Numeric(20, 8)),
        sa.Column("monthly_searches", postgresql.JSONB(), nullable=False),
        sa.Column("metric_semantics", postgresql.JSONB(), nullable=False),
        sa.Column("provider_metadata", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("position > 0", name="ck_external_keyword_position"),
        sa.ForeignKeyConstraint(
            ["external_search_observation_id"],
            ["gis_raw.external_search_observation.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "external_search_observation_id",
            "normalized_keyword",
            "ranking_domain",
            "normalized_url",
            name="uq_external_keyword_observation_rank",
        ),
        schema="gis_raw",
    )
    op.create_index(
        "ix_external_keyword_normalized",
        "external_keyword_ranking",
        ["normalized_keyword"],
        schema="gis_raw",
    )
    op.create_index(
        "ix_external_keyword_domain",
        "external_keyword_ranking",
        ["ranking_domain"],
        schema="gis_raw",
    )
    op.create_index(
        "ix_external_keyword_url", "external_keyword_ranking", ["normalized_url"], schema="gis_raw"
    )
    op.create_table(
        "external_competitor_observation",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("external_search_observation_id", sa.UUID(), nullable=False),
        sa.Column("competitor_domain", sa.String(253), nullable=False),
        sa.Column("target_keyword_count", sa.Integer()),
        sa.Column("competitor_keyword_count", sa.Integer()),
        sa.Column("shared_keyword_count", sa.Integer()),
        sa.Column("provider_relevance", sa.Numeric(20, 8)),
        sa.Column("provider_estimated_traffic", sa.Numeric(20, 8)),
        sa.Column("provider_visibility", sa.Numeric(20, 8)),
        sa.Column("gis_competitive_strength", sa.Numeric(20, 8)),
        sa.Column("metric_semantics", postgresql.JSONB(), nullable=False),
        sa.Column("provider_metadata", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["external_search_observation_id"],
            ["gis_raw.external_search_observation.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "external_search_observation_id",
            "competitor_domain",
            name="uq_external_competitor_observation_domain",
        ),
        schema="gis_raw",
    )
    op.create_index(
        "ix_external_competitor_domain",
        "external_competitor_observation",
        ["competitor_domain"],
        schema="gis_raw",
    )


def downgrade() -> None:
    op.drop_table("external_competitor_observation", schema="gis_raw")
    op.drop_table("external_keyword_ranking", schema="gis_raw")
    op.drop_table("external_search_observation", schema="gis_raw")
