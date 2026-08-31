select p.id as participant_observation_id, o.tenant_id, o.site_id,
       o.market_definition_id, o.market_definition_version, o.effective_date,
       p.market_observation_id, p.domain, p.ownership, p.participant_class,
       p.query_count, p.ranking_page_count, p.serp_appearance_count,
       p.top_3_appearances, p.top_10_appearances, p.top_20_appearances,
       p.visibility_weight, p.visibility_share, p.volume_weighted_visibility,
       p.volume_weighted_visibility_share, p.query_overlap_rate,
       p.first_observed_at, p.last_observed_at, p.classification_method,
       p.classification_version, p.semantic_class, p.metadata
from {{ source('gis_raw', 'market_participant_observation') }} p
join {{ ref('stg_market_observations') }} o on o.market_observation_id=p.market_observation_id
