select tenant_id, site_id, date, gis_channel, provider_channel, source, medium,
  sessions, active_users, new_users, engaged_sessions, engagement_rate, key_events,
  first_party_sessions, conversions
from gis_analytics.mart_acquisition_daily
where 1=1 [[and tenant_id::text = {{tenant_id}}]] [[and site_id::text = {{site_id}}]]
  [[and date >= {{start_date}}]] [[and date <= {{end_date}}]]
  [[and gis_channel = {{channel}}]]
order by date desc, sessions desc, first_party_sessions desc
