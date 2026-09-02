"""add conservative objective feasibility state

Revision ID: 20260902_0026
Revises: 20260902_0025
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260902_0026"
down_revision: Union[str, None] = "20260902_0025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    feasibility = postgresql.ENUM(
        "NOT_ASSESSED",
        "INSUFFICIENT_DATA",
        "PLAUSIBLE",
        "AGGRESSIVE",
        "EXTREMELY_AGGRESSIVE",
        "CURRENT_TRAJECTORY_INSUFFICIENT",
        "UNSUPPORTED_BY_CURRENT_EVIDENCE",
        name="objective_feasibility",
        schema="gis_core",
        create_type=False,
    )
    feasibility.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "strategic_objective",
        sa.Column(
            "feasibility_state",
            feasibility,
            server_default="NOT_ASSESSED",
            nullable=False,
        ),
        schema="gis_core",
    )
    op.add_column(
        "strategic_objective",
        sa.Column("feasibility_reason", sa.Text()),
        schema="gis_core",
    )


def downgrade() -> None:
    op.drop_column("strategic_objective", "feasibility_reason", schema="gis_core")
    op.drop_column("strategic_objective", "feasibility_state", schema="gis_core")
    postgresql.ENUM(name="objective_feasibility", schema="gis_core", create_type=False).drop(
        op.get_bind(), checkfirst=True
    )
