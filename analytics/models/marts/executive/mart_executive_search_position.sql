select tenant_id, site_id, observed_date as date, device,
       tracked_queries_observed, queries_with_top_10_presence,
       tracked_queries_observed - queries_with_top_10_presence as queries_outside_top_10,
       {{ safe_divide('queries_with_top_10_presence', 'tracked_queries_observed') }} as top_10_rate,
       average_owned_visibility, average_top_10_churn,
       'OBSERVED_TRACKED_QUERY_SET' as coverage_semantics
from {{ ref('mart_serp_visibility_daily') }}
