select coverage_state, evidence_strength, collection_regime_changed,
       signal_count, newly_observed_count, insufficient_history_count
from gis_analytics.mart_demand_evidence_coverage
where tenant_id = {{tenant_id}} and site_id = {{site_id}}
  and {{start_date}} <= {{end_date}}
order by signal_count desc
