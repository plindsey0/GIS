select r.tenant_id, r.site_id, s.market_definition_id, s.market_definition_version,
       s.collection_target_id, s.entity_key as query, s.source_series_key,
       s.window_start, s.window_end, s.signal_type, s.current_value, s.prior_value,
       s.absolute_change, s.relative_change, s.velocity, s.prior_velocity,
       s.acceleration, s.observation_count, s.evidence_strength, s.coverage_state,
       s.collection_regime_changed, s.policy_version, s.reasons_json
from {{ ref('stg_demand_signals') }} s
join {{ ref('stg_demand_analysis_runs') }} r using (analysis_run_id)
where s.entity_type = 'QUERY'

