select o.tenant_id, o.site_id, o.observed_date, o.normalized_query, o.device,
  r.hostname, r.ownership, min(r.rank_absolute) as best_rank,
  count(*) filter (where r.is_organic) as organic_positions,
  count(*) as result_count
from {{ ref('stg_serp_observations') }} o
join {{ ref('stg_serp_results') }} r using (observation_id)
where r.hostname is not null
group by 1,2,3,4,5,6,7
