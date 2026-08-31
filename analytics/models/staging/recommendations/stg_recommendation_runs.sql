select id as recommendation_run_id, tenant_id, site_id, opportunity_id,
 recommendation_policy_id, status::text as status, provider_key, model_identifier,
 prompt_version, context_hash, started_at, completed_at, input_tokens, output_tokens,
 provider_cost, validation_errors_json, repair_attempts, failure_reason, created_at
from {{ source('gis_core', 'recommendation_run') }}
