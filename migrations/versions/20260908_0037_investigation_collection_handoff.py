"""add governed investigation and collection requirement handoff"""
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


def _enum(name: str) -> postgresql.ENUM:
    return postgresql.ENUM(name=name, schema=SCHEMA, create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    proposal_type = postgresql.ENUM(
        "INVESTIGATION", "EXPERIMENT", name="proposal_artifact_type", schema=SCHEMA
    )
    capability = postgresql.ENUM(
        "OWNED_PAGE_CONTENT", "EXACT_QUERY_SERP", "UNSUPPORTED",
        name="collection_requirement_capability", schema=SCHEMA,
    )
    status = postgresql.ENUM(
        "REQUESTED", "BLOCKED", "CANDIDATE", "APPLIED", "COLLECTING", "SATISFIED",
        "FAILED", "UNSUPPORTED", "CANCELLED", name="collection_requirement_status", schema=SCHEMA,
    )
    reassessment = postgresql.ENUM(
        "NOT_REASSESSED", "SATISFIED", "STILL_INSUFFICIENT", "FAILED", "INCONCLUSIVE",
        name="evidence_reassessment_status", schema=SCHEMA,
    )
    for enum in (proposal_type, capability, status, reassessment):
        enum.create(bind, checkfirst=True)
    op.add_column(
        "experiment_proposal",
        sa.Column(
            "proposal_type", _enum("proposal_artifact_type"), nullable=False,
            server_default="EXPERIMENT"
        ),
        schema=SCHEMA,
    )
    uuid_type = postgresql.UUID(as_uuid=True)
    json_type = postgresql.JSONB(astext_type=sa.Text())
    op.create_table(
        "collection_requirement",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("tenant_id", uuid_type, nullable=False),
        sa.Column("site_id", uuid_type, nullable=False),
        sa.Column("proposal_id", uuid_type, nullable=False),
        sa.Column("recommendation_id", uuid_type, nullable=False),
        sa.Column("opportunity_id", uuid_type, nullable=False),
        sa.Column("analytical_entity_id", uuid_type, nullable=False),
        sa.Column("evidence_gap_id", uuid_type),
        sa.Column("gap_reference_id", uuid_type, nullable=False),
        sa.Column("gap_type", sa.String(100), nullable=False),
        sa.Column("capability", _enum("collection_requirement_capability"), nullable=False),
        sa.Column(
            "target_type",
            _enum("collection_target_type"),
            nullable=False,
        ),
        sa.Column("target_value", sa.Text(), nullable=False),
        sa.Column("normalized_target", sa.Text(), nullable=False),
        sa.Column("country_code", sa.String(2)),
        sa.Column("language_code", sa.String(16)),
        sa.Column("device", sa.String(32)),
        sa.Column("requested_characteristics_json", json_type, nullable=False),
        sa.Column("unsupported_characteristics_json", json_type, nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("rights_constraints_json", json_type, nullable=False),
        sa.Column("human_constraints_json", json_type, nullable=False),
        sa.Column(
            "priority",
            _enum("collection_priority_tier"),
            nullable=False,
        ),
        sa.Column(
            "freshness_expectation",
            _enum("collection_cadence"),
            nullable=False,
        ),
        sa.Column("status", _enum("collection_requirement_status"), nullable=False),
        sa.Column("blocker", sa.String(255)),
        sa.Column("cost_class", sa.String(32), nullable=False, server_default="UNKNOWN"),
        sa.Column("provider_key", sa.String(100)),
        sa.Column("collection_target_id", uuid_type),
        sa.Column("collection_plan_item_id", uuid_type),
        sa.Column("satisfying_evidence_package_id", uuid_type),
        sa.Column("reassessment_status", _enum("evidence_reassessment_status"), nullable=False),
        sa.Column("reassessed_at", sa.DateTime(timezone=True)),
        sa.Column("reassessment_notes", sa.Text()),
        sa.Column("intelligence_reassessment_eligible_at", sa.DateTime(timezone=True)),
        sa.Column("identity_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id", "site_id"], [f"{SCHEMA}.site.tenant_id", f"{SCHEMA}.site.id"]),
        sa.ForeignKeyConstraint(["proposal_id"], [f"{SCHEMA}.experiment_proposal.id"]),
        sa.ForeignKeyConstraint(["recommendation_id"], [f"{SCHEMA}.recommendation.id"]),
        sa.ForeignKeyConstraint(["opportunity_id"], [f"{SCHEMA}.opportunity.id"]),
        sa.ForeignKeyConstraint(["analytical_entity_id"], [f"{SCHEMA}.analytical_entity.id"]),
        sa.ForeignKeyConstraint(["evidence_gap_id"], [f"{SCHEMA}.evidence_gap.id"]),
        sa.ForeignKeyConstraint(["collection_target_id"], [f"{SCHEMA}.collection_target.id"]),
        sa.ForeignKeyConstraint(["collection_plan_item_id"], [f"{SCHEMA}.collection_plan_item.id"]),
        sa.ForeignKeyConstraint(["satisfying_evidence_package_id"], [f"{SCHEMA}.evidence_package.id"]),
        sa.UniqueConstraint("identity_hash", name="uq_collection_requirement_identity"),
        schema=SCHEMA,
    )
    op.create_index("ix_collection_requirement_scope", "collection_requirement", ["tenant_id", "site_id", "status"], schema=SCHEMA)
    op.create_index("ix_collection_requirement_proposal", "collection_requirement", ["proposal_id", "created_at"], schema=SCHEMA)
    op.create_index("ix_collection_requirement_target", "collection_requirement", ["collection_target_id"], schema=SCHEMA)


def downgrade() -> None:
    op.drop_table("collection_requirement", schema=SCHEMA)
    op.drop_column("experiment_proposal", "proposal_type", schema=SCHEMA)
    bind = op.get_bind()
    for name in (
        "evidence_reassessment_status", "collection_requirement_status",
        "collection_requirement_capability", "proposal_artifact_type",
    ):
        postgresql.ENUM(name=name, schema=SCHEMA).drop(bind, checkfirst=True)
