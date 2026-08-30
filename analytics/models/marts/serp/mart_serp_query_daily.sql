select *,
  (best_own_rank is not null and best_own_rank <= 3) as own_top_3,
  (best_own_rank is not null and best_own_rank <= 10) as own_top_10,
  (best_own_rank is not null and best_own_rank <= 20) as own_top_20,
  case when best_own_rank is null then 0 else greatest(0, 101 - best_own_rank) end as owned_visibility_score,
  feature_count::numeric / nullif(organic_result_count + paid_result_count + feature_count, 0) as feature_density
from {{ ref('int_serp_query_daily') }}
