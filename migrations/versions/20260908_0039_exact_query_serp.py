"""add governed exact-query SERP snapshot details"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260908_0039"
down_revision: Union[str, None] = "20260908_0038"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "gis_core"
RAW_SCHEMA = "gis_raw"


def upgrade() -> None:
    op.create_table(
        "exact_query_serp_snapshot_detail",
        sa.Column("observation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("analytical_entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("collection_target_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("market_definition_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("previous_observation_id", postgresql.UUID(as_uuid=True)),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("method_version", sa.String(100), nullable=False),
        sa.Column("returned_depth", sa.Integer(), nullable=False),
        sa.Column("result_count", sa.Integer(), nullable=False),
        sa.Column("snapshot_hash", sa.String(64), nullable=False),
        sa.Column("change_classification", sa.String(50), nullable=False),
        sa.Column("owned_presence_state", sa.String(64), nullable=False),
        sa.Column("owned_best_position", sa.Integer()),
        sa.Column("summary_json", postgresql.JSONB(), nullable=False),
        sa.Column("comparison_json", postgresql.JSONB(), nullable=False),
        sa.Column("quality_state", sa.String(50), nullable=False),
        sa.Column("limitations_json", postgresql.JSONB(), nullable=False),
        sa.Column("reassessment_ready", sa.Boolean(), nullable=False),
        sa.Column("evidence_package_id", postgresql.UUID(as_uuid=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["observation_id"], [f"{RAW_SCHEMA}.serp_observation.id"],
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["previous_observation_id"],
                                [f"{RAW_SCHEMA}.serp_observation.id"]),
        sa.ForeignKeyConstraint(["analytical_entity_id"],
                                [f"{SCHEMA}.analytical_entity.id"]),
        sa.ForeignKeyConstraint(["collection_target_id"], [f"{SCHEMA}.collection_target.id"]),
        sa.ForeignKeyConstraint(["market_definition_id"], [f"{SCHEMA}.market_definition.id"]),
        sa.ForeignKeyConstraint(["evidence_package_id"], [f"{SCHEMA}.evidence_package.id"]),
        sa.PrimaryKeyConstraint("observation_id"),
        schema=SCHEMA,
    )
    op.create_index("ix_exact_serp_entity_time", "exact_query_serp_snapshot_detail",
                    ["analytical_entity_id", "observed_at"], schema=SCHEMA)
    op.create_index("ix_exact_serp_target_time", "exact_query_serp_snapshot_detail",
                    ["collection_target_id", "observed_at"], schema=SCHEMA)


def downgrade() -> None:
    op.drop_table("exact_query_serp_snapshot_detail", schema=SCHEMA)
