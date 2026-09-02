"""enforce one selected decomposition plan per objective

Revision ID: 20260902_0028
Revises: 20260902_0027
"""

from collections.abc import Sequence
from typing import Union

from alembic import op

revision: str = "20260902_0028"
down_revision: Union[str, None] = "20260902_0027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "uq_decomposition_plan_selected",
        "decomposition_plan",
        ["objective_id"],
        unique=True,
        schema="gis_core",
        postgresql_where="selected",
    )


def downgrade() -> None:
    op.drop_index(
        "uq_decomposition_plan_selected", table_name="decomposition_plan", schema="gis_core"
    )
