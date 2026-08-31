select p.tenant_id, p.site_id, g.*, p.condition_key, p.sufficiency
from {{ ref('stg_evidence_gaps') }} g
join {{ ref('stg_evidence_packages') }} p using (evidence_package_id)

