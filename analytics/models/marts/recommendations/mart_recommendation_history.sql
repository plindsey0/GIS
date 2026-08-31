select r.tenant_id, r.site_id, r.recommendation_id, r.opportunity_id,
 v.recommendation_review_id, v.decision, v.reviewer, v.reason_category, v.comment,
 v.reviewed_at
from {{ ref('stg_recommendations') }} r
join {{ ref('stg_recommendation_reviews') }} v using (recommendation_id)
