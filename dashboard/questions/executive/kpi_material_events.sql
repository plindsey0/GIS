select count(*) filter (where is_material) as material_changes
from gis_analytics.mart_executive_recent_events
where 1=1 [[and tenant_id::text={{tenant_id}}]] [[and site_id::text={{site_id}}]]
[[and event_time::date >= {{start_date}}]] [[and event_time::date <= {{end_date}}]]
