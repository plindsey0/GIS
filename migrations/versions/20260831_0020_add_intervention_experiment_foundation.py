"""add intervention experiment foundation

Revision ID: 20260831_0020
Revises: 20260831_0019
Create Date: 2026-08-31 08:57:21.512105
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260831_0020"
down_revision: Union[str, None] = '20260831_0019'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _enum(name: str) -> postgresql.ENUM:
    return postgresql.ENUM(name=name, schema="gis_core", create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    definitions = {
        "intervention_family": ['CONTENT', 'SEO', 'EXPERIENCE', 'CONVERSION', 'TECHNICAL', 'INTERNAL_LINKING', 'AUTHORITY', 'RESEARCH_ASSET', 'COLLECTION'],
        "intervention_status": ['DRAFT', 'PROPOSED', 'APPROVED', 'REJECTED', 'SCHEDULED', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED', 'MEASURING', 'MEASURED', 'ARCHIVED'],
        "feasibility_state": ['FEASIBLE', 'BLOCKED', 'PARTIALLY_FEASIBLE', 'UNKNOWN'],
        "measurement_readiness": ['READY', 'PARTIAL', 'NOT_READY', 'UNKNOWN'],
        "expected_direction": ['INCREASE', 'DECREASE', 'IMPROVE', 'MAINTAIN'],
        "experiment_type": ['OBSERVATIONAL_BEFORE_AFTER', 'A_B_TEST', 'HOLDOUT', 'MATCHED_CONTROL', 'TIME_SERIES'],
        "experiment_status": ['DRAFT', 'READY', 'RUNNING', 'PAUSED', 'COMPLETED', 'INVALIDATED', 'CANCELLED'],
        "outcome_state": ['POSITIVE', 'NEGATIVE', 'NEUTRAL', 'MIXED', 'INCONCLUSIVE', 'NOT_MEASURABLE', 'INSUFFICIENT_DATA'],
        "metric_role": ['PRIMARY', 'SECONDARY', 'GUARDRAIL'],
    }
    for name, values in definitions.items():
        postgresql.ENUM(*values, name=name, schema='gis_core').create(bind, checkfirst=True)
    op.create_table('intervention_metric_definition',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('key', sa.String(length=100), nullable=False),
    sa.Column('version', sa.String(length=50), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('source_system', sa.String(length=100), nullable=False),
    sa.Column('unit', sa.String(length=100), nullable=False),
    sa.Column('grain', sa.String(length=100), nullable=False),
    sa.Column('enabled', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('key', 'version', name='uq_intervention_metric_version'),
    schema='gis_core'
    )
    op.create_table('intervention_type_definition',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('key', sa.String(length=100), nullable=False),
    sa.Column('version', sa.String(length=50), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('family', _enum('intervention_family'), nullable=False),
    sa.Column('execution_mode', sa.String(length=50), nullable=False),
    sa.Column('autonomy_level', sa.String(length=50), nullable=False),
    sa.Column('reversible', sa.Boolean(), nullable=True),
    sa.Column('enabled', sa.Boolean(), nullable=False),
    sa.Column('schema_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('key', 'version', name='uq_intervention_type_version'),
    schema='gis_core'
    )
    op.create_table('intervention',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('site_id', sa.UUID(), nullable=False),
    sa.Column('primary_opportunity_id', sa.UUID(), nullable=False),
    sa.Column('analytical_entity_id', sa.UUID(), nullable=False),
    sa.Column('intervention_type_id', sa.UUID(), nullable=False),
    sa.Column('market_definition_id', sa.UUID(), nullable=True),
    sa.Column('market_definition_version', sa.Integer(), nullable=True),
    sa.Column('status', _enum('intervention_status'), nullable=False),
    sa.Column('feasibility', _enum('feasibility_state'), nullable=False),
    sa.Column('measurement_readiness', _enum('measurement_readiness'), nullable=False),
    sa.Column('title', sa.Text(), nullable=False),
    sa.Column('parameters_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('constraints_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('risk_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('effort', sa.String(length=10), nullable=True),
    sa.Column('estimated_cost', sa.Numeric(precision=20, scale=4), nullable=True),
    sa.Column('actual_cost', sa.Numeric(precision=20, scale=4), nullable=True),
    sa.Column('proposed_by', sa.String(length=255), nullable=True),
    sa.Column('identity_hash', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['analytical_entity_id'], ['gis_core.analytical_entity.id'], ),
    sa.ForeignKeyConstraint(['intervention_type_id'], ['gis_core.intervention_type_definition.id'], ),
    sa.ForeignKeyConstraint(['market_definition_id'], ['gis_core.market_definition.id'], ),
    sa.ForeignKeyConstraint(['primary_opportunity_id'], ['gis_core.opportunity.id'], ),
    sa.ForeignKeyConstraint(['tenant_id', 'site_id'], ['gis_core.site.tenant_id', 'gis_core.site.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('identity_hash', name='uq_intervention_identity'),
    schema='gis_core'
    )
    op.create_index('ix_intervention_scope', 'intervention', ['tenant_id', 'site_id', 'status'], unique=False, schema='gis_core')
    op.create_table('intervention_execution',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('intervention_id', sa.UUID(), nullable=False),
    sa.Column('planned_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('actual_started_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('actual_completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('executor_type', sa.String(length=50), nullable=False),
    sa.Column('status', sa.String(length=50), nullable=False),
    sa.Column('actual_parameters_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('artifact_reference', sa.Text(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['intervention_id'], ['gis_core.intervention.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    schema='gis_core'
    )
    op.create_index('ix_intervention_execution_history', 'intervention_execution', ['intervention_id', 'actual_started_at'], unique=False, schema='gis_core')
    op.create_table('intervention_hypothesis',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('intervention_id', sa.UUID(), nullable=False),
    sa.Column('target_metric_key', sa.String(length=100), nullable=False),
    sa.Column('expected_direction', _enum('expected_direction'), nullable=False),
    sa.Column('target_entity_id', sa.UUID(), nullable=False),
    sa.Column('rationale', sa.Text(), nullable=False),
    sa.Column('expected_magnitude', sa.Numeric(precision=20, scale=8), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['intervention_id'], ['gis_core.intervention.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['target_entity_id'], ['gis_core.analytical_entity.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('intervention_id', name='uq_intervention_hypothesis'),
    schema='gis_core'
    )
    op.create_table('intervention_lifecycle_event',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('intervention_id', sa.UUID(), nullable=False),
    sa.Column('from_status', _enum('intervention_status'), nullable=True),
    sa.Column('to_status', _enum('intervention_status'), nullable=False),
    sa.Column('actor', sa.String(length=255), nullable=True),
    sa.Column('reason', sa.Text(), nullable=True),
    sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['intervention_id'], ['gis_core.intervention.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    schema='gis_core'
    )
    op.create_index('ix_intervention_lifecycle_history', 'intervention_lifecycle_event', ['intervention_id', 'occurred_at'], unique=False, schema='gis_core')
    op.create_table('measurement_contract',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('intervention_id', sa.UUID(), nullable=False),
    sa.Column('version', sa.String(length=50), nullable=False),
    sa.Column('baseline_strategy', sa.String(length=50), nullable=False),
    sa.Column('baseline_start', sa.DateTime(timezone=True), nullable=False),
    sa.Column('baseline_end', sa.DateTime(timezone=True), nullable=False),
    sa.Column('measurement_start', sa.DateTime(timezone=True), nullable=False),
    sa.Column('measurement_end', sa.DateTime(timezone=True), nullable=False),
    sa.Column('washout_days', sa.Integer(), nullable=False),
    sa.Column('comparison_method', sa.String(length=50), nullable=False),
    sa.Column('minimum_evidence', _enum('demand_evidence_strength'), nullable=False),
    sa.Column('freshness_days', sa.Integer(), nullable=False),
    sa.Column('exclusions_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('method_version', sa.String(length=50), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['intervention_id'], ['gis_core.intervention.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('intervention_id', 'version', name='uq_measurement_contract_version'),
    schema='gis_core'
    )
    op.create_table('experiment',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('site_id', sa.UUID(), nullable=False),
    sa.Column('intervention_id', sa.UUID(), nullable=False),
    sa.Column('measurement_contract_id', sa.UUID(), nullable=False),
    sa.Column('experiment_type', _enum('experiment_type'), nullable=False),
    sa.Column('status', _enum('experiment_status'), nullable=False),
    sa.Column('method_version', sa.String(length=50), nullable=False),
    sa.Column('invalidation_reason', sa.String(length=100), nullable=True),
    sa.Column('planned_sample_size', sa.Integer(), nullable=True),
    sa.Column('observed_sample_size', sa.Integer(), nullable=True),
    sa.Column('contamination_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['intervention_id'], ['gis_core.intervention.id'], ),
    sa.ForeignKeyConstraint(['measurement_contract_id'], ['gis_core.measurement_contract.id'], ),
    sa.ForeignKeyConstraint(['tenant_id', 'site_id'], ['gis_core.site.tenant_id', 'gis_core.site.id'], ),
    sa.PrimaryKeyConstraint('id'),
    schema='gis_core'
    )
    op.create_index('ix_experiment_scope', 'experiment', ['tenant_id', 'site_id', 'status'], unique=False, schema='gis_core')
    op.create_table('intervention_outcome',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('intervention_id', sa.UUID(), nullable=False),
    sa.Column('measurement_contract_id', sa.UUID(), nullable=False),
    sa.Column('state', _enum('outcome_state'), nullable=False),
    sa.Column('expectation_result', sa.String(length=50), nullable=False),
    sa.Column('baseline_value', sa.Numeric(precision=20, scale=8), nullable=True),
    sa.Column('post_value', sa.Numeric(precision=20, scale=8), nullable=True),
    sa.Column('absolute_change', sa.Numeric(precision=20, scale=8), nullable=True),
    sa.Column('relative_change', sa.Numeric(precision=20, scale=8), nullable=True),
    sa.Column('evidence_sufficiency', _enum('demand_evidence_strength'), nullable=False),
    sa.Column('completeness', sa.String(length=50), nullable=False),
    sa.Column('causal_attribution', sa.Boolean(), nullable=False),
    sa.Column('limitations_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('identity_hash', sa.String(length=64), nullable=False),
    sa.Column('method_version', sa.String(length=50), nullable=False),
    sa.Column('evaluated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['intervention_id'], ['gis_core.intervention.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['measurement_contract_id'], ['gis_core.measurement_contract.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('identity_hash', name='uq_intervention_outcome_identity'),
    schema='gis_core'
    )
    op.create_index('ix_intervention_outcome_history', 'intervention_outcome', ['intervention_id', 'evaluated_at'], unique=False, schema='gis_core')
    op.create_table('measurement_metric',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('measurement_contract_id', sa.UUID(), nullable=False),
    sa.Column('metric_definition_id', sa.UUID(), nullable=False),
    sa.Column('role', _enum('metric_role'), nullable=False),
    sa.Column('expected_direction', _enum('expected_direction'), nullable=False),
    sa.ForeignKeyConstraint(['measurement_contract_id'], ['gis_core.measurement_contract.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['metric_definition_id'], ['gis_core.intervention_metric_definition.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('measurement_contract_id', 'metric_definition_id', 'role', name='uq_measurement_metric_role'),
    schema='gis_core'
    )


def downgrade() -> None:
    op.drop_table('measurement_metric', schema='gis_core')
    op.drop_index('ix_intervention_outcome_history', table_name='intervention_outcome', schema='gis_core')
    op.drop_table('intervention_outcome', schema='gis_core')
    op.drop_index('ix_experiment_scope', table_name='experiment', schema='gis_core')
    op.drop_table('experiment', schema='gis_core')
    op.drop_table('measurement_contract', schema='gis_core')
    op.drop_index('ix_intervention_lifecycle_history', table_name='intervention_lifecycle_event', schema='gis_core')
    op.drop_table('intervention_lifecycle_event', schema='gis_core')
    op.drop_table('intervention_hypothesis', schema='gis_core')
    op.drop_index('ix_intervention_execution_history', table_name='intervention_execution', schema='gis_core')
    op.drop_table('intervention_execution', schema='gis_core')
    op.drop_index('ix_intervention_scope', table_name='intervention', schema='gis_core')
    op.drop_table('intervention', schema='gis_core')
    op.drop_table('intervention_type_definition', schema='gis_core')
    op.drop_table('intervention_metric_definition', schema='gis_core')
    bind = op.get_bind()
    for name in ('metric_role', 'outcome_state', 'experiment_status', 'experiment_type', 'expected_direction', 'measurement_readiness', 'feasibility_state', 'intervention_status', 'intervention_family'):
        postgresql.ENUM(name=name, schema='gis_core').drop(bind, checkfirst=True)
