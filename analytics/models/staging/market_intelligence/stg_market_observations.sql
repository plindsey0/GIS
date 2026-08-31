select id as market_observation_id, tenant_id, organization_id, site_id,
       market_definition_id, market_definition_version, ingestion_run_id,
       rights_policy_id, rights_policy_version, effective_date, observed_at,
       country_code, language_code, device, method_key, method_version,
       semantic_class, coverage_status, configured_query_count, observed_query_count,
       query_coverage_rate, source_coverage, observation_key, content_hash,
       provider_reported_cost, estimated_cost, cost_currency, provenance_metadata,
       effective_start, effective_end, created_at
from {{ source('gis_raw', 'market_observation') }} where effective_end is null
