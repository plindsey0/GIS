select p.tenant_id, p.site_id, p.date, p.normalized_path, p.gsc_impressions, p.gsc_clicks,
  p.gsc_ctr, p.gsc_avg_position, p.ga4_sessions, p.ga4_engaged_sessions,
  p.ga4_engagement_rate, p.ga4_key_events,
  case when r.first_party_data_present then p.first_party_sessions end as first_party_sessions,
  case when r.first_party_data_present then p.calculator_starts end as calculator_starts,
  case when r.first_party_data_present then p.calculator_completions end as calculator_completions,
  case when r.first_party_data_present then p.cta_clicks end as cta_clicks,
  case when r.first_party_data_present then p.conversions end as conversions,
  r.first_party_data_present
from gis_analytics.mart_page_daily p
left join gis_analytics.mart_data_reconciliation r using (tenant_id, site_id, date)
where 1=1 [[and p.tenant_id::text = {{tenant_id}}]] [[and p.site_id::text = {{site_id}}]]
  [[and p.date >= {{start_date}}]] [[and p.date <= {{end_date}}]]
  [[and p.normalized_path ilike '%' || {{page}} || '%']]
order by p.gsc_impressions desc, p.ga4_sessions desc
