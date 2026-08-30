select tenant_id, site_id, provider, observed_date as date, referring_domain,
       target_domain, ownership, backlink_count, followed_count, nofollow_count,
       link_state, first_seen_at, last_seen_at, semantic_class
from {{ ref('stg_referring_domain_observations') }}
