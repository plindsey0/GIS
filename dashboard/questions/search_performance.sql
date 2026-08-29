select tenant_id, site_id, date, gsc_impressions as impressions, gsc_clicks as clicks,
  gsc_ctr as ctr, gsc_avg_position as average_position
from gis_analytics.mart_site_daily
where 1=1 [[and tenant_id::text = {{tenant_id}}]] [[and site_id::text = {{site_id}}]]
  [[and date >= {{start_date}}]] [[and date <= {{end_date}}]]
order by date
