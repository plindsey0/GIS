select display_name, lifecycle_stage, capability_status, data_availability
from gis_analytics.mart_intelligence_coverage
where not implemented [[and tenant_id::text={{tenant_id}}]] [[and site_id::text={{site_id}}]]
[[and current_date >= {{start_date}}]] [[and current_date <= {{end_date}}]] order by sort_order
