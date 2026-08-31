select condition_key as analytical_condition, gap_type as missing_evidence,
       desired_evidence_capability, urgency, sufficiency, count(*) as affected_claims
from gis_analytics.mart_evidence_gaps
where tenant_id = {{tenant_id}} and site_id = {{site_id}}
  and created_at::date between {{start_date}} and {{end_date}}
group by 1, 2, 3, 4, 5 order by affected_claims desc

