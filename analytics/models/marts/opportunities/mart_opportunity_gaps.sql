select o.tenant_id, o.site_id, o.opportunity_id, o.opportunity_type, o.status,
       o.evidence_sufficiency, o.limitations_json
from {{ ref('stg_opportunities') }} o
where o.status = 'WATCHING' or o.family = 'INTELLIGENCE_GAP'
