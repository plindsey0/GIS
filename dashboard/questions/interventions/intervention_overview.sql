select title as "Intervention contract", initcap(replace(status, '_', ' ')) as "Status",
 initcap(replace(feasibility, '_', ' ')) as "Feasibility",
 initcap(replace(measurement_readiness, '_', ' ')) as "Measurement readiness",
 primary_opportunity_id as "Opportunity", estimated_cost as "Estimated cost",
 actual_cost as "Actual cost", created_at as "Created"
from gis_analytics.mart_intervention_current
where tenant_id::text={{tenant_id}} and site_id::text={{site_id}}
 and created_at::date >= {{start_date}} and created_at::date <= {{end_date}}
order by created_at desc
