"""Add immutable governed evidence-gap adjudication.

Revision ID: 20260912_0041
Revises: 20260908_0040
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260912_0041"
down_revision: Union[str, None] = "20260908_0040"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
SCHEMA = "gis_core"


def upgrade() -> None:
    op.create_table(
        "evidence_gap_adjudication",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evidence_gap_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("collection_requirement_id", postgresql.UUID(as_uuid=True)),
        sa.Column("analytical_entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("market_definition_id", postgresql.UUID(as_uuid=True)),
        sa.Column("previous_adjudication_id", postgresql.UUID(as_uuid=True)),
        sa.Column("outcome", sa.String(50), nullable=False),
        sa.Column("method_key", sa.String(100), nullable=False),
        sa.Column("method_version", sa.String(50), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("input_fingerprint", sa.String(64), nullable=False),
        sa.Column("required_capability", sa.String(100), nullable=False),
        sa.Column("observed_capabilities_json", postgresql.JSONB(), nullable=False),
        sa.Column("evidence_reference_ids_json", postgresql.JSONB(), nullable=False),
        sa.Column("scope_compatibility", sa.String(50), nullable=False),
        sa.Column("identity_compatibility", sa.String(50), nullable=False),
        sa.Column("freshness_assessment", sa.String(50), nullable=False),
        sa.Column("rights_assessment", sa.String(50), nullable=False),
        sa.Column("method_compatibility", sa.String(50), nullable=False),
        sa.Column("evidence_sufficiency", sa.String(50), nullable=False),
        sa.Column("conflict_state", sa.String(50), nullable=False),
        sa.Column("reasons_json", postgresql.JSONB(), nullable=False),
        sa.Column("rejected_evidence_json", postgresql.JSONB(), nullable=False),
        sa.Column("remaining_requirements_json", postgresql.JSONB(), nullable=False),
        sa.Column("limitations_json", postgresql.JSONB(), nullable=False),
        sa.Column("recommended_next_action", sa.Text(), nullable=False),
        sa.Column("human_review_required", sa.Boolean(), nullable=False),
        sa.Column("downstream_reassessment_eligible", sa.Boolean(), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "site_id"], [f"{SCHEMA}.site.tenant_id", f"{SCHEMA}.site.id"]
        ),
        sa.ForeignKeyConstraint(["evidence_gap_id"], [f"{SCHEMA}.evidence_gap.id"]),
        sa.ForeignKeyConstraint(
            ["collection_requirement_id"], [f"{SCHEMA}.collection_requirement.id"]
        ),
        sa.ForeignKeyConstraint(["analytical_entity_id"], [f"{SCHEMA}.analytical_entity.id"]),
        sa.ForeignKeyConstraint(["market_definition_id"], [f"{SCHEMA}.market_definition.id"]),
        sa.ForeignKeyConstraint(
            ["previous_adjudication_id"], [f"{SCHEMA}.evidence_gap_adjudication.id"]
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("input_fingerprint", name="uq_evidence_gap_adjudication_input"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_gap_adjudication_history",
        "evidence_gap_adjudication",
        ["evidence_gap_id", "evaluated_at", "id"],
        schema=SCHEMA,
    )
    op.create_index(
        "uq_gap_adjudication_current",
        "evidence_gap_adjudication",
        ["evidence_gap_id"],
        unique=True,
        schema=SCHEMA,
        postgresql_where=sa.text("is_current"),
    )
    op.create_index(
        "ix_gap_adjudication_scope_outcome",
        "evidence_gap_adjudication",
        ["tenant_id", "site_id", "outcome", "is_current"],
        schema=SCHEMA,
    )
    op.create_table(
        "evidence_gap_adjudication_evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("adjudication_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evidence_package_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["adjudication_id"], [f"{SCHEMA}.evidence_gap_adjudication.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["evidence_package_id"], [f"{SCHEMA}.evidence_package.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "adjudication_id", "evidence_package_id", name="uq_gap_adjudication_evidence"
        ),
        schema=SCHEMA,
    )
    op.create_table(
        "evidence_gap_adjudication_review",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("adjudication_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("decision", sa.String(32), nullable=False),
        sa.Column("reviewer", sa.String(255), nullable=False),
        sa.Column("comment", sa.Text()),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["adjudication_id"], [f"{SCHEMA}.evidence_gap_adjudication.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_gap_adjudication_review_history",
        "evidence_gap_adjudication_review",
        ["adjudication_id", "reviewed_at", "id"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_gap_adjudication_review_history",
        table_name="evidence_gap_adjudication_review",
        schema=SCHEMA,
    )
    op.drop_table("evidence_gap_adjudication_review", schema=SCHEMA)
    op.drop_table("evidence_gap_adjudication_evidence", schema=SCHEMA)
    op.drop_index(
        "ix_gap_adjudication_scope_outcome", table_name="evidence_gap_adjudication", schema=SCHEMA
    )
    op.drop_index(
        "uq_gap_adjudication_current", table_name="evidence_gap_adjudication", schema=SCHEMA
    )
    op.drop_index(
        "ix_gap_adjudication_history", table_name="evidence_gap_adjudication", schema=SCHEMA
    )
    op.drop_table("evidence_gap_adjudication", schema=SCHEMA)
