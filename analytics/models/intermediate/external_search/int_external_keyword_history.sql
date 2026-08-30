select
    rankings.*,
    min(observed_date) over (
        partition by tenant_id, site_id, target_domain, normalized_keyword, ranking_domain
    ) as first_observed_date,
    max(observed_date) over (
        partition by tenant_id, site_id, target_domain, normalized_keyword, ranking_domain
    ) as last_observed_date,
    case
        when prior_position is null then 'NEW'
        when position < prior_position then 'GAINED'
        when position > prior_position then 'LOST_GROUND'
        else 'UNCHANGED'
    end as movement
from {{ ref('stg_external_keyword_rankings') }} rankings
