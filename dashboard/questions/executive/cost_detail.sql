select month, currency, observed_provider_cost, ledger_rows, paid_pipeline_count, cost_semantics
from gis_analytics.mart_executive_cost
where 1=1 [[and tenant_id::text={{tenant_id}}]] [[and site_id::text={{site_id}}]]
[[and (month is null or month >= date_trunc('month', {{start_date}})::date)]]
[[and (month is null or month <= {{end_date}})]] order by month desc nulls last
