with coverage as (
  select tenant_id, site_id, bool_or(first_party_data_present) as first_party_available
  from gis_analytics.mart_data_reconciliation
  where 1=1 [[and tenant_id::text = {{tenant_id}}]] [[and site_id::text = {{site_id}}]]
    [[and date >= {{start_date}}]] [[and date <= {{end_date}}]] group by 1,2
), performance as (
  select * from gis_analytics.mart_calculator_performance
  where 1=1 [[and tenant_id::text = {{tenant_id}}]] [[and site_id::text = {{site_id}}]]
    [[and date >= {{start_date}}]] [[and date <= {{end_date}}]]
)
select c.tenant_id, c.site_id, p.date, p.calculator_type, p.calculator_views,
  p.calculator_starts, p.calculator_completions, p.start_to_complete_rate as completion_rate,
  p.cta_clicks, p.lead_form_completions, p.conversions,
  case when c.first_party_available then 'AVAILABLE' else 'FIRST_PARTY_TELEMETRY_NOT_YET_AVAILABLE' end as telemetry_status
from coverage c left join performance p using (tenant_id, site_id)
order by p.date desc, p.calculator_starts desc
