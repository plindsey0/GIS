select id as obligation_id, tenant_id, site_id, pipeline_id, schedule_id, target_id,
       data_source_connection_id, policy_version, window_start, window_end, due_at, expires_at,
       status, completion_outcome, attempt_count, next_attempt_at, satisfied_at,
       ingestion_run_id, failure_category, status_reason, created_at, updated_at
from {{ source('gis_core', 'orchestration_obligation') }}
