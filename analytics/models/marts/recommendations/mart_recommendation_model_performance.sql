select tenant_id, site_id, provider_key, model_identifier, prompt_version,
 count(*) as run_count, count(*) filter (where status='SUCCEEDED') as successful_runs,
 count(*) filter (where repair_attempts > 0) as repaired_runs,
 count(*) filter (where status='FAILED') as failed_runs
from {{ ref('stg_recommendation_runs') }}
group by tenant_id, site_id, provider_key, model_identifier, prompt_version
