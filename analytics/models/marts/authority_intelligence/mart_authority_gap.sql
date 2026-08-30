with presence as (
  select tenant_id, site_id, provider, observed_date as date, referring_domain,
         bool_or(ownership='OWNED') as links_to_owned,
         count(distinct target_domain) filter (where ownership='COMPETITOR') as competitor_targets_linked
  from {{ ref('stg_referring_domain_observations') }}
  where ownership in ('OWNED','COMPETITOR') group by 1,2,3,4,5
)
select *, case when links_to_owned and competitor_targets_linked>0 then 'SHARED'
               when links_to_owned then 'OWNED_ONLY'
               else 'COMPETITOR_ONLY' end as observed_gap_class
from presence
