select
    tenant_id, site_id, observed_date as date, ranking_domain,
    count(distinct normalized_keyword) as ranking_keyword_count,
    min(position) as best_position,
    sum(coalesce(estimated_traffic, 0)) as provider_estimated_traffic,
    sum(coalesce(search_volume, 0) / nullif(position, 0)) as search_volume_weighted_visibility
from {{ ref('stg_external_keyword_rankings') }}
group by 1, 2, 3, 4
