select round(100.0 * count(*) filter (where capability_status='OPERATIONAL') /
             nullif(count(*) filter (where implemented),0), 1) as operational_coverage_percent
from gis_analytics.mart_intelligence_coverage
where 1=1 [[and tenant_id::text={{tenant_id}}]] [[and site_id::text={{site_id}}]]
[[and current_date >= {{start_date}}]] [[and current_date <= {{end_date}}]]
