select date,
       case when search_data_available then organic_clicks end as organic_clicks,
       case when analytics_data_available then sessions end as sessions,
       case when telemetry_data_available then conversions end as conversions
from gis_analytics.mart_executive_site_daily
where 1=1 [[and tenant_id::text={{tenant_id}}]] [[and site_id::text={{site_id}}]]
[[and date >= {{start_date}}]] [[and date <= {{end_date}}]] order by date
