select tenant_id, site_id, provider_key, model_identifier,
 count(*) as run_count, sum(provider_cost) as known_provider_cost,
 sum(input_tokens) as input_tokens, sum(output_tokens) as output_tokens
from {{ ref('stg_recommendation_runs') }}
group by tenant_id, site_id, provider_key, model_identifier
