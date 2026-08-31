select id as outcome_id, intervention_id, measurement_contract_id, state::text as state,
 expectation_result, baseline_value, post_value, absolute_change, relative_change,
 evidence_sufficiency::text as evidence_sufficiency, completeness, causal_attribution,
 limitations_json, method_version, evaluated_at
from {{ source('gis_core', 'intervention_outcome') }}
