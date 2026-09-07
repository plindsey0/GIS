"""add governed downstream reference lineage and proposal supersession"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260907_0035"
down_revision: Union[str, None] = "20260907_0034"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    j = postgresql.JSONB(astext_type=sa.Text())
    u = postgresql.UUID(as_uuid=True)
    op.add_column("recommendation", sa.Column("evidence_references_json", j, nullable=False, server_default="[]"), schema="gis_core")
    op.add_column("experiment_proposal", sa.Column("evidence_references_json", j, nullable=False, server_default="[]"), schema="gis_core")
    op.add_column("experiment_proposal", sa.Column("supersedes_proposal_id", u), schema="gis_core")
    op.add_column("experiment_proposal", sa.Column("replacement_proposal_id", u), schema="gis_core")
    op.create_foreign_key("fk_proposal_supersedes", "experiment_proposal", "experiment_proposal", ["supersedes_proposal_id"], ["id"], source_schema="gis_core", referent_schema="gis_core")
    op.create_foreign_key("fk_proposal_replacement", "experiment_proposal", "experiment_proposal", ["replacement_proposal_id"], ["id"], source_schema="gis_core", referent_schema="gis_core")

def downgrade() -> None:
    op.drop_constraint("fk_proposal_replacement", "experiment_proposal", schema="gis_core", type_="foreignkey")
    op.drop_constraint("fk_proposal_supersedes", "experiment_proposal", schema="gis_core", type_="foreignkey")
    op.drop_column("experiment_proposal", "replacement_proposal_id", schema="gis_core")
    op.drop_column("experiment_proposal", "supersedes_proposal_id", schema="gis_core")
    op.drop_column("experiment_proposal", "evidence_references_json", schema="gis_core")
    op.drop_column("recommendation", "evidence_references_json", schema="gis_core")
