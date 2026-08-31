select o.tenant_id, o.site_id, o.opportunity_id, o.family, o.opportunity_type,
       e.opportunity_evaluation_id, e.evaluated_at, e.computed_status, e.qualifies,
       e.reasons_json, e.blockers_json, e.metrics_json
from {{ ref('stg_opportunity_evaluations') }} e
join {{ ref('stg_opportunities') }} o using (opportunity_id)
