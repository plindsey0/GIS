select tenant_id, site_id, provider, ownership, observed_date as date,
       target_domain, target_url, count(*) as backlink_count,
       count(distinct source_domain) as referring_domain_count,
       count(*) filter (where link_state='OBSERVED_NEW') as new_backlink_count,
       count(*) filter (where link_state='OBSERVED_LOST') as lost_backlink_count,
       count(*) filter (where follow_state='FOLLOWED') as followed_backlink_count,
       count(*) filter (where follow_state='NOFOLLOW') as nofollow_backlink_count
from {{ ref('stg_backlink_observations') }}
group by 1,2,3,4,5,6,7
