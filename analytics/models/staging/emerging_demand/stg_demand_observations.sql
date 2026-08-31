select id as demand_observation_id, tenant_id, site_id, market_definition_id,
       market_definition_version, collection_target_id, entity_type, entity_key,
       observed_date, observed_at, source_system, source_connection_id, source_record_id,
       source_metric, value, unit, resolution_days, country_code, language_code, device,
       semantic_class, coverage_state, method_key, method_version, rights_policy_id,
       observation_key, content_hash, provenance_metadata, effective_start, effective_end,
       created_at
from {{ source('gis_raw', 'demand_observation') }}

