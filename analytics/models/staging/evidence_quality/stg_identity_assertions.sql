select id as identity_assertion_id, subject_entity_id, object_entity_id, relationship,
       computed_strength, effective_strength, resolution_method, method_version,
       assertion_hash, status, evidence_json, override_applied, override_reason,
       override_actor, effective_start, effective_end, created_at
from {{ source('gis_core', 'identity_assertion') }}

