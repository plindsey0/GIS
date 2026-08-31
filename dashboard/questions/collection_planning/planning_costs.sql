select capability_key, target_type, priority_tier, known_monthly_cost,
       unknown_cost_item_count, currency, cost_semantics
from gis_analytics.mart_collection_cost_forecast where 1=1
[[and tenant_id::text={{tenant_id}}]] [[and site_id::text={{site_id}}]]
[[and current_date >= {{start_date}}]] [[and current_date <= {{end_date}}]]
order by known_monthly_cost desc nulls last, capability_key
