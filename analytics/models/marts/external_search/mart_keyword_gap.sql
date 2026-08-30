with external as (
  select * from {{ ref('stg_external_keyword_rankings') }}
),
gsc as (
  select tenant_id, site_id, observed_date, normalized_query, sum(impressions) as gsc_impressions
  from {{ ref('stg_gsc_search_observations') }}
  group by 1, 2, 3, 4
),
controlled_serp as (
  select tenant_id, site_id, observed_date, normalized_query, count(*) as controlled_observations
  from {{ ref('stg_serp_observations') }}
  group by 1, 2, 3, 4
)
select
  e.tenant_id, e.site_id, e.observed_date as date, e.normalized_keyword, e.keyword,
  e.ranking_domain, e.position, e.search_volume,
  coalesce(g.gsc_impressions, 0) as gsc_impressions,
  coalesce(s.controlled_observations, 0) as controlled_serp_observations,
  (g.normalized_query is null) as externally_discovered_only
from external e
left join gsc g on g.tenant_id=e.tenant_id and g.site_id=e.site_id
  and g.observed_date=e.observed_date and g.normalized_query=e.normalized_keyword
left join controlled_serp s on s.tenant_id=e.tenant_id and s.site_id=e.site_id
 and s.observed_date=e.observed_date and s.normalized_query=e.normalized_keyword
