select tenant_id, site_id, pipeline_id, due_at::date as obligation_date,
       count(*) as obligations_expected,
       count(*) filter (where status = 'SATISFIED' and satisfied_at <= due_at) as satisfied_on_time,
       count(*) filter (where status = 'SATISFIED' and satisfied_at > due_at) as recovered_late,
       count(*) filter (where status not in ('SATISFIED', 'EXPIRED') and due_at < now()) as unsatisfied,
       count(*) filter (where status in ('BLOCKED', 'FAILED')) as terminal_blocked_or_failed,
       avg(extract(epoch from (satisfied_at - due_at))) filter (where status = 'SATISFIED') as average_lateness_seconds,
       sum(attempt_count) as retry_and_attempt_count,
       count(*) filter (where status = 'SATISFIED')::numeric / nullif(count(*), 0) as satisfaction_rate
from {{ ref('stg_orchestration_obligations') }}
group by 1, 2, 3, 4
