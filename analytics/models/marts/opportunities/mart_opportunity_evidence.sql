select o.tenant_id, o.site_id, o.opportunity_id, o.opportunity_type, o.status,
       e.opportunity_evaluation_id, x.evidence_package_id, x.evidence_role,
       p.sufficiency, p.rights_usability, p.corroboration, p.source_independence,
       p.conflict_count, p.limitations_json
from {{ ref('stg_opportunities') }} o
join {{ ref('stg_opportunity_evaluations') }} e using (opportunity_id)
join {{ ref('stg_opportunity_evidence') }} x using (opportunity_evaluation_id)
join {{ ref('stg_evidence_packages') }} p using (evidence_package_id)
