select condition_key as analytical_condition, sufficiency, count(*) as package_count,
       sum(case when source_independence in ('SAME_ROOT_SOURCE', 'UNKNOWN') then 1 else 0 end) as single_or_unknown_source,
       sum(case when rights_usability <> 'USABLE' then 1 else 0 end) as rights_limited,
       sum(case when conflict_count > 0 then 1 else 0 end) as material_conflicts
from gis_analytics.mart_evidence_quality_current
where tenant_id = {{tenant_id}} and site_id = {{site_id}}
  and period_end between {{start_date}} and {{end_date}}
group by 1, 2 order by 1, 2

