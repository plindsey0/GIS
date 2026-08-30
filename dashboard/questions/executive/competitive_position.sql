select date, observed_domain, evidence_domain, source_system, primary_metric, primary_value,
       secondary_metric, secondary_value, provider_metrics, semantics
from gis_analytics.mart_executive_competitive_position
where 1=1 [[and tenant_id::text={{tenant_id}}]] [[and site_id::text={{site_id}}]]
[[and date >= {{start_date}}]] [[and date <= {{end_date}}]]
order by date desc, evidence_domain, primary_value desc nulls last limit 100
