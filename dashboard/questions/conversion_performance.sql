with coverage as (
  select tenant_id, site_id, bool_or(first_party_data_present) as first_party_available
  from gis_analytics.mart_data_reconciliation
  where 1=1 [[and tenant_id::text = {{tenant_id}}]] [[and site_id::text = {{site_id}}]]
    [[and date >= {{start_date}}]] [[and date <= {{end_date}}]] group by 1,2
), conversions as (
  select * from gis_analytics.mart_conversion_daily
  where 1=1 [[and tenant_id::text = {{tenant_id}}]] [[and site_id::text = {{site_id}}]]
    [[and date >= {{start_date}}]] [[and date <= {{end_date}}]]
)
select c.tenant_id, c.site_id, v.date, v.conversion_type, v.conversions,
  v.sessions_with_conversion, v.conversion_value, v.currency,
  case when c.first_party_available then 'AVAILABLE' else 'FIRST_PARTY_TELEMETRY_NOT_YET_AVAILABLE' end as telemetry_status
from coverage c left join conversions v using (tenant_id, site_id)
order by v.date desc, v.conversions desc
