select id as orchestration_run_id, tenant_id, organization_id, site_id, pipeline_id,
       schedule_id, target_id, data_source_connection_id, rights_policy_id,
       upstream_run_id, ingestion_run_id, trigger_type, status, requested_at,
       scheduled_for, available_at, started_at, completed_at, backfill_start,
       backfill_end, estimated_provider_cost, actual_provider_cost, currency,
       error_classification, error_detail, configuration_json, created_at
from {{ source('gis_core', 'orchestration_run') }}
