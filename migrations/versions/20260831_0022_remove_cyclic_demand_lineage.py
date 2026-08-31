"""remove cyclic emerging-demand lineage

Revision ID: 20260831_0022
Revises: 20260831_0021
Create Date: 2026-08-31 19:20:00
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260831_0022"
down_revision: Union[str, None] = "20260831_0021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            DELETE FROM gis_core.data_asset_lineage AS edge
            USING gis_core.data_asset AS upstream, gis_core.data_asset AS downstream
            WHERE edge.upstream_asset_id = upstream.id
              AND edge.downstream_asset_id = downstream.id
              AND upstream.canonical_name = 'gis_core.collection_planning_decision'
              AND downstream.canonical_name = 'gis_raw.demand_observation'
            """
        )
    )


def downgrade() -> None:
    # The removed edge is invalid because it closes a feedback cycle. Do not restore it.
    pass
