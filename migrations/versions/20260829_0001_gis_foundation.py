"""Create the GIS data platform foundation.

Revision ID: 20260829_0001
Revises: None
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260829_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "gis_core"


def _enum(name: str, *values: str) -> postgresql.ENUM:
    return postgresql.ENUM(*values, name=name, schema=SCHEMA, create_type=False)


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def upgrade() -> None:
    op.execute(sa.schema.CreateSchema(SCHEMA))
    enums = {
        "tenant_status": ("ACTIVE", "SUSPENDED", "ARCHIVED"),
        "site_status": ("ACTIVE", "INACTIVE", "ARCHIVED"),
        "domain_type": ("PRIMARY", "ALIAS", "REDIRECT", "COMPETITOR", "RELATED", "OTHER"),
        "source_type": (
            "FIRST_PARTY",
            "PUBLIC",
            "COMMERCIAL",
            "CUSTOMER_CONNECTED",
            "CRAWLED",
            "MANUAL",
        ),
        "rights_decision": ("ALLOWED", "PROHIBITED", "UNKNOWN"),
        "connection_type": ("NATIVE", "BYOD", "LICENSED_ENRICHMENT", "CUSTOMER_SIDE"),
        "connection_status": ("PENDING", "ACTIVE", "DISABLED", "ERROR"),
        "ingestion_status": ("PENDING", "RUNNING", "SUCCEEDED", "PARTIAL", "FAILED", "CANCELLED"),
        "quality_flag": ("VALID", "SUSPECT", "INVALID", "UNKNOWN"),
    }
    for name, values in enums.items():
        postgresql.ENUM(*values, name=name, schema=SCHEMA).create(op.get_bind())

    op.create_table(
        "tenant",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("status", _enum("tenant_status", *enums["tenant_status"]), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("slug", name="uq_tenant_slug"),
        schema=SCHEMA,
    )
    op.create_table(
        "organization",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{SCHEMA}.tenant.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("tenant_id", "slug", name="uq_organization_tenant_slug"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_organization_tenant_id"),
        schema=SCHEMA,
    )
    op.create_table(
        "site",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{SCHEMA}.tenant.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("canonical_url", sa.String(2048), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("status", _enum("site_status", *enums["site_status"]), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["tenant_id", "organization_id"],
            [f"{SCHEMA}.organization.tenant_id", f"{SCHEMA}.organization.id"],
            ondelete="CASCADE",
            name="fk_site_organization_tenant",
        ),
        sa.UniqueConstraint("tenant_id", "slug", name="uq_site_tenant_slug"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_site_tenant_id"),
        schema=SCHEMA,
    )
    op.create_table(
        "domain",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{SCHEMA}.tenant.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("hostname", sa.String(253), nullable=False),
        sa.Column("domain_type", _enum("domain_type", *enums["domain_type"]), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True)),
        sa.Column("last_seen_at", sa.DateTime(timezone=True)),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["tenant_id", "site_id"],
            [f"{SCHEMA}.site.tenant_id", f"{SCHEMA}.site.id"],
            ondelete="CASCADE",
            name="fk_domain_site_tenant",
        ),
        sa.UniqueConstraint("tenant_id", "site_id", "hostname", name="uq_domain_site_hostname"),
        schema=SCHEMA,
    )
    op.create_index("ix_domain_hostname", "domain", ["hostname"], schema=SCHEMA)
    op.create_index(
        "uq_domain_primary_per_site",
        "domain",
        ["site_id"],
        unique=True,
        schema=SCHEMA,
        postgresql_where=sa.text("is_primary"),
    )

    rights_columns = [
        "commercial_use_allowed",
        "third_party_processing_allowed",
        "deterministic_analysis_allowed",
        "ai_inference_allowed",
        "model_training_allowed",
        "raw_storage_allowed",
        "derived_storage_allowed",
        "raw_display_allowed",
        "derived_display_allowed",
        "aggregation_allowed",
        "cross_tenant_learning_allowed",
        "attribution_required",
    ]
    op.create_table(
        "data_rights_policy",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{SCHEMA}.tenant.id", ondelete="CASCADE"),
        ),
        sa.Column("name", sa.String(255), nullable=False),
        *[
            sa.Column(column, _enum("rights_decision", *enums["rights_decision"]), nullable=False)
            for column in rights_columns
        ],
        sa.Column("retention_days", sa.Integer()),
        sa.Column("attribution_text", sa.Text()),
        sa.Column("license_type", sa.String(100)),
        sa.Column("license_version", sa.String(100)),
        sa.Column("license_url", sa.String(2048)),
        sa.Column("license_review_date", sa.Date()),
        sa.Column("policy_notes", sa.Text()),
        *_timestamps(),
        sa.CheckConstraint(
            "retention_days IS NULL OR retention_days >= 0", name="ck_policy_retention"
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_rights_policy_tenant_id"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_data_rights_policy_tenant_id", "data_rights_policy", ["tenant_id"], schema=SCHEMA
    )
    op.create_table(
        "data_source",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("provider", sa.String(255), nullable=False),
        sa.Column("source_type", _enum("source_type", *enums["source_type"]), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column(
            "default_rights_policy_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{SCHEMA}.data_rights_policy.id", ondelete="SET NULL"),
        ),
        *_timestamps(),
        sa.UniqueConstraint("key", name="uq_data_source_key"),
        schema=SCHEMA,
    )
    op.create_table(
        "data_source_connection",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{SCHEMA}.tenant.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("site_id", postgresql.UUID(as_uuid=True)),
        sa.Column(
            "data_source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{SCHEMA}.data_source.id"),
            nullable=False,
        ),
        sa.Column(
            "rights_policy_id",
            postgresql.UUID(as_uuid=True),
        ),
        sa.Column(
            "connection_type", _enum("connection_type", *enums["connection_type"]), nullable=False
        ),
        sa.Column(
            "status", _enum("connection_status", *enums["connection_status"]), nullable=False
        ),
        sa.Column("external_account_id", sa.String(255)),
        sa.Column("configuration_json", postgresql.JSONB(), nullable=False),
        sa.Column("credential_reference", sa.String(1024)),
        sa.Column("last_successful_sync_at", sa.DateTime(timezone=True)),
        sa.Column("last_attempted_sync_at", sa.DateTime(timezone=True)),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["tenant_id", "site_id"],
            [f"{SCHEMA}.site.tenant_id", f"{SCHEMA}.site.id"],
            name="fk_connection_site_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "rights_policy_id"],
            [
                f"{SCHEMA}.data_rights_policy.tenant_id",
                f"{SCHEMA}.data_rights_policy.id",
            ],
            name="fk_connection_rights_policy_tenant",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_connection_tenant_id"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_connection_tenant_site",
        "data_source_connection",
        ["tenant_id", "site_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_data_source_connection_tenant_id",
        "data_source_connection",
        ["tenant_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_data_source_connection_data_source_id",
        "data_source_connection",
        ["data_source_id"],
        schema=SCHEMA,
    )
    op.create_table(
        "ingestion_run",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{SCHEMA}.tenant.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("site_id", postgresql.UUID(as_uuid=True)),
        sa.Column("data_source_connection_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("status", _enum("ingestion_status", *enums["ingestion_status"]), nullable=False),
        sa.Column("records_received", sa.Integer(), nullable=False),
        sa.Column("records_inserted", sa.Integer(), nullable=False),
        sa.Column("records_rejected", sa.Integer(), nullable=False),
        sa.Column("error_count", sa.Integer(), nullable=False),
        sa.Column("error_summary", sa.Text()),
        sa.Column("source_cursor", sa.Text()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "site_id"],
            [f"{SCHEMA}.site.tenant_id", f"{SCHEMA}.site.id"],
            name="fk_ingestion_site_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "data_source_connection_id"],
            [f"{SCHEMA}.data_source_connection.tenant_id", f"{SCHEMA}.data_source_connection.id"],
            ondelete="CASCADE",
            name="fk_ingestion_connection_tenant",
        ),
        sa.CheckConstraint(
            "completed_at IS NULL OR completed_at >= started_at", name="ck_ingestion_times"
        ),
        sa.CheckConstraint(
            "records_received >= 0 AND records_inserted >= 0 AND records_rejected >= 0 AND error_count >= 0",
            name="ck_ingestion_counts",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_ingestion_tenant_site", "ingestion_run", ["tenant_id", "site_id"], schema=SCHEMA
    )
    op.create_index(
        "ix_ingestion_connection_started",
        "ingestion_run",
        ["data_source_connection_id", "started_at"],
        schema=SCHEMA,
    )
    op.create_index("ix_ingestion_status", "ingestion_run", ["status"], schema=SCHEMA)


def downgrade() -> None:
    for table in (
        "ingestion_run",
        "data_source_connection",
        "data_source",
        "data_rights_policy",
        "domain",
        "site",
        "organization",
        "tenant",
    ):
        op.drop_table(table, schema=SCHEMA)
    for name in (
        "quality_flag",
        "ingestion_status",
        "connection_status",
        "connection_type",
        "rights_decision",
        "source_type",
        "domain_type",
        "site_status",
        "tenant_status",
    ):
        postgresql.ENUM(name=name, schema=SCHEMA).drop(op.get_bind())
    op.execute(sa.schema.DropSchema(SCHEMA))
