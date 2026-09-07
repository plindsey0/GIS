"""add governed LLM intelligence and experiment proposals

Revision ID: 20260907_0034
Revises: 20260905_0033
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260907_0034"
down_revision: Union[str, None] = "20260905_0033"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

J = postgresql.JSONB(astext_type=sa.Text())
U = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "llm_run",
        sa.Column("id", U, nullable=False), sa.Column("tenant_id", U, nullable=False),
        sa.Column("site_id", U, nullable=False), sa.Column("task_type", sa.String(100), nullable=False),
        sa.Column("provider_key", sa.String(100), nullable=False),
        sa.Column("model_identifier", sa.String(255), nullable=False),
        sa.Column("prompt_version", sa.String(100), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("input_evidence_ids_json", J, nullable=False),
        sa.Column("input_opportunity_ids_json", J, nullable=False),
        sa.Column("input_recommendation_ids_json", J, nullable=False),
        sa.Column("response_snapshot_json", J, nullable=False),
        sa.Column("validation_status", sa.String(50), nullable=False),
        sa.Column("validation_errors_json", J, nullable=False),
        sa.Column("provider_metadata_json", J, nullable=False),
        sa.Column("input_tokens", sa.Integer()), sa.Column("output_tokens", sa.Integer()),
        sa.Column("provider_cost", sa.Numeric(20, 8)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id", "site_id"], ["gis_core.site.tenant_id", "gis_core.site.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_fingerprint", name="uq_llm_run_request_fingerprint"),
        schema="gis_core")
    op.create_index("ix_llm_run_scope", "llm_run", ["tenant_id", "site_id", "created_at"], schema="gis_core")
    op.create_table(
        "llm_opportunity_detail", sa.Column("id", U, nullable=False),
        sa.Column("opportunity_id", U, nullable=False), sa.Column("llm_run_id", U, nullable=False),
        sa.Column("summary", sa.Text(), nullable=False), sa.Column("problem_or_signal", sa.Text(), nullable=False),
        sa.Column("reasoning", sa.Text(), nullable=False), sa.Column("expected_value", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False),
        sa.Column("suggested_action", sa.Text(), nullable=False), sa.Column("assumptions_json", J, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["llm_run_id"], ["gis_core.llm_run.id"]),
        sa.ForeignKeyConstraint(["opportunity_id"], ["gis_core.opportunity.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("opportunity_id", name="uq_llm_opportunity_detail"), schema="gis_core")
    op.create_table(
        "opportunity_review", sa.Column("id", U, nullable=False), sa.Column("opportunity_id", U, nullable=False),
        sa.Column("decision", sa.String(50), nullable=False), sa.Column("reviewer", sa.String(255), nullable=False),
        sa.Column("comment", sa.Text()), sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["opportunity_id"], ["gis_core.opportunity.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"), schema="gis_core")
    op.create_index("ix_opportunity_review_history", "opportunity_review", ["opportunity_id", "reviewed_at"], schema="gis_core")
    op.create_table(
        "llm_recommendation_detail", sa.Column("id", U, nullable=False),
        sa.Column("recommendation_id", U, nullable=False), sa.Column("llm_run_id", U, nullable=False),
        sa.Column("title", sa.Text(), nullable=False), sa.Column("recommended_action", sa.Text(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False), sa.Column("expected_impact", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False), sa.Column("priority", sa.String(50), nullable=False),
        sa.Column("estimated_effort", sa.String(50), nullable=False), sa.Column("risks_json", J, nullable=False),
        sa.Column("dependencies_json", J, nullable=False), sa.Column("success_signals_json", J, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["llm_run_id"], ["gis_core.llm_run.id"]),
        sa.ForeignKeyConstraint(["recommendation_id"], ["gis_core.recommendation.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("recommendation_id", name="uq_llm_recommendation_detail"), schema="gis_core")
    op.create_table(
        "recommendation_opportunity", sa.Column("id", U, nullable=False),
        sa.Column("recommendation_id", U, nullable=False), sa.Column("opportunity_id", U, nullable=False),
        sa.ForeignKeyConstraint(["opportunity_id"], ["gis_core.opportunity.id"]),
        sa.ForeignKeyConstraint(["recommendation_id"], ["gis_core.recommendation.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("recommendation_id", "opportunity_id", name="uq_recommendation_opportunity"), schema="gis_core")
    op.create_table(
        "experiment_proposal", sa.Column("id", U, nullable=False), sa.Column("tenant_id", U, nullable=False),
        sa.Column("site_id", U, nullable=False), sa.Column("recommendation_id", U, nullable=False),
        sa.Column("llm_run_id", U, nullable=False), sa.Column("status", sa.String(50), nullable=False),
        sa.Column("title", sa.Text(), nullable=False), sa.Column("objective", sa.Text(), nullable=False),
        sa.Column("hypothesis", sa.Text(), nullable=False), sa.Column("target_surface", sa.Text(), nullable=False),
        sa.Column("target_url_or_resource", sa.Text(), nullable=False),
        sa.Column("control_description", sa.Text(), nullable=False),
        sa.Column("treatment_description", sa.Text(), nullable=False),
        sa.Column("implementation_steps_json", J, nullable=False), sa.Column("primary_metric", sa.Text(), nullable=False),
        sa.Column("secondary_metrics_json", J, nullable=False), sa.Column("expected_direction", sa.String(50), nullable=False),
        sa.Column("expected_effect_description", sa.Text(), nullable=False),
        sa.Column("evaluation_window", sa.Text(), nullable=False),
        sa.Column("minimum_observation_guidance", sa.Text(), nullable=False),
        sa.Column("guardrail_metrics_json", J, nullable=False),
        sa.Column("instrumentation_requirements_json", J, nullable=False),
        sa.Column("dependencies_json", J, nullable=False), sa.Column("risks_json", J, nullable=False),
        sa.Column("rollback_plan", sa.Text(), nullable=False), sa.Column("decision_rule", sa.Text(), nullable=False),
        sa.Column("implementation_notes", sa.Text(), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["llm_run_id"], ["gis_core.llm_run.id"]),
        sa.ForeignKeyConstraint(["recommendation_id"], ["gis_core.recommendation.id"]),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("request_fingerprint", name="uq_experiment_proposal_request"), schema="gis_core")
    op.create_index("ix_experiment_proposal_scope", "experiment_proposal", ["tenant_id", "site_id", "status"], schema="gis_core")
    op.create_table(
        "experiment_proposal_evidence", sa.Column("id", U, nullable=False),
        sa.Column("experiment_proposal_id", U, nullable=False), sa.Column("evidence_package_id", U, nullable=False),
        sa.ForeignKeyConstraint(["evidence_package_id"], ["gis_core.evidence_package.id"]),
        sa.ForeignKeyConstraint(["experiment_proposal_id"], ["gis_core.experiment_proposal.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("experiment_proposal_id", "evidence_package_id", name="uq_experiment_proposal_evidence"), schema="gis_core")
    op.create_table(
        "experiment_proposal_review", sa.Column("id", U, nullable=False),
        sa.Column("experiment_proposal_id", U, nullable=False), sa.Column("decision", sa.String(50), nullable=False),
        sa.Column("reviewer", sa.String(255), nullable=False), sa.Column("comment", sa.Text()),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["experiment_proposal_id"], ["gis_core.experiment_proposal.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"), schema="gis_core")
    op.create_index("ix_experiment_proposal_review_history", "experiment_proposal_review",
                    ["experiment_proposal_id", "reviewed_at"], schema="gis_core")


def downgrade() -> None:
    """Remove only objects introduced by this revision.

    Repository migration tests exercise older revisions only in positively identified,
    run-owned disposable databases. Operators must not downgrade a persistent database.
    """
    op.drop_index("ix_experiment_proposal_review_history", table_name="experiment_proposal_review", schema="gis_core")
    op.drop_table("experiment_proposal_review", schema="gis_core")
    op.drop_table("experiment_proposal_evidence", schema="gis_core")
    op.drop_index("ix_experiment_proposal_scope", table_name="experiment_proposal", schema="gis_core")
    op.drop_table("experiment_proposal", schema="gis_core")
    op.drop_table("recommendation_opportunity", schema="gis_core")
    op.drop_table("llm_recommendation_detail", schema="gis_core")
    op.drop_index("ix_opportunity_review_history", table_name="opportunity_review", schema="gis_core")
    op.drop_table("opportunity_review", schema="gis_core")
    op.drop_table("llm_opportunity_detail", schema="gis_core")
    op.drop_index("ix_llm_run_scope", table_name="llm_run", schema="gis_core")
    op.drop_table("llm_run", schema="gis_core")
