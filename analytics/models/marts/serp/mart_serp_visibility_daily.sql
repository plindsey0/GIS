select tenant_id, site_id, observed_date, device,
  count(*) as tracked_queries_observed,
  count(*) filter (where own_top_10) as queries_with_top_10_presence,
  avg(owned_visibility_score) as average_owned_visibility,
  avg(top_10_churn) as average_top_10_churn
from {{ ref('mart_serp_query_daily') }} group by 1,2,3,4
