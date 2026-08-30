select
    c.id as competitor_observation_id,
    o.tenant_id,
    o.site_id,
    o.observed_date,
    o.target_domain,
    o.country_code,
    o.location_code,
    o.language_code,
    c.competitor_domain,
    c.target_keyword_count,
    c.competitor_keyword_count,
    c.shared_keyword_count,
    c.provider_relevance,
    c.provider_estimated_traffic,
    c.provider_visibility,
    c.gis_competitive_strength,
    c.metric_semantics
from {{ source('gis_raw', 'external_competitor_observation') }} c
join {{ ref('stg_external_search_observations') }} o
  on o.observation_id = c.external_search_observation_id
