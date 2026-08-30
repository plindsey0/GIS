select sum(open_alert_count) as open_alerts
from gis_analytics.mart_executive_operations
where 1=1 [[and tenant_id::text={{tenant_id}}]] [[and site_id::text={{site_id}}]]
[[and current_date >= {{start_date}}]] [[and current_date <= {{end_date}}]]
