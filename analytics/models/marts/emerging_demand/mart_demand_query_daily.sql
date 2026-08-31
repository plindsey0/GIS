select r.tenant_id, r.site_id, s.market_definition_id, s.market_definition_version,
       s.collection_target_id, s.entity_key as query, s.window_end as date,
       s.current_value as observable_demand, s.metrics_json ->> 'unit' as unit,
       s.metrics_json ->> 'source_system' as source_system, s.coverage_state,
       s.evidence_strength, s.policy_version
from {{ ref('stg_demand_signals') }} s
join {{ ref('stg_demand_analysis_runs') }} r using (analysis_run_id)
where s.entity_type = 'QUERY'

