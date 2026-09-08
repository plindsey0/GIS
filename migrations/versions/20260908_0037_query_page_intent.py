"""Add versioned governed query/page/intent assessments.

Revision ID: 20260908_0037
Revises: 20260907_0036
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260908_0037"
down_revision: Union[str, None] = "20260907_0036"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
SCHEMA = "gis_core"


def upgrade() -> None:
    op.create_table(
        "query_page_intent_assessment",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("query_entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("page_entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("market_definition_id", postgresql.UUID(as_uuid=True)),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("page_url", sa.Text(), nullable=False),
        sa.Column("association_state", sa.String(50), nullable=False),
        sa.Column("targeting_state", sa.String(50), nullable=False),
        sa.Column("intent_satisfaction_state", sa.String(50), nullable=False),
        sa.Column("interpreted_user_need", sa.Text(), nullable=False),
        sa.Column("origin", sa.String(32), nullable=False),
        sa.Column("method_key", sa.String(100), nullable=False),
        sa.Column("method_version", sa.String(50), nullable=False),
        sa.Column("prompt_version", sa.String(100)),
        sa.Column("llm_run_id", postgresql.UUID(as_uuid=True)),
        sa.Column("previous_assessment_id", postgresql.UUID(as_uuid=True)),
        sa.Column("input_fingerprint", sa.String(64), nullable=False),
        sa.Column("page_content_fingerprint", sa.String(64)),
        sa.Column("serp_fingerprint", sa.String(64)),
        sa.Column("supporting_references_json", postgresql.JSONB(), nullable=False),
        sa.Column("conflicting_references_json", postgresql.JSONB(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("assumptions_json", postgresql.JSONB(), nullable=False),
        sa.Column("limitations_json", postgresql.JSONB(), nullable=False),
        sa.Column("evidence_gaps_json", postgresql.JSONB(), nullable=False),
        sa.Column("quality_json", postgresql.JSONB(), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column("reassessment_needed", sa.Boolean(), nullable=False),
        sa.Column("reassessment_reasons_json", postgresql.JSONB(), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id", "site_id"], [f"{SCHEMA}.site.tenant_id", f"{SCHEMA}.site.id"]),
        sa.ForeignKeyConstraint(["query_entity_id"], [f"{SCHEMA}.analytical_entity.id"]),
        sa.ForeignKeyConstraint(["page_entity_id"], [f"{SCHEMA}.analytical_entity.id"]),
        sa.ForeignKeyConstraint(["market_definition_id"], [f"{SCHEMA}.market_definition.id"]),
        sa.ForeignKeyConstraint(["llm_run_id"], [f"{SCHEMA}.llm_run.id"]),
        sa.ForeignKeyConstraint(["previous_assessment_id"], [f"{SCHEMA}.query_page_intent_assessment.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("input_fingerprint", name="uq_query_page_intent_input"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_query_page_intent_current",
        "query_page_intent_assessment",
        ["tenant_id", "site_id", "query_entity_id", "page_entity_id", "is_current"],
        schema=SCHEMA,
    )
    op.create_table(
        "query_page_intent_evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assessment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evidence_package_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["assessment_id"], [f"{SCHEMA}.query_page_intent_assessment.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["evidence_package_id"], [f"{SCHEMA}.evidence_package.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("assessment_id", "evidence_package_id", name="uq_query_page_intent_evidence"),
        schema=SCHEMA,
    )
    op.create_table(
        "query_page_intent_review",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assessment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("decision", sa.String(32), nullable=False),
        sa.Column("reviewer", sa.String(255), nullable=False),
        sa.Column("comment", sa.Text()),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["assessment_id"], [f"{SCHEMA}.query_page_intent_assessment.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )
    op.create_index("ix_query_page_intent_review_history", "query_page_intent_review", ["assessment_id", "reviewed_at"], schema=SCHEMA)


def downgrade() -> None:
    op.drop_index("ix_query_page_intent_review_history", table_name="query_page_intent_review", schema=SCHEMA)
    op.drop_table("query_page_intent_review", schema=SCHEMA)
    op.drop_table("query_page_intent_evidence", schema=SCHEMA)
    op.drop_index("ix_query_page_intent_current", table_name="query_page_intent_assessment", schema=SCHEMA)
    op.drop_table("query_page_intent_assessment", schema=SCHEMA)
