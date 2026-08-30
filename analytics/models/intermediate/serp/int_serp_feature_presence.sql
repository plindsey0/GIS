select o.tenant_id, o.site_id, o.observed_date, o.normalized_query, o.device,
  r.feature_type, count(*) as feature_count, min(r.rank_absolute) as first_position
from {{ ref('stg_serp_observations') }} o
join {{ ref('stg_serp_results') }} r using (observation_id)
group by 1,2,3,4,5,6
