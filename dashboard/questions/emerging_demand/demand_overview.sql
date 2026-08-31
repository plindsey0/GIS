select signal_type as demand_state, count(*) as target_count,
       evidence_strength, coverage_state,
       'Observable demand only; not an opportunity assessment.' as semantics
from gis_analytics.mart_demand_query_trend
where tenant_id = {{tenant_id}} and site_id = {{site_id}}
  and window_end between {{start_date}} and {{end_date}}
group by 1, 3, 4 order by target_count desc

