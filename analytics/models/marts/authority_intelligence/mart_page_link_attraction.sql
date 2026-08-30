select tenant_id, site_id, provider, ownership, target_domain, target_url,
       min(observed_date) as first_observed_date, max(observed_date) as last_observed_date,
       count(*) as observed_backlink_rows, count(distinct source_domain) as observed_referring_domains,
       count(*) filter (where link_state='OBSERVED_NEW') as explicitly_new_links,
       count(*) filter (where link_state='OBSERVED_LOST') as explicitly_lost_links
from {{ ref('stg_backlink_observations') }}
group by 1,2,3,4,5,6
