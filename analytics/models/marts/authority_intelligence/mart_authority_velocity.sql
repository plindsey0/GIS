with daily as (
  select tenant_id, site_id, provider, target_domain, observed_date as date,
         count(*) filter (where link_state='OBSERVED_NEW') as new_links,
         count(*) filter (where link_state='OBSERVED_LOST') as lost_links,
         count(distinct source_domain) filter (where link_state='OBSERVED_NEW') as new_referring_domains,
         count(distinct source_domain) filter (where link_state='OBSERVED_LOST') as lost_referring_domains
  from {{ ref('stg_backlink_observations') }} group by 1,2,3,4,5
)
select *, new_links-lost_links as net_link_velocity,
       new_referring_domains-lost_referring_domains as net_referring_domain_velocity
from daily
