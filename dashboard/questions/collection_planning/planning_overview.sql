select market_definition_id, market_definition_version, priority_tier, effective_status,
       target_count, average_priority_score
from gis_analytics.mart_collection_priority_distribution where 1=1
[[and tenant_id::text={{tenant_id}}]] [[and site_id::text={{site_id}}]]
[[and current_date >= {{start_date}}]] [[and current_date <= {{end_date}}]]
order by priority_tier, effective_status
