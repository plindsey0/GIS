with pipelines as (
  select id, paid_provider from {{ source('gis_core', 'pipeline_definition') }}
), observed as (
  select c.tenant_id, c.site_id, date_trunc('month', c.date)::date as month, c.currency,
         sum(c.actual_provider_cost) as observed_provider_cost,
         count(*) as ledger_rows
  from {{ ref('mart_provider_cost_daily') }} c group by 1,2,3,4
), configured as (
  select s.tenant_id, s.site_id, count(*) filter (where p.paid_provider) as paid_pipeline_count
  from {{ source('gis_core', 'schedule_definition') }} s join pipelines p on p.id=s.pipeline_id group by 1,2
), scopes as (
  select tenant_id, id as site_id from {{ source('gis_core', 'site') }}
)
select s.tenant_id, s.site_id, o.month, coalesce(o.currency,'USD') as currency,
       o.observed_provider_cost, coalesce(o.ledger_rows,0) as ledger_rows,
       coalesce(c.paid_pipeline_count,0) as paid_pipeline_count,
       case when o.ledger_rows > 0 then 'OBSERVED' else 'UNKNOWN' end as cost_semantics
from scopes s left join observed o using (tenant_id,site_id)
left join configured c using (tenant_id,site_id)
