"""Add evidence-backed content briefs and page-change proposals.

Revision ID: 20260912_0043
Revises: 20260912_0042
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260912_0043"
down_revision: Union[str, None] = "20260912_0042"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
SCHEMA = "gis_core"


def upgrade() -> None:
    op.create_table("content_brief",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("investigation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("query_entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("page_entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("market_definition_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("exact_query", sa.Text(), nullable=False), sa.Column("candidate_url", sa.Text(), nullable=False),
        sa.Column("brief_type", sa.String(50), nullable=False), sa.Column("status", sa.String(50), nullable=False),
        sa.Column("method_key", sa.String(100), nullable=False), sa.Column("method_version", sa.String(50), nullable=False),
        sa.Column("prompt_version", sa.String(100)), sa.Column("llm_run_id", postgresql.UUID(as_uuid=True)),
        sa.Column("previous_brief_id", postgresql.UUID(as_uuid=True)), sa.Column("input_fingerprint", sa.String(64), nullable=False),
        sa.Column("evidence_package_ids_json", postgresql.JSONB(), nullable=False), sa.Column("evidence_reference_ids_json", postgresql.JSONB(), nullable=False),
        sa.Column("adjudication_ids_json", postgresql.JSONB(), nullable=False), sa.Column("assessment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("human_review_dependencies_json", postgresql.JSONB(), nullable=False), sa.Column("executive_summary", sa.Text(), nullable=False),
        sa.Column("interpreted_user_need", sa.Text(), nullable=False), sa.Column("current_page_role", sa.Text(), nullable=False),
        sa.Column("recommended_page_role", sa.Text(), nullable=False), sa.Column("audience_json", postgresql.JSONB(), nullable=False),
        sa.Column("recommendations_json", postgresql.JSONB(), nullable=False), sa.Column("out_of_scope_json", postgresql.JSONB(), nullable=False),
        sa.Column("prohibited_claims_json", postgresql.JSONB(), nullable=False), sa.Column("assumptions_json", postgresql.JSONB(), nullable=False),
        sa.Column("conflicts_json", postgresql.JSONB(), nullable=False), sa.Column("limitations_json", postgresql.JSONB(), nullable=False),
        sa.Column("remaining_gaps_json", postgresql.JSONB(), nullable=False), sa.Column("recommended_next_action", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id", "site_id"], [f"{SCHEMA}.site.tenant_id", f"{SCHEMA}.site.id"]),
        sa.ForeignKeyConstraint(["investigation_id"], [f"{SCHEMA}.seo_investigation.id"]),
        sa.ForeignKeyConstraint(["query_entity_id"], [f"{SCHEMA}.analytical_entity.id"]), sa.ForeignKeyConstraint(["page_entity_id"], [f"{SCHEMA}.analytical_entity.id"]),
        sa.ForeignKeyConstraint(["market_definition_id"], [f"{SCHEMA}.market_definition.id"]), sa.ForeignKeyConstraint(["llm_run_id"], [f"{SCHEMA}.llm_run.id"]),
        sa.ForeignKeyConstraint(["previous_brief_id"], [f"{SCHEMA}.content_brief.id"]), sa.ForeignKeyConstraint(["assessment_id"], [f"{SCHEMA}.query_page_intent_assessment.id"]),
        sa.UniqueConstraint("input_fingerprint", name="uq_content_brief_input"), schema=SCHEMA)
    op.create_index("ix_content_brief_scope", "content_brief", ["tenant_id", "site_id", "status", "created_at", "id"], schema=SCHEMA)
    op.create_index("ix_content_brief_history", "content_brief", ["investigation_id", "created_at", "id"], schema=SCHEMA)
    op.create_table("page_change_proposal",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("content_brief_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("investigation_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("target_page", sa.Text(), nullable=False),
        sa.Column("category", sa.String(100), nullable=False), sa.Column("target_region", sa.String(100), nullable=False),
        sa.Column("current_observed_state", sa.Text(), nullable=False), sa.Column("proposed_instruction", sa.Text(), nullable=False), sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("supporting_reference_ids_json", postgresql.JSONB(), nullable=False), sa.Column("conflicting_reference_ids_json", postgresql.JSONB(), nullable=False),
        sa.Column("expected_qualitative_effect", sa.Text(), nullable=False), sa.Column("measurement_signal", sa.Text(), nullable=False), sa.Column("risk", sa.Text(), nullable=False),
        sa.Column("dependencies_json", postgresql.JSONB(), nullable=False), sa.Column("review_requirements_json", postgresql.JSONB(), nullable=False),
        sa.Column("implementation_owner_type", sa.String(50), nullable=False), sa.Column("engineering_required", sa.Boolean(), nullable=False),
        sa.Column("compliance_review_required", sa.Boolean(), nullable=False), sa.Column("analytics_instrumentation_required", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(50), nullable=False), sa.Column("previous_proposal_id", postgresql.UUID(as_uuid=True)),
        sa.Column("identity_hash", sa.String(64), nullable=False), sa.Column("evidence_fingerprint", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["content_brief_id"], [f"{SCHEMA}.content_brief.id"]), sa.ForeignKeyConstraint(["investigation_id"], [f"{SCHEMA}.seo_investigation.id"]),
        sa.ForeignKeyConstraint(["previous_proposal_id"], [f"{SCHEMA}.page_change_proposal.id"]), sa.UniqueConstraint("identity_hash", name="uq_page_change_proposal_identity"), schema=SCHEMA)
    op.create_index("ix_page_change_proposal_brief", "page_change_proposal", ["content_brief_id", "status", "created_at", "id"], schema=SCHEMA)
    op.create_index("ix_page_change_proposal_investigation", "page_change_proposal", ["investigation_id", "created_at", "id"], schema=SCHEMA)
    op.create_table("content_proposal_review",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("proposal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reviewer", sa.String(255), nullable=False), sa.Column("decision", sa.String(50), nullable=False), sa.Column("comment", sa.Text()),
        sa.Column("evidence_fingerprint", sa.String(64), nullable=False), sa.Column("scope_fingerprint", sa.String(64), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False), sa.ForeignKeyConstraint(["proposal_id"], [f"{SCHEMA}.page_change_proposal.id"]), schema=SCHEMA)
    op.create_index("ix_content_proposal_review_history", "content_proposal_review", ["proposal_id", "reviewed_at", "id"], schema=SCHEMA)


def downgrade() -> None:
    op.drop_index("ix_content_proposal_review_history", table_name="content_proposal_review", schema=SCHEMA)
    op.drop_table("content_proposal_review", schema=SCHEMA)
    op.drop_index("ix_page_change_proposal_investigation", table_name="page_change_proposal", schema=SCHEMA)
    op.drop_index("ix_page_change_proposal_brief", table_name="page_change_proposal", schema=SCHEMA)
    op.drop_table("page_change_proposal", schema=SCHEMA)
    op.drop_index("ix_content_brief_history", table_name="content_brief", schema=SCHEMA)
    op.drop_index("ix_content_brief_scope", table_name="content_brief", schema=SCHEMA)
    op.drop_table("content_brief", schema=SCHEMA)
