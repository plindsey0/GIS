select tenant_id, site_id, date, gsc_data_present, ga4_data_present, first_party_data_present,
  gsc_clicks, ga4_organic_sessions, first_party_organic_sessions,
  gsc_to_ga4_delta, gsc_to_ga4_ratio, ga4_to_first_party_delta,
  ga4_to_first_party_ratio, quality_status
from gis_analytics.mart_data_reconciliation
where 1=1 [[and tenant_id::text = {{tenant_id}}]] [[and site_id::text = {{site_id}}]]
  [[and date >= {{start_date}}]] [[and date <= {{end_date}}]]
order by date desc
