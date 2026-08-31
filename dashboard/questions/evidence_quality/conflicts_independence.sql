select condition_key as analytical_condition, source_independence,
       corroboration, conflict_count, independent_source_count,
       sufficiency, count(*) as package_count
from gis_analytics.mart_evidence_quality_current
where tenant_id = {{tenant_id}} and site_id = {{site_id}}
  and period_end between {{start_date}} and {{end_date}}
group by 1, 2, 3, 4, 5, 6 order by conflict_count desc, package_count desc
