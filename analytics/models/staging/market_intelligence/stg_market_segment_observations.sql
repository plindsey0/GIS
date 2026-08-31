select s.id as segment_observation_id, o.tenant_id, o.site_id,
       o.market_definition_id, o.market_definition_version, o.effective_date,
       s.market_observation_id, s.segment_type, s.segment_key, s.segment_label,
       s.query_count, s.participant_count, s.provider_reported_search_volume,
       s.observed_visibility_hhi, s.method_key, s.method_version, s.semantic_class
from {{ source('gis_raw', 'market_segment_observation') }} s
join {{ ref('stg_market_observations') }} o on o.market_observation_id=s.market_observation_id
