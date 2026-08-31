select t.tenant_id, t.site_id, t.market_definition_id, t.market_definition_version,
       t.target_id, t.target_type, t.normalized_identity, t.display_value,
       d.decision_id, d.planning_run_id, d.evaluated_at, d.policy_version,
       d.priority_score, d.priority_tier, d.component_scores, d.unknown_components,
       d.computed_status, d.effective_status, d.computed_cadence,
       d.effective_cadence, d.primary_blocker, d.blockers_json,
       d.override_applied, d.explanation_json
from {{ ref('stg_collection_planning_decisions') }} d
join {{ ref('stg_collection_targets') }} t using (target_id)
