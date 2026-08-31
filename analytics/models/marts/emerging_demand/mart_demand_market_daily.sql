select r.tenant_id, r.site_id, s.market_definition_id, s.market_definition_version,
       s.entity_key as market, s.window_end as date, s.current_value as observable_demand,
       s.absolute_change, s.relative_change, s.signal_type, s.evidence_strength,
       s.coverage_state, s.policy_version
from {{ ref('stg_demand_signals') }} s
join {{ ref('stg_demand_analysis_runs') }} r using (analysis_run_id)
where s.entity_type = 'MARKET'

