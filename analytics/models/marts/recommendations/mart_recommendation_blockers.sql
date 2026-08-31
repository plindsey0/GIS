select tenant_id, site_id, failure_reason, status,
 count(*) as blocked_run_count, max(started_at) as latest_blocked_at
from {{ ref('stg_recommendation_runs') }}
where status in ('BLOCKED','FAILED','NO_VALID_RECOMMENDATION')
group by tenant_id, site_id, failure_reason, status
