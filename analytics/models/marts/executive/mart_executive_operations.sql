with scope as (
  select tenant_id, id as site_id from {{ source('gis_core', 'site') }}
), schedules as (
  select tenant_id, site_id,
         count(*) as schedule_count,
         count(*) filter (where status='ENABLED') as enabled_schedule_count,
         count(*) filter (where status='DISABLED') as disabled_schedule_count
  from {{ source('gis_core', 'schedule_definition') }} group by 1,2
), freshness as (
  select tenant_id, site_id, count(*) as monitored_pipeline_count,
         count(*) filter (where not is_stale) as fresh_pipeline_count,
         count(*) filter (where is_stale) as stale_pipeline_count,
         max(last_successful_at) as latest_pipeline_success_at,
         sum(consecutive_failures) as consecutive_failures
  from {{ ref('mart_pipeline_freshness') }} group by 1,2
), alerts as (
  select tenant_id, site_id, count(*) filter (where status='OPEN') as open_alert_count,
         count(*) filter (where status='OPEN' and severity in ('ERROR','CRITICAL')) as critical_alert_count
  from {{ source('gis_core', 'operational_alert') }} group by 1,2
)
select s.tenant_id, s.site_id,
       coalesce(sc.schedule_count,0) as schedule_count,
       coalesce(sc.enabled_schedule_count,0) as enabled_schedule_count,
       coalesce(sc.disabled_schedule_count,0) as disabled_schedule_count,
       coalesce(f.monitored_pipeline_count,0) as monitored_pipeline_count,
       coalesce(f.fresh_pipeline_count,0) as fresh_pipeline_count,
       coalesce(f.stale_pipeline_count,0) as stale_pipeline_count,
       {{ safe_divide('f.fresh_pipeline_count', 'f.monitored_pipeline_count') }} as pipeline_freshness_rate,
       f.latest_pipeline_success_at, coalesce(f.consecutive_failures,0) as consecutive_failures,
       coalesce(a.open_alert_count,0) as open_alert_count,
       coalesce(a.critical_alert_count,0) as critical_alert_count
from scope s left join schedules sc using (tenant_id,site_id)
left join freshness f using (tenant_id,site_id)
left join alerts a on a.tenant_id=s.tenant_id and a.site_id is not distinct from s.site_id
