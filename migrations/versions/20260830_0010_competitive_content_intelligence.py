"""add competitive content intelligence

Revision ID: 20260830_0010
Revises: 20260830_0009
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260830_0010"
down_revision: Union[str, None] = "20260830_0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "competitive_content_observation",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("site_id", sa.UUID(), nullable=False),
        sa.Column("data_source_connection_id", sa.UUID(), nullable=False),
        sa.Column("ingestion_run_id", sa.UUID(), nullable=False),
        sa.Column("rights_policy_id", sa.UUID(), nullable=False),
        sa.Column("rights_policy_version", sa.String(100), nullable=False),
        sa.Column("requested_url", sa.Text(), nullable=False),
        sa.Column("normalized_url", sa.Text(), nullable=False),
        sa.Column("resolved_url", sa.Text()),
        sa.Column("canonical_url", sa.Text()),
        sa.Column("domain", sa.String(253), nullable=False),
        sa.Column("page_path", sa.Text(), nullable=False),
        sa.Column("ownership_class", sa.String(32), nullable=False),
        sa.Column("tracked_query_id", sa.UUID()),
        sa.Column("serp_result_id", sa.UUID()),
        sa.Column("external_search_observation_id", sa.UUID()),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True)),
        sa.Column("retrieval_status", sa.String(50), nullable=False),
        sa.Column("http_status", sa.Integer()),
        sa.Column("render_mode", sa.String(32), nullable=False),
        sa.Column("content_type", sa.String(255)),
        sa.Column("content_language", sa.String(32)),
        sa.Column("response_bytes", sa.Integer()),
        sa.Column("content_hash", sa.String(64)),
        sa.Column("observation_key", sa.String(64), nullable=False),
        sa.Column("provider_request_id", sa.String(255)),
        sa.Column("provider_reported_cost", sa.Numeric(20, 8)),
        sa.Column("estimated_cost", sa.Numeric(20, 8)),
        sa.Column("cost_currency", sa.String(3), nullable=False),
        sa.Column("raw_payload_reference", sa.Text()),
        sa.Column("raw_retained", sa.Boolean(), nullable=False),
        sa.Column("truncated", sa.Boolean(), nullable=False),
        sa.Column("retrieval_metadata", postgresql.JSONB(), nullable=False),
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
            name="ck_content_observation_effective_window",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["gis_core.organization.id"]),
        sa.ForeignKeyConstraint(
            ["data_source_connection_id"], ["gis_core.data_source_connection.id"]
        ),
        sa.ForeignKeyConstraint(["rights_policy_id"], ["gis_core.data_rights_policy.id"]),
        sa.ForeignKeyConstraint(["tracked_query_id"], ["gis_core.tracked_query.id"]),
        sa.ForeignKeyConstraint(["serp_result_id"], ["gis_raw.serp_result.id"]),
        sa.ForeignKeyConstraint(
            ["external_search_observation_id"], ["gis_raw.external_search_observation.id"]
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "site_id"],
            ["gis_core.site.tenant_id", "gis_core.site.id"],
            name="fk_content_observation_site_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "site_id", "ingestion_run_id"],
            [
                "gis_core.ingestion_run.tenant_id",
                "gis_core.ingestion_run.site_id",
                "gis_core.ingestion_run.id",
            ],
            name="fk_content_observation_run_scope",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="gis_raw",
    )
    op.create_index(
        "ix_content_observation_site_date",
        "competitive_content_observation",
        ["tenant_id", "site_id", "observed_at"],
        schema="gis_raw",
    )
    op.create_index(
        "ix_content_observation_url",
        "competitive_content_observation",
        ["normalized_url"],
        schema="gis_raw",
    )
    op.create_index(
        "ix_content_observation_domain",
        "competitive_content_observation",
        ["domain"],
        schema="gis_raw",
    )
    op.create_index(
        "ix_content_observation_hash",
        "competitive_content_observation",
        ["content_hash"],
        schema="gis_raw",
    )
    op.create_index(
        "uq_content_observation_current",
        "competitive_content_observation",
        ["observation_key"],
        unique=True,
        schema="gis_raw",
        postgresql_where=sa.text("effective_end IS NULL"),
    )
    op.create_table(
        "competitive_content_document",
        sa.Column("observation_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.Text()),
        sa.Column("meta_description", sa.Text()),
        sa.Column("robots_directives", postgresql.JSONB(), nullable=False),
        sa.Column("normalized_word_count", sa.Integer(), nullable=False),
        sa.Column("paragraph_count", sa.Integer(), nullable=False),
        sa.Column("h1_count", sa.Integer(), nullable=False),
        sa.Column("h2_count", sa.Integer(), nullable=False),
        sa.Column("h3_count", sa.Integer(), nullable=False),
        sa.Column("ordered_list_count", sa.Integer(), nullable=False),
        sa.Column("unordered_list_count", sa.Integer(), nullable=False),
        sa.Column("table_count", sa.Integer(), nullable=False),
        sa.Column("image_count", sa.Integer(), nullable=False),
        sa.Column("video_count", sa.Integer(), nullable=False),
        sa.Column("form_count", sa.Integer(), nullable=False),
        sa.Column("iframe_count", sa.Integer(), nullable=False),
        sa.Column("internal_link_count", sa.Integer(), nullable=False),
        sa.Column("external_link_count", sa.Integer(), nullable=False),
        sa.Column("publication_dates", postgresql.JSONB(), nullable=False),
        sa.Column("modified_dates", postgresql.JSONB(), nullable=False),
        sa.Column("metric_semantics", postgresql.JSONB(), nullable=False),
        sa.ForeignKeyConstraint(
            ["observation_id"], ["gis_raw.competitive_content_observation.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("observation_id"),
        schema="gis_raw",
    )
    op.create_table(
        "competitive_content_heading",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("observation_id", sa.UUID(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("heading_text", sa.Text(), nullable=False),
        sa.Column("normalized_text", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["observation_id"], ["gis_raw.competitive_content_observation.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("observation_id", "ordinal"),
        schema="gis_raw",
    )
    op.create_table(
        "competitive_content_schema_type",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("observation_id", sa.UUID(), nullable=False),
        sa.Column("schema_type", sa.String(255), nullable=False),
        sa.Column("occurrence_count", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["observation_id"], ["gis_raw.competitive_content_observation.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("observation_id", "schema_type"),
        schema="gis_raw",
    )
    op.create_table(
        "competitive_content_link",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("observation_id", sa.UUID(), nullable=False),
        sa.Column("target_url", sa.Text(), nullable=False),
        sa.Column("target_domain", sa.String(253), nullable=False),
        sa.Column("link_class", sa.String(32), nullable=False),
        sa.Column("anchor_text", sa.Text()),
        sa.Column("rel_values", postgresql.JSONB(), nullable=False),
        sa.ForeignKeyConstraint(
            ["observation_id"], ["gis_raw.competitive_content_observation.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="gis_raw",
    )
    op.create_index(
        "ix_content_link_domain", "competitive_content_link", ["target_domain"], schema="gis_raw"
    )
    op.create_table(
        "competitive_content_component",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("observation_id", sa.UUID(), nullable=False),
        sa.Column("component_type", sa.String(100), nullable=False),
        sa.Column("occurrence_count", sa.Integer(), nullable=False),
        sa.Column("detection_method", sa.String(100), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False),
        sa.Column("metric_semantics", sa.String(32), nullable=False),
        sa.Column("evidence", postgresql.JSONB(), nullable=False),
        sa.ForeignKeyConstraint(
            ["observation_id"], ["gis_raw.competitive_content_observation.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("observation_id", "component_type"),
        schema="gis_raw",
    )
    op.create_table(
        "competitive_content_term",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("observation_id", sa.UUID(), nullable=False),
        sa.Column("term", sa.Text(), nullable=False),
        sa.Column("normalized_term", sa.Text(), nullable=False),
        sa.Column("occurrence_count", sa.Integer(), nullable=False),
        sa.Column("extraction_method", sa.String(100), nullable=False),
        sa.Column("metric_semantics", sa.String(32), nullable=False),
        sa.ForeignKeyConstraint(
            ["observation_id"], ["gis_raw.competitive_content_observation.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("observation_id", "normalized_term"),
        schema="gis_raw",
    )
    op.create_index(
        "ix_content_term_normalized",
        "competitive_content_term",
        ["normalized_term"],
        schema="gis_raw",
    )
    op.create_table(
        "competitive_content_cohort",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("site_id", sa.UUID(), nullable=False),
        sa.Column("tracked_query_id", sa.UUID()),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("definition", postgresql.JSONB(), nullable=False),
        sa.Column("frozen_at", sa.DateTime(timezone=True), nullable=False),
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
        sa.ForeignKeyConstraint(["tenant_id"], ["gis_core.tenant.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["gis_core.organization.id"]),
        sa.ForeignKeyConstraint(["site_id"], ["gis_core.site.id"]),
        sa.ForeignKeyConstraint(["tracked_query_id"], ["gis_core.tracked_query.id"]),
        sa.PrimaryKeyConstraint("id"),
        schema="gis_core",
    )
    op.create_index(
        "ix_content_cohort_site_created",
        "competitive_content_cohort",
        ["tenant_id", "site_id", "created_at"],
        schema="gis_core",
    )
    op.create_table(
        "competitive_content_cohort_member",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("cohort_id", sa.UUID(), nullable=False),
        sa.Column("observation_id", sa.UUID(), nullable=False),
        sa.Column("rank_position", sa.Integer()),
        sa.Column("membership_source", sa.String(50), nullable=False),
        sa.Column(
            "added_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["cohort_id"], ["gis_core.competitive_content_cohort.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["observation_id"], ["gis_raw.competitive_content_observation.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cohort_id", "observation_id"),
        schema="gis_core",
    )


def downgrade() -> None:
    op.drop_table("competitive_content_cohort_member", schema="gis_core")
    op.drop_table("competitive_content_cohort", schema="gis_core")
    op.drop_table("competitive_content_term", schema="gis_raw")
    op.drop_table("competitive_content_component", schema="gis_raw")
    op.drop_table("competitive_content_link", schema="gis_raw")
    op.drop_table("competitive_content_schema_type", schema="gis_raw")
    op.drop_table("competitive_content_heading", schema="gis_raw")
    op.drop_table("competitive_content_document", schema="gis_raw")
    op.drop_table("competitive_content_observation", schema="gis_raw")
