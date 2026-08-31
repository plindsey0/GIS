select target_type, normalized_identity as target, priority_tier, capability_key,
       blocker, rights_status, budget_decision, estimated_monthly_cost, currency
from gis_analytics.mart_collection_blockers where 1=1
[[and tenant_id::text={{tenant_id}}]] [[and site_id::text={{site_id}}]]
[[and current_date >= {{start_date}}]] [[and current_date <= {{end_date}}]]
order by priority_tier, blocker, target
