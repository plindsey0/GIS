select tenant_id, site_id, opportunity_id, count(*) as recommendation_count,
 count(*) filter (where status in ('ACCEPTED','PARTIALLY_ACCEPTED')) as accepted_count,
 max(created_at) as latest_recommendation_at
from {{ ref('stg_recommendations') }}
group by tenant_id, site_id, opportunity_id
