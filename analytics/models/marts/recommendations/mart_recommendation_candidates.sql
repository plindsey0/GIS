select r.tenant_id, r.site_id, r.opportunity_id, c.*
from {{ ref('stg_recommendation_candidates') }} c
join {{ ref('stg_recommendations') }} r using (recommendation_id)
