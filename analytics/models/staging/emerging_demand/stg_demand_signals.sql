select id as demand_signal_id, analysis_run_id, market_definition_id,
       market_definition_version, collection_target_id, entity_type, entity_key,
       source_series_key, signal_type, window_key, window_start, window_end,
       current_value, prior_value, absolute_change, relative_change, velocity,
       prior_velocity, acceleration, evidence_strength, coverage_state,
       observation_count, collection_regime_changed, policy_version, reasons_json,
       metrics_json, identity_hash, created_at
from {{ source('gis_core', 'demand_signal') }}

