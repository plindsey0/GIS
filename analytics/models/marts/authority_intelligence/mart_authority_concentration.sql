with domain_counts as (
  select tenant_id, site_id, provider, target_domain, observed_date as date,
         source_domain, count(*)::numeric as link_count
  from {{ ref('stg_backlink_observations') }} group by 1,2,3,4,5,6
), totals as (
  select *, sum(link_count) over (partition by tenant_id,site_id,provider,target_domain,date) as total_links
  from domain_counts
)
select tenant_id,site_id,provider,target_domain,date,
       sum(power(link_count/nullif(total_links,0),2)) as referring_domain_hhi,
       1-sum(power(link_count/nullif(total_links,0),2)) as referring_domain_diversification,
       count(*) as referring_domain_count
from totals group by 1,2,3,4,5
