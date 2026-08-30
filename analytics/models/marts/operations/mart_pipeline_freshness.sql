select f.tenant_id, f.site_id, f.pipeline_id, f.schedule_id,
       p.key as pipeline_key, s.name as schedule_name,
       f.last_attempted_at, f.last_successful_at, f.expected_next_execution_at,
       f.freshness_sla_seconds, f.stale_since, f.consecutive_failures,
       (f.stale_since is not null) as is_stale,
       extract(epoch from (current_timestamp-f.last_successful_at)) as seconds_since_success
from {{ source('gis_core', 'freshness_state') }} f
join {{ source('gis_core', 'pipeline_definition') }} p on p.id=f.pipeline_id
left join {{ source('gis_core', 'schedule_definition') }} s on s.id=f.schedule_id
