select case when bool_or(r.first_party_data_present) then sum(s.first_party_sessions) end
  as first_party_sessions
from gis_analytics.mart_site_daily s
left join gis_analytics.mart_data_reconciliation r using (tenant_id, site_id, date)
where 1=1 [[and s.tenant_id::text = {{tenant_id}}]] [[and s.site_id::text = {{site_id}}]]
  [[and s.date >= {{start_date}}]] [[and s.date <= {{end_date}}]]
