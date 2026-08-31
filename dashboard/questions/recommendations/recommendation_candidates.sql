select recommendation_id, opportunity_id, rank, fit, validation_state,
 target_metric_key, expected_direction, feasibility, measurement_readiness,
 rationale, accepted_intervention_id, created_at
from gis_analytics.mart_recommendation_candidates
where tenant_id = {{tenant_id}}::uuid and site_id = {{site_id}}::uuid
  and created_at::date between {{start_date}}::date and {{end_date}}::date
order by created_at desc, recommendation_id, rank
limit 100
