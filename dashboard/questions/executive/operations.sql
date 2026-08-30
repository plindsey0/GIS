select enabled_schedule_count, disabled_schedule_count, monitored_pipeline_count,
       fresh_pipeline_count, stale_pipeline_count, pipeline_freshness_rate,
       consecutive_failures, open_alert_count, critical_alert_count, latest_pipeline_success_at
from gis_analytics.mart_executive_operations
where 1=1 [[and tenant_id::text={{tenant_id}}]] [[and site_id::text={{site_id}}]]
[[and current_date >= {{start_date}}]] [[and current_date <= {{end_date}}]]
