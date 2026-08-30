select
  id as observation_id, tenant_id, organization_id, site_id, data_source_connection_id,
  ingestion_run_id, rights_policy_id, normalized_url, resolved_url, canonical_url,
  domain, page_path, ownership_class, tracked_query_id, serp_result_id,
  external_search_observation_id, observed_at, retrieved_at, retrieval_status,
  http_status, render_mode, content_type, content_language, response_bytes, content_hash,
  raw_retained, truncated, retrieval_metadata
from {{ source('gis_raw', 'competitive_content_observation') }}
where effective_end is null
