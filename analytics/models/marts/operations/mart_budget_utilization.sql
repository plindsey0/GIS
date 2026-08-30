with daily as (
  select tenant_id, site_id, data_source_id, pipeline_id, schedule_id, currency,
         sum(amount) filter (where occurred_at >= date_trunc('day', current_timestamp)) as daily_spend,
         sum(amount) filter (where occurred_at >= date_trunc('month', current_timestamp)) as monthly_spend
  from {{ source('gis_core', 'cost_ledger_entry') }} group by 1,2,3,4,5,6
)
select b.id as budget_id, b.tenant_id, b.site_id, b.data_source_id, b.pipeline_id,
       b.schedule_id, b.currency, b.daily_limit, b.monthly_limit, b.per_run_limit,
       coalesce(d.daily_spend,0) as daily_spend,
       coalesce(d.monthly_spend,0) as monthly_spend,
       coalesce(d.daily_spend,0)/nullif(b.daily_limit,0) as daily_utilization,
       coalesce(d.monthly_spend,0)/nullif(b.monthly_limit,0) as monthly_utilization
from {{ source('gis_core', 'cost_budget') }} b
left join daily d on d.tenant_id=b.tenant_id
 and d.site_id is not distinct from b.site_id
 and d.data_source_id is not distinct from b.data_source_id
 and d.pipeline_id is not distinct from b.pipeline_id
 and d.schedule_id is not distinct from b.schedule_id
 and d.currency=b.currency
where b.active
