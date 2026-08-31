select id as evidence_id, target_id, source_system, evidence_type, evidence_identifier,
       evidence_at, semantic_class, signal_name, signal_value, metadata, created_at
from {{ source('gis_core', 'collection_target_evidence') }}
