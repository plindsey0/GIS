select id as observation_id, tenant_id, site_id, tracked_query_id, ingestion_run_id,
  data_source_connection_id as connection_id, rights_policy_id, rights_policy_version,
  provider_task_id, observation_key, observed_date, observed_at, search_engine,
  query_text, normalized_query, country_code, location_code, location_name,
  language_code, device, requested_depth, effective_start
from {{ source('gis_raw', 'serp_observation') }}
where effective_end is null
