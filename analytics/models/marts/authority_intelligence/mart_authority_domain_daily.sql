with links as (
  select tenant_id, site_id, provider, target_domain, ownership, observed_date as date,
         count(*) as backlink_count, count(distinct source_domain) as referring_domain_count,
         count(distinct source_url) as referring_page_count,
         count(*) filter (where follow_state='FOLLOWED') as followed_backlink_count,
         count(*) filter (where follow_state='NOFOLLOW') as nofollow_backlink_count,
         count(*) filter (where link_state='OBSERVED_NEW') as new_backlink_count,
         count(*) filter (where link_state='OBSERVED_LOST') as lost_backlink_count
  from {{ ref('stg_backlink_observations') }} group by 1,2,3,4,5,6
), metrics as (
  select tenant_id, site_id, provider, target_domain, observed_date as date,
         jsonb_object_agg(metric_provider || ':' || metric_key, metric_value) as provider_metrics
  from {{ ref('stg_authority_metric_observations') }} where target_type='DOMAIN'
  group by 1,2,3,4,5
)
select l.*, l.new_backlink_count-l.lost_backlink_count as net_backlink_change,
       coalesce(m.provider_metrics, '{}'::jsonb) as provider_metrics
from links l left join metrics m using (tenant_id,site_id,provider,target_domain,date)
