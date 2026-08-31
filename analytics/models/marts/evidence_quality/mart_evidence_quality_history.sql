select p.*, e.entity_type, e.canonical_key, c.contract_key, c.contract_version
from {{ ref('stg_evidence_packages') }} p
join {{ ref('stg_analytical_entities') }} e using (analytical_entity_id)
join {{ ref('stg_evidence_contracts') }} c using (evidence_contract_id)

