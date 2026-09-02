"""correct linked orchestration completion timestamps

Revision ID: 20260902_0024
Revises: 20260902_0023
Create Date: 2026-09-02 14:30:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260902_0024"
down_revision: str | None = "20260902_0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Use completed ingestion as the lower bound for successful orchestration completion."""
    op.execute(
        """
        UPDATE gis_core.execution_attempt AS attempt
        SET completed_at = ingestion.completed_at
        FROM gis_core.ingestion_run AS ingestion
        WHERE attempt.ingestion_run_id = ingestion.id
          AND attempt.status = 'SUCCEEDED'
          AND ingestion.completed_at IS NOT NULL
          AND (attempt.completed_at IS NULL OR attempt.completed_at < ingestion.completed_at)
        """
    )
    op.execute(
        """
        UPDATE gis_core.orchestration_run AS run
        SET completed_at = ingestion.completed_at
        FROM gis_core.ingestion_run AS ingestion
        WHERE run.ingestion_run_id = ingestion.id
          AND run.status = 'SUCCEEDED'
          AND ingestion.completed_at IS NOT NULL
          AND (run.completed_at IS NULL OR run.completed_at < ingestion.completed_at)
        """
    )
    op.execute(
        """
        UPDATE gis_core.orchestration_obligation AS obligation
        SET satisfied_at = ingestion.completed_at,
            updated_at = now()
        FROM gis_core.ingestion_run AS ingestion
        WHERE obligation.ingestion_run_id = ingestion.id
          AND obligation.status = 'SATISFIED'
          AND ingestion.completed_at IS NOT NULL
          AND (obligation.satisfied_at IS NULL OR obligation.satisfied_at < ingestion.completed_at)
        """
    )


def downgrade() -> None:
    # The previous timestamps were demonstrably earlier than their linked ingestion completion.
    # Restoring those inaccurate values would require fabricating history, so this correction is
    # intentionally irreversible while the schema migration itself remains downgrade-safe.
    pass
