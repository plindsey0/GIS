"""add governed owned-surface observation details"""

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
RAW_SCHEMA = "gis_raw"


def upgrade() -> None:
    op.create_table(
        "owned_surface_observation_detail",
        sa.Column("observation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("collection_target_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("previous_observation_id", postgresql.UUID(as_uuid=True)),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("method_version", sa.String(100), nullable=False),
        sa.Column("retrieval_state", sa.String(50), nullable=False),
        sa.Column("render_state", sa.String(50), nullable=False),
        sa.Column("canonical_assessment", sa.String(50), nullable=False),
        sa.Column("indexability_assessment", sa.String(50), nullable=False),
        sa.Column("raw_response_fingerprint", sa.String(64), nullable=False),
        sa.Column("normalized_content_fingerprint", sa.String(64), nullable=False),
        sa.Column("structure_fingerprint", sa.String(64), nullable=False),
        sa.Column("metadata_fingerprint", sa.String(64), nullable=False),
        sa.Column("change_classification", sa.String(150), nullable=False),
        sa.Column("visible_text_preview", sa.Text(), nullable=False),
        sa.Column("controls_json", postgresql.JSONB(), nullable=False),
        sa.Column("images_json", postgresql.JSONB(), nullable=False),
        sa.Column("landmarks_json", postgresql.JSONB(), nullable=False),
        sa.Column("instrumentation_json", postgresql.JSONB(), nullable=False),
        sa.Column("quality_state", sa.String(50), nullable=False),
        sa.Column("limitations_json", postgresql.JSONB(), nullable=False),
        sa.Column("reassessment_ready", sa.Boolean(), nullable=False),
        sa.Column("evidence_package_id", postgresql.UUID(as_uuid=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["observation_id"],
            [f"{RAW_SCHEMA}.competitive_content_observation.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["previous_observation_id"],
            [f"{RAW_SCHEMA}.competitive_content_observation.id"],
        ),
        sa.ForeignKeyConstraint(
            ["collection_target_id"], [f"{SCHEMA}.collection_target.id"]
        ),
        sa.ForeignKeyConstraint(
            ["evidence_package_id"], [f"{SCHEMA}.evidence_package.id"]
        ),
        sa.PrimaryKeyConstraint("observation_id"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_owned_surface_detail_site_time",
        "owned_surface_observation_detail",
        ["tenant_id", "site_id", "observed_at"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_owned_surface_detail_target",
        "owned_surface_observation_detail",
        ["collection_target_id", "observed_at"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("owned_surface_observation_detail", schema=SCHEMA)
