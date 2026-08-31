"""add market intelligence

Revision ID: 20260830_0015
Revises: 20260830_0014
Create Date: 2026-08-30
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260830_0015"
down_revision: Union[str, None] = "20260830_0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _enum(name: str) -> postgresql.ENUM:
    return postgresql.ENUM(name=name, schema="gis_core", create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    enums = {
        "market_status": ["DRAFT", "ACTIVE", "SUPERSEDED"],
        "market_type": [
            "SEARCH_MARKET",
            "TOPIC_MARKET",
            "PRODUCT_CATEGORY",
            "COMPETITOR_MARKET",
            "CONTENT_MARKET",
            "CUSTOM",
        ],
        "market_member_type": [
            "TRACKED_QUERY",
            "QUERY_PATTERN",
            "TOPIC",
            "DOMAIN",
            "PAGE",
            "COMPETITOR",
            "MANUAL_SEED",
        ],
        "market_inclusion": ["INCLUDE", "EXCLUDE"],
        "market_coverage_status": ["COMPLETE", "PARTIAL", "SPARSE", "STALE", "UNKNOWN"],
        "market_participant_class": [
            "OWNED",
            "DIRECT",
            "ADJACENT",
            "PERIPHERAL",
            "EMERGING",
            "UNKNOWN",
        ],
    }
    for name, values in enums.items():
        postgresql.ENUM(*values, name=name, schema="gis_core").create(bind, checkfirst=True)

    op.create_table(
        "market_definition",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column(
            "organization_id", sa.UUID(), sa.ForeignKey("gis_core.organization.id"), nullable=False
        ),
        sa.Column("site_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("status", _enum("market_status"), nullable=False),
        sa.Column("market_type", _enum("market_type"), nullable=False),
        sa.Column("country_code", sa.String(2), nullable=False),
        sa.Column("language_code", sa.String(16), nullable=False),
        sa.Column("device", sa.String(32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("superseded_at", sa.DateTime(timezone=True)),
        sa.Column("supersedes_id", sa.UUID(), sa.ForeignKey("gis_core.market_definition.id")),
        sa.Column("created_by", sa.String(255)),
        sa.Column("semantic_notes", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "site_id"], ["gis_core.site.tenant_id", "gis_core.site.id"]
        ),
        sa.UniqueConstraint("tenant_id", "site_id", "slug", "version", name="uq_market_version"),
        schema="gis_core",
    )
    op.create_index(
        "ix_market_definition_scope",
        "market_definition",
        ["tenant_id", "site_id", "slug", "status"],
        schema="gis_core",
    )
    op.create_table(
        "market_definition_member",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "market_definition_id",
            sa.UUID(),
            sa.ForeignKey("gis_core.market_definition.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("member_type", _enum("market_member_type"), nullable=False),
        sa.Column("member_key", sa.Text(), nullable=False),
        sa.Column("member_uuid", sa.UUID()),
        sa.Column("inclusion", _enum("market_inclusion"), nullable=False),
        sa.Column("weight", sa.Numeric(12, 6)),
        sa.Column("rank_order", sa.Integer(), nullable=False),
        sa.Column("effective_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_end", sa.DateTime(timezone=True)),
        sa.Column("provenance_metadata", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("weight IS NULL OR weight >= 0", name="ck_market_member_weight"),
        sa.UniqueConstraint(
            "market_definition_id", "member_type", "member_key", name="uq_market_member_identity"
        ),
        schema="gis_core",
    )
    op.create_index(
        "ix_market_member_definition",
        "market_definition_member",
        ["market_definition_id", "rank_order"],
        schema="gis_core",
    )
    op.create_table(
        "market_metric_definition",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("metric_key", sa.String(150), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("unit", sa.String(50)),
        sa.Column("method_key", sa.String(100), nullable=False),
        sa.Column("method_version", sa.String(50), nullable=False),
        sa.Column("semantic_class", _enum("event_semantic_class"), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint(
            "metric_key", "method_key", "method_version", name="uq_market_metric_method"
        ),
        schema="gis_core",
    )
    op.create_table(
        "market_observation",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column(
            "organization_id", sa.UUID(), sa.ForeignKey("gis_core.organization.id"), nullable=False
        ),
        sa.Column("site_id", sa.UUID(), nullable=False),
        sa.Column(
            "market_definition_id",
            sa.UUID(),
            sa.ForeignKey("gis_core.market_definition.id"),
            nullable=False,
        ),
        sa.Column("market_definition_version", sa.Integer(), nullable=False),
        sa.Column("ingestion_run_id", sa.UUID(), sa.ForeignKey("gis_core.ingestion_run.id")),
        sa.Column(
            "rights_policy_id",
            sa.UUID(),
            sa.ForeignKey("gis_core.data_rights_policy.id"),
            nullable=False,
        ),
        sa.Column("rights_policy_version", sa.String(100), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("country_code", sa.String(2)),
        sa.Column("language_code", sa.String(16)),
        sa.Column("device", sa.String(32)),
        sa.Column("method_key", sa.String(100), nullable=False),
        sa.Column("method_version", sa.String(50), nullable=False),
        sa.Column("semantic_class", _enum("event_semantic_class"), nullable=False),
        sa.Column("coverage_status", _enum("market_coverage_status"), nullable=False),
        sa.Column("configured_query_count", sa.Integer(), nullable=False),
        sa.Column("observed_query_count", sa.Integer(), nullable=False),
        sa.Column("query_coverage_rate", sa.Numeric(8, 6), nullable=False),
        sa.Column("source_coverage", postgresql.JSONB(), nullable=False),
        sa.Column("observation_key", sa.String(64), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("provider_reported_cost", sa.Numeric(20, 8)),
        sa.Column("estimated_cost", sa.Numeric(20, 8), nullable=False),
        sa.Column("cost_currency", sa.String(3), nullable=False),
        sa.Column("provenance_metadata", postgresql.JSONB(), nullable=False),
        sa.Column("effective_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_end", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "site_id"], ["gis_core.site.tenant_id", "gis_core.site.id"]
        ),
        sa.CheckConstraint("configured_query_count >= 0", name="ck_market_configured_queries"),
        sa.CheckConstraint("observed_query_count >= 0", name="ck_market_observed_queries"),
        sa.CheckConstraint("query_coverage_rate BETWEEN 0 AND 1", name="ck_market_query_coverage"),
        sa.CheckConstraint(
            "effective_end IS NULL OR effective_end >= effective_start",
            name="ck_market_observation_window",
        ),
        schema="gis_raw",
    )
    op.create_index(
        "ix_market_observation_definition_date",
        "market_observation",
        ["market_definition_id", "effective_date"],
        schema="gis_raw",
    )
    op.create_index(
        "uq_market_observation_current",
        "market_observation",
        ["observation_key"],
        unique=True,
        schema="gis_raw",
        postgresql_where=sa.text("effective_end IS NULL"),
    )
    op.create_table(
        "market_participant_observation",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "market_observation_id",
            sa.UUID(),
            sa.ForeignKey("gis_raw.market_observation.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("domain", sa.String(253), nullable=False),
        sa.Column("ownership", sa.String(32), nullable=False),
        sa.Column("participant_class", _enum("market_participant_class"), nullable=False),
        sa.Column("query_count", sa.Integer(), nullable=False),
        sa.Column("ranking_page_count", sa.Integer(), nullable=False),
        sa.Column("serp_appearance_count", sa.Integer(), nullable=False),
        sa.Column("top_3_appearances", sa.Integer(), nullable=False),
        sa.Column("top_10_appearances", sa.Integer(), nullable=False),
        sa.Column("top_20_appearances", sa.Integer(), nullable=False),
        sa.Column("visibility_weight", sa.Numeric(24, 10), nullable=False),
        sa.Column("visibility_share", sa.Numeric(12, 10), nullable=False),
        sa.Column("volume_weighted_visibility", sa.Numeric(24, 10)),
        sa.Column("volume_weighted_visibility_share", sa.Numeric(12, 10)),
        sa.Column("query_overlap_rate", sa.Numeric(8, 6), nullable=False),
        sa.Column("first_observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("classification_method", sa.String(100), nullable=False),
        sa.Column("classification_version", sa.String(50), nullable=False),
        sa.Column("semantic_class", _enum("event_semantic_class"), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint("visibility_share BETWEEN 0 AND 1", name="ck_market_visibility_share"),
        sa.CheckConstraint(
            "volume_weighted_visibility_share IS NULL OR volume_weighted_visibility_share BETWEEN 0 AND 1",
            name="ck_market_volume_visibility_share",
        ),
        sa.UniqueConstraint("market_observation_id", "domain", name="uq_market_participant_domain"),
        schema="gis_raw",
    )
    op.create_index(
        "ix_market_participant_domain",
        "market_participant_observation",
        ["domain"],
        schema="gis_raw",
    )
    op.create_table(
        "market_segment_observation",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "market_observation_id",
            sa.UUID(),
            sa.ForeignKey("gis_raw.market_observation.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("segment_type", sa.String(50), nullable=False),
        sa.Column("segment_key", sa.String(255), nullable=False),
        sa.Column("segment_label", sa.String(255), nullable=False),
        sa.Column("query_count", sa.Integer(), nullable=False),
        sa.Column("participant_count", sa.Integer(), nullable=False),
        sa.Column("provider_reported_search_volume", sa.Numeric(24, 6)),
        sa.Column("observed_visibility_hhi", sa.Numeric(12, 10)),
        sa.Column("method_key", sa.String(100), nullable=False),
        sa.Column("method_version", sa.String(50), nullable=False),
        sa.Column("semantic_class", _enum("event_semantic_class"), nullable=False),
        sa.UniqueConstraint(
            "market_observation_id", "segment_type", "segment_key", name="uq_market_segment"
        ),
        schema="gis_raw",
    )
    op.create_table(
        "market_metric_observation",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "market_observation_id",
            sa.UUID(),
            sa.ForeignKey("gis_raw.market_observation.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "metric_definition_id", sa.UUID(), sa.ForeignKey("gis_core.market_metric_definition.id")
        ),
        sa.Column("metric_key", sa.String(150), nullable=False),
        sa.Column("metric_value", sa.Numeric(24, 10)),
        sa.Column("unit", sa.String(50)),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("method_key", sa.String(100), nullable=False),
        sa.Column("method_version", sa.String(50), nullable=False),
        sa.Column("semantic_class", _enum("event_semantic_class"), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=False),
        sa.UniqueConstraint(
            "market_observation_id",
            "metric_key",
            "method_key",
            "provider",
            name="uq_market_metric_observation",
        ),
        schema="gis_raw",
    )
    op.create_index(
        "ix_market_metric_key",
        "market_metric_observation",
        ["metric_key", "method_key"],
        schema="gis_raw",
    )


def downgrade() -> None:
    # dbt relations are reproducible and may depend on both tables and enum types.
    # Remove only this epic's analytical outputs before transactional rollback.
    for relation in (
        "mart_market_change",
        "mart_market_competitor_daily",
        "mart_market_concentration_daily",
        "mart_market_coverage",
        "mart_market_daily",
        "mart_market_demand_distribution",
        "mart_market_overlap",
        "mart_market_participant_daily",
        "mart_market_segment_daily",
        "mart_market_serp_structure",
        "mart_market_visibility_daily",
    ):
        op.execute(f"DROP TABLE IF EXISTS gis_analytics.{relation} CASCADE")
    for view in (
        "stg_market_metric_observations",
        "stg_market_segment_observations",
        "stg_market_participant_observations",
        "stg_market_observations",
        "stg_market_definitions",
    ):
        op.execute(f"DROP VIEW IF EXISTS gis_staging.{view} CASCADE")
    op.drop_table("market_metric_observation", schema="gis_raw")
    op.drop_table("market_segment_observation", schema="gis_raw")
    op.drop_table("market_participant_observation", schema="gis_raw")
    op.drop_table("market_observation", schema="gis_raw")
    op.drop_table("market_metric_definition", schema="gis_core")
    op.drop_table("market_definition_member", schema="gis_core")
    op.drop_table("market_definition", schema="gis_core")
    for name in (
        "market_participant_class",
        "market_coverage_status",
        "market_inclusion",
        "market_member_type",
        "market_type",
        "market_status",
    ):
        op.execute(f"DROP TYPE gis_core.{name}")
