select
  title as "Observed condition",
  initcap(replace(family, '_', ' ')) as "Family",
  initcap(replace(status, '_', ' ')) as "Status",
  initcap(replace(priority, '_', ' ')) as "Priority",
  initcap(replace(evidence_sufficiency, '_', ' ')) as "Evidence support",
  period_end as "Evidence through",
  limitations_json as "Limitations"
from gis_analytics.mart_opportunity_current
where tenant_id::text = {{tenant_id}}
  and site_id::text = {{site_id}}
  and detected_at::date >= {{start_date}}
  and detected_at::date <= {{end_date}}
order by case priority when 'CRITICAL' then 1 when 'HIGH' then 2 when 'MEDIUM' then 3 when 'LOW' then 4 else 5 end,
         detected_at desc
