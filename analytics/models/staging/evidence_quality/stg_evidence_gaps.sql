select id as evidence_gap_id, evidence_package_id, collection_target_id, gap_type,
       description, desired_evidence_capability, urgency, identity_hash,
       planning_evidence_id, resolved_at, provenance_metadata, created_at, updated_at
from {{ source('gis_core', 'evidence_gap') }}

