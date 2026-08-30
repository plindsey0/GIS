"""Add versioned rights grants, acquisition provenance, and asset lineage.

Revision ID: 20260829_0006
Revises: 20260829_0005
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260829_0006"
down_revision: str | None = "20260829_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CORE = "gis_core"
rights_status = postgresql.ENUM(
    "ALLOWED", "DENIED", "UNKNOWN", name="rights_status", schema=CORE, create_type=False
)
permitted_use = postgresql.ENUM(
    "internal_analysis",
    "commercial_use",
    "raw_retention",
    "normalized_retention",
    "derivative_creation",
    "aggregate_statistics",
    "external_publication",
    "raw_redistribution",
    "normalized_redistribution",
    "customer_facing_display",
    "customer_export",
    "rag_retrieval",
    "ai_inference",
    "ai_training",
    name="permitted_use",
    schema=CORE,
    create_type=False,
)
acquisition_method = postgresql.ENUM(
    "FIRST_PARTY",
    "PUBLIC_API",
    "AUTHENTICATED_API",
    "LICENSED_API",
    "OPEN_DATA",
    "PUBLIC_WEB",
    "USER_PROVIDED",
    "MANUAL_IMPORT",
    "OTHER",
    "UNKNOWN",
    name="acquisition_method",
    schema=CORE,
    create_type=False,
)
asset_type = postgresql.ENUM(
    "TABLE",
    "VIEW",
    "MODEL",
    "DATASET",
    "METRIC",
    "EVIDENCE",
    "OTHER",
    name="asset_type",
    schema=CORE,
    create_type=False,
)
asset_layer = postgresql.ENUM(
    "RAW",
    "CORE",
    "STAGING",
    "INTERMEDIATE",
    "ANALYTICS",
    "EXTERNAL",
    "OTHER",
    name="asset_layer",
    schema=CORE,
    create_type=False,
)
lineage_type = postgresql.ENUM(
    "TRANSFORMS", "REFERENCES", "DERIVES", name="lineage_type", schema=CORE, create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    for enum in (
        rights_status,
        permitted_use,
        acquisition_method,
        asset_type,
        asset_layer,
        lineage_type,
    ):
        enum.create(bind, checkfirst=True)

    for column in (
        sa.Column("policy_version", sa.String(100), nullable=False, server_default="1"),
        sa.Column("effective_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("review_authority", sa.String(255)),
        sa.Column("documented_basis", sa.Text()),
        sa.Column("jurisdiction_notes", sa.Text()),
        sa.Column("supersedes_policy_id", sa.UUID()),
    ):
        op.add_column("data_rights_policy", column, schema=CORE)
    op.create_foreign_key(
        "fk_policy_supersedes",
        "data_rights_policy",
        "data_rights_policy",
        ["supersedes_policy_id"],
        ["id"],
        source_schema=CORE,
        referent_schema=CORE,
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        "ck_policy_effective_window",
        "data_rights_policy",
        "expires_at IS NULL OR effective_at IS NULL OR expires_at >= effective_at",
        schema=CORE,
    )

    op.create_table(
        "data_rights_grant",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("policy_id", sa.UUID(), nullable=False),
        sa.Column("permitted_use", permitted_use, nullable=False),
        sa.Column("status", rights_status, nullable=False, server_default="UNKNOWN"),
        sa.Column("reason", sa.Text()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(
            ["policy_id"], [f"{CORE}.data_rights_policy.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint("policy_id", "permitted_use", name="uq_rights_grant_policy_use"),
        schema=CORE,
    )
    op.create_index("ix_rights_grant_policy", "data_rights_grant", ["policy_id"], schema=CORE)

    op.add_column(
        "data_source",
        sa.Column(
            "acquisition_method", acquisition_method, nullable=False, server_default="UNKNOWN"
        ),
        schema=CORE,
    )
    op.add_column("data_source", sa.Column("authoritative_url", sa.String(2048)), schema=CORE)
    op.add_column("data_source", sa.Column("terms_url", sa.String(2048)), schema=CORE)
    op.add_column(
        "data_source",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        schema=CORE,
    )
    op.execute(
        sa.text(
            f"UPDATE {CORE}.data_source SET acquisition_method = CASE WHEN key = 'first_party' THEN 'FIRST_PARTY'::{CORE}.acquisition_method WHEN key IN ('google_search_console', 'ga4') THEN 'AUTHENTICATED_API'::{CORE}.acquisition_method WHEN source_type::text = 'MANUAL' THEN 'MANUAL_IMPORT'::{CORE}.acquisition_method ELSE 'UNKNOWN'::{CORE}.acquisition_method END"
        )
    )

    for column in (
        sa.Column("records_updated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rights_policy_id", sa.UUID()),
        sa.Column(
            "acquisition_method", acquisition_method, nullable=False, server_default="UNKNOWN"
        ),
        sa.Column("collector_name", sa.String(255)),
        sa.Column("collector_version", sa.String(100)),
        sa.Column("schema_version", sa.String(100)),
        sa.Column("requested_start_at", sa.DateTime(timezone=True)),
        sa.Column("requested_end_at", sa.DateTime(timezone=True)),
        sa.Column(
            "source_metadata",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    ):
        op.add_column("ingestion_run", column, schema=CORE)
    op.create_foreign_key(
        "fk_ingestion_rights_policy",
        "ingestion_run",
        "data_rights_policy",
        ["rights_policy_id"],
        ["id"],
        source_schema=CORE,
        referent_schema=CORE,
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        "ck_ingestion_records_updated", "ingestion_run", "records_updated >= 0", schema=CORE
    )
    op.create_check_constraint(
        "ck_ingestion_requested_window",
        "ingestion_run",
        "requested_end_at IS NULL OR requested_start_at IS NULL OR requested_end_at >= requested_start_at",
        schema=CORE,
    )
    op.execute(
        sa.text(
            f"UPDATE {CORE}.ingestion_run r SET acquisition_method = s.acquisition_method "
            f"FROM {CORE}.data_source_connection c JOIN {CORE}.data_source s "
            "ON s.id = c.data_source_id WHERE c.id = r.data_source_connection_id"
        )
    )
    op.execute(
        sa.text(
            "WITH observed_policies AS ("
            " SELECT ingestion_run_id, rights_policy_id FROM gis_raw.gsc_search_observation"
            " UNION ALL SELECT ingestion_run_id, rights_policy_id FROM gis_raw.ga4_landing_page_observation"
            " UNION ALL SELECT ingestion_run_id, rights_policy_id FROM gis_raw.ga4_acquisition_observation"
            " UNION ALL SELECT ingestion_run_id, rights_policy_id FROM gis_raw.ga4_event_observation"
            "), unambiguous AS ("
            " SELECT ingestion_run_id, min(rights_policy_id::text)::uuid AS rights_policy_id"
            " FROM observed_policies GROUP BY ingestion_run_id"
            " HAVING count(DISTINCT rights_policy_id) = 1"
            ") UPDATE gis_core.ingestion_run r SET rights_policy_id = u.rights_policy_id"
            " FROM unambiguous u WHERE u.ingestion_run_id = r.id"
        )
    )

    op.create_table(
        "data_asset",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("canonical_name", sa.String(512), nullable=False),
        sa.Column("asset_type", asset_type, nullable=False),
        sa.Column("layer", asset_layer, nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("canonical_name", name="uq_data_asset_canonical_name"),
        schema=CORE,
    )
    op.create_index("ix_data_asset_layer", "data_asset", ["layer"], schema=CORE)
    op.create_table(
        "data_asset_source",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("asset_id", sa.UUID(), nullable=False),
        sa.Column("data_source_id", sa.UUID(), nullable=False),
        sa.Column("data_source_connection_id", sa.UUID()),
        sa.Column("rights_policy_id", sa.UUID()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["asset_id"], [f"{CORE}.data_asset.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["data_source_id"], [f"{CORE}.data_source.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["data_source_connection_id"], [f"{CORE}.data_source_connection.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["rights_policy_id"], [f"{CORE}.data_rights_policy.id"], ondelete="SET NULL"
        ),
        sa.UniqueConstraint(
            "asset_id", "data_source_id", "data_source_connection_id", name="uq_asset_source_scope"
        ),
        schema=CORE,
    )
    op.create_index("ix_data_asset_source_asset", "data_asset_source", ["asset_id"], schema=CORE)
    op.create_table(
        "data_asset_lineage",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("upstream_asset_id", sa.UUID(), nullable=False),
        sa.Column("downstream_asset_id", sa.UUID(), nullable=False),
        sa.Column("lineage_type", lineage_type, nullable=False, server_default="TRANSFORMS"),
        sa.Column("transformation_reference", sa.String(2048)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(
            ["upstream_asset_id"], [f"{CORE}.data_asset.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["downstream_asset_id"], [f"{CORE}.data_asset.id"], ondelete="CASCADE"
        ),
        sa.CheckConstraint("upstream_asset_id <> downstream_asset_id", name="ck_lineage_not_self"),
        sa.UniqueConstraint(
            "upstream_asset_id", "downstream_asset_id", name="uq_asset_lineage_edge"
        ),
        schema=CORE,
    )
    op.create_index(
        "ix_lineage_downstream", "data_asset_lineage", ["downstream_asset_id"], schema=CORE
    )


def downgrade() -> None:
    op.drop_table("data_asset_lineage", schema=CORE)
    op.drop_table("data_asset_source", schema=CORE)
    op.drop_table("data_asset", schema=CORE)
    for name in ("ck_ingestion_requested_window", "ck_ingestion_records_updated"):
        op.drop_constraint(name, "ingestion_run", schema=CORE, type_="check")
    op.drop_constraint(
        "fk_ingestion_rights_policy", "ingestion_run", schema=CORE, type_="foreignkey"
    )
    for name in (
        "source_metadata",
        "requested_end_at",
        "requested_start_at",
        "schema_version",
        "collector_version",
        "collector_name",
        "acquisition_method",
        "rights_policy_id",
        "records_updated",
    ):
        op.drop_column("ingestion_run", name, schema=CORE)
    for name in ("is_active", "terms_url", "authoritative_url", "acquisition_method"):
        op.drop_column("data_source", name, schema=CORE)
    op.drop_table("data_rights_grant", schema=CORE)
    op.drop_constraint(
        "ck_policy_effective_window", "data_rights_policy", schema=CORE, type_="check"
    )
    op.drop_constraint(
        "fk_policy_supersedes", "data_rights_policy", schema=CORE, type_="foreignkey"
    )
    for name in (
        "supersedes_policy_id",
        "jurisdiction_notes",
        "documented_basis",
        "review_authority",
        "reviewed_at",
        "expires_at",
        "effective_at",
        "policy_version",
    ):
        op.drop_column("data_rights_policy", name, schema=CORE)
    bind = op.get_bind()
    for enum in (
        lineage_type,
        asset_layer,
        asset_type,
        acquisition_method,
        permitted_use,
        rights_status,
    ):
        enum.drop(bind, checkfirst=True)
