with scopes as (
  select tenant_id, id as site_id from {{ source('gis_core', 'site') }}
), registry as (
  select * from {{ ref('intelligence_capability_registry') }}
), pipelines as (
  select id, key, data_source_id from {{ source('gis_core', 'pipeline_definition') }}
), schedule_state as (
  select s.tenant_id, s.site_id, p.key as pipeline_key,
         count(*) as schedule_count,
         count(*) filter (where s.status='ENABLED') as enabled_schedule_count,
         count(*) filter (where s.status='DISABLED') as disabled_schedule_count
  from {{ source('gis_core', 'schedule_definition') }} s
  join pipelines p on p.id=s.pipeline_id group by 1,2,3
), connection_state as (
  select c.tenant_id, c.site_id, p.key as pipeline_key,
         count(*) as connection_count,
         count(*) filter (where c.status='ACTIVE') as active_connection_count,
         bool_or(
           coalesce(cp.derived_display_allowed, dp.derived_display_allowed, 'UNKNOWN') <> 'ALLOWED'
           or coalesce(cp.aggregation_allowed, dp.aggregation_allowed, 'UNKNOWN') <> 'ALLOWED'
         ) as dashboard_rights_blocked
  from {{ source('gis_core', 'data_source_connection') }} c
  join pipelines p on p.data_source_id=c.data_source_id
  join {{ source('gis_core', 'data_source') }} ds on ds.id=c.data_source_id
  left join {{ source('gis_core', 'data_rights_policy') }} cp on cp.id=c.rights_policy_id
  left join {{ source('gis_core', 'data_rights_policy') }} dp on dp.id=ds.default_rights_policy_id
  group by 1,2,3
), latest_run as (
  select tenant_id, site_id, pipeline_key, status as latest_run_status, completed_at as latest_run_at
  from (
    select r.tenant_id, r.site_id, p.key as pipeline_key, r.status, r.completed_at,
           row_number() over (partition by r.tenant_id,r.site_id,p.key order by r.created_at desc,r.orchestration_run_id desc) as ordinal
    from {{ ref('stg_orchestration_runs') }} r join pipelines p on p.id=r.pipeline_id
  ) ranked where ordinal=1
), alert_state as (
  select a.tenant_id, a.site_id, p.key as pipeline_key,
         count(*) filter (where a.status='OPEN') as open_alert_count
  from {{ source('gis_core', 'operational_alert') }} a
  left join pipelines p on p.id=a.pipeline_id group by 1,2,3
), combined as (
  select s.tenant_id, s.site_id, r.capability_key, r.display_name, r.lifecycle_stage,
         r.implemented, r.pipeline_key, r.freshness_days, r.rights_required, r.sort_order,
         coalesce(e.evidence_count,0) as evidence_count, e.latest_evidence_at,
         coalesce(sc.schedule_count,0) as schedule_count,
         coalesce(sc.enabled_schedule_count,0) as enabled_schedule_count,
         coalesce(sc.disabled_schedule_count,0) as disabled_schedule_count,
         coalesce(c.connection_count,0) as connection_count,
         coalesce(c.active_connection_count,0) as active_connection_count,
         coalesce(c.dashboard_rights_blocked,false) as dashboard_rights_blocked,
         lr.latest_run_status, lr.latest_run_at, coalesce(a.open_alert_count,0) as open_alert_count
  from scopes s cross join registry r
  left join {{ ref('int_capability_evidence') }} e
    on e.tenant_id=s.tenant_id and e.site_id=s.site_id and e.capability_key=r.capability_key
  left join schedule_state sc
    on sc.tenant_id=s.tenant_id and sc.site_id=s.site_id and sc.pipeline_key=r.pipeline_key
  left join connection_state c
    on c.tenant_id=s.tenant_id and c.site_id=s.site_id and c.pipeline_key=r.pipeline_key
  left join latest_run lr
    on lr.tenant_id=s.tenant_id and lr.site_id=s.site_id and lr.pipeline_key=r.pipeline_key
  left join alert_state a
    on a.tenant_id=s.tenant_id and a.site_id=s.site_id and a.pipeline_key=r.pipeline_key
)
select *,
  case
    when not implemented then 'NOT_IMPLEMENTED'
    when rights_required and dashboard_rights_blocked then 'BLOCKED_BY_RIGHTS'
    when latest_run_status in ('FAILED','BLOCKED') then 'FAILED'
    when evidence_count > 0 and open_alert_count > 0 then 'DEGRADED'
    when evidence_count > 0 and freshness_days > 0
      and latest_evidence_at < current_timestamp - make_interval(days => freshness_days) then 'STALE'
    when schedule_count > 0 and enabled_schedule_count = 0 then 'DISABLED'
    when evidence_count = 0 and (active_connection_count > 0 or schedule_count > 0) then 'IMPLEMENTED_NO_DATA'
    when evidence_count = 0 and connection_count > 0 then 'CONFIGURED'
    when evidence_count = 0 then 'IMPLEMENTED_NO_DATA'
    else 'OPERATIONAL'
  end as capability_status,
  case
    when evidence_count = 0 then 'NO_DATA'
    else 'AVAILABLE'
  end as data_availability
from combined
