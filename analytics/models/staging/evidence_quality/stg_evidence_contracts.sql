select id as evidence_contract_id, contract_key, contract_version, description,
       requirements_json, active, created_at, updated_at
from {{ source('gis_core', 'evidence_contract') }}

