select r.*, o.family as opportunity_family, o.opportunity_type, o.priority,
 count(c.recommendation_candidate_id) as candidate_count
from {{ ref('stg_recommendations') }} r
join {{ ref('stg_opportunities') }} o using (opportunity_id)
left join {{ ref('stg_recommendation_candidates') }} c using (recommendation_id)
group by r.recommendation_id, r.recommendation_run_id, r.tenant_id, r.site_id,
 r.opportunity_id, r.analytical_entity_id, r.market_definition_id,
 r.market_definition_version, r.status, r.summary, r.assumptions_json,
 r.limitations_json, r.identity_hash, r.created_at, r.updated_at,
 o.family, o.opportunity_type, o.priority
