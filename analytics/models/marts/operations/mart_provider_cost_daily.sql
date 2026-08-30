select l.tenant_id, l.site_id, l.data_source_id, l.pipeline_id, l.schedule_id,
       l.occurred_at::date as date, l.currency,
       count(*) as charged_execution_count, sum(l.amount) as actual_provider_cost
from {{ source('gis_core', 'cost_ledger_entry') }} l
group by 1,2,3,4,5,6,7
