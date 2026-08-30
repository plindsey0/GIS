select id as evidence_id, tenant_id, site_id, competitive_event_id, source_asset,
       source_record_id, observation_time, evidence_role, semantic_class,
       confidence, data_source_connection_id, ingestion_run_id,
       rights_policy_id, rights_policy_version, created_at
from {{ source('gis_core', 'competitive_event_evidence') }}
