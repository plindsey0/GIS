select
    tenant_id, site_id, observed_date as date, ranking_domain, normalized_url,
    max(ranking_url) as ranking_url,
    count(distinct normalized_keyword) as ranking_keyword_count,
    min(position) as best_position,
    sum(coalesce(estimated_traffic, 0)) as provider_estimated_traffic
from {{ ref('stg_external_keyword_rankings') }}
where normalized_url <> ''
group by 1, 2, 3, 4, 5
