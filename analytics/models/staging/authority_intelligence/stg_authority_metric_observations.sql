select m.id as authority_metric_observation_id, m.authority_observation_id,
       o.tenant_id, o.site_id, o.provider, o.target_type, o.target_domain,
       o.target_url, o.ownership, o.observed_date, o.observed_at,
       m.metric_provider, m.metric_key, m.metric_name, m.metric_value,
       m.scale_min, m.scale_max, m.unit, m.methodology_version,
       m.semantic_class, m.created_at
from {{ source('gis_raw', 'authority_metric_observation') }} m
join {{ ref('stg_authority_observations') }} o using (authority_observation_id)
