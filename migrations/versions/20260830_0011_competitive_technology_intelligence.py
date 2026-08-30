"""add competitive technology intelligence

Revision ID: 20260830_0011
Revises: 20260830_0010
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260830_0011"
down_revision: Union[str, None] = "20260830_0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "technology",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("vendor", sa.String(255)),
        sa.Column("product_family", sa.String(255)),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_technology_slug"),
        schema="gis_core",
    )
    op.create_index("ix_technology_category", "technology", ["category"], schema="gis_core")
    op.create_table(
        "technology_alias",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("technology_id", sa.UUID(), nullable=False),
        sa.Column("source_key", sa.String(100), nullable=False),
        sa.Column("alias", sa.String(255), nullable=False),
        sa.Column("normalized_alias", sa.String(255), nullable=False),
        sa.Column("provider_identifier", sa.String(255)),
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
        sa.ForeignKeyConstraint(["technology_id"], ["gis_core.technology.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_key", "normalized_alias", name="uq_technology_alias_source"),
        schema="gis_core",
    )
    op.create_index(
        "ix_technology_alias_normalized",
        "technology_alias",
        ["normalized_alias"],
        schema="gis_core",
    )
    op.create_table(
        "technology_observation",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("site_id", sa.UUID(), nullable=False),
        sa.Column("data_source_connection_id", sa.UUID(), nullable=False),
        sa.Column("ingestion_run_id", sa.UUID(), nullable=False),
        sa.Column("rights_policy_id", sa.UUID(), nullable=False),
        sa.Column("rights_policy_version", sa.String(100), nullable=False),
        sa.Column("domain", sa.String(253), nullable=False),
        sa.Column("requested_url", sa.Text(), nullable=False),
        sa.Column("normalized_url", sa.Text(), nullable=False),
        sa.Column("ownership_class", sa.String(32), nullable=False),
        sa.Column("observation_scope", sa.String(32), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True)),
        sa.Column("collection_status", sa.String(50), nullable=False),
        sa.Column("http_status", sa.Integer()),
        sa.Column("render_mode", sa.String(32), nullable=False),
        sa.Column("content_hash", sa.String(64)),
        sa.Column("observation_key", sa.String(64), nullable=False),
        sa.Column("provider_request_id", sa.String(255)),
        sa.Column("request_count", sa.Integer(), nullable=False),
        sa.Column("provider_reported_cost", sa.Numeric(20, 8)),
        sa.Column("estimated_cost", sa.Numeric(20, 8)),
        sa.Column("cost_currency", sa.String(3), nullable=False),
        sa.Column("signature_version", sa.String(100)),
        sa.Column("collection_metadata", postgresql.JSONB(), nullable=False),
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
            name="ck_technology_observation_effective_window",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["gis_core.organization.id"]),
        sa.ForeignKeyConstraint(
            ["data_source_connection_id"], ["gis_core.data_source_connection.id"]
        ),
        sa.ForeignKeyConstraint(["rights_policy_id"], ["gis_core.data_rights_policy.id"]),
        sa.ForeignKeyConstraint(
            ["tenant_id", "site_id"],
            ["gis_core.site.tenant_id", "gis_core.site.id"],
            name="fk_technology_observation_site_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "site_id", "ingestion_run_id"],
            [
                "gis_core.ingestion_run.tenant_id",
                "gis_core.ingestion_run.site_id",
                "gis_core.ingestion_run.id",
            ],
            name="fk_technology_observation_run_scope",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="gis_raw",
    )
    op.create_index(
        "ix_technology_observation_site_date",
        "technology_observation",
        ["tenant_id", "site_id", "observed_at"],
        schema="gis_raw",
    )
    op.create_index(
        "ix_technology_observation_domain_date",
        "technology_observation",
        ["domain", "observed_at"],
        schema="gis_raw",
    )
    op.create_index(
        "uq_technology_observation_current",
        "technology_observation",
        ["observation_key"],
        unique=True,
        schema="gis_raw",
        postgresql_where=sa.text("effective_end IS NULL"),
    )
    op.create_table(
        "technology_detection",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("observation_id", sa.UUID(), nullable=False),
        sa.Column("technology_id", sa.UUID(), nullable=False),
        sa.Column("provider_technology_name", sa.String(255)),
        sa.Column("provider_category", sa.String(255)),
        sa.Column("detected_version", sa.String(255)),
        sa.Column("provider_first_seen_at", sa.DateTime(timezone=True)),
        sa.Column("provider_last_seen_at", sa.DateTime(timezone=True)),
        sa.Column("presence_status", sa.String(32), nullable=False),
        sa.Column("detection_scope", sa.String(32), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False),
        sa.Column("semantic_class", sa.String(32), nullable=False),
        sa.Column("detection_method", sa.String(100), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["observation_id"], ["gis_raw.technology_observation.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["technology_id"], ["gis_core.technology.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "observation_id",
            "technology_id",
            "detection_scope",
            name="uq_technology_detection_observation",
        ),
        schema="gis_raw",
    )
    op.create_index(
        "ix_technology_detection_technology",
        "technology_detection",
        ["technology_id"],
        schema="gis_raw",
    )
    op.create_index(
        "ix_technology_detection_semantics",
        "technology_detection",
        ["semantic_class"],
        schema="gis_raw",
    )
    op.create_table(
        "technology_evidence",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("detection_id", sa.UUID(), nullable=False),
        sa.Column("signature_key", sa.String(255), nullable=False),
        sa.Column("signature_version", sa.String(100), nullable=False),
        sa.Column("evidence_type", sa.String(50), nullable=False),
        sa.Column("match_target", sa.String(50), nullable=False),
        sa.Column("evidence_value", sa.Text()),
        sa.Column("evidence_hash", sa.String(64), nullable=False),
        sa.Column("semantic_class", sa.String(32), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["detection_id"], ["gis_raw.technology_detection.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "detection_id",
            "signature_key",
            "evidence_hash",
            name="uq_technology_evidence_signature",
        ),
        schema="gis_raw",
    )
    op.create_index(
        "ix_technology_evidence_signature",
        "technology_evidence",
        ["signature_key"],
        schema="gis_raw",
    )


def downgrade() -> None:
    op.drop_table("technology_evidence", schema="gis_raw")
    op.drop_table("technology_detection", schema="gis_raw")
    op.drop_table("technology_observation", schema="gis_raw")
    op.drop_table("technology_alias", schema="gis_core")
    op.drop_table("technology", schema="gis_core")
