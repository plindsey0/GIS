"""add competitive event synthesis

Revision ID: 20260830_0013
Revises: 20260830_0012
Create Date: 2026-08-30
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260830_0013"
down_revision: Union[str, None] = "20260830_0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _enum(name: str, values: list[str]) -> postgresql.ENUM:
    return postgresql.ENUM(*values, name=name, schema="gis_core", create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    definitions = {
        "competitive_subject_type": [
            "DOMAIN",
            "PAGE",
            "QUERY",
            "TECHNOLOGY",
            "SERP_FEATURE",
            "CONTENT_COMPONENT",
            "SITE",
            "COMPETITOR",
        ],
        "competitive_event_domain": [
            "SERP",
            "SEARCH_VISIBILITY",
            "CONTENT",
            "TECHNOLOGY",
            "EXPERIENCE",
            "DOMAIN",
            "CROSS_SOURCE",
        ],
        "competitive_event_type": [
            "SERP_RANK_ENTERED",
            "SERP_RANK_EXITED",
            "SERP_RANK_INCREASED",
            "SERP_RANK_DECREASED",
            "SERP_FEATURE_APPEARED",
            "SERP_FEATURE_DISAPPEARED",
            "KEYWORD_GAINED",
            "KEYWORD_LOST",
            "SEARCH_VISIBILITY_INCREASED",
            "SEARCH_VISIBILITY_DECREASED",
            "PAGE_FIRST_OBSERVED",
            "PAGE_CONTENT_CHANGED",
            "TITLE_CHANGED",
            "META_DESCRIPTION_CHANGED",
            "HEADING_STRUCTURE_CHANGED",
            "CONTENT_COMPONENT_APPEARED",
            "SCHEMA_TYPE_APPEARED",
            "WORD_COUNT_INCREASED",
            "WORD_COUNT_DECREASED",
            "TECHNOLOGY_FIRST_DETECTED",
            "TECHNOLOGY_VERSION_CHANGED",
            "TECHNOLOGY_ADDED",
            "EXPERIENCE_METRIC_IMPROVED",
            "EXPERIENCE_METRIC_DEGRADED",
            "COMPETITOR_PAGE_EMERGENCE",
        ],
        "event_semantic_class": ["MEASURED", "PROVIDER_REPORTED", "GIS_DERIVED", "HEURISTIC"],
        "competitive_event_status": ["ACTIVE", "SUPERSEDED", "RETRACTED"],
        "competitive_evidence_role": ["BEFORE", "AFTER", "PRIMARY", "SUPPORTING"],
        "competitive_event_relationship_type": [
            "SUPPORTS",
            "PRECEDES",
            "SUPERSEDES",
            "SAME_CHANGE",
            "CONSTITUENT_OF",
        ],
    }
    for name, values in definitions.items():
        postgresql.ENUM(*values, name=name, schema="gis_core").create(bind, checkfirst=True)

    op.create_table(
        "competitive_event_policy",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("site_id", sa.UUID(), nullable=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("policy_version", sa.String(32), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("thresholds_json", postgresql.JSONB(), nullable=False),
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
        sa.ForeignKeyConstraint(["site_id"], ["gis_core.site.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "site_id",
            "name",
            "policy_version",
            name="uq_competitive_event_policy_version",
        ),
        schema="gis_core",
    )
    op.create_index(
        "ix_competitive_event_policy_scope",
        "competitive_event_policy",
        ["tenant_id", "site_id", "active"],
        schema="gis_core",
    )

    op.create_table(
        "competitive_event",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("public_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID()),
        sa.Column("site_id", sa.UUID(), nullable=False),
        sa.Column("subject_type", _enum("competitive_subject_type", []), nullable=False),
        sa.Column("subject_id", sa.UUID()),
        sa.Column("subject_key", sa.Text(), nullable=False),
        sa.Column("subject_domain", sa.String(253)),
        sa.Column("subject_url", sa.Text()),
        sa.Column("event_domain", _enum("competitive_event_domain", []), nullable=False),
        sa.Column("event_type", _enum("competitive_event_type", []), nullable=False),
        sa.Column("event_subtype", sa.String(100)),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("first_observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_start_at", sa.DateTime(timezone=True)),
        sa.Column("effective_end_at", sa.DateTime(timezone=True)),
        sa.Column("semantic_class", _enum("event_semantic_class", []), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False),
        sa.Column("magnitude", sa.Numeric(20, 6)),
        sa.Column("magnitude_unit", sa.String(32)),
        sa.Column("status", _enum("competitive_event_status", []), nullable=False),
        sa.Column("synthesis_method", sa.String(100), nullable=False),
        sa.Column("synthesis_method_version", sa.String(32), nullable=False),
        sa.Column("policy_id", sa.UUID(), nullable=False),
        sa.Column("policy_version", sa.String(32), nullable=False),
        sa.Column("rights_policy_id", sa.UUID()),
        sa.Column("rights_policy_version", sa.String(100)),
        sa.Column("effective_rights_status", _enum("rights_status", []), nullable=False),
        sa.Column("identity_hash", sa.String(64), nullable=False),
        sa.Column("correction_reason", sa.Text()),
        sa.Column("replaced_by_event_id", sa.UUID()),
        sa.Column("provider_cost", sa.Numeric(20, 8), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_competitive_event_confidence"),
        sa.CheckConstraint("provider_cost = 0", name="ck_competitive_event_zero_provider_cost"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "site_id"], ["gis_core.site.tenant_id", "gis_core.site.id"]
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["gis_core.organization.id"]),
        sa.ForeignKeyConstraint(["policy_id"], ["gis_core.competitive_event_policy.id"]),
        sa.ForeignKeyConstraint(["rights_policy_id"], ["gis_core.data_rights_policy.id"]),
        sa.ForeignKeyConstraint(["replaced_by_event_id"], ["gis_core.competitive_event.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("public_id"),
        sa.UniqueConstraint(
            "tenant_id", "site_id", "identity_hash", name="uq_competitive_event_identity"
        ),
        sa.UniqueConstraint("tenant_id", "site_id", "id", name="uq_competitive_event_scope_id"),
        schema="gis_core",
    )
    op.create_index(
        "ix_competitive_event_timeline",
        "competitive_event",
        ["tenant_id", "site_id", "event_time"],
        schema="gis_core",
    )
    op.create_index(
        "ix_competitive_event_type",
        "competitive_event",
        ["tenant_id", "site_id", "event_domain", "event_type"],
        schema="gis_core",
    )
    op.create_index(
        "ix_competitive_event_subject",
        "competitive_event",
        ["tenant_id", "site_id", "subject_key"],
        schema="gis_core",
    )

    op.create_table(
        "competitive_event_evidence",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("site_id", sa.UUID(), nullable=False),
        sa.Column("competitive_event_id", sa.UUID(), nullable=False),
        sa.Column("source_asset", sa.String(150), nullable=False),
        sa.Column("source_record_id", sa.String(255), nullable=False),
        sa.Column("observation_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("evidence_role", _enum("competitive_evidence_role", []), nullable=False),
        sa.Column("semantic_class", _enum("event_semantic_class", []), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False),
        sa.Column("data_source_connection_id", sa.UUID()),
        sa.Column("ingestion_run_id", sa.UUID()),
        sa.Column("rights_policy_id", sa.UUID()),
        sa.Column("rights_policy_version", sa.String(100)),
        sa.Column("metadata", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "site_id", "competitive_event_id"],
            [
                "gis_core.competitive_event.tenant_id",
                "gis_core.competitive_event.site_id",
                "gis_core.competitive_event.id",
            ],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["data_source_connection_id"], ["gis_core.data_source_connection.id"]
        ),
        sa.ForeignKeyConstraint(["ingestion_run_id"], ["gis_core.ingestion_run.id"]),
        sa.ForeignKeyConstraint(["rights_policy_id"], ["gis_core.data_rights_policy.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "competitive_event_id",
            "source_asset",
            "source_record_id",
            "evidence_role",
            name="uq_competitive_event_evidence",
        ),
        schema="gis_core",
    )
    op.create_index(
        "ix_competitive_event_evidence_source",
        "competitive_event_evidence",
        ["source_asset", "source_record_id"],
        schema="gis_core",
    )

    op.create_table(
        "competitive_event_relationship",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("site_id", sa.UUID(), nullable=False),
        sa.Column("from_event_id", sa.UUID(), nullable=False),
        sa.Column("to_event_id", sa.UUID(), nullable=False),
        sa.Column(
            "relationship_type", _enum("competitive_event_relationship_type", []), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "from_event_id <> to_event_id", name="ck_competitive_event_relationship_not_self"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "site_id", "from_event_id"],
            [
                "gis_core.competitive_event.tenant_id",
                "gis_core.competitive_event.site_id",
                "gis_core.competitive_event.id",
            ],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "site_id", "to_event_id"],
            [
                "gis_core.competitive_event.tenant_id",
                "gis_core.competitive_event.site_id",
                "gis_core.competitive_event.id",
            ],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "from_event_id",
            "to_event_id",
            "relationship_type",
            name="uq_competitive_event_relationship",
        ),
        schema="gis_core",
    )


def downgrade() -> None:
    op.drop_table("competitive_event_relationship", schema="gis_core")
    op.drop_index(
        "ix_competitive_event_evidence_source",
        table_name="competitive_event_evidence",
        schema="gis_core",
    )
    op.drop_table("competitive_event_evidence", schema="gis_core")
    for index in (
        "ix_competitive_event_subject",
        "ix_competitive_event_type",
        "ix_competitive_event_timeline",
    ):
        op.drop_index(index, table_name="competitive_event", schema="gis_core")
    op.drop_table("competitive_event", schema="gis_core")
    op.drop_index(
        "ix_competitive_event_policy_scope",
        table_name="competitive_event_policy",
        schema="gis_core",
    )
    op.drop_table("competitive_event_policy", schema="gis_core")
    bind = op.get_bind()
    for name in (
        "competitive_event_relationship_type",
        "competitive_evidence_role",
        "competitive_event_status",
        "event_semantic_class",
        "competitive_event_type",
        "competitive_event_domain",
        "competitive_subject_type",
    ):
        postgresql.ENUM(name=name, schema="gis_core").drop(bind, checkfirst=True)
