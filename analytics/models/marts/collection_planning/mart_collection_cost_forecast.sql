select tenant_id, site_id, market_definition_id, market_definition_version,
       capability_key, target_type, priority_tier, currency,
       count(*) as plan_item_count,
       sum(estimated_monthly_cost) as known_monthly_cost,
       count(*) filter (where estimated_monthly_cost is null) as unknown_cost_item_count,
       case when count(*) filter (where estimated_monthly_cost is null)>0
            then 'PARTIALLY_UNKNOWN' else 'KNOWN' end as cost_semantics
from {{ ref('mart_collection_plan_current') }}
group by 1,2,3,4,5,6,7,8
