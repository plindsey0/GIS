select tenant_id, site_id, market_definition_id, market_definition_version,
       capability_key, evidence_product, currency, count(*) as target_count,
       sum(estimated_monthly_cost) as known_monthly_cost,
       count(*) filter (where estimated_monthly_cost is null) as unknown_cost_target_count
from {{ ref('mart_collection_plan_current') }} group by 1,2,3,4,5,6,7
