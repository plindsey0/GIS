select b.id as backlink_observation_id, b.authority_observation_id,
       o.tenant_id, o.site_id, o.provider, o.ownership, o.observed_date,
       o.observed_at, o.completeness, b.provider_record_id, b.link_identity,
       b.source_url, b.source_domain, b.target_url, b.target_domain,
       b.link_state, b.follow_state, b.sponsored, b.ugc, b.link_type,
       b.anchor_hash, b.anchor_classification, b.anchor_method,
       b.anchor_method_version, b.anchor_confidence, b.first_seen_at,
       b.last_seen_at, b.semantic_class, b.created_at
from {{ source('gis_raw', 'backlink_observation') }} b
join {{ ref('stg_authority_observations') }} o using (authority_observation_id)
