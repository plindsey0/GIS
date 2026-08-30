select sort_order, display_name, lifecycle_stage, capability_status, data_availability,
       evidence_count, latest_evidence_at, enabled_schedule_count, disabled_schedule_count,
       latest_run_status, open_alert_count
from gis_analytics.mart_intelligence_coverage
where 1=1 [[and tenant_id::text={{tenant_id}}]] [[and site_id::text={{site_id}}]]
[[and current_date >= {{start_date}}]] [[and current_date <= {{end_date}}]] order by sort_order
