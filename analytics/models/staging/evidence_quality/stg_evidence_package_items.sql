select id as evidence_package_item_id, evidence_package_id, evidence_key, evidence_type,
       evidence_reference_id, evidence_role, root_source_key, independence,
       method_compatibility, scope_compatibility, rights_usability, supports_claim,
       metadata, created_at
from {{ source('gis_core', 'evidence_package_item') }}

