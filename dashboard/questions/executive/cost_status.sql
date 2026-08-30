select observed_provider_cost, cost_semantics
from gis_analytics.mart_executive_cost
where 1=1 [[and tenant_id::text={{tenant_id}}]] [[and site_id::text={{site_id}}]]
[[and month >= date_trunc('month', {{start_date}})::date]] [[and month <= {{end_date}}]]
order by month desc nulls last limit 1
