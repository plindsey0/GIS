select recommendation_id, opportunity_id, opportunity_family, opportunity_type,
 priority, status as recommendation_status, candidate_count, summary, created_at
from gis_analytics.mart_recommendation_current
where tenant_id = {{tenant_id}}::uuid and site_id = {{site_id}}::uuid
  and created_at::date between {{start_date}}::date and {{end_date}}::date
order by case status when 'READY_FOR_REVIEW' then 0 else 1 end, created_at desc
limit 50
