"""Add governed SEO measurement plans and outcome tracking.

Revision ID: 20260912_0044
Revises: 20260912_0043
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260912_0044"
down_revision: Union[str, None] = "20260912_0043"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
SCHEMA = "gis_core"


def upgrade() -> None:
    op.create_table("seo_measurement_plan",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("site_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("investigation_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("content_brief_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("proposal_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("query_entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("page_entity_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("market_definition_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("exact_query", sa.Text(), nullable=False), sa.Column("candidate_url", sa.Text(), nullable=False), sa.Column("status", sa.String(50), nullable=False),
        sa.Column("measurement_method", sa.String(100), nullable=False), sa.Column("method_version", sa.String(50), nullable=False),
        sa.Column("previous_plan_id", postgresql.UUID(as_uuid=True)), sa.Column("identity_hash", sa.String(64), nullable=False), sa.Column("created_by", sa.String(255), nullable=False),
        sa.Column("baseline_start", sa.Date(), nullable=False), sa.Column("baseline_end", sa.Date(), nullable=False), sa.Column("implementation_at", sa.DateTime(timezone=True)),
        sa.Column("observation_start", sa.Date(), nullable=False), sa.Column("observation_end", sa.Date(), nullable=False), sa.Column("minimum_observation_guidance", sa.Text(), nullable=False),
        sa.Column("primary_signals_json", postgresql.JSONB(), nullable=False), sa.Column("secondary_signals_json", postgresql.JSONB(), nullable=False),
        sa.Column("guardrail_signals_json", postgresql.JSONB(), nullable=False), sa.Column("required_sources_json", postgresql.JSONB(), nullable=False),
        sa.Column("scope_dimensions_json", postgresql.JSONB(), nullable=False), sa.Column("expected_direction", sa.String(32), nullable=False),
        sa.Column("null_expectation", sa.Text(), nullable=False), sa.Column("confounders_json", postgresql.JSONB(), nullable=False),
        sa.Column("risks_json", postgresql.JSONB(), nullable=False), sa.Column("assumptions_json", postgresql.JSONB(), nullable=False),
        sa.Column("limitations_json", postgresql.JSONB(), nullable=False), sa.Column("decision_rule", sa.Text(), nullable=False),
        sa.Column("human_review_requirements_json", postgresql.JSONB(), nullable=False), sa.Column("readiness_state", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id", "site_id"], [f"{SCHEMA}.site.tenant_id", f"{SCHEMA}.site.id"]),
        sa.ForeignKeyConstraint(["investigation_id"], [f"{SCHEMA}.seo_investigation.id"]), sa.ForeignKeyConstraint(["content_brief_id"], [f"{SCHEMA}.content_brief.id"]),
        sa.ForeignKeyConstraint(["proposal_id"], [f"{SCHEMA}.page_change_proposal.id"]), sa.ForeignKeyConstraint(["query_entity_id"], [f"{SCHEMA}.analytical_entity.id"]),
        sa.ForeignKeyConstraint(["page_entity_id"], [f"{SCHEMA}.analytical_entity.id"]), sa.ForeignKeyConstraint(["market_definition_id"], [f"{SCHEMA}.market_definition.id"]),
        sa.ForeignKeyConstraint(["previous_plan_id"], [f"{SCHEMA}.seo_measurement_plan.id"]), sa.UniqueConstraint("identity_hash", name="uq_seo_measurement_plan_identity"), schema=SCHEMA)
    op.create_index("ix_seo_measurement_plan_scope", "seo_measurement_plan", ["tenant_id", "site_id", "status", "updated_at", "id"], schema=SCHEMA)
    op.create_index("ix_seo_measurement_plan_history", "seo_measurement_plan", ["proposal_id", "created_at", "id"], schema=SCHEMA)
    op.create_table("seo_implementation_record",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("measurement_plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("proposal_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("candidate_url", sa.Text(), nullable=False),
        sa.Column("actor", sa.String(255), nullable=False), sa.Column("implementation_state", sa.String(50), nullable=False),
        sa.Column("claimed_implementation_at", sa.DateTime(timezone=True)), sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deployment_reference", sa.Text()), sa.Column("implemented_categories_json", postgresql.JSONB(), nullable=False),
        sa.Column("deviations_json", postgresql.JSONB(), nullable=False), sa.Column("concurrent_changes_json", postgresql.JSONB(), nullable=False),
        sa.Column("rollback_reference", sa.Text()), sa.Column("notes", sa.Text()), sa.Column("artifact_references_json", postgresql.JSONB(), nullable=False),
        sa.Column("verification_state", sa.String(50), nullable=False), sa.Column("reviewer", sa.String(255)), sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["tenant_id", "site_id"], [f"{SCHEMA}.site.tenant_id", f"{SCHEMA}.site.id"]),
        sa.ForeignKeyConstraint(["measurement_plan_id"], [f"{SCHEMA}.seo_measurement_plan.id"]), sa.ForeignKeyConstraint(["proposal_id"], [f"{SCHEMA}.page_change_proposal.id"]), schema=SCHEMA)
    op.create_index("ix_seo_implementation_history", "seo_implementation_record", ["measurement_plan_id", "recorded_at", "id"], schema=SCHEMA)
    op.create_table("seo_outcome_assessment",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("measurement_plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("implementation_record_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("previous_assessment_id", postgresql.UUID(as_uuid=True)),
        sa.Column("input_fingerprint", sa.String(64), nullable=False), sa.Column("assessed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_start", sa.Date(), nullable=False), sa.Column("window_end", sa.Date(), nullable=False), sa.Column("outcome_state", sa.String(50), nullable=False),
        sa.Column("primary_result_json", postgresql.JSONB(), nullable=False), sa.Column("secondary_results_json", postgresql.JSONB(), nullable=False),
        sa.Column("guardrail_results_json", postgresql.JSONB(), nullable=False), sa.Column("evidence_package_ids_json", postgresql.JSONB(), nullable=False),
        sa.Column("evidence_reference_ids_json", postgresql.JSONB(), nullable=False), sa.Column("scope_result", sa.String(50), nullable=False),
        sa.Column("rights_result", sa.String(50), nullable=False), sa.Column("quality_result", sa.String(50), nullable=False),
        sa.Column("completeness_result", sa.String(50), nullable=False), sa.Column("conflict_state", sa.String(50), nullable=False),
        sa.Column("confounders_json", postgresql.JSONB(), nullable=False), sa.Column("concurrent_changes_json", postgresql.JSONB(), nullable=False),
        sa.Column("comparisons_json", postgresql.JSONB(), nullable=False), sa.Column("bounded_interpretation", sa.Text(), nullable=False),
        sa.Column("causal_classification", sa.String(50), nullable=False), sa.Column("assumptions_json", postgresql.JSONB(), nullable=False),
        sa.Column("limitations_json", postgresql.JSONB(), nullable=False), sa.Column("remaining_needs_json", postgresql.JSONB(), nullable=False),
        sa.Column("recommended_next_action", sa.Text(), nullable=False), sa.Column("continued_observation_required", sa.Boolean(), nullable=False),
        sa.Column("human_review_required", sa.Boolean(), nullable=False), sa.Column("closure_eligible", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["measurement_plan_id"], [f"{SCHEMA}.seo_measurement_plan.id"]), sa.ForeignKeyConstraint(["implementation_record_id"], [f"{SCHEMA}.seo_implementation_record.id"]),
        sa.ForeignKeyConstraint(["previous_assessment_id"], [f"{SCHEMA}.seo_outcome_assessment.id"]), sa.UniqueConstraint("input_fingerprint", name="uq_seo_outcome_assessment_input"), schema=SCHEMA)
    op.create_index("ix_seo_outcome_history", "seo_outcome_assessment", ["measurement_plan_id", "assessed_at", "id"], schema=SCHEMA)
    op.create_table("seo_measurement_review",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("measurement_plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("artifact_type", sa.String(50), nullable=False), sa.Column("artifact_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reviewer", sa.String(255), nullable=False), sa.Column("decision", sa.String(50), nullable=False), sa.Column("comment", sa.Text()),
        sa.Column("evidence_fingerprint", sa.String(64), nullable=False), sa.Column("requested_follow_up_json", postgresql.JSONB(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False), sa.ForeignKeyConstraint(["measurement_plan_id"], [f"{SCHEMA}.seo_measurement_plan.id"]), schema=SCHEMA)
    op.create_index("ix_seo_measurement_review_history", "seo_measurement_review", ["artifact_type", "artifact_id", "reviewed_at", "id"], schema=SCHEMA)


def downgrade() -> None:
    op.drop_index("ix_seo_measurement_review_history", table_name="seo_measurement_review", schema=SCHEMA)
    op.drop_table("seo_measurement_review", schema=SCHEMA)
    op.drop_index("ix_seo_outcome_history", table_name="seo_outcome_assessment", schema=SCHEMA)
    op.drop_table("seo_outcome_assessment", schema=SCHEMA)
    op.drop_index("ix_seo_implementation_history", table_name="seo_implementation_record", schema=SCHEMA)
    op.drop_table("seo_implementation_record", schema=SCHEMA)
    op.drop_index("ix_seo_measurement_plan_history", table_name="seo_measurement_plan", schema=SCHEMA)
    op.drop_index("ix_seo_measurement_plan_scope", table_name="seo_measurement_plan", schema=SCHEMA)
    op.drop_table("seo_measurement_plan", schema=SCHEMA)
