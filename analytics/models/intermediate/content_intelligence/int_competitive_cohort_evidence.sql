select
  c.id as cohort_id, c.tenant_id, c.site_id, c.tracked_query_id, c.frozen_at,
  m.observation_id, m.rank_position, m.membership_source,
  p.normalized_url, p.domain, p.ownership_class, p.normalized_word_count,
  p.h1_count, p.h2_count, p.h3_count, p.table_count, p.form_count,
  p.internal_link_count, p.external_link_count
from {{ source('gis_core', 'competitive_content_cohort') }} c
join {{ source('gis_core', 'competitive_content_cohort_member') }} m on m.cohort_id=c.id
join {{ ref('stg_competitive_content_pages') }} p on p.observation_id=m.observation_id
