select id as execution_attempt_id, orchestration_run_id, trigger_type, attempt_number,
       status, worker_id, started_at, completed_at, ingestion_run_id,
       error_classification, error_detail, estimated_provider_cost,
       actual_provider_cost, created_at
from {{ source('gis_core', 'execution_attempt') }}
