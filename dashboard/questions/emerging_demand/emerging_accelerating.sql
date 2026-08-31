select query, signal_type, current_value, relative_change, velocity, acceleration,
       evidence_strength, coverage_state,
       case when signal_type = 'FIRST_OBSERVED' then 'Newly observed; not emerging' else signal_type end as executive_label
from gis_analytics.mart_demand_query_trend
where tenant_id = {{tenant_id}} and site_id = {{site_id}}
  and window_end between {{start_date}} and {{end_date}}
  and signal_type in ('EMERGING', 'ACCELERATING', 'SPIKE', 'FIRST_OBSERVED')
order by window_end desc, query

