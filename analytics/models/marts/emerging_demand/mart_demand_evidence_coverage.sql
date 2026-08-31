select r.tenant_id, r.site_id, s.market_definition_id, s.market_definition_version,
       s.coverage_state, s.evidence_strength, s.collection_regime_changed,
       count(*) as signal_count,
       sum(case when s.signal_type = 'FIRST_OBSERVED' then 1 else 0 end) as newly_observed_count,
       sum(case when s.signal_type = 'INSUFFICIENT_HISTORY' then 1 else 0 end) as insufficient_history_count
from {{ ref('stg_demand_signals') }} s
join {{ ref('stg_demand_analysis_runs') }} r using (analysis_run_id)
group by 1, 2, 3, 4, 5, 6, 7
