select
  tenant_id, site_id, observed_date as date, ranking_domain,
  count(distinct normalized_keyword) as keyword_footprint,
  sum(coalesce(search_volume, 0) / nullif(position, 0)) as search_volume_weighted_visibility,
  sum(case when position <= 10 then 1 else 0 end) as top_10_keywords,
  sum(case when position <= 3 then 1 else 0 end) as top_3_keywords
from {{ ref('stg_external_keyword_rankings') }}
group by 1, 2, 3, 4
