select id as authority_observation_id, tenant_id, organization_id, site_id,
       data_source_connection_id, ingestion_run_id, rights_policy_id,
       rights_policy_version, provider, provider_task_id, target_type,
       target_domain, target_url, ownership, observed_date, observed_at,
       observation_scope, completeness, observation_key, content_hash,
       request_count, records_received, provider_reported_cost, estimated_cost,
       cost_currency, effective_start, effective_end, created_at
from {{ source('gis_raw', 'authority_observation') }}
