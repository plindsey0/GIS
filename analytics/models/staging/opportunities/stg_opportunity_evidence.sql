select id as opportunity_evidence_id, opportunity_evaluation_id, evidence_package_id,
       evidence_role, created_at
from {{ source('gis_core', 'opportunity_evidence') }}
