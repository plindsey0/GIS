with attempts as (
  select orchestration_run_id, count(*) as attempt_count,
         count(*) filter (where status='FAILED') as failed_attempt_count
  from {{ ref('stg_execution_attempts') }} group by 1
)
select r.tenant_id, r.site_id, r.pipeline_id, r.created_at::date as date,
       count(*) as execution_count,
       count(*) filter (where r.status='SUCCEEDED') as successful_execution_count,
       count(*) filter (where r.status in ('FAILED','BLOCKED')) as failed_or_blocked_count,
       count(*) filter (where r.trigger_type='BACKFILL') as backfill_count,
       coalesce(sum(a.attempt_count),0) as attempt_count,
       coalesce(sum(a.failed_attempt_count),0) as failed_attempt_count,
       avg(extract(epoch from (r.completed_at-r.started_at))) filter (where r.completed_at is not null) as average_duration_seconds,
       sum(coalesce(r.estimated_provider_cost,0)) as estimated_provider_cost,
       sum(coalesce(r.actual_provider_cost,0)) as actual_provider_cost,
       min(r.currency) as currency,
       count(*) filter (where r.status='SUCCEEDED')::numeric/nullif(count(*),0) as success_rate
from {{ ref('stg_orchestration_runs') }} r
left join attempts a using (orchestration_run_id)
group by 1,2,3,4
