with gsc as (
  select tenant_id, site_id, observed_date, normalized_query,
    sum(impressions) as impressions, sum(clicks) as clicks,
    sum(position * impressions) / nullif(sum(impressions), 0) as gsc_position
  from {{ ref('stg_gsc_search_observations') }}
  where query is not null
  group by 1,2,3,4
), owned_page as (
  select o.tenant_id, o.site_id, o.observed_date, o.normalized_query,
    r.normalized_url, r.rank_absolute,
    row_number() over (partition by o.observation_id order by r.rank_absolute) as selection_order
  from {{ ref('stg_serp_observations') }} o
  join {{ ref('stg_serp_results') }} r using (observation_id)
  where r.ownership = 'OWN_SITE' and r.normalized_url is not null
)
select s.*, g.impressions, g.clicks, g.gsc_position, p.normalized_url as observed_page,
  e.measurement_type, e.scope as experience_scope, e.form_factor,
  e.availability as experience_availability, e.lcp, e.inp, e.cls,
  e.lcp_status, e.inp_status, e.cls_status
from {{ ref('mart_serp_query_daily') }} s
left join gsc g on g.tenant_id = s.tenant_id and g.site_id = s.site_id
  and g.observed_date = s.observed_date and g.normalized_query = s.normalized_query
left join owned_page p on p.tenant_id = s.tenant_id and p.site_id = s.site_id
  and p.observed_date = s.observed_date and p.normalized_query = s.normalized_query
  and p.selection_order = 1
left join {{ ref('mart_page_experience') }} e on e.tenant_id = s.tenant_id
  and e.site_id = s.site_id and e.period_end = s.observed_date
  and e.normalized_target = p.normalized_url
