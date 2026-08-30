select o.tenant_id, o.site_id, o.domain, o.normalized_url, o.ownership_class,
       o.observation_scope, o.observed_at, o.collection_status,
       d.id as detection_id, d.observation_id, d.technology_id,
       t.slug as technology_slug, t.name as technology_name, t.vendor,
       t.category, d.provider_technology_name, d.provider_category,
       d.detected_version, d.provider_first_seen_at, d.provider_last_seen_at,
       d.presence_status, d.detection_scope, d.confidence, d.semantic_class,
       d.detection_method, d.metadata
from {{ source('gis_raw', 'technology_detection') }} d
join {{ ref('stg_technology_observations') }} o on o.observation_id=d.observation_id
join {{ source('gis_core', 'technology') }} t on t.id=d.technology_id
