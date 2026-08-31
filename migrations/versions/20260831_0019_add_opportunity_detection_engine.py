"""add opportunity detection engine

Revision ID: 20260831_0019
Revises: 20260831_0018
Create Date: 2026-08-31 08:24:02.224938
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260831_0019"
down_revision: Union[str, None] = '20260831_0018'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    postgresql.ENUM('DEMAND', 'VISIBILITY', 'COMPETITIVE', 'CONTENT', 'AUTHORITY', 'EXPERIENCE', 'MARKET_STRUCTURE', 'INTELLIGENCE_GAP', name='opportunity_family', schema='gis_core').create(bind, checkfirst=True)
    postgresql.ENUM('DETECTED', 'ACTIVE', 'WATCHING', 'RESOLVED', 'EXPIRED', 'DISMISSED', 'SUPERSEDED', name='opportunity_status', schema='gis_core').create(bind, checkfirst=True)
    postgresql.ENUM('CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'WATCH', name='opportunity_priority', schema='gis_core').create(bind, checkfirst=True)
    opportunity_family = postgresql.ENUM(name='opportunity_family', schema='gis_core', create_type=False)
    opportunity_status = postgresql.ENUM(name='opportunity_status', schema='gis_core', create_type=False)
    opportunity_priority = postgresql.ENUM(name='opportunity_priority', schema='gis_core', create_type=False)
    demand_evidence_strength = postgresql.ENUM(name='demand_evidence_strength', schema='gis_core', create_type=False)
    op.create_table('opportunity_detector_policy',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('detector_key', sa.String(length=100), nullable=False),
    sa.Column('detector_version', sa.String(length=50), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('family', opportunity_family, nullable=False),
    sa.Column('opportunity_type', sa.String(length=100), nullable=False),
    sa.Column('evidence_contract_key', sa.String(length=100), nullable=False),
    sa.Column('enabled', sa.Boolean(), nullable=False),
    sa.Column('experimental', sa.Boolean(), nullable=False),
    sa.Column('policy_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('detector_key', 'detector_version', name='uq_opportunity_detector_version'),
    schema='gis_core'
    )
    op.create_table('opportunity',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('site_id', sa.UUID(), nullable=False),
    sa.Column('analytical_entity_id', sa.UUID(), nullable=False),
    sa.Column('market_definition_id', sa.UUID(), nullable=True),
    sa.Column('market_definition_version', sa.Integer(), nullable=True),
    sa.Column('detector_policy_id', sa.UUID(), nullable=False),
    sa.Column('family', opportunity_family, nullable=False),
    sa.Column('opportunity_type', sa.String(length=100), nullable=False),
    sa.Column('status', opportunity_status, nullable=False),
    sa.Column('computed_status', opportunity_status, nullable=False),
    sa.Column('priority', opportunity_priority, nullable=False),
    sa.Column('evidence_sufficiency', demand_evidence_strength, nullable=False),
    sa.Column('title', sa.Text(), nullable=False),
    sa.Column('condition_description', sa.Text(), nullable=False),
    sa.Column('detected_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('condition_first_observed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('period_start', sa.Date(), nullable=False),
    sa.Column('period_end', sa.Date(), nullable=False),
    sa.Column('identity_hash', sa.String(length=64), nullable=False),
    sa.Column('materiality_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('priority_components_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('limitations_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['analytical_entity_id'], ['gis_core.analytical_entity.id'], ),
    sa.ForeignKeyConstraint(['detector_policy_id'], ['gis_core.opportunity_detector_policy.id'], ),
    sa.ForeignKeyConstraint(['market_definition_id'], ['gis_core.market_definition.id'], ),
    sa.ForeignKeyConstraint(['tenant_id', 'site_id'], ['gis_core.site.tenant_id', 'gis_core.site.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('identity_hash', name='uq_opportunity_identity'),
    schema='gis_core'
    )
    op.create_index('ix_opportunity_scope', 'opportunity', ['tenant_id', 'site_id', 'status', 'priority'], unique=False, schema='gis_core')
    op.create_table('opportunity_evaluation',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('opportunity_id', sa.UUID(), nullable=False),
    sa.Column('evaluated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('computed_status', opportunity_status, nullable=False),
    sa.Column('qualifies', sa.Boolean(), nullable=False),
    sa.Column('evaluation_hash', sa.String(length=64), nullable=False),
    sa.Column('reasons_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('blockers_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('metrics_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['opportunity_id'], ['gis_core.opportunity.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('evaluation_hash', name='uq_opportunity_evaluation'),
    schema='gis_core'
    )
    op.create_index('ix_opportunity_evaluation_history', 'opportunity_evaluation', ['opportunity_id', 'evaluated_at'], unique=False, schema='gis_core')
    op.create_table('opportunity_override',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('opportunity_id', sa.UUID(), nullable=False),
    sa.Column('dismissed_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('dismissed_by', sa.String(length=255), nullable=True),
    sa.Column('reason', sa.Text(), nullable=False),
    sa.Column('category', sa.String(length=100), nullable=True),
    sa.Column('restored_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('restored_by', sa.String(length=255), nullable=True),
    sa.ForeignKeyConstraint(['opportunity_id'], ['gis_core.opportunity.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    schema='gis_core'
    )
    op.create_index('ix_opportunity_override_current', 'opportunity_override', ['opportunity_id', 'restored_at'], unique=False, schema='gis_core')
    op.create_table('opportunity_evidence',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('opportunity_evaluation_id', sa.UUID(), nullable=False),
    sa.Column('evidence_package_id', sa.UUID(), nullable=False),
    sa.Column('evidence_role', sa.String(length=100), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['evidence_package_id'], ['gis_core.evidence_package.id'], ),
    sa.ForeignKeyConstraint(['opportunity_evaluation_id'], ['gis_core.opportunity_evaluation.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('opportunity_evaluation_id', 'evidence_package_id', name='uq_opportunity_evidence'),
    schema='gis_core'
    )


def downgrade() -> None:
    op.drop_table('opportunity_evidence', schema='gis_core')
    op.drop_index('ix_opportunity_override_current', table_name='opportunity_override', schema='gis_core')
    op.drop_table('opportunity_override', schema='gis_core')
    op.drop_index('ix_opportunity_evaluation_history', table_name='opportunity_evaluation', schema='gis_core')
    op.drop_table('opportunity_evaluation', schema='gis_core')
    op.drop_index('ix_opportunity_scope', table_name='opportunity', schema='gis_core')
    op.drop_table('opportunity', schema='gis_core')
    op.drop_table('opportunity_detector_policy', schema='gis_core')
    bind = op.get_bind()
    postgresql.ENUM(name='opportunity_priority', schema='gis_core').drop(bind, checkfirst=True)
    postgresql.ENUM(name='opportunity_status', schema='gis_core').drop(bind, checkfirst=True)
    postgresql.ENUM(name='opportunity_family', schema='gis_core').drop(bind, checkfirst=True)
