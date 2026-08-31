select id as recommendation_candidate_id, recommendation_id, intervention_type_id, rank,
 fit, validation_state::text as validation_state, parameters_json, target_metric_key,
 expected_direction::text as expected_direction, rationale, assumptions_json,
 limitations_json, feasibility::text as feasibility,
 measurement_readiness::text as measurement_readiness, validation_errors_json,
 accepted_intervention_id, created_at, updated_at
from {{ source('gis_core', 'recommendation_candidate') }}
