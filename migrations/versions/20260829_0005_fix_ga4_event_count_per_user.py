"""Correct the GA4 event-count-per-user metric name.

Revision ID: 20260829_0005
Revises: 20260829_0004
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260829_0005"
down_revision: str | None = "20260829_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "gis_raw"
TABLE = "ga4_event_observation"
OLD_COLUMN = "event_count_per_active_user"
NEW_COLUMN = "event_count_per_user"


def upgrade() -> None:
    op.drop_constraint(
        "ck_ga4_event_event_count_per_active_user_nonnegative",
        TABLE,
        schema=SCHEMA,
        type_="check",
    )
    op.alter_column(TABLE, OLD_COLUMN, new_column_name=NEW_COLUMN, schema=SCHEMA)
    op.create_check_constraint(
        "ck_ga4_event_event_count_per_user_nonnegative",
        TABLE,
        f"{NEW_COLUMN} >= 0",
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_ga4_event_event_count_per_user_nonnegative",
        TABLE,
        schema=SCHEMA,
        type_="check",
    )
    op.alter_column(TABLE, NEW_COLUMN, new_column_name=OLD_COLUMN, schema=SCHEMA)
    op.create_check_constraint(
        "ck_ga4_event_event_count_per_active_user_nonnegative",
        TABLE,
        f"{OLD_COLUMN} >= 0",
        schema=SCHEMA,
    )
