select
    tenant_id, site_id, observed_date as date, target_domain, ranking_domain,
    normalized_keyword, keyword, normalized_url, ranking_url, position, prior_position,
    search_volume, cpc, paid_competition, competition_index, search_intent,
    keyword_difficulty, estimated_traffic, estimated_traffic_share,
    first_observed_date, last_observed_date, movement
from {{ ref('int_external_keyword_history') }}
