"""separate governed LLM request identity from immutable execution attempts"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260907_0036"
down_revision: Union[str, None] = "20260907_0035"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(
        "uq_llm_run_request_fingerprint", "llm_run", schema="gis_core", type_="unique"
    )
    op.add_column(
        "llm_run",
        sa.Column("attempt_number", sa.Integer(), nullable=False, server_default="1"),
        schema="gis_core",
    )
    op.add_column(
        "llm_run",
        sa.Column("retry_of_run_id", postgresql.UUID(as_uuid=True)),
        schema="gis_core",
    )
    op.create_foreign_key(
        "fk_llm_run_retry_of",
        "llm_run",
        "llm_run",
        ["retry_of_run_id"],
        ["id"],
        source_schema="gis_core",
        referent_schema="gis_core",
        ondelete="SET NULL",
    )
    op.create_unique_constraint(
        "uq_llm_run_fingerprint_attempt",
        "llm_run",
        ["request_fingerprint", "attempt_number"],
        schema="gis_core",
    )
    op.create_index(
        "ix_llm_run_request_fingerprint",
        "llm_run",
        ["request_fingerprint"],
        schema="gis_core",
    )


def downgrade() -> None:
    op.execute(sa.text("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM gis_core.llm_run
                GROUP BY request_fingerprint HAVING count(*) > 1
            ) THEN
                RAISE EXCEPTION
                    'Cannot downgrade: governed LLM retry history contains duplicate fingerprints';
            END IF;
        END $$
    """))
    op.drop_index("ix_llm_run_request_fingerprint", table_name="llm_run", schema="gis_core")
    op.drop_constraint(
        "uq_llm_run_fingerprint_attempt", "llm_run", schema="gis_core", type_="unique"
    )
    op.drop_constraint(
        "fk_llm_run_retry_of", "llm_run", schema="gis_core", type_="foreignkey"
    )
    op.drop_column("llm_run", "retry_of_run_id", schema="gis_core")
    op.drop_column("llm_run", "attempt_number", schema="gis_core")
    op.create_unique_constraint(
        "uq_llm_run_request_fingerprint",
        "llm_run",
        ["request_fingerprint"],
        schema="gis_core",
    )
