select id as observation_id, tenant_id, organization_id, site_id,
       data_source_connection_id, ingestion_run_id, rights_policy_id,
       domain, normalized_url, ownership_class, observation_scope,
       observed_at, collected_at, collection_status, http_status, render_mode,
       content_hash, signature_version, collection_metadata
from {{ source('gis_raw', 'technology_observation') }}
where effective_end is null
