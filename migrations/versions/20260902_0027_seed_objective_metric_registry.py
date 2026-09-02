"""seed governed objective metric registry

Revision ID: 20260902_0027
Revises: 20260902_0026
"""

from collections.abc import Sequence
from typing import Union

from alembic import op

revision: str = "20260902_0027"
down_revision: Union[str, None] = "20260902_0026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO gis_core.intervention_metric_definition
          (id, key, version, name, source_system, unit, grain, enabled,
           description, domain, directionality, aggregation, supported_scopes_json,
           currently_measurable, derived)
        VALUES
          (gen_random_uuid(), 'GSC_IMPRESSIONS', '1', 'GSC impressions', 'GSC', 'count', 'objective_window', true, 'Governed objective metric: GSC impressions.', 'SEARCH', 'HIGHER_IS_BETTER', 'SUM', '["SITE","QUERY","URL"]', true, false),
          (gen_random_uuid(), 'GSC_CLICKS', '1', 'GSC clicks', 'GSC', 'count', 'objective_window', true, 'Governed objective metric: GSC clicks.', 'SEARCH', 'HIGHER_IS_BETTER', 'SUM', '["SITE","QUERY","URL"]', true, false),
          (gen_random_uuid(), 'GSC_CTR', '1', 'Organic click-through rate', 'GSC', 'ratio', 'objective_window', true, 'Governed objective metric: organic CTR.', 'SEARCH', 'HIGHER_IS_BETTER', 'WEIGHTED_RATE', '["SITE","QUERY","URL"]', true, false),
          (gen_random_uuid(), 'GSC_POSITION', '1', 'GSC average position', 'GSC', 'rank', 'objective_window', true, 'Lower numerical rank is better.', 'SEARCH', 'LOWER_IS_BETTER', 'WEIGHTED_AVERAGE', '["QUERY","URL"]', true, false),
          (gen_random_uuid(), 'GA4_SESSIONS', '1', 'GA4 sessions', 'GA4', 'count', 'objective_window', true, 'Governed objective metric: GA4 sessions.', 'TRAFFIC', 'HIGHER_IS_BETTER', 'SUM', '["SITE","CHANNEL","URL"]', true, false),
          (gen_random_uuid(), 'CRUX_LCP', '1', 'Largest Contentful Paint', 'CRUX', 'milliseconds', 'objective_window', true, 'Requires authoritative CrUX field data; Lighthouse lab data is not substituted.', 'EXPERIENCE', 'LOWER_IS_BETTER', 'P75', '["SITE","URL"]', false, false)
        ON CONFLICT (key, version) DO UPDATE SET
          description = EXCLUDED.description,
          domain = EXCLUDED.domain,
          directionality = EXCLUDED.directionality,
          aggregation = EXCLUDED.aggregation,
          supported_scopes_json = EXCLUDED.supported_scopes_json,
          currently_measurable = EXCLUDED.currently_measurable,
          derived = EXCLUDED.derived
    """)


def downgrade() -> None:
    # Registry definitions are harmless shared metadata and may have been adopted by
    # intervention contracts after upgrade. Preserve them rather than deleting rows.
    pass
