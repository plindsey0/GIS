"""Add guided SEO investigations and append-only events.

Revision ID: 20260912_0042
Revises: 20260912_0041
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260912_0042"
down_revision: Union[str, None] = "20260912_0041"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
SCHEMA = "gis_core"


def upgrade() -> None:
    op.create_table(
        "seo_investigation",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("query_entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("candidate_page_entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("market_definition_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("exact_query", sa.Text(), nullable=False),
        sa.Column("normalized_candidate_url", sa.Text(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("lifecycle_state", sa.String(50), nullable=False),
        sa.Column("priority", postgresql.ENUM(name="collection_priority_tier", schema=SCHEMA, create_type=False), nullable=False),
        sa.Column("origin", sa.String(50), nullable=False),
        sa.Column("created_by", sa.String(255), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column("close_reason", sa.Text()),
        sa.Column("evidence_readiness_state", sa.String(50), nullable=False),
        sa.Column("human_review_required", sa.Boolean(), nullable=False),
        sa.Column("recommendation_generation_eligible", sa.Boolean(), nullable=False),
        sa.Column("identity_hash", sa.String(64), nullable=False),
        sa.Column("originating_proposal_id", postgresql.UUID(as_uuid=True)),
        sa.Column("originating_recommendation_id", postgresql.UUID(as_uuid=True)),
        sa.Column("current_query_page_intent_assessment_id", postgresql.UUID(as_uuid=True)),
        sa.Column("current_evidence_gap_adjudication_id", postgresql.UUID(as_uuid=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id", "site_id"], [f"{SCHEMA}.site.tenant_id", f"{SCHEMA}.site.id"]),
        sa.ForeignKeyConstraint(["query_entity_id"], [f"{SCHEMA}.analytical_entity.id"]),
        sa.ForeignKeyConstraint(["candidate_page_entity_id"], [f"{SCHEMA}.analytical_entity.id"]),
        sa.ForeignKeyConstraint(["market_definition_id"], [f"{SCHEMA}.market_definition.id"]),
        sa.ForeignKeyConstraint(["originating_proposal_id"], [f"{SCHEMA}.experiment_proposal.id"]),
        sa.ForeignKeyConstraint(["originating_recommendation_id"], [f"{SCHEMA}.recommendation.id"]),
        sa.ForeignKeyConstraint(["current_query_page_intent_assessment_id"], [f"{SCHEMA}.query_page_intent_assessment.id"]),
        sa.ForeignKeyConstraint(["current_evidence_gap_adjudication_id"], [f"{SCHEMA}.evidence_gap_adjudication.id"]),
        sa.PrimaryKeyConstraint("id"), schema=SCHEMA,
    )
    op.create_index("uq_seo_investigation_active_identity", "seo_investigation", ["identity_hash"], unique=True, schema=SCHEMA, postgresql_where=sa.text("closed_at IS NULL"))
    op.create_index("ix_seo_investigation_scope_stage", "seo_investigation", ["tenant_id", "site_id", "lifecycle_state", "priority"], schema=SCHEMA)
    op.create_index("ix_seo_investigation_order", "seo_investigation", ["tenant_id", "site_id", "updated_at", "id"], schema=SCHEMA)
    op.create_table(
        "seo_investigation_event",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("investigation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor", sa.String(255), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("previous_state", sa.String(50)),
        sa.Column("new_state", sa.String(50), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("evidence_gap_id", postgresql.UUID(as_uuid=True)),
        sa.Column("adjudication_id", postgresql.UUID(as_uuid=True)),
        sa.Column("assessment_id", postgresql.UUID(as_uuid=True)),
        sa.Column("collection_requirement_id", postgresql.UUID(as_uuid=True)),
        sa.Column("review_id", postgresql.UUID(as_uuid=True)),
        sa.Column("metadata", postgresql.JSONB(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["investigation_id"], [f"{SCHEMA}.seo_investigation.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["evidence_gap_id"], [f"{SCHEMA}.evidence_gap.id"]),
        sa.ForeignKeyConstraint(["adjudication_id"], [f"{SCHEMA}.evidence_gap_adjudication.id"]),
        sa.ForeignKeyConstraint(["assessment_id"], [f"{SCHEMA}.query_page_intent_assessment.id"]),
        sa.ForeignKeyConstraint(["collection_requirement_id"], [f"{SCHEMA}.collection_requirement.id"]),
        sa.PrimaryKeyConstraint("id"), schema=SCHEMA,
    )
    op.create_index("ix_seo_investigation_event_history", "seo_investigation_event", ["investigation_id", "occurred_at", "id"], schema=SCHEMA)


def downgrade() -> None:
    op.drop_index("ix_seo_investigation_event_history", table_name="seo_investigation_event", schema=SCHEMA)
    op.drop_table("seo_investigation_event", schema=SCHEMA)
    op.drop_index("ix_seo_investigation_order", table_name="seo_investigation", schema=SCHEMA)
    op.drop_index("ix_seo_investigation_scope_stage", table_name="seo_investigation", schema=SCHEMA)
    op.drop_index("uq_seo_investigation_active_identity", table_name="seo_investigation", schema=SCHEMA)
    op.drop_table("seo_investigation", schema=SCHEMA)
