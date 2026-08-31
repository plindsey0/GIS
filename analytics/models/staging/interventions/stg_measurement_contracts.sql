select id as measurement_contract_id, intervention_id, version, baseline_strategy,
 baseline_start, baseline_end, measurement_start, measurement_end, washout_days,
 comparison_method, minimum_evidence::text as minimum_evidence, freshness_days,
 exclusions_json, method_version, created_at, updated_at
from {{ source('gis_core', 'measurement_contract') }}
