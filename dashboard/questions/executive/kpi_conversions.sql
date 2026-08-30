select case when bool_or(telemetry_data_available) then sum(conversions) end as conversions
from gis_analytics.mart_executive_site_daily
where 1=1 [[and tenant_id::text={{tenant_id}}]] [[and site_id::text={{site_id}}]]
[[and date >= {{start_date}}]] [[and date <= {{end_date}}]]
