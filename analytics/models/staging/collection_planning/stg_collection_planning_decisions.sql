select id as decision_id, planning_run_id, target_id, policy_version, priority_score,
       priority_tier, component_scores, unknown_components, computed_status,
       effective_status, computed_cadence, effective_cadence, primary_blocker,
       blockers_json, override_applied, explanation_json, evaluated_at, created_at
from {{ source('gis_core', 'collection_planning_decision') }}
