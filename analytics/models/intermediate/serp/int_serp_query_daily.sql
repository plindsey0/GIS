with observations as (
  select o.*, lag(o.observation_id) over (
    partition by o.tenant_id, o.site_id, o.tracked_query_id, o.device
    order by o.observed_at
  ) as prior_observation_id
  from {{ ref('stg_serp_observations') }} o
), aggregates as (
  select o.tenant_id, o.site_id, o.observation_id, o.prior_observation_id,
    o.tracked_query_id, o.observed_date, o.normalized_query, o.device,
    min(r.rank_absolute) filter (where r.ownership = 'OWN_SITE') as best_own_rank,
    count(*) filter (where r.ownership = 'OWN_SITE') as own_result_count,
    count(*) filter (where r.is_organic) as organic_result_count,
    count(*) filter (where r.is_paid) as paid_result_count,
    count(*) filter (where r.is_feature) as feature_count,
    count(distinct r.hostname) as domain_diversity
  from observations o join {{ ref('stg_serp_results') }} r using (observation_id)
  group by 1,2,3,4,5,6,7,8
), overlap as (
  select a.observation_id,
    count(*) filter (where prior.result_id is not null) as overlapping_urls,
    count(*) as current_urls
  from aggregates a
  join {{ ref('stg_serp_results') }} current using (observation_id)
  left join {{ ref('stg_serp_results') }} prior
    on prior.observation_id = a.prior_observation_id
   and prior.normalized_url = current.normalized_url
  where current.normalized_url is not null and current.rank_absolute <= 10
  group by 1
)
select a.*, case when a.prior_observation_id is null then null
  else 1 - (coalesce(o.overlapping_urls, 0)::numeric / nullif(o.current_urls, 0)) end as top_10_churn
from aggregates a left join overlap o using (observation_id)
