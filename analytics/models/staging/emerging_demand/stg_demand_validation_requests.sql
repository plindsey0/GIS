select id as validation_request_id, signal_id, collection_target_id, reason,
       desired_evidence_capability, urgency, status, expires_at, identity_hash,
       provenance_metadata, created_at, updated_at
from {{ source('gis_core', 'demand_validation_request') }}

