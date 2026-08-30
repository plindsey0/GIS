select r.id as referring_domain_observation_id, r.authority_observation_id,
       o.tenant_id, o.site_id, o.provider, o.ownership, o.observed_date,
       o.observed_at, o.completeness, r.referring_domain, r.target_domain,
       r.backlink_count, r.followed_count, r.nofollow_count, r.first_seen_at,
       r.last_seen_at, r.link_state, r.semantic_class, r.created_at
from {{ source('gis_raw', 'referring_domain_observation') }} r
join {{ ref('stg_authority_observations') }} o using (authority_observation_id)
