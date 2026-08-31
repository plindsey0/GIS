select m.id as metric_observation_id, o.tenant_id, o.site_id,
       o.market_definition_id, o.market_definition_version, o.effective_date,
       m.market_observation_id, m.metric_definition_id, m.metric_key,
       m.metric_value, m.unit, m.provider, m.method_key, m.method_version,
       m.semantic_class, m.metadata
from {{ source('gis_raw', 'market_metric_observation') }} m
join {{ ref('stg_market_observations') }} o on o.market_observation_id=m.market_observation_id
